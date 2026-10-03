<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/lib/api'
import DataList from '@/components/DataList.vue'
import OrderCreateView from '@/views/OrderCreateView.vue'
import OrderRecordPanel from '@/components/OrderRecordPanel.vue'

const rows = ref([])
const selected = ref(null)
const loading = ref(true)
const error = ref('')
const message = ref('')
const showCreate = ref(true)

const columns = [
  { key: 'referencia_cliente', label: 'Cliente' },
  { key: 'created_at', label: 'Data', format: (r) => (r.created_at || '').slice(0, 10) },
]

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.listRecords('encomendas_internas', { visible_only: 'false' })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const openRow = (row) => {
  selected.value = row
  showCreate.value = false
}

const toggleVisibility = async (row) => {
  const next = row.visibilidade === false
  try {
    await api.setVisibility('encomendas_internas', row.id, next)
    row.visibilidade = next
  } catch (e) {
    error.value = e.message
  }
}

const deleteRow = async (row) => {
  if (
    !confirm(
      'Apagar esta encomenda da base de dados?\n\nEsta acção não pode ser desfeita.\nPara ocultar sem apagar, use Visível/Oculto.',
    )
  ) {
    return
  }
  try {
    await api.deleteRecord('encomendas_internas', row.id, true)
    rows.value = rows.value.filter((r) => r.id !== row.id)
    if (selected.value?.id === row.id) selected.value = null
    message.value = 'Encomenda eliminada.'
  } catch (e) {
    error.value = e.message
  }
}

const onOrderSaved = async () => {
  message.value = 'Encomenda criada.'
  showCreate.value = false
  await load()
}

const showNewForm = () => {
  selected.value = null
  showCreate.value = true
}

onMounted(load)
</script>

<template>
  <div class="encomendas">
    <div class="list-pane card">
      <div class="list-head">
        <h2>Encomendas</h2>
        <button class="btn btn-primary btn-sm" @click="showNewForm">+ Nova</button>
      </div>
      <p v-if="message" class="ok">{{ message }}</p>
      <p v-if="error" class="err">{{ error }}</p>
      <DataList
        :rows="rows"
        :columns="columns"
        :loading="loading"
        @open="openRow"
        @toggle-visibility="toggleVisibility"
        @delete="deleteRow"
      />
    </div>

    <div class="detail-pane">
      <OrderRecordPanel
        v-if="selected && !showCreate"
        kind="encomenda"
        :record="selected"
        show-back
        @close="selected = null"
        @back="showNewForm"
      />
      <OrderCreateView v-else @saved="onOrderSaved" />
    </div>
  </div>
</template>

<style scoped>
.encomendas {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(360px, 1.4fr);
  gap: 20px;
  align-items: start;
  animation: slideUp 0.5s ease-out;
}

.list-pane {
  padding: 18px;
  animation: slideDown 0.4s ease-out;
}

.list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.08);
}

.list-head h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--text-primary);
}

.btn-sm {
  padding: 8px 14px;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.ok {
  margin: 0 0 12px 0;
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
  margin: 0 0 12px 0;
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

@media (max-width: 960px) {
  .encomendas {
    grid-template-columns: 1fr;
  }
}
</style>
