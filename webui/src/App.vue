<template>
  <template v-if="showSplash">
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
onMounted(() => {
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
</style>
