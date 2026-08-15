import { ref } from 'vue'

import { apiGet } from '@/lib/api'
import {
  catalogueModelsForTipo,
  getCatalogMeta,
  modelDetailAuto,
  modelDetailForSlugs,
  modelDetailForTipo,
} from '@/lib/catalogSupabase'
import { supabaseConfigured } from '@/lib/supabase'

import {

  formatBadgeLabel,

  formatPickerLabel,

  isSingleProductMode,

  storefrontContextForModel,

} from '@/lib/storefrontFormat'

import { parseDimensions } from '@/lib/images'



const metaCache = ref(null)



export function useCatalog() {

  const loadMeta = async (force = false) => {

    if (metaCache.value && !force) return metaCache.value

    metaCache.value = supabaseConfigured
      ? getCatalogMeta()
      : await apiGet('/catalogo/meta')

    return metaCache.value

  }



  const tipoConfig = (tipo) => (metaCache.value?.catalog_types || []).find((t) => t.tipo === tipo) || null

  const storefrontMode = (tipo) => tipoConfig(tipo)?.storefront_mode || 'variantes'

  const isAssentoMode = (tipo) => storefrontMode(tipo) === 'assento'



  const storefrontContext = (tipo, model = null) =>

    storefrontContextForModel(model, tipoConfig(tipo))



  const badgeLabel = (model, tipo) => {

    const ctx = storefrontContext(tipo, model)

    return formatBadgeLabel(ctx.badge, model)

  }



  const fetchCategoryModels = async (tipo, categoryId, filterTipo = null) => {
    if (supabaseConfigured && !metaCache.value) {
      await loadMeta()
    }

    let url = `/catalogo/${encodeURIComponent(tipo)}/modelos-catalogo/${categoryId}`

    if (filterTipo && storefrontMode(tipo) === 'variantes') {

      url += `?filter_tipo=${encodeURIComponent(filterTipo)}`

    }

    if (supabaseConfigured) {
      const filterField = filterTipo && storefrontMode(tipo) === 'variantes'
        ? (tipoConfig(tipo)?.storefront_filters?.[0]?.field || null)
        : null
      return catalogueModelsForTipo(tipo, categoryId, {
        filterField,
        filterValue: filterTipo || null,
      })
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
      return {
        ...data,
        _tipo_catalogo: data._tipo_catalogo || tipo,
        _storefront_mode: data._storefront_mode || (tipo ? storefrontMode(tipo) : data._storefront_mode),
      }
    }

    if (categorySlug && modelSlug) {
      const resolvedTipo = tipo || (await apiGet(`/categorias/slug/${encodeURIComponent(categorySlug)}`)).tipo_catalogo
      const data = await apiGet(
        `/catalogo/${encodeURIComponent(resolvedTipo)}/modelo-detalhe/slug/${encodeURIComponent(categorySlug)}/${encodeURIComponent(modelSlug)}`,
      )
      return {
        ...data,
        _tipo_catalogo: resolvedTipo,
        _storefront_mode: data._storefront_mode || storefrontMode(resolvedTipo),
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

    if (!model || !ctx?.picker) return []



    const picker = ctx.picker

    const productTable = ctx.product_table



    if (picker.source === 'model') {

      return (model[picker.field] || []).map((value) => ({

        id: value,

        value,

        label: formatPickerLabel(picker, value),

        raw: value,

      }))

    }



    const variants = Array.isArray(model[productTable]) ? model[productTable] : []

    const options = variants.map((product) => ({

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

      return model[pt] || null

    }

    return selectedOption?.value || null

  }



  const filterOptionsForTipo = (tipo) => {

    const cfg = tipoConfig(tipo)

    const filters = cfg?.storefront_filters || []

    const tipoFilter = filters.find((f) => f.field === 'tipo')

    if (!tipoFilter) return [{ value: '', label: 'Todos os tipos' }]

    return [

      { value: '', label: 'Todos os tipos' },

      ...(tipoFilter.options || []).map((v) => ({

        value: v,

        label: tipoFilter.labels?.[v] || v,

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

    storefrontContext,

    badgeLabel,

    fetchCategoryModels,

    fetchModelDetail,

    buildPickerOptions,

    activeProduct,

    filterOptionsForTipo,

    realtimeTables,

  }

}

