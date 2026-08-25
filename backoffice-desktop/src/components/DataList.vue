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
  // Evita "assento / assento" quando nome === slug
  if (sub.toLowerCase() === main) return ''
  return sub
}
</script>

<template>
  <div class="list" role="list">
    <p v-if="loading" class="empty">A carregar…</p>
    <p v-else-if="!rows.length" class="empty">Sem registos.</p>

    <article v-for="row in rows" :key="row.id" class="item" role="listitem">
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
          >{{ row.visibilidade === false ? 'Oculto' : 'Visível' }}</span>
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
  gap: 0.55rem;
}

.item {
  padding: 0.95rem 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.item:hover {
  border-color: rgba(15, 110, 86, 0.28);
  box-shadow: 0 2px 10px rgba(24, 33, 43, 0.08);
}

.item-body {
  flex: 1;
  min-width: 180px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.title {
  margin: 0;
  font-weight: 650;
  font-size: 0.98rem;
  letter-spacing: -0.01em;
}

.sub {
  margin: 0.3rem 0 0 0.15rem;
  color: var(--text-muted);
  font-size: 0.84rem;
}

.status-pill {
  font-size: 0.66rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0.18rem 0.45rem;
  border-radius: 999px;
  background: var(--success-soft);
  color: var(--success);
}

.status-pill.hidden {
  background: var(--danger-soft);
  color: var(--danger);
}

.status-pill.unread {
  background: var(--accent-soft);
  color: var(--accent-hover);
}

.actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.empty {
  padding: 2.5rem 1rem;
  text-align: center;
  color: var(--text-muted);
  background: var(--bg-panel);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
}
</style>
