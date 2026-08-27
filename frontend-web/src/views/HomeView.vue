<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useCategories } from '@/composables/useCategories'
import { categoryProductsRoute } from '@/lib/catalogRoutes'
import LoadingState from '@/components/LoadingState.vue'

const { categories, loading, error, load } = useCategories()

const pretty = (name) => {
  const t = String(name || '').trim()
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : ''
}

/** Pré-visualização curta — a lista completa vive em /categorias */
const previewCats = computed(() => categories.value.slice(0, 2))
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="page-shell hero-inner">
        <img src="/brand/logo.svg" alt="Diomika" class="hero-logo" width="320" height="57" fetchpriority="high" decoding="async" />
        <h1>Almofadas e assentos</h1>
        <p>Catálogo B2B — consulte modelos e peça orçamento online.</p>
        <div class="hero-actions">
          <RouterLink to="/categorias" class="btn btn-primary hero-cta">Ver categorias</RouterLink>
          <RouterLink to="/carrinho" class="btn btn-secondary hero-cta-alt">Pedir orçamento</RouterLink>
        </div>
      </div>
    </section>

    <section class="how-section">
      <div class="page-shell">
        <h2 class="section-title">Como pedir</h2>
        <ol class="steps">
          <li>
            <span class="step-n">1</span>
            <div>
              <strong>Escolha a categoria</strong>
              <p>Abra o catálogo e seleccione a gama que interessa.</p>
            </div>
          </li>
          <li>
            <span class="step-n">2</span>
            <div>
              <strong>Configure o modelo</strong>
              <p>Cor, variante e quantidade — sem preços no site.</p>
            </div>
          </li>
          <li>
            <span class="step-n">3</span>
            <div>
              <strong>Envie o orçamento</strong>
              <p>Recebe resposta comercial com a proposta.</p>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <section class="preview-section">
      <div class="page-shell">
        <div class="preview-head">
          <div>
            <h2 class="section-title">Destaques do catálogo</h2>
            <p class="section-lead">Uma amostra das categorias — veja a lista completa na página de categorias.</p>
          </div>
          <RouterLink to="/categorias" class="btn btn-secondary preview-all">Todas as categorias</RouterLink>
        </div>

        <LoadingState v-if="loading" message="A carregar…" />
        <p v-else-if="error" class="alert alert-error">
          {{ error }}
          <button type="button" class="btn btn-secondary btn-retry" @click="load(true)">
            Tentar novamente
          </button>
        </p>

        <div v-else-if="previewCats.length" class="preview-grid">
          <RouterLink
            v-for="cat in previewCats"
            :key="cat.id"
            :to="categoryProductsRoute(cat)"
            class="preview-card"
          >
            <div class="preview-media">
              <img
                v-if="cat.imagem"
                :src="cat.imagem"
                :alt="pretty(cat.nome)"
                loading="lazy"
                decoding="async"
                width="640"
                height="480"
              />
              <span v-else class="preview-ph">{{ pretty(cat.nome).charAt(0) || 'D' }}</span>
            </div>
            <div class="preview-body">
              <h3>{{ pretty(cat.nome) }}</h3>
              <span>Ver modelos</span>
            </div>
          </RouterLink>
        </div>

        <div v-else class="empty-state-block surface-card">
          <p>Sem categorias disponíveis.</p>
          <button type="button" class="btn btn-secondary" @click="load(true)">Tentar novamente</button>
        </div>
      </div>
    </section>

    <section class="cta-section">
      <div class="page-shell cta-inner">
        <h2>Precisa de ajuda a escolher?</h2>
        <p>Envie uma mensagem — respondemos com acompanhamento comercial.</p>
        <RouterLink to="/contact" class="btn btn-hero">Contactar</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse 70% 90% at 85% 10%, rgba(27, 54, 93, 0.18), transparent 55%),
    linear-gradient(165deg, #f3f6fa 0%, #dfe8f2 48%, #c9d7e8 100%);
  min-height: min(68vh, 560px);
  display: flex;
  align-items: center;
}

.hero-inner {
  position: relative;
  z-index: 1;
  padding-top: clamp(3rem, 9vw, 5.5rem);
  padding-bottom: clamp(3rem, 9vw, 5.5rem);
  text-align: center;
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}

.hero-logo {
  width: min(300px, 78vw);
  height: auto;
  margin: 0 auto 1.75rem;
}

.hero h1 {
  margin: 0 0 0.75rem;
  font-size: clamp(2.1rem, 5vw, 3.1rem);
  font-weight: 700;
  color: var(--color-ink-deep);
}

.hero p {
  margin: 0 auto 1.75rem;
  max-width: 28rem;
  font-size: 1.1rem;
  color: var(--color-muted);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.65rem;
}

.hero-cta,
.hero-cta-alt {
  padding: 0.85rem 1.5rem;
}

.how-section {
  background: #fff;
  padding: 0.5rem 0;
}

.section-title {
  text-align: left;
  margin: 0 0 0.5rem;
  font-size: clamp(1.45rem, 2.5vw, 1.85rem);
  color: var(--color-ink-deep);
}

.section-lead {
  margin: 0;
  color: var(--color-muted);
  font-size: 1.02rem;
  max-width: 36rem;
}

.steps {
  list-style: none;
  margin: 1.5rem 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.1rem;
}

.steps li {
  display: flex;
  gap: 0.85rem;
  padding: 1.2rem 1.15rem;
  background: var(--color-bg);
  border-radius: 12px;
  border: 1px solid var(--color-border);
}

.step-n {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  border-radius: 999px;
  background: var(--color-ink-deep);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 0.9rem;
}

.steps strong {
  display: block;
  margin-bottom: 0.25rem;
  color: var(--color-ink-deep);
}

.steps p {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.92rem;
  line-height: 1.45;
}

.preview-section {
  background: var(--color-bg);
  padding: 0.5rem 0 1rem;
}

.preview-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.preview-all {
  flex-shrink: 0;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.preview-card {
  text-decoration: none;
  color: inherit;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  overflow: hidden;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  min-height: 180px;
}

.preview-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

.preview-media {
  background: linear-gradient(145deg, #1b365d, #0b1f3a);
  min-height: 180px;
}

.preview-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-ph {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 2.5rem;
  font-weight: 700;
  color: #fff;
}

.preview-body {
  padding: 1.35rem 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.45rem;
}

.preview-body h3 {
  margin: 0;
  font-size: 1.35rem;
  color: var(--color-ink-deep);
}

.preview-body span {
  font-weight: 600;
  color: var(--color-ink-soft);
  font-size: 0.92rem;
}

.cta-section {
  background: linear-gradient(155deg, #0b1f3a 0%, #13294b 100%);
  color: #fff;
}

.cta-inner {
  text-align: center;
  padding-top: 3rem;
  padding-bottom: 3rem;
}

.cta-inner h2 {
  margin: 0 0 0.55rem;
  color: #fff;
  font-size: clamp(1.5rem, 3vw, 2rem);
}

.cta-inner p {
  margin: 0 auto 1.35rem;
  max-width: 28rem;
  opacity: 0.92;
}

@media (max-width: 900px) {
  .steps { grid-template-columns: 1fr; }
  .preview-grid { grid-template-columns: 1fr; }
  .preview-card { grid-template-columns: 1fr; }
  .preview-media { min-height: 160px; aspect-ratio: 16 / 9; }
}
</style>
