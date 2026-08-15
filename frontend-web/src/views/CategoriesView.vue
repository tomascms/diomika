<script setup>
import { RouterLink } from 'vue-router'
import { useCategories } from '@/composables/useCategories'
import { categoryProductsRoute } from '@/lib/catalogRoutes'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import LoadingState from '@/components/LoadingState.vue'

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
  <div class="categories-page">
    <Breadcrumbs :items="breadcrumbItems" />

    <header class="page-hero">
      <div class="page-shell hero-inner">
        <h1>Categorias</h1>
        <p>Escolha uma categoria para ver os modelos e pedir orçamento.</p>
      </div>
    </header>

    <div class="page-shell">
      <LoadingState v-if="loading" message="A carregar categorias…" />
      <p v-else-if="error" class="alert alert-error">
        {{ error }}
        <button type="button" class="btn btn-secondary btn-retry" @click="load(true)">
          Tentar novamente
        </button>
      </p>

      <div v-else-if="categories.length" class="grid">
        <RouterLink
          v-for="cat in categories"
          :key="cat.id"
          :to="categoryProductsRoute(cat)"
          class="cat-card"
        >
          <div class="cat-media">
            <img
              v-if="cat.imagem"
              :src="cat.imagem"
              :alt="pretty(cat.nome)"
              class="cat-img"
              loading="lazy"
            />
            <span v-else class="cat-placeholder">{{ pretty(cat.nome).charAt(0) || 'D' }}</span>
          </div>
          <div class="cat-body">
            <h2>{{ pretty(cat.nome) }}</h2>
            <span class="cat-go">Ver modelos</span>
          </div>
        </RouterLink>
      </div>

      <div v-else class="empty-state-block surface-card">
        <p>Sem categorias disponíveis.</p>
        <button type="button" class="btn btn-secondary" @click="load(true)">Tentar novamente</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.categories-page {
  background: #fff;
  padding-bottom: 2.5rem;
}

.page-hero {
  background: linear-gradient(155deg, #0b1f3a 0%, #1b365d 100%);
  color: #fff;
}

.hero-inner {
  padding-top: 2.25rem;
  padding-bottom: 2.25rem;
}

.page-hero h1 {
  margin: 0 0 0.5rem;
  color: #fff;
  font-size: clamp(1.85rem, 3.5vw, 2.5rem);
}

.page-hero p {
  margin: 0;
  opacity: 0.92;
  max-width: 36rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1.25rem;
  padding-top: 0.25rem;
}

.cat-card {
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  overflow: hidden;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.cat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--color-border-strong);
}

.cat-media {
  aspect-ratio: 16 / 10;
  background: linear-gradient(145deg, #1b365d, #0b1f3a);
  overflow: hidden;
}

.cat-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s ease;
}

.cat-card:hover .cat-img {
  transform: scale(1.04);
}

.cat-placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 2.75rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
}

.cat-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.1rem 1.2rem;
}

.cat-body h2 {
  margin: 0;
  font-size: 1.2rem;
}

.cat-go {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--color-ink-deep);
  white-space: nowrap;
}
</style>
