<template>
  <aside 
    class="w-[var(--sidebar-width)] h-[calc(100vh-var(--topbar-height))] bg-bg-card border-r border-border flex flex-col pt-4 transition-colors duration-300"
  >
    <!-- 导航标签 -->
    <nav class="flex-1 px-3 overflow-y-auto">
      <template v-for="item in navItems" :key="item.key">
        <!-- 普通菜单项 -->
        <button
          v-if="!item.children"
          :data-testid="`nav-${item.key}`"
          @click="select(item.key)"
          :class="[
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-0.5 transition-all duration-200',
            isActive(item.key)
              ? 'bg-primary/15 text-primary font-medium border-l-3 border-primary'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
          ]"
        >
          <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
          <span>{{ item.label }}</span>
          <span v-if="isActive(item.key)" class="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
        </button>
        
        <!-- 有子菜单的项（如配置） -->
        <div v-else>
          <button
            :data-testid="`nav-group-${item.key}`"
            @click="toggleExpand(item.key)"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-0.5 transition-all duration-200',
              isActive(item.key)
                ? 'bg-primary/15 text-primary font-medium border-l-3 border-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
            ]"
          >
            <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
            <span class="flex-1 text-left">{{ item.label }}</span>
            <svg 
              class="w-4 h-4 transition-transform duration-200"
              :class="{ 'rotate-90': expanded[item.key] }"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
          </button>
          
          <!-- 子菜单 -->
          <Transition name="submenu">
            <div v-if="expanded[item.key]" class="ml-2 mb-0.5 border-l-2 border-border/50 pl-2 space-y-0.5">
              <button
                v-for="child in item.children"
                :key="child.key"
                :data-testid="`nav-${child.key}`"
                @click="select(child.key)"
                :class="[
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200',
                  activeItem === child.key
                    ? 'bg-primary/15 text-primary font-medium'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                ]"
              >
                <component :is="child.icon" class="w-4 h-4 flex-shrink-0" />
                <span>{{ child.label }}</span>
                <span v-if="activeItem === child.key" class="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
              </button>
            </div>
          </Transition>
        </div>
      </template>
    </nav>
    
    <!-- 底部状态 -->
    <div class="px-4 py-3 border-t border-border">
      <div class="flex items-center gap-2 text-xs text-text-secondary" data-testid="api-status">
        <span class="w-2 h-2 rounded-full bg-success animate-pulse" />
        <span>API 已连接</span>
      </div>
      <div class="mt-1 text-[10px] text-text-disabled">v1.0.0</div>
    </div>
  </aside>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { 
  Home, User, Settings, Puzzle, Plug, MessageSquare, 
  GitBranch, BarChart3, FileText, Cpu, Database, Terminal,
  SlidersHorizontal, Monitor, Wrench, BookOpen
} from 'lucide-vue-next'

const props = defineProps({
  activeItem: { type: String, default: 'home' }
})

const emit = defineEmits(['update:activeItem'])

// 子菜单展开状态
const expanded = reactive({
  config: false
})

// 判断某个项是否激活（父级在子项激活时也显示激活态）
const isActive = (key) => {
  if (props.activeItem === key) return true
  // 如果子项处于激活态，父级也显示激活
  if (key === 'config' && props.activeItem.startsWith('config-')) return true
  return false
}

const navItems = [
  { key: 'home', label: '首页', icon: Home },
  { key: 'persona', label: '人格', icon: User },
  { 
    key: 'config', 
    label: '配置', 
    icon: Settings,
    children: [
      { key: 'config-general', label: '普通配置', icon: SlidersHorizontal },
      { key: 'config-system', label: '系统配置', icon: Monitor },
      { key: 'config-model', label: '模型配置', icon: Cpu },
      { key: 'config-memory', label: '记忆配置', icon: Database },
      { key: 'config-tools', label: '工具配置', icon: Wrench },
    ]
  },
  { key: 'skills', label: 'Skills', icon: Puzzle },
  { key: 'mcp', label: 'MCP', icon: Plug },
  { key: 'conversations', label: '对话数据', icon: MessageSquare },
  { key: 'subagent', label: '子 Agent 配置', icon: GitBranch },
  { key: 'knowledge', label: '知识库', icon: BookOpen },
  { key: 'statistics', label: '数据统计', icon: BarChart3 },
  { key: 'logs', label: '平台日志', icon: FileText },
]

const toggleExpand = (key) => {
  expanded[key] = !expanded[key]
}

const select = (key) => {
  emit('update:activeItem', key)
}
</script>

<style scoped>
.border-l-3 {
  border-left-width: 3px;
}

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
