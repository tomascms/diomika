<script setup>
import { RouterLink } from 'vue-router'
import Breadcrumbs from '@/components/Breadcrumbs.vue'

const breadcrumbItems = [
  { label: 'Início', to: { name: 'home' } },
  { label: 'Sobre nós' },
]
</script>

<template>
  <div class="about-page">
    <Breadcrumbs :items="breadcrumbItems" />

    <section class="hero">
      <div class="page-shell hero-inner">
        <p class="eyebrow">Diomika</p>
        <h1>Catálogo B2B de almofadas e assentos</h1>
        <p>
          Facilitamos a consulta de modelos e variantes e o pedido de orçamento —
          sem preços no site, com resposta comercial directa.
        </p>
      </div>
    </section>

    <section class="page-shell section">
      <div class="intro">
        <h2>Quem somos</h2>
        <p>
          A Diomika é um catálogo online pensado para quem precisa de almofadas e assentos
          em contexto profissional: lojas, projectos de interiores, hotelaria ou revenda.
          Organizamos a oferta por categoria e modelo, com cores e variantes claras,
          para que o pedido de cotação seja simples e completo.
        </p>
        <p>
          Não vendemos com preço fixo no site. Cada pedido é analisado e responde-se
          com um orçamento adequado às quantidades e referências escolhidas.
        </p>
      </div>
    </section>

    <section class="band">
      <div class="page-shell section">
        <h2 class="center">O que encontra no catálogo</h2>
        <div class="cards">
          <article>
            <h3>Categorias e modelos</h3>
            <p>
              Navegue por categoria, abra cada modelo e veja as opções disponíveis
              antes de montar o pedido.
            </p>
          </article>
          <article>
            <h3>Cores e variantes</h3>
            <p>
              Em cada produto pode seleccionar cor e, quando existir, dimensão
              ou outra variante registada no catálogo.
            </p>
          </article>
          <article>
            <h3>Pedido de orçamento</h3>
            <p>
              Adicione linhas ao carrinho com quantidades válidas e envie o pedido
              com os seus dados de contacto.
            </p>
          </article>
        </div>
      </div>
    </section>

    <section class="page-shell section">
      <h2>Como funciona o orçamento</h2>
      <ol class="steps">
        <li>
          <strong>Escolha</strong>
          <span>Categoria → modelo → cor e variante.</span>
        </li>
        <li>
          <strong>Monte o pedido</strong>
          <span>Adicione quantidades ao carrinho (há mínimo de encomenda).</span>
        </li>
        <li>
          <strong>Envie</strong>
          <span>Preencha nome e email — opcionalmente telefone e notas.</span>
        </li>
        <li>
          <strong>Receba resposta</strong>
          <span>A equipa comercial contacta com a proposta.</span>
        </li>
      </ol>
      <p class="note">
        Preferir falar primeiro? Use o formulário de contacto — sem compromisso de encomenda.
      </p>
    </section>

    <section class="cta">
      <div class="page-shell cta-inner">
        <h2>Pronto a consultar o catálogo?</h2>
        <p>Explore as categorias ou peça já um orçamento.</p>
        <div class="actions">
          <RouterLink to="/categorias" class="btn btn-hero">Ver categorias</RouterLink>
          <RouterLink to="/contact" class="btn btn-hero-outline">Contactar</RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.about-page {
  background: #fff;
}

.hero {
  background: linear-gradient(155deg, #0b1f3a 0%, #1b365d 100%);
  color: #fff;
}

.hero-inner {
  padding-top: 2.75rem;
  padding-bottom: 3rem;
  max-width: 720px;
}

.eyebrow {
  margin: 0 0 0.65rem;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.8;
}

.hero h1 {
  margin: 0 0 1rem;
  color: #fff;
  font-size: clamp(2rem, 4vw, 2.85rem);
}

.hero p {
  margin: 0;
  font-size: 1.08rem;
  line-height: 1.55;
  opacity: 0.94;
  max-width: 38rem;
}

.section {
  padding-top: 3rem;
  padding-bottom: 3rem;
}

.intro {
  max-width: 40rem;
}

.intro h2,
.section > h2,
.band h2 {
  margin: 0 0 1rem;
  font-size: clamp(1.45rem, 2.5vw, 1.85rem);
  color: var(--color-ink-deep);
}

.intro p {
  margin: 0 0 1rem;
  color: var(--color-muted);
  line-height: 1.65;
  font-size: 1.05rem;
}

.intro p:last-child { margin-bottom: 0; }

.band {
  background: var(--color-bg);
}

.center { text-align: center; }

.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
  margin-top: 1.75rem;
}

.cards article {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  padding: 1.4rem 1.35rem;
}

.cards h3 {
  margin: 0 0 0.55rem;
  font-size: 1.1rem;
  color: var(--color-ink-deep);
}

.cards p {
  margin: 0;
  color: var(--color-muted);
  line-height: 1.55;
  font-size: 0.98rem;
}

.steps {
  list-style: none;
  margin: 1.25rem 0 1.5rem;
  padding: 0;
  display: grid;
  gap: 0.9rem;
  max-width: 40rem;
}

.steps li {
  display: grid;
  gap: 0.2rem;
  padding: 1rem 1.15rem;
  border-left: 3px solid var(--color-ink-deep);
  background: var(--color-bg);
  border-radius: 0 10px 10px 0;
}

.steps strong {
  color: var(--color-ink-deep);
  font-size: 1rem;
}

.steps span {
  color: var(--color-muted);
  line-height: 1.45;
}

.note {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.95rem;
}

.cta {
  background: linear-gradient(155deg, #0b1f3a 0%, #13294b 100%);
  color: #fff;
}

.cta-inner {
  text-align: center;
  padding-top: 3rem;
  padding-bottom: 3rem;
}

.cta h2 {
  margin: 0 0 0.6rem;
  color: #fff;
  font-size: clamp(1.6rem, 3vw, 2.1rem);
}

.cta p {
  margin: 0 auto 1.5rem;
  max-width: 28rem;
  opacity: 0.92;
}

.actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

@media (max-width: 860px) {
  .cards { grid-template-columns: 1fr; }
}
</style>
