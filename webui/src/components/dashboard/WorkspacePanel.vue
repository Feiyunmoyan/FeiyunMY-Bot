<template>
  <div class="flex w-full h-full">
    <!-- 左侧栏 -->
    <aside class="w-56 h-full bg-bg-card border-r border-border flex flex-col transition-colors duration-300">
      <div class="p-3 border-b border-border">
        <h2 class="text-base font-semibold text-text-primary">工作空间</h2>
      </div>
      
      <nav class="flex-1 overflow-y-auto p-2 space-y-0.5">
        <button @click="activeSection = 'list'" :class="mainBtnClass('list')">
          <Layers class="w-4 h-4" />
          <span>所有空间</span>
        </button>
        
        <!-- 每个工作空间是一个折叠组 -->
        <div v-for="ws in workspaces" :key="ws.id || ws.name" class="mt-1">
          <button @click="toggleWorkspace(ws)" :class="wsHeaderClass(ws)">
            <ChevronRight class="w-3.5 h-3.5 transition-transform flex-shrink-0" :class="{ 'rotate-90': expandedWorkspaces[ws.id || ws.name] }" />
            <span class="truncate flex-1">{{ ws.name }}</span>
          </button>
          
          <div v-if="expandedWorkspaces[ws.id || ws.name]" class="ml-3 pl-2 border-l-2 border-border/50 space-y-0.5 mt-0.5">
            <button @click="selectAndView(ws, 'detail')" :class="subBtnClass('detail', ws)">
              <Info class="w-3.5 h-3.5" /> 空间详情
            </button>
            <button @click="selectAndView(ws, 'tasks')" :class="subBtnClass('tasks', ws)">
              <CheckSquare class="w-3.5 h-3.5" /> 任务管理
            </button>
            <button @click="selectAndView(ws, 'agents')" :class="subBtnClass('agents', ws)">
              <Bot class="w-3.5 h-3.5" /> Agent 状态
            </button>
            <button @click="selectAndView(ws, 'stats')" :class="subBtnClass('stats', ws)">
              <BarChart3 class="w-3.5 h-3.5" /> 空间统计
            </button>
            <button @click="selectAndView(ws, 'chat')" :class="subBtnClass('chat', ws)">
              <MessageSquare class="w-3.5 h-3.5" /> 对话
            </button>
          </div>
        </div>
        
        <button @click="openCreate" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-all mt-2">
          <Plus class="w-4 h-4" />
          <span>新建空间</span>
        </button>
        
        <!-- 子代理编排（可折叠） -->
        <div class="border-t border-border pt-2 mt-3">
          <button @click="wsSubagentExpanded = !wsSubagentExpanded" class="w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-all text-left text-text-secondary hover:text-text-primary hover:bg-bg-hover rounded-lg">
            <GitBranch class="w-4 h-4" />
            <span class="flex-1 text-left">子代理编排</span>
            <svg class="w-4 h-4 transition-transform duration-200" :class="{ 'rotate-90': wsSubagentExpanded }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
          </button>
          <Transition name="submenu">
            <div v-if="wsSubagentExpanded" class="ml-3 pl-2 border-l-2 border-border/50 space-y-0.5 mt-0.5">
              <button @click="activeSection = 'subagent'" :class="mainBtnClass('subagent')" class="w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-all text-left text-text-secondary hover:text-text-primary hover:bg-bg-hover">
                <BarChart3 class="w-3.5 h-3.5" /> 启用/禁用子Agent
              </button>
            </div>
          </Transition>
        </div>
      </nav>
    </aside>
    
    <!-- 右侧内容 -->
    <div class="flex-1 overflow-y-auto">
      <!-- 所有空间列表 -->
      <div v-if="activeSection === 'list'" class="p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-2xl font-bold text-text-primary">所有工作空间</h2>
        </div>
        <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
        <div v-else-if="workspaces.length === 0" class="card"><EmptyState title="暂无工作空间" description="点击左侧「新建空间」创建" /></div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="ws in workspaces" :key="ws.id || ws.name" @click="toggleWorkspace(ws)" class="card cursor-pointer hover:ring-1 hover:ring-border-focus transition-all group">
            <div class="flex items-start justify-between gap-3">
              <div class="flex-1 min-w-0">
                <h3 class="font-semibold text-text-primary truncate">{{ ws.name }}</h3>
                <p class="text-xs text-text-secondary mt-1">{{ ws.description || '暂无描述' }}</p>
                <div class="flex items-center gap-3 mt-2 text-xs text-text-secondary">
                  <span>📋 {{ ws.total_tasks ?? '-' }} 任务</span>
                  <span>🤖 {{ ws.total_agents ?? '-' }} Agent</span>
                </div>
              </div>
              <ChevronRight class="w-4 h-4 text-text-disabled flex-shrink-0 mt-1" />
            </div>
          </div>
        </div>
      </div>
      
      <!-- 新建空间 -->
      <div v-if="activeSection === 'create'" class="p-6 max-w-2xl">
        <h2 class="text-2xl font-bold text-text-primary mb-6">新建工作空间</h2>
        <div class="card space-y-4">
          <div><label class="block text-sm text-text-secondary mb-1">名称 *</label><input v-model="form.name" class="input-base" placeholder="博客项目" /></div>
          <div><label class="block text-sm text-text-secondary mb-1">描述</label><textarea v-model="form.description" class="input-base h-20 resize-none" placeholder="简要描述这个项目的目标" /></div>
          <div>
            <label class="block text-sm text-text-secondary mb-1">参与 Agent（可选）</label>
            <div v-if="availableAgents.length === 0" class="text-xs text-text-disabled py-1">暂无已配置的 Agent，可前往「子 Agent 配置」创建</div>
            <div v-else class="flex flex-wrap gap-2">
              <button
                v-for="a in availableAgents"
                :key="a.agent_id"
                @click="toggleAgent(a)"
                :class="selectedAgentIds.includes(a.agent_id)
                  ? 'btn-primary text-xs px-3 py-1.5'
                  : 'btn-secondary text-xs px-3 py-1.5'"
              >
                {{ a.name }}
              </button>
            </div>
          </div>
          <div class="flex gap-3">
            <button @click="createWorkspace" class="btn-primary" :disabled="!form.name">创建</button>
            <button @click="activeSection = 'list'" class="btn-secondary">取消</button>
          </div>
        </div>
      </div>
      
      <!-- 空间详情 -->
      <div v-if="activeSection === 'detail' && selectedWorkspace" class="p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-2xl font-bold text-text-primary">{{ selectedWorkspace.name }}</h2>
          <button @click="enterWorkspaceChat(selectedWorkspace)" class="btn-primary text-sm flex items-center gap-1.5">
            <MessageSquare class="w-4 h-4" /> 进入对话
          </button>
        </div>
        <div class="card space-y-4">
          <div><label class="text-sm text-text-secondary block">名称</label><input v-model="detailForm.name" class="input-base mt-1" /></div>
          <div><label class="text-sm text-text-secondary block">描述</label><textarea v-model="detailForm.description" class="input-base h-20 resize-none mt-1" /></div>
          <div class="flex gap-3">
            <button @click="updateWorkspace" class="btn-primary">保存修改</button>
            <button @click="deleteWorkspace(selectedWorkspace)" class="btn-danger">删除空间</button>
          </div>
        </div>
        <!-- 空间 Agent 管理 -->
        <div class="card mt-4 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-text-primary">空间 Agent</h3>
            <button @click="showDetailAgentModal = true" class="btn-primary text-xs px-3 py-1.5 flex items-center gap-1">
              <Plus class="w-3.5 h-3.5" /> 添加 Agent
            </button>
          </div>
          <div v-if="detailAgents.length === 0" class="text-xs text-text-disabled py-2">暂无 Agent，点击「添加 Agent」从已启用的 Agent 中选择</div>
          <div v-else class="space-y-2">
            <div v-for="a in detailAgents" :key="a.name" class="flex items-center justify-between py-1.5 px-2 rounded bg-bg-hover/50">
              <div class="flex items-center gap-2">
                <Bot class="w-4 h-4 text-primary" />
                <span class="text-sm text-text-primary">{{ a.name }}</span>
                <span class="text-xs text-text-secondary">{{ a.display_name || '' }}</span>
              </div>
              <button @click="removeAgentFromDetail(a)" class="text-xs text-error hover:text-error/80">移除</button>
            </div>
          </div>
        </div>
        <!-- 添加 Agent 弹窗 -->
        <Modal :show="showDetailAgentModal" title="添加 Agent 到工作空间" @update:show="showDetailAgentModal = false">
          <div v-if="enabledAgentsForDetail.length === 0" class="text-sm text-text-secondary py-4 text-center">没有更多可添加的 Agent</div>
          <div v-else class="space-y-2">
            <button
              v-for="a in enabledAgentsForDetail"
              :key="a.agent_id"
              @click="addAgentToDetail(a)"
              class="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-bg-hover text-left transition-all"
            >
              <Bot class="w-4 h-4 text-primary" />
              <div>
                <p class="text-sm text-text-primary">{{ a.display_name || a.name }}</p>
                <p class="text-xs text-text-secondary font-mono">{{ a.name }}</p>
              </div>
            </button>
          </div>
        </Modal>
      </div>
      
      <!-- 任务管理 -->
      <div v-if="activeSection === 'tasks' && selectedWorkspace" class="p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-2xl font-bold text-text-primary">任务管理 · {{ selectedWorkspace.name }}</h2>
          <button @click="showTaskModal = true" class="btn-primary text-sm flex items-center gap-1.5">
            <Plus class="w-4 h-4" /> 添加任务
          </button>
        </div>
        <div v-if="tasks.length === 0" class="card"><EmptyState title="暂无任务" description="添加第一个任务开始工作" /></div>
        <div v-else class="space-y-2">
          <div v-for="t in tasks" :key="t.id || t.task_id" class="card flex items-center justify-between">
            <div>
              <p class="text-sm text-text-primary font-medium">{{ t.description }}</p>
              <p class="text-xs text-text-secondary mt-0.5">Agent: {{ t.agent }} · {{ t.status || 'pending' }}</p>
            </div>
            <select :value="t.status" @change="updateTaskStatus(t, $event.target.value)" class="input-base w-28 text-sm">
              <option value="pending">待处理</option>
              <option value="working">进行中</option>
              <option value="done">已完成</option>
              <option value="failed">失败</option>
            </select>
          </div>
        </div>
        
        <Modal :show="showTaskModal" title="添加任务" @update:show="showTaskModal = false">
          <div class="space-y-3">
            <div><label class="block text-sm text-text-secondary mb-1">负责 Agent</label><input v-model="taskForm.agent" class="input-base" placeholder="code" /></div>
            <div><label class="block text-sm text-text-secondary mb-1">任务描述</label><textarea v-model="taskForm.description" class="input-base h-20 resize-none" placeholder="用Vue搭建前端框架" /></div>
          </div>
          <template #footer>
            <button class="btn-secondary" @click="showTaskModal = false">取消</button>
            <button class="btn-primary" @click="addTask">添加</button>
          </template>
        </Modal>
      </div>
      
      <!-- Agent 状态 -->
      <div v-if="activeSection === 'agents' && selectedWorkspace" class="p-6">
        <h2 class="text-2xl font-bold text-text-primary mb-6">Agent 状态 · {{ selectedWorkspace.name }}</h2>
        <div v-if="wsAgents.length === 0" class="card"><EmptyState title="暂无 Agent" description="在空间详情中可配置 Agent" /></div>
        <div v-else class="space-y-3">
          <div v-for="a in wsAgents" :key="a.name" class="card">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <Bot class="w-5 h-5 text-primary" />
                <div>
                  <p class="text-sm font-medium text-text-primary">{{ a.name }}</p>
                  <p class="text-xs text-text-secondary">{{ a.progress || a.status || '空闲中' }}</p>
                </div>
              </div>
              <span class="text-xs px-2 py-0.5 rounded" :class="statusClass(a.status)">{{ a.status || 'idle' }}</span>
            </div>
          </div>
        </div>
        <!-- 命令执行区域 -->
        <div class="card mt-4">
          <h3 class="text-sm font-semibold text-text-primary mb-2">执行命令</h3>
          <p class="text-xs text-text-secondary mb-2">输入 @Agent名称 任务描述 来指派任务给子 Agent</p>
          <div class="flex gap-2">
            <input v-model="execCommand" class="input-base flex-1" placeholder='例如: @code 帮我写个登录页面' @keydown.enter="executeCommand" />
            <button @click="executeCommand" class="btn-primary text-sm px-4 whitespace-nowrap" :disabled="executing">执行</button>
          </div>
          <div v-if="execResult" class="mt-3 p-3 rounded bg-bg-hover/50 text-sm text-text-primary whitespace-pre-wrap max-h-60 overflow-y-auto">{{ execResult }}</div>
        </div>
      </div>
      
      <!-- 工作空间对话 -->
      <div v-if="activeSection === 'chat' && selectedWorkspace" class="p-6 flex flex-col h-full">
        <div class="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 class="text-2xl font-bold text-text-primary">对话 · {{ selectedWorkspace.name }}</h2>
          <button @click="activeSection = 'detail'" class="btn-secondary text-sm">返回详情</button>
        </div>
        <div class="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0">
          <div v-for="(msg, i) in chatMessages" :key="i" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
            <div class="max-w-[80%] p-3 rounded-lg" :class="msg.role === 'user' ? 'bg-primary/15 text-text-primary' : 'bg-bg-hover/70 text-text-primary'">
              <p class="text-xs text-text-secondary mb-1">{{ msg.role === 'user' ? '我' : msg.agent || 'AI' }}</p>
              <p class="text-sm whitespace-pre-wrap">{{ msg.content }}</p>
            </div>
          </div>
          <div v-if="chatLoading" class="flex justify-center"><LoadingSpinner size="sm" /></div>
        </div>
        <div class="flex gap-2 flex-shrink-0">
          <input v-model="chatInput" class="input-base flex-1" placeholder='输入消息或 @Agent名称 任务描述' @keydown.enter="sendChatMessage" :disabled="chatLoading" />
          <button @click="sendChatMessage" class="btn-primary text-sm px-4 whitespace-nowrap" :disabled="chatLoading || !chatInput.trim()">发送</button>
        </div>
      </div>
      
      <!-- 空间统计 -->
      <div v-if="activeSection === 'stats' && selectedWorkspace" class="p-6">
        <h2 class="text-2xl font-bold text-text-primary mb-6">空间统计 · {{ selectedWorkspace.name }}</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div class="card text-center"><p class="text-2xl font-bold text-primary">{{ wsStats.total_tasks || 0 }}</p><p class="text-xs text-text-secondary mt-1">总任务</p></div>
          <div class="card text-center"><p class="text-2xl font-bold text-success">{{ wsStats.done_tasks || 0 }}</p><p class="text-xs text-text-secondary mt-1">已完成</p></div>
          <div class="card text-center"><p class="text-2xl font-bold text-warning">{{ wsStats.working_tasks || 0 }}</p><p class="text-xs text-text-secondary mt-1">进行中</p></div>
          <div class="card text-center"><p class="text-2xl font-bold text-info">{{ Math.round(wsStats.token_usage / 1000) || 0 }}k</p><p class="text-xs text-text-secondary mt-1">Token</p></div>
        </div>
      </div>
      <!-- 子代理编排 · Agent 启用管理 -->
      <div v-if="activeSection === 'subagent'" class="p-6 max-w-5xl">
        <h2 class="text-2xl font-bold text-text-primary mb-6">子代理编排 · Agent 工作空间可用性</h2>
        <p class="text-sm text-text-secondary mb-4">在此页面启用或禁用在仪表盘中已配置的 Agent，只有启用了的 Agent 才能在创建工作空间或空间详情时选择。</p>
        <div v-if="allAgentsLoading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
        <div v-else-if="allAgents.length === 0" class="card"><EmptyState title="暂无 Agent" description="请先在仪表盘的「子 Agent 配置」中创建 Agent" /></div>
        <div v-else class="space-y-2">
          <div v-for="a in allAgents" :key="a.agent_id || a.name" class="card flex items-center justify-between">
            <div class="flex items-center gap-3">
              <Bot class="w-5 h-5 text-primary" />
              <div>
                <p class="text-sm font-medium text-text-primary">{{ a.display_name || a.name }}</p>
                <p class="text-xs text-text-secondary">
                  <span class="font-mono">{{ a.name }}</span>
                  <span v-if="a.model_id" class="ml-2">{{ a.model_id }}</span>
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-text-secondary">{{ a.enabled_for_workspace !== false ? '已启用' : '已禁用' }}</span>
              <Toggle
                :modelValue="a.enabled_for_workspace !== false"
                @update:modelValue="toggleAgentWorkspace(a)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <!-- 删除确认 -->
  <ConfirmDialog
    :show="showDeleteConfirm"
    title="删除工作空间"
    :message="`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`"
    @confirm="confirmDeleteWs"
    @update:show="showDeleteConfirm = false"
  />
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { Layers, Plus, Info, CheckSquare, Bot, BarChart3, ChevronRight, GitBranch, MessageSquare } from 'lucide-vue-next'
import Modal from '../shared/Modal.vue'
import EmptyState from '../shared/EmptyState.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'
import Toggle from '../shared/Toggle.vue'

const API = '/api'
const showToast = window.showToast
const workspaces = ref([])
const loading = ref(false)
const activeSection = ref('list')
const selectedWorkspace = ref(null)
const tasks = ref([])
const wsAgents = ref([])
const availableAgents = ref([])
const selectedAgentIds = ref([])
const allAgents = ref([])
const allAgentsLoading = ref(false)
const showDetailAgentModal = ref(false)
const detailAgents = ref([])
const enabledAgentsForDetail = ref([])
const wsStats = ref({})
const execCommand = ref('')
const execResult = ref('')
const executing = ref(false)
const chatInput = ref('')
const chatMessages = ref([])
const chatLoading = ref(false)
const showTaskModal = ref(false)
const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)

// 关闭任务弹窗时重置表单
watch(showTaskModal, (val) => {
  if (!val) {
    taskForm.value = { agent: '', description: '' }
  }
})

const form = ref({ name: '', description: '' })
const detailForm = ref({ name: '', description: '' })
const taskForm = ref({ agent: '', description: '' })
const expandedWorkspaces = reactive({})
const wsSubagentExpanded = ref(false)

const mainBtnClass = (key) => {
  const base = 'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all text-left'
  return activeSection.value === key
    ? base + ' bg-primary/15 text-primary font-medium'
    : base + ' text-text-secondary hover:text-text-primary hover:bg-bg-hover'
}

const wsHeaderClass = (ws) => {
  const key = ws.id || ws.name
  return expandedWorkspaces[key]
    ? 'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all text-left bg-bg-hover text-text-primary font-medium'
    : 'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all text-left text-text-secondary hover:text-text-primary hover:bg-bg-hover'
}

const subBtnClass = (section, ws) => {
  const base = 'w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-all text-left'
  const isActive = activeSection.value === section && (selectedWorkspace.value?.id || selectedWorkspace.value?.name) === (ws.id || ws.name)
  return isActive
    ? base + ' bg-primary/15 text-primary font-medium'
    : base + ' text-text-secondary hover:text-text-primary hover:bg-bg-hover'
}

// 切换视图时自动加载对应数据
watch(activeSection, (section) => {
  if (section === 'subagent') {
    loadAllAgents()
    return
  }
  if (!selectedWorkspace.value) return
  if (section === 'tasks') loadTasks()
  else if (section === 'agents') loadAgents()
  else if (section === 'stats') loadStats()
  else if (section === 'detail') loadDetailAgents()
  else if (section === 'chat') loadChatMessages()
})

onMounted(() => {
  loadWorkspaces()
  loadAvailableAgents()
})

const loadAllAgents = async () => {
  allAgentsLoading.value = true
  try {
    const res = await fetch(API + '/agents').then(r => r.json())
    allAgents.value = Array.isArray(res) ? res : (res.agents || [])
  } catch (e) {
    console.error('[Workspace] 加载全部 Agent 失败:', e)
  } finally {
    allAgentsLoading.value = false
  }
}

const toggleAgentWorkspace = async (agent) => {
  const newVal = agent.enabled_for_workspace === false
  const oldVal = agent.enabled_for_workspace
  agent.enabled_for_workspace = newVal  // 乐观更新
  try {
    await fetch(API + '/agents/' + agent.agent_id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled_for_workspace: newVal })
    })
    showToast?.('Agent ' + agent.name + ' 已' + (newVal ? '启用' : '禁用'), 'success')
  } catch (e) {
    agent.enabled_for_workspace = oldVal  // 失败回滚
    showToast?.('更新失败: ' + e.message, 'error')
  }
}

const loadAvailableAgents = async () => {
  try {
    const res = await fetch(API + '/agents/names?enabled_only=true').then(r => r.json())
    availableAgents.value = Array.isArray(res) ? res : (res.agents || [])
  } catch (e) {
    console.error('[Workspace] 加载 Agent 列表失败:', e)
  }
}

const toggleAgent = (agent) => {
  const idx = selectedAgentIds.value.indexOf(agent.agent_id)
  if (idx > -1) {
    selectedAgentIds.value.splice(idx, 1)
  } else {
    selectedAgentIds.value.push(agent.agent_id)
  }
}

const loadWorkspaces = async () => {
  loading.value = true
  try {
    const res = await fetch(API + '/workspaces').then(r => r.json())
    const raw = Array.isArray(res) ? res : (res.workspaces || [])
    // 归一化 ID 字段：兼容 workspace_id / _id / uuid → id
    workspaces.value = raw.map(w => ({
      ...w,
      id: w.workspace_id || w.id || w._id || w.uuid || ''
    }))
  } catch (e) { console.error('[Workspace] 加载失败:', e) }
  finally { loading.value = false }
}

const toggleWorkspace = (ws) => {
  const key = ws.id || ws.name
  if (expandedWorkspaces[key]) {
    expandedWorkspaces[key] = false
  } else {
    // 折叠其他，展开当前
    Object.keys(expandedWorkspaces).forEach(k => expandedWorkspaces[k] = false)
    expandedWorkspaces[key] = true
    selectWorkspace(ws)
    activeSection.value = 'detail'
  }
}

const selectAndView = async (ws, section) => {
  await selectWorkspace(ws)
  activeSection.value = section
  if (section === 'tasks') loadTasks()
  else if (section === 'agents') loadAgents()
  else if (section === 'stats') loadStats()
}

const selectWorkspace = async (ws) => {
  selectedWorkspace.value = ws
  detailForm.value = { name: ws.name, description: ws.description || '' }
}

const openCreate = () => {
  form.value = { name: '', description: '' }
  selectedAgentIds.value = []
  loadAvailableAgents()  // 刷新已启用的 Agent 列表
  activeSection.value = 'create'
}

const createWorkspace = async () => {
  try {
    const body = {
      ...form.value,
      agent_ref_ids: selectedAgentIds.value,
    }
    const res = await fetch(API + '/workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const data = await res.json()
    showToast?.('工作空间已创建', 'success')
    // 兼容不同 ID 字段名（workspace_id / _id / id / uuid）
    const createdId = data.workspace?.workspace_id || data.workspace_id || data.id || data._id || data.uuid || ''
    await loadWorkspaces()
    // 优先用创建返回的 ID 匹配，再用名称
    let found
    if (createdId) {
      found = workspaces.value.find(w => (w.id || w._id || w.uuid) === createdId)
    }
    if (!found) {
      found = workspaces.value.find(w => w.name === form.value.name)
    }
    if (!found && createdId) {
      workspaces.value.push({ id: createdId, name: form.value.name, description: form.value.description })
      found = workspaces.value[workspaces.value.length - 1]
    }
    if (found) toggleWorkspace(found)
  } catch (e) { showToast?.('创建失败: ' + e.message, 'error') }
}

const updateWorkspace = async () => {
  if (!selectedWorkspace.value) return
  try {
    const id = selectedWorkspace.value.id || selectedWorkspace.value.name
    await fetch(API + `/workspaces/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(detailForm.value)
    })
    showToast?.('已更新', 'success')
    await loadWorkspaces()
    if (selectedWorkspace.value) {
      selectedWorkspace.value.name = detailForm.value.name
    }
  } catch (e) { showToast?.('更新失败: ' + e.message, 'error') }
}

const deleteWorkspace = (ws) => {
  deleteTarget.value = ws
  showDeleteConfirm.value = true
}

const confirmDeleteWs = async () => {
  const ws = deleteTarget.value
  if (!ws) return
  try {
    const id = ws.id || ws.name
    const res = await fetch(API + `/workspaces/${id}`, { method: 'DELETE' })

    if (!res.ok) {
      showToast?.('删除失败: 后端返回 ' + res.status, 'error')
      return
    }

    // 重新拉取列表，检查空间是否真的没了
    await loadWorkspaces()
    const stillExists = workspaces.value.some(w => (w.id || w.name) === id)

    if (stillExists) {
      showToast?.('删除失败: 后端返回成功但空间仍存在', 'error')
      return
    }

    showToast?.('已删除', 'success')
    delete expandedWorkspaces[id]
    selectedWorkspace.value = null
    activeSection.value = 'list'
    showDeleteConfirm.value = false
    deleteTarget.value = null
  } catch (e) { showToast?.('删除失败: ' + e.message, 'error') }
}

const loadTasks = async () => {
  if (!selectedWorkspace.value) return
  try {
    const id = selectedWorkspace.value.id || selectedWorkspace.value.name
    const res = await fetch(API + `/workspaces/${id}/tasks`).then(r => r.json())
    tasks.value = Array.isArray(res) ? res : (res.tasks || [])
  } catch (e) {}
}

const loadAgents = async () => {
  if (!selectedWorkspace.value) return
  try {
    const id = selectedWorkspace.value.id || selectedWorkspace.value.name
    const res = await fetch(API + `/workspaces/${id}/agents`).then(r => r.json())
    wsAgents.value = Array.isArray(res) ? res : (res.agents || [])
  } catch (e) {}
}

const loadStats = async () => {
  if (!selectedWorkspace.value) return
  try {
    const id = selectedWorkspace.value.id || selectedWorkspace.value.name
    const res = await fetch(API + `/workspaces/${id}/stats`).then(r => r.json())
    wsStats.value = res.stats || res || {}
  } catch (e) {}
}

const loadDetailAgents = async () => {
  if (!selectedWorkspace.value) return
  detailAgents.value = selectedWorkspace.value.agents || []
  try {
    const res = await fetch(API + "/agents/names?enabled_only=true").then(r => r.json())
    const allEnabled = Array.isArray(res) ? res : (res.agents || [])
    const existingNames = detailAgents.value.map(a => a.name)
    enabledAgentsForDetail.value = allEnabled.filter(a => !existingNames.includes(a.name))
  } catch (e) {}
}

const addAgentToDetail = async (agent) => {
  if (!selectedWorkspace.value) return
  const wid = selectedWorkspace.value.id || selectedWorkspace.value.name
  try {
    await fetch(API + "/workspaces/" + wid + "/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_name: agent.name, agent_ref_id: agent.agent_id })
    })
    showToast?.("Agent " + agent.name + " 已添加", "success")
    showDetailAgentModal.value = false
    const res = await fetch(API + "/workspaces/" + wid).then(r => r.json())
    const ws = res.workspace || res
    selectedWorkspace.value.agents = ws.agents || []
    detailAgents.value = ws.agents || []
    const existingNames = detailAgents.value.map(a => a.name)
    enabledAgentsForDetail.value = enabledAgentsForDetail.value.filter(a => !existingNames.includes(a.name))
  } catch (e) { showToast?.("添加失败: " + e.message, "error") }
}

const removeAgentFromDetail = async (agent) => {
  if (!selectedWorkspace.value) return
  const wid = selectedWorkspace.value.id || selectedWorkspace.value.name
  try {
    const updatedAgents = (selectedWorkspace.value.agents || []).filter(a => a.name !== agent.name)
    await fetch(API + "/workspaces/" + wid, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agents: updatedAgents })
    })
    selectedWorkspace.value.agents = updatedAgents
    detailAgents.value = updatedAgents
    showToast?.("Agent " + agent.name + " 已移除", "success")
  } catch (e) { showToast?.("移除失败: " + e.message, "error") }
}

const enterWorkspaceChat = (ws) => {
  selectWorkspace(ws)
  activeSection.value = 'chat'
  chatMessages.value = []
  chatInput.value = ''
}

const loadChatMessages = async () => {
  if (!selectedWorkspace.value) return
  chatMessages.value = []
  const wid = selectedWorkspace.value.id || selectedWorkspace.value.name
  try {
    const res = await fetch(API + '/workspaces/' + wid + '/logs?limit=50').then(r => r.json())
    const logs = res.logs || []
    // 按时间排序
    logs.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
    for (const msg of logs) {
      chatMessages.value.push({
        role: msg.role || 'assistant',
        content: msg.content || '',
        agent: msg.agent || 'AI',
        timestamp: msg.timestamp,
      })
    }
  } catch (e) {
    console.error('[Workspace] 加载对话历史失败:', e)
  }
}

const sendChatMessage = async () => {
  if (!selectedWorkspace.value || !chatInput.value.trim() || chatLoading.value) return
  const msg = chatInput.value
  chatInput.value = ''
  chatMessages.value.push({ role: 'user', content: msg })
  chatLoading.value = true
  try {
    const wid = selectedWorkspace.value.id || selectedWorkspace.value.name
    const res = await fetch(API + '/workspaces/' + wid + '/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    })
    const data = await res.json()
    chatMessages.value.push({ role: 'assistant', content: data.reply || '无响应', agent: data.target || 'AI' })
  } catch (e) {
    chatMessages.value.push({ role: 'assistant', content: '请求失败: ' + e.message, agent: '系统' })
  } finally {
    chatLoading.value = false
  }
}

const executeCommand = async () => {
  if (!selectedWorkspace.value || !execCommand.value.trim() || executing.value) return
  executing.value = true
  execResult.value = ''
  try {
    const wid = selectedWorkspace.value.id || selectedWorkspace.value.name
    const res = await fetch(API + '/workspaces/' + wid + '/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: execCommand.value })
    })
    const data = await res.json()
    execResult.value = data.reply || JSON.stringify(data, null, 2)
    // 刷新 Agent 状态
    loadAgents()
  } catch (e) {
    execResult.value = '执行失败: ' + e.message
  } finally {
    executing.value = false
  }
}

const addTask = async () => {
  if (!selectedWorkspace.value || !taskForm.value.description) return
  try {
    const id = selectedWorkspace.value.id || selectedWorkspace.value.name
    await fetch(API + `/workspaces/${id}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskForm.value)
    })
    showTaskModal.value = false
    taskForm.value = { agent: '', description: '' }
    showToast?.('任务已添加', 'success')
    await loadTasks()
  } catch (e) { showToast?.('添加失败: ' + e.message, 'error') }
}

const updateTaskStatus = async (t, status) => {
  if (!selectedWorkspace.value) return
  const oldStatus = t.status
  t.status = status  // 乐观更新
  try {
    const wid = selectedWorkspace.value.id || selectedWorkspace.value.name
    const tid = t.id || t.task_id
    await fetch(API + `/workspaces/${wid}/tasks/${tid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    })
  } catch (e) {
    t.status = oldStatus  // 失败回滚
    showToast?.('更新失败: ' + e.message, 'error')
  }
}

const statusClass = (status) => {
  const map = { active: 'bg-success/10 text-success', working: 'bg-info/10 text-info', done: 'bg-success/10 text-success', failed: 'bg-error/10 text-error', idle: 'bg-text-disabled/10 text-text-disabled' }
  return map[status] || 'bg-text-disabled/10 text-text-disabled'
}
</script>

<style scoped>
/* 子菜单折叠动画 */
.submenu-enter-active, .submenu-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.submenu-enter-from,
.submenu-leave-to {
  opacity: 0;
  max-height: 0;
}
.submenu-enter-to,
.submenu-leave-from {
  opacity: 1;
  max-height: 200px;
}
</style>
