<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiPost } from '@/lib/api'
import { useTurnstile } from '@/composables/useTurnstile'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import { COMPANY, whatsappUrl } from '@/lib/constants'

const turnstile = useTurnstile()
const {
  enabled: turnstileEnabled,
  el: turnstileEl,
  loadError: turnstileLoadError,
  token: turnstileToken,
  reset: resetTurnstile,
  requireToken,
} = turnstile

const contactForm = ref({
  nome: '',
  email: '',
  contacto: '',
  assunto: '',
  mensagem: '',
  website: '',
})

const isSending = ref(false)
const messageSent = ref(false)
const errorMessage = ref('')

const breadcrumbItems = [
  { label: 'Início', to: { name: 'home' } },
  { label: 'Contacto' },
]

const IDEMPOTENCY_STORAGE_KEY = 'diomika-contact-idempotency'

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

const submitContact = async () => {
  if (contactForm.value.website) return
  if (!requireToken()) {
    errorMessage.value = 'Confirme a verificação anti-spam antes de enviar.'
    return
  }

  isSending.value = true
  messageSent.value = false
  errorMessage.value = ''

  try {
    const idempotencyKey = getOrCreateIdempotencyKey()
    await apiPost('/contacto', {
      ...contactForm.value,
      cf_turnstile_response: turnstileToken.value || null,
    }, { idempotencyKey })
    messageSent.value = true
    clearIdempotencyKey()
    contactForm.value = { nome: '', email: '', contacto: '', assunto: '', mensagem: '', website: '' }
    resetTurnstile()
  } catch (e) {
    errorMessage.value = e.message || 'Erro ao enviar mensagem.'
    resetTurnstile()
  } finally {
    isSending.value = false
  }
}
</script>

<template>
  <div class="contact-page">
    <Breadcrumbs :items="breadcrumbItems" />

    <div class="page-shell contact-wrap">
      <h1 class="page-title">Contacto</h1>
      <div class="direct-actions">
        <a class="btn btn-secondary" :href="`tel:${COMPANY.phoneTel}`">Ligar {{ COMPANY.phoneDisplay }}</a>
        <a class="btn btn-primary" :href="whatsappUrl('Olá! Gostaria de falar com a Diomika.')" target="_blank" rel="noopener noreferrer">WhatsApp</a>
      </div>

      <p class="privacy-note">
        Usamos estes dados só para responder ao pedido.
        <RouterLink to="/privacidade">Privacidade</RouterLink>.
      </p>

      <form class="contact-form" @submit.prevent="submitContact">
        <input
          v-model="contactForm.website"
          type="text"
          name="website"
          tabindex="-1"
          autocomplete="off"
          class="hp-field"
          aria-hidden="true"
        />

        <div>
          <label class="field-label" for="nome">Nome</label>
          <input id="nome" v-model="contactForm.nome" class="field-input" placeholder="O seu nome" required maxlength="120" />
        </div>
        <div>
          <label class="field-label" for="email">Email</label>
          <input id="email" v-model="contactForm.email" class="field-input" type="email" placeholder="email@empresa.pt" required />
        </div>
        <div>
          <label class="field-label" for="contacto">Telefone</label>
          <input id="contacto" v-model="contactForm.contacto" class="field-input" placeholder="912 345 678" required maxlength="20" />
        </div>
        <div>
          <label class="field-label" for="assunto">Assunto</label>
          <input id="assunto" v-model="contactForm.assunto" class="field-input" placeholder="Motivo do contacto" required maxlength="200" />
        </div>
        <div>
          <label class="field-label" for="mensagem">Mensagem</label>
          <textarea id="mensagem" v-model="contactForm.mensagem" class="field-textarea" placeholder="Como podemos ajudar?" required rows="6" maxlength="5000" />
        </div>

        <div v-if="turnstileEnabled" ref="turnstileEl" class="turnstile-wrap" />
        <p v-if="turnstileLoadError" class="alert alert-error">{{ turnstileLoadError }}</p>

        <button type="submit" class="btn btn-primary btn-block" :disabled="isSending">
          {{ isSending ? 'A enviar…' : 'Enviar mensagem' }}
        </button>

        <p v-if="messageSent" class="alert alert-success" role="status">
          Mensagem enviada. Entraremos em contacto em breve.
        </p>
        <p v-if="errorMessage" class="alert alert-error" role="alert">{{ errorMessage }}</p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.contact-page {
  padding-bottom: 3rem;
  background: #fff;
}

.contact-wrap {
  max-width: 640px;
  padding-top: 2.5rem;
  animation: slideUp 0.6s ease-out;
}

.page-title {
  margin: 0 0 1rem;
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--color-ink-deep);
}

.direct-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 1.5rem 0 1.75rem;
  animation: slideDown 0.4s ease-out 0.1s both;
}

.privacy-note {
  font-size: 0.93rem;
  color: var(--color-muted);
  font-weight: 500;
  line-height: 1.6;
  margin: 0 0 2rem;
}

.contact-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  position: relative;
  animation: slideUp 0.6s ease-out 0.15s both;
}

.contact-form > div {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.field-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--color-ink-deep);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.field-input,
.field-textarea {
  padding: 0.95rem 1.15rem;
  font-size: 1rem;
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 10px;
  background: linear-gradient(135deg, #fff 0%, rgba(59, 130, 246, 0.01) 100%);
  color: var(--color-ink-deep);
  font-family: inherit;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.04);
}

.field-input::placeholder,
.field-textarea::placeholder {
  color: var(--color-muted);
}

.field-input:hover,
.field-textarea:hover {
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
}

.field-input:focus,
.field-textarea:focus {
  outline: none;
  border-color: rgba(59, 130, 246, 0.4);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12), inset 0 0 0 1px rgba(59, 130, 246, 0.1);
  background: linear-gradient(135deg, #fff 0%, rgba(59, 130, 246, 0.03) 100%);
}

.field-textarea {
  resize: vertical;
  min-height: 140px;
  font-size: 0.95rem;
  line-height: 1.6;
}

.turnstile-wrap {
  min-height: 65px;
  display: flex;
  align-items: center;
}

.btn-block {
  width: 100%;
}

.hp-field {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(12px);
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
