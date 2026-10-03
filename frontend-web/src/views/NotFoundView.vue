<template>
  <div class="not-found page-shell">
    <div class="not-found-card surface-card surface-card--elevated">
      <p class="code">404</p>
      <h1>Página não encontrada</h1>
      <p>O endereço que procurou não existe ou foi movido.</p>
      <div class="actions">
        <RouterLink to="/" class="btn btn-primary">Voltar ao início</RouterLink>
        <RouterLink to="/contact" class="btn btn-secondary">Contacto</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  padding-top: 4rem;
  padding-bottom: 5rem;
  min-height: 60vh;
  display: flex;
  align-items: center;
  background: #fff;
  animation: fadeIn 0.6s ease-out;
}

.not-found-card {
  max-width: 440px;
  margin: 0 auto;
  padding: 3rem 2.5rem;
  text-align: center;
  background: linear-gradient(135deg, #f8fafc 0%, #f0f4f8 100%);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.08);
  animation: slideUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.code {
  margin: 0 0 1rem;
  font-size: clamp(3rem, 8vw, 4.5rem);
  line-height: 1;
  font-weight: 800;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.8) 0%, rgba(27, 54, 93, 0.6) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
}

.not-found-card h1 {
  margin: 0 0 1rem;
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.015em;
  color: var(--color-ink-deep);
}

.not-found-card p {
  margin: 0 0 2rem;
  color: var(--color-muted);
  font-size: 1.05rem;
  font-weight: 500;
  line-height: 1.6;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
