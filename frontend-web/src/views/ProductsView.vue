<script setup>

import { ref, onMounted, onUnmounted, watch, computed } from 'vue'

import { supabase, supabaseConfigured, subscribeRealtime } from '@/lib/supabase'

import { resolveImageUrl, PLACEHOLDER, safeCssUrl } from '@/lib/images'

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

const route = useRoute()



const breadcrumbItems = ref([{ label: 'Início', to: { name: 'home' } }])



const catalogTipo = computed(() => categoryData.value?.tipo_catalogo || '')

const filterDefs = computed(() => catalog.filterDefinitionsForTipo(catalogTipo.value))

const showFilters = computed(() => filterDefs.value.length > 0)



const tipoLabel = (product) => catalog.badgeLabel(product, catalogTipo.value)



const heroImageUrl = computed(() => safeCssUrl(categoryData.value?.imagem) || '')



const coverImage = (product) => {

  const imgs = [product.imagem_capa, ...(product.galeria || [])].filter(Boolean)

  return imgs[product.currentImgIdx] || PLACEHOLDER

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



const colorCount = (product) => {

  const n = (product.modelo_cores || []).filter((c) => c.visibilidade !== false).length

  return n > 0 ? n : null

}



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

      imagem: await resolveImageUrl(cat.imagem, ''),

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

    products.value = await Promise.all(

      visible.map(async (m) => {

        const cores = (m.modelo_cores || []).filter((c) => c.visibilidade !== false)

        const firstCor = cores.sort((a, b) => a.numero - b.numero)[0] || {}

        const galeria = (

          await Promise.all(cores.slice(1).map((c) => resolveImageUrl(c.imagem, '')))

        ).filter(Boolean)

        return {

          ...m,

          _tipo_catalogo: m._tipo_catalogo || tipo,

          imagem_capa: await resolveImageUrl(firstCor.imagem, ''),

          galeria,

          currentImgIdx: 0,

          _colorCount: cores.length,

        }

      }),

    )

  } catch (err) {

    error.value = 'Erro ao carregar produtos: ' + err.message

    console.error(err)

  } finally {

    loading.value = false

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
    selectedFilters.value = {}
    fetchProducts()
  },
)

watch(selectedFilters, fetchProducts, { deep: true })



onMounted(async () => {

  await fetchProducts()



  await catalog.loadMeta()

  if (supabaseConfigured) {

    const channel = supabase.channel('catalog_realtime')

    for (const table of catalog.realtimeTables()) {

      channel.on('postgres_changes', { event: '*', schema: 'public', table }, fetchProducts)

    }

    productsSubscription = subscribeRealtime(channel)

  }

})



onUnmounted(() => {

  if (productsSubscription && supabaseConfigured) {

    supabase.removeChannel(productsSubscription)

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

      />

      <div class="page-shell page-shell--hero">

        <h1>{{ categoryData.nome }}</h1>

        <p v-if="!loading" class="category-count">{{ products.length }} modelos</p>

      </div>

    </header>



    <div v-if="categoryData && showFilters" class="filters-bar">
      <div class="page-shell page-shell--bar filters-inner filters-inner--multi">
        <div v-for="filterDef in filterDefs" :key="filterDef.field" class="filter-field">
          <label :for="`filter-${filterDef.field}`" class="field-label">{{ filterDef.label }}</label>
          <select
            :id="`filter-${filterDef.field}`"
            v-model="selectedFilters[filterDef.field]"
            class="field-select filter-select"
          >
            <option v-for="opt in catalog.filterOptionsForField(filterDef)" :key="opt.value || 'all'" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>
    </div>



    <LoadingState v-if="loading" message="A carregar modelos…" />



    <p v-else-if="error" class="alert alert-error page-shell">{{ error }}</p>



    <div v-else-if="products.length > 0" class="page-shell page-shell--grid product-grid">

      <RouterLink

        v-for="product in products"

        :key="product.id"

        :to="modelDetailRoute(categoryData, product)"

        class="product-card surface-card surface-card--elevated"

      >

        <span v-if="tipoLabel(product)" class="badge-pill badge-accent card-badge">

          {{ tipoLabel(product) }}

        </span>



        <div class="card-image-container">

          <img

            :src="coverImage(product)"

            :alt="product.nome"

            class="cover-image"

            loading="lazy"

          />

          <div v-if="product.galeria?.length" class="carousel-nav">

            <button type="button" class="nav-btn" aria-label="Imagem anterior" @click="prevImg($event, product)">‹</button>

            <button type="button" class="nav-btn" aria-label="Próxima imagem" @click="nextImg($event, product)">›</button>

          </div>

          <span v-if="colorCount(product)" class="color-count">{{ colorCount(product) }} cores</span>

        </div>



        <div class="card-body">

          <h2>{{ product.nome }}</h2>

          <span class="card-link">Ver detalhes</span>

        </div>

      </RouterLink>

    </div>



    <div v-else class="page-shell page-shell--grid">

      <div class="empty-state-block surface-card empty-card">

        <h2>Sem modelos nesta categoria</h2>

        <p>Ainda não existem modelos com produtos visíveis. Volte mais tarde ou escolha outra categoria.</p>

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

  transition: transform var(--transition), box-shadow var(--transition);

}



.product-card:hover {

  transform: translateY(-5px);

  box-shadow: var(--shadow-lg);

}



.card-badge {

  position: absolute;

  top: 0.75rem;

  right: 0.75rem;

  z-index: 2;

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

  transition: transform 0.35s ease;

}



.product-card:hover .cover-image {

  transform: scale(1.03);

}



.color-count {

  position: absolute;

  left: 0.75rem;

  bottom: 0.75rem;

  padding: 0.3rem 0.6rem;

  background: rgba(26, 37, 47, 0.78);

  color: #fff;

  border-radius: var(--radius-pill);

  font-size: 0.72rem;

  font-weight: 600;

  backdrop-filter: blur(4px);

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

