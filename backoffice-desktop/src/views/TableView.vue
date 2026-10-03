<script setup>
defineOptions({ name: 'TableView' })

import { ref, computed, watch, onMounted, onActivated } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { useWorkspace } from '@/composables/useWorkspace'
import { useAggregatedTipos } from '@/composables/useAggregatedTipos'
import DataList from '@/components/DataList.vue'
import CategoryCreatePanel from '@/components/CategoryCreatePanel.vue'

const PAGE_SIZE = 40

const route = useRoute()
const router = useRouter()
const { tableConfig, workspace } = useWorkspace()
const { getAggregatedTiposForCategory } = useAggregatedTipos()

const rows = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const message = ref('')
const filterText = ref('')
const filterCategoriaId = ref('')
const filterModeloId = ref('')
const showNewPicker = ref(false)
const importInput = ref(null)
const importBusy = ref(false)
const categories = ref([])
const newCategoryId = ref('')
const listOffset = ref(0)
const hasMore = ref(false)
const totalApprox = ref(null)
let loadSeq = 0

const table = computed(() => route.params.table)
const isCategories = computed(() => table.value === 'categories')
const cfg = computed(() => tableConfig(table.value) || workspace.value?.sidebar?.[table.value])
const isMerged = computed(() => {
  if (table.value === 'produtos' || table.value === 'modelos') return true
  return Boolean(cfg.value?.ui_catalog_merged_list)
})
const sectionLabel = computed(() => cfg.value?.label || table.value)
const canShowNew = computed(() => !isCategories.value)
const canImportExport = computed(() => !isCategories.value && !isMerged.value)

const catalogTypes = computed(() => workspace.value?.catalog?.catalog_types || [])
const categoryDefinitions = computed(() => workspace.value?.catalog?.category_definitions || {})

// Esquema unificado: a relação "modelo" embutida numa linha de produto vem
// sempre sob o nome físico da tabela (product_models), seja qual for a
// família — já não é preciso adivinhar entre N tabelas.
const embeddedModel = (row) => row?.product_models || null

const recordLabel = (row) => {
  if (table.value === 'produtos') {
    const model = embeddedModel(row)
    const attrs = row.attributes || {}
    const parts = [model?.nome, attrs.dimensoes, attrs.altura, attrs.segmento, row.ean].filter(Boolean)
    return parts.join(' · ') || '—'
  }
  return row.nome || row.ean || String(row.id).slice(0, 8)
}

const categoryLabel = (row) => {
  if (row.categories?.nome) return row.categories.nome
  const model = embeddedModel(row)
  if (model?.categories?.nome) return model.categories.nome
  if (row._categoria_label) return row._categoria_label
  return '—'
}

const rowSearchText = (row) => {
  const model = embeddedModel(row)
  const attrs = row.attributes || {}
  const parts = [
    row.nome,
    row.ean,
    attrs.dimensoes,
    attrs.altura,
    attrs.segmento,
    row.slug,
    row._categoria_label,
    row.categories?.nome,
    model?.nome,
    model?.categories?.nome,
    row._ptable,
  ]
  return parts.filter(Boolean).join(' ').toLowerCase()
}

const columns = computed(() => {
  if (isMerged.value) {
    return [
      { key: 'nome', label: table.value === 'produtos' ? 'Produto' : 'Modelo', format: recordLabel },
      { key: '_categoria', label: 'Categoria', format: categoryLabel },
    ]
  }
  const fields = tableConfig(table.value)?.list_label_fields || ['nome']
  if (isCategories.value) {
    return [{ key: 'nome', label: 'Nome', format: (row) => String(row.nome || '').trim() || '—' }]
  }
  return fields.map((f) => ({ key: f, label: f.replace(/_/g, ' ') }))
})

const filteredRows = computed(() => {
  if (!isMerged.value) return rows.value
  const q = filterText.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((r) => rowSearchText(r).includes(q))
})

const newPhysicalTipo = ref('')

const mergedListParams = computed(() => {
  const params = {}
  if (filterCategoriaId.value) params.categoria_id = filterCategoriaId.value
  if (filterModeloId.value) params.modelo_id = filterModeloId.value
  const cat = categories.value.find((c) => String(c.id) === String(filterCategoriaId.value))
  if (cat?.tipo_catalogo) params.tipo_catalogo = cat.tipo_catalogo
  return params
})

const selectedCategory = computed(() =>
  categories.value.find((c) => c.id === newCategoryId.value) || null,
)


const isAggregatedCategory = computed(() => Boolean(getAggregatedTiposForCategory(selectedCategory.value)))

const loadRows = async ({ append = false } = {}) => {
  const seq = ++loadSeq
  if (append) loadingMore.value = true
  else {
    loading.value = true
    listOffset.value = 0
    hasMore.value = false
    totalApprox.value = null
  }
  error.value = ''
  try {
    if (isMerged.value && !filterCategoriaId.value) {
      if (seq !== loadSeq) return
      rows.value = []
      hasMore.value = false
      totalApprox.value = 0
      return
    }
    if (isMerged.value) {
      const viewKey = table.value === 'produtos' ? 'produtos' : 'modelos'
      const offset = append ? listOffset.value : 0
      const page = await api.mergedList(viewKey, {
        ...mergedListParams.value,
        limit: String(PAGE_SIZE),
        offset: String(offset),
      })
      if (seq !== loadSeq) return
      const items = page.items || []
      rows.value = append ? [...rows.value, ...items] : items
      listOffset.value = offset + items.length
      totalApprox.value = page.total_approx ?? null
      hasMore.value = items.length >= PAGE_SIZE && (
        totalApprox.value == null || listOffset.value < totalApprox.value
      )
    } else {
      const offset = append ? listOffset.value : 0
      const params = {
        visible_only: 'false',
        limit: String(PAGE_SIZE),
        offset: String(offset),
      }
      const q = filterText.value.trim()
      if (q) params.q = q
      const page = await api.listRecordsPage(table.value, params)
      if (seq !== loadSeq) return
      const items = page.items || []
      rows.value = append ? [...rows.value, ...items] : items
      listOffset.value = offset + items.length
      hasMore.value = items.length >= PAGE_SIZE
    }
  } catch (e) {
    if (seq !== loadSeq) return
    error.value = e.message
    // Não limpar rows existentes — evita «Sem registos» falso em falhas transitórias
  } finally {
    if (seq === loadSeq) {
      loading.value = false
      loadingMore.value = false
    }
  }
}

const loadMore = () => {
  if (!hasMore.value || loadingMore.value || loading.value) return
  return loadRows({ append: true })
}

const onCategoryCreated = async () => {
  message.value = 'Categoria criada.'
  error.value = ''
  await loadRows()
}

const openRow = (row) => {
  const ptable = row._ptable || table.value
  router.push({ name: 'record-edit', params: { table: ptable, id: row.id } })
}

const toggleVisibility = async (row) => {
  const ptable = row._ptable || table.value
  const next = row.visibilidade === false
  try {
    await api.setVisibility(ptable, row.id, next)
    row.visibilidade = next
    message.value = next ? 'Registo visível.' : 'Registo oculto.'
  } catch (e) {
    error.value = e.message
  }
}

const deleteRow = async (row) => {
  const ptable = row._ptable || table.value
  const ok = confirm(
    'Apagar este registo da base de dados?\n\nEsta acção não pode ser desfeita.\nPara ocultar sem apagar, use o botão Visível/Oculto.',
  )
  if (!ok) return
  try {
    await api.deleteRecord(ptable, row.id, true)
    rows.value = rows.value.filter((r) => r.id !== row.id)
    message.value = 'Registo eliminado.'
  } catch (e) {
    error.value = e.message
  }
}

const physicalTableForCategory = (categoryId, physicalTipo = null) => {
  const cat = categories.value.find((c) => c.id === categoryId)
  if (!cat?.tipo_catalogo) return null
  const aggregated = getAggregatedTiposForCategory(cat)
  const tipo = physicalTipo || cat.tipo_catalogo
  if (aggregated && !physicalTipo) return null
  const ct = catalogTypes.value.find((t) => t.tipo === tipo)
  if (!ct) return null
  return table.value === 'produtos' ? ct.product_table : ct.model_table
}

const startNew = async () => {
  if (isMerged.value) {
    if (!categories.value.length) {
      categories.value = await api.listCategoriesForForms()
    }
    newCategoryId.value = ''
    newPhysicalTipo.value = ''
    showNewPicker.value = true
    return
  }
  router.push({ name: 'record-new', params: { table: table.value } })
}

const confirmNew = () => {
  if (!newCategoryId.value) {
    error.value = 'Escolha uma categoria.'
    return
  }
  const cat = selectedCategory.value
  const aggregated = getAggregatedTiposForCategory(cat)
  if (aggregated && !newPhysicalTipo.value) {
    error.value = 'Escolha a família de produto.'
    return
  }
  const physicalTable = physicalTableForCategory(newCategoryId.value, newPhysicalTipo.value || null)
  if (!physicalTable) {
    error.value = 'Categoria inválida ou tipo de catálogo em falta.'
    return
  }
  router.push({
    name: 'record-new-physical',
    params: { table: table.value, physicalTable },
    query: { id_categoria: newCategoryId.value },
  })
}

const exportTable = async () => {
  try {
    const blob = await api.exportCsv(table.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${table.value}.csv`
    a.click()
    URL.revokeObjectURL(url)
    message.value = 'Exportação concluída.'
  } catch (e) {
    error.value = e.message
  }
}

const triggerImport = () => importInput.value?.click()

const onImportFile = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const preview = await api.importCsv(table.value, file, true)
    const ok = confirm(`Pré-visualização: ${preview.created} linhas válidas.\nImportar para a base de dados?`)
    if (!ok) return
    const result = await api.importCsv(table.value, file, false)
    message.value = `Importação: ${result.created} criados, ${result.updated} actualizados.`
    await loadRows()
  } catch (e) {
    error.value = e.message
  } finally {
    importBusy.value = false
  }
}

const filterModeloOptions = ref([])

const loadModeloFilterOptions = async () => {
  filterModeloOptions.value = []
  filterModeloId.value = ''
  if (table.value !== 'produtos' || !filterCategoriaId.value) return
  try {
    const page = await api.mergedList('modelos', {
      categoria_id: filterCategoriaId.value,
      tipo_catalogo: categories.value.find((c) => String(c.id) === String(filterCategoriaId.value))?.tipo_catalogo || '',
      limit: '100',
      offset: '0',
    })
    filterModeloOptions.value = (page.items || []).map((m) => ({
      id: m.id,
      label: m.nome || String(m.id).slice(0, 8),
    }))
  } catch {
    filterModeloOptions.value = []
  }
}

const ensureCategories = async () => {
  if (!isMerged.value || categories.value.length) return
  try {
    categories.value = await api.listCategoriesForForms()
  } catch {
    categories.value = []
  }
}

watch(table, (next, prev) => {
  filterCategoriaId.value = ''
  filterModeloId.value = ''
  filterText.value = ''
  filterModeloOptions.value = []
  if (prev !== undefined && next !== prev) {
    rows.value = []
    hasMore.value = false
    totalApprox.value = null
  }
  void loadRows()
  void ensureCategories()
}, { immediate: true })

watch([filterCategoriaId, filterModeloId], () => {
  if (isMerged.value) void loadRows()
})

watch(filterCategoriaId, () => {
  if (table.value === 'produtos') void loadModeloFilterOptions()
})

let filterDebounce = null
watch(filterText, () => {
  if (isMerged.value) return
  clearTimeout(filterDebounce)
  filterDebounce = setTimeout(() => void loadRows(), 300)
})

onMounted(() => {
  void ensureCategories()
})

onActivated(() => {
  void ensureCategories()
})
</script>

<template>
  <div class="page-view">
    <CategoryCreatePanel v-if="isCategories" @created="onCategoryCreated" @error="error = $event" />

    <div class="toolbar toolbar-panel">
      <input v-model="filterText" class="input search" type="search" placeholder="Filtrar registos…" />
      <template v-if="isMerged">
        <select v-model="filterCategoriaId" class="input filter-mini">
          <option value="">— Escolher categoria —</option>
          <option v-for="c in categories" :key="c.id" :value="c.id">
            {{ c.nome }}{{ c.visibilidade === false ? ' (oculta no site)' : '' }}
          </option>
        </select>
        <select v-if="table === 'produtos'" v-model="filterModeloId" class="input filter-mini">
          <option value="">Todos modelos</option>
          <option v-for="m in filterModeloOptions" :key="m.id" :value="m.id">{{ m.label }}</option>
        </select>
      </template>
      <button v-if="canShowNew" type="button" class="btn btn-primary" @click="startNew">Novo registo</button>
      <template v-if="canImportExport">
        <button class="btn btn-ghost" @click="exportTable">Exportar CSV</button>
        <button class="btn btn-ghost" :disabled="importBusy" @click="triggerImport">
          {{ importBusy ? 'A importar…' : 'Importar CSV' }}
        </button>
        <input ref="importInput" type="file" accept=".csv,text/csv" class="hidden-file" @change="onImportFile" />
      </template>
    </div>

    <div v-if="showNewPicker" class="card picker">
      <h3>Novo registo — {{ sectionLabel }}</h3>
      <label>Categoria</label>
      <select v-model="newCategoryId" class="input">
        <option value="">— Escolher categoria —</option>
        <option v-for="c in categories" :key="c.id" :value="c.id">
          {{ c.nome }}{{ c.visibilidade === false ? ' (oculta no site)' : '' }}
        </option>
      </select>
      <template v-if="isAggregatedCategory">
        <label>Família</label>
        <select v-model="newPhysicalTipo" class="input">
          <option value="">— Escolher família —</option>
          <option
            v-for="tipo in getAggregatedTiposForCategory(selectedCategory)"
            :key="tipo"
            :value="tipo"
          >
            {{ catalogTypes.find((t) => t.tipo === tipo)?.label || tipo }}
          </option>
        </select>
      </template>
      <div class="picker-actions">
        <button class="btn btn-ghost" @click="showNewPicker = false">Cancelar</button>
        <button class="btn btn-primary" @click="confirmNew">Continuar</button>
      </div>
    </div>

    <p v-if="message" class="ok">{{ message }}</p>
    <p v-if="error" class="err">{{ error }}</p>

    <p v-if="isMerged && !filterCategoriaId && !loading" class="notice">
      Escolha uma categoria acima para carregar modelos ou produtos — evita esperas longas.
    </p>

    <DataList
      :rows="filteredRows"
      :columns="columns"
      :loading="loading"
      @open="openRow"
      @toggle-visibility="toggleVisibility"
      @delete="deleteRow"
    />

    <div v-if="isMerged && rows.length" class="pager">
      <p class="pager-meta">
        A mostrar {{ rows.length }}{{ totalApprox != null ? ` de ~${totalApprox}` : '' }} registos
      </p>
      <button
        v-if="hasMore"
        type="button"
        class="btn btn-ghost"
        :disabled="loadingMore || loading"
        @click="loadMore"
      >
        {{ loadingMore ? 'A carregar…' : 'Carregar mais' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.page-view {
  display: grid;
  gap: 20px;
}

.toolbar-panel {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 18px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition);
  animation: slideDown 0.4s ease-out;
}

.toolbar-panel:focus-within {
  border-color: var(--accent);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
}

.input {
  padding: 11px 13px;
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 14px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.01) 100%);
  color: var(--text-primary);
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.04);
}

.input::placeholder {
  color: var(--text-muted);
}

.input:hover {
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
}

.input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12), inset 0 0 0 1px rgba(59, 130, 246, 0.1);
  background: linear-gradient(to bottom, var(--surface), rgba(59, 130, 246, 0.03));
}

.input.search {
  flex: 1;
  min-width: 200px;
}

.input.filter-mini {
  min-width: 150px;
}

.hidden-file {
  display: none;
}

.notice {
  margin: 0;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12) 0%, rgba(59, 130, 246, 0.04) 100%);
  color: var(--accent);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-left: 4px solid var(--accent);
  font-size: 14px;
  font-weight: 600;
  animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.12);
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

.picker {
  padding: 22px;
  margin-bottom: 18px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.12);
  animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  position: relative;
  overflow: hidden;
}

.picker::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.3) 50%, transparent 100%);
  pointer-events: none;
}

.picker::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 100% 80% at 50% 0%, rgba(59, 130, 246, 0.03), transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.picker h3 {
  position: relative;
  z-index: 1;
  margin: 0 0 18px 0;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--text-primary);
}

.picker label {
  position: relative;
  z-index: 1;
  display: block;
  margin: 18px 0 10px 0;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: var(--accent);
}

.picker-actions {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 12px;
  margin-top: 24px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.ok {
  color: var(--success);
  margin: 0 0 14px 0;
  font-weight: 700;
  font-size: 13px;
  padding: 12px 14px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);
  border-radius: var(--radius-md);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-left: 4px solid var(--success);
  animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
}

.err {
  color: var(--danger);
  margin: 0 0 14px 0;
  font-weight: 700;
  font-size: 13px;
  padding: 12px 14px;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
  border-radius: var(--radius-md);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 4px solid var(--danger);
  animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.12);
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 20px;
  padding: 14px 16px;
  background: linear-gradient(135deg, var(--bg-secondary) 0%, rgba(59, 130, 246, 0.04) 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  flex-wrap: wrap;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  animation: slideUp 0.4s ease-out 0.1s both;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.04);
}

.pager:hover {
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.12);
}

.pager-meta {
  margin: 0;
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 800;
  letter-spacing: 0.4px;
  text-transform: uppercase;
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
</style>
