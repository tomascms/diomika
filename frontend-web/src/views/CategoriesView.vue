<script setup>
import { RouterLink } from 'vue-router'
import { useCategories } from '@/composables/useCategories'
import { categoryProductsRoute } from '@/lib/catalogRoutes'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import LoadingState from '@/components/LoadingState.vue'
import SoftImage from '@/components/SoftImage.vue'

const { categories, loading, error, load } = useCategories()

const pretty = (name) => {
  const t = String(name || '').trim()
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : ''
}

const breadcrumbItems = [
  { label: 'Início', to: { name: 'home' } },
  { label: 'Categorias' },
]
</script>

<template>
  <div class="min-h-screen bg-white">
    <Breadcrumbs :items="breadcrumbItems" />

    <!-- Hero Section -->
    <header class="bg-gradient-to-r from-slate-900 to-slate-800 text-white py-16 px-4">
      <div class="max-w-6xl mx-auto">
        <h1 class="text-4xl md:text-5xl font-bold mb-3">Categorias</h1>
        <p class="text-lg text-slate-300 max-w-2xl">Escolha uma categoria para ver os modelos e pedir orçamento.</p>
      </div>
    </header>

    <!-- Content -->
    <div class="max-w-6xl mx-auto px-4 py-12">
      <LoadingState v-if="loading" message="A carregar categorias…" />

      <div v-else-if="error" class="alert alert-error rounded-lg p-4 mb-6">
        <p class="text-red-700 mb-3">{{ error }}</p>
        <button type="button" class="btn btn-sm" @click="load(true)">Tentar novamente</button>
      </div>

      <!-- Grid de Categorias -->
      <div v-else-if="categories.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <RouterLink
          v-for="cat in categories"
          :key="cat.id"
          :to="categoryProductsRoute(cat)"
          class="group card bg-base-100 shadow-md hover:shadow-lg transition-all duration-300 overflow-hidden h-full"
        >
          <!-- Imagem -->
          <div class="w-full h-48 bg-gradient-to-br from-blue-900 to-slate-900 overflow-hidden flex items-center justify-center">
            <SoftImage
              v-if="cat.imagem"
              :src="cat.imagem"
              :alt="pretty(cat.nome)"
              img-class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
            <span v-else class="text-5xl font-bold text-white opacity-80">{{ pretty(cat.nome).charAt(0) || 'D' }}</span>
          </div>

          <!-- Corpo -->
          <div class="card-body p-5 flex flex-col justify-between flex-1">
            <h2 class="card-title text-lg font-semibold text-slate-900 truncate">{{ pretty(cat.nome) }}</h2>
            <div class="text-sm text-blue-600 font-medium group-hover:text-blue-700">Ver modelos →</div>
          </div>
        </RouterLink>
      </div>

      <!-- Vazio -->
      <div v-else class="card bg-base-100 shadow-sm p-12 text-center">
        <p class="text-slate-600 mb-4 text-lg">Sem categorias disponíveis.</p>
        <button type="button" class="btn btn-primary" @click="load(true)">Tentar novamente</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Estilos usando Tailwind CSS acima no template */
</style>
