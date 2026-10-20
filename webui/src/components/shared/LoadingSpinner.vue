<template>
  <div :class="['flex items-center justify-center', size === 'sm' && 'p-2', size === 'lg' && 'p-8']">
    <div :class="[
      'animate-spin rounded-full border-2 border-t-transparent',
      size === 'sm' && 'w-4 h-4 border-text-secondary',
      size === 'md' && 'w-6 h-6 border-text-secondary',
      size === 'lg' && 'w-8 h-8 border-primary',
    ]" />
  </div>
</template>

<script setup>
defineProps({
  size: { type: String, default: 'md', validator: v => ['sm', 'md', 'lg'].includes(v) }
})
</script>
