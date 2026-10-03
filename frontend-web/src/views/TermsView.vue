<template>
  <div class="legal-page">
    <Breadcrumbs :items="breadcrumbItems" />
    <article class="legal-content">
      <h1>Aviso Legal</h1>
      <p class="updated">Última actualização: {{ new Date().getFullYear() }}</p>

      <section>
        <h2>Identificação</h2>
        <p>
          Este site é operado pela Diomika. Para dados de contacto comercial, consulte a página
          <RouterLink to="/contacto">Contacto</RouterLink>.
        </p>
      </section>

      <section>
        <h2>Objecto do site</h2>
        <p>
          O site destina-se à apresentação do catálogo B2B e à recepção de pedidos de orçamento.
          A informação publicada tem carácter informativo e pode ser alterada sem aviso prévio.
        </p>
      </section>

      <section>
        <h2>Propriedade intelectual</h2>
        <p>
          Textos, imagens, logótipos e design são propriedade da Diomika ou dos respectivos titulares.
          É proibida a reprodução sem autorização escrita.
        </p>
      </section>

      <section>
        <h2>Responsabilidade</h2>
        <p>
          A Diomika esforça-se por manter informação correcta, mas não garante a ausência de erros
          tipográficos ou indisponibilidade temporária do serviço.
        </p>
      </section>

      <section>
        <h2>Legislação aplicável</h2>
        <p>Lei portuguesa. Foro competente: Portugal.</p>
      </section>
    </article>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import Breadcrumbs from '@/components/Breadcrumbs.vue'

const breadcrumbItems = [
  { label: 'Início', to: { name: 'home' } },
  { label: 'Aviso legal' },
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
