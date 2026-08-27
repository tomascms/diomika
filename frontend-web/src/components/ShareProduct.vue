<script setup>
import { ref } from 'vue'
import { whatsappUrl } from '@/lib/constants'

const props = defineProps({ title: { type: String, default: 'Produto Diomika' }, url: { type: String, default: '' } })
const copied = ref(false)
const shareUrl = () => props.url || window.location.href
async function copyLink() {
  try {
    await navigator.clipboard.writeText(shareUrl())
    copied.value = true
    window.setTimeout(() => { copied.value = false }, 2000)
  } catch { copied.value = false }
}
const whatsappLink = () => whatsappUrl(`Veja este produto Diomika: ${props.title} — ${shareUrl()}`)
</script>
<template>
  <div class="share-product" aria-label="Partilhar produto">
    <button type="button" class="share-link" @click="copyLink">{{ copied ? 'Link copiado' : 'Copiar link' }}</button>
    <a class="share-link" :href="whatsappLink()" target="_blank" rel="noopener noreferrer">WhatsApp</a>
  </div>
</template>
<style scoped>
.share-product { display: flex; flex-wrap: wrap; gap: 0.55rem; }
.share-link { border: 1px solid var(--color-border); border-radius: var(--radius-pill); background: #fff; color: var(--color-ink-deep); padding: 0.42rem 0.8rem; font: inherit; font-size: 0.85rem; font-weight: 600; text-decoration: none; cursor: pointer; }
.share-link:hover { border-color: var(--color-ink-deep); }
</style>
