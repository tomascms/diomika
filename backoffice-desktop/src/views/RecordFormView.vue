<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import SchemaForm from '@/components/SchemaForm.vue'
import ModelColorsPanel from '@/components/ModelColorsPanel.vue'

const route = useRoute()
const router = useRouter()

const table = computed(() => route.params.physicalTable || route.params.table)
const recordId = computed(() => route.params.id)
const isNew = computed(() => !recordId.value)
const isCategories = computed(() => table.value === 'categories')

const schema = ref(null)
const formData = ref({ visibilidade: true })
const relations = ref({})
const pendingFiles = ref({})
const colorsPanel = ref(null)
const schemaFormRef = ref(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')

const embedColors = computed(() => Boolean(schema.value?.config?.ui_embed_colors))
const savedModelId = computed(() => (isNew.value ? null : String(recordId.value)))

const title = computed(() =>
  isNew.value ? `Novo — ${schema.value?.label || table.value}` : `Editar — ${schema.value?.label || table.value}`,
)

const loadRelations = async (fields) => {
  const relTables = [...new Set(fields.filter((f) => f.relation).map((f) => f.relation))]
  const out = {}
  for (const rt of relTables) {
    try {
      const data = await api.listRecords(rt, { visible_only: 'false', limit: '200' })
      out[rt] = data.map((r) => ({ id: r.id, label: r.nome || r.ean || r.numero || String(r.id).slice(0, 8) }))
    } catch {
      out[rt] = []
    }
  }
  relations.value = out
}

const load = async () => {
  if (isNew.value && isCategories.value) {
    router.replace({ name: 'workspace', params: { table: 'categories' } })
    return
  }
  loading.value = true
  error.value = ''
  try {
    schema.value = await api.formSchema(table.value)
    await loadRelations(schema.value.fields || [])
    if (!isNew.value) {
      formData.value = { ...(await api.getRecord(table.value, recordId.value)) }
    } else {
      formData.value = { visibilidade: true }
      if (route.query.id_categoria) formData.value.id_categoria = route.query.id_categoria
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const resolvePendingImages = async (payload) => {
  const out = { ...payload }
  for (const [field, fileOrFiles] of Object.entries(pendingFiles.value)) {
    if (!fileOrFiles) continue
    if (Array.isArray(fileOrFiles)) {
      const urls = []
      for (const f of fileOrFiles) {
        const up = await api.uploadImage(table.value, field, f)
        urls.push(up.url)
      }
      out[field] = urls
    } else {
      const up = await api.uploadImage(table.value, field, fileOrFiles)
      out[field] = up.url
    }
  }
  return out
}

const save = async () => {
  if (schemaFormRef.value && !schemaFormRef.value.validate()) {
    error.value = 'Preencha os campos obrigatórios.'
    return
  }
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    let payload = { ...formData.value }
    payload = await resolvePendingImages(payload)
    if (typeof payload.composicao === 'string') {
      try {
        payload.composicao = JSON.parse(payload.composicao)
      } catch {
        throw new Error('Composição inválida — use JSON válido (ex: {"algodao":60,"poliester":40}).')
      }
    }

    let savedId = recordId.value
    if (isNew.value) {
      const created = await api.createRecord(table.value, payload)
      savedId = created.id
    } else {
      await api.updateRecord(table.value, recordId.value, payload)
    }

    if (embedColors.value && colorsPanel.value) {
      try {
        await colorsPanel.value.save(String(savedId))
      } catch (e) {
        message.value = `Modelo guardado, mas cores: ${e.message}`
        saving.value = false
        return
      }
    }

    message.value = 'Guardado.'
    const backTable = route.params.physicalTable ? route.params.table : table.value
    setTimeout(() => router.push({ name: 'workspace', params: { table: backTable } }), 700)
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

const hideRecord = async () => {
  if (!confirm('Ocultar este registo no catálogo?')) return
  try {
    await api.deleteRecord(table.value, recordId.value, false)
    router.back()
  } catch (e) {
    error.value = e.message
  }
}

const hardDelete = async () => {
  if (
    !confirm(
      'Apagar este registo da base de dados?\n\nEsta acção não pode ser desfeita.\nPara ocultar sem apagar, use o botão Ocultar.',
    )
  ) {
    return
  }
  try {
    await api.deleteRecord(table.value, recordId.value, true)
    router.back()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div class="form-view">
    <div class="form-header">
      <button class="btn btn-ghost" @click="router.back()">← Voltar</button>
      <h2>{{ title }}</h2>
    </div>
    <p v-if="loading">A carregar…</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="ok">{{ message }}</p>
    <div v-if="!loading && schema" class="form-card card">
      <SchemaForm
        ref="schemaFormRef"
        v-model="formData"
        :fields="schema.fields"
        :relations="relations"
        :editing="!isNew"
        :table-name="table"
        @pending-files="pendingFiles = $event"
      />
      <ModelColorsPanel
        v-if="embedColors"
        ref="colorsPanel"
        :model-id="savedModelId"
      />
      <div class="actions">
        <button class="btn btn-primary" :disabled="saving" @click="save">{{ saving ? 'A guardar…' : 'Guardar' }}</button>
        <template v-if="!isNew">
          <button class="btn btn-ghost" type="button" @click="hideRecord">Ocultar</button>
          <button class="btn btn-danger" type="button" @click="hardDelete">Apagar</button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-header {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  margin-bottom: 1.1rem;
  flex-wrap: wrap;
}
.form-header h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 560;
  letter-spacing: -0.02em;
}
.form-card { padding: 1.35rem 1.4rem; max-width: 720px; }
.actions {
  display: flex;
  gap: 0.55rem;
  margin-top: 1.35rem;
  padding-top: 1.1rem;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.error { color: var(--danger); font-weight: 600; }
.ok { color: var(--success); font-weight: 600; }
</style>
