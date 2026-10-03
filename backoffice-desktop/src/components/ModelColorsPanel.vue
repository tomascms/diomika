<script setup>
import { ref, watch } from 'vue'
import { api } from '@/lib/api'
import ImageField from '@/components/ImageField.vue'

const props = defineProps({
  modelId: { type: String, default: null },
  colorsTable: { type: String, default: null },
  readOnly: { type: Boolean, default: false },
})

const rows = ref([])
const loading = ref(false)
const error = ref('')

const emptyRow = () => ({
  id: null,
  numero: '',
  nome: '',
  imagem: '',
  pendingFile: null,
})

async function mapPool(items, concurrency, fn) {
  if (!items.length) return []
  const results = new Array(items.length)
  let next = 0
  const workers = Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    while (next < items.length) {
      const idx = next++
      results[idx] = await fn(items[idx], idx)
    }
  })
  await Promise.all(workers)
  return results
}

const load = async () => {
  rows.value = []
  if (!props.modelId || !props.colorsTable) {
    if (!props.readOnly) rows.value = [emptyRow()]
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await api.listModelColors(props.colorsTable, props.modelId)
    rows.value = data.length
      ? data.map((c) => ({
          id: c.id,
          numero: String(c.numero ?? ''),
          nome: c.nome || '',
          imagem: c.imagem || '',
          pendingFile: null,
        }))
      : props.readOnly
        ? []
        : [emptyRow()]
  } catch (e) {
    error.value = e.message
    if (!props.readOnly) rows.value = [emptyRow()]
  } finally {
    loading.value = false
  }
}

watch(() => [props.modelId, props.colorsTable], load, { immediate: true })

const addRow = () => {
  rows.value.push(emptyRow())
}

const removeRow = async (idx) => {
  const row = rows.value[idx]
  if (row.id && !confirm('Eliminar esta cor?')) return
  if (row.id && props.colorsTable) {
    try {
      await api.deleteRecord(props.colorsTable, row.id, true)
    } catch (e) {
      error.value = e.message
      return
    }
  }
  rows.value.splice(idx, 1)
  if (!rows.value.length && !props.readOnly) rows.value.push(emptyRow())
}

const onImageFile = (row, file) => {
  row.pendingFile = file
}

const save = async (modelId, { publish = false } = {}) => {
  if (props.readOnly || !modelId || !props.colorsTable) return
  error.value = ''
  const keptIds = new Set()
  const toSave = rows.value.filter((row) => String(row.numero || '').trim())
  if (publish && !toSave.length) {
    throw new Error('Adicione pelo menos uma cor (número + imagem) antes de publicar na loja.')
  }

  await mapPool(toSave, 4, async (row) => {
    if (row.pendingFile) {
      const up = await api.uploadImage(props.colorsTable, 'imagem', row.pendingFile)
      row.imagem = up.url
      row.pendingFile = null
    }
  })

  for (const row of toSave) {
    const numero = String(row.numero || '').trim()
    if (!row.imagem) throw new Error(`Cor nº ${numero}: escolha uma imagem.`)
  }

  await mapPool(toSave, 4, async (row) => {
    const numero = String(row.numero || '').trim()
    const payload = {
      id_modelo: modelId,
      numero: parseInt(numero, 10),
      nome: (row.nome || '').trim(),
      imagem: row.imagem,
      visibilidade: publish,
    }
    if (row.id) {
      await api.updateRecord(props.colorsTable, row.id, { ...payload, id: row.id })
      keptIds.add(row.id)
    } else {
      const created = await api.createRecord(props.colorsTable, payload)
      row.id = created.id
      keptIds.add(created.id)
    }
  })

  if (props.modelId) {
    const existing = await api.listModelColors(props.colorsTable, modelId)
    const orphans = existing.filter((c) => !keptIds.has(c.id))
    await mapPool(orphans, 4, (c) => api.deleteRecord(props.colorsTable, c.id, true))
  }

  await load()
}

defineExpose({ save })
</script>

<template>
  <section class="colors-panel">
    <h3>Cores do modelo</h3>
    <p class="hint">
      Obrigatório para aparecer na loja: pelo menos uma cor com número e imagem.
      Os produtos (EAN/dimensões) só entram no site depois disto e de «Publicar na loja».
    </p>
    <p v-if="loading" class="muted">A carregar cores…</p>
    <p v-if="error" class="err">{{ error }}</p>

    <article v-for="(row, idx) in rows" :key="row.id || `new-${idx}`" class="color-row card">
      <div class="fields">
        <input v-model="row.numero" class="input num" type="number" min="1" placeholder="Nº" :disabled="readOnly" />
        <input v-model="row.nome" class="input" placeholder="Nome cor" :disabled="readOnly" />
        <ImageField
          v-if="!readOnly"
          v-model="row.imagem"
          @file-selected="onImageFile(row, $event)"
        />
        <img v-else-if="row.imagem" :src="row.imagem" alt="" class="thumb" />
      </div>
      <button v-if="!readOnly" type="button" class="btn btn-danger btn-sm" @click="removeRow(idx)">X</button>
    </article>

    <button v-if="!readOnly" type="button" class="btn btn-ghost" @click="addRow">+ Adicionar cor</button>
  </section>
</template>

<style scoped>
.colors-panel {
  margin-top: 32px;
  padding-top: 24px;
  padding-bottom: 20px;
  border-top: 2px solid var(--border);
  display: grid;
  gap: 16px;
  position: relative;
}

.colors-panel::before {
  content: 'Cores';
  position: absolute;
  top: -12px;
  left: 0;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--accent);
  padding: 0 6px;
  background: var(--surface);
}

.colors-panel > h3 {
  display: none;
}

.hint,
.muted {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.err {
  color: var(--danger);
  margin: 0;
  padding: 10px 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
}

.color-row {
  padding: 16px;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all var(--transition);
  animation: fadeIn 0.2s ease-out;
  position: relative;
  overflow: hidden;
}

.color-row::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent) 0%, transparent 100%);
  opacity: 0;
  transition: opacity var(--transition);
}

.color-row:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.color-row:hover::before {
  opacity: 1;
}

.fields {
  flex: 1;
  display: grid;
  gap: 12px;
}

.fields .input {
  padding: 10px 12px;
  font-size: 13px;
}

.num {
  max-width: 80px;
}

.thumb {
  max-width: 140px;
  height: auto;
  aspect-ratio: auto;
  border-radius: var(--radius-md);
  border: 2px solid var(--border);
  transition: all var(--transition);
  background: var(--bg-secondary);
  box-shadow: var(--shadow-sm);
}

.thumb:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: scale(1.02);
}

.btn-sm {
  padding: 8px 12px;
  font-size: 12px;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.btn-sm:hover {
  transform: translateY(-1px);
}

.colors-panel > .btn-ghost {
  align-self: flex-start;
  margin-top: 4px;
  padding: 10px 16px;
  font-weight: 600;
  transition: all var(--transition-fast);
}

.colors-panel > .btn-ghost:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
  background: var(--accent-soft);
  color: var(--accent);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
