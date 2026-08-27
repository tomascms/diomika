<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clearApiCaches } from '@/lib/api'
import {
  mapApiError,
  saveSettings,
  writeSessionUser,
  clearSession,
  isAuthenticated,
} from '@/lib/settings'

const router = useRouter()
const username = ref('')
const password = ref('')
const totpCode = ref('')
const mfaRequired = ref(false)
const mfaSetupMode = ref(false)
const mfaSecret = ref('')
const mfaUri = ref('')
const error = ref('')
const loading = ref(false)
const loginRequired = ref(true)
const checking = ref(true)

onMounted(async () => {
  try {
    const st = await api.authStatus()
    loginRequired.value = Boolean(st.login_required)
    if (!st.login_required && isAuthenticated()) {
      router.replace({ name: 'workspace', params: { table: 'categories' } })
    } else if (st.login_required && isAuthenticated()) {
      try {
        await api.me()
        router.replace({ name: 'workspace', params: { table: 'categories' } })
      } catch {
        clearApiCaches()
        clearSession()
      }
    }
  } catch (e) {
    loginRequired.value = true
    error.value = mapApiError(e.message || e)
  } finally {
    checking.value = false
  }
})

async function completeLogin(res) {
  if (!res?.access_token) {
    throw new Error(res?.detail || 'Resposta de login inválida')
  }
  saveSettings({ accessToken: res.access_token })
  writeSessionUser({ username: res.username, role: res.role })
  clearApiCaches()
  await router.replace({ name: 'workspace', params: { table: 'categories' } })
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const user = username.value.trim()
    const pass = password.value
    const code = totpCode.value.trim()

    if (mfaSetupMode.value) {
      if (!code) {
        error.value = 'Introduza o código de 6 dígitos da app autenticadora.'
        return
      }
      await api.mfaConfirm(user, pass, code)
      mfaSetupMode.value = false
      mfaSecret.value = ''
      mfaUri.value = ''
      const res = await api.login(user, pass, code)
      await completeLogin(res)
      return
    }

    const res = await api.login(user, pass, mfaRequired.value ? code : undefined)
    if (res?.mfa_required) {
      mfaRequired.value = true
      error.value = ''
      return
    }
    if (res?.mfa_setup_required) {
      const setup = await api.mfaSetup(user, pass)
      mfaSetupMode.value = true
      mfaRequired.value = false
      mfaSecret.value = setup.secret || ''
      mfaUri.value = setup.otpauth_uri || ''
      totpCode.value = ''
      error.value = ''
      return
    }
    await completeLogin(res)
  } catch (e) {
    error.value = mapApiError(e.message || e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel card">
      <p class="brand">Diomika</p>
      <h1>Backoffice</h1>
      <p class="lead">Sessão local do administrador. Expira automaticamente por segurança.</p>

      <p v-if="checking" class="muted">A verificar…</p>

      <form v-else class="form" @submit.prevent="submit">
        <label>
          Utilizador
          <input
            v-model="username"
            class="input"
            type="text"
            autocomplete="username"
            required
            autofocus
            :disabled="mfaSetupMode || mfaRequired"
          />
        </label>
        <label>
          Password
          <input
            v-model="password"
            class="input"
            type="password"
            autocomplete="current-password"
            required
            :disabled="mfaSetupMode || mfaRequired"
          />
        </label>

        <div v-if="mfaSetupMode" class="mfa-setup">
          <p class="mfa-title">Configure o MFA (obrigatório)</p>
          <p class="muted">
            Adicione esta conta na Google Authenticator / Authy (scan do URI ou secret manual) e
            confirme com o código de 6 dígitos.
          </p>
          <p v-if="mfaSecret" class="secret">
            Secret: <code>{{ mfaSecret }}</code>
          </p>
          <p v-if="mfaUri" class="uri"><code>{{ mfaUri }}</code></p>
        </div>

        <label v-if="mfaRequired || mfaSetupMode">
          Código MFA
          <input
            v-model="totpCode"
            class="input"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="6 dígitos"
            required
          />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="!loginRequired" class="muted">
          Login ainda não configurado no servidor (ADMIN_BOOTSTRAP_*). Em desenvolvimento pode usar API key.
        </p>
        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{
            loading
              ? 'A entrar…'
              : mfaSetupMode
                ? 'Confirmar MFA e entrar'
                : mfaRequired
                  ? 'Confirmar MFA'
                  : 'Entrar'
          }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem;
  background:
    radial-gradient(ellipse 70% 50% at 15% 0%, rgba(15, 110, 86, 0.12), transparent 55%),
    radial-gradient(ellipse 50% 40% at 90% 100%, rgba(24, 33, 43, 0.06), transparent 50%),
    var(--bg);
}

.login-panel {
  width: min(420px, 100%);
  padding: 2rem 1.75rem;
}

.brand {
  margin: 0;
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 560;
  letter-spacing: -0.02em;
  color: var(--accent-hover);
}

h1 {
  margin: 0.25rem 0 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-muted);
}

.lead {
  margin: 1rem 0 1.35rem;
  font-size: 0.92rem;
  line-height: 1.45;
  color: var(--text-muted);
}

.form {
  display: grid;
  gap: 0.85rem;
}

label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text-muted);
}

.mfa-setup {
  display: grid;
  gap: 0.5rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--border, #2a3140);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.04);
}

.mfa-title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 650;
}

.secret,
.uri {
  margin: 0;
  font-size: 0.78rem;
  word-break: break-all;
}

.secret code,
.uri code {
  font-size: 0.76rem;
}

.error {
  margin: 0;
  color: var(--danger);
  font-size: 0.88rem;
  font-weight: 500;
}

.muted {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}
</style>
