<template>
  <div class="legal-page">
    <Breadcrumbs :items="breadcrumbItems" />
    <article class="legal-content">
      <h1>Política de Privacidade</h1>
      <p class="updated">Última actualização: {{ new Date().getFullYear() }}</p>

      <section>
        <h2>Responsável</h2>
        <p>
          A Diomika trata os dados pessoais recolhidos através deste site e do formulário de contacto
          para responder aos seus pedidos e gerir a relação comercial.
        </p>
      </section>

      <section>
        <h2>Dados que recolhemos</h2>
        <ul>
          <li>Nome</li>
          <li>Endereço de email</li>
          <li>Contacto telefónico</li>
          <li>Conteúdo da mensagem enviada</li>
        </ul>
      </section>

      <section>
        <h2>Finalidade e base legal</h2>
        <p>
          Os dados são utilizados para responder ao seu contacto e, quando aplicável, para a gestão de
          encomendas ou pedidos de informação. A base legal é o <strong>interesse legítimo</strong> e/ou
          a <strong>execução de diligências pré-contratuais</strong> a seu pedido.
        </p>
      </section>

      <section>
        <h2>Conservação</h2>
        <p>
          Conservamos os dados pelo tempo necessário para responder e acompanhar a conversa, ou enquanto
          existir interesse comercial legítimo, salvo obrigação legal em contrário.
        </p>
        <ul>
          <li>Mensagens de contacto: até 24 meses (depois são apagadas automaticamente)</li>
          <li>Pedidos de orçamento: até 24 meses em estados terminais</li>
          <li>Registos técnicos de auditoria interna: até 12 meses</li>
        </ul>
        <p>
          Pode pedir o apagamento dos seus dados através do
          <RouterLink to="/contact">formulário de contacto</RouterLink>
          (assunto: «Apagar os meus dados»). Tratamos o pedido após verificação de identidade.
        </p>
      </section>

      <section>
        <h2>Partilha com terceiros</h2>
        <p>
          Utilizamos fornecedores de alojamento e base de dados (Supabase), email (Gmail/SMTP) e, com o
          seu consentimento, analytics (PostHog) para melhorar o serviço. Não vendemos os seus dados.
        </p>
      </section>

      <section>
        <h2>Cookies e analytics</h2>
        <p>
          Utilizamos cookies estritamente necessários para o funcionamento do site. Analytics de produto
          (PostHog) só são activados se aceitar no banner de consentimento.
        </p>
      </section>

      <section>
        <h2>Os seus direitos</h2>
        <p>
          Pode solicitar acesso, rectificação, apagamento ou limitação do tratamento contactando-nos
          através do formulário de contacto ou do email indicado no site.
        </p>
      </section>

      <section>
        <h2>Contacto</h2>
        <p>
          Para questões sobre privacidade, use a página
          <RouterLink to="/contact">Contacte-nos</RouterLink>.
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
  { label: 'Privacidade' },
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
  margin: 0 0 1rem;
  color: var(--color-ink-soft);
  font-size: 0.99rem;
}

section p:last-child {
  margin-bottom: 0;
}

section strong {
  font-weight: 700;
  color: var(--color-ink-deep);
}

ul {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}

li {
  margin: 0.5rem 0;
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
