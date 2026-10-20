<template>
  <div class="panel">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-text-primary">Skills 管理</h2>
      <div class="flex gap-2">
        <label class="btn-secondary flex items-center gap-2 cursor-pointer">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/>
          </svg>
          上传技能包
          <input type="file" accept=".zip" class="hidden" @change="handleUpload" />
        </label>
        <button @click="showCreateModal = true" class="btn-primary">新建 Skill</button>
      </div>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
    <div v-else-if="skills.length === 0" class="card"><EmptyState title="暂无技能" description="上传 .zip 技能包或手动创建" /></div>
    <div v-else class="card overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-text-secondary border-b border-border">
            <th class="pb-3 font-medium">名称</th>
            <th class="pb-3 font-medium">描述</th>
            <th class="pb-3 font-medium">状态</th>
            <th class="pb-3 font-medium w-40">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="skill in skills" :key="skill.name" class="border-b border-border last:border-0">
            <td class="py-3 text-text-primary font-medium">{{ skill.name }}</td>
            <td class="py-3 text-text-secondary truncate max-w-xs">{{ skill.description || '-' }}</td>
            <td class="py-3">
              <Toggle :modelValue="skill.enabled" @update:modelValue="v => toggleSkill(skill, v)" />
            </td>
            <td class="py-3">
              <button @click="confirmDelete(skill.name)" class="text-error hover:underline text-xs">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <Modal :show="showCreateModal" title="新建 Skill" @update:show="showCreateModal = false">
      <div class="space-y-4">
        <div><label class="block text-sm text-text-secondary mb-1">名称</label><input v-model="form.name" class="input-base" /></div>
        <div><label class="block text-sm text-text-secondary mb-1">描述</label><input v-model="form.description" class="input-base" /></div>
        <div><label class="block text-sm text-text-secondary mb-1">Prompt</label><textarea v-model="form.prompt" class="input-base h-24 resize-none" /></div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showCreateModal = false">取消</button>
        <button class="btn-primary" @click="createSkill">创建</button>
      </template>
    </Modal>
    
    <ConfirmDialog
      :show="showDeleteConfirm"
      title="删除 Skill"
      :message="`确定要删除 Skill「${deleteTarget}」吗？`"
      @confirm="confirmDeleteSkill"
      @update:show="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { skillsApi } from '@/api/index.js'
import Toggle from '../shared/Toggle.vue'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'

const skills = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const showDeleteConfirm = ref(false)
const deleteTarget = ref('')
const form = ref({ name: '', description: '', prompt: '', enabled: true })

onMounted(() => loadSkills())

const loadSkills = async () => {
  loading.value = true
  try {
    const result = await skillsApi.list()
    skills.value = Array.isArray(result) ? result : (result.skills || [])
  } catch (e) {
    console.error('加载 Skills 失败:', e)
  } finally {
    loading.value = false
  }
}

const handleUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    await skillsApi.upload(file)
    showToast?.('技能包上传成功', 'success')
    await loadSkills()
  } catch (err) {
    showToast?.('上传失败: ' + err.message, 'error')
  }
  e.target.value = ''
}

const toggleSkill = async (skill, val) => {
  skill.enabled = val
  try {
    await skillsApi.update(skill.name, { enabled: val })
  } catch (e) {
    skill.enabled = !val
    showToast?.('更新失败: ' + e.message, 'error')
  }
}

const createSkill = async () => {
  try {
    await skillsApi.create(form.value)
    showCreateModal.value = false
    form.value = { name: '', description: '', prompt: '', enabled: true }
    await loadSkills()
    showToast?.('创建成功', 'success')
  } catch (e) {
    showToast?.('创建失败: ' + e.message, 'error')
  }
}

const confirmDelete = (name) => {
  deleteTarget.value = name
  showDeleteConfirm.value = true
}

const confirmDeleteSkill = async () => {
  try {
    await skillsApi.delete(deleteTarget.value)
    await loadSkills()
    showToast?.('已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}
</script>
