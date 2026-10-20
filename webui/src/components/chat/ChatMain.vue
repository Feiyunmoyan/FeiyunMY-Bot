<template>
  <div class="flex flex-col h-full">
    <!-- 会话标题栏 -->
    <div class="flex items-center justify-between px-6 py-3 border-b border-border bg-bg-card">
      <h2 class="text-lg font-semibold text-text-primary truncate flex-1 mr-4">
        {{ sessionName || '新会话' }}
      </h2>
      <div class="flex items-center gap-2">
        <button
          @click="$emit('auto-name')"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          title="自动命名"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
          </svg>
        </button>
      </div>
    </div>
    
    <!-- 消息列表 -->
    <div ref="messageListRef" class="flex-1 overflow-y-auto">
      <div v-if="messages.length === 0" class="flex items-center justify-center h-full">
        <div class="text-center">
          <div class="w-20 h-20 mx-auto mb-4 rounded-full bg-bg-hover flex items-center justify-center">
            <svg class="w-10 h-10 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
            </svg>
          </div>
          <h3 class="text-lg font-medium text-text-primary mb-2">开始新对话</h3>
          <p class="text-text-secondary text-sm">在下方输入消息开始与 AI 对话</p>
        </div>
      </div>
      
      <div v-else class="max-w-4xl mx-auto px-6 py-4 space-y-4">
        <TransitionGroup name="message">
          <template v-for="(msg, index) in messages" :key="index">
            <!-- 日期分隔线 -->
            <div
              v-if="showDateSeparator(msg, index)"
              :key="'date-' + index"
              class="flex items-center gap-3 py-2 w-full"
            >
              <div class="flex-1 h-px bg-border"></div>
              <span class="text-xs text-text-secondary flex-shrink-0 px-2">{{ formatDate(msg.timestamp) }}</span>
              <div class="flex-1 h-px bg-border"></div>
            </div>
            <MessageBubble
              :message="msg"
              :index="index"
            />
          </template>
        </TransitionGroup>
      </div>
    </div>
    
    <!-- 输入区域 -->
    <ChatInput
      :disabled="isStreaming"
      :is-streaming="isStreaming"
      :streaming-enabled="chat.streamingEnabled.value"
      @send="$emit('send', $event)"
      @stop="$emit('stop')"
      @toggle-streaming="chat.streamingEnabled.value = !chat.streamingEnabled.value"
    />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'
import { useChat } from '@/composables/useChat'

const chat = useChat()

const props = defineProps({
  messages: { type: Array, default: () => [] },
  sessionName: { type: String, default: '' },
  isStreaming: { type: Boolean, default: false }
})

defineEmits(['send', 'stop', 'auto-name'])

const messageListRef = ref(null)

// 切换到Chat页面时自动滚动到底部（消息已存在时触发）
onMounted(async () => {
  await nextTick()
  scrollToBottom()
})

// 消息变化时自动滚动到底部
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    scrollToBottom()
  }
)

const scrollToBottom = () => {
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

// ─── 时间分隔线 ───

function parseMsgDate(ts) {
  if (!ts) return new Date(NaN)
  if (typeof ts === 'number' || !isNaN(Number(ts))) {
    const num = Number(ts)
    return new Date(num < 1e12 ? num * 1000 : num)
  }
  return new Date(ts)
}

function formatDate(ts) {
  const d = parseMsgDate(ts)
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
  const prevDate = parseMsgDate(prev.timestamp)
  const currDate = parseMsgDate(msg.timestamp)
  return prevDate.toDateString() !== currDate.toDateString()
}
</script>

<style scoped>
.message-enter-active {
  transition: all 0.3s ease;
}
.message-leave-active {
  transition: all 0.2s ease;
}
.message-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.message-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
