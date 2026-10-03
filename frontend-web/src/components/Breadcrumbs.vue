<script setup>
defineProps({
  items: {
    type: Array,
    required: true,
  },
})
</script>

<template>
  <nav class="breadcrumbs" aria-label="Navegação">
    <div class="page-shell breadcrumbs-inner">
      <ol class="breadcrumb-list">
        <li v-for="(item, index) in items" :key="index" class="breadcrumb-item">
          <RouterLink v-if="item.to" :to="item.to">{{ item.label }}</RouterLink>
          <span v-else class="current">{{ item.label }}</span>
        </li>
      </ol>
    </div>
  </nav>
</template>

<style scoped>
.breadcrumbs {
  position: sticky;
  top: var(--header-h);
  z-index: 990;
  background: linear-gradient(
    180deg,
    var(--color-ink-deep) 0%,
    rgba(15, 23, 42, 0.98) 100%
  );
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  animation: slideDown 0.4s ease-out;
}

.breadcrumbs::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.1) 50%, transparent 100%);
  pointer-events: none;
}

.breadcrumbs-inner {
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  position: relative;
  z-index: 1;
}

.breadcrumb-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.breadcrumb-item {
  display: inline-flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.8);
  transition: color 0.2s ease;
}

.breadcrumb-item:not(:last-child)::after {
  content: '→';
  margin: 0 0.35rem;
  opacity: 0.5;
  font-size: 0.8rem;
}

.breadcrumb-item a {
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s ease;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  position: relative;
}

.breadcrumb-item a::after {
  content: '';
  position: absolute;
  bottom: 2px;
  left: 0.5rem;
  right: 0.5rem;
  height: 1px;
  background: rgba(255, 255, 255, 0.3);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.2s ease;
  pointer-events: none;
}

.breadcrumb-item a:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.breadcrumb-item a:hover::after {
  transform: scaleX(1);
}

.breadcrumb-item .current {
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.02em;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
