<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '@/lib/api'
import DataList from '@/components/DataList.vue'
import OrderRecordPanel from '@/components/OrderRecordPanel.vue'

const rows = ref([])
const selected = ref(null)
const loading = ref(true)
const error = ref('')
const message = ref('')

const columns = [
  { key: 'nome', label: 'Cliente', format: (r) => r.nome || r.referencia_cliente || '—' },
  { key: 'email', label: 'Email' },
]

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.listRecords('pedidos_orcamento', { visible_only: 'false' })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const openRow = async (row) => {
  selected.value = row
  if (!row.lida) {
    try {
      await api.setLida('pedidos_orcamento', row.id, true)
      row.lida = true
    } catch (e) {
      error.value = e.message
    }
  }
}

const toggleRead = async (row) => {
  const next = !row.lida
  try {
    await api.setLida('pedidos_orcamento', row.id, next)
    row.lida = next
    if (selected.value?.id === row.id) selected.value = { ...row, lida: next }
  } catch (e) {
    error.value = e.message
  }
}

const deleteRow = async (row) => {
  if (
    !confirm(
      'Apagar este orçamento da base de dados?\n\nEsta acção não pode ser desfeita.',
    )
  ) {
    return
  }
  try {
    await api.deleteRecord('pedidos_orcamento', row.id, true)
    rows.value = rows.value.filter((r) => r.id !== row.id)
    if (selected.value?.id === row.id) selected.value = null
    message.value = 'Orçamento eliminado.'
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div class="split">
    <div class="list-pane">
      <h2>Orçamentos do site</h2>
      <p v-if="message" class="ok">{{ message }}</p>
      <p v-if="error" class="err">{{ error }}</p>
      <DataList
        variant="conversation"
        :rows="rows"
        :columns="columns"
        :loading="loading"
        @open="openRow"
        @toggle-read="toggleRead"
        @delete="deleteRow"
      />
    </div>
    <OrderRecordPanel
      v-if="selected"
      kind="orcamento"
      :record="selected"
      @close="selected = null"
    />
    <div v-else class="placeholder card">
      <h3>Seleciona um orçamento</h3>
      <p>Clica em <strong>Abrir</strong> na lista para ver detalhes e descarregar PDF.</p>
    </div>
  </div>
</template>

<style scoped>
.split {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(320px, 1.2fr);
  gap: 20px;
  align-items: start;
  animation: slideUp 0.5s ease-out;
}

.list-pane {
  animation: slideDown 0.4s ease-out;
}

.list-pane h2 {
  margin: 0 0 14px;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--text-primary);
}

.placeholder {
  padding: 28px;
  color: var(--text-muted);
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  animation: slideUp 0.4s ease-out 0.1s both;
}

.placeholder h3 {
  margin: 0 0 8px;
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.placeholder p {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.6;
}

.ok {
  margin: 0 0 12px;
  color: var(--success);
  font-size: 0.9rem;
  font-weight: 700;
  padding: 10px 12px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);
  border-radius: var(--radius-md);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-left: 4px solid var(--success);
  animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
}

.err {
  margin: 0 0 12px;
  color: var(--danger);
  font-size: 0.9rem;
  font-weight: 700;
  padding: 10px 12px;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
  border-radius: var(--radius-md);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 4px solid var(--danger);
  animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.12);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  .split {
    grid-template-columns: 1fr;
  }
}
</style>
