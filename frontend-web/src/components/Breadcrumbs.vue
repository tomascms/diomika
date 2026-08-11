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
  background: var(--color-ink-deep);
}

.breadcrumbs-inner {
  padding-top: 0.65rem;
  padding-bottom: 0.65rem;
}

.breadcrumb-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.88rem;
}

.breadcrumb-item {
  display: inline-flex;
  align-items: center;
  color: rgba(255, 255, 255, 0.85);
}

.breadcrumb-item:not(:last-child)::after {
  content: '/';
  margin-left: 0.35rem;
  opacity: 0.6;
}

.breadcrumb-item a {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
}

.breadcrumb-item a:hover {
  text-decoration: underline;
}

.breadcrumb-item .current {
  color: #fff;
  font-weight: 600;
}
</style>
