<template>
  <div class="panel">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-text-primary">人格管理</h2>
      <button @click="showCreateModal = true" class="btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        新建人格
      </button>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12">
      <LoadingSpinner size="lg" />
    </div>
    
    <div v-else-if="personas.length === 0" class="card">
      <EmptyState title="暂无人格" description="点击「新建人格」创建第一个 AI 人格" />
    </div>
    
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div 
        v-for="persona in personas" 
        :key="persona.name"
        :class="[
          'card relative',
          persona.is_active && 'ring-2 ring-success'
        ]"
      >
        <div class="flex items-start justify-between mb-3">
          <h3 class="text-lg font-semibold text-text-primary">{{ persona.name }}</h3>
          <Badge v-if="persona.is_active" variant="success">使用中</Badge>
        </div>
        
        <p class="text-sm text-text-secondary mb-4 line-clamp-2">{{ persona.description || '暂无描述' }}</p>
        
        <div class="flex items-center gap-2">
          <button 
            v-if="!persona.is_active"
            @click="handleActivate(persona.name)"
            class="btn-primary text-sm"
          >
            激活
          </button>
          <button @click="handleEdit(persona)" class="btn-secondary text-sm">编辑</button>
          <button @click="handleDelete(persona.name, persona.is_active)" class="btn-danger text-sm">删除</button>
        </div>
      </div>
    </div>
    
    <!-- 创建/编辑弹窗 -->
    <Modal :show="showCreateModal" :title="editingPersona ? '编辑人格' : '新建人格'" size="xl" @update:show="showCreateModal = false">
      <div class="flex gap-6 min-h-[400px]">
        <!-- 左侧：名称、描述、提示词 -->
        <div class="w-1/2 space-y-4">
          <div>
            <label class="block text-sm text-text-secondary mb-1">名称</label>
            <input v-model="form.name" class="input-base" placeholder="例如：助手" :disabled="!!editingPersona" />
          </div>
          <div>
            <label class="block text-sm text-text-secondary mb-1">描述</label>
            <input v-model="form.description" class="input-base" placeholder="简短描述这个人格" />
          </div>
          <div>
            <label class="block text-sm text-text-secondary mb-1">系统提示词</label>
            <textarea v-model="form.prompt" class="input-base h-60 resize-none" placeholder="输入 System Prompt，定义人格的行为方式和回复风格..." />
          </div>
        </div>
        
        <!-- 右侧：预设对话 -->
        <div class="w-1/2 border-l border-border pl-6">
          <div class="flex items-center justify-between mb-3">
            <label class="block text-sm text-text-secondary">预设对话（一问一答）</label>
            <button @click="addPresetPair" class="text-xs btn-primary py-1 px-2">+ 添加问答</button>
          </div>
          <div class="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            <div v-for="(pair, index) in form.preset_conversations" :key="index" class="border border-border rounded-lg p-3">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-text-disabled">问答 #{{ index + 1 }}</span>
                <button @click="removePresetPair(index)" class="text-error hover:underline text-xs">删除</button>
              </div>
              <div class="space-y-2">
                <div>
                  <span class="text-xs text-text-secondary block mb-1">👤 用户：</span>
                  <textarea v-model="pair.user" class="input-base text-sm h-16 resize-none" placeholder="用户的问题..." />
                </div>
                <div>
                  <span class="text-xs text-text-secondary block mb-1">🤖 AI 回复：</span>
                  <textarea v-model="pair.assistant" class="input-base text-sm h-20 resize-none" placeholder="AI 的回答..." />
                </div>
              </div>
            </div>
            <div v-if="form.preset_conversations.length === 0" class="text-center py-8 text-text-disabled text-sm">
              暂无预设对话<br>
              点击上方「添加问答」来设置对话示例
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showCreateModal = false">取消</button>
        <button class="btn-primary" @click="handleSave" :disabled="!form.name">保存</button>
      </template>
    </Modal>
    
    <!-- 确认删除 -->
    <ConfirmDialog 
      :show="showDeleteConfirm" 
      title="删除人格" 
      :message="`确定要删除人格「${deleteTarget}」吗？此操作不可撤销。`"
      @confirm="confirmDelete"
      @update:show="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { personaApi } from '@/api/index.js'
import Badge from '../shared/Badge.vue'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'

const personas = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const showDeleteConfirm = ref(false)
const deleteTarget = ref('')
const editingPersona = ref(null)

const form = ref({ name: '', description: '', prompt: '', preset_conversations: [] })

onMounted(() => loadPersonas())

// 关闭弹窗时重置表单（无论点取消还是点×）
watch(() => showCreateModal.value, (val) => {
  if (!val) {
    setTimeout(() => {
      editingPersona.value = null
      form.value = { name: '', description: '', prompt: '', preset_conversations: [] }
    }, 200)  // 等弹窗关闭动画结束再重置
  }
})

const addPresetPair = () => {
  form.value.preset_conversations.push({ user: '', assistant: '' })
}

const removePresetPair = (index) => {
  form.value.preset_conversations.splice(index, 1)
}

const loadPersonas = async () => {
  loading.value = true
  try {
    const result = await personaApi.list()
    personas.value = Array.isArray(result) ? result : (result.personas || [])
  } catch (e) {
    console.error('加载人格失败:', e)
  } finally {
    loading.value = false
  }
}

const handleActivate = async (name) => {
  try {
    await personaApi.activate(name)
    await loadPersonas()
    showToast?.('人格已切换', 'success')
  } catch (e) {
    showToast?.('切换失败: ' + e.message, 'error')
  }
}

const handleEdit = async (persona) => {
  // 获取完整详情（含预设对话）
  try {
    const detail = await personaApi.get(persona.name)
    if (detail) persona = detail
  } catch (e) {
    showToast?.('加载人格详情失败，部分数据可能不完整', 'warning')
  }
  editingPersona.value = persona
  form.value = { 
    name: persona.name, 
    description: persona.description || '', 
    prompt: persona.prompt || '',
    preset_conversations: persona.preset_conversations ? JSON.parse(JSON.stringify(persona.preset_conversations)) : []
  }
  showCreateModal.value = true
}

const handleDelete = (name, isActive) => {
  if (isActive) {
    showToast?.('「' + name + '」正在使用中，请先切换其他人格再删除', 'warning')
    return
  }
  deleteTarget.value = name
  showDeleteConfirm.value = true
}

const confirmDelete = async () => {
  try {
    await personaApi.delete(deleteTarget.value)
    await loadPersonas()
    showToast?.('人格已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}

const handleSave = async () => {
  try {
    if (editingPersona.value) {
      await personaApi.update(editingPersona.value.name, {
        description: form.value.description,
        prompt: form.value.prompt,
        preset_conversations: form.value.preset_conversations,
      })
    } else {
      await personaApi.create({
        name: form.value.name,
        description: form.value.description,
        prompt: form.value.prompt,
        preset_conversations: form.value.preset_conversations,
      })
    }
    showCreateModal.value = false
    editingPersona.value = null
    form.value = { name: '', description: '', prompt: '', preset_conversations: [] }
    await loadPersonas()
    showToast?.('保存成功', 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
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
