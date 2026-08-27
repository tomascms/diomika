<script setup>

import { ref, onMounted, onUnmounted, watch, computed } from 'vue'

import { ensureSupabase, supabaseConfigured, subscribeRealtime } from '@/lib/supabase'

import { resolveImageUrl, resolveImageUrls, PLACEHOLDER, safeCssUrl } from '@/lib/images'
import SoftImage from '@/components/SoftImage.vue'

import { watchDynamicTitle } from '@/composables/usePageMeta'

import Breadcrumbs from '@/components/Breadcrumbs.vue'

import LoadingState from '@/components/LoadingState.vue'

import { useRoute } from 'vue-router'

import { resolveCategoryParam } from '@/lib/catalogSupabase'

import { categoryProductsRoute, modelDetailRoute } from '@/lib/catalogRoutes'

import { apiGet } from '@/lib/api'

import { useCatalog } from '@/composables/useCatalog'



const catalog = useCatalog()



const products = ref([])

const loading = ref(true)

const error = ref(null)

const categoryData = ref(null)

const selectedFilters = ref({})
const localSearch = ref('')
const sortBy = ref('az')

const route = useRoute()



const breadcrumbItems = ref([{ label: 'Início', to: { name: 'home' } }])



const catalogTipo = computed(() => categoryData.value?.tipo_catalogo || '')

const filterDefs = computed(() => catalog.filterDefinitionsForTipo(catalogTipo.value))

const showFilters = computed(() => filterDefs.value.length > 0)

function blankFilters(defs = filterDefs.value) {
  const next = {}
  for (const def of defs || []) {
    if (def?.field) next[def.field] = ''
  }
  return next
}

function resetFilters() {
  selectedFilters.value = blankFilters()
  localSearch.value = ''
  sortBy.value = 'az'
}



const tipoLabel = (product) => catalog.badgeLabel(product, catalogTipo.value)



const heroImageUrl = computed(() => safeCssUrl(categoryData.value?.imagem) || '')



const coverImage = (product) => {
  const imgs = [product.imagem_capa, ...(product.galeria || [])].filter(Boolean)
  return imgs[product.currentImgIdx] || PLACEHOLDER
}

const hasGallery = (product) =>
  (product.galeria || []).length > 0 || (product._galleryPaths || []).length > 0



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
  if (Array.isArray(value)) { value.forEach((entry) => nestedEans(entry, found)); return found }
  for (const [key, entry] of Object.entries(value)) {
    if (key === 'ean' && entry != null) found.push(String(entry))
    else if (entry && typeof entry === 'object') nestedEans(entry, found)
  }
  return found
}

const displayedProducts = computed(() => {
  const q = localSearch.value.trim().toLocaleLowerCase('pt')
  const list = products.value.filter((product) => {
    if (!q) return true
    return [product.nome, product.slug, ...nestedEans(product)].filter(Boolean).join(' ').toLocaleLowerCase('pt').includes(q)
  })
  return [...list].sort((a, b) => {
    if (sortBy.value === 'za') return String(b.nome || '').localeCompare(String(a.nome || ''), 'pt')
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



const fetchProducts = async () => {

  try {

    loading.value = true

    error.value = null

    products.value = []

    categoryData.value = null



    if (!route.params.categorySlug) {

      loading.value = false

      return

    }



    await catalog.loadMeta()



    const cat = supabaseConfigured

      ? await resolveCategoryParam(route.params.categorySlug)

      : await apiGet(`/categorias/slug/${encodeURIComponent(route.params.categorySlug)}`)

    categoryData.value = {

      ...cat,

      imagem: await resolveImageUrl(cat.imagem, PLACEHOLDER),

    }



    breadcrumbItems.value = [

      { label: 'Início', to: { name: 'home' } },

      { label: categoryData.value.nome },

    ]



    const tipo = categoryData.value.tipo_catalogo

    if (!tipo) {

      throw new Error('Categoria sem tipo de catálogo.')

    }



    const models = await catalog.fetchCategoryModels(
      tipo,
      categoryData.value.id,
      showFilters.value ? selectedFilters.value : null,
    )



    if (!Array.isArray(models)) {

      products.value = []

      return

    }



    const visible = models.filter((m) => m && m.visibilidade !== false)

    // 1 request de assinatura em lote só para capas — galeria em background
    const prepared = visible.map((m) => {
      const cores = (m.modelo_cores || [])
        .filter((c) => c.visibilidade !== false)
        .sort((a, b) => a.numero - b.numero)
      const firstCor = cores[0] || {}
      return {
        model: m,
        coverPath: firstCor.imagem || '',
        galleryPaths: cores.slice(1).map((c) => c.imagem).filter(Boolean),
        colorCount: cores.length,
      }
    })

    const covers = await resolveImageUrls(prepared.map((p) => p.coverPath), PLACEHOLDER)

    products.value = prepared.map((p, i) => ({
      ...p.model,
      _tipo_catalogo: p.model._tipo_catalogo || tipo,
      imagem_capa: covers[i] || PLACEHOLDER,
      galeria: [],
      _galleryPaths: p.galleryPaths,
      currentImgIdx: 0,
      _colorCount: p.colorCount,
    }))

    // Galerias não bloqueiam o primeiro paint
    void hydrateGalleries(products.value)

  } catch (err) {

    error.value = 'Erro ao carregar produtos: ' + err.message

    console.error(err)

  } finally {

    loading.value = false

  }

}



async function hydrateGalleries(list) {
  const pending = (list || []).filter((p) => (p._galleryPaths || []).length && !(p.galeria || []).length)
  if (!pending.length) return
  const flat = pending.flatMap((p) => p._galleryPaths)
  const urls = await resolveImageUrls(flat, PLACEHOLDER)
  let offset = 0
  for (const product of pending) {
    const n = product._galleryPaths.length
    product.galeria = urls.slice(offset, offset + n).filter(Boolean)
    offset += n
  }
}

const prevImg = (e, product) => {
  e.preventDefault()
  e.stopPropagation()
  const imgs = [product.imagem_capa, ...(product.galeria || [])].filter((i) => i)
  if (imgs.length === 0) return
  product.currentImgIdx = (product.currentImgIdx - 1 + imgs.length) % imgs.length
}

const nextImg = (e, product) => {
  e.preventDefault()
  e.stopPropagation()
  const imgs = [product.imagem_capa, ...(product.galeria || [])].filter((i) => i)
  if (imgs.length === 0) return
  product.currentImgIdx = (product.currentImgIdx + 1) % imgs.length
}



let productsSubscription = null



watch(
  () => route.params.categorySlug,
  () => {
    resetFilters()
    fetchProducts()
  },
)

watch(
  filterDefs,
  (defs) => {
    const next = blankFilters(defs)
    let changed = false
    for (const field of Object.keys(next)) {
      if (!(field in selectedFilters.value) || selectedFilters.value[field] == null) {
        selectedFilters.value[field] = ''
        changed = true
      }
    }
    // Drop stale fields from previous category
    for (const field of Object.keys(selectedFilters.value)) {
      if (!(field in next)) {
        delete selectedFilters.value[field]
        changed = true
      }
    }
    if (changed && !Object.keys(next).length) selectedFilters.value = {}
  },
  { immediate: true },
)

watch(selectedFilters, fetchProducts, { deep: true })



onMounted(async () => {
  await fetchProducts()
  await catalog.loadMeta()
  if (supabaseConfigured) {
    const supabase = await ensureSupabase()
    if (!supabase) return
    const channel = supabase.channel('catalog_realtime')
    for (const table of catalog.realtimeTables()) {
      channel.on('postgres_changes', { event: '*', schema: 'public', table }, fetchProducts)
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
            @change="selectedFilters[filterDef.field] = $event.target.value"
          >
            <option
              v-for="opt in catalog.filterOptionsForField(filterDef)"
              :key="opt.value || 'all'"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <LoadingState v-if="loading" message="A carregar modelos…" />



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

            <button type="button" class="nav-btn" aria-label="Imagem anterior" @click="prevImg($event, product)">‹</button>

            <button type="button" class="nav-btn" aria-label="Próxima imagem" @click="nextImg($event, product)">›</button>

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

  display: flex;

  justify-content: space-between;

  align-items: center;

  opacity: 0;

  transition: opacity var(--transition);

  pointer-events: none;

}



.card-image-container:hover .carousel-nav {

  opacity: 1;

}



.nav-btn {

  pointer-events: auto;

  width: 2.25rem;

  height: 2.25rem;

  margin: 0 0.4rem;

  border: none;

  border-radius: var(--radius-pill);

  background: rgba(255, 255, 255, 0.88);

  color: var(--color-ink);

  font-size: 1.25rem;

  cursor: pointer;

  line-height: 1;

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

