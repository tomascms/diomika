<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { workspace } from '@/composables/useWorkspace'
import { useAggregatedTipos } from '@/composables/useAggregatedTipos'
import SchemaForm from '@/components/SchemaForm.vue'
import ModelColorsPanel from '@/components/ModelColorsPanel.vue'
import ModelVariantsPanel from '@/components/ModelVariantsPanel.vue'

const route = useRoute()
const router = useRouter()
const { getAggregatedTiposForCategory } = useAggregatedTipos()

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
const variantsPanel = ref(null)
const schemaFormRef = ref(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')
const createIdempotencyKey = ref(null)
const categoryRows = ref([])
const familyTipo = ref('')
const bundleProductTable = ref(null)
const bundleColorsTable = ref(null)
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

const productTableForModel = computed(() => bundleProductTable.value)

const storefrontCheck = ref(null)

const storefrontIssues = computed(() => {
  const s = storefrontCheck.value
  if (!s) return []
  const issues = []
  if (!s.withEan) {
    issues.push('Falta pelo menos um produto com EAN (secção «Produtos (EAN)» abaixo).')
  }
  if (!s.withColorImg) {
    if (s.withEan > 0) {
      issues.push(
        `Já tem ${s.withEan} produto(s) com EAN, mas falta uma cor com imagem — a loja não mostra o modelo sem isso.`,
      )
    } else {
      issues.push('Falta pelo menos uma cor com imagem (secção «Cores do modelo» abaixo).')
    }
  }
  if (s.withEan > 0 && s.withColorImg > 0 && !s.published) {
    issues.push('Tudo pronto — falta clicar «Publicar na loja».')
  }
  return issues
})

const loadStorefrontCheck = async () => {
  storefrontCheck.value = null
  if (!isModelForm.value || isNew.value || !recordId.value) return
  if (!bundleProductTable.value || !bundleColorsTable.value) return
  try {
    const [products, colors] = await Promise.all([
      api.listRecords(bundleProductTable.value, { id_modelo: recordId.value, limit: '50' }),
      api.listModelColors(bundleColorsTable.value, recordId.value),
    ])
    storefrontCheck.value = {
      withEan: products.filter((p) => String(p.ean || '').trim()).length,
      withColorImg: colors.filter((c) => String(c.imagem || '').trim()).length,
      published: formData.value.visibilidade === true,
    }
  } catch {
    storefrontCheck.value = null
  }
}

const title = computed(() =>
  isNew.value ? `Novo — ${schema.value?.label || table.value}` : `Editar — ${schema.value?.label || table.value}`,
)

const selectedCategory = computed(() =>
  categoryRows.value.find((c) => String(c.id) === String(formData.value.id_categoria || '')) || null,
)

const aggregatedTipos = computed(() => getAggregatedTiposForCategory(selectedCategory.value))

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
  const aggregated = getAggregatedTiposForCategory(cat)
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
  // Preserva nome/descrição e quaisquer atributos que a família nova também
  // tenha (ex.: "composicao" existe em quase todas as famílias de têxteis) —
  // em vez de descartar tudo o resto do formulário ao mudar de categoria.
  formCarry = {
    nome: formData.value.nome,
    descricao: formData.value.descricao,
    attributes: { ...formData.value.attributes },
  }
  createIdempotencyKey.value = crypto.randomUUID()
  pendingFiles.value = {}
  await router.replace({
    name: 'record-new-physical',
    params: { table: 'modelos', physicalTable },
    query: categoryId ? { id_categoria: String(categoryId) } : {},
  })
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
    // Esquema unificado: dimensoes/alturas do modelo vivem em `attributes`.
    // O fallback de topo cobre respostas já achatadas pela API da loja.
    const raw = model?.attributes?.[modelField] ?? model?.[modelField]
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
    const bundleData = await api.formBundle(tableName, !isNew.value ? recordId.value : null)
    if (seq !== loadSeq) return

    const schemaData = {
      table: bundleData.table,
      label: bundleData.label,
      fields: bundleData.fields,
      config: bundleData.config,
    }
    schema.value = schemaData
    categoryRows.value = bundleData.categories || []
    relations.value = bundleData.relations || {}
    fieldOptions.value = bundleData.field_options || {}
    bundleProductTable.value = bundleData.product_table || null
    bundleColorsTable.value = bundleData.colors_table || null

    const record = bundleData.record
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
    await loadStorefrontCheck()
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
    if (embedColors.value && variantsPanel.value) {
      try {
        await variantsPanel.value.save(String(savedId), { publish: false })
      } catch (e) {
        message.value = `Rascunho guardado, mas produtos: ${e.message}`
        saving.value = false
        if (isNew.value && savedId) await goToEdit(savedId)
        return
      }
    }

    formData.value.visibilidade = false
    message.value = 'Rascunho guardado (oculto na loja).'
    if (isNew.value && savedId) await goToEdit(savedId)
    await loadStorefrontCheck()
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
    if (embedColors.value && variantsPanel.value) {
      try {
        await variantsPanel.value.save(String(savedId), { publish: true })
      } catch (e) {
        message.value = `Dados guardados, mas produtos: ${e.message}`
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
    await loadStorefrontCheck()
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

    <div v-if="storefrontIssues.length" class="storefront-banner card">
      <strong>Para aparecer na loja</strong>
      <ul>
        <li v-for="(issue, idx) in storefrontIssues" :key="idx">{{ issue }}</li>
      </ul>
    </div>

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
      <ModelVariantsPanel
        v-if="embedColors"
        ref="variantsPanel"
        :model-id="savedModelId"
        :product-table="productTableForModel"
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
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.06) 0%, rgba(59, 130, 246, 0.01) 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  animation: slideDown 0.3s ease-out;
}
.form-header h2 {
  margin: 0;
  flex: 1;
  min-width: 160px;
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.header-save { margin-left: auto; }
.vis-chip {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(120, 120, 120, 0.15) 0%, rgba(120, 120, 120, 0.05) 100%);
  color: var(--text-muted);
  border: 1px solid rgba(120, 120, 120, 0.2);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  transition: all var(--transition);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}
.vis-chip.live {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
  color: var(--success, #10b981);
  border-color: rgba(16, 185, 129, 0.3);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.15);
}
.error {
  color: var(--danger);
  margin: 0 0 0.75rem;
  padding: 0.85rem 1rem;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 3px solid var(--danger);
  border-radius: var(--radius-md);
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.1);
  font-weight: 500;
  font-size: 0.95rem;
}
.ok {
  color: var(--success, #10b981);
  margin: 0 0 0.75rem;
  padding: 0.85rem 1rem;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-left: 3px solid var(--success, #10b981);
  border-radius: var(--radius-md);
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.1);
  font-weight: 500;
  font-size: 0.95rem;
}
.storefront-banner {
  margin-bottom: 0.85rem;
  padding: 1rem;
  border-left: 3px solid #c47a00;
  background: linear-gradient(135deg, rgba(196, 122, 0, 0.15) 0%, rgba(196, 122, 0, 0.05) 100%);
  border-radius: var(--radius-md);
  border: 1px solid rgba(196, 122, 0, 0.3);
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 8px rgba(196, 122, 0, 0.1);
}
.storefront-banner strong {
  display: block;
  margin-bottom: 0.6rem;
  font-size: 0.95rem;
  color: var(--text-primary);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.storefront-banner ul {
  margin: 0;
  padding-left: 1.5rem;
  font-size: 0.88rem;
  color: var(--text-secondary);
  display: grid;
  gap: 0.35rem;
  line-height: 1.5;
}
.loading-banner {
  color: var(--text-muted);
  font-size: 0.95rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.15);
  border-radius: var(--radius-md);
  animation: slideDown 0.3s ease-out;
}
.form-card {
  padding: 1.5rem;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  animation: fadeIn 0.3s ease-out;
}
.form-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.3) 50%, transparent 100%);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  pointer-events: none;
}
.form-skeleton {
  display: grid;
  gap: 0.75rem;
  animation: fadeIn 0.2s ease-out;
}
.sk-line {
  height: 14px;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--bg-hover) 50%, var(--bg-secondary) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
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
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 1.5rem;
}
.actions-sticky {
  position: sticky;
  bottom: 0;
  padding: 1rem;
  background: linear-gradient(to top, var(--bg) 0%, var(--bg) 80%, transparent 100%);
  backdrop-filter: blur(8px);
  border-top: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
}
.create-flex {
  padding: 1rem;
  margin-bottom: 0.85rem;
  display: grid;
  gap: 0.85rem;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.15);
  border-radius: var(--radius-md);
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.05);
}
.create-flex-hint {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.5;
}
.family-field {
  display: grid;
  gap: 0.5rem;
  max-width: 320px;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.family-field .input {
  font-weight: 500;
  text-transform: none;
  letter-spacing: normal;
}
</style>
