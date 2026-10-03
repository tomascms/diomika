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
  padding: 32px 20px;
  background:
    radial-gradient(ellipse 70% 50% at 15% 0%, rgba(59, 130, 246, 0.08), transparent 55%),
    radial-gradient(ellipse 50% 40% at 90% 100%, rgba(15, 23, 42, 0.04), transparent 50%),
    var(--bg);
}

.login-panel {
  width: min(420px, 100%);
  padding: 40px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
}

.brand {
  margin: 0;
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

h1 {
  margin: 8px 0 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.lead {
  margin: 16px 0 24px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.form {
  display: grid;
  gap: 16px;
}

label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
}

.input {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 14px;
  background: var(--surface);
  color: var(--text-primary);
  transition: all var(--transition);
}

.input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.input:disabled {
  background: var(--bg-secondary);
  color: var(--text-muted);
  cursor: not-allowed;
}

.mfa-setup {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius);
  background: var(--accent-soft);
}

.mfa-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
}

.secret,
.uri {
  margin: 0;
  font-size: 12px;
  word-break: break-all;
  color: var(--text-secondary);
}

.secret code,
.uri code {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 2px 4px;
  background: var(--surface);
  border-radius: 3px;
  color: var(--text-primary);
}

.error {
  margin: 0;
  padding: 10px 12px;
  color: var(--danger);
  font-size: 13px;
  font-weight: 500;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius);
}

.muted {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
