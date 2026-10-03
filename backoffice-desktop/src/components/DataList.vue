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
  gap: 10px;
}

.loading-banner {
  margin: 0 0 12px 0;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: var(--accent);
  background: linear-gradient(135deg, var(--accent-soft) 0%, rgba(59, 130, 246, 0.04) 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-md);
  animation: slideDown 0.3s ease-out;
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
  animation: slideUp 0.3s ease-out;
  position: relative;
  overflow: hidden;
}

.item::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.05) 50%, transparent 100%);
  transition: left var(--transition-slow);
  pointer-events: none;
}

.item.dimmed {
  opacity: 0.5;
  pointer-events: none;
}

.item:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.item:hover::before {
  left: 100%;
}

.item-body {
  flex: 1;
  min-width: 200px;
  position: relative;
  z-index: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.title {
  margin: 0;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  transition: color var(--transition);
}

.item:hover .title {
  color: var(--accent);
}

.sub {
  margin: 6px 0 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  transition: color var(--transition);
}

.item:hover .sub {
  color: var(--text-primary);
}

.status-pill {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  padding: 5px 10px;
  border-radius: 6px;
  background: var(--success-soft);
  color: var(--success);
  transition: all var(--transition-fast);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.status-pill:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 4px rgba(16, 185, 129, 0.15);
}

.status-pill.hidden {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.2);
}

.status-pill.unread {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: rgba(59, 130, 246, 0.2);
  animation: pulse 2s ease-in-out infinite;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  position: relative;
  z-index: 2;
}

.empty {
  padding: 48px 28px;
  text-align: center;
  color: var(--text-muted);
  background: var(--surface);
  border: 2px dashed var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition);
  position: relative;
}

.empty:hover {
  border-color: var(--accent-light);
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.skeleton {
  pointer-events: none;
  animation: fadeIn 0.4s ease-out;
}

.sk-line {
  height: 10px;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--surface-secondary) 50%, var(--bg-secondary) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.8s ease-in-out infinite;
}

.sk-title {
  width: min(60%, 300px);
  height: 16px;
  border-radius: 8px;
}

.sk-sub {
  width: min(40%, 200px);
  margin-top: 10px;
  opacity: 0.6;
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

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
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

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}
</style>
