<script setup>
defineProps({
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
</script>

<template>
  <div class="list" role="list" :aria-busy="loading">
    <p v-if="loading" class="loading-banner">
      {{ rows.length ? 'A actualizar lista…' : 'A carregar registos…' }}
    </p>

    <template v-if="loading && !rows.length">
      <div v-for="n in 6" :key="`sk-${n}`" class="item skeleton" aria-hidden="true">
        <div class="item-body">
          <div class="sk-line sk-title" />
          <div class="sk-line sk-sub" />
        </div>
      </div>
    </template>

    <p v-else-if="!loading && !rows.length" class="empty">Sem registos.</p>

    <article v-for="row in rows" :key="row.id" class="item" role="listitem" :class="{ dimmed: loading }">
      <div class="item-body">
        <div class="title-row">
          <span
            v-if="variant === 'conversation'"
            class="status-pill"
            :class="{ unread: !row.lida }"
          >{{ row.lida ? 'Lida' : 'Nova' }}</span>
          <span
            v-else
            class="status-pill"
            :class="{ hidden: row.visibilidade === false }"
          >{{ row.visibilidade === false ? 'Rascunho' : 'Publicado' }}</span>
          <p class="title">{{ primary(row, columns) }}</p>
        </div>
        <p v-if="subtitle(row, columns)" class="sub">{{ subtitle(row, columns) }}</p>
      </div>
      <div class="actions">
        <button
          v-if="variant === 'conversation'"
          type="button"
          class="btn btn-ghost btn-sm"
          @click="$emit('toggle-read', row)"
        >
          {{ row.lida ? 'Marcar não lida' : 'Marcar lida' }}
        </button>
        <button
          v-else
          type="button"
          class="btn btn-ghost btn-sm"
          @click="$emit('toggle-visibility', row)"
        >
          {{ row.visibilidade === false ? 'Mostrar' : 'Ocultar' }}
        </button>
        <button type="button" class="btn btn-primary btn-sm" @click="$emit('open', row)">Abrir</button>
        <button type="button" class="btn btn-danger btn-sm" @click="$emit('delete', row)">Apagar</button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.list {
  display: grid;
  gap: 8px;
}

.loading-banner {
  margin: 0 0 8px 0;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius);
}

.item {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
  transition: all var(--transition);
}

.item.dimmed {
  opacity: 0.5;
  pointer-events: none;
}

.item:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.item-body {
  flex: 1;
  min-width: 200px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.title {
  margin: 0;
  font-weight: 600;
  font-size: 15px;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.sub {
  margin: 4px 0 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.status-pill {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--success-soft);
  color: var(--success);
}

.status-pill.hidden {
  background: var(--danger-soft);
  color: var(--danger);
}

.status-pill.unread {
  background: var(--accent-soft);
  color: var(--accent);
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  background: var(--surface);
  border: 2px dashed var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
}

.skeleton {
  pointer-events: none;
}

.sk-line {
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--surface-secondary) 50%, var(--bg-secondary) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

.sk-title {
  width: min(60%, 300px);
  height: 14px;
}

.sk-sub {
  width: min(40%, 200px);
  margin-top: 8px;
  opacity: 0.7;
}

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
