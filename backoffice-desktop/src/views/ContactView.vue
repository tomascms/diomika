<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/lib/api'
import DataList from '@/components/DataList.vue'
import ConversationPanel from '@/components/ConversationPanel.vue'

const rows = ref([])
const selected = ref(null)
const loading = ref(true)
const error = ref('')
const message = ref('')

const columns = [{ key: 'email', label: 'Email' }]

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.listContact()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const openMsg = async (row) => {
  selected.value = { ...row }
  message.value = ''
  if (!row.lida) {
    try {
      await api.markContactRead(row.id, true)
      row.lida = true
      selected.value = { ...row, lida: true }
    } catch (e) {
      error.value = e.message
    }
  }
}

const toggleRead = async (row) => {
  const next = !row.lida
  try {
    await api.markContactRead(row.id, next)
    row.lida = next
  } catch (e) {
    error.value = e.message
  }
}

const deleteMsg = async (row) => {
  if (
    !confirm(
      'Apagar esta mensagem da base de dados?\n\nEsta acção não pode ser desfeita.',
    )
  ) {
    return
  }
  try {
    await api.deleteRecord('contact_messages', row.id, true)
    rows.value = rows.value.filter((r) => r.id !== row.id)
    if (selected.value?.id === row.id) selected.value = null
    message.value = 'Mensagem eliminada.'
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div class="contact-layout">
    <div class="list-pane">
      <h2>Mensagens de contacto</h2>
      <p class="hint">Acompanhamento de conversas por email — responde no teu cliente de email.</p>
      <p v-if="message" class="ok">{{ message }}</p>
      <p v-if="error" class="err">{{ error }}</p>
      <DataList
        variant="conversation"
        :rows="rows"
        :columns="columns"
        :loading="loading"
        @open="openMsg"
        @toggle-read="toggleRead"
        @delete="deleteMsg"
      />
    </div>
    <ConversationPanel :message="selected" />
  </div>
</template>

<style scoped>
.contact-layout {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(360px, 1.4fr);
  gap: 20px;
  align-items: start;
  animation: slideUp 0.5s ease-out;
}

.list-pane {
  animation: slideDown 0.4s ease-out;
}

.list-pane h2 {
  margin: 0 0 8px;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--text-primary);
}

.hint {
  margin: 0 0 16px;
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 500;
  line-height: 1.5;
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
  .contact-layout {
    grid-template-columns: 1fr;
  }
}
</style>
