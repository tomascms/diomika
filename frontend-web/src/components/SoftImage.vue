<script setup>
import { ref, watch } from 'vue'
import { PLACEHOLDER } from '@/lib/images'

const props = defineProps({
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  eager: { type: Boolean, default: false },
  fetchpriority: { type: String, default: undefined },
  width: { type: [Number, String], default: undefined },
  height: { type: [Number, String], default: undefined },
  imgClass: { type: String, default: '' },
})

const loaded = ref(false)
const current = ref(props.src || PLACEHOLDER)

watch(
  () => props.src,
  (value) => {
    loaded.value = false
    current.value = value || PLACEHOLDER
  },
)

function onLoad() {
  loaded.value = true
}

function onError() {
  // Só fallback se ainda não for placeholder — evita loops
  if (current.value && !String(current.value).includes('placeholder')) {
    current.value = PLACEHOLDER
    loaded.value = true
  }
}
</script>

<template>
  <span class="soft-image" :class="{ 'is-loaded': loaded }">
    <span class="soft-image__skeleton" aria-hidden="true" />
    <img
      :src="current"
      :alt="alt"
      :class="['soft-image__img', imgClass]"
      :loading="eager ? 'eager' : 'lazy'"
      :fetchpriority="fetchpriority"
      :width="width"
      :height="height"
      decoding="async"
      @load="onLoad"
      @error="onError"
    />
  </span>
</template>

<style scoped>
.soft-image {
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(120deg, #eef2f6 25%, #e2e8f0 37%, #eef2f6 63%);
  background-size: 200% 100%;
  animation: soft-shimmer 1.1s ease-in-out infinite;
}

.soft-image.is-loaded {
  animation: none;
  background: transparent;
}

.soft-image__skeleton {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.soft-image__img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.4s ease;
}

.soft-image.is-loaded .soft-image__img {
  opacity: 1;
}

@keyframes soft-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .soft-image {
    animation: none;
  }
  .soft-image__img {
    transition: none;
    transform: none;
    opacity: 1;
  }
}
</style>
