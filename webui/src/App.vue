<template>
  <!-- 鉴权检查中：先不渲染业务组件，避免发出大量注定 401 的请求 -->
  <div v-if="authChecking" class="gate-blank"></div>

  <!-- 需要访问令牌（局域网 / 移动端访问时出现） -->
  <div v-else-if="needToken" class="gate-wrap">
    <form class="gate-card" @submit.prevent="submitToken">
      <div class="gate-mark"></div>
      <h1 class="gate-title">需要访问令牌</h1>
      <p class="gate-desc">当前不是本机访问，请输入访问令牌以继续。</p>
      <input
        v-model="tokenInput"
        class="gate-input"
        type="password"
        placeholder="访问令牌"
        autocomplete="current-password"
      />
      <p v-if="tokenError" class="gate-error">{{ tokenError }}</p>
      <button class="gate-btn" type="submit" :disabled="submitting">
        {{ submitting ? '验证中…' : '进入' }}
      </button>
      <p class="gate-hint">令牌保存在服务端 data/access_token.txt</p>
    </form>
  </div>

  <template v-else-if="showSplash">
    <SplashScreen @complete="onSplashComplete" />
  </template>
  <template v-else>
    <MainLayout :currentPage="currentPage" @navigate="navigateTo">
      <!-- 仪表盘页面 -->
      <div v-if="currentPage === 'dashboard'" class="flex h-[calc(100vh-var(--topbar-height))]">
        <Sidebar v-model:activeItem="activePanel" />
        <div class="flex-1 overflow-y-auto">
          <Transition name="fade" mode="out-in">
            <component :is="currentPanelComponent" :key="activePanel" :activePanel="activePanel" />
          </Transition>
        </div>
      </div>
      
      <!-- Chat 页面 -->
      <div v-else-if="currentPage === 'chat'" class="flex h-[calc(100vh-var(--topbar-height))]">
        <ChatPage />
      </div>
      
      <!-- 工作空间页面 -->
      <div v-else-if="currentPage === 'workspace'" class="flex h-[calc(100vh-var(--topbar-height))]">
        <WorkspacePanel />
      </div>
    </MainLayout>
  </template>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import SplashScreen from './components/splash/SplashScreen.vue'
import MainLayout from './components/layout/MainLayout.vue'
import Sidebar from './components/layout/Sidebar.vue'
import ChatPage from './components/chat/ChatPage.vue'
import WorkspacePanel from './components/dashboard/WorkspacePanel.vue'
import { useChat } from '@/composables/useChat'

// 仪表盘面板组件（懒加载）
import HomePanel from './components/dashboard/HomePanel.vue'
import PersonaPanel from './components/dashboard/PersonaPanel.vue'
import ConfigPanel from './components/dashboard/ConfigPanel.vue'
import SkillsPanel from './components/dashboard/SkillsPanel.vue'
import MCPPanel from './components/dashboard/MCPPanel.vue'
import ConversationDataPanel from './components/dashboard/ConversationDataPanel.vue'
import SubAgentPanel from './components/dashboard/SubAgentPanel.vue'
import KnowledgeBasePanel from './components/dashboard/KnowledgeBasePanel.vue'
import StatisticsPanel from './components/dashboard/StatisticsPanel.vue'
import LogPanel from './components/dashboard/LogPanel.vue'

const showSplash = ref(true)
const currentPage = ref('dashboard')
const activePanel = ref('home')

// ===== 访问令牌闸门 =====
const authChecking = ref(true)
const needToken = ref(false)
const tokenInput = ref('')
const tokenError = ref('')
const submitting = ref(false)

const checkAuth = async () => {
  try {
    const res = await fetch('/api/auth/status')
    if (!res.ok) {
      // 状态接口异常时不阻塞使用
      authChecking.value = false
      return
    }
    const status = await res.json()
    needToken.value = Boolean(status.auth_enabled && !status.authenticated)
  } catch (e) {
    console.warn('[auth] 状态检查失败，按已授权处理', e)
  } finally {
    authChecking.value = false
  }
}

const submitToken = async () => {
  const token = tokenInput.value.trim()
  if (!token) {
    tokenError.value = '请输入访问令牌'
    return
  }
  submitting.value = true
  tokenError.value = ''
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
    if (!res.ok) {
      tokenError.value = '访问令牌不正确'
      return
    }
    // 令牌已换取 HttpOnly Cookie，重载页面以重新拉取全部数据
    window.location.reload()
  } catch (e) {
    tokenError.value = '网络错误，请确认服务是否在运行'
  } finally {
    submitting.value = false
  }
}

const panelMap = {
  home: HomePanel,
  persona: PersonaPanel,
  config: ConfigPanel,
  'config-general': ConfigPanel,
  'config-system': ConfigPanel,
  'config-model': ConfigPanel,
  'config-memory': ConfigPanel,
  'config-shell': ConfigPanel,
  'config-tools': ConfigPanel,
  skills: SkillsPanel,
  mcp: MCPPanel,
  conversations: ConversationDataPanel,
  subagent: SubAgentPanel,
  knowledge: KnowledgeBasePanel,
  statistics: StatisticsPanel,
  logs: LogPanel,
}

const currentPanelComponent = computed(() => panelMap[activePanel.value] || HomePanel)

const onSplashComplete = () => {
  showSplash.value = false
}

const navigateTo = (page) => {
  currentPage.value = page
}

// 全局 SSE 连接（保持常驻，不随页面切换断开）
const chat = useChat()
onMounted(async () => {
  await checkAuth()
  if (needToken.value) return // 未授权时不要发起 SSE / 状态上报
  chat.connectSSE()
  // 每30秒上报用户状态
  setInterval(() => {
    try {
      fetch('/api/user/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyboard_freq: 0,
          cpu_usage: 0,
          gpu_usage: 0,
          screen_focused: !document.hidden,
        }),
      })
    } catch (e) {}
  }, 30000)

  // 监听首页"最近对话"点击事件，跳转到 Chat 页面
  window.addEventListener('navigate-to-chat', (e) => {
    currentPage.value = 'chat'
    const sessionId = e.detail?.sessionId
    if (sessionId) {
      // 切到 Chat 页面后自动选中该会话
      setTimeout(() => {
        chat.switchView('chat')
        chat.selectSession(sessionId)
      }, 100)
    }
  })
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* ===== 访问令牌闸门 ===== */
.gate-blank {
  height: 100vh;
  background: #0d0d0f;
}

.gate-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #0d0d0f;
  color: #e8e6e3;
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
}

.gate-card {
  width: 340px;
  padding: 40px 36px 32px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  background: #131316;
}

.gate-mark {
  width: 26px;
  height: 3px;
  margin-bottom: 28px;
  border-radius: 2px;
  background: #c2453c;
}

.gate-title {
  margin: 0 0 10px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.gate-desc {
  margin: 0 0 24px;
  font-size: 13px;
  line-height: 1.7;
  color: #8b8a88;
}

.gate-input {
  width: 100%;
  box-sizing: border-box;
  padding: 11px 13px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 9px;
  background: #0d0d0f;
  color: #e8e6e3;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s ease;
}

.gate-input:focus {
  border-color: #c2453c;
}

.gate-error {
  margin: 10px 0 0;
  font-size: 12px;
  color: #d9695f;
}

.gate-btn {
  width: 100%;
  margin-top: 18px;
  padding: 11px 0;
  border: none;
  border-radius: 9px;
  background: #c2453c;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.gate-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.gate-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.gate-hint {
  margin: 18px 0 0;
  font-size: 11px;
  text-align: center;
  color: #5f5e5c;
}
</style>
