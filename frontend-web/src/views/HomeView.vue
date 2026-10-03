<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useCategories } from '@/composables/useCategories'
import { categoryProductsRoute } from '@/lib/catalogRoutes'
import LoadingState from '@/components/LoadingState.vue'
import SoftImage from '@/components/SoftImage.vue'

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
              <SoftImage
                v-if="cat.imagem"
                :src="cat.imagem"
                :alt="pretty(cat.nome)"
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
    radial-gradient(ellipse 70% 90% at 85% 10%, rgba(27, 54, 93, 0.25), transparent 55%),
    radial-gradient(ellipse 60% 80% at 10% 90%, rgba(59, 130, 246, 0.15), transparent 50%),
    linear-gradient(165deg, #f3f6fa 0%, #dfe8f2 48%, #c9d7e8 100%);
  min-height: min(68vh, 560px);
  display: flex;
  align-items: center;
  animation: fadeIn 0.6s ease-out;
}

.hero::before {
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
  margin: 0 auto 2rem;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.05));
}

.hero h1 {
  margin: 0 0 0.85rem;
  font-size: clamp(2.1rem, 5vw, 3.3rem);
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--color-ink-deep);
}

.hero p {
  margin: 0 auto 2rem;
  max-width: 28rem;
  font-size: 1.15rem;
  font-weight: 500;
  color: var(--color-muted);
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.85rem;
  animation: slideUp 0.6s ease-out 0.2s both;
}

.hero-cta,
.hero-cta-alt {
  padding: 0.95rem 2rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 0.9rem;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.how-section {
  background: #fff;
  padding: 0.5rem 0;
}

.section-title {
  text-align: left;
  margin: 0 0 0.75rem;
  font-size: clamp(1.45rem, 2.5vw, 2rem);
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--color-ink-deep);
}

.section-lead {
  margin: 0;
  color: var(--color-muted);
  font-size: 1.05rem;
  line-height: 1.6;
  max-width: 36rem;
}

.steps {
  list-style: none;
  margin: 2rem 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}

.steps li {
  display: flex;
  gap: 1rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, #f8fafc 0%, #f0f4f8 100%);
  border-radius: 12px;
  border: 1px solid rgba(59, 130, 246, 0.1);
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  animation: slideUp 0.4s ease-out;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.05);
}

.steps li:hover {
  transform: translateY(-4px);
  border-color: rgba(59, 130, 246, 0.3);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.15);
  background: linear-gradient(135deg, #f0f4f8 0%, #e8ecf2 100%);
}

.step-n {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 999px;
  background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 1.1rem;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.steps strong {
  display: block;
  margin-bottom: 0.35rem;
  color: var(--color-ink-deep);
  font-weight: 700;
  font-size: 1rem;
}

.steps p {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.95rem;
  line-height: 1.6;
}

.preview-section {
  background: var(--color-bg);
  padding: 3rem 0 4rem;
}

.preview-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 2.5rem;
}

.preview-all {
  flex-shrink: 0;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
  animation: slideUp 0.6s ease-out;
}

.preview-card {
  text-decoration: none;
  color: inherit;
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  background: #fff;
  border: 1px solid rgba(59, 130, 246, 0.08);
  border-radius: 14px;
  overflow: hidden;
  transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  min-height: 180px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.05);
}

.preview-card:hover {
  transform: translateY(-6px);
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 16px 48px rgba(59, 130, 246, 0.15);
}

.preview-media {
  background: linear-gradient(145deg, #1b365d, #0b1f3a);
  min-height: 180px;
  position: relative;
  overflow: hidden;
}

.preview-media::after {
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
}

.preview-media :deep(.soft-image),
.preview-media :deep(.soft-image__img) {
  width: 100%;
  height: 100%;
  min-height: 180px;
}

.preview-media :deep(.soft-image__img) {
  object-fit: cover;
}

.preview-ph {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  font-size: 2.5rem;
  font-weight: 800;
  color: #fff;
}

.preview-body {
  padding: 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.5rem;
  background: linear-gradient(135deg, #fff 0%, rgba(59, 130, 246, 0.01) 100%);
}

.preview-body h3 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--color-ink-deep);
  letter-spacing: -0.01em;
}

.preview-body span {
  font-weight: 600;
  color: var(--color-ink-soft);
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cta-section {
  background: linear-gradient(155deg, #0b1f3a 0%, #13294b 100%);
  color: #fff;
  position: relative;
  overflow: hidden;
}

.cta-section::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 100% at 50% 100%, rgba(59, 130, 246, 0.12), transparent 60%),
    radial-gradient(ellipse 50% 80% at 50% 0%, rgba(59, 130, 246, 0.08), transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.cta-inner {
  position: relative;
  z-index: 1;
  text-align: center;
  padding-top: 4rem;
  padding-bottom: 4rem;
  animation: slideUp 0.6s ease-out 0.2s both;
}

.cta-inner h2 {
  margin: 0 0 0.85rem;
  color: #fff;
  font-size: clamp(1.5rem, 3vw, 2.2rem);
  font-weight: 800;
  letter-spacing: -0.01em;
}

.cta-inner p {
  margin: 0 auto 2.2rem;
  max-width: 32rem;
  font-size: 1.15rem;
  font-weight: 500;
  opacity: 0.95;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .steps { grid-template-columns: 1fr; }

  .preview-grid { grid-template-columns: 1fr; }

  .preview-card {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .preview-media {
    min-height: 160px;
    aspect-ratio: 16 / 9;
  }
}
</style>
