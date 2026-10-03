<script setup>
defineProps({
  message: { type: String, default: 'A carregar…' },
})
</script>

<template>
  <div class="loading-state" role="status" aria-live="polite">
    <div class="spinner" aria-hidden="true" />
    <p>{{ message }}</p>
  </div>
</template>

<style scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 3rem 2rem;
  min-height: 200px;
  animation: fadeIn 0.3s ease-out;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(59, 130, 246, 0.15);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.1);
}

.loading-state p {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
  color: var(--color-ink-soft);
  letter-spacing: 0.02em;
  animation: fadeInDelay 0.4s ease-out 0.1s both;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes fadeInDelay {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
