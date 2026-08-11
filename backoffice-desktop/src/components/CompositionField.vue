<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: [Object, String], default: () => ({}) },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const rows = ref([{ material: '', percent: '' }])

const parseValue = (val) => {
  if (!val) return [{ material: '', percent: '' }]
  if (typeof val === 'string') {
    try {
      val = JSON.parse(val)
    } catch {
      return [{ material: '', percent: '' }]
    }
  }
  if (typeof val === 'object' && !Array.isArray(val)) {
    const entries = Object.entries(val)
    return entries.length ? entries.map(([material, percent]) => ({ material, percent: String(percent) })) : [{ material: '', percent: '' }]
  }
  return [{ material: '', percent: '' }]
}

watch(() => props.modelValue, (v) => { rows.value = parseValue(v) }, { immediate: true })

const total = computed(() =>
  rows.value.reduce((sum, r) => sum + (parseInt(r.percent, 10) || 0), 0),
)

const sync = () => {
  const out = {}
  for (const r of rows.value) {
    const m = r.material.trim()
    const p = r.percent.trim()
    if (m && p) out[m] = parseInt(p, 10)
  }
  emit('update:modelValue', out)
}

const addRow = () => {
  rows.value.push({ material: '', percent: '' })
}

const removeRow = (idx) => {
  rows.value.splice(idx, 1)
  if (!rows.value.length) rows.value.push({ material: '', percent: '' })
  sync()
}
</script>

<template>
  <div class="composition">
    <div v-for="(row, idx) in rows" :key="idx" class="row">
      <input
        v-model="row.material"
        class="input"
        placeholder="Material"
        :disabled="disabled"
        @input="sync"
      />
      <input
        v-model="row.percent"
        class="input pct"
        type="number"
        min="0"
        max="100"
        placeholder="%"
        :disabled="disabled"
        @input="sync"
      />
      <button v-if="!disabled" type="button" class="btn btn-danger btn-sm" @click="removeRow(idx)">X</button>
    </div>
    <button v-if="!disabled" type="button" class="btn btn-ghost btn-sm" @click="addRow">+ Adicionar material</button>
    <p class="sum" :class="{ ok: total === 100, warn: total !== 100 }">Total: {{ total }}% (deve ser 100%)</p>
  </div>
</template>

<style scoped>
.composition { display: grid; gap: 8px; padding: 12px; background: var(--bg-hover); border-radius: var(--radius); }
.row { display: flex; gap: 8px; align-items: center; }
.pct { width: 72px; flex-shrink: 0; }
.btn-sm { padding: 6px 10px; font-size: 0.8rem; }
.sum { margin: 4px 0 0; font-size: 0.8rem; }
.sum.ok { color: var(--success); }
.sum.warn { color: var(--danger); }
</style>
