<template>
  <span :class="[
    'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
    variant === 'primary' && 'bg-primary/20 text-primary',
    variant === 'success' && 'bg-success/20 text-success',
    variant === 'warning' && 'bg-warning/20 text-warning',
    variant === 'error' && 'bg-error/20 text-error',
    variant === 'info' && 'bg-info/20 text-info',
    variant === 'default' && 'bg-bg-hover text-text-secondary',
  ]">
    <slot />
  </span>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'default' }
})
</script>
