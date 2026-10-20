<template>
  <Modal :show="show" :title="title" @update:show="$emit('update:show', $event)">
    <p class="text-text-secondary mb-4">{{ message }}</p>
    <template #footer>
      <button class="btn-secondary" @click="cancel">取消</button>
      <button class="btn-danger" @click="confirm">确认</button>
    </template>
  </Modal>
</template>

<script setup>
import Modal from './Modal.vue'

defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗？' }
})

const emit = defineEmits(['update:show', 'confirm', 'cancel'])

const confirm = () => { emit('confirm'); emit('update:show', false) }
const cancel = () => { emit('cancel'); emit('update:show', false) }
</script>
