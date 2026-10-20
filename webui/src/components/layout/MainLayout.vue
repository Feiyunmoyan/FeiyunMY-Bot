<template>
  <div class="min-h-screen bg-bg-base transition-colors duration-300">
    <TopBar :currentPage="currentPage" @navigate="$emit('navigate', $event)" />
    
    <main class="pt-[var(--topbar-height)]">
      <slot />
    </main>
    
    <Toast ref="toastRef" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TopBar from './TopBar.vue'
import Toast from '../shared/Toast.vue'

defineProps({
  currentPage: { type: String, default: 'dashboard' }
})

defineEmits(['navigate'])

const toastRef = ref(null)
defineExpose({ toastRef })
</script>
