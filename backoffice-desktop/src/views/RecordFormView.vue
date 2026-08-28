<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { workspace } from '@/composables/useWorkspace'
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
const categoryRows = ref([])
const familyTipo = ref('')
let switchingSchema = false
/** Campos a repor após mudar categoria/família (novo registo). */
let formCarry = null

const catalogTypes = computed(() => workspace.value?.catalog?.catalog_types || [])
const categoryDefinitions = computed(() => workspace.value?.catalog?.category_definitions || {})

const embedColors = computed(() => Boolean(schema.value?.config?.ui_embed_colors))
const catalogTipo = computed(() => schema.value?.config?.ui_catalog_tipo || null)
const colorsTable = computed(() => schema.value?.config?.ui_colors_table || null)
const savedModelId = computed(() => (isNew.value ? null : String(recordId.value)))
const isCatalogRecord = computed(() => Boolean(schema.value?.config?.ui_catalog_tipo || colorsTable.value))
const isPublished = computed(() => formData.value.visibilidade === true)
const isModelForm = computed(() =>
  catalogTypes.value.some((t) => t.model_table === table.value),
)
const isProductForm = computed(() =>
  catalogTypes.value.some((t) => t.product_table === table.value),
)

const title = computed(() =>
  isNew.value ? `Novo — ${schema.value?.label || table.value}` : `Editar — ${schema.value?.label || table.value}`,
)

const selectedCategory = computed(() =>
  categoryRows.value.find((c) => String(c.id) === String(formData.value.id_categoria || '')) || null,
)

const aggregatedTipos = computed(() => {
  const cat = selectedCategory.value
  if (!cat?.tipo_catalogo) return null
  for (const def of Object.values(categoryDefinitions.value || {})) {
    if (def.tipo_catalogo === cat.tipo_catalogo && def.aggregated_tipos?.length) {
      return def.aggregated_tipos
    }
  }
  return null
})

const showFamilyPicker = computed(
  () => isNew.value && isModelForm.value && Boolean(aggregatedTipos.value?.length),
)

/** Sempre editar/guardar na tabela física (nunca «modelos» / «produtos»). */
const goToEdit = (savedId) =>
  router.replace({
    name: 'record-edit',
    params: { table: table.value, id: String(savedId) },
  })

const modelTableForTipo = (tipo) =>
  catalogTypes.value.find((t) => t.tipo === tipo)?.model_table || null

const resolveTargetModelTable = (cat, preferredTipo = null) => {
  if (!cat?.tipo_catalogo) return null
  const aggregated = (() => {
    for (const def of Object.values(categoryDefinitions.value || {})) {
      if (def.tipo_catalogo === cat.tipo_catalogo && def.aggregated_tipos?.length) {
        return def.aggregated_tipos
      }
    }
    return null
  })()
  let tipo = preferredTipo || cat.tipo_catalogo
  if (aggregated?.length) {
    const currentTipo = catalogTipo.value
    if (preferredTipo && aggregated.includes(preferredTipo)) tipo = preferredTipo
    else if (currentTipo && aggregated.includes(currentTipo)) tipo = currentTipo
    else tipo = aggregated[0]
  }
  return modelTableForTipo(tipo)
}

const navigateNewPhysical = async (physicalTable, categoryId) => {
  if (!physicalTable) return
  if (physicalTable === table.value && String(route.query.id_categoria || '') === String(categoryId || '')) {
    return
  }
  switchingSchema = true
  formCarry = {
    nome: formData.value.nome,
    descricao: formData.value.descricao,
    composicao: formData.value.composicao,
  }
  createIdempotencyKey.value = crypto.randomUUID()
  pendingFiles.value = {}
  await router.replace({
    name: 'record-new-physical',
    params: { table: 'modelos', physicalTable },
    query: categoryId ? { id_categoria: String(categoryId) } : {},
  })
}

const loadCategories = async () => {
  try {
    categoryRows.value = await api.listCategoriesForForms()
  } catch {
    categoryRows.value = []
  }
}

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

watch(
  () => formData.value.id_categoria,
  async (catId) => {
    if (!isNew.value || !isModelForm.value || switchingSchema || loading.value) return
    if (!catId) return
    const cat = categoryRows.value.find((c) => String(c.id) === String(catId))
    if (!cat) return
    const target = resolveTargetModelTable(cat, familyTipo.value || null)
    if (!target) {
      error.value = 'Categoria sem tipo de catálogo — escolha outra.'
      return
    }
    if (target !== table.value) {
      message.value = ''
      error.value = ''
      await navigateNewPhysical(target, catId)
    }
  },
)

watch(familyTipo, async (tipo) => {
  if (!isNew.value || !showFamilyPicker.value || switchingSchema || loading.value) return
  if (!tipo || !formData.value.id_categoria) return
  const target = modelTableForTipo(tipo)
  if (target && target !== table.value) {
    await navigateNewPhysical(target, formData.value.id_categoria)
  }
})

let loadSeq = 0

const load = async () => {
  if (isNew.value && isCategories.value) {
    router.replace({ name: 'workspace', params: { table: 'categories' } })
    return
  }
  // Evitar formSchema em vistas virtuais (modelos/produtos)
  if (table.value === 'modelos' || table.value === 'produtos') {
    error.value = 'Escolha uma categoria e família para criar o registo.'
    loading.value = false
    schema.value = null
    return
  }
  const seq = ++loadSeq
  loading.value = true
  error.value = ''
  try {
    const tableName = table.value
    await loadCategories()
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
      if (formCarry) {
        formData.value = {
          ...formData.value,
          ...Object.fromEntries(
            Object.entries(formCarry).filter(([, v]) => v !== undefined && v !== null && v !== ''),
          ),
        }
        formCarry = null
      }
    }
    familyTipo.value = schemaData?.config?.ui_catalog_tipo || catalogTipo.value || ''
    await loadModelDiscriminatorOptions(formData.value.id_modelo)
  } catch (e) {
    if (seq === loadSeq) error.value = e.message
  } finally {
    if (seq === loadSeq) {
      loading.value = false
      await nextTick()
      switchingSchema = false
    }
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

const preparePayload = async () => {
  let payload = { ...formData.value, visibilidade: false }
  payload = await resolvePendingImages(payload)
  if (typeof payload.composicao === 'string') {
    try {
      payload.composicao = JSON.parse(payload.composicao)
    } catch {
      throw new Error('Composição inválida — use material e % em cada linha.')
    }
  }
  return payload
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
    const payload = await preparePayload()
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
        if (isNew.value && savedId) await goToEdit(savedId)
        return
      }
    }

    formData.value.visibilidade = false
    message.value = 'Rascunho guardado (oculto na loja).'
    if (isNew.value && savedId) await goToEdit(savedId)
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
    const payload = await preparePayload()
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
        if (isNew.value && savedId) await goToEdit(savedId)
        return
      }
    }

    if (isCatalogRecord.value) {
      await api.publishRecord(table.value, savedId)
    } else {
      await api.updateRecord(table.value, savedId, { ...payload, visibilidade: true })
    }

    formData.value.visibilidade = true
    message.value = 'Publicado. Pode criar outro sem voltar atrás.'
    if (isNew.value && savedId) await goToEdit(savedId)
  } catch (e) {
    const msg = e.message || ''
    if (isNew.value && /502|504|timeout|abort|inacessível/i.test(msg)) {
      error.value =
        'A API não respondeu a tempo, mas o registo pode ter sido criado. Verifique a lista antes de tentar outra vez.'
    } else if (isNew.value && /409|processamento/i.test(msg)) {
      error.value =
        'Pedido ainda em processamento. Aguarde e clique «Publicar» outra vez (não crie duplicado).'
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

/** Novo registo — limpa o formulário; pode mudar categoria/família na mesma página. */
const createAnother = async () => {
  const keepCat = formData.value?.id_categoria || route.query.id_categoria || ''
  message.value = ''
  error.value = ''
  pendingFiles.value = {}
  createIdempotencyKey.value = crypto.randomUUID()

  if (isNew.value) {
    formData.value = { visibilidade: false }
    if (keepCat) formData.value.id_categoria = String(keepCat)
    message.value = 'Formulário limpo — mude a categoria ou a subcategoria e guarde.'
    return
  }

  if (isModelForm.value) {
    await router.push({
      name: 'record-new-physical',
      params: { table: 'modelos', physicalTable: table.value },
      query: keepCat ? { id_categoria: String(keepCat) } : {},
    })
    return
  }
  if (isProductForm.value) {
    await router.push({
      name: 'record-new-physical',
      params: { table: 'produtos', physicalTable: table.value },
    })
    return
  }
  await router.push({
    name: 'record-new',
    params: { table: table.value },
  })
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

    <div v-if="isNew && isModelForm && !loading" class="create-flex card">
      <p class="create-flex-hint">
        Pode mudar a categoria (e a subcategoria) sem sair desta página — o formulário adapta-se.
      </p>
      <label v-if="showFamilyPicker" class="family-field">
        <span>Subcategoria</span>
        <select v-model="familyTipo" class="input">
          <option
            v-for="tipo in aggregatedTipos"
            :key="tipo"
            :value="tipo"
          >
            {{ catalogTypes.find((t) => t.tipo === tipo)?.label || tipo }}
          </option>
        </select>
      </label>
    </div>

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
        <button
          v-if="isCatalogRecord || isModelForm || isProductForm"
          class="btn btn-ghost"
          type="button"
          :disabled="saving"
          @click="createAnother"
        >
          Criar outro
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
  background: rgba(34, 140, 70, 0.15);
  color: var(--success, #1a7a3a);
}
.error { color: var(--danger); margin: 0 0 0.75rem; }
.ok { color: var(--success, #1a7a3a); margin: 0 0 0.75rem; }
.loading-banner { color: var(--text-muted); }
.form-card { padding: 1.25rem; }
.form-skeleton { display: grid; gap: 0.75rem; }
.sk-line {
  height: 14px;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--bg-hover), transparent);
}
.actions { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1.25rem; }
.actions-sticky {
  position: sticky;
  bottom: 0;
  padding: 0.75rem 0;
  background: var(--bg, #fff);
}
.create-flex {
  padding: 0.85rem 1rem;
  margin-bottom: 0.85rem;
  display: grid;
  gap: 0.65rem;
}
.create-flex-hint {
  margin: 0;
  font-size: 0.88rem;
  color: var(--text-muted);
}
.family-field {
  display: grid;
  gap: 0.35rem;
  max-width: 320px;
  font-size: 0.85rem;
  font-weight: 600;
}
.family-field .input {
  font-weight: 500;
}
</style>
