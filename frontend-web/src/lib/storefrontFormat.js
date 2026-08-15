export function formatStorefrontValue(spec, value) {
  if (value == null || value === '') return null

  if (spec.widget === 'enum') {
    return spec.enum_labels?.[value] || value
  }

  if (spec.widget === 'composition' && typeof value === 'object' && !Array.isArray(value)) {
    return Object.entries(value)
      .map(([material, percent]) => `${percent}% ${material}`)
      .join(', ')
  }

  if (spec.widget === 'boolean') {
    return value ? 'Sim' : 'Não'
  }

  if (Array.isArray(value)) {
    return value.join(', ')
  }

  return String(value)
}

export function formatPickerLabel(picker, rawValue) {
  if (rawValue == null || rawValue === '') return ''
  if (picker?.format === 'dimensions') {
    return `${rawValue}${picker.suffix || ''}`.trim()
  }
  return String(rawValue)
}

export function formatBadgeLabel(badge, model) {
  if (!badge || !model) return ''
  const val = model[badge.field]
  if (!val) return ''
  return badge.labels?.[val] || val
}

export function storefrontContextForModel(model, tipoConfig) {
  return model?._storefront || {
    mode: tipoConfig?.storefront_mode || 'variantes',
    product_table: tipoConfig?.product_table,
    picker: tipoConfig?.storefront_picker,
    specs: tipoConfig?.storefront_specs || [],
    badge: tipoConfig?.storefront_badge,
  }
}

export function isSingleProductMode(ctx) {
  return ctx?.picker?.source === 'model'
}
