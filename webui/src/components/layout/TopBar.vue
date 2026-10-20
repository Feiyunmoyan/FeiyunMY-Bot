<template>
  <!-- 顶栏 -->
  <header class="fixed top-0 left-0 right-0 z-40 h-[var(--topbar-height)] bg-bg-card border-b border-border flex items-center px-4 transition-colors duration-300">
    <!-- 左侧：品牌区 -->
    <div class="flex items-center gap-3 cursor-pointer" @click="$emit('navigate', 'dashboard')">
      <img src="/assets/logo.png" alt="Logo" class="w-8 h-8 object-contain" />
      <span class="font-semibold text-text-primary text-lg hidden sm:inline">FeiyunMY-Bot</span>
    </div>
    
    <!-- 右侧：页面切换 + 菜单 -->
    <div class="ml-auto flex items-center gap-2">
      <!-- 页面切换按钮 -->
      <nav class="flex items-center bg-bg-hover rounded-lg p-1">
        <button
          @click="$emit('navigate', 'dashboard')"
          :class="[
            'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200',
            currentPage === 'dashboard'
              ? 'bg-primary text-white shadow-sm'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover/50'
          ]"
        >
          <span class="flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/>
            </svg>
            仪表盘
          </span>
        </button>
        <button
          @click="$emit('navigate', 'chat')"
          :class="[
            'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200',
            currentPage === 'chat'
              ? 'bg-primary text-white shadow-sm'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover/50'
          ]"
        >
          <span class="flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
            </svg>
            Chat
          </span>
        </button>
        <button
          @click="$emit('navigate', 'workspace')"
          :class="[
            'px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200',
            currentPage === 'workspace'
              ? 'bg-primary text-white shadow-sm'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover/50'
          ]"
        >
          <span class="flex items-center gap-1.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21"/>
            </svg>
            工作空间
          </span>
        </button>
      </nav>
      
      <!-- ⋯ 更多菜单 -->
      <div class="relative" ref="menuRef">
        <button
          @click="menuOpen = !menuOpen"
          class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          aria-label="更多选项"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="5" r="2"/>
            <circle cx="12" cy="12" r="2"/>
            <circle cx="12" cy="19" r="2"/>
          </svg>
        </button>
        
        <!-- 下拉菜单 -->
        <Transition name="dropdown">
          <div v-if="menuOpen" class="absolute right-0 top-full mt-1 w-44 bg-bg-card border border-border rounded-lg shadow-xl overflow-hidden z-50">
            <div class="p-1">
              <button
                @click="setTheme('light'); menuOpen = false"
                class="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors hover:bg-bg-hover text-text-primary"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                </svg>
                浅色模式
                <span v-if="!isDark" class="ml-auto text-primary">✓</span>
              </button>
              <button
                @click="setTheme('dark'); menuOpen = false"
                class="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors hover:bg-bg-hover text-text-primary"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
                </svg>
                暗红色模式
                <span v-if="isDark" class="ml-auto text-primary">✓</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useTheme } from '@/composables/useTheme'

defineProps({
  currentPage: { type: String, default: 'dashboard' }
})

defineEmits(['navigate'])

const { isDark, setTheme } = useTheme()
const menuOpen = ref(false)
const menuRef = ref(null)

// 点击外部关闭菜单
const handleClickOutside = (e) => {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    menuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from, .dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
