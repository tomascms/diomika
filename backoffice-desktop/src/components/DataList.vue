<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  variant: { type: String, default: 'catalog' },
})
defineEmits(['open', 'toggle-visibility', 'toggle-read', 'delete'])

const primary = (row, columns) => {
  const col = columns[0]
  if (!col) return '—'
  return col.format ? col.format(row) : row[col.key] ?? '—'
}

const subtitle = (row, columns) => {
  if (columns.length < 2) return ''
  const col = columns[1]
  const value = col.format ? col.format(row) : row[col.key] ?? ''
  const main = String(primary(row, columns) ?? '').trim().toLowerCase()
  const sub = String(value ?? '').trim()
  if (!sub) return ''
  if (sub.toLowerCase() === main) return ''
  return sub
}

const hoverRowId = ref(null)
const ITEMS_PER_PAGE = 40
const page = ref(0)

const paginatedRows = computed(() => {
  const start = page.value * ITEMS_PER_PAGE
  return props.rows.slice(start, start + ITEMS_PER_PAGE)
})

const totalPages = computed(() => Math.ceil(props.rows.length / ITEMS_PER_PAGE))
const canLoadMore = computed(() => page.value < totalPages.value - 1)

const loadMore = () => {
  if (canLoadMore.value) page.value++
}
</script>

<template>
  <div class="list-wrapper">
    <p v-if="loading && !rows.length" class="loading-banner">
      {{ 'A carregar registos…' }}
    </p>

    <template v-if="loading && !rows.length">
      <div v-for="n in 6" :key="`sk-${n}`" class="item skeleton">
        <div class="item-body">
          <div class="sk-line sk-title" />
          <div class="sk-line sk-sub" />
        </div>
      </div>
    </template>

    <div v-else-if="!loading && !rows.length" class="empty">Sem registos.</div>

    <div v-else class="list" role="list" :aria-busy="loading">
      <article
        v-for="row in paginatedRows"
        :key="row.id"
        class="item"
        role="listitem"
        @mouseenter="hoverRowId = row.id"
        @mouseleave="hoverRowId = null"
      >
        <div class="item-left">
          <span class="status-indicator" :class="variant === 'conversation' ? (row.lida ? 'read' : 'unread') : (row.visibilidade === false ? 'hidden' : 'visible')" />
          <div class="item-body">
            <p class="title">{{ primary(row, columns) }}</p>
            <p v-if="subtitle(row, columns)" class="sub">{{ subtitle(row, columns) }}</p>
          </div>
        </div>
        <div v-if="hoverRowId === row.id" class="item-actions">
          <button type="button" class="action-btn" title="Abrir" @click.stop="$emit('open', row)">✎</button>
          <button
            type="button"
            class="action-btn"
            :title="variant === 'conversation' ? (row.lida ? 'Marcar não lida' : 'Marcar lida') : (row.visibilidade === false ? 'Mostrar' : 'Ocultar')"
            @click.stop="variant === 'conversation' ? $emit('toggle-read', row) : $emit('toggle-visibility', row)"
          >
            {{ variant === 'conversation' ? (row.lida ? '◇' : '●') : (row.visibilidade === false ? '✓' : '○') }}
          </button>
          <button type="button" class="action-btn danger" title="Apagar" @click.stop="$emit('delete', row)">✕</button>
        </div>
      </article>
    </div>

    <div v-if="!loading && rows.length > ITEMS_PER_PAGE" class="pagination">
      <p class="page-info">{{ page * ITEMS_PER_PAGE + 1 }}–{{ Math.min((page + 1) * ITEMS_PER_PAGE, rows.length) }} de {{ rows.length }}</p>
      <button v-if="canLoadMore" type="button" class="btn-load-more" @click="loadMore">Carregar mais</button>
    </div>
  </div>
</template>

<style scoped>
.list-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.loading-banner {
  margin: 0;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-md);
}

.item {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: var(--surface);
  cursor: pointer;
  transition: background-color 150ms ease;
  min-height: 50px;
  overflow: hidden;
}

.item:hover {
  background: var(--bg-secondary);
}

.item-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--text-secondary);
}

.status-indicator.visible {
  background: var(--success);
}

.status-indicator.hidden {
  background: var(--danger);
}

.status-indicator.read {
  background: var(--success);
}

.status-indicator.unread {
  background: var(--accent);
}

.item-body {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.title {
  margin: 0;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub {
  margin: 2px 0 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 150ms ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.action-btn:hover {
  background: var(--bg-secondary);
  color: var(--accent);
}

.action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger);
}

.empty {
  padding: 60px 20px;
  text-align: center;
  color: var(--text-muted);
  background: var(--surface);
  border: 2px dashed var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
}

.skeleton {
  padding: 12px 16px;
  background: var(--surface);
  display: flex;
  gap: 12px;
}

.sk-line {
  height: 12px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--surface-secondary) 50%, var(--bg-secondary) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

.sk-title {
  flex: 1;
  width: 100%;
  height: 14px;
}

.sk-sub {
  flex: 1;
  width: 60%;
  opacity: 0.7;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}

.page-info {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
}

.btn-load-more {
  padding: 8px 16px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--accent);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
}

.btn-load-more:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
}

@keyframes shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
</style>
