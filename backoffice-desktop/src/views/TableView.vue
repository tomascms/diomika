<script setup>
defineOptions({ name: 'TableView' })

import { ref, computed, watch, onMounted, onActivated } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { useWorkspace } from '@/composables/useWorkspace'
import DataList from '@/components/DataList.vue'
import CategoryCreatePanel from '@/components/CategoryCreatePanel.vue'

const PAGE_SIZE = 40

const route = useRoute()
const router = useRouter()
const { tableConfig, workspace } = useWorkspace()

const plan = ref(null)
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

const modelTables = computed(() =>
  (catalogTypes.value || []).map((t) => t.model_table).filter(Boolean),
)

const embeddedModel = (row) => {
  for (const mt of modelTables.value) {
    if (row[mt]) return row[mt]
  }
  return null
}

const recordLabel = (row) => {
  if (table.value === 'produtos') {
    const model = embeddedModel(row)
    const parts = [model?.nome, row.dimensoes, row.altura, row.segmento, row.ean].filter(Boolean)
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
  const parts = [
    row.nome,
    row.ean,
    row.dimensoes,
    row.altura,
    row.segmento,
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
  const q = filterText.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((r) => rowSearchText(r).includes(q))
})

const loadPlan = async () => {
  if (!isCategories.value) return
  try {
    plan.value = await api.categoriesPlan()
  } catch {
    plan.value = null
  }
}

const newPhysicalTipo = ref('')

const mergedListParams = computed(() => {
  const params = {}
  if (filterCategoriaId.value) params.categoria_id = filterCategoriaId.value
  if (filterModeloId.value) params.modelo_id = filterModeloId.value
  return params
})

const selectedCategory = computed(() =>
  categories.value.find((c) => c.id === newCategoryId.value) || null,
)

const aggregatedTiposForCategory = (cat) => {
  if (!cat?.tipo_catalogo) return null
  for (const def of Object.values(categoryDefinitions.value || {})) {
    if (def.tipo_catalogo === cat.tipo_catalogo && def.aggregated_tipos?.length) {
      return def.aggregated_tipos
    }
  }
  return null
}

const isAggregatedCategory = computed(() => Boolean(aggregatedTiposForCategory(selectedCategory.value)))

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
      const data = await api.listRecords(table.value, { visible_only: 'false', limit: '200' })
      if (seq !== loadSeq) return
      rows.value = data
      hasMore.value = false
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
  await loadPlan()
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
  const aggregated = aggregatedTiposForCategory(cat)
  const tipo = physicalTipo || cat.tipo_catalogo
  if (aggregated && !physicalTipo) return null
  const ct = catalogTypes.value.find((t) => t.tipo === tipo)
  if (!ct) return null
  return table.value === 'produtos' ? ct.product_table : ct.model_table
}

const startNew = async () => {
  if (isMerged.value) {
    if (!categories.value.length) {
      // Inclui categorias ocultas na loja — preparo de catálogo antes de publicar
      const all = await api.listRecords('categories', { visible_only: 'false', limit: '200' })
      categories.value = (Array.isArray(all) ? all : []).filter((c) => c.tipo_catalogo)
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
  const aggregated = aggregatedTiposForCategory(cat)
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
    const all = await api.listRecords('categories', { visible_only: 'false', limit: '200' })
    categories.value = (Array.isArray(all) ? all : []).filter((c) => c.tipo_catalogo)
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
  void loadPlan()
  void ensureCategories()
}, { immediate: true })

watch([filterCategoriaId, filterModeloId], () => {
  if (isMerged.value) void loadRows()
})

watch(filterCategoriaId, () => {
  if (table.value === 'produtos') void loadModeloFilterOptions()
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
    <CategoryCreatePanel
      v-if="isCategories && plan?.can_create"
      :plan="plan"
      @created="onCategoryCreated"
      @error="error = $event"
    />

    <p v-else-if="isCategories && plan && !plan.can_create" class="notice">
      Catálogo completo — abre uma categoria para editar.
    </p>

    <div class="toolbar toolbar-panel">
      <input v-model="filterText" class="input search" type="search" placeholder="Filtrar registos…" />
      <template v-if="isMerged">
        <select v-model="filterCategoriaId" class="input filter-mini">
          <option value="">Todas categorias</option>
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
            v-for="tipo in aggregatedTiposForCategory(selectedCategory)"
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
.page-view { display: grid; gap: 0.25rem; }
.toolbar { margin-bottom: 0; }
.search { max-width: none; }
.hidden-file { display: none; }
.notice {
  margin: 0 0 0.85rem;
  padding: 0.65rem 0.9rem;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--accent-hover);
  font-size: 0.88rem;
  font-weight: 600;
}
.picker { padding: 1.15rem 1.25rem; margin-bottom: 1rem; }
.picker h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 560;
}
.picker label { display: block; margin: 0.85rem 0 0.35rem; font-size: 0.84rem; font-weight: 600; color: var(--text-muted); }
.picker-actions { display: flex; gap: 0.55rem; margin-top: 1rem; }
.ok { color: var(--success); margin: 0 0 0.75rem; font-weight: 600; }
.err { color: var(--danger); margin: 0 0 0.75rem; font-weight: 600; }
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.85rem;
  flex-wrap: wrap;
}
.pager-meta {
  margin: 0;
  font-size: 0.84rem;
  color: var(--text-muted);
  font-weight: 550;
}
</style>
