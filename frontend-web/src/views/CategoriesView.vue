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
            <SoftImage
              v-if="cat.imagem"
              :src="cat.imagem"
              :alt="pretty(cat.nome)"
              img-class="cat-img"
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
  padding-bottom: 3rem;
}

.page-hero {
  background:
    radial-gradient(ellipse 70% 80% at 85% 15%, rgba(27, 54, 93, 0.35), transparent 55%),
    radial-gradient(ellipse 50% 70% at 15% 85%, rgba(59, 130, 246, 0.12), transparent 50%),
    linear-gradient(155deg, #0b1f3a 0%, #1b365d 100%);
  color: #fff;
  position: relative;
  overflow: hidden;
  animation: fadeIn 0.6s ease-out;
}

.page-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(59, 130, 246, 0.08) 0%,
    transparent 50%,
    rgba(59, 130, 246, 0.04) 100%
  );
  pointer-events: none;
  z-index: 0;
}

.hero-inner {
  position: relative;
  z-index: 1;
  padding-top: 3rem;
  padding-bottom: 3rem;
}

.page-hero h1 {
  margin: 0 0 0.75rem;
  color: #fff;
  font-size: clamp(1.85rem, 3.5vw, 2.5rem);
  font-weight: 800;
  letter-spacing: -0.015em;
}

.page-hero p {
  margin: 0;
  opacity: 0.93;
  max-width: 40rem;
  font-size: 1.1rem;
  font-weight: 500;
  line-height: 1.6;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 1.5rem;
  padding-top: 0.5rem;
  animation: slideUp 0.6s ease-out;
}

.cat-card {
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
  border: 1px solid rgba(59, 130, 246, 0.08);
  transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.05);
}

.cat-card:hover {
  transform: translateY(-6px);
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 16px 48px rgba(59, 130, 246, 0.15);
}

.cat-media {
  aspect-ratio: 16 / 10;
  background: linear-gradient(145deg, #1b365d, #0b1f3a);
  overflow: hidden;
  position: relative;
}

.cat-media::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(59, 130, 246, 0.1) 0%,
    transparent 50%,
    rgba(59, 130, 246, 0.05) 100%
  );
  pointer-events: none;
  z-index: 1;
}

.cat-media :deep(.soft-image),
.cat-media :deep(.soft-image__img) {
  width: 100%;
  height: 100%;
}

.cat-media :deep(.soft-image__img) {
  object-fit: cover;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.cat-card:hover :deep(.soft-image__img) {
  transform: scale(1.05);
}

.cat-placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 2.75rem;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.9);
  z-index: 0;
}

.cat-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.3rem 1.4rem;
  background: linear-gradient(135deg, #fff 0%, rgba(59, 130, 246, 0.01) 100%);
}

.cat-body h2 {
  margin: 0;
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--color-ink-deep);
  letter-spacing: -0.01em;
}

.cat-go {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--color-ink-soft);
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
</style>
