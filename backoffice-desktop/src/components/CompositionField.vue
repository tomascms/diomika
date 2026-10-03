<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: [Object, String], default: () => ({}) },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const rows = ref([{ material: '', percent: '' }])
let syncing = false

const parseValue = (val) => {
  if (!val) return [{ material: '', percent: '' }]
  let parsed = val
  if (typeof val === 'string') {
    try {
      parsed = JSON.parse(val)
    } catch {
      return [{ material: '', percent: '' }]
    }
  }
  if (typeof parsed === 'object' && !Array.isArray(parsed)) {
    const entries = Object.entries(parsed)
    return entries.length
      ? entries.map(([material, percent]) => ({
          material: String(material),
          percent: String(percent ?? ''),
        }))
      : [{ material: '', percent: '' }]
  }
  return [{ material: '', percent: '' }]
}

watch(
  () => props.modelValue,
  (v) => {
    if (syncing) return
    rows.value = parseValue(v)
  },
  { immediate: true },
)

const buildPayload = () => {
  const out = {}
  for (const r of rows.value) {
    const m = String(r.material ?? '').trim()
    const pRaw = String(r.percent ?? '').trim()
    if (!m || !pRaw) continue
    const p = parseInt(pRaw, 10)
    if (!Number.isFinite(p) || p < 0) continue
    out[m] = p
  }
  return out
}

/** Total visual: soma % das linhas (mesmo sem material ainda). */
const totalUi = computed(() =>
  rows.value.reduce((sum, r) => sum + (parseInt(String(r.percent ?? ''), 10) || 0), 0),
)

const totalSaved = computed(() =>
  Object.values(buildPayload()).reduce((sum, p) => sum + p, 0),
)

const sync = () => {
  syncing = true
  emit('update:modelValue', buildPayload())
  queueMicrotask(() => {
    syncing = false
  })
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
        placeholder="Material (ex: algodão)"
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
    <p class="sum" :class="{ ok: totalSaved === 100, warn: totalSaved !== 100 }">
      Total a gravar: {{ totalSaved }}%
      <span v-if="totalUi !== totalSaved"> (a escrever: {{ totalUi }}%)</span>
      — deve ser 100%
    </p>
  </div>
</template>

<style scoped>
.composition {
  display: grid;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.12);
  border-radius: var(--radius-md);
  transition: all var(--transition);
}

.composition:has(.input:focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.08);
}

.row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
  animation: slideIn 0.2s ease-out;
}

.row:hover {
  border-color: var(--accent-light);
  background: var(--bg-hover);
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.08);
}

.row .input {
  padding: 8px 10px;
  border: none;
  background: transparent;
  font-size: 13px;
}

.row .input:focus {
  outline: none;
  background: var(--surface);
}

.pct {
  width: 72px;
  flex-shrink: 0;
  text-align: center;
}

.pct::after {
  content: '%';
  margin-left: -4px;
  font-weight: 600;
  color: var(--text-muted);
}

.btn-sm {
  padding: 6px 10px;
  font-size: 12px;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.btn-sm:hover {
  transform: scale(1.05);
}

.sum {
  margin: 8px 0 0;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  transition: all var(--transition);
  letter-spacing: 0.3px;
}

.sum.ok {
  color: var(--success);
  background: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.sum.warn {
  color: var(--danger);
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.2);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.2);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1);
  }
}
</style>
