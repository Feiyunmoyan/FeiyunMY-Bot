<template>
  <div class="panel">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-text-primary">MCP 服务器管理</h2>
      <button @click="showCreateModal = true" class="btn-primary">添加服务器</button>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
    <div v-else-if="servers.length === 0" class="card"><EmptyState title="暂无 MCP 服务器" description="添加一个 MCP 服务器来扩展 AI 能力" /></div>
    <div v-else class="space-y-4">
      <div v-for="server in servers" :key="server.name" class="card">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="w-2.5 h-2.5 rounded-full" :class="server.enabled ? 'bg-success' : 'bg-text-disabled'" />
            <div>
              <h3 class="font-medium text-text-primary">{{ server.name }}</h3>
              <p class="text-xs text-text-secondary">{{ server.description || server.url || '无描述' }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Toggle :modelValue="server.enabled" @update:modelValue="v => toggleServer(server, v)" />
            <button @click="confirmDelete(server.name)" class="text-error text-sm hover:underline">删除</button>
          </div>
        </div>
      </div>
    </div>
    
    <Modal :show="showCreateModal" title="添加 MCP 服务器" size="md" @update:show="showCreateModal = false">
      <div class="space-y-4">
        <div><label class="block text-sm text-text-secondary mb-1">名称</label><input v-model="form.name" class="input-base" /></div>
        <div><label class="block text-sm text-text-secondary mb-1">URL / 命令</label><input v-model="form.url" class="input-base" placeholder="http://... 或命令路径" /></div>
        <div><label class="block text-sm text-text-secondary mb-1">描述</label><input v-model="form.description" class="input-base" /></div>
        <div class="flex items-center gap-2">
          <Toggle v-model="form.enabled" />
          <span class="text-sm text-text-secondary">启用</span>
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showCreateModal = false">取消</button>
        <button class="btn-primary" @click="createServer">添加</button>
      </template>
    </Modal>
    
    <ConfirmDialog
      :show="showDeleteConfirm"
      title="删除服务器"
      :message="`确定要删除 MCP 服务器「${deleteTarget}」吗？`"
      @confirm="confirmDeleteServer"
      @update:show="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { mcpApi } from '@/api/index.js'
import Toggle from '../shared/Toggle.vue'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'

const servers = ref([])
const loading = ref(false)
const showCreateModal = ref(false)
const showDeleteConfirm = ref(false)
const deleteTarget = ref('')
const form = ref({ name: '', url: '', description: '', enabled: true })

onMounted(() => loadServers())

const loadServers = async () => {
  loading.value = true
  try {
    const result = await mcpApi.list()
    servers.value = Array.isArray(result) ? result : (result.servers || [])
  } catch (e) {
    console.error('加载 MCP 服务器失败:', e)
  } finally {
    loading.value = false
  }
}

const createServer = async () => {
  try {
    await mcpApi.create(form.value)
    showCreateModal.value = false
    form.value = { name: '', url: '', description: '', enabled: true }
    await loadServers()
    showToast?.('服务器已添加', 'success')
  } catch (e) {
    showToast?.('添加失败: ' + e.message, 'error')
  }
}

const toggleServer = async (server, val) => {
  server.enabled = val
  try {
    await mcpApi.update(server.name, { enabled: val })
  } catch (e) {
    server.enabled = !val
    showToast?.('切换失败: ' + e.message, 'error')
  }
}

const confirmDelete = (name) => {
  deleteTarget.value = name
  showDeleteConfirm.value = true
}

const confirmDeleteServer = async () => {
  try {
    await mcpApi.delete(deleteTarget.value)
    await loadServers()
    showToast?.('已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}
</script>
