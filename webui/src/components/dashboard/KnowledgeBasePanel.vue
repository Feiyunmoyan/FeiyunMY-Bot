<template>
  <div class="panel">
    <div class="flex items-center justify-between mb-6">
      <h2 class="text-2xl font-bold text-text-primary">知识库</h2>
      <button @click="openCreate" class="btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
        </svg>
        创建知识库
      </button>
    </div>
    
    <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
    <div v-else-if="kbs.length === 0" class="card"><EmptyState title="暂无知识库" description="创建一个知识库来管理文档" /></div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div v-for="kb in kbs" :key="kb.id || kb.name" @click="selectKB(kb)" class="card cursor-pointer hover:ring-1 hover:ring-border-focus transition-all group">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="font-semibold text-text-primary">{{ kb.name }}</h3>
            <p class="text-xs text-text-secondary mt-1">{{ kb.description || '暂无描述' }}</p>
            <div v-if="kb.tags?.length" class="flex flex-wrap gap-1 mt-2">
              <span v-for="t in kb.tags" :key="t" class="text-[10px] px-1.5 py-0.5 rounded bg-bg-hover text-text-secondary">{{ t }}</span>
            </div>
          </div>
          <ChevronRight class="w-4 h-4 text-text-disabled flex-shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </div>
    
    <!-- 知识库详情弹窗 -->
    <Modal :show="showDetail" :title="selectedKB?.name || '知识库详情'" size="lg" @update:show="showDetail = false">
      <div class="space-y-4">
        <div class="flex gap-4">
          <div class="flex-1"><label class="text-sm text-text-secondary block mb-1">名称</label><input v-model="detailForm.name" class="input-base" /></div>
          <div class="flex-1"><label class="text-sm text-text-secondary block mb-1">标签</label><input v-model="tagInput" class="input-base" placeholder="输入后回车" @keydown.enter="addTag" /></div>
        </div>
        <div><label class="text-sm text-text-secondary block mb-1">描述</label><textarea v-model="detailForm.description" class="input-base h-16 resize-none" /></div>
        <div v-if="detailTags.length" class="flex flex-wrap gap-1">
          <span v-for="(t, i) in detailTags" :key="i" class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-bg-hover text-text-primary">{{ t }}<button @click="detailTags.splice(i, 1)" class="text-error hover:text-error/80 leading-none">×</button></span>
        </div>
        
        <div class="border-t border-border pt-3">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-text-primary">文档列表</span>
            <label class="text-xs btn-secondary py-1 px-2 cursor-pointer flex items-center gap-1">
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
              上传文档
              <input type="file" class="hidden" @change="uploadDoc" />
            </label>
          </div>
          <div v-if="documents.length === 0" class="text-xs text-text-disabled py-2">暂无文档</div>
          <div v-else class="space-y-1">
            <div v-for="doc in documents" :key="doc.id || doc.doc_id" class="flex items-center justify-between px-2 py-1.5 rounded bg-bg-hover/50 text-xs group">
              <span class="text-text-primary truncate flex-1">{{ doc.name || doc.filename || doc.id }}</span>
              <button @click="deleteDoc(doc)" class="text-error hover:underline opacity-0 group-hover:opacity-100 transition-opacity">删除</button>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showDetail = false">关闭</button>
        <button class="btn-primary" @click="saveKB">保存</button>
        <button class="btn-danger" @click="deleteKB(selectedKB)">删除知识库</button>
      </template>
    </Modal>
    
    <!-- 创建弹窗 -->
    <Modal :show="showCreate" title="创建知识库" @update:show="showCreate = false">
      <div class="space-y-3">
        <div><label class="text-sm text-text-secondary block mb-1">名称 *</label><input v-model="form.name" class="input-base" /></div>
        <div><label class="text-sm text-text-secondary block mb-1">描述</label><textarea v-model="form.description" class="input-base h-16 resize-none" /></div>
        <div><label class="text-sm text-text-secondary block mb-1">标签（逗号分隔）</label><input v-model="form.tags" class="input-base" placeholder="前端, Vue, 文档" /></div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="showCreate = false">取消</button>
        <button class="btn-primary" @click="createKB" :disabled="!form.name">创建</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'

const API = '/api'
const kbs = ref([])
const loading = ref(false)
const showDetail = ref(false)
const showCreate = ref(false)
const selectedKB = ref(null)
const documents = ref([])
const tagInput = ref('')
const detailTags = ref([])

const form = ref({ name: '', description: '', tags: '' })
const detailForm = ref({ name: '', description: '' })

onMounted(() => loadKBs())

const loadKBs = async () => {
  loading.value = true
  try {
    const res = await fetch(API + '/knowledge_bases').then(r => r.json())
    kbs.value = Array.isArray(res) ? res : (res.knowledge_bases || [])
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const openCreate = () => {
  form.value = { name: '', description: '', tags: '' }
  showCreate.value = true
}

const createKB = async () => {
  try {
    const tags = form.value.tags ? form.value.tags.split(/[,，]/).map(t => t.trim()).filter(Boolean) : []
    await fetch(API + '/knowledge_bases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: form.value.name, description: form.value.description, tags })
    })
    showCreate.value = false
    showToast?.('知识库已创建', 'success')
    await loadKBs()
  } catch (e) { showToast?.('创建失败: ' + e.message, 'error') }
}

const selectKB = async (kb) => {
  selectedKB.value = kb
  detailForm.value = { name: kb.name, description: kb.description || '' }
  detailTags.value = [...(kb.tags || [])]
  tagInput.value = ''
  showDetail.value = true
  await loadDocs(kb)
}

const loadDocs = async (kb) => {
  const id = kb.id || kb.name
  try {
    const res = await fetch(API + `/knowledge_bases/${id}/documents`).then(r => r.json())
    documents.value = Array.isArray(res) ? res : (res.documents || [])
  } catch (e) { documents.value = [] }
}

const addTag = () => {
  const t = tagInput.value.trim()
  if (t && !detailTags.value.includes(t)) detailTags.value.push(t)
  tagInput.value = ''
}

const saveKB = async () => {
  if (!selectedKB.value) return
  const id = selectedKB.value.id || selectedKB.value.name
  try {
    await fetch(API + `/knowledge_bases/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...detailForm.value, tags: detailTags.value })
    })
    showToast?.('已保存', 'success')
    await loadKBs()
  } catch (e) { showToast?.('保存失败: ' + e.message, 'error') }
}

const deleteKB = async (kb) => {
  if (!confirm(`确定要删除「${kb.name}」吗？`)) return
  const id = kb.id || kb.name
  try {
    await fetch(API + `/knowledge_bases/${id}`, { method: 'DELETE' })
    showDetail.value = false
    showToast?.('已删除', 'success')
    await loadKBs()
  } catch (e) { showToast?.('删除失败: ' + e.message, 'error') }
}

const uploadDoc = async (e) => {
  const file = e.target.files?.[0]
  if (!file || !selectedKB.value) return
  const id = selectedKB.value.id || selectedKB.value.name
  const fd = new FormData()
  fd.append('file', file)
  try {
    await fetch(API + `/knowledge_bases/${id}/upload`, { method: 'POST', body: fd })
    showToast?.('文档已上传', 'success')
    await loadDocs(selectedKB.value)
  } catch (err) { showToast?.('上传失败: ' + err.message, 'error') }
  e.target.value = ''
}

const deleteDoc = async (doc) => {
  if (!selectedKB.value) return
  const kid = selectedKB.value.id || selectedKB.value.name
  const did = doc.id || doc.doc_id
  try {
    await fetch(API + `/knowledge_bases/${kid}/documents/${did}`, { method: 'DELETE' })
    await loadDocs(selectedKB.value)
    showToast?.('文档已删除', 'success')
  } catch (e) { showToast?.('删除失败: ' + e.message, 'error') }
}
</script>
