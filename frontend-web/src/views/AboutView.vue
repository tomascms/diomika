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
.about-page { background: #fff; }
.hero { background: linear-gradient(155deg, #0b1f3a 0%, #1b365d 100%); color: #fff; }
.hero-inner { padding-top: 3rem; padding-bottom: 3rem; max-width: 780px; }
.eyebrow { margin: 0 0 0.65rem; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.8; }
.hero h1 { margin: 0 0 1rem; color: #fff; font-size: clamp(2rem, 4vw, 2.85rem); }
.hero p { margin: 0; font-size: 1.08rem; line-height: 1.6; opacity: 0.94; }
.section { padding-top: 3rem; padding-bottom: 3rem; }
.intro { max-width: 760px; }
h2 { color: var(--color-ink-deep); }
.intro p, .contact-section p { color: var(--color-muted); line-height: 1.65; font-size: 1.03rem; }
.band { background: var(--color-bg); }
.center { text-align: center; }
.steps { list-style: none; margin: 1.75rem 0 0; padding: 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.steps li { display: flex; flex-direction: column; gap: 0.45rem; padding: 1.3rem; background: #fff; border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.steps b { display: grid; place-items: center; width: 2rem; height: 2rem; border-radius: 50%; background: var(--color-ink-deep); color: #fff; }
.steps strong { color: var(--color-ink-deep); }
.steps span { color: var(--color-muted); line-height: 1.5; }
.actions { display: flex; flex-wrap: wrap; gap: 0.7rem; margin-top: 1.25rem; }
@media (max-width: 900px) { .steps { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 520px) { .steps { grid-template-columns: 1fr; } }
</style>
