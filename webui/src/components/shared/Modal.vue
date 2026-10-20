<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" data-testid="modal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <!-- 背景遮罩 -->
        <div 
          class="absolute inset-0 bg-black/50 backdrop-blur-sm"
          @click="close"
        />
        
        <!-- 模态框内容 -->
        <div 
          :class="[
            'relative bg-bg-card border border-border rounded-xl shadow-2xl max-h-[85vh] flex flex-col',
            sizeClasses
          ]"
        >
          <!-- 头部 -->
          <div v-if="title" class="flex items-center justify-between p-4 border-b border-border">
            <h3 class="text-lg font-semibold text-text-primary">{{ title }}</h3>
            <button 
              @click="close"
              class="p-1 rounded hover:bg-bg-hover text-text-secondary transition-colors"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          
          <!-- 内容区域 -->
          <div class="p-4 overflow-y-auto flex-1">
            <slot />
          </div>
          
          <!-- 底部操作区 -->
          <div v-if="$slots.footer" class="p-4 border-t border-border flex justify-end gap-2">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: { type: String, default: 'md' } // sm, md, lg, xl
})
const emit = defineEmits(['update:show', 'close'])

const close = () => emit('update:show', false) || emit('close')

const sizeClasses = computed(() => ({
  sm: 'w-full max-w-md',
  md: 'w-full max-w-lg',
  lg: 'w-full max-w-3xl',
  xl: 'w-full max-w-5xl',
})[props.size] || 'w-full max-w-lg')
</script>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.modal-enter-from > div:last-child {
  transform: scale(0.95);
  opacity: 0;
}
.modal-leave-to > div:last-child {
  transform: scale(0.95);
  opacity: 0;
}
</style>
