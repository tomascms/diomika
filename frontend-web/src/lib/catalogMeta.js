/** Metadados estáticos do catálogo — espelham backend/models/schemas.py (CATALOG_TYPES). */
export const CATALOG_META = {
  catalog_types: [
    {
      tipo: 'almofada',
      label: 'Almofadas',
      model_table: 'modelos_almofadas',
      product_table: 'almofada',
      product_select: 'id, ean, barcode_url, visibilidade, dimensoes',
      storefront_mode: 'variantes',
      storefront_filters: [
        {
          field: 'tipo',
          label: 'Tipo de Almofada',
          options: ['decorativa', 'dormir'],
          labels: { decorativa: 'decorativa', dormir: 'dormir' },
        },
      ],
      storefront_picker: {
        source: 'products',
        field: 'dimensoes',
        label: 'Tamanho',
        format: 'dimensions',
        suffix: ' cm',
      },
      storefront_badge: {
        field: 'tipo',
        labels: { decorativa: 'decorativa', dormir: 'dormir' },
      },
      storefront_specs: [
        { field: 'composicao', label: 'Composição', widget: 'composition', enum_labels: {} },
      ],
      order_picker_mode: 'variantes',
    },
    {
      tipo: 'assento',
      label: 'Assentos',
      model_table: 'modelos_assentos',
      product_table: 'assento',
      product_select: 'id, ean, barcode_url, visibilidade',
      storefront_mode: 'assento',
      storefront_filters: [],
      storefront_picker: {
        source: 'model',
        field: 'alturas',
        label: 'Variante',
        format: 'plain',
      },
      storefront_badge: null,
      storefront_specs: [
        { field: 'material_forro', label: 'Material do forro', widget: 'text', enum_labels: {} },
        { field: 'material_enchimento', label: 'Material do enchimento', widget: 'text', enum_labels: {} },
      ],
      order_picker_mode: 'assento',
    },
  ],
  category_definitions: {
    almofadas: { nome: 'Almofadas', tipo_catalogo: 'almofada', carrinho_step: 6, carrinho_min: 6 },
    assentos: { nome: 'Assentos', tipo_catalogo: 'assento', carrinho_step: 12, carrinho_min: 12 },
  },
}

export function getTipoConfig(tipo) {
  return CATALOG_META.catalog_types.find((t) => t.tipo === tipo) || null
}
