<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/lib/api'

const status = ref(null)
const lastAction = ref('')
const report = ref(null)
const loading = ref(false)
const error = ref('')

const summaryLines = computed(() => {
  const r = report.value
  if (!r) return []
  const lines = []
  if (r.message) lines.push(r.message)
  if (r.applied !== undefined) lines.push(r.applied ? 'Alterações aplicadas.' : 'Pré-visualização (nada aplicado).')
  if (r.created_tables?.length) lines.push(`Tabelas novas: ${r.created_tables.join(', ')}`)
  if (r.added_columns?.length) lines.push(`Colunas novas: ${r.added_columns.length}`)
  if (r.sql_pending?.length) lines.push(`SQL pendente: ${r.sql_pending.length} comando(s)`)
  if (r.seeded_categories?.length) lines.push(`Categorias seed: ${r.seeded_categories.join(', ')}`)
  if (r.new_field_warnings?.length) lines.push(`Avisos: ${r.new_field_warnings.length}`)
  return lines
})

const incompleteEntries = computed(() => {
  const inc = report.value?.incomplete_records || status.value?.incomplete_records || {}
  return Object.entries(inc).flatMap(([table, rows]) =>
    (rows || []).slice(0, 5).map((row) => ({ table, id: row.id, missing: row.missing_fields || row.missing || [] })),
  )
})

const loadStatus = async () => {
  try {
    status.value = await api.schemaStatus()
  } catch {
    status.value = null
  }
}

const runDry = async () => {
  loading.value = true
  error.value = ''
  lastAction.value = 'Pré-visualização'
  try {
    report.value = await api.schemaSync(true)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const runApply = async () => {
  if (!confirm('Aplicar alterações de schema na base de dados?')) return
  loading.value = true
  error.value = ''
  lastAction.value = 'Schema aplicado'
  try {
    report.value = await api.schemaSync(false)
    await loadStatus()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const runDeploySql = async () => {
  if (!confirm('Aplicar SQL de deploy (RLS, idempotency, infra)?')) return
  loading.value = true
  error.value = ''
  lastAction.value = 'SQL de deploy'
  try {
    report.value = await api.applyDeploySql()
    await loadStatus()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="schema-view">
    <div class="card intro">
      <h2>Schema & Sync</h2>
      <p>Edita <code>schemas.py</code>, reinicia a API, e aplica aqui. Sidebar e formulários actualizam sozinhos.</p>

      <div v-if="status" class="status-box card-inner">
        <h3>Estado actual</h3>
        <p>{{ status.message }}</p>
        <ul v-if="status.created_tables?.length || status.added_columns?.length">
          <li v-if="status.created_tables?.length">Tabelas em falta: {{ status.created_tables.join(', ') }}</li>
          <li v-if="status.added_columns?.length">Colunas pendentes: {{ status.added_columns.length }}</li>
          <li v-if="status.sql_pending?.length">SQL manual: {{ status.sql_pending.length }}</li>
        </ul>
      </div>

      <div class="workflow card-inner">
        <h3>Fluxo recomendado do catálogo</h3>
        <ol>
          <li><strong>Categorias</strong> — criar categoria com imagem e tipo de catálogo</li>
          <li><strong>Modelos</strong> — nome, descrição, specs (composição, alturas, etc.)</li>
          <li><strong>Cores</strong> — painel de cores no formulário do modelo</li>
          <li><strong>Produtos</strong> — EAN/código de barras por variante</li>
        </ol>
      </div>

      <div class="actions">
        <button class="btn btn-ghost" :disabled="loading" @click="runDry">Pré-visualizar</button>
        <button class="btn btn-primary" :disabled="loading" @click="runApply">Aplicar schema</button>
        <button class="btn btn-ghost" :disabled="loading" @click="runDeploySql">SQL de deploy</button>
        <button class="btn btn-ghost" :disabled="loading" @click="loadStatus">Actualizar estado</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="report" class="card report-panel">
      <h3>{{ lastAction || 'Resultado' }}</h3>
      <ul v-if="summaryLines.length" class="summary">
        <li v-for="(line, i) in summaryLines" :key="i">{{ line }}</li>
      </ul>

      <div v-if="incompleteEntries.length" class="incomplete">
        <h4>Registos incompletos</h4>
        <ul>
          <li v-for="item in incompleteEntries" :key="`${item.table}-${item.id}`">
            {{ item.table }} · {{ String(item.id).slice(0, 8) }}… — falta: {{ item.missing.join(', ') }}
          </li>
        </ul>
      </div>

      <details class="raw-json">
        <summary>Ver JSON completo</summary>
        <pre>{{ JSON.stringify(report, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

<style scoped>
.intro { padding: 1.35rem 1.4rem; margin-bottom: 1rem; }
.intro h2 {
  margin: 0 0 0.4rem;
  font-family: var(--font-display);
  font-weight: 560;
  font-size: 1.35rem;
}
.intro p { color: var(--text-muted); line-height: 1.6; margin: 0; }
.card-inner { margin-top: 1rem; padding: 1rem 1.1rem; background: var(--bg-soft); border-radius: var(--radius-sm); border: 1px solid var(--border); }
.card-inner h3, .card-inner h4 { margin: 0 0 10px; font-size: 0.95rem; }
.card-inner ol, .card-inner ul { margin: 0; padding-left: 1.25rem; line-height: 1.7; color: var(--text-muted); }
.status-box p { margin: 0; color: var(--text-muted); }
.actions { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
.report-panel { padding: 20px 24px; margin-bottom: 20px; }
.report-panel h3 { margin: 0 0 12px; }
.summary { margin: 0 0 16px; padding-left: 1.2rem; line-height: 1.7; }
.incomplete { margin-bottom: 16px; }
.incomplete ul { margin: 0; padding-left: 1.2rem; font-size: 0.88rem; color: var(--text-muted); }
.raw-json summary { cursor: pointer; color: var(--accent); font-size: 0.88rem; margin-bottom: 8px; }
.raw-json pre { overflow: auto; font-size: 0.75rem; max-height: 40vh; background: var(--bg-soft); padding: 12px; border-radius: 8px; border: 1px solid var(--border); }
.error { color: var(--danger); margin-top: 12px; }
</style>
