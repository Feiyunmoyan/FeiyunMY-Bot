<template>
  <div 
    class="fixed inset-0 z-[100] flex flex-col items-center justify-center cursor-pointer select-none"
    :style="{
      background: 'radial-gradient(ellipse at center, #241518 0%, #1A1012 100%)'
    }"
    @click="skip"
  >
    <!-- Logo -->
    <div 
      class="animate-splash-logo"
      :style="{ animationDelay: '0ms' }"
    >
      <img 
        src="/assets/logo.png" 
        alt="FeiyunMY-Bot Logo"
        class="w-48 h-48 object-contain drop-shadow-[0_0_30px_rgba(139,26,43,0.4)]"
      />
    </div>
    
    <!-- 项目名称 -->
    <h1 
      class="mt-6 text-4xl font-bold tracking-wide animate-splash-title"
      style="color: #EDE0D4;"
    >
      FeiyunMY-Bot
    </h1>
    
    <!-- 副标题 -->
    <p 
      class="mt-3 text-sm animate-splash-subtitle"
      style="color: #B8A0A0;"
    >
      轻量级 AI 聊天机器人管理平台
    </p>
    
    <!-- 加载指示器 -->
    <div class="mt-8 flex items-center gap-2 animate-splash-loader">
      <div class="w-2 h-2 rounded-full bg-primary animate-bounce" style="animation-delay: 0ms;"></div>
      <div class="w-2 h-2 rounded-full bg-primary animate-bounce" style="animation-delay: 150ms;"></div>
      <div class="w-2 h-2 rounded-full bg-primary animate-bounce" style="animation-delay: 300ms;"></div>
    </div>
    
    <!-- 跳过提示 -->
    <p class="absolute bottom-8 text-xs text-text-secondary opacity-60">
      点击任意位置跳过
    </p>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue'

const emit = defineEmits(['complete'])

let timer = null
let skipped = false

const skip = () => {
  if (skipped) return
  skipped = true
  clearTimeout(timer)
  emit('complete')
}

onMounted(() => {
  // 3.2秒后自动进入主界面
  timer = setTimeout(() => {
    if (!skipped) {
      skipped = true
      emit('complete')
    }
  }, 3200)
})

onBeforeUnmount(() => {
  clearTimeout(timer)
})
</script>

<style scoped>
@keyframes splashLogo {
  0% { opacity: 0; transform: translateY(20px) scale(0.95); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes splashTitle {
  0% { opacity: 0; transform: translateY(15px); }
  100% { opacity: 1; transform: translateY(0); }
}

@keyframes splashSubtitle {
  0% { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}

@keyframes splashLoader {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

.animate-splash-logo {
  animation: splashLogo 0.6s ease-out forwards;
}

.animate-splash-title {
  opacity: 0;
  animation: splashTitle 0.6s ease-out 0.4s forwards;
}

.animate-splash-subtitle {
  opacity: 0;
  animation: splashSubtitle 0.5s ease-out 0.8s forwards;
}

.animate-splash-loader {
  opacity: 0;
  animation: splashLoader 0.4s ease-out 1.2s forwards;
}
</style>
