import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { chatApi, sessionApi } from '../api/index.js'

/**
 * Chat 状态管理 Composable
 * 状态定义在模块级别，确保所有调用方共享同一份数据
 */
const sessions = ref([])
const currentSessionId = ref(null)
const currentSessionName = ref('')
const messages = ref([])
const isLoading = ref(false)
const isStreaming = ref(false)
const streamingEnabled = ref(true)
let abortController = null
let sessionPollTimer = null
let pollingStarted = false

// ─── 主动推送 / 系统通知 ───
const currentView = ref('chat')       // 'chat' | 'push' | 'notification'
const pushMessages = ref([])           // 💬 普通消息（可回复）
const systemNotifications = ref([])    // 🔔 系统通知（只读）
const pushUnread = ref(0)
const notificationUnread = ref(0)
let sseClient = null
const messagesCache = {}  // 会话消息缓存 { sessionId: mergedMessages }
const CACHE_MAX = 20       // 最多缓存20个会话
let pushMessagesCache = null  // 普通消息缓存（移到这里统一管理）
const PUSH_CACHE_MAX = 1000    // 普通消息缓存上限（匹配后端）
let pushPage = 1           // 当前加载的页数
let pushTotal = 0           // 后端总消息数
const PUSH_PAGE_SIZE = 200  // 每页加载条数

// 自动清理最旧的缓存
function trimCache() {
  const keys = Object.keys(messagesCache)
  if (keys.length > CACHE_MAX) {
    const toDelete = keys.length - CACHE_MAX
    // 删除最早的 toDelete 个（按添加顺序）
    for (let i = 0; i < toDelete; i++) {
      delete messagesCache[keys[i]]
    }
  }
}

export function useChat() {
  
  // ─── SSE 连接 ───
  const connectSSE = () => {
    if (sseClient) return
    try {
      sseClient = new EventSource('/api/events')
      sseClient.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'system_event' || data.target === 'notification') {
            console.log('[SSE] 收到系统通知:', data.content?.slice(0, 30))
            systemNotifications.value.push(data)
            if (currentView.value !== 'notification') {
              notificationUnread.value++
            }
          }
          else {
            console.log('[SSE] 收到普通消息:', data.content?.slice(0, 30))
            const newMsg = {
              role: 'assistant',
              content: data.content || '',
              source: data.source || '',
              type: data.type || 'active_push',
              timestamp: data.created_at || Date.now() / 1000,
              id: data.id,
              priority: data.priority,
              reasoning: data.reasoning_content || '',
            }
            // 焦点识别：有活跃会话 → 注入当前对话；无会话 → 走普通消息频道
            if (currentSessionId.value) {
              messages.value.push(newMsg)
              if (messagesCache[currentSessionId.value]) {
                messagesCache[currentSessionId.value].push(newMsg)
              }
            } else {
              pushMessages.value.push(newMsg)
              if (pushMessagesCache) {
                pushMessagesCache = [...pushMessagesCache, newMsg]
              }
              if (currentView.value !== 'push') {
                pushUnread.value++
              }
            }
          }
        } catch (err) {
          console.warn('[SSE] 解析消息失败:', err)
        }
      }
      sseClient.onerror = () => {
        // 浏览器 EventSource 自带自动重连，不需要手动处理
        console.warn('[SSE] 连接断开，浏览器将自动重连...')
      }
      console.log('[SSE] 已连接')
    } catch (e) {
      console.warn('[SSE] 连接失败:', e)
    }
  }

  const disconnectSSE = () => {
    if (sseClient) {
      sseClient.close()
      sseClient = null
      console.log('[SSE] 已断开')
    }
  }

  // 切换视图
  const switchView = (view) => {
    currentView.value = view
    // 离开会话视图时清除选中的会话高亮
    if (view !== 'chat') {
      currentSessionId.value = null
    }
    // 上报焦点给后端（主动引擎据此调整推送策略）
    reportUserFocus(view)
    if (view === 'push') {
      pushUnread.value = 0
      // 有缓存就直接用，不用重新拉取
      if (!pushMessagesCache) {
        loadPushMessages()
      }
    }
    if (view === 'notification') {
      notificationUnread.value = 0
      loadNotifications()  // 进入系统通知视图时加载历史
    }
  }

  // 上报用户焦点
  const reportUserFocus = async (view) => {
    try {
      const resp = await fetch('/api/user/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ view, session_id: currentSessionId.value }),
      })
      if (!resp.ok) console.warn('[Focus] 上报失败:', resp.status)
    } catch (e) {
      // 静默失败，不影响体验
    }
  }

  // 标记已读
  const markPushRead = () => { pushUnread.value = 0 }
  const markNotificationRead = () => { notificationUnread.value = 0 }

  // ─── 加载普通消息历史 ───

  const loadPushMessages = async () => {
    pushPage = 1  // 重置页码
    pushTotal = 0
    pushMessagesCache = null
    try {
      const res = await fetch(`/api/push/messages?page=1&page_size=${PUSH_PAGE_SIZE}`).then(r => r.json())
      if (res && res.items) {
        pushTotal = res.total || 0
        // 后端返回 DESC（最新在前），反转成 ASC（最早在前）像微信一样
        const normalized = res.items.reverse().map(item => ({
          role: item.role || 'assistant',
          content: item.content || '',
          source: item.source || '',
          type: item.type || 'chat_reply',
          timestamp: item.created_at || item.timestamp || Date.now() / 1000,
          id: item.id,
          priority: item.priority,
          reasoning: item.reasoning_content || '',  // 兼容 reasoning 字段
        }))
        pushMessagesCache = normalized
        pushMessages.value = normalized
      }
    } catch (e) {
      console.warn('[Push] 加载历史消息失败:', e)
    }
  }

  // ─── 加载更多普通消息（分页加载更早的消息） ───
  const loadMorePushMessages = async () => {
    const nextPage = pushPage + 1
    try {
      const res = await fetch(`/api/push/messages?page=${nextPage}&page_size=${PUSH_PAGE_SIZE}`).then(r => r.json())
      if (res && res.items && res.items.length > 0) {
        pushPage = nextPage
        pushTotal = res.total || 0
        // 反转成 ASC，拼接到已有消息前面（更早的消息在顶部）
        const older = res.items.reverse().map(item => ({
          role: item.role || 'assistant',
          content: item.content || '',
          source: item.source || '',
          type: item.type || 'chat_reply',
          timestamp: item.created_at || item.timestamp || Date.now() / 1000,
          id: item.id,
          priority: item.priority,
          reasoning: item.reasoning_content || '',
        }))
        // 更老的消息放到前面（ASC 顺序，最早的在上）
        pushMessagesCache = [...older, ...(pushMessagesCache || [])]
        pushMessages.value = pushMessagesCache
      }
    } catch (e) {
      console.warn('[Push] 加载更多消息失败:', e)
    }
  }

  // ─── 是否还有更多普通消息可加载 ───
  const hasMorePushMessages = computed(() => {
    return pushMessagesCache ? pushMessagesCache.length < pushTotal : false
  })

  // ─── 加载系统通知历史 ───
  const loadNotifications = async () => {
    try {
      const res = await fetch('/api/notifications?page=1&page_size=200').then(r => r.json())
      if (res && res.items) {
        const existingIds = new Set(systemNotifications.value.map(n => n.id))
        const history = res.items.filter(n => !existingIds.has(n.id))
        systemNotifications.value = [...history.reverse(), ...systemNotifications.value]
      }
    } catch (e) {
      console.warn('[Notification] 加载通知历史失败:', e)
    }
  }
  
  // 启动会话列表自动刷新（每5秒）
  const startSessionPolling = () => {
    if (pollingStarted) return
    pollingStarted = true
    sessionPollTimer = setInterval(loadSessions, 30000)
  }
  
  // 停止会话列表自动刷新
  const stopSessionPolling = () => {
    if (sessionPollTimer) {
      clearInterval(sessionPollTimer)
      sessionPollTimer = null
    }
    pollingStarted = false
  }
  
  // 加载会话列表
  const loadSessions = async () => {
    try {
      const result = await sessionApi.list()
      sessions.value = Array.isArray(result) ? result : (result.sessions || [])
    } catch (e) {
      console.error('加载会话列表失败:', e)
    }
  }
  
  // 创建新会话
  const createSession = async (name) => {
    try {
      const result = await sessionApi.create(name || '')
      await loadSessions()
      const newSessionId = result.session_id
      await selectSession(newSessionId)
      return newSessionId
    } catch (e) {
      console.error('创建会话失败:', e)
      throw e
    }
  }
  
  // 选择会话
  const selectSession = async (sessionId) => {
    currentSessionId.value = sessionId
    messages.value = []
    
    // 查找会话名称
    const session = sessions.value.find(s => s.id === sessionId || s.session_id === sessionId)
    if (session) {
      currentSessionName.value = session.name || session.title || '未命名会话'
    }
    
    // 有缓存直接用
    if (messagesCache[sessionId]) {
      messages.value = messagesCache[sessionId]
      return
    }
    
    // 加载历史消息
    try {
      const result = await sessionApi.getMessages(sessionId)
      const rawMessages = result.messages || []
      
      // 归一化：reasoning_content → reasoning（兼容新旧数据）
      // 过滤旧数据：跳过 [你上轮的思考过程] 及相关消息 + reasoning_content 映射
      const normalized = []
      let skipNext = false
      for (const msg of rawMessages) {
          if (msg.role === 'user' && msg.content === '[你上轮的思考过程]') {
              skipNext = true  // 跳过这条，下条也跳过
              continue
          }
          if (skipNext && msg.role === 'assistant') {
              skipNext = false  // 跳过旧格式的 reasoning 内容
              continue
          }
          skipNext = false
          if (msg.role === 'assistant' && msg.reasoning_content) {
              normalized.push({ ...msg, reasoning: msg.reasoning_content })
          } else {
              normalized.push(msg)
          }
      }
      
      messagesCache[sessionId] = normalized
      trimCache()
      messages.value = normalized
    } catch (e) {
      console.error('加载消息失败:', e)
      messages.value = []
    }
  }
  
  // 删除会话
  const deleteSession = async (sessionId) => {
    try {
      await sessionApi.delete(sessionId)
      delete messagesCache[sessionId]  // 清除缓存
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        messages.value = []
      }
      await loadSessions()
    } catch (e) {
      console.error('删除会话失败:', e)
      throw e
    }
  }
  
  // 重命名会话
  const renameSession = async (sessionId, newName) => {
    try {
      await sessionApi.rename(sessionId, newName)
      if (currentSessionId.value === sessionId) {
        currentSessionName.value = newName
      }
      await loadSessions()
    } catch (e) {
      console.error('重命名会话失败:', e)
      throw e
    }
  }
  
  // 发送消息（支持流式/非流式）
  const sendMessage = async (content, fileIds = []) => {
    if (!currentSessionId.value || isStreaming.value) return
    
    // 发送新消息时清除缓存
    delete messagesCache[currentSessionId.value]
    
    // 添加用户消息
    const userMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }
    // 添加文件信息到用户消息
    if (fileIds.length > 0) userMessage.files = fileIds.map(id => ({ name: id }))
    messages.value.push(userMessage)
    
    // 创建 AI 消息占位
    const aiMessageIndex = messages.value.length
    messages.value.push({
      role: 'assistant',
      content: '',
      reasoning: '',
      tools_used: [],
      isStreaming: streamingEnabled.value,
      timestamp: new Date().toISOString(),
    })
    
    isStreaming.value = true
    isLoading.value = true
    abortController = new AbortController()
    
    if (streamingEnabled.value) {
      // 流式模式
      try {
        const response = await chatApi.sendStream(content, currentSessionId.value, fileIds)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        // 按双换行分割 SSE 事件（兼容 data 中包含换行的情况）
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        
        for (const part of parts) {
          if (!part.trim()) continue
          // 提取所有 data: 行的内容并拼接
          const dataLines = part.split('\n').filter(l => l.startsWith('data: '))
          if (dataLines.length === 0) continue
          const dataStr = dataLines.map(l => l.slice(6)).join('\n')
          if (!dataStr.trim()) continue
          
          try {
            const data = JSON.parse(dataStr)
            const aiMsg = messages.value[aiMessageIndex]
            
            switch (data.type) {
                case 'text':
                  aiMsg.content += data.content || data.text || ''
                  break
                case 'reasoning':
                  aiMsg.reasoning += data.content || data.text || ''
                  break
                case 'tool_used':
                  aiMsg.tools_used.push(data)
                  break
                case 'done':
                  aiMsg.isStreaming = false
                  isStreaming.value = false
                  isLoading.value = false
                  // 自动命名：消息达到 10 条且还未自定义标题时触发
                  const totalMsgs = messages.value.filter(m => m.role !== 'system').length
                  const session = sessions.value.find(s => 
                    (s.id || s.session_id) === currentSessionId.value
                  )
                  const isDefaultTitle = session && (
                    !session.name || 
                    session.name.startsWith('对话 ') || 
                    session.name === '新对话' ||
                    session.name === '未命名会话'
                  )
                  if (totalMsgs >= 10 && isDefaultTitle) {
                    try {
                      await sessionApi.autoName(currentSessionId.value)
                    } catch (e) {}
                  }
                  await loadSessions()
                  break
                case 'error':
                  aiMsg.content += `\n[错误: ${data.message || '未知错误'}]`
                  aiMsg.isStreaming = false
                  isStreaming.value = false
                  isLoading.value = false
                  break
              }
              
            // 触发响应式更新
            messages.value = [...messages.value]
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        console.error('发送消息失败:', e)
        if (messages.value[aiMessageIndex]) {
          messages.value[aiMessageIndex].content += `\n[错误: ${e.message}]`
          messages.value[aiMessageIndex].isStreaming = false
        }
      }
      isStreaming.value = false
      isLoading.value = false
  }
    } else {
      // 非流式模式
      try {
        const result = await chatApi.send(content, currentSessionId.value, fileIds)
        const aiMsg = messages.value[aiMessageIndex]
        aiMsg.content = result.reply || ''
        aiMsg.isStreaming = false
        if (result.reasoning) aiMsg.reasoning = result.reasoning
        if (result.tools_used) aiMsg.tools_used = result.tools_used
        isStreaming.value = false
        isLoading.value = false
        messages.value = [...messages.value]
        loadSessions()
      } catch (e) {
        console.error('发送消息失败:', e)
        if (messages.value[aiMessageIndex]) {
          messages.value[aiMessageIndex].content += `\n[错误: ${e.message}]`
          messages.value[aiMessageIndex].isStreaming = false
        }
        isStreaming.value = false
        isLoading.value = false
      }
    }
  }
  
  // 停止生成
  const stopGeneration = () => {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    isStreaming.value = false
    isLoading.value = false
    
    // 标记当前流式消息为完成
    const streamingMsg = messages.value.find(m => m.isStreaming)
    if (streamingMsg) {
      streamingMsg.isStreaming = false
    }
  }
  
  // 自动命名
  const autoNameSession = async (sessionId) => {
    try {
      await sessionApi.autoName(sessionId || currentSessionId.value)
      await loadSessions()
    } catch (e) {
      console.error('自动命名失败:', e)
    }
  }
  
  return {
    sessions,
    currentSessionId,
    currentSessionName,
    messages,
    isLoading,
    isStreaming,
    loadSessions,
    createSession,
    selectSession,
    deleteSession,
    renameSession,
    sendMessage,
    stopGeneration,
    streamingEnabled,
    autoNameSession,
    startSessionPolling,
    stopSessionPolling,
    // ─── 主动推送 / 系统通知 ───
    currentView,
    pushMessages,
    systemNotifications,
    pushUnread,
    notificationUnread,
    connectSSE,
    disconnectSSE,
    switchView,
    markPushRead,
    markNotificationRead,
    loadPushMessages,
    loadNotifications,
    loadMorePushMessages,
    hasMorePushMessages,
  }
}
