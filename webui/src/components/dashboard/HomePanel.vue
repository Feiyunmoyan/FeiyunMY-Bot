<template>
  <div class="panel">
    <h2 class="text-2xl font-bold text-text-primary mb-6">系统概览</h2>
    
    <!-- 加载状态 -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="text-center">
        <div class="w-10 h-10 mx-auto mb-3 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        <p class="text-sm text-text-secondary">加载系统信息...</p>
      </div>
    </div>
    
    <template v-else>
      <!-- 系统状态卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div class="card">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-text-secondary">服务状态</span>
            <span class="w-2.5 h-2.5 rounded-full bg-success animate-pulse" />
          </div>
          <p class="text-2xl font-bold text-text-primary">运行中</p>
          <p class="text-xs text-text-secondary mt-1">运行时长: {{ uptime || '计算中...' }}</p>
        </div>
        
        <div class="card">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-text-secondary">CPU 使用率</span>
          </div>
          <p class="text-2xl font-bold" :class="cpuColor">{{ stats.cpu }}%</p>
          <div class="mt-2 w-full bg-bg-hover rounded-full h-1.5">
            <div class="h-1.5 rounded-full transition-all" :class="cpuBarColor" :style="{ width: stats.cpu + '%' }" />
          </div>
          <p v-if="psutilMissing" class="text-[10px] text-text-secondary mt-1">需安装 psutil 以获取准确数据</p>
        </div>
        
        <div class="card">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-text-secondary">内存使用</span>
          </div>
          <p class="text-2xl font-bold" :class="memoryColor">{{ stats.memory }}%</p>
          <div class="mt-2 w-full bg-bg-hover rounded-full h-1.5">
            <div class="h-1.5 rounded-full transition-all" :class="memoryBarColor" :style="{ width: stats.memory + '%' }" />
          </div>
          <p v-if="psutilMissing" class="text-[10px] text-text-secondary mt-1">需安装 psutil 以获取准确数据</p>
        </div>
        
        <div class="card">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-text-secondary">磁盘使用</span>
          </div>
          <p class="text-2xl font-bold" :class="diskColor">{{ stats.disk }}%</p>
          <div class="mt-2 w-full bg-bg-hover rounded-full h-1.5">
            <div class="h-1.5 rounded-full transition-all" :class="diskBarColor" :style="{ width: stats.disk + '%' }" />
          </div>
          <p v-if="psutilMissing" class="text-[10px] text-text-secondary mt-1">需安装 psutil 以获取准确数据</p>
        </div>
      </div>
      
      <!-- 当前配置摘要 -->
      <div class="card mb-6">
        <h3 class="text-lg font-semibold text-text-primary mb-4">当前配置</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <span class="text-sm text-text-secondary">当前人格</span>
            <p class="text-text-primary font-medium mt-1">{{ config.persona || '默认' }}</p>
          </div>
          <div>
            <span class="text-sm text-text-secondary">记忆模式</span>
            <p class="text-text-primary font-medium mt-1">{{ config.memoryMode }}</p>
          </div>
          <div>
            <span class="text-sm text-text-secondary">模型</span>
            <p class="text-text-primary font-medium mt-1">{{ config.model || '未配置' }}</p>
          </div>
        </div>
      </div>
      
      <!-- 最近对话 -->
      <div class="card">
        <h3 class="text-lg font-semibold text-text-primary mb-4">最近对话</h3>
        <div v-if="recentSessions.length === 0" class="text-text-secondary text-sm py-4">暂无对话记录</div>
        <div v-else class="space-y-2">
          <div
            v-for="session in recentSessions"
            :key="session.id"
            @click="goToSession(session)"
            class="flex items-center justify-between py-2 px-3 rounded-lg border-b border-border last:border-0 cursor-pointer hover:bg-bg-hover transition-colors"
          >
            <span class="text-text-primary truncate flex-1 mr-4">{{ session.name || '未命名' }}</span>
            <span class="text-xs text-text-secondary flex-shrink-0">{{ formatTime(session.updated_at) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { statsApi, configApi, sessionApi } from '@/api/index.js'

const loading = ref(true)
const stats = ref({ cpu: 0, memory: 0, disk: 0 })
const config = ref({ persona: '', memoryMode: 'Simple', model: '' })
const recentSessions = ref([])
const uptime = ref('')
const psutilMissing = ref(false)
let refreshTimer = null

const loadStats = async () => {
  try {
    const sysStats = await statsApi.getSystem()
    if (sysStats) {
      // 检测 psutil 是否安装
      if (sysStats.note || sysStats.cpu?.note) {
        psutilMissing.value = true
      }
      
      stats.value = {
        cpu: typeof sysStats.cpu?.percent === 'number' ? Math.round(sysStats.cpu.percent) : 0,
        memory: typeof sysStats.memory?.percent === 'number' ? Math.round(sysStats.memory.percent) : 0,
        disk: typeof sysStats.disk?.percent === 'number' ? Math.round(sysStats.disk.percent) : 0,
      }
      uptime.value = sysStats.uptime_str || ''
    }
  } catch (e) {
    console.error('加载系统统计失败:', e)
  }
}

const loadConfig = async () => {
  try {
    const cfg = await configApi.get()
    if (cfg) {
      // 记忆模式：根据 enabled 字段推导 true=Memoria, false=Simple
      const memoryEnabled = cfg.memory?.enabled
      config.value = {
        persona: cfg.persona?.active || '默认',
        memoryMode: memoryEnabled ? 'MemoriaDB' : 'Simple',
        model: cfg.provider?.model || '未配置',
      }
    }
  } catch (e) {
    console.error('加载配置失败:', e)
  }
}

const loadRecentSessions = async () => {
  try {
    const sessions = await sessionApi.list()
    recentSessions.value = (Array.isArray(sessions) ? sessions : (sessions.sessions || [])).slice(0, 5)
  } catch (e) {
    console.error('加载会话失败:', e)
  }
}

// 点击最近对话跳转到 Chat 页面
const goToSession = (session) => {
  // 通过 emit 或 router 导航到 chat 页面并选中该会话
  // 目前通过触发全局事件，让 App.vue 处理跳转
  window.dispatchEvent(new CustomEvent('navigate-to-chat', { detail: { sessionId: session.id } }))
}

// 根据使用率返回颜色
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

const cpuColor = computed(() => getUsageColor(stats.value.cpu))
const cpuBarColor = computed(() => getBarColor(stats.value.cpu))
const memoryColor = computed(() => getUsageColor(stats.value.memory, 85, 65))
const memoryBarColor = computed(() => getBarColor(stats.value.memory, 85, 65))
const diskColor = computed(() => getUsageColor(stats.value.disk, 90, 75))
const diskBarColor = computed(() => getBarColor(stats.value.disk, 90, 75))

onMounted(async () => {
  await Promise.all([loadStats(), loadConfig(), loadRecentSessions()])
  loading.value = false
  // 每 10 秒自动刷新系统状态（CPU/内存/磁盘/运行时间）
  refreshTimer = setInterval(loadStats, 10000)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  let date
  if (typeof timeStr === 'number' || !isNaN(timeStr)) {
    date = new Date(Number(timeStr) * 1000)
  } else {
    date = new Date(timeStr)
  }
  if (isNaN(date.getTime())) return ''
  const diff = Date.now() - date.getTime()
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN')
}
</script>
