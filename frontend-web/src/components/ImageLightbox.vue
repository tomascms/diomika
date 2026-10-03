<script setup>
import { onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const onKey = (e) => {
  if (e.key === 'Escape') emit('close')
}

watch(
  () => props.open,
  (v) => {
    document.body.style.overflow = v ? 'hidden' : ''
  },
)

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && src"
      class="lightbox"
      role="dialog"
      aria-modal="true"
      :aria-label="alt || 'Ampliar imagem'"
      @click.self="emit('close')"
    >
      <button type="button" class="lightbox-close" aria-label="Fechar" @click="emit('close')">×</button>
      <img :src="src" :alt="alt" class="lightbox-img" />
    </div>
  </Teleport>
</template>

<style scoped>
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(8, 16, 28, 0.88);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  cursor: zoom-out;
  animation: backdropFadeIn 0.3s ease-out;
}

.lightbox-img {
  max-width: min(96vw, 1200px);
  max-height: 92vh;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: 12px;
  cursor: default;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.1);
  animation: imageZoomIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  transition: all var(--transition, 0.3s ease-out);
}

.lightbox-img:hover {
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.15);
}

.lightbox-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 1.6rem;
  line-height: 1;
  font-weight: 300;
  cursor: pointer;
  transition: all 0.2s ease-out;
  animation: closeButtonFadeIn 0.3s ease-out 0.1s both;
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-close:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  box-shadow: 0 8px 24px rgba(255, 255, 255, 0.15);
  transform: scale(1.1);
}

.lightbox-close:active {
  transform: scale(0.95);
}

@keyframes backdropFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes imageZoomIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes closeButtonFadeIn {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
