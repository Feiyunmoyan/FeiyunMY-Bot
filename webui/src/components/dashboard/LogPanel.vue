<template>
  <div class="panel">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-2xl font-bold text-text-primary">平台日志</h2>
      <div class="flex items-center gap-2">
        <select v-model="levelFilter" class="input-base w-28 text-sm">
          <option value="">全部级别</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
        <input v-model="keyword" class="input-base w-36 text-sm" placeholder="搜索关键词" @keydown.enter="loadLogs" />
        <button @click="loadLogs" class="btn-secondary text-sm">刷新</button>
      </div>
    </div>
    
    <!-- 统计栏 -->
    <div v-if="stats" class="flex items-center gap-4 mb-3 text-xs text-text-secondary">
      <span>共 <strong class="text-text-primary">{{ stats.total || 0 }}</strong> 条</span>
      <span>📄 {{ formatSize(stats.file_size) }}</span>
      <span>💾 {{ stats.cache_count }} 条缓存</span>
      <span class="ml-auto flex gap-3">
        <span>✅ <strong class="text-success">{{ stats.levels?.INFO || 0 }}</strong></span>
        <span>⚠️ <strong class="text-warning">{{ stats.levels?.WARNING || 0 }}</strong></span>
        <span>❌ <strong class="text-error">{{ stats.levels?.ERROR || 0 }}</strong></span>
      </span>
    </div>
    
    <!-- 日志列表 -->
    <div ref="logListRef" class="card bg-bg-base font-mono text-xs h-[55vh] overflow-y-auto">
      <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
      <div v-else-if="parsedLogs.length === 0" class="py-8 text-center text-text-secondary">暂无日志</div>
      <div v-else class="divide-y divide-border">
        <div 
          v-for="(log, idx) in parsedLogs" 
          :key="idx"
          class="py-1.5 px-3 hover:bg-bg-hover transition-colors leading-relaxed"
        >
          <span class="text-text-disabled">{{ log.time }}</span>
          <span :class="['mx-1.5 font-medium', levelColor(log.level)]">[{{ log.level }}]</span>
          <span class="text-text-secondary">[{{ log.module }}]</span>
          <span class="text-text-primary ml-1.5">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { logsApi } from '@/api/index.js'
import LoadingSpinner from '../shared/LoadingSpinner.vue'

const logs = ref([])
const stats = ref(null)
const loading = ref(false)
const levelFilter = ref('')
const keyword = ref('')
const logListRef = ref(null)
let refreshTimer = null
let scrollPos = 0

// 解析日志字符串： "2026-05-28 10:00 [INFO] tools.registry: 消息"
const parseLog = (line) => {
  const match = line.match(/^(\S+\s+\S+)\s+\[(\w+)\]\s+([^:]+):\s*(.*)$/)
  if (match) {
    return { time: match[1], level: match[2], module: match[3], message: match[4], raw: line }
  }
  return { time: '', level: 'INFO', module: '?', message: line, raw: line }
}

const parsedLogs = computed(() => {
  let result = logs.value.map(parseLog)
  if (levelFilter.value) {
    result = result.filter(l => l.level === levelFilter.value)
  }
  if (keyword.value) {
    const kw = keyword.value.toLowerCase()
    result = result.filter(l => l.raw.toLowerCase().includes(kw))
  }
  return result
})

const levelColor = (level) => ({
  ERROR: 'text-error',
  WARNING: 'text-warning',
  INFO: 'text-info',
}[level] || 'text-text-secondary')

const formatSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

const loadLogs = async (isInitial = false) => {
  // 保存当前滚动位置
  if (logListRef.value) {
    scrollPos = logListRef.value.scrollTop
  }
  if (isInitial) loading.value = true
  try {
    const params = { lines: 200 }
    if (levelFilter.value) params.level = levelFilter.value
    if (keyword.value) params.keyword = keyword.value
    const result = await logsApi.get(params)
    if (result) {
      logs.value = result.logs || []
      stats.value = { total: result.total, ...result.stats }
    }
  } catch (e) {
    console.error('加载日志失败:', e)
  } finally {
    loading.value = false
    // 等 DOM 更新后恢复滚动位置
    if (logListRef.value && scrollPos > 0) {
      requestAnimationFrame(() => {
        logListRef.value.scrollTop = scrollPos
      })
    }
  }
}

onMounted(() => {
  loadLogs(true)
  refreshTimer = setInterval(() => loadLogs(), 3000)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>
