<template>
  <div :class="[
    'flex gap-3',
    message.role === 'user' ? 'justify-end' : 'justify-start'
  ]">
    <!-- AI头像 -->
    <div v-if="message.role === 'assistant'" class="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center mt-1 overflow-hidden">
      <img :src="logoSrc" alt="AI" class="w-6 h-6 object-contain" />
    </div>
    
    <!-- 消息气泡 -->
    <div :class="[
      'max-w-[75%] rounded-2xl px-4 py-3',
      message.role === 'user' 
        ? 'bg-primary text-white rounded-br-md' 
        : 'bg-bg-card border border-border rounded-bl-md'
    ]">
      <!-- 思考过程（可折叠） -->
      <div v-if="message.reasoning" class="mb-3">
        <button
          @click="showReasoning = !showReasoning"
          class="flex items-center gap-2 text-xs text-text-secondary hover:text-text-primary transition-colors"
        >
          <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-90': showReasoning }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
          思考过程
        </button>
        <Transition name="slide">
          <div v-if="showReasoning" class="mt-2 pl-3 border-l-2 border-border text-sm text-text-secondary italic whitespace-pre-wrap">
            {{ message.reasoning }}
          </div>
        </Transition>
      </div>
      
      <!-- 主动推送标记 -->
      <div v-if="message.type === 'active_push'" class="mb-2">
        <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary/70 font-medium">主动</span>
      </div>
      
      <!-- 工具调用步骤时间线 -->
      <div v-if="message.tools_used && message.tools_used.length > 0" class="mb-3 space-y-1.5">
        <div
          v-for="(tool, idx) in message.tools_used"
          :key="idx"
          class="flex gap-2.5"
        >
          <!-- 步骤连接线 -->
          <div class="flex flex-col items-center flex-shrink-0 pt-1.5" style="width: 18px;">
            <div class="w-2 h-2 rounded-full" :class="getToolStatusColor(tool)"></div>
            <div v-if="idx < message.tools_used.length - 1" class="w-0.5 flex-1 bg-border min-h-[20px]"></div>
          </div>
          
          <!-- 步骤卡片 -->
          <div class="flex-1 min-w-0 tool-step-card">
            <button
              @click="toggleToolExpand(idx)"
              class="tool-step-header"
            >
              <Wrench class="w-3.5 h-3.5 flex-shrink-0" />
              <span class="tool-step-name">{{ tool.name || tool.tool_name || '未知工具' }}</span>
              <span v-if="tool.duration" class="tool-step-duration">{{ tool.duration }}</span>
              <span v-if="tool.status === 'running'" class="tool-step-status status-running">运行中...</span>
              <span v-else-if="tool.status === 'failed'" class="tool-step-status status-failed">失败</span>
              <svg
                class="w-3.5 h-3.5 tool-step-arrow flex-shrink-0"
                :class="{ expanded: expandedTools[idx] }"
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
            </button>
            <Transition name="tool-expand">
              <div v-if="expandedTools[idx]" class="tool-step-details">
                <div v-if="tool.args" class="tool-detail-row">
                  <span class="detail-label">参数</span>
                  <pre class="detail-json">{{ formatJson(tool.args) }}</pre>
                </div>
                <div v-if="tool.result" class="tool-detail-row">
                  <span class="detail-label">结果</span>
                  <pre class="detail-json detail-result">{{ truncateResult(tool.result) }}</pre>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </div>
      
      <!-- 消息文件列表（用户消息） -->
      <div v-if="message.files && message.files.length > 0" class="mb-2 space-y-1">
        <div v-for="(f, i) in message.files" :key="i" class="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs" :class="message.role === 'user' ? 'bg-white/10 text-white' : 'bg-bg-hover text-text-primary'">
          <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
          </svg>
          <span class="truncate">{{ f.name }}</span>
        </div>
      </div>
      
      <!-- 消息内容 -->
      <div v-if="message.role === 'assistant'" class="text-sm leading-relaxed" style="color: inherit" v-html="renderedContent"></div>
      <div v-else class="whitespace-pre-wrap text-sm leading-relaxed">
        {{ message.content }}
      </div>
      <!-- 流式光标 -->
      <span v-if="message.isStreaming" class="inline-block mt-0.5 animate-cursor-blink text-primary text-sm">▌</span>
      
      <!-- 时间戳 -->
      <div class="mt-2 text-[10px] text-text-secondary text-right">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>
    
    <!-- 用户头像 -->
    <div v-if="message.role === 'user'" class="flex-shrink-0 w-8 h-8 rounded-full bg-bg-hover flex items-center justify-center mt-1">
      <svg class="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
      </svg>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { Wrench } from 'lucide-vue-next'
import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true,        // 支持换行
  gfm: true,           // GitHub 风格 Markdown
})

// logo 路径
const logoSrc = './assets/logo.png'

const props = defineProps({
  message: { type: Object, required: true },
  index: { type: Number, default: 0 }
})

const showReasoning = ref(false)
const expandedTools = reactive({})

// AI 消息渲染 Markdown
const renderedContent = computed(() => {
  if (props.message.role === 'assistant' && props.message.content) {
    return marked.parse(props.message.content)
  }
  return ''
})

const toggleToolExpand = (idx) => {
  expandedTools[idx] = !expandedTools[idx]
}

const getToolStatusColor = (tool) => {
  if (tool.status === 'running') return 'bg-info'
  if (tool.status === 'failed') return 'bg-error'
  return 'bg-primary'  // done / 默认
}

const truncateResult = (text) => {
  if (!text || text.length <= 500) return text
  return text.slice(0, 500) + " ... (内容过长，已截断)"
}

const formatJson = (obj) => {
  try {
    return JSON.stringify(typeof obj === 'string' ? JSON.parse(obj) : obj, null, 2)
  } catch {
    return String(obj)
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  let date
  if (typeof timeStr === 'number' || !isNaN(timeStr)) {
    date = new Date(Number(timeStr) * 1000)
  } else {
    date = new Date(timeStr)
  }
  if (isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.slide-enter-active, .slide-leave-active {
  transition: all 0.2s ease;
}
.slide-enter-from, .slide-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}
.border-l-2 {
  border-left-width: 2px;
}

/* 工具调用步骤时间线 */
.tool-step-card {
  font-size: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.tool-step-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--color-bg-hover);
  border: none;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: 12px;
  text-align: left;
  transition: background 0.15s;
}
.tool-step-header:hover {
  background: var(--color-bg-card);
}

.tool-step-name {
  flex: 1;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-step-duration {
  flex-shrink: 0;
  color: var(--color-text-disabled);
  font-size: 11px;
}

.tool-step-status {
  flex-shrink: 0;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
}
.status-running {
  background: var(--color-info);
  color: white;
  animation: pulse 1.5s ease infinite;
}
.status-failed {
  background: var(--color-error);
  color: white;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.tool-step-arrow {
  flex-shrink: 0;
  transition: transform 0.2s;
}
.tool-step-arrow.expanded {
  transform: rotate(90deg);
}

.tool-step-details {
  padding: 8px 10px;
  border-top: 1px solid var(--color-border);
}

.tool-detail-row {
  margin-bottom: 6px;
}
.tool-detail-row:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--color-text-secondary);
  display: block;
  margin-bottom: 2px;
}

.detail-json {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
  margin: 0;
  color: var(--color-text-primary);
  background: var(--color-bg-input);
  padding: 4px 6px;
  border-radius: 4px;
}

.detail-result {
  max-height: 160px;
}

/* 工具展开动画 */
.tool-expand-enter-active, .tool-expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.tool-expand-enter-from,
.tool-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.tool-expand-enter-to,
.tool-expand-leave-from {
  opacity: 1;
  max-height: 400px;
}

/* Markdown 渲染样式 */
.text-sm :deep(h1),
.text-sm :deep(h2),
.text-sm :deep(h3),
.text-sm :deep(h4) {
  margin: 0.5em 0 0.25em;
  font-weight: 600;
  line-height: 1.3;
}
.text-sm :deep(h1) { font-size: 1.2em; }
.text-sm :deep(h2) { font-size: 1.1em; }
.text-sm :deep(h3) { font-size: 1.05em; }
.text-sm :deep(p) { margin: 0.3em 0; }
.text-sm :deep(ul),
.text-sm :deep(ol) { padding-left: 1.5em; margin: 0.3em 0; }
.text-sm :deep(li) { margin: 0.15em 0; }
.text-sm :deep(code) {
  background: var(--color-bg-hover);
  padding: 0.15em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.text-sm :deep(pre) {
  background: var(--color-bg-input);
  padding: 0.75em 1em;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0.5em 0;
  border: 1px solid var(--color-border);
}
.text-sm :deep(pre code) {
  background: none;
  padding: 0;
  border-radius: 0;
}
.text-sm :deep(blockquote) {
  border-left: 3px solid var(--color-border);
  padding-left: 0.75em;
  margin: 0.5em 0;
  color: var(--color-text-secondary);
}
.text-sm :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}
.text-sm :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
  width: 100%;
  font-size: 0.9em;
}
.text-sm :deep(th),
.text-sm :deep(td) {
  border: 1px solid var(--color-border);
  padding: 0.4em 0.6em;
  text-align: left;
}
.text-sm :deep(th) {
  background: var(--color-bg-hover);
  font-weight: 600;
}
.text-sm :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 0.75em 0;
}
</style>
