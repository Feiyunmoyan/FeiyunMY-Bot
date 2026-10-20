<template>
  <div class="flex w-full h-full">
    <!-- 左侧会话面板 -->
    <SessionSidebar 
      @select-session="selectSession"
      @new-session="createNewSession"
      @delete-session="handleDeleteSession"
      @rename-session="handleRenameSession"
      @auto-name="handleAutoName"
      @switch-view="switchView"
    />
    
    <!-- 右侧内容 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 会话模式 -->
      <template v-if="chat.currentView.value === 'chat'">
        <ChatMain 
          :messages="chat.messages.value"
          :session-name="chat.currentSessionName.value"
          :is-streaming="chat.isStreaming.value"
          @send="handleSend"
          @stop="stopPushStream"
          @auto-name="handleAutoName"
        />
      </template>
      
      <!-- 💬 普通消息（可回复） -->
      <template v-else-if="chat.currentView.value === 'push'">
        <PushPanel
          :messages="chat.pushMessages.value"
          :is-streaming="chat.isStreaming.value"
          :has-more="chat.hasMorePushMessages.value"
          title="普通消息"
          icon="💬"
          :show-input="true"
          @send="handlePushReply"
          @stop="chat.stopGeneration()"
          @load-more="chat.loadMorePushMessages()"
        />
      </template>
      
      <!-- 🔔 系统通知（只读） -->
      <template v-else-if="chat.currentView.value === 'notification'">
        <PushPanel
          :messages="chat.systemNotifications.value"
          title="系统通知"
          icon="🔔"
          :show-input="false"
          variant="notification"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue'
import SessionSidebar from './SessionSidebar.vue'
import ChatMain from './ChatMain.vue'
import PushPanel from './PushPanel.vue'
import { useChat } from '@/composables/useChat'

const chat = useChat()

onMounted(() => {
  chat.loadSessions()
  chat.startSessionPolling()
})

onBeforeUnmount(() => {
  chat.stopSessionPolling()
})

const selectSession = (id) => {
  chat.switchView('chat')
  chat.selectSession(id)
}
const createNewSession = async (name) => {
  await chat.createSession(name)
  chat.switchView('chat')
}
const handleDeleteSession = async (id) => {
  await chat.deleteSession(id)
}
const handleRenameSession = async (id, name) => {
  await chat.renameSession(id, name)
}
const handleAutoName = async () => {
  await chat.autoNameSession()
}
const handleSend = async (data) => {
  const text = typeof data === 'string' ? data : (data.text || '')
  const fileIds = data.fileIds || []
  if (text || fileIds.length > 0) await chat.sendMessage(text, fileIds)
}
const switchView = (view) => chat.switchView(view)
let lastPushText = ''
let lastPushTime = 0
let pushAbortController = null

const handlePushReply = async (data) => {
  const text = typeof data === 'string' ? data : (data.text || '')
  const fileIds = data.fileIds || []
  if (!text) return
  // 防抖：同一文本1秒内不重复发送
  const now = Date.now()
  if (text === lastPushText && now - lastPushTime < 1000) {
    console.log('[Push] 防抖: 忽略重复消息')
    return
  }
  lastPushText = text
  lastPushTime = now
  
  // 添加用户消息
  chat.pushMessages.value = [...chat.pushMessages.value, {
    role: 'user',
    content: text,
    timestamp: Date.now() / 1000,
  }]
  
  // 创建 AI 消息占位（流式）
  const aiIndex = chat.pushMessages.value.length
  chat.pushMessages.value = [...chat.pushMessages.value, {
    role: 'assistant',
    content: '',
    reasoning: '',
    isStreaming: true,
    timestamp: Date.now() / 1000,
  }]
  
  try {
    pushAbortController = new AbortController()
    const res = await fetch('/api/push/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
      signal: pushAbortController.signal,
    })
    
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split("\n\n")
      buffer = parts.pop() || ''
      
      for (const part of parts) {
        if (!part.trim()) continue
        const dataLines = part.split("\n").filter(l => l.startsWith("data: "))
        if (dataLines.length === 0) continue
        const dataStr = dataLines.map(l => l.slice(6)).join("\n")
        if (!dataStr.trim()) continue
        
        try {
          const event = JSON.parse(dataStr)
          const aiMsg = chat.pushMessages.value[aiIndex]
          if (!aiMsg) continue
          
          switch (event.type) {
            case 'text':
              aiMsg.content += event.content || ''
              break
            case 'reasoning':
              aiMsg.reasoning += event.content || ''
              break
            case 'tool_used':
              if (!aiMsg.tools_used) aiMsg.tools_used = []
              aiMsg.tools_used.push(event)
              break
            case 'done':
              aiMsg.isStreaming = false
              break
            case 'error':
              aiMsg.content += `
[错误: ${event.message || '未知错误'}]`
              aiMsg.isStreaming = false
              break
          }
          chat.pushMessages.value = [...chat.pushMessages.value]
        } catch (e) {}
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      const aiMsg = chat.pushMessages.value[aiIndex]
      if (aiMsg) {
        aiMsg.content += `
[错误: ${e.message}]`
        aiMsg.isStreaming = false
        chat.pushMessages.value = [...chat.pushMessages.value]
      }
    }
  }
}

const stopPushStream = () => {
  if (pushAbortController) {
    pushAbortController.abort()
    pushAbortController = null
  }
  const streamingMsg = chat.pushMessages.value.find(m => m.isStreaming)
  if (streamingMsg) streamingMsg.isStreaming = false
}
</script>
