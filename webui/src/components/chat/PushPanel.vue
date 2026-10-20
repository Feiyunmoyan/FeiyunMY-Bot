<template>
  <div class="flex flex-col h-full">
    <!-- 标题栏 -->
    <div class="flex items-center gap-2 px-6 py-3 border-b border-border bg-bg-card">
      <component :is="iconComponent" class="w-5 h-5 text-primary" />
      <h2 class="text-lg font-semibold text-text-primary">{{ title }}</h2>
      <span v-if="messages.length" class="text-xs text-text-secondary ml-auto">
        共 {{ messages.length }} 条
      </span>
    </div>
    
    <!-- 消息列表 -->
    <div ref="messageListRef" class="flex-1 overflow-y-auto" @scroll="onScroll">
      <div v-if="messages.length === 0" class="flex items-center justify-center h-full">
        <div class="text-center">
          <div class="w-16 h-16 mx-auto mb-3 rounded-full bg-bg-hover flex items-center justify-center">
            <component :is="iconComponent" class="w-8 h-8 text-text-secondary" />
          </div>
          <h3 class="text-lg font-medium text-text-primary mb-1">暂无{{ title }}</h3>
          <p class="text-text-secondary text-sm">{{ emptyDesc }}</p>
        </div>
      </div>
      
      <!-- 🔔 系统通知模式：居中卡片 -->
      <div v-else-if="variant === 'notification'" class="max-w-4xl mx-auto px-6 py-4 space-y-3">
        <div
          v-for="(msg, index) in messages"
          :key="msg.id || index"
          class="card hover:ring-1 hover:ring-border-focus transition-all"
        >
          <div class="flex items-start justify-between gap-3 mb-2">
            <div class="flex items-center gap-2">
              <span v-if="msg.priority === 'urgent'" class="text-xs px-1.5 py-0.5 rounded bg-error/10 text-error font-medium">紧急</span>
              <span v-else-if="msg.priority === 'important'" class="text-xs px-1.5 py-0.5 rounded bg-warning/10 text-warning font-medium">重要</span>
              <span class="text-xs text-text-secondary">{{ msg.source || '系统' }}</span>
            </div>
            <span class="text-[10px] text-text-disabled flex-shrink-0">{{ formatTime(msg.created_at) }}</span>
          </div>
          <p class="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">{{ msg.content }}</p>
        </div>
      </div>
      
      <!-- 💬 普通消息模式：复用消息气泡 -->
      <div v-else class="max-w-4xl mx-auto px-6 py-4 space-y-4">
        <!-- 加载更早的消息（ASC 顺序下最早的在上，按钮放顶部） -->
        <div v-if="!isNotification && hasMore && messages.length > 0" class="text-center py-2">
          <button
            @click="$emit('load-more')"
            class="px-4 py-2 text-sm text-text-secondary hover:text-text-primary border border-border rounded-lg hover:bg-bg-hover transition-colors"
          >
            加载更早的消息
          </button>
        </div>
        <template v-for="(msg, idx) in messages" :key="idx">
          <!-- 日期分隔线：第一条消息或跨天时显示 -->
          <div
            v-if="showDateSeparator(msg, idx)"
            class="flex items-center gap-3 py-2"
          >
            <div class="flex-1 h-px bg-border"></div>
            <span class="text-xs text-text-secondary flex-shrink-0 px-2">{{ formatDate(msg.timestamp) }}</span>
            <div class="flex-1 h-px bg-border"></div>
          </div>
          <MessageBubble
            :message="msg"
            :index="idx"
          />
        </template>
      </div>
    </div>
    
    <!-- 输入区域 -->
    <div v-if="showInput" class="border-t border-border bg-bg-card">
      <ChatInput
        :disabled="isStreaming"
        :is-streaming="isStreaming"
        :streaming-enabled="true"
        @send="emit('send', $event)"
        @stop="emit('stop')"
        @toggle-streaming="() => {}"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { MessageSquare, Bell } from 'lucide-vue-next'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  title: { type: String, default: '' },
  icon: { type: String, default: 'MessageSquare' },
  showInput: { type: Boolean, default: true },
  isStreaming: { type: Boolean, default: false },
  variant: { type: String, default: 'chat' },  // 'chat' | 'notification'
  hasMore: { type: Boolean, default: false },
})

const emit = defineEmits(['send', 'stop', 'load-more'])

const isNotification = computed(() => props.variant === 'notification')

// ─── 时间分隔线 ───

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(Number(ts) * 1000)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const msgDate = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  
  if (msgDate.getTime() === today.getTime()) return '今天'
  if (msgDate.getTime() === yesterday.getTime()) return '昨天'
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function showDateSeparator(msg, idx) {
  if (idx === 0) return true
  const prev = props.messages[idx - 1]
  if (!prev || !prev.timestamp || !msg.timestamp) return false
  
  const prevDate = new Date(Number(prev.timestamp) * 1000)
  const currDate = new Date(Number(msg.timestamp) * 1000)
  return prevDate.toDateString() !== currDate.toDateString()
}

const iconComponent = computed(() => {
  if (props.variant === 'notification') return Bell
  return MessageSquare
})

const inputText = ref('')
const textareaRef = ref(null)
const messageListRef = ref(null)

// 自动滚动到底部（只有用户本来就在底部时才滚动）
let _prevScrollAtBottom = true
watch(() => props.messages.length, async (newLen, oldLen) => {
  await nextTick()
  if (_prevScrollAtBottom) {
    scrollToBottom()
  }
})

// 记录用户滚动位置
const onScroll = () => {
  const el = messageListRef.value
  if (!el) return
  const threshold = 100  // 距离底部100px以内算"在底部"
  _prevScrollAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
}

onMounted(async () => {
  await nextTick()
  scrollToBottom()
})

const scrollToBottom = () => {
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const autoResize = () => {
  const el = textareaRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const handleSend = () => {
  const text = inputText.value.trim()
  if (text) {
    emit('send', { text, fileIds: [] })
    inputText.value = ''
    nextTick(() => {
      autoResize()
      textareaRef.value?.focus()
    })
  }
}

const formatTime = (ts) => {
  if (!ts) return ''
  const date = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  if (isNaN(date.getTime())) return ''
  const now = new Date()
  const diff = now - date
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>
