<script setup>
import { RouterLink } from 'vue-router'
import Breadcrumbs from '@/components/Breadcrumbs.vue'
import { COMPANY, whatsappUrl } from '@/lib/constants'
const breadcrumbItems = [{ label: 'Início', to: { name: 'home' } }, { label: 'Sobre nós' }]
</script>
<template>
  <div class="about-page">
    <Breadcrumbs :items="breadcrumbItems" />
    <section class="hero"><div class="page-shell hero-inner"><p class="eyebrow">Diomika</p><h1>Um catálogo B2B pensado para profissionais</h1><p>Reunimos artigos têxteis, utilidades, acessórios e outras linhas para revenda, hotelaria, decoração e projetos profissionais.</p></div></section>
    <section class="page-shell section"><div class="intro"><h2>Quem somos</h2><p>A Diomika organiza uma oferta diversificada por categorias, modelos, cores e variantes para tornar cada consulta comercial simples e completa.</p><p>O site não apresenta preços fixos: analisamos referências, quantidades e necessidades de entrega para preparar uma proposta adequada a cada cliente.</p></div></section>
    <section class="band"><div class="page-shell section"><h2 class="center">Como funciona</h2><ol class="steps"><li><b>1</b><strong>Explore</strong><span>Consulte categorias e pesquise modelos ou EAN.</span></li><li><b>2</b><strong>Escolha</strong><span>Selecione cores, variantes e quantidades.</span></li><li><b>3</b><strong>Envie</strong><span>Reveja o pedido e indique os seus dados.</span></li><li><b>4</b><strong>Receba a proposta</strong><span>Respondemos comercialmente no prazo de 1 dia útil.</span></li></ol></div></section>
    <section class="page-shell section contact-section"><h2>Fale diretamente connosco</h2><p>Estamos disponíveis para esclarecer referências, mínimos e condições comerciais.</p><div class="actions"><a class="btn btn-primary" :href="whatsappUrl('Olá! Gostaria de conhecer melhor o catálogo B2B Diomika.')" target="_blank" rel="noopener noreferrer">WhatsApp</a><a class="btn btn-secondary" :href="`tel:${COMPANY.phoneTel}`">Ligar {{ COMPANY.phoneDisplay }}</a><RouterLink class="btn btn-secondary" to="/categorias">Ver catálogo</RouterLink></div></section>
  </div>
</template>
<style scoped>
.about-page {
  background: #fff;
}

.hero {
  background:
    radial-gradient(ellipse 70% 80% at 85% 15%, rgba(27, 54, 93, 0.35), transparent 55%),
    radial-gradient(ellipse 50% 70% at 15% 85%, rgba(59, 130, 246, 0.12), transparent 50%),
    linear-gradient(155deg, #0b1f3a 0%, #1b365d 100%);
  color: #fff;
  position: relative;
  overflow: hidden;
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
  padding-top: 4rem;
  padding-bottom: 4rem;
  max-width: 780px;
}

.eyebrow {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.85;
}

.hero h1 {
  margin: 0 0 1.2rem;
  color: #fff;
  font-size: clamp(2rem, 4vw, 2.85rem);
  font-weight: 800;
  letter-spacing: -0.015em;
}

.hero p {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 500;
  line-height: 1.6;
  opacity: 0.95;
}

.section {
  padding-top: 3.5rem;
  padding-bottom: 3.5rem;
}

.intro {
  max-width: 760px;
}

h2 {
  margin: 0 0 1rem;
  color: var(--color-ink-deep);
  font-size: clamp(1.5rem, 2.5vw, 2rem);
  font-weight: 800;
  letter-spacing: -0.01em;
}

.intro p,
.contact-section p {
  color: var(--color-muted);
  line-height: 1.7;
  font-size: 1.05rem;
  font-weight: 500;
  margin: 0 0 1rem;
}

.band {
  background: var(--color-bg);
}

.center {
  text-align: center;
}

.steps {
  list-style: none;
  margin: 2rem 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.25rem;
  animation: slideUp 0.6s ease-out 0.1s both;
}

.steps li {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1.5rem;
  background: #fff;
  border: 1px solid rgba(59, 130, 246, 0.08);
  border-radius: var(--radius-md);
  transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.05);
}

.steps li:hover {
  transform: translateY(-4px);
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 12px 32px rgba(59, 130, 246, 0.12);
}

.steps b {
  display: grid;
  place-items: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-ink-deep) 0%, rgba(59, 130, 246, 0.8) 100%);
  color: #fff;
  font-weight: 800;
  font-size: 1rem;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.steps strong {
  color: var(--color-ink-deep);
  font-weight: 700;
  font-size: 1rem;
}

.steps span {
  color: var(--color-muted);
  line-height: 1.5;
  font-size: 0.95rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.5rem;
  justify-content: center;
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

@media (max-width: 900px) {
  .steps {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .steps {
    grid-template-columns: 1fr;
  }
}
</style>
