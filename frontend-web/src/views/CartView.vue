<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCart, resolveCartQtyRules, isValidCartQty } from '@/composables/useCart'
import { useTurnstile } from '@/composables/useTurnstile'
import { apiPost } from '@/lib/api'
import { MIN_ORCAMENTO_MSG } from '@/lib/constants'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import QtySelect from '@/components/QtySelect.vue'

const router = useRouter()
const cart = useCart()
const turnstile = useTurnstile()
const { enabled: turnstileEnabled, el: turnstileEl, loadError: turnstileLoadError, token: turnstileToken, reset: resetTurnstile, requireToken } = turnstile
const items = ref([])
const submitting = ref(false)
const success = ref('')
const error = ref('')

const form = ref({
  nome: '',
  email: '',
  contacto: '',
  observacoes: '',
  website: '',
})

const breadcrumbItems = [
  { label: 'Início', to: { name: 'home' } },
  { label: 'Pedido de orçamento' },
]

const reload = () => {
  items.value = cart.getItems()
}

onMounted(reload)

const totalUnits = computed(() => items.value.reduce((n, i) => n + i.quantidade, 0))

const remove = (item) => {
  cart.removeItem(item.ean, item.numero_cor, item.altura || '')
  reload()
}

const changeQty = (item, qty) => {
  cart.updateQty(item.ean, item.numero_cor, Number(qty), item.altura || '')
  reload()
}

const cartRules = (item) => resolveCartQtyRules(item)

const IDEMPOTENCY_STORAGE_KEY = 'diomika-orcamento-idempotency'

const getOrCreateIdempotencyKey = () => {
  let key = sessionStorage.getItem(IDEMPOTENCY_STORAGE_KEY)
  if (!key) {
    key = crypto.randomUUID()
    sessionStorage.setItem(IDEMPOTENCY_STORAGE_KEY, key)
  }
  return key
}

const clearIdempotencyKey = () => {
  sessionStorage.removeItem(IDEMPOTENCY_STORAGE_KEY)
}

const submit = async () => {
  error.value = ''
  success.value = ''
  if (form.value.website) return
  if (items.value.length === 0) {
    error.value = 'O pedido está vazio.'
    return
  }
  for (const item of items.value) {
    const { step, min } = cartRules(item)
    if (!isValidCartQty(item.quantidade, item)) {
      error.value = `Quantidade inválida para EAN ${item.ean}: mínimo ${min}, múltiplos de ${step}.`
      return
    }
  }
  if (!requireToken()) {
    error.value = 'Confirme a verificação anti-spam antes de enviar.'
    return
  }
  submitting.value = true
  const idempotencyKey = getOrCreateIdempotencyKey()
  try {
    const contacto = form.value.contacto.trim()
    const observacoes = form.value.observacoes.trim()
    await apiPost(
      '/orcamentos',
      {
        nome: form.value.nome.trim(),
        email: form.value.email.trim(),
        contacto: contacto || null,
        observacoes: observacoes || null,
        website: form.value.website,
        cf_turnstile_response: turnstileToken.value || null,
        linhas: items.value.map((i) => ({
          ean: i.ean,
          numero_cor: Number(i.numero_cor),
          quantidade: Number(i.quantidade),
          ...(i.altura ? { altura: i.altura } : {}),
        })),
      },
      { idempotencyKey },
    )
    success.value = 'Pedido enviado com sucesso. Entraremos em contacto em breve.'
    clearIdempotencyKey()
    cart.clear()
    reload()
    setTimeout(() => router.push('/'), 3500)
  } catch (e) {
    error.value = e.message || 'Erro ao enviar pedido.'
    resetTurnstile()
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="cart-page">
    <Breadcrumbs :items="breadcrumbItems" />

    <div class="page-shell">
      <header class="page-header">
        <h1 class="page-title">Pedido de orçamento</h1>
        <p class="alert alert-info">{{ MIN_ORCAMENTO_MSG }}</p>
      </header>

      <div v-if="items.length === 0 && !success" class="empty surface-card empty-card">
        <p>O seu pedido está vazio.</p>
        <RouterLink to="/" class="btn btn-primary">Explorar catálogo</RouterLink>
      </div>

      <div v-else-if="!success" class="cart-layout">
        <section class="lines surface-card surface-card--elevated">
          <div class="lines-head">
            <h2>Artigos</h2>
            <span class="badge-pill badge-soft">{{ totalUnits }} un.</span>
          </div>

          <article
            v-for="item in items"
            :key="`${item.ean}-${item.numero_cor}-${item.altura || ''}`"
            class="line"
          >
            <div class="line-info">
              <strong>{{ item.modeloNome }}</strong>
              <span class="line-meta">
                {{ item.dimensoes }}{{ item.altura ? '' : ' cm' }}
                · Cor {{ item.numero_cor }}{{ item.corNome ? ` (${item.corNome})` : '' }}
              </span>
              <span class="line-ean">EAN {{ item.ean }}</span>
            </div>
            <div class="line-actions">
              <label class="qty-field">
                <span class="field-label">Quantidade</span>
                <QtySelect
                  :model-value="item.quantidade"
                  :step="cartRules(item).step"
                  :min="cartRules(item).min"
                  unit-label="un."
                  @update:model-value="changeQty(item, $event)"
                />
              </label>
              <button type="button" class="btn btn-secondary remove-btn" @click="remove(item)">
                Remover
              </button>
            </div>
          </article>
        </section>

        <section class="form-section surface-card surface-card--elevated">
          <h2>Os seus dados</h2>
          <p class="form-hint">Nome e email são obrigatórios.</p>
          <form class="quote-form" @submit.prevent="submit">
            <input
              v-model="form.website"
              type="text"
              name="website"
              tabindex="-1"
              autocomplete="off"
              class="hp-field"
              aria-hidden="true"
            />
            <div>
              <label class="field-label" for="nome">Nome *</label>
              <input id="nome" v-model="form.nome" class="field-input" required autocomplete="name" />
            </div>
            <div>
              <label class="field-label" for="email">Email *</label>
              <input id="email" v-model="form.email" class="field-input" type="email" required autocomplete="email" />
            </div>
            <div>
              <label class="field-label" for="contacto">Contacto</label>
              <input id="contacto" v-model="form.contacto" class="field-input" autocomplete="tel" placeholder="Telefone (opcional)" />
            </div>
            <div>
              <label class="field-label" for="observacoes">Observações</label>
              <textarea id="observacoes" v-model="form.observacoes" class="field-textarea" placeholder="Prazos, entrega, notas sobre o projecto…" />
            </div>
            <div v-if="turnstileEnabled" ref="turnstileEl" class="turnstile-wrap" />
            <p v-if="turnstileLoadError" class="alert alert-error">{{ turnstileLoadError }}</p>
            <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>
            <button type="submit" class="btn btn-primary btn-block" :disabled="submitting">
              {{ submitting ? 'A enviar…' : 'Enviar pedido de orçamento' }}
            </button>
          </form>
        </section>
      </div>

      <p v-if="success" class="alert alert-success success-card">{{ success }}</p>
    </div>
  </div>
</template>

<style scoped>
.cart-page {
  padding-bottom: 2rem;
  background: #fff;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header .alert {
  margin-top: 0.85rem;
  margin-bottom: 0;
}

.cart-layout {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 1.25rem;
  align-items: start;
}

.lines,
.form-section {
  padding: 1.25rem 1.35rem;
}

.lines-head {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 0.5rem;
}

.lines-head h2,
.form-section h2 {
  margin: 0;
  font-size: 1.35rem;
}

.line {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--color-border);
}

.line:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.line-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.line-info strong {
  font-size: 1.02rem;
  color: var(--color-ink);
}

.line-meta {
  color: var(--color-muted);
  font-size: 0.92rem;
}

.line-ean {
  font-size: 0.82rem;
  font-family: ui-monospace, monospace;
  color: var(--color-muted);
}

.line-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.5rem;
  flex-shrink: 0;
}

.qty-field {
  min-width: 8rem;
}

.remove-btn {
  font-size: 0.88rem;
  padding: 0.45rem 0.85rem;
  color: var(--color-danger);
  border-color: #fecaca;
}

.remove-btn:hover {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.quote-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: relative;
}

.form-hint {
  margin: -0.25rem 0 0.25rem;
  font-size: 0.88rem;
  color: var(--color-muted);
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

.empty-card,
.success-card {
  padding: 2.5rem;
  text-align: center;
}

.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.empty-card p {
  margin: 0;
  color: var(--color-muted);
}

@media (max-width: 768px) {
  .cart-layout {
    grid-template-columns: 1fr;
  }

  .line {
    flex-direction: column;
  }

  .line-actions {
    width: 100%;
    flex-direction: row;
    justify-content: space-between;
    align-items: flex-end;
  }
}
</style>
