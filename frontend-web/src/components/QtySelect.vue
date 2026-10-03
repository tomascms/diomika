<script setup>
import { computed } from 'vue'
import { buildQtyOptions } from '@/composables/useCart'

const props = defineProps({
  modelValue: { type: Number, required: true },
  step: { type: Number, default: 6 },
  min: { type: Number, default: 6 },
  max: { type: Number, default: 6000 },
  unitLabel: { type: String, default: 'un.' },
})

const emit = defineEmits(['update:modelValue'])

const options = computed(() => buildQtyOptions(props.step, props.min, props.max))

const onChange = (event) => {
  emit('update:modelValue', Number(event.target.value))
}
</script>

<template>
  <select class="qty-select" :value="modelValue" @change="onChange">
    <option v-for="q in options" :key="q" :value="q">
      {{ q }} {{ unitLabel }}
    </option>
  </select>
</template>

<style scoped>
.qty-select {
  margin-top: 0.35rem;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 500;
  background: linear-gradient(135deg, var(--color-surface) 0%, rgba(59, 130, 246, 0.01) 100%);
  color: var(--color-ink-deep);
  cursor: pointer;
  transition: all var(--transition);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.qty-select:hover {
  border-color: rgba(59, 130, 246, 0.3);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.1);
  background: linear-gradient(135deg, var(--color-surface), rgba(59, 130, 246, 0.03));
}

.qty-select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12), inset 0 0 0 1px rgba(59, 130, 246, 0.1);
  background: linear-gradient(135deg, var(--color-surface), rgba(59, 130, 246, 0.04));
}
</style>
