<template>
  <div class="panel">
    <h2 class="text-2xl font-bold text-text-primary mb-6">对话数据</h2>
    
    <div class="card mb-4">
      <div class="flex gap-3">
        <input v-model="searchQuery" class="input-base flex-1" placeholder="搜索会话..." />
        <button @click="loadSessions" class="btn-secondary">刷新</button>
      </div>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
    <div v-else-if="filteredSessions.length === 0" class="card"><EmptyState title="暂无对话数据" /></div>
    <div v-else class="card overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-text-secondary border-b border-border">
            <th class="pb-3 font-medium">会话名称</th>
            <th class="pb-3 font-medium">消息数</th>
            <th class="pb-3 font-medium">最后活跃</th>
            <th class="pb-3 font-medium w-48">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="session in filteredSessions" :key="session.id || session.session_id" class="border-b border-border last:border-0">
            <td class="py-3 text-text-primary">{{ session.name || session.title || '未命名' }}</td>
            <td class="py-3 text-text-secondary">{{ session.message_count || '-' }}</td>
            <td class="py-3 text-text-secondary text-xs">{{ formatTime(session.updated_at || session.last_active) }}</td>
            <td class="py-3">
              <div class="flex items-center gap-2">
                <button @click="previewSession(session.id || session.session_id)" class="text-info hover:underline text-xs">预览</button>
                <button @click="deleteSession(session.id || session.session_id, session.name || session.title)" class="text-error hover:underline text-xs">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 预览浮窗 -->
    <Modal :show="showPreview" title="会话预览" size="full" @update:show="showPreview = false">
      <div v-if="previewLoading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
      <div v-else-if="previewMessages.length === 0" class="text-center py-12 text-text-secondary text-sm">暂无消息</div>
      <div v-else class="max-w-4xl mx-auto space-y-4 py-2 max-h-[60vh] overflow-y-auto">
        <div
          v-for="(msg, idx) in previewMessages"
          :key="idx"
          class="flex gap-3"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <!-- AI头像 -->
          <div v-if="msg.role === 'assistant'" class="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center mt-1">
            <svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
            </svg>
          </div>
          <!-- 消息气泡 -->
          <div
            :class="[
              'max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
              msg.role === 'user'
                ? 'bg-primary text-white rounded-br-md'
                : 'bg-bg-card border border-border rounded-bl-md text-text-primary'
            ]"
          >
            <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)"></div>
            <div v-else class="whitespace-pre-wrap">{{ msg.content }}</div>
            <div class="mt-2 text-[10px] text-text-secondary text-right">{{ formatTimestamp(msg.timestamp) }}</div>
          </div>
          <!-- 用户头像 -->
          <div v-if="msg.role === 'user'" class="flex-shrink-0 w-8 h-8 rounded-full bg-bg-hover flex items-center justify-center mt-1">
            <svg class="w-4 h-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
          </div>
        </div>
      </div>
    </Modal>
    
    <ConfirmDialog
      :show="showDeleteConfirm"
      title="删除会话"
      :message="`确定要删除会话「${deleteTargetName}」吗？此操作不可撤销。`"
      @confirm="confirmDeleteSession"
      @update:show="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { sessionApi } from '@/api/index.js'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const sessions = ref([])
const loading = ref(false)
const searchQuery = ref('')
const showDeleteConfirm = ref(false)
const deleteTargetId = ref('')
const deleteTargetName = ref('')

// 预览相关
const showPreview = ref(false)
const previewLoading = ref(false)
const previewMessages = ref([])

// 过滤掉内部频道（__push_channel__ 和开头带 __ 的）
const filteredSessions = computed(() => {
  let list = sessions.value.filter(s => {
    const id = s.id || s.session_id || ''
    return !id.startsWith('__')
  })
  if (!searchQuery.value) return list
  const q = searchQuery.value.toLowerCase()
  return list.filter(s => (s.name || s.title || '').toLowerCase().includes(q))
})

onMounted(() => loadSessions())

const loadSessions = async () => {
  loading.value = true
  try {
    const result = await sessionApi.list()
    sessions.value = Array.isArray(result) ? result : (result.sessions || [])
  } catch (e) {
    console.error('加载会话失败:', e)
  } finally {
    loading.value = false
  }
}

// 预览会话
const previewSession = async (id) => {
  showPreview.value = true
  previewLoading.value = true
  previewMessages.value = []
  try {
    const result = await sessionApi.getMessages(id)
    const rawMessages = result.messages || []
    // 合并思考过程和工具调用到 AI 回复中（与 ChatMain 保持一致）
    const merged = []
    let pendingReasoning = null
    for (const msg of rawMessages) {
      if (msg.role === 'system' && msg.content && msg.content.startsWith('[思考过程]')) {
        pendingReasoning = (pendingReasoning || '') + msg.content.replace('[思考过程] ', '')
      } else if ((msg.role === 'system' && msg.content && msg.content.startsWith('[工具:')) || (msg.role === 'tool')) {
        // 工具调用结果不显示在预览中（太冗长）
        continue
      } else {
        if (pendingReasoning && msg.role === 'assistant') {
          merged.push({ ...msg, reasoning: pendingReasoning })
          pendingReasoning = null
        } else {
          merged.push(msg)
        }
      }
    }
    previewMessages.value = merged
  } catch (e) {
    console.error('加载消息失败:', e)
    previewMessages.value = [{ role: 'system', content: '加载失败: ' + e.message }]
  } finally {
    previewLoading.value = false
  }
}

// 渲染 Markdown
const renderMarkdown = (content) => {
  if (!content) return ''
  try {
    return marked.parse(content)
  } catch {
    return content
  }
}

const deleteSession = (id, name) => {
  deleteTargetId.value = id
  deleteTargetName.value = name || '未命名会话'
  showDeleteConfirm.value = true
}

const confirmDeleteSession = async () => {
  try {
    await sessionApi.delete(deleteTargetId.value)
    await loadSessions()
    showToast?.('会话已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  let date
  if (typeof timeStr === 'number' || !isNaN(timeStr)) {
    date = new Date(Number(timeStr) * 1000)
  } else {
    date = new Date(timeStr)
  }
  if (isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN')
}

const formatTimestamp = (ts) => {
  if (!ts) return ''
  const date = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>
