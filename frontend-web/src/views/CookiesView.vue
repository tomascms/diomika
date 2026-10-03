<template>
  <div class="legal-page">
    <Breadcrumbs :items="breadcrumbItems" />
    <article class="legal-content">
      <h1>Política de Cookies</h1>
      <p class="updated">Última actualização: {{ new Date().getFullYear() }}</p>

      <section>
        <h2>O que são cookies</h2>
        <p>
          Cookies são pequenos ficheiros guardados no seu dispositivo para recordar preferências
          ou medir utilização do site.
        </p>
      </section>

      <section>
        <h2>Cookies que utilizamos</h2>
        <ul>
          <li><strong>Estritamente necessários</strong> — sessão do carrinho e preferência de consentimento.</li>
          <li><strong>Analytics (opcional)</strong> — PostHog, apenas se aceitar no banner.</li>
        </ul>
      </section>

      <section>
        <h2>Como gerir</h2>
        <p>
          Pode recusar cookies não essenciais no banner ao entrar no site. Para revogar analytics,
          limpe os dados do site no browser ou contacte-nos.
        </p>
      </section>

      <section>
        <h2>Mais informação</h2>
        <p>
          Consulte também a <RouterLink to="/privacidade">Política de Privacidade</RouterLink>.
        </p>
      </section>
    </article>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import Breadcrumbs from '@/components/Breadcrumbs.vue'

const breadcrumbItems = [
  { label: 'Início', to: { name: 'home' } },
  { label: 'Cookies' },
]
</script>

<style scoped>
.legal-page {
  padding-bottom: 3rem;
  background: #fff;
}

.legal-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 2.5rem var(--page-pad) 3.5rem;
  line-height: 1.8;
  animation: slideUp 0.6s ease-out;
}

.legal-content h1 {
  font-size: clamp(1.85rem, 3vw, 2.25rem);
  font-weight: 800;
  letter-spacing: -0.015em;
  margin: 0 0 0.75rem;
  color: var(--color-ink-deep);
}

.updated {
  color: var(--color-muted);
  font-size: 0.95rem;
  font-weight: 500;
  margin-bottom: 2.5rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

section {
  margin-bottom: 2.25rem;
  padding-bottom: 1.75rem;
  border-bottom: 1px solid rgba(59, 130, 246, 0.08);
  animation: slideUp 0.6s ease-out;
}

section:last-child {
  border-bottom: none;
}

section h2 {
  font-family: var(--font-body);
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  margin: 0 0 0.85rem;
  color: var(--color-ink-deep);
}

section p {
  margin: 0;
  color: var(--color-ink-soft);
  font-size: 0.99rem;
}

ul {
  margin: 0.75rem 0 0;
  padding-left: 1.5rem;
}

li {
  margin: 0.5rem 0;
  color: var(--color-ink-soft);
  font-size: 0.99rem;
}

strong {
  font-weight: 700;
  color: var(--color-ink-deep);
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
</style>
