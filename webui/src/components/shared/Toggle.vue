<template>
  <button
    data-testid="toggle"
    @click="toggle"
    :class="[
      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
      modelValue ? 'bg-primary' : 'bg-bg-hover border border-border'
    ]"
    role="switch"
    :aria-checked="modelValue"
  >
    <span
      :class="[
        'inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200',
        modelValue ? 'translate-x-6' : 'translate-x-1'
      ]"
    />
  </button>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

const toggle = () => emit('update:modelValue', !props.modelValue)
</script>
