import { supabase, supabaseConfigured } from '@/lib/supabase'
import { CATALOG_META, getTipoConfig } from '@/lib/catalogMeta'

const CATEGORY_FIELDS = 'id,nome,slug,imagem,tipo_catalogo,carrinho_step,carrinho_min'
const CATEGORY_EMBED = 'id, nome, slug, carrinho_step, carrinho_min, tipo_catalogo'

function isVisible(row) {
  return row && row.visibilidade !== false
}

function visibleProducts(rows) {
  const list = Array.isArray(rows) ? rows : rows ? [rows] : []
  return list.filter(isVisible)
}

function normalizeStringList(value) {
  if (value == null) return []
  if (Array.isArray(value)) {
    return [...value].map((v) => String(v).trim()).filter(Boolean).sort()
  }
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) {
        return parsed.map((v) => String(v).trim()).filter(Boolean).sort()
      }
    } catch {
      /* continua */
    }
    const trimmed = value.trim()
    return trimmed ? [trimmed] : []
  }
  return []
}

function attachStorefrontFields(data, cfg) {
  const picker = cfg.storefront_picker
  if (picker?.source === 'model' && picker.field && picker.field in data) {
    data[picker.field] = normalizeStringList(data[picker.field])
  }
  return data
}

function modeloCores(data) {
  const cores = (data.modelo_cores || []).filter(isVisible)
  cores.sort((a, b) => (a.numero || 0) - (b.numero || 0))
  return cores
}

async function attachModeloCores(rows, tipo = null) {
  if (!rows?.length) return

  const cfg = getTipoConfig(tipo)
  const colorsTable = cfg?.colors_table
  if (!colorsTable) return

  const modelIds = rows.map((row) => String(row.id)).filter(Boolean)
  const coresByModel = Object.fromEntries(modelIds.map((id) => [id, []]))

  if (modelIds.length) {
    const { data: direct } = await supabase
      .from(colorsTable)
      .select('id_modelo, numero, nome, imagem, visibilidade')
      .in('id_modelo', modelIds)

    for (const cor of direct || []) {
      const mid = String(cor.id_modelo || '')
      if (coresByModel[mid]) coresByModel[mid].push(cor)
    }
  }

  for (const row of rows) {
    const mid = String(row.id || '')
    row.modelo_cores = modeloCores({ modelo_cores: coresByModel[mid] || [] })
  }
}

function storefrontContext(cfg) {
  return {
    mode: cfg.storefront_mode || 'variantes',
    product_table: cfg.product_table,
    picker: cfg.storefront_picker,
    specs: cfg.storefront_specs || [],
    badge: cfg.storefront_badge,
  }
}

function finalizeModelRow(row, cfg) {
  const pt = cfg.product_table
  const mode = cfg.storefront_mode || 'variantes'
  const products = visibleProducts(row[pt])

  if (mode === 'assento') {
    if (!products.length) return null
    products.sort((a, b) => String(a.altura || '').localeCompare(String(b.altura || '')))
    row[pt] = products
  } else {
    if (!products.length) return null
    products.sort((a, b) => String(a.dimensoes || '').localeCompare(String(b.dimensoes || '')))
    row[pt] = products
  }

  row._tipo_catalogo = cfg.tipo
  row._storefront = storefrontContext(cfg)
  row._storefront_mode = mode
  return row
}

export function getCatalogMeta() {
  return CATALOG_META
}

export async function listCategories() {
  if (!supabaseConfigured) throw new Error('Supabase não configurado.')

  const { data, error } = await supabase
    .from('categories')
    .select(CATEGORY_FIELDS)
    .eq('visibilidade', true)
    .order('nome')

  if (error) throw new Error(error.message)
  return data || []
}

export async function getCategoryById(id) {
  if (!supabaseConfigured) throw new Error('Supabase não configurado.')

  const { data, error } = await supabase
    .from('categories')
    .select(CATEGORY_FIELDS)
    .eq('id', id)
    .eq('visibilidade', true)
    .maybeSingle()

  if (error) throw new Error(error.message)
  if (!data) throw new Error('Categoria não encontrada.')
  return data
}

export async function getCategoryBySlug(slug) {
  if (!supabaseConfigured) throw new Error('Supabase não configurado.')

  const key = String(slug || '').trim()
  if (!key) throw new Error('Categoria não encontrada.')

  const { data, error } = await supabase
    .from('categories')
    .select(CATEGORY_FIELDS)
    .eq('slug', key)
    .eq('visibilidade', true)
    .maybeSingle()

  if (error) throw new Error(error.message)
  if (data) return data

  const { data: byName, error: nameError } = await supabase
    .from('categories')
    .select(CATEGORY_FIELDS)
    .ilike('nome', key)
    .eq('visibilidade', true)
    .maybeSingle()

  if (nameError) throw new Error(nameError.message)
  if (!byName) throw new Error('Categoria não encontrada.')
  return byName
}

export async function resolveCategoryParam(param) {
  const key = String(param || '').trim()
  if (!key) throw new Error('Categoria não encontrada.')
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(key)) {
    return getCategoryById(key)
  }
  return getCategoryBySlug(key)
}

async function requirePublicCategory(categoryId) {
  const { data, error } = await supabase
    .from('categories')
    .select('id,visibilidade')
    .eq('id', categoryId)
    .maybeSingle()
  if (error) throw new Error(error.message)
  return isVisible(data)
}

export async function catalogueModelsForTipo(tipo, categoryId, { filterField = null, filterValue = null } = {}) {
  if (!supabaseConfigured) throw new Error('Supabase não configurado.')

  const cfg = getTipoConfig(tipo)
  if (!cfg) return []
  if (!(await requirePublicCategory(categoryId))) return []

  const mt = cfg.model_table
  const pt = cfg.product_table
  const productFields = cfg.product_select || 'id, ean, barcode_url, visibilidade'

  let query = supabase
    .from(mt)
    .select(`*, categories(${CATEGORY_EMBED}), ${pt}(${productFields})`)
    .eq('id_categoria', categoryId)
    .eq('visibilidade', true)

  if (filterField && filterValue) {
    query = query.eq(filterField, filterValue)
  }

  const { data, error } = await query.order('nome')
  if (error) throw new Error(error.message)

  await attachModeloCores(data || [], tipo)

  const out = []
  for (const raw of data || []) {
    const row = attachStorefrontFields({ ...raw }, cfg)
    row.modelo_cores = modeloCores(row)
    const finalized = finalizeModelRow(row, cfg)
    if (finalized) out.push(finalized)
  }
  return out
}

export async function modelDetailForTipo(tipo, modelId) {
  if (!supabaseConfigured) throw new Error('Supabase não configurado.')

  const cfg = getTipoConfig(tipo)
  if (!cfg) return null

  const mt = cfg.model_table
  const pt = cfg.product_table

  const { data, error } = await supabase
    .from(mt)
    .select(`*, categories(${CATEGORY_EMBED},visibilidade), ${pt}(*)`)
    .eq('id', modelId)
    .maybeSingle()

  if (error) throw new Error(error.message)
  return await finalizeModelDetailRow(data, cfg)
}

export async function modelDetailForSlugs(categorySlug, modelSlug, tipo = null) {
  if (!supabaseConfigured) throw new Error('Supabase não configurado.')

  const category = await resolveCategoryParam(categorySlug)
  const resolvedTipo = tipo || category.tipo_catalogo
  const cfg = getTipoConfig(resolvedTipo)
  if (!cfg) return null

  const mt = cfg.model_table
  const pt = cfg.product_table
  const modKey = String(modelSlug || '').trim()
  if (!modKey) return null

  const isUuidKey = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(modKey)
  let data = null
  let error = null

  const baseSelect = `*, categories(${CATEGORY_EMBED},visibilidade), ${pt}(*)`
  const baseFilters = (q) =>
    q.eq('id_categoria', category.id).eq('visibilidade', true)

  if (isUuidKey) {
    ;({ data, error } = await baseFilters(supabase.from(mt).select(baseSelect)).eq('id', modKey).maybeSingle())
  } else {
    const { data: rows, error: rowsError } = await baseFilters(supabase.from(mt).select(baseSelect)).or(
      `slug.eq.${modKey},nome.ilike.${modKey}`,
    ).limit(1)
    error = rowsError
    data = rows?.[0] || null
  }

  if (error) throw new Error(error.message)
  return await finalizeModelDetailRow(data, cfg)
}

async function finalizeModelDetailRow(data, cfg) {
  if (!data || !isVisible(data)) return null
  if (data.categories && !isVisible(data.categories)) return null

  if (data.categories) {
    const { visibilidade: _v, ...publicCat } = data.categories
    data.categories = publicCat
  }

  await attachModeloCores([data], cfg.tipo)
  const row = attachStorefrontFields({ ...data }, cfg)
  row.modelo_cores = modeloCores(row)
  return finalizeModelRow(row, cfg)
}

export async function modelDetailAuto(modelId) {
  for (const cfg of CATALOG_META.catalog_types) {
    const data = await modelDetailForTipo(cfg.tipo, modelId)
    if (data) return data
  }
  return null
}
