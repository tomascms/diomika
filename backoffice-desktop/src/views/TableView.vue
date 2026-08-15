<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/lib/api'
import { useWorkspace } from '@/composables/useWorkspace'
import DataList from '@/components/DataList.vue'
import CategoryCreatePanel from '@/components/CategoryCreatePanel.vue'

const route = useRoute()
const router = useRouter()
const { tableConfig, workspace } = useWorkspace()

const plan = ref(null)
const rows = ref([])
const loading = ref(true)
const error = ref('')
const message = ref('')
const filterText = ref('')
const showNewPicker = ref(false)
const importInput = ref(null)
const importBusy = ref(false)
const categories = ref([])
const newCategoryId = ref('')

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

const recordLabel = (row) => {
  if (table.value === 'produtos') {
    const model = row.modelos_almofadas || row.modelos_assentos
    const parts = [model?.nome, row.dimensoes, row.ean].filter(Boolean)
    return parts.join(' · ') || '—'
  }
  return row.nome || row.ean || String(row.id).slice(0, 8)
}

const categoryLabel = (row) => {
  if (row._categoria_label) return row._categoria_label
  if (row.categories?.nome) return row.categories.nome
  const model = row.modelos_almofadas || row.modelos_assentos
  return model?.categories?.nome || '—'
}

const columns = computed(() => {
  if (isMerged.value) {
    return [
      { key: 'nome', label: table.value === 'produtos' ? 'Produto' : 'Modelo', format: recordLabel },
      { key: '_categoria', label: 'Categoria', format: categoryLabel },
    ]
  }
  const fields = tableConfig(table.value)?.list_label_fields || ['nome']
  // Preferir nome + contexto útil (evita slug duplicado quando igual ao nome)
  if (isCategories.value) {
    const pretty = (s) => {
      const t = String(s || '').trim()
      return t ? t.charAt(0).toUpperCase() + t.slice(1) : ''
    }
    return [
      { key: 'nome', label: 'Nome', format: (row) => pretty(row.nome) || '—' },
      {
        key: 'tipo_catalogo',
        label: 'Tipo',
        format: (row) => pretty(row.tipo_catalogo) || (row.slug !== row.nome ? row.slug : ''),
      },
    ]
  }
  return fields.map((f) => ({ key: f, label: f.replace(/_/g, ' ') }))
})

const filteredRows = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((r) => JSON.stringify(r).toLowerCase().includes(q))
})

const loadPlan = async () => {
  if (!isCategories.value) return
  try {
    plan.value = await api.categoriesPlan()
  } catch {
    plan.value = null
  }
}

const loadRows = async () => {
  loading.value = true
  error.value = ''
  try {
    if (isMerged.value) {
      const viewKey = table.value === 'produtos' ? 'produtos' : 'modelos'
      rows.value = await api.mergedList(viewKey)
    } else {
      rows.value = await api.listRecords(table.value, { visible_only: 'false' })
    }
  } catch (e) {
    error.value = e.message
    rows.value = []
  } finally {
    loading.value = false
  }
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

const physicalTableForCategory = (categoryId) => {
  const cat = categories.value.find((c) => c.id === categoryId)
  if (!cat?.tipo_catalogo) return null
  const ct = catalogTypes.value.find((t) => t.tipo === cat.tipo_catalogo)
  if (!ct) return null
  return table.value === 'produtos' ? ct.product_table : ct.model_table
}

const startNew = async () => {
  if (isMerged.value) {
    categories.value = (await api.listCategories()).filter((c) => c.tipo_catalogo)
    newCategoryId.value = ''
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
  const physicalTable = physicalTableForCategory(newCategoryId.value)
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

watch(table, () => {
  loadRows()
  loadPlan()
}, { immediate: true })

onMounted(loadPlan)
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
        <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.nome }}</option>
      </select>
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
</style>
