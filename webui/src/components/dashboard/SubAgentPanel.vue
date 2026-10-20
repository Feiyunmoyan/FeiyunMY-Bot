<template>
  <div class="panel">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-text-primary">子 Agent 配置</h2>
      <button @click="openCreate" class="btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        创建 Agent
      </button>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
    <div v-else-if="agents.length === 0" class="card"><EmptyState title="暂无 Agent" description="创建一个子 Agent 来分担任务" /></div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div v-for="agent in agents" :key="agent.name" class="card group relative hover:ring-1 hover:ring-border-focus transition-all">
        <div class="flex items-start gap-3">
          <!-- 头像图标 -->
          <div class="w-10 h-10 rounded-lg bg-primary/15 flex items-center justify-center flex-shrink-0">
            <component :is="getAgentIcon(agent)" class="w-5 h-5 text-primary" />
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="font-semibold text-text-primary">{{ agent.display_name || agent.name }}</h3>
            <p class="text-xs text-text-secondary mt-0.5">
              <span class="font-mono">{{ agent.name }}</span>
              <span class="mx-1.5">·</span>
              {{ agent.model_id || '未设置模型' }}
              <span v-if="agent.persona_id" class="mx-1.5">·</span>
              {{ agent.persona_id || '' }}
            </p>
            <p class="text-xs text-text-secondary mt-1.5 line-clamp-2">{{ agent.description || '暂无描述' }}</p>
            <!-- 工具标签 -->
            <div v-if="agent.tools_enabled?.length" class="flex flex-wrap gap-1 mt-2">
              <span v-for="t in agent.tools_enabled" :key="t" class="text-[10px] px-1.5 py-0.5 rounded bg-bg-hover text-text-secondary">{{ t }}</span>
            </div>
          </div>
          <!-- 操作按钮 -->
          <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button @click="openEdit(agent)" class="p-1.5 rounded hover:bg-bg-hover text-text-secondary" title="编辑">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
              </svg>
            </button>
            <button @click="confirmDelete(agent)" class="p-1.5 rounded hover:bg-bg-hover text-error" title="删除">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 创建/编辑弹窗 -->
    <Modal :show="showModal" :title="editing ? '编辑 Agent' : '创建 Agent'" size="lg" @update:show="showModal = false">
      <div class="grid grid-cols-2 gap-x-4 gap-y-3">
        <div>
          <label class="block text-sm text-text-secondary mb-1">名称 *</label>
          <input v-model="form.name" class="input-base" placeholder="唯一标识，如 code" :disabled="!!editing" />
        </div>
        <div>
          <label class="block text-sm text-text-secondary mb-1">显示名称</label>
          <input v-model="form.display_name" class="input-base" placeholder="程序员助手" />
        </div>
        <div class="col-span-2">
          <label class="block text-sm text-text-secondary mb-1">描述</label>
          <input v-model="form.description" class="input-base" placeholder="擅长..." />
        </div>
        <div>
          <label class="block text-sm text-text-secondary mb-1">模型</label>
          <select v-model="form.model_id" class="input-base">
            <option value="">请选择</option>
            <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm text-text-secondary mb-1">人格</label>
          <select v-model="form.persona_id" class="input-base">
            <option value="">请选择</option>
            <option v-for="p in personas" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
        </div>
        <div class="flex items-center gap-3">
          <Toggle v-model="form.memory_enabled" />
          <span class="text-sm text-text-secondary">启用记忆</span>
        </div>
        <div class="flex items-center gap-2">
          <label class="text-sm text-text-secondary whitespace-nowrap">温度</label>
          <input v-model.number="form.temperature" type="range" min="0" max="2" step="0.1" class="flex-1 accent-primary" />
          <span class="text-sm text-text-primary w-8 text-right">{{ form.temperature }}</span>
        </div>
        <div class="col-span-2">
          <label class="block text-sm text-text-secondary mb-1">启用的工具</label>
          <div class="flex flex-wrap gap-3">
            <label v-for="t in allTools" :key="t.key" class="flex items-center gap-1.5 cursor-pointer text-sm text-text-primary">
              <input type="checkbox" :checked="form.tools_enabled.includes(t.key)" @change="toggleTool(t.key)" class="accent-primary" />
              {{ t.label }}
            </label>
          </div>
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showModal = false">取消</button>
        <button class="btn-primary" @click="save" :disabled="!form.name">保存</button>
      </template>
    </Modal>
    
    <ConfirmDialog
      :show="showDeleteConfirm"
      title="删除 Agent"
      :message="`确定要删除 Agent「${deleteTarget?.display_name || deleteTarget?.name}」吗？`"
      @confirm="confirmDeleteAgent"
      @update:show="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { personaApi } from '@/api/index.js'
import { Bot, Code2, Palette, Feather } from 'lucide-vue-next'
import Toggle from '../shared/Toggle.vue'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'

const agents = ref([])
const personas = ref([])
const models = ref([])
const loading = ref(false)
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const editing = ref(null)
const deleteTarget = ref(null)

const form = ref({
  name: '', display_name: '', description: '',
  model_id: '', persona_id: '',
  memory_enabled: true, temperature: 0.7,
  tools_enabled: []
})

const allTools = [
  { key: 'web', label: '网络' }, { key: 'execute', label: '执行' },
  { key: 'file_ops', label: '文件' }, { key: 'common_utils', label: '通用' },
  { key: 'http_request', label: 'HTTP' }, { key: 'memory_query', label: '记忆查询' },
  { key: 'note_taking', label: '笔记' },
]

const API_BASE = '/api'

onMounted(async () => {
  loading.value = true
  try {
    const agentsRes = await fetch(API_BASE + '/agents').then(r => r.json())
    const personasRes = await personaApi.list()
    // 从现有提供商获取模型列表
    let modelsList = []
    try {
      const pv = await fetch(API_BASE + '/providers').then(r => r.json())
      const providers = pv.providers || []
      for (const p of providers) {
        for (const m of p.models || []) {
          if (m.id && m.enabled !== false && !modelsList.includes(m.id)) {
            modelsList.push(m.id)
          }
        }
      }
    } catch {}
    // 兜底：常见模型
    if (modelsList.length === 0) {
      modelsList = ['deepseek-chat', 'deepseek-reasoner']
    }
    
    agents.value = Array.isArray(agentsRes) ? agentsRes : (agentsRes.agents || [])
    personas.value = Array.isArray(personasRes) ? personasRes : (personasRes.personas || [])
    models.value = modelsList
  } catch (e) {
    console.error('加载数据失败:', e)
  } finally {
    loading.value = false
  }
})

const getAgentIcon = (agent) => {
  const name = (agent.name || '').toLowerCase()
  if (name.includes('code') || name.includes('dev') || name.includes('程序')) return Code2
  if (name.includes('design') || name.includes('ui') || name.includes('设计')) return Palette
  if (name.includes('write') || name.includes('文案') || name.includes('写作')) return Feather
  return Bot
}

const openCreate = () => {
  editing.value = null
  form.value = { name: '', display_name: '', description: '', model_id: '', persona_id: '', memory_enabled: true, temperature: 0.7, tools_enabled: [] }
  showModal.value = true
}

const openEdit = (agent) => {
  editing.value = agent
  form.value = {
    name: agent.name, display_name: agent.display_name || '',
    description: agent.description || '', model_id: agent.model_id || '',
    persona_id: agent.persona_id || '', memory_enabled: agent.memory_enabled ?? true,
    temperature: agent.temperature ?? 0.7,
    tools_enabled: [...(agent.tools_enabled || [])],
  }
  showModal.value = true
}

const toggleTool = (key) => {
  const idx = form.value.tools_enabled.indexOf(key)
  if (idx > -1) form.value.tools_enabled.splice(idx, 1)
  else form.value.tools_enabled.push(key)
}

const save = async () => {
  try {
    const data = { ...form.value }
    const url = API_BASE + (editing.value ? `/agents/${editing.value.name}` : '/agents')
    const method = editing.value ? 'PUT' : 'POST'
    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    if (!res.ok) throw new Error((await res.json()).detail || '请求失败')
    showModal.value = false
    const agentsRes = await fetch(API_BASE + '/agents').then(r => r.json())
    agents.value = Array.isArray(agentsRes) ? agentsRes : (agentsRes.agents || [])
    showToast?.('保存成功', 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

const confirmDelete = (agent) => {
  deleteTarget.value = agent
  showDeleteConfirm.value = true
}

const confirmDeleteAgent = async () => {
  try {
    await fetch(API_BASE + `/agents/${deleteTarget.value.agent_id}`, { method: 'DELETE' })
    agents.value = agents.value.filter(a => a.name !== deleteTarget.value.name)
    showToast?.('已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
