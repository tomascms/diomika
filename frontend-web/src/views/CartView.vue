<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useCart, resolveCartQtyRules, isValidCartQty } from '@/composables/useCart'
import { useTurnstile } from '@/composables/useTurnstile'
import { apiPost } from '@/lib/api'
import { MIN_ORCAMENTO_MSG, QUOTE_FORM_DRAFT_KEY, whatsappUrl } from '@/lib/constants'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import QtySelect from '@/components/QtySelect.vue'
import SoftImage from '@/components/SoftImage.vue'

const cart = useCart()
const turnstile = useTurnstile()
const { enabled: turnstileEnabled, el: turnstileEl, loadError: turnstileLoadError, token: turnstileToken, reset: resetTurnstile, requireToken } = turnstile
const items = ref([])
const submittedLines = ref([])
const submitting = ref(false)
const success = ref('')
const error = ref('')
const form = ref({ nome: '', email: '', contacto: '', observacoes: '', website: '' })
const breadcrumbItems = [{ label: 'Início', to: { name: 'home' } }, { label: 'Pedido de orçamento' }]
const reload = () => { items.value = cart.getItems() }
const printQuote = () => window.print()

onMounted(() => {
  reload()
  try {
    const draft = JSON.parse(localStorage.getItem(QUOTE_FORM_DRAFT_KEY) || '{}')
    for (const field of ['nome', 'email', 'contacto', 'observacoes']) if (typeof draft[field] === 'string') form.value[field] = draft[field]
  } catch { /* rascunho inválido */ }
})
watch(form, (value) => {
  if (success.value) return
  try {
    const { nome, email, contacto, observacoes } = value
    localStorage.setItem(QUOTE_FORM_DRAFT_KEY, JSON.stringify({ nome, email, contacto, observacoes }))
  } catch { /* storage indisponível */ }
}, { deep: true })

const totalUnits = computed(() => items.value.reduce((n, i) => n + i.quantidade, 0))
const remove = (item) => { cart.removeItem(item.ean, item.numero_cor, item.altura || ''); reload() }
const changeQty = (item, qty) => { cart.updateQty(item.ean, item.numero_cor, Number(qty), item.altura || ''); reload() }
const cartRules = (item) => resolveCartQtyRules(item)
const IDEMPOTENCY_STORAGE_KEY = 'diomika-orcamento-idempotency'
const getOrCreateIdempotencyKey = () => { let key = sessionStorage.getItem(IDEMPOTENCY_STORAGE_KEY); if (!key) { key = crypto.randomUUID(); sessionStorage.setItem(IDEMPOTENCY_STORAGE_KEY, key) } return key }
const clearIdempotencyKey = () => sessionStorage.removeItem(IDEMPOTENCY_STORAGE_KEY)

const submit = async () => {
  error.value = ''; success.value = ''
  if (form.value.website) return
  if (!items.value.length) { error.value = 'O pedido está vazio.'; return }
  for (const item of items.value) {
    const { step, min } = cartRules(item)
    if (!isValidCartQty(item.quantidade, item)) { error.value = `Quantidade inválida para EAN ${item.ean}: mínimo ${min}, múltiplos de ${step}.`; return }
  }
  if (!requireToken()) { error.value = 'Confirme a verificação anti-spam antes de enviar.'; return }
  submitting.value = true
  try {
    const idempotencyKey = getOrCreateIdempotencyKey()
    const contacto = form.value.contacto.trim()
    const observacoes = form.value.observacoes.trim()
    await apiPost('/orcamentos', {
      nome: form.value.nome.trim(), email: form.value.email.trim(), contacto: contacto || null, observacoes: observacoes || null,
      website: form.value.website, cf_turnstile_response: turnstileToken.value || null,
      linhas: items.value.map((i) => ({ ean: i.ean, numero_cor: Number(i.numero_cor), quantidade: Number(i.quantidade), ...(i.altura ? { altura: i.altura } : {}) })),
    }, { idempotencyKey })
    submittedLines.value = items.value.map((item) => ({ ...item }))
    success.value = 'Pedido enviado com sucesso.'
    clearIdempotencyKey(); localStorage.removeItem(QUOTE_FORM_DRAFT_KEY); cart.clear(); reload()
    form.value = { nome: '', email: '', contacto: '', observacoes: '', website: '' }
  } catch (e) { error.value = e.message || 'Erro ao enviar pedido.'; resetTurnstile() }
  finally { submitting.value = false }
}
</script>

<template>
  <div class="cart-page">
    <Breadcrumbs :items="breadcrumbItems" />
    <div class="page-shell">
      <header class="page-header"><h1 class="page-title">Pedido de orçamento</h1><p class="alert alert-info">{{ MIN_ORCAMENTO_MSG }}</p></header>
      <div v-if="items.length === 0 && !success" class="empty surface-card empty-card"><p>O seu pedido está vazio.</p><RouterLink to="/categorias" class="btn btn-primary">Explorar catálogo</RouterLink></div>
      <div v-else-if="!success" class="cart-layout">
        <section class="lines surface-card surface-card--elevated print-area">
          <div class="lines-head"><h2>Artigos</h2><span class="badge-pill badge-soft">{{ totalUnits }} un.</span><button type="button" class="btn btn-secondary print-btn" @click="printQuote">Imprimir / PDF</button></div>
          <article v-for="item in items" :key="`${item.ean}-${item.numero_cor}-${item.altura || ''}`" class="line">
            <div v-if="item.imagem" class="line-thumb"><SoftImage :src="item.imagem" :alt="item.modeloNome" /></div>
            <div class="line-info"><strong>{{ item.modeloNome }}</strong><span class="line-meta">{{ item.dimensoes }}{{ item.altura ? '' : ' cm' }} · Cor {{ item.numero_cor }}{{ item.corNome ? ` (${item.corNome})` : '' }}</span><span class="line-ean">EAN {{ item.ean }}</span></div>
            <div class="line-actions"><label class="qty-field"><span class="field-label">Quantidade</span><QtySelect :model-value="item.quantidade" :step="cartRules(item).step" :min="cartRules(item).min" unit-label="un." @update:model-value="changeQty(item, $event)" /></label><button type="button" class="btn btn-secondary remove-btn" @click="remove(item)">Remover</button></div>
          </article>
        </section>
        <section class="form-section surface-card surface-card--elevated"><h2>Os seus dados</h2><p class="form-hint">Nome e email são obrigatórios. O rascunho fica guardado neste dispositivo.</p>
          <form class="quote-form" @submit.prevent="submit">
            <input v-model="form.website" type="text" name="website" tabindex="-1" autocomplete="off" class="hp-field" aria-hidden="true" />
            <div><label class="field-label" for="nome">Nome *</label><input id="nome" v-model="form.nome" class="field-input" required autocomplete="name" /></div>
            <div><label class="field-label" for="email">Email *</label><input id="email" v-model="form.email" class="field-input" type="email" required autocomplete="email" /></div>
            <div><label class="field-label" for="contacto">Contacto</label><input id="contacto" v-model="form.contacto" class="field-input" autocomplete="tel" placeholder="Telefone (opcional)" /></div>
            <div><label class="field-label" for="observacoes">Observações</label><textarea id="observacoes" v-model="form.observacoes" class="field-textarea" placeholder="Prazos, entrega, notas sobre o projecto…" /></div>
            <div v-if="turnstileEnabled" ref="turnstileEl" class="turnstile-wrap" /><p v-if="turnstileLoadError" class="alert alert-error">{{ turnstileLoadError }}</p><p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>
            <button type="submit" class="btn btn-primary btn-block" :disabled="submitting">{{ submitting ? 'A enviar…' : 'Enviar pedido de orçamento' }}</button>
          </form>
        </section>
      </div>
      <section v-if="success" class="success-card surface-card" role="status"><h2>{{ success }}</h2><p>A nossa equipa responderá no prazo de 1 dia útil.</p><div class="submitted-summary"><h3>Resumo enviado</h3><p v-for="item in submittedLines" :key="`${item.ean}-${item.numero_cor}-${item.altura || ''}`"><strong>{{ item.modeloNome }}</strong> — {{ item.quantidade }} un. · Cor {{ item.numero_cor }} · EAN {{ item.ean }}</p></div><div class="success-actions"><a class="btn btn-primary" :href="whatsappUrl('Olá! Acabei de enviar um pedido de orçamento no site Diomika.')" target="_blank" rel="noopener noreferrer">Falar no WhatsApp</a><RouterLink to="/categorias" class="btn btn-secondary">Voltar ao catálogo</RouterLink></div></section>
    </div>
  </div>
</template>

<style scoped>
.cart-page {
  padding-bottom: 2rem;
  background: #fff;
}

.page-header {
  margin-bottom: 1.75rem;
  animation: slideDown 0.3s ease-out;
}

.page-header .alert {
  margin-top: 1rem;
  margin-bottom: 0;
}

.cart-layout {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 1.5rem;
  align-items: start;
}

.lines,
.form-section {
  padding: 1.5rem 1.65rem;
  background: linear-gradient(135deg, #f8fafc 0%, #f0f4f8 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.05);
  animation: slideUp 0.4s ease-out;
}

.lines-head {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid rgba(59, 130, 246, 0.15);
}

.lines-head h2,
.form-section h2 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 800;
  color: var(--color-ink-deep);
  letter-spacing: -0.01em;
}

.print-btn {
  margin-left: auto;
  font-size: 0.85rem;
}

.line {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.25rem 0;
  border-bottom: 1px solid rgba(59, 130, 246, 0.08);
  transition: background-color 0.2s ease-out;
  animation: slideUp 0.3s ease-out;
}

.line:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.03) 0%, transparent 100%);
  padding: 1.25rem 0.75rem;
  margin: 0 -0.75rem;
  border-radius: 8px;
}

.line:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.line-thumb {
  width: 80px;
  height: 80px;
  flex: 0 0 80px;
  overflow: hidden;
  border-radius: 8px;
  background: linear-gradient(135deg, #f4f7fb 0%, #eef2f6 100%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.line-thumb :deep(.soft-image__img) {
  object-fit: cover;
  width: 100%;
  height: 100%;
}

.line-info {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}

.line-info strong {
  color: var(--color-ink-deep);
  font-weight: 700;
  font-size: 0.98rem;
}

.line-meta,
.line-ean {
  color: var(--color-muted);
  font-size: 0.88rem;
  line-height: 1.4;
}

.line-ean {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  letter-spacing: 0.05em;
  font-weight: 500;
}

.line-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.75rem;
  flex-shrink: 0;
}

.qty-field {
  min-width: 9rem;
}

.remove-btn {
  font-size: 0.8rem;
  padding: 0.5rem 0.95rem;
  color: var(--danger, #ef4444);
  border-color: rgba(239, 68, 68, 0.3);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  transition: all 0.2s ease-out;
}

.remove-btn:hover {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.02) 100%);
  border-color: rgba(239, 68, 68, 0.5);
}

.quote-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  position: relative;
}

.form-hint {
  font-size: 0.9rem;
  color: var(--color-muted);
  line-height: 1.5;
}

.turnstile-wrap {
  min-height: 65px;
}

.hp-field {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.empty-card {
  padding: 3rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
  background: linear-gradient(135deg, #f8fafc 0%, #f0f4f8 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 12px;
  animation: slideUp 0.4s ease-out;
}

.empty-card p {
  margin: 0;
  color: var(--color-muted);
  font-size: 1.05rem;
}

.success-card {
  padding: 3rem;
  text-align: center;
  max-width: 760px;
  margin: 0 auto;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.02) 100%);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 12px;
  animation: slideUp 0.4s ease-out;
  box-shadow: 0 8px 24px rgba(16, 185, 129, 0.15);
}

.success-card h2 {
  margin: 0 0 0.5rem;
  color: var(--color-success);
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.success-card > p {
  margin: 0 0 1.5rem;
  color: var(--color-muted);
  font-size: 1rem;
  line-height: 1.6;
}

.submitted-summary {
  margin: 2rem auto;
  padding: 1.5rem;
  max-width: 620px;
  text-align: left;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
  border-left: 3px solid #3b82f6;
  border-radius: 8px;
}

.submitted-summary h3 {
  margin: 0 0 1rem;
  font-size: 0.95rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-ink-deep);
}

.submitted-summary p {
  margin: 0.6rem 0;
  font-size: 0.9rem;
  color: var(--color-ink);
  line-height: 1.5;
}

.submitted-summary strong {
  font-weight: 700;
}

.success-actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 1rem;
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

@media (max-width: 768px) {
  .cart-layout {
    grid-template-columns: 1fr;
  }

  .line {
    flex-wrap: wrap;
  }

  .line-actions {
    width: 100%;
    flex-direction: row;
    justify-content: space-between;
    align-items: flex-end;
  }

  .success-card {
    padding: 2rem;
  }
}
</style>
<style>
@media print {
  nav, footer, .whatsapp-fab, .form-section, .print-btn { display: none !important; }
  body * { visibility: hidden !important; }
  .print-area, .print-area * { visibility: visible !important; }
  .print-area { position: absolute !important; inset: 0 auto auto 0; width: 100%; box-shadow: none !important; border: 0 !important; }
  .print-area .print-btn, .print-area .remove-btn, .print-area .qty-field { display: none !important; }
}
</style>
