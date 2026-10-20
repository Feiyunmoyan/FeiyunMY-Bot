<template>
  <div
    class="border-t border-border bg-bg-card relative"
    @dragover.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @drop.prevent="handleDrop"
  >
    <!-- 拖拽上传遮罩 -->
    <Transition name="fade">
      <div v-if="isDragging" class="absolute inset-0 z-10 flex items-center justify-center bg-bg-card/90 backdrop-blur-sm">
        <div class="text-center">
          <svg class="w-12 h-12 mx-auto mb-2 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
          </svg>
          <p class="text-sm text-text-primary font-medium">释放以上传文件</p>
        </div>
      </div>
    </Transition>
    
    <div class="max-w-4xl mx-auto p-4">
      <div class="flex items-end gap-2">
        <!-- [+] 菜单按钮 -->
        <div class="relative" ref="menuRef">
          <button @click="menuOpen = !menuOpen" class="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors" title="更多选项">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
          </button>
          
          <!-- 下拉菜单 -->
          <Transition name="menu-slide">
            <div v-if="menuOpen" class="absolute bottom-full left-0 mb-2 w-64 bg-bg-card border border-border rounded-xl shadow-xl overflow-hidden z-50">
              <div class="p-2 space-y-1">
                <!-- 上传文件 -->
                <label class="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer hover:bg-bg-hover text-sm text-text-primary transition-colors">
                  <svg class="w-4 h-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>
                  </svg>
                  上传文件
                  <input type="file" class="hidden" @change="onFileSelected" />
                </label>
                
                <!-- 流式开关 -->
                <div class="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-bg-hover text-sm text-text-primary transition-colors">
                  <div class="flex items-center gap-3">
                    <svg class="w-4 h-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                    </svg>
                    流式响应
                  </div>
                  <button @click.stop="$emit('toggle-streaming')" class="relative w-9 h-5 rounded-full transition-colors flex-shrink-0" :class="streamingEnabled ? 'bg-primary' : 'bg-bg-hover border border-border'">
                    <span class="absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all" :class="streamingEnabled ? 'left-[18px]' : 'left-0.5'" />
                  </button>
                </div>

                <div class="border-t border-border my-1" />
                
                <!-- 人格切换 -->
                <div class="px-3 py-2">
                  <label class="text-xs text-text-secondary mb-1.5 block">当前人格</label>
                  <select v-model="activePersona" @change="switchPersona" class="input-base text-sm w-full">
                    <option v-for="p in personas" :key="p.name" :value="p.name">{{ p.name }}</option>
                  </select>
                </div>
                
                <!-- 模型切换 -->
                <div class="px-3 py-2">
                  <label class="text-xs text-text-secondary mb-1.5 block">当前模型</label>
                  <select v-model="selectedModel" @change="switchModel" class="input-base text-sm w-full">
                    <optgroup v-for="p in providers" :key="p.id" :label="p.name">
                      <option v-for="m in p.models" :key="p.id + '/' + m.id" :value="p.id + '/' + m.id" :disabled="!m.id || !m.enabled">
                        {{ m.id || '（空）' }}
                      </option>
                    </optgroup>
                    <option value="" disabled>暂无可用提供商</option>
                  </select>
                </div>
              </div>
            </div>
          </Transition>
        </div>
        
        <!-- 输入框 -->
        <div class="flex-1">
          <!-- 已上传文件预览 -->
          <div v-if="uploadedFiles.length > 0" class="flex flex-wrap gap-1.5 mb-1.5">
            <div v-for="(f, i) in uploadedFiles" :key="i" class="flex items-center gap-1 px-2 py-1 rounded-md bg-bg-hover text-xs text-text-primary group">
              <svg class="w-3 h-3 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
              </svg>
              <span class="truncate max-w-[120px]">{{ f.name }}</span>
              <button @click="uploadedFiles.splice(i, 1)" class="text-error hover:text-error/80 opacity-0 group-hover:opacity-100 transition-opacity leading-none">×</button>
            </div>
            <button @click="uploadedFiles = []" class="text-xs text-text-secondary hover:text-text-primary px-1 transition-colors">清空</button>
          </div>
          <textarea
            ref="textareaRef"
            v-model="inputText"
            @keydown="handleKeydown"
            @input="autoResize"
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            :disabled="disabled && !isStreaming"
            :rows="1"
            class="w-full px-4 py-2.5 bg-bg-input border border-border rounded-xl text-sm text-text-primary placeholder-text-secondary focus:outline-none focus:border-border-focus focus:ring-1 focus:ring-border-focus resize-none transition-colors disabled:opacity-50"
          />
        </div>
        
        <!-- 发送/停止按钮 -->
        <button
          v-if="!isStreaming"
          @click="handleSend"
          :disabled="!inputText.trim()"
          class="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-primary text-white hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
          </svg>
        </button>
        <button
          v-else
          @click="$emit('stop')"
          class="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-error text-white hover:opacity-90 transition-opacity"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="1"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { filesApi, personaApi, providerMgmtApi, configApi } from '@/api/index.js'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  isStreaming: { type: Boolean, default: false },
  streamingEnabled: { type: Boolean, default: true }
})

const emit = defineEmits(['send', 'stop', 'toggle-streaming'])

const inputText = ref('')
const textareaRef = ref(null)
const isDragging = ref(false)
const menuOpen = ref(false)
const menuRef = ref(null)
const personas = ref([])
const providers = ref([])
const activePersona = ref('')
const selectedModel = ref('')
const uploadedFiles = ref([])
const availableAgentNames = ref([])  // { file_id, name }

// 加载人格、提供商列表和当前配置
onMounted(async () => {
  try {
    const [pResult, pvResult, cfgResult] = await Promise.allSettled([
      personaApi.list(),
      providerMgmtApi.list(),
      configApi.get()
    ])
    
    if (pResult.status === 'fulfilled') {
      const p = pResult.value
      personas.value = Array.isArray(p) ? p : (p.personas || [])
      const active = personas.value.find(p => p.is_active)
      if (active) activePersona.value = active.name
    }
    
    if (pvResult.status === 'fulfilled') {
      providers.value = pvResult.value.providers || []
      // 匹配当前使用的模型
      const config = cfgResult.status === 'fulfilled' ? cfgResult.value : {}
      const currentModel = config.provider?.model
      if (currentModel) {
        for (const p of providers.value) {
          for (const m of p.models) {
            if (m.id === currentModel && m.enabled !== false) {
              selectedModel.value = p.id + '/' + m.id
              break
            }
          }
        }
      }
    }
  } catch (e) {}
  // 加载可用 Agent（供 @ 提示）
  try {
    const res = await fetch('/api/agents/names?enabled_only=true').then(r => r.json())
    availableAgentNames.value = Array.isArray(res) ? res : (res.agents || [])
  } catch (e) {}
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

const handleClickOutside = (e) => {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    menuOpen.value = false
  }
}

const switchPersona = async () => {
  try {
    await personaApi.activate(activePersona.value)
    showToast?.(`已切换至 ${activePersona.value}`, 'success')
  } catch (e) {
    showToast?.('切换失败: ' + e.message, 'error')
  }
  menuOpen.value = false
}

const switchModel = async () => {
  if (!selectedModel.value) return
  const [pid] = selectedModel.value.split('/')
  try {
    await providerMgmtApi.switch(pid)
    showToast?.('模型已切换', 'success')
  } catch (e) {
    showToast?.('切换失败: ' + e.message, 'error')
  }
  menuOpen.value = false
}

const autoResize = () => {
  const el = textareaRef.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    // 如果有 @ 菜单打开，选择 Agent
    if (window.__agentMenuOpen) {
      e.preventDefault()
      window.__agentMenuSelect?.()
      return
    }
    e.preventDefault()
    handleSend()
  }
}

const handleSend = () => {
  const text = inputText.value.trim()
  const fileIds = uploadedFiles.value.map(f => f.file_id)
  if (text || fileIds.length > 0) {
    emit('send', { text, fileIds })
    inputText.value = ''
    uploadedFiles.value = []
    nextTick(() => {
      autoResize()
      textareaRef.value?.focus()
    })
  }
}

const handleUpload = async (file) => {
  if (!file) return
  try {
    const data = await filesApi.upload(file)
    const fileId = data.file_id || file.name
    uploadedFiles.value.push({ file_id: fileId, name: file.name })
    showToast?.(`文件 ${file.name} 已上传`, 'success')
  } catch (err) {
    showToast?.('上传失败: ' + err.message, 'error')
  }
}

// 拖拽上传
const handleDrop = async (e) => {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    for (const file of files) {
      await handleUpload(file)
    }
  }
}

// 点击上传
const onFileSelected = async (e) => {
  await handleUpload(e.target.files?.[0])
  e.target.value = ''
}
</script>
