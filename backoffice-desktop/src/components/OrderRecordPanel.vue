<script setup>
import { ref } from 'vue'
import { api } from '@/lib/api'

const props = defineProps({
  kind: { type: String, required: true }, // 'orcamento' | 'encomenda'
  record: { type: Object, required: true },
  showBack: { type: Boolean, default: false },
})

defineEmits(['close', 'back'])

const error = ref('')
const loadingPdf = ref(false)

const title = () => {
  if (props.kind === 'orcamento') return `Orçamento — ${props.record.nome || '—'}`
  return `Encomenda — ${props.record.referencia_cliente || '—'}`
}

const meta = () => {
  if (props.kind === 'orcamento') {
    const parts = [
      props.record.email && `Email: ${props.record.email}`,
      props.record.contacto && `Contacto: ${props.record.contacto}`,
      props.record.empresa && `Empresa: ${props.record.empresa}`,
    ].filter(Boolean)
    return parts.join('\n') || 'Pedido do site.'
  }
  return `Criada: ${(props.record.created_at || '').slice(0, 10)}`
}

const lines = () => props.record.linhas || []

const downloadPdf = async () => {
  loadingPdf.value = true
  error.value = ''
  try {
    const blob =
      props.kind === 'orcamento'
        ? await api.orcamentoPdf(props.record.id)
        : await api.orderPdf(props.record.id)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  } catch (e) {
    error.value = e.message
  } finally {
    loadingPdf.value = false
  }
}
</script>

<template>
  <div class="detail card">
    <div class="head">
      <div>
        <button v-if="showBack" class="btn btn-ghost btn-sm" @click="$emit('back')">← Nova encomenda</button>
        <h3>{{ title() }}</h3>
      </div>
      <button class="btn btn-ghost btn-sm" @click="$emit('close')">×</button>
    </div>

    <p class="meta">{{ meta() }}</p>
    <p v-if="record.observacoes" class="obs"><strong>Obs:</strong> {{ record.observacoes }}</p>

    <h4>Linhas ({{ lines().length }})</h4>
    <ul v-if="lines().length" class="lines">
      <li v-for="(ln, i) in lines()" :key="i">
        {{ i + 1 }}. EAN {{ ln.ean }} · cor {{ ln.numero_cor }}
        <span v-if="ln.altura"> · {{ ln.altura }}</span>
        · qtd {{ ln.quantidade }}
      </li>
    </ul>
    <p v-else class="empty">Sem linhas registadas.</p>

    <p v-if="error" class="err">{{ error }}</p>
    <button class="btn btn-primary" :disabled="loadingPdf" @click="downloadPdf">
      {{ loadingPdf ? 'A gerar…' : 'Descarregar PDF' }}
    </button>
  </div>
</template>

<style scoped>
.detail {
  padding: 20px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 16px;
  animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.head h3 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.meta {
  white-space: pre-line;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0;
  padding: 12px;
  background: rgba(59, 130, 246, 0.04);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.obs {
  margin: 0;
  font-size: 0.9rem;
  padding: 12px;
  background: rgba(120, 120, 120, 0.04);
  border: 1px solid rgba(120, 120, 120, 0.15);
  border-left: 3px solid var(--text-muted);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.detail h4 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--accent);
}

.lines {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.01) 0%, transparent 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.lines li {
  padding: 12px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.08);
  font-size: 0.92rem;
  color: var(--text-secondary);
  transition: all var(--transition);
  position: relative;
}

.lines li:last-child {
  border-bottom: none;
}

.lines li:hover {
  background: rgba(59, 130, 246, 0.06);
  color: var(--text-primary);
}

.empty {
  margin: 0;
  padding: 12px;
  color: var(--text-muted);
  font-size: 0.9rem;
  text-align: center;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.04) 0%, transparent 100%);
  border: 1px dashed rgba(59, 130, 246, 0.15);
  border-radius: var(--radius-sm);
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
</style>
