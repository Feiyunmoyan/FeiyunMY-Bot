<template>
  <div class="panel">
    <h2 class="text-2xl font-bold text-text-primary mb-6">数据统计</h2>
    
    <div v-if="loading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" />
    </div>
    
    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="card text-center">
          <p class="text-3xl font-bold text-primary">{{ stats.memory_count || 0 }}</p>
          <p class="text-sm text-text-secondary mt-1">记忆条数</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-info">{{ stats.persona_count || 0 }}</p>
          <p class="text-sm text-text-secondary mt-1">人格数量</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-success">{{ stats.uptime_seconds ? formatUptime(stats.uptime_seconds) : '-' }}</p>
          <p class="text-sm text-text-secondary mt-1">运行时长</p>
        </div>
        <div class="card text-center">
          <p class="text-3xl font-bold text-warning">{{ stats.active_persona || '-' }}</p>
          <p class="text-sm text-text-secondary mt-1">当前人格</p>
        </div>
      </div>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div class="card">
          <h3 class="text-lg font-semibold text-text-primary mb-4">功能状态</h3>
          <div class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-text-secondary">记忆模式</span>
              <span class="text-text-primary font-medium">{{ stats.memory_mode || '-' }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-text-secondary">联网搜索</span>
              <span :class="stats.web_search_enabled ? 'text-success' : 'text-text-disabled'">{{ stats.web_search_enabled ? '已启用' : '已禁用' }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-text-secondary">人格系统</span>
              <span :class="stats.persona_enabled ? 'text-success' : 'text-text-disabled'">{{ stats.persona_enabled ? '已启用' : '已禁用' }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-text-secondary">MCP 服务</span>
              <span :class="stats.mcp_enabled ? 'text-success' : 'text-text-disabled'">{{ stats.mcp_enabled ? `已启用 (${stats.mcp_count}个)` : '已禁用' }}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-text-secondary">Skills 技能</span>
              <span :class="stats.skills_enabled ? 'text-success' : 'text-text-disabled'">{{ stats.skills_enabled ? `已启用 (${stats.skills_count}个)` : '已禁用' }}</span>
            </div>
          </div>
        </div>
        
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-text-primary">资源监控</h3>
            <button @click="loadStats" class="btn-secondary text-sm">刷新</button>
          </div>
          <div class="space-y-4">
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-text-secondary">CPU</span>
                <span class="text-text-primary" :class="cpuColor">{{ sysStats.cpu }}%</span>
              </div>
              <div class="w-full bg-bg-hover rounded-full h-2">
                <div class="h-2 rounded-full transition-all" :class="cpuBarColor" :style="{ width: sysStats.cpu + '%' }" />
              </div>
            </div>
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-text-secondary">内存</span>
                <span class="text-text-primary" :class="memColor">{{ sysStats.memory }}%</span>
              </div>
              <div class="w-full bg-bg-hover rounded-full h-2">
                <div class="h-2 rounded-full transition-all" :class="memBarColor" :style="{ width: sysStats.memory + '%' }" />
              </div>
            </div>
            <div>
              <div class="flex justify-between text-sm mb-1">
                <span class="text-text-secondary">磁盘</span>
                <span class="text-text-primary" :class="diskColor">{{ sysStats.disk }}%</span>
              </div>
              <div class="w-full bg-bg-hover rounded-full h-2">
                <div class="h-2 rounded-full transition-all" :class="diskBarColor" :style="{ width: sysStats.disk + '%' }" />
              </div>
            </div>
            <p v-if="psutilMissing" class="text-[10px] text-text-secondary text-center">需安装 psutil 以获取准确数据</p>
          </div>
        </div>
      </div>
      
      <div class="card">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-text-primary">工具状态</h3>
        </div>
        <div v-if="toolList.length === 0" class="text-text-secondary text-sm">暂无工具数据</div>
        <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          <div v-for="tool in toolList" :key="tool.name" class="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-hover/50 text-sm">
            <span class="w-2 h-2 rounded-full flex-shrink-0" :class="tool.enabled ? 'bg-success' : 'bg-text-disabled'" />
            <span class="text-text-primary">{{ toolLabel(tool.name) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { statsApi } from '@/api/index.js'
import LoadingSpinner from '../shared/LoadingSpinner.vue'

const stats = ref({})
const sysStats = ref({ cpu: 0, memory: 0, disk: 0 })
const toolList = ref([])
const loading = ref(true)
const psutilMissing = ref(false)
let refreshTimer = null

// 颜色逻辑（复用 HomePanel 的）
const getUsageColor = (value, high = 80, mid = 50) => {
  if (value >= high) return 'text-error'
  if (value >= mid) return 'text-warning'
  return 'text-text-primary'
}
const getBarColor = (value, high = 80, mid = 50) => {
  if (value >= high) return 'bg-error'
  if (value >= mid) return 'bg-warning'
  return 'bg-primary'
}
const cpuColor = computed(() => getUsageColor(sysStats.value.cpu))
const cpuBarColor = computed(() => getBarColor(sysStats.value.cpu))
const memColor = computed(() => getUsageColor(sysStats.value.memory, 85, 65))
const memBarColor = computed(() => getBarColor(sysStats.value.memory, 85, 65))
const diskColor = computed(() => getUsageColor(sysStats.value.disk, 90, 75))
const diskBarColor = computed(() => getBarColor(sysStats.value.disk, 90, 75))

onMounted(async () => {
  await loadStats()
  loading.value = false
  refreshTimer = setInterval(loadStats, 10000)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})

const loadStats = async () => {
  try {
    const [result, sys] = await Promise.all([
      statsApi.get().catch(() => null),
      statsApi.getSystem().catch(() => null),
    ])
    if (result) {
      stats.value = result
      toolList.value = result.tools || []
    }
    if (sys) {
      if (sys.note || sys.cpu?.note) psutilMissing.value = true
      sysStats.value = {
        cpu: Math.round(typeof sys.cpu?.percent === 'number' ? sys.cpu.percent : 0),
        memory: Math.round(typeof sys.memory?.percent === 'number' ? sys.memory.percent : 0),
        disk: Math.round(typeof sys.disk?.percent === 'number' ? sys.disk.percent : 0),
      }
    }
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

const toolLabel = (name) => {
  const map = {
    web: '网络搜索',
    web_search: '网页搜索',
    web_extract: '网页提取',
    execute: '代码执行',
    code_exec: 'Python 执行',
    shell_exec: 'Shell 执行',
    file_ops: '文件操作',
    common_utils: '通用工具',
    get_datetime: '时间查询',
    calculator: '计算器',
    random_utils: '随机工具',
    http_request: 'HTTP 请求',
    memory_query: '记忆查询',
    note_taking: '笔记管理',
    json_process: 'JSON 处理',
    agent_tools: 'Agent 工具',
    manage_session: '会话管理',
    workspace_tools: '工作空间',
  }
  return map[name] || name
}

const formatUptime = (seconds) => {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const parts = []
  if (d > 0) parts.push(d + '天')
  if (h > 0) parts.push(h + '时')
  parts.push(m + '分')
  return parts.join('')
}
</script>
