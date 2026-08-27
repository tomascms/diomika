import { ref } from 'vue'

import { apiGet } from '@/lib/api'
import {
  catalogueModelsForCategory,
  modelDetailAuto,
  modelDetailForSlugs,
  modelDetailForTipo,
} from '@/lib/catalogSupabase'
import { getCatalogMeta, setLiveCatalogMeta } from '@/lib/catalogMeta'
import { supabaseConfigured } from '@/lib/supabase'

import {
  formatBadgeLabel,
  formatPickerLabel,
  isSingleProductMode,
  storefrontContextForModel,
  prettyCatalogLabel,
} from '@/lib/storefrontFormat'
import { parseDimensions } from '@/lib/images'

const metaCache = ref(null)

export function useCatalog() {
  const loadMeta = async (force = false) => {
    if (metaCache.value && !force) return metaCache.value
    try {
      // Fonte de verdade: API (evita drift com catalogMeta.js estático)
      const data = await apiGet('/catalogo/meta')
      metaCache.value = data
      setLiveCatalogMeta(data)
    } catch {
      metaCache.value = getCatalogMeta()
    }
    return metaCache.value
  }

  const tipoConfig = (tipo) =>
    (metaCache.value?.catalog_types || []).find((t) => t.tipo === tipo) || null

  const storefrontMode = (tipo) => tipoConfig(tipo)?.storefront_mode || 'variantes'

  const isAssentoMode = (tipo) => storefrontMode(tipo) === 'assento'

  const isAggregatedMode = (tipo) => storefrontMode(tipo) === 'aggregado'

  const storefrontContext = (tipo, model = null) => {
    if (model?._storefront) return model._storefront
    const physicalTipo = model?._tipo_catalogo || tipo
    return storefrontContextForModel(model, tipoConfig(physicalTipo))
  }

  const badgeLabel = (model, tipo) => {
    const ctx = storefrontContext(tipo, model)
    const fam = model?._familia_label
    const base = formatBadgeLabel(ctx.badge, model)
    if (fam && isAggregatedMode(tipo)) return fam
    return base || fam || ''
  }

  const buildFilterQuery = (tipo, activeFilters) => {
    const params = new URLSearchParams()
    for (const [field, value] of Object.entries(activeFilters || {})) {
      if (value) params.set(`filter_${field}`, value)
    }
    const qs = params.toString()
    return qs ? `?${qs}` : ''
  }

  const fetchCategoryModels = async (tipo, categoryId, activeFilters = null) => {
    if (supabaseConfigured && !metaCache.value) {
      await loadMeta()
    }

    let url = `/catalogo/${encodeURIComponent(tipo)}/modelos-catalogo/${categoryId}`
    url += buildFilterQuery(tipo, activeFilters)

    if (supabaseConfigured) {
      return catalogueModelsForCategory(tipo, categoryId, { filters: activeFilters || {} })
    }

    return apiGet(url)
  }

  const fetchModelDetail = async ({ categorySlug = null, modelSlug = null, modelId = null, tipo = null } = {}) => {
    if (supabaseConfigured) {
      let data = null
      if (categorySlug && modelSlug) {
        data = await modelDetailForSlugs(categorySlug, modelSlug, tipo)
      } else if (modelId) {
        data = tipo
          ? await modelDetailForTipo(tipo, modelId)
          : await modelDetailAuto(modelId)
      }
      if (!data) throw new Error('Modelo não encontrado.')
      const resolvedTipo = data._tipo_catalogo || tipo
      return {
        ...data,
        _tipo_catalogo: resolvedTipo,
        _storefront_mode:
          data._storefront_mode || (resolvedTipo ? storefrontMode(resolvedTipo) : data._storefront_mode),
      }
    }

    if (categorySlug && modelSlug) {
      const resolvedTipo =
        tipo || (await apiGet(`/categorias/slug/${encodeURIComponent(categorySlug)}`)).tipo_catalogo
      const data = await apiGet(
        `/catalogo/${encodeURIComponent(resolvedTipo)}/modelo-detalhe/slug/${encodeURIComponent(categorySlug)}/${encodeURIComponent(modelSlug)}`,
      )
      return {
        ...data,
        _tipo_catalogo: data._tipo_catalogo || resolvedTipo,
        _storefront_mode: data._storefront_mode || storefrontMode(data._tipo_catalogo || resolvedTipo),
      }
    }

    if (tipo && modelId) {
      const data = await apiGet(`/catalogo/${encodeURIComponent(tipo)}/modelo-detalhe/${modelId}`)
      return {
        ...data,
        _tipo_catalogo: tipo,
        _storefront_mode: data._storefront_mode || storefrontMode(tipo),
      }
    }

    if (modelId) {
      return apiGet(`/catalogo/modelo-detalhe/${modelId}`)
    }

    throw new Error('Modelo não encontrado.')
  }

  const buildPickerOptions = (model, ctx) => {
    if (!model || !ctx) return []

    const withEan = (rows) => {
      const list = Array.isArray(rows) ? rows : rows ? [rows] : []
      return list.filter((p) => p && String(p.ean || '').trim())
    }

    if (ctx.mode === 'unico') {
      const pt = ctx.product_table
      const product = withEan(model[pt])[0]
      if (!product) return []
      return [
        {
          id: product.id,
          value: product,
          raw: product.ean,
          label: 'Referência',
          product,
        },
      ]
    }

    if (model.tipo_oculo === 'leitura') {
      const pt = ctx.product_table
      const product = withEan(model[pt])[0]
      if (!product) return []
      return [
        {
          id: product.id,
          value: product,
          raw: product.ean,
          label: 'Sortido',
          product,
        },
      ]
    }

    const picker = ctx.picker
    if (!picker) return []

    const productTable = ctx.product_table

    if (picker.source === 'model') {
      return (model[picker.field] || []).map((value) => ({
        id: value,
        value,
        label: formatPickerLabel(picker, value),
        raw: value,
      }))
    }

    const variants = withEan(model[productTable])
    const options = variants
      .filter((product) => product[picker.field] != null && product[picker.field] !== '')
      .map((product) => ({
        id: product.id,
        value: product,
        raw: product[picker.field],
        label: formatPickerLabel(picker, product[picker.field]),
        product,
      }))

    if (picker.format === 'dimensions') {
      options.sort((a, b) => parseDimensions(a.raw) - parseDimensions(b.raw))
    }

    return options
  }

  const activeProduct = (model, ctx, selectedOption) => {
    if (!model || !ctx) return null
    if (isSingleProductMode(ctx)) {
      const pt = ctx.product_table
      const products = Array.isArray(model[pt]) ? model[pt] : model[pt] ? [model[pt]] : []
      return selectedOption?.value || products[0] || null
    }
    return selectedOption?.value || null
  }

  const filterDefinitionsForTipo = (tipo) => {
    const cfg = tipoConfig(tipo)
    return cfg?.storefront_filters || []
  }

  const filterOptionsForField = (filterDef) => {
    if (!filterDef) return [{ value: '', label: 'Todos' }]
    return [
      { value: '', label: 'Todos' },
      ...(filterDef.options || []).map((v) => ({
        value: v,
        label: filterDef.labels?.[v] || prettyCatalogLabel(v),
      })),
    ]
  }

  const realtimeTables = () => {
    const tables = new Set()
    for (const t of metaCache.value?.catalog_types || []) {
      if (t.colors_table) tables.add(t.colors_table)
      if (t.model_table) tables.add(t.model_table)
      if (t.product_table) tables.add(t.product_table)
    }
    return [...tables]
  }

  return {
    metaCache,
    loadMeta,
    tipoConfig,
    storefrontMode,
    isAssentoMode,
    isAggregatedMode,
    storefrontContext,
    badgeLabel,
    fetchCategoryModels,
    fetchModelDetail,
    buildPickerOptions,
    activeProduct,
    filterDefinitionsForTipo,
    filterOptionsForField,
    realtimeTables,
  }
}
