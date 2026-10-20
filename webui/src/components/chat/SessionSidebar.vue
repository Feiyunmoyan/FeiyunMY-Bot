<template>
  <div class="w-[var(--session-panel-width)] h-full bg-bg-card border-r border-border flex flex-col transition-colors duration-300">
    <!-- 搜索栏 -->
    <div class="p-3 border-b border-border">
      <div class="relative">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索会话..."
          class="w-full pl-9 pr-3 py-2 bg-bg-input border border-border rounded-lg text-sm text-text-primary placeholder-text-secondary focus:outline-none focus:border-border-focus transition-colors"
        />
      </div>
    </div>
    
    <!-- 新建按钮 -->
    <div class="p-3">
      <button
        @click="emit('new-session', '')"
        class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-hover transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        新建会话
      </button>
    </div>
    
    <!-- 会话列表 -->
    <div class="flex-1 overflow-y-auto px-2 pb-2">
      <div
        v-for="session in filteredSessions"
        :key="session.id || session.session_id"
        @click="selectSession(session)"
        :class="[
          'group relative px-3 py-3 rounded-lg mb-1 cursor-pointer transition-all duration-200',
          isSelected(session)
            ? 'bg-primary/15 border-l-3 border-primary'
            : 'hover:bg-bg-hover'
        ]"
      >
        <div class="flex items-start justify-between gap-2">
          <h4 v-if="renamingSessionId !== (session.id || session.session_id)" class="text-sm font-medium text-text-primary truncate flex-1">
            {{ session.name || session.title || '未命名会话' }}
          </h4>
          <input v-else v-model="renameValue" @keydown.enter="confirmRename" @blur="confirmRename" @keydown.escape="cancelRename" class="rename-input text-sm font-medium bg-bg-input border border-border-focus rounded px-1.5 py-0.5 text-text-primary flex-1 min-w-0 outline-none" />
          <div class="flex items-center gap-1 flex-shrink-0">
            <!-- 消息数量徽章（内联，不遮挡按钮） -->
            <span v-if="session.message_count" class="inline-flex items-center justify-center w-5 h-5 text-[10px] font-medium rounded-full bg-bg-hover text-text-secondary">
              {{ Math.ceil(session.message_count / 2) }}
            </span>
            <!-- 操作按钮（悬停显示） -->
            <div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <button @click.stop="startRename(session)" class="p-1 rounded hover:bg-bg-card text-text-secondary" title="重命名">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
              </button>
              <button @click.stop="handleDelete(session)" class="p-1 rounded hover:bg-bg-card text-error" title="删除">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
        
        <!-- 摘要和时间 -->
        <div class="mt-1 flex items-center justify-between text-xs text-text-secondary">
          <span class="truncate flex-1 mr-2">{{ getLastMessage(session) }}</span>
          <span class="flex-shrink-0">{{ formatTime(session.updated_at || session.last_active) }}</span>
        </div>
      </div>
      
      <!-- 空状态 -->
      <div v-if="filteredSessions.length === 0" class="py-8 text-center text-text-secondary text-sm">
        {{ searchQuery ? '未找到匹配的会话' : '暂无会话' }}
      </div>
    </div>
    
    <!-- 删除确认弹窗 -->
    <ConfirmDialog
      :show="showDeleteConfirm"
      title="删除会话"
      :message="`确定要删除会话「${deleteTargetName}」吗？此操作不可撤销。`"
      @confirm="confirmDelete"
      @update:show="showDeleteConfirm = false"
    />
    
    <!-- 底部：常驻入口 -->
    <div class="border-t border-border mt-auto">
      <div class="p-2 space-y-0.5">
        <button
          @click="emit('switch-view', 'push')"
          :class="[
            'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-all text-left',
            isPushView
              ? 'bg-primary/15 text-primary font-medium'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
          ]"
        >
          <MessageSquare class="w-4 h-4" />
          <span class="flex-1">普通消息</span>
          <span v-if="chat.pushUnread.value > 0" class="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-error text-white text-[10px] font-medium">
            {{ chat.pushUnread.value > 99 ? '99+' : chat.pushUnread.value }}
          </span>
        </button>
        <button
          @click="emit('switch-view', 'notification')"
          :class="[
            'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-all text-left',
            isNotificationView
              ? 'bg-primary/15 text-primary font-medium'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
          ]"
        >
          <Bell class="w-4 h-4" />
          <span class="flex-1">系统通知</span>
          <span v-if="chat.notificationUnread.value > 0" class="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-error text-white text-[10px] font-medium">
            {{ chat.notificationUnread.value > 99 ? '99+' : chat.notificationUnread.value }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { MessageSquare, Bell } from 'lucide-vue-next'
import { useChat } from '@/composables/useChat'
import ConfirmDialog from '../shared/ConfirmDialog.vue'

const emit = defineEmits(['select-session', 'new-session', 'delete-session', 'rename-session', 'auto-name', 'switch-view'])

const chat = useChat()
const searchQuery = ref('')
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)
const deleteTargetName = ref('')
const renamingSessionId = ref(null)
const renameValue = ref('')

// 当前是否是推送/通知视图
const isPushView = computed(() => chat.currentView.value === 'push')
const isNotificationView = computed(() => chat.currentView.value === 'notification')

const startRename = (session) => {
  renamingSessionId.value = session.id || session.session_id
  renameValue.value = session.name || session.title || ''
  // 输入框自动聚焦（通过 nextTick）
  setTimeout(() => {
    const input = document.querySelector('.rename-input')
    if (input) input.focus()
  }, 50)
}

const confirmRename = () => {
  if (renamingSessionId.value && renameValue.value.trim()) {
    emit('rename-session', renamingSessionId.value, renameValue.value.trim())
  }
  renamingSessionId.value = null
}

const cancelRename = () => {
  renamingSessionId.value = null
}

const filteredSessions = computed(() => {
  // 过滤掉内部频道
  const visible = chat.sessions.value.filter(s => {
    const sid = s.id || s.session_id || ''
    const sname = s.title || s.name || ''
    // 过滤掉系统频道、工作空间子 Agent 会话和工作空间主脑会话
    if (sid === '__push_channel__') return false
    if (sname.startsWith('[')) return false
    if (sid.startsWith('ws_')) return false
    return true
  })
  if (!searchQuery.value) return visible
  const q = searchQuery.value.toLowerCase()
  return visible.filter(s => 
    (s.name || s.title || '').toLowerCase().includes(q)
  )
})

const isSelected = (session) => {
  const id = session.id || session.session_id
  return id === chat.currentSessionId.value
}

const selectSession = (session) => {
  emit('select-session', session.id || session.session_id)
}

const getLastMessage = (session) => {
  return session.last_message || '新会话'
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  // 支持 ISO 字符串和 Unix 秒数两种格式
  let date
  if (typeof timeStr === 'number' || !isNaN(timeStr)) {
    date = new Date(Number(timeStr) * 1000)
  } else {
    date = new Date(timeStr)
  }
  if (isNaN(date.getTime())) return ''
  
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return date.toLocaleDateString('zh-CN')
}

const handleDelete = (session) => {
  deleteTarget.value = session
  deleteTargetName.value = session.name || session.title || '未命名会话'
  showDeleteConfirm.value = true
}

const confirmDelete = () => {
  if (deleteTarget.value) {
    emit('delete-session', deleteTarget.value.id || deleteTarget.value.session_id)
    deleteTarget.value = null
  }
}
</script>

<style scoped>
.border-l-3 {
  border-left-width: 3px;
}
</style>
