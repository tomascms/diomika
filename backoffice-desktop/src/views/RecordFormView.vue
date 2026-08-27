<script setup>
import { ref, computed, watch } from 'vue'
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
const formData = ref({ visibilidade: false })
const relations = ref({})
const pendingFiles = ref({})
const fieldOptions = ref({})
const colorsPanel = ref(null)
const schemaFormRef = ref(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')
const createIdempotencyKey = ref(null)

const embedColors = computed(() => Boolean(schema.value?.config?.ui_embed_colors))
const catalogTipo = computed(() => schema.value?.config?.ui_catalog_tipo || null)
const colorsTable = computed(() => schema.value?.config?.ui_colors_table || null)
const savedModelId = computed(() => (isNew.value ? null : String(recordId.value)))
const isCatalogRecord = computed(() => Boolean(schema.value?.config?.ui_catalog_tipo || colorsTable.value))
const isPublished = computed(() => formData.value.visibilidade === true)

const title = computed(() =>
  isNew.value ? `Novo — ${schema.value?.label || table.value}` : `Editar — ${schema.value?.label || table.value}`,
)

const loadRelations = async (fields) => {
  const relTables = [...new Set(fields.filter((f) => f.relation).map((f) => f.relation))]
  const entries = await Promise.all(
    relTables.map(async (rt) => [rt, await api.listRelationOptions(rt)]),
  )
  relations.value = Object.fromEntries(entries)
}

const loadModelDiscriminatorOptions = async (modelId) => {
  const field = (schema.value?.fields || []).find((f) =>
    ['altura_modelo', 'dimensao_modelo'].includes(f.widget),
  )
  if (!field || !modelId) {
    fieldOptions.value = { ...fieldOptions.value, altura_modelo: [], dimensoes_modelo: [] }
    return
  }
  const relation = (schema.value?.fields || []).find((f) => f.name === 'id_modelo')?.relation
  if (!relation) return
  const modelField = field.widget === 'altura_modelo' ? 'alturas' : 'dimensoes'
  const optionKey = field.widget === 'altura_modelo' ? 'altura_modelo' : 'dimensoes_modelo'
  try {
    const model = await api.getRecord(relation, modelId)
    const raw = model?.[modelField]
    const values = Array.isArray(raw)
      ? raw.map((v) => String(v).trim()).filter(Boolean)
      : typeof raw === 'string'
        ? (() => {
            try {
              const parsed = JSON.parse(raw)
              return Array.isArray(parsed) ? parsed.map((v) => String(v).trim()).filter(Boolean) : []
            } catch {
              return raw.trim() ? [raw.trim()] : []
            }
          })()
        : []
    fieldOptions.value = { ...fieldOptions.value, [optionKey]: values }
  } catch {
    fieldOptions.value = { ...fieldOptions.value, [optionKey]: [] }
  }
}

watch(
  () => formData.value.id_modelo,
  (modelId) => {
    loadModelDiscriminatorOptions(modelId)
  },
)

let loadSeq = 0

const load = async () => {
  if (isNew.value && isCategories.value) {
    router.replace({ name: 'workspace', params: { table: 'categories' } })
    return
  }
  const seq = ++loadSeq
  loading.value = true
  error.value = ''
  try {
    const tableName = table.value
    const schemaPromise = api.formSchema(tableName)
    const recordPromise = !isNew.value
      ? api.getRecord(tableName, recordId.value)
      : Promise.resolve(null)

    const schemaData = await schemaPromise
    if (seq !== loadSeq) return
    schema.value = schemaData

    const relationsPromise = loadRelations(schemaData.fields || [])
    const [record] = await Promise.all([recordPromise, relationsPromise])
    if (seq !== loadSeq) return

    if (record) {
      formData.value = { ...record }
    } else {
      formData.value = { visibilidade: false }
      createIdempotencyKey.value = null
      const hasCategoria = (schemaData.fields || []).some((f) => f.name === 'id_categoria')
      if (hasCategoria && route.query.id_categoria) {
        formData.value.id_categoria = route.query.id_categoria
      }
    }
    await loadModelDiscriminatorOptions(formData.value.id_modelo)
  } catch (e) {
    if (seq === loadSeq) error.value = e.message
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

const resolvePendingImages = async (payload) => {
  const out = { ...payload }
  const entries = Object.entries(pendingFiles.value).filter(([, v]) => v)
  await Promise.all(
    entries.map(async ([field, fileOrFiles]) => {
      if (Array.isArray(fileOrFiles)) {
        const uploads = await Promise.all(
          fileOrFiles.map((f) => api.uploadImage(table.value, field, f)),
        )
        out[field] = uploads.map((up) => up.url)
      } else {
        const up = await api.uploadImage(table.value, field, fileOrFiles)
        out[field] = up.url
      }
    }),
  )
  return out
}

const saveDraft = async () => {
  if (saving.value) return
  if (schemaFormRef.value && !schemaFormRef.value.validate()) {
    error.value = 'Preencha os campos obrigatórios.'
    return
  }
  saving.value = true
  error.value = ''
  message.value = ''
  if (isNew.value && !createIdempotencyKey.value) {
    createIdempotencyKey.value = crypto.randomUUID()
  }
  try {
    let payload = { ...formData.value, visibilidade: false }
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
      const created = await api.createRecord(table.value, payload, createIdempotencyKey.value)
      savedId = created.id
    } else {
      await api.updateRecord(table.value, recordId.value, payload)
    }

    if (embedColors.value && colorsPanel.value) {
      try {
        await colorsPanel.value.save(String(savedId), { publish: false })
      } catch (e) {
        message.value = `Rascunho guardado, mas cores: ${e.message}`
        saving.value = false
        if (isNew.value && savedId) {
          await router.replace({
            name: 'record-edit',
            params: { table: route.params.table, physicalTable: route.params.physicalTable, id: savedId },
          })
        }
        return
      }
    }

    formData.value.visibilidade = false
    message.value = 'Rascunho guardado (oculto na loja).'
    if (isNew.value && savedId) {
      await router.replace({
        name: 'record-edit',
        params: {
          table: route.params.table,
          ...(route.params.physicalTable ? { physicalTable: route.params.physicalTable } : {}),
          id: savedId,
        },
      })
    }
  } catch (e) {
    error.value = e.message || 'Não foi possível guardar o rascunho.'
  } finally {
    saving.value = false
  }
}

const publish = async () => {
  if (saving.value) return
  if (schemaFormRef.value && !schemaFormRef.value.validate()) {
    error.value = 'Preencha os campos obrigatórios.'
    return
  }
  saving.value = true
  error.value = ''
  message.value = ''
  if (isNew.value && !createIdempotencyKey.value) {
    createIdempotencyKey.value = crypto.randomUUID()
  }
  try {
    // 1) Guardar sempre como rascunho primeiro (modelos novos nunca nascem públicos)
    let payload = { ...formData.value, visibilidade: false }
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
      const created = await api.createRecord(table.value, payload, createIdempotencyKey.value)
      savedId = created.id
    } else {
      await api.updateRecord(table.value, recordId.value, { ...payload, visibilidade: false })
    }

    if (embedColors.value && colorsPanel.value) {
      try {
        await colorsPanel.value.save(String(savedId), { publish: true })
      } catch (e) {
        message.value = `Dados guardados, mas cores: ${e.message}`
        saving.value = false
        if (isNew.value && savedId) {
          await router.replace({
            name: 'record-edit',
            params: {
              table: route.params.table,
              ...(route.params.physicalTable ? { physicalTable: route.params.physicalTable } : {}),
              id: savedId,
            },
          })
        }
        return
      }
    }

    // 2) Publicar via endpoint que valida cor + EAN
    if (isCatalogRecord.value) {
      await api.publishRecord(table.value, savedId)
    } else {
      await api.updateRecord(table.value, savedId, { ...payload, visibilidade: true })
    }

    formData.value.visibilidade = true
    message.value = 'Publicado na loja.'
    const backTable = route.params.physicalTable ? route.params.table : table.value
    setTimeout(() => router.push({ name: 'workspace', params: { table: backTable } }), 900)
  } catch (e) {
    const msg = e.message || ''
    if (isNew.value && /502|504|timeout|abort|inacessível/i.test(msg)) {
      error.value =
        'A API não respondeu a tempo, mas o registo pode ter sido criado. Verifique a lista antes de publicar outra vez.'
    } else if (isNew.value && /409|processamento/i.test(msg)) {
      error.value =
        'Pedido ainda em processamento. Aguarde alguns segundos e clique «Publicar» outra vez (não crie duplicado).'
    } else {
      error.value = msg
    }
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

watch(() => route.fullPath, load, { immediate: true })
</script>

<template>
  <div class="form-view">
    <div class="form-header">
      <button class="btn btn-ghost" @click="router.back()">← Voltar</button>
      <h2>{{ title }}</h2>
      <span v-if="isCatalogRecord && !isNew" class="vis-chip" :class="{ live: isPublished }">
        {{ isPublished ? 'Visível na loja' : 'Oculto no site' }}
      </span>
      <button
        v-if="!loading && schema"
        class="btn btn-ghost header-save"
        type="button"
        :disabled="saving"
        @click="saveDraft"
      >
        {{ saving ? 'A guardar…' : 'Guardar rascunho' }}
      </button>
      <button
        v-if="!loading && schema"
        class="btn btn-primary"
        type="button"
        :disabled="saving"
        @click="publish"
      >
        {{ saving ? 'A publicar…' : 'Publicar na loja' }}
      </button>
    </div>
    <p v-if="loading" class="loading-banner">A carregar formulário…</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="ok">{{ message }}</p>
    <div v-if="loading && !schema" class="form-card card form-skeleton" aria-hidden="true">
      <div class="sk-line" style="width:40%" />
      <div class="sk-line" style="width:100%" />
      <div class="sk-line" style="width:100%" />
      <div class="sk-line" style="width:70%" />
    </div>
    <div v-if="!loading && schema" class="form-card card">
      <SchemaForm
        ref="schemaFormRef"
        v-model="formData"
        :fields="schema.fields"
        :relations="relations"
        :field-options="fieldOptions"
        :editing="!isNew"
        :table-name="table"
        @pending-files="pendingFiles = $event"
      />
      <ModelColorsPanel
        v-if="embedColors"
        ref="colorsPanel"
        :model-id="savedModelId"
        :colors-table="colorsTable"
      />
      <div class="actions actions-sticky">
        <button class="btn btn-ghost" type="button" :disabled="saving" @click="saveDraft">
          {{ saving ? 'A guardar…' : 'Guardar rascunho' }}
        </button>
        <button class="btn btn-primary" type="button" :disabled="saving" @click="publish">
          {{ saving ? 'A publicar…' : 'Publicar na loja' }}
        </button>
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
  flex: 1;
  min-width: 160px;
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 560;
  letter-spacing: -0.02em;
}
.header-save { margin-left: auto; }
.vis-chip {
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  background: rgba(120, 120, 120, 0.15);
  color: var(--text-muted);
}
.vis-chip.live {
  background: rgba(34, 120, 70, 0.12);
  color: var(--success);
}
.form-card { padding: 1.35rem 1.4rem 5.5rem; max-width: 720px; }
.actions {
  display: flex;
  gap: 0.55rem;
  margin-top: 1.35rem;
  padding-top: 1.1rem;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.actions-sticky {
  position: sticky;
  bottom: 0;
  z-index: 5;
  margin-top: 1.5rem;
  padding: 0.85rem 0 0.35rem;
  background: linear-gradient(to top, var(--bg-panel) 78%, rgba(255, 255, 255, 0));
}
.error { color: var(--danger); font-weight: 600; }
.ok { color: var(--success); font-weight: 600; }
.loading-banner {
  margin: 0 0 0.75rem;
  padding: 0.55rem 0.85rem;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--accent-hover);
  background: var(--accent-soft);
  border-radius: var(--radius-sm);
}
.form-skeleton { display: grid; gap: 0.85rem; padding: 1.35rem 1.4rem; }
.form-skeleton .sk-line {
  height: 2.2rem;
  border-radius: 6px;
  background: linear-gradient(90deg, #e8ecef 0%, #f4f6f8 45%, #e8ecef 100%);
  background-size: 200% 100%;
  animation: shimmer 1.1s ease-in-out infinite;
}
@keyframes shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
</style>
