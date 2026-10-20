<template>
  <Teleport to="body">
    <div data-testid="toast-container" class="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :data-testid="`toast-${toast.type}`"
          :class="[
            'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border min-w-[280px] max-w-sm',
            toast.type === 'success' && 'bg-success/10 border-success text-success',
            toast.type === 'error' && 'bg-error/10 border-error text-error',
            toast.type === 'warning' && 'bg-warning/10 border-warning text-warning',
            toast.type === 'info' && 'bg-info/10 border-info text-info',
          ]"
        >
          <span class="flex-1 text-sm">{{ toast.message }}</span>
          <button @click="remove(toast.id)" class="opacity-60 hover:opacity-100">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const toasts = ref([])
let nextId = 1

function add(message, type = 'info', duration = 3000) {
  const id = nextId++
  toasts.value.push({ id, message, type })
  
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
  
  return id
}

function remove(id) {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index !== -1) {
    toasts.value.splice(index, 1)
  }
}

// 暴露方法供外部调用
defineExpose({ add, remove })

// 提供全局 toast 方法
window.showToast = add
</script>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease;
}
.toast-leave-active {
  transition: all 0.2s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
