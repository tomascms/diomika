<script setup>
import { ref, watch } from 'vue'
import { api } from '@/lib/api'

const props = defineProps({
  message: { type: Object, default: null },
})

const history = ref([])
const loadingHistory = ref(false)
const error = ref('')

const lastSenderLabel = (value) => {
  if (value === 'vendor') return 'Loja (tu)'
  if (value === 'client') return 'Cliente'
  return '—'
}

const formatDate = (value) => {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return String(value).slice(0, 16)
  }
}

const loadHistory = async () => {
  history.value = []
  error.value = ''
  if (!props.message?.id) return

  loadingHistory.value = true
  try {
    const data = await api.getContactMessage(props.message.id)
    history.value = data.history || []
  } catch (e) {
    error.value = e.message
  } finally {
    loadingHistory.value = false
  }
}

watch(() => props.message?.id, loadHistory, { immediate: true })
</script>

<template>
  <div v-if="!message" class="placeholder card">
    <h3>Seleciona uma mensagem</h3>
    <p>Clica em <strong>Abrir</strong> na lista para ver o histórico da conversa por email.</p>
  </div>

  <div v-else class="conversation card">
    <div class="meta">
      <div class="chips">
        <span class="chip">{{ message.status || 'Nova' }}</span>
        <span class="chip muted">Último: {{ lastSenderLabel(message.last_sender) }}</span>
      </div>
      <button type="button" class="btn btn-ghost btn-sm" :disabled="loadingHistory" @click="loadHistory">
        {{ loadingHistory ? 'A actualizar…' : '↻ Actualizar' }}
      </button>
    </div>

    <p class="who">{{ message.nome }} &lt;{{ message.email }}&gt;</p>
    <h3>{{ message.assunto || '(sem assunto)' }}</h3>

    <div class="thread">
      <article class="bubble client">
        <p class="head">Cliente · {{ formatDate(message.created_at) }}</p>
        <p v-if="message.contacto" class="sub">Tel: {{ message.contacto }}</p>
        <p class="body">{{ message.mensagem }}</p>
      </article>

      <p v-if="loadingHistory && !history.length" class="loading-hint">A carregar respostas…</p>

      <article
        v-for="reply in history"
        :key="reply.id"
        class="bubble"
        :class="reply.role === 'vendor' ? 'vendor' : 'client'"
      >
        <p class="head">
          {{ reply.role === 'vendor' ? 'Loja' : 'Cliente' }} · {{ formatDate(reply.created_at) }}
        </p>
        <p class="body">{{ reply.body || '(sem texto)' }}</p>
      </article>
    </div>

    <p v-if="error" class="err">Histórico indisponível: {{ error }}</p>
  </div>
</template>

<style scoped>
.placeholder {
  padding: 3rem 2rem;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.04) 0%, transparent 100%);
  border: 2px dashed rgba(59, 130, 246, 0.15);
  border-radius: var(--radius-md);
  animation: fadeIn 0.3s ease-out;
}

.placeholder h3 {
  margin: 0 0 12px;
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--text-primary);
}

.placeholder p {
  margin: 0;
  font-size: 0.9rem;
  text-align: center;
  max-width: 300px;
}

.conversation {
  padding: 20px;
  display: grid;
  gap: 16px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  transition: all var(--transition);
}

.chip.muted {
  background: rgba(120, 120, 120, 0.08);
  color: var(--text-muted);
  font-weight: 500;
  text-transform: none;
  letter-spacing: normal;
}

.who {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  font-weight: 500;
}

.conversation h3 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.thread {
  display: grid;
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 8px;
  scroll-behavior: smooth;
}

.bubble {
  border-radius: 12px;
  padding: 14px;
  animation: slideUp 0.3s ease-out;
  transition: all var(--transition);
  border: 1px solid transparent;
}

.bubble.vendor {
  margin-left: 48px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(59, 130, 246, 0.04) 100%);
  border-color: rgba(59, 130, 246, 0.15);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.08);
}

.bubble.vendor:hover {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.25);
}

.bubble.client {
  margin-right: 48px;
  background: linear-gradient(135deg, rgba(120, 120, 120, 0.08) 0%, rgba(120, 120, 120, 0.02) 100%);
  border-color: rgba(120, 120, 120, 0.15);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}

.bubble.client:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: rgba(120, 120, 120, 0.25);
}

.head {
  margin: 0 0 8px;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.sub {
  margin: 0 0 8px;
  font-size: 0.85rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.body {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}

.loading-hint {
  margin: 0;
  padding: 12px;
  color: var(--text-muted);
  font-size: 0.9rem;
  text-align: center;
  background: rgba(59, 130, 246, 0.04);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-sm);
  animation: fadeIn 0.3s ease-out;
}

.err {
  margin: 0;
  padding: 12px;
  color: var(--danger);
  font-size: 0.9rem;
  font-weight: 700;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 4px solid var(--danger);
  border-radius: var(--radius-sm);
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.1);
}

.btn-sm {
  padding: 8px 14px;
  font-size: 0.8rem;
  font-weight: 600;
  border-radius: var(--radius-sm);
  transition: all var(--transition);
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

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
