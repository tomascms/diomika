<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import Breadcrumbs from '@/components/Breadcrumbs.vue'
import LoadingState from '@/components/LoadingState.vue'
import SoftImage from '@/components/SoftImage.vue'
import { useCatalog } from '@/composables/useCatalog'
import { watchDynamicTitle } from '@/composables/usePageMeta'
import { apiGet } from '@/lib/api'
import { resolveCategoryParam } from '@/lib/catalogSupabase'
import { modelDetailRoute } from '@/lib/catalogRoutes'
import { PLACEHOLDER, resolveImageUrl, resolveImageUrls, safeCssUrl } from '@/lib/images'
import { ensureSupabase, subscribeRealtime, supabaseConfigured } from '@/lib/supabase'

const route = useRoute()
const catalog = useCatalog()

const products = ref([])
const loading = ref(true)
const error = ref(null)
const categoryData = ref(null)
const selectedFilters = ref({})
const localSearch = ref('')
const sortBy = ref('az')
const breadcrumbItems = ref([{ label: 'Início', to: { name: 'home' } }])

const catalogTipo = computed(() => categoryData.value?.tipo_catalogo || '')
const filterDefs = computed(() => catalog.filterDefinitionsForTipo(catalogTipo.value) || [])
const heroImageUrl = computed(() => safeCssUrl(categoryData.value?.imagem) || '')
const tipoLabel = (product) => catalog.badgeLabel(product, catalogTipo.value)

let fetchSeq = 0
let productsSubscription = null

function blankFilters(defs = filterDefs.value) {
  return Object.fromEntries(
    (defs || []).filter((def) => def?.field).map((def) => [def.field, '']),
  )
}

function resetPageControls() {
  selectedFilters.value = {}
  localSearch.value = ''
  sortBy.value = 'az'
}

function onFilterChange(field, value) {
  selectedFilters.value = {
    ...selectedFilters.value,
    [field]: value ?? '',
  }
  void fetchProducts()
}

watchDynamicTitle(
  () => [categoryData.value?.nome, route.params.categorySlug],
  () => {
    const nome = categoryData.value?.nome
    if (!nome) return null
    return {
      title: nome,
      description: `Modelos ${nome} — explore variantes e peça orçamento online.`,
      image: categoryData.value?.imagem || PLACEHOLDER,
      path: route.fullPath,
    }
  },
)

function nestedEans(value, found = []) {
  if (!value || typeof value !== 'object') return found
  if (Array.isArray(value)) {
    value.forEach((entry) => nestedEans(entry, found))
    return found
  }
  for (const [key, entry] of Object.entries(value)) {
    if (key === 'ean' && entry != null) found.push(String(entry))
    else if (entry && typeof entry === 'object') nestedEans(entry, found)
  }
  return found
}

function foldText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLocaleLowerCase('pt')
}

function searchHaystack(product) {
  const cores = (product.modelo_cores || []).map((c) => c?.nome).filter(Boolean)
  const extras = [
    product.tipo,
    product.tipo_oculo,
    product.tipo_produto,
    product.material,
    product.subtipo,
    product._familia_label,
  ].filter(Boolean)
  return foldText([product.nome, product.slug, ...extras, ...cores, ...nestedEans(product)].join(' '))
}

function modelMatchesClientFilters(product, filters) {
  const entries = Object.entries(filters || {}).filter(([, v]) => String(v ?? '').trim())
  if (!entries.length) return true
  return entries.every(([field, value]) => {
    const wanted = String(value)
    if (String(product?.[field] ?? '') === wanted) return true
    if (field === '_tipo_catalogo' && String(product?._tipo_catalogo || '') === wanted) return true
    const pt =
      product?._storefront?.product_table ||
      catalog.storefrontContext(catalogTipo.value, product)?.product_table
    if (!pt) return false
    const rows = Array.isArray(product[pt]) ? product[pt] : product[pt] ? [product[pt]] : []
    return rows.some((row) => String(row?.[field] ?? '') === wanted)
  })
}

const displayedProducts = computed(() => {
  const query = foldText(localSearch.value.trim())
  const active = Object.fromEntries(
    Object.entries(selectedFilters.value || {}).filter(([, v]) => String(v ?? '').trim()),
  )
  const filtered = products.value.filter((product) => {
    if (!modelMatchesClientFilters(product, active)) return false
    if (!query) return true
    return searchHaystack(product).includes(query)
  })

  return [...filtered].sort((a, b) => {
    if (sortBy.value === 'za') {
      return String(b.nome || '').localeCompare(String(a.nome || ''), 'pt')
    }
    if (sortBy.value === 'recent') return Number(b.id || 0) - Number(a.id || 0)
    return String(a.nome || '').localeCompare(String(b.nome || ''), 'pt')
  })
})

const hasActiveFilters = computed(() =>
  Boolean(
    localSearch.value.trim() ||
      Object.values(selectedFilters.value).some((value) => String(value ?? '').trim()),
  ),
)

async function fetchProducts({ resetCategory = false } = {}) {
  const seq = ++fetchSeq
  const categorySlug = route.params.categorySlug

  loading.value = true
  error.value = null

  if (resetCategory) {
    categoryData.value = null
    products.value = []
    resetPageControls()
  }

  try {
    if (!categorySlug) return

    await catalog.loadMeta()
    if (seq !== fetchSeq) return

    let category = categoryData.value
    if (resetCategory || !category) {
      const rawCategory = supabaseConfigured
        ? await resolveCategoryParam(categorySlug)
        : await apiGet(`/categorias/slug/${encodeURIComponent(categorySlug)}`)
      if (seq !== fetchSeq) return

      category = {
        ...rawCategory,
        imagem: await resolveImageUrl(rawCategory.imagem, PLACEHOLDER),
      }
      if (seq !== fetchSeq) return

      categoryData.value = category
      breadcrumbItems.value = [
        { label: 'Início', to: { name: 'home' } },
        { label: category.nome },
      ]

      // Quiet initialization: every type filter starts visibly on "Todos".
      selectedFilters.value = blankFilters(
        catalog.filterDefinitionsForTipo(category.tipo_catalogo) || [],
      )
    }

    const tipo = category.tipo_catalogo
    if (!tipo) throw new Error('Categoria sem tipo de catálogo.')

    const filters = Object.fromEntries(
      Object.entries(selectedFilters.value || {}).filter(([, value]) => String(value ?? '').trim()),
    )
    const models = await catalog.fetchCategoryModels(
      tipo,
      category.id,
      Object.keys(filters).length ? filters : null,
    )
    if (seq !== fetchSeq) return

    const visible = Array.isArray(models)
      ? models.filter((model) => {
          if (!model || model.visibilidade === false) return false
          const pt = model._storefront?.product_table || catalog.storefrontContext(tipo, model)?.product_table
          if (!pt) return false
          const rows = Array.isArray(model[pt]) ? model[pt] : model[pt] ? [model[pt]] : []
          const hasEan = rows.some((p) => String(p?.ean || '').trim())
          const hasColor = (model.modelo_cores || []).some((c) => c && c.visibilidade !== false)
          return hasEan && hasColor
        })
      : []
    const prepared = visible.map((model) => {
      const cores = (model.modelo_cores || [])
        .filter((cor) => cor.visibilidade !== false)
        .sort((a, b) => a.numero - b.numero)
      return {
        model,
        coverPath: cores[0]?.imagem || '',
        galleryPaths: cores.slice(1).map((cor) => cor.imagem).filter(Boolean),
      }
    })

    const covers = await resolveImageUrls(
      prepared.map((entry) => entry.coverPath),
      PLACEHOLDER,
    )
    if (seq !== fetchSeq) return

    const nextProducts = prepared.map((entry, index) => ({
      ...entry.model,
      _tipo_catalogo: entry.model._tipo_catalogo || tipo,
      imagem_capa: covers[index] || PLACEHOLDER,
      galeria: [],
      _galleryPaths: entry.galleryPaths,
      currentImgIdx: 0,
    }))
    products.value = nextProducts
    void hydrateGalleries(nextProducts, seq)
  } catch (err) {
    if (seq !== fetchSeq) return
    error.value = `Erro ao carregar produtos: ${err.message}`
    console.error(err)
  } finally {
    if (seq === fetchSeq) loading.value = false
  }
}

async function hydrateGalleries(list, seq) {
  const pending = list.filter(
    (product) => (product._galleryPaths || []).length && !(product.galeria || []).length,
  )
  if (!pending.length) return

  const urls = await resolveImageUrls(
    pending.flatMap((product) => product._galleryPaths),
    PLACEHOLDER,
  )
  if (seq !== fetchSeq) return

  let offset = 0
  let changed = false
  for (const product of pending) {
    const count = product._galleryPaths.length
    const galeria = urls.slice(offset, offset + count).filter(Boolean)
    offset += count
    const live = products.value.find((row) => row.id === product.id)
    if (!live) continue
    live.galeria = galeria
    changed = true
  }
  // Garante re-render do SoftImage / setas após hydrate assíncrono
  if (changed) products.value = products.value.map((row) => ({ ...row }))
}

function galleryImages(product) {
  return [product.imagem_capa, ...(product.galeria || [])].filter(Boolean)
}

const hasGallery = (product) =>
  galleryImages(product).length > 1 || (product._galleryPaths || []).length > 0

const coverImage = (product) => {
  const images = galleryImages(product)
  if (!images.length) return PLACEHOLDER
  const idx = ((product.currentImgIdx || 0) % images.length + images.length) % images.length
  return images[idx] || PLACEHOLDER
}

const prevImg = (e, product) => {
  e.preventDefault()
  e.stopPropagation()
  const live = products.value.find((row) => row.id === product.id) || product
  const imgs = galleryImages(live)
  if (imgs.length < 2) return
  live.currentImgIdx = ((live.currentImgIdx || 0) - 1 + imgs.length) % imgs.length
}

const nextImg = (e, product) => {
  e.preventDefault()
  e.stopPropagation()
  const live = products.value.find((row) => row.id === product.id) || product
  const imgs = galleryImages(live)
  if (imgs.length < 2) return
  live.currentImgIdx = ((live.currentImgIdx || 0) + 1) % imgs.length
}



watch(
  () => route.params.categorySlug,
  () => void fetchProducts({ resetCategory: true }),
)
onMounted(async () => {
  await fetchProducts({ resetCategory: true })
  if (supabaseConfigured) {
    const supabase = await ensureSupabase()
    if (!supabase) return
    const channel = supabase.channel('catalog_realtime')
    for (const table of catalog.realtimeTables()) {
      channel.on('postgres_changes', { event: '*', schema: 'public', table }, () => {
        void fetchProducts()
      })
    }
    productsSubscription = subscribeRealtime(channel)
  }
})

onUnmounted(() => {
  if (productsSubscription && supabaseConfigured) {
    ensureSupabase().then((supabase) => {
      if (supabase) supabase.removeChannel(productsSubscription)
    })
  }
})

</script>



<template>

  <div class="products-page">

    <Breadcrumbs :items="breadcrumbItems" />



    <header

      v-if="categoryData"

      class="category-hero"

      :class="{ 'has-image': !!heroImageUrl }"

    >

      <img

        v-if="heroImageUrl"

        class="category-hero__img"

        :src="heroImageUrl"

        alt=""

        aria-hidden="true"
        decoding="async"
        fetchpriority="high"

      />

      <div class="page-shell page-shell--hero">

        <h1>{{ categoryData.nome }}</h1>

        <p v-if="!loading" class="category-count">{{ displayedProducts.length }} de {{ products.length }} modelos</p>

      </div>

    </header>



    <div v-if="categoryData" class="catalog-tools">
      <div class="page-shell tools-inner">
        <label class="tool-search">
          <span class="field-label">Pesquisar</span>
          <input v-model="localSearch" class="field-input" type="search" placeholder="Modelo ou EAN…" />
        </label>
        <label>
          <span class="field-label">Ordenar</span>
          <select v-model="sortBy" class="field-select">
            <option value="az">A–Z</option>
            <option value="za">Z–A</option>
            <option value="recent">Recentes</option>
          </select>
        </label>
        <label
          v-for="filterDef in filterDefs"
          :key="filterDef.field"
        >
          <span class="field-label">{{ filterDef.label }}</span>
          <select
            class="field-select"
            :value="selectedFilters[filterDef.field] ?? ''"
            @change="onFilterChange(filterDef.field, $event.target.value)"
          >
            <option value="">Todos</option>
            <option
              v-for="opt in catalog.filterOptionsForField(filterDef).filter((item) => item.value !== '')"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <LoadingState v-if="loading && !products.length" message="A carregar modelos…" />



    <p v-else-if="error" class="alert alert-error page-shell">{{ error }}</p>



    <div v-else-if="displayedProducts.length > 0" class="page-shell page-shell--grid product-grid">

      <RouterLink

        v-for="product in displayedProducts"

        :key="product.id"

        :to="modelDetailRoute(categoryData, product)"

        class="product-card surface-card surface-card--elevated"

      >

        <div class="card-image-container">

          <SoftImage
            :src="coverImage(product)"
            :alt="product.nome"
            img-class="cover-image"
          />

          <div v-if="hasGallery(product)" class="carousel-nav">
            <button
              type="button"
              class="nav-btn"
              aria-label="Imagem anterior"
              @click.prevent.stop="prevImg($event, product)"
            >‹</button>
            <button
              type="button"
              class="nav-btn"
              aria-label="Próxima imagem"
              @click.prevent.stop="nextImg($event, product)"
            >›</button>
          </div>

          <span v-if="tipoLabel(product)" class="type-chip">{{ tipoLabel(product) }}</span>

        </div>



        <div class="card-body">

          <h2>{{ product.nome }}</h2>

          <span class="card-link">Ver detalhes</span>

        </div>

      </RouterLink>

    </div>



    <div v-else class="page-shell page-shell--grid">

      <div class="empty-state-block surface-card empty-card">

        <h2>{{ hasActiveFilters ? 'Sem modelos para estes filtros' : 'Sem modelos nesta categoria' }}</h2>

        <p>{{ hasActiveFilters ? 'Ajuste a pesquisa ou os filtros para ver outros modelos.' : 'Ainda não existem modelos com produtos visíveis. Volte mais tarde ou escolha outra categoria.' }}</p>

        <RouterLink to="/categorias" class="btn btn-secondary">Ver categorias</RouterLink>

      </div>

    </div>

  </div>

</template>



<style scoped>

.products-page {

  padding-bottom: 2rem;

}



.category-hero {

  background: linear-gradient(165deg, #0b1f3a 0%, #1b365d 100%);

  color: #fff;

  position: relative;

  overflow: hidden;

}



.category-hero__img {

  position: absolute;

  inset: 0;

  width: 100%;

  height: 100%;

  object-fit: cover;

  z-index: 0;

}



.category-hero .page-shell {

  position: relative;

  z-index: 1;

  padding-top: 2rem;

  padding-bottom: 2rem;

}



.category-hero.has-image::before {

  content: '';

  position: absolute;

  inset: 0;

  z-index: 1;

  background: linear-gradient(90deg, rgba(11, 31, 58, 0.88), rgba(27, 54, 93, 0.4));

  pointer-events: none;

}



.category-hero h1 {

  margin: 0 0 0.35rem;

  font-size: clamp(1.75rem, 3.5vw, 2.4rem);

  color: #fff;

  text-transform: capitalize;

}



.category-count {

  margin: 0;

  opacity: 0.85;

  font-size: 0.95rem;

}



.filters-bar {

  background: var(--color-surface);

  border-bottom: 1px solid var(--color-border);

  padding: 1rem 0;

}



.filters-inner {

  display: flex;

  flex-wrap: wrap;

  align-items: flex-end;

  gap: 0.75rem 1rem;

}



.filter-select {

  min-width: min(100%, 220px);

  max-width: 320px;

  flex: 1 1 220px;

}



.catalog-tools { background: #fff; border-bottom: 1px solid var(--color-border); padding: 1rem 0; }
.tools-inner { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 0.8rem; }
.tools-inner label { flex: 0 1 220px; }
.tools-inner .tool-search { flex: 1 1 300px; }
.tools-inner .field-input, .tools-inner .field-select { width: 100%; }

.product-grid {

  display: grid;

  grid-template-columns: repeat(4, minmax(0, 1fr));

  gap: 1.1rem;

  justify-items: stretch;

}



@media (max-width: 1100px) {

  .product-grid {

    grid-template-columns: repeat(3, minmax(0, 1fr));

  }

}



@media (max-width: 800px) {

  .product-grid {

    grid-template-columns: repeat(2, minmax(0, 1fr));

  }

}



@media (max-width: 480px) {

  .product-grid {

    grid-template-columns: 1fr;

  }

}



.product-card {

  position: relative;

  text-decoration: none;

  color: inherit;

  overflow: hidden;

  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.35s ease;

}



.product-card:hover {

  transform: translateY(-4px);

  box-shadow: var(--shadow-lg);

}



.card-image-container {

  position: relative;

  aspect-ratio: 1;

  overflow: hidden;

  background: var(--color-cream-dark);

}



.cover-image {

  width: 100%;

  height: 100%;

  object-fit: cover;

  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);

}



.card-image-container :deep(.soft-image),
.card-image-container :deep(.soft-image__img) {
  width: 100%;
  height: 100%;
}

.card-image-container :deep(.soft-image__img) {
  object-fit: cover;
}

.product-card:hover :deep(.soft-image__img) {

  transform: scale(1.03);

}

.card-image-container :deep(.soft-image__img) {
  transition: opacity 0.4s ease, transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}



.type-chip {

  position: absolute;

  left: 0.75rem;

  bottom: 0.75rem;

  padding: 0.3rem 0.65rem;

  background: rgba(26, 37, 47, 0.78);

  color: #fff;

  border-radius: var(--radius-pill);

  font-size: 0.72rem;

  font-weight: 600;

  letter-spacing: 0.02em;

  backdrop-filter: blur(4px);

  z-index: 2;

}



.carousel-nav {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  justify-content: space-between;
  align-items: center;
  opacity: 0;
  transition: opacity var(--transition);
  pointer-events: none;
}

.card-image-container:hover .carousel-nav,
.card-image-container:focus-within .carousel-nav {
  opacity: 1;
}

.nav-btn {
  pointer-events: auto;
  z-index: 4;
  width: 2.25rem;
  height: 2.25rem;
  margin: 0 0.4rem;
  border: none;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.92);
  color: var(--color-ink);
  font-size: 1.25rem;
  cursor: pointer;
  line-height: 1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
}

@media (hover: none) {
  .carousel-nav {
    opacity: 1;
  }
}



.card-body {

  padding: 1rem 1.1rem 1.15rem;

}



.card-body h2 {

  margin: 0 0 0.35rem;

  font-size: 1.05rem;

  line-height: 1.25;

}



.card-link {

  font-size: 0.88rem;

  font-weight: 600;

  color: var(--color-accent);

}



.empty-card {

  padding: 2.5rem;

  text-align: center;

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 0.75rem;

  max-width: 480px;

  margin: 0 auto;

}



.empty-card h2 {

  margin: 0;

  font-size: 1.25rem;

}



.empty-card p {

  margin: 0;

  color: var(--color-muted);

  line-height: 1.5;

}

</style>

