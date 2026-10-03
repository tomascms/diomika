<script setup>
import { computed } from 'vue'
import { formatStorefrontValue } from '@/lib/storefrontFormat'

const props = defineProps({
  model: { type: Object, default: null },
  specs: { type: Array, default: () => [] },
  extras: { type: Array, default: () => [] },
})

const rows = computed(() =>
  (props.specs || [])
    .map((spec) => {
      const raw = props.model?.[spec.field]
      return {
        ...spec,
        raw,
        display: formatStorefrontValue(spec, raw),
        isComposition: spec.widget === 'composition' && raw && typeof raw === 'object',
        compositionEntries: spec.widget === 'composition' && raw && typeof raw === 'object'
          ? Object.entries(raw)
          : [],
      }
    })
    .filter((row) => row.display || row.compositionEntries.length),
)
</script>

<template>
  <div v-if="rows.length || extras.length" class="specs-panel">
    <h3 class="specs-title">Especificações</h3>
    <dl class="specs-grid">
      <template v-for="row in rows" :key="row.field">
        <div class="spec-item">
          <dt>{{ row.label }}</dt>
          <dd v-if="row.isComposition" class="composition-tags">
            <span v-for="([material, percent], idx) in row.compositionEntries" :key="material" class="mat-tag">
              {{ percent }}% {{ material }}<span v-if="idx < row.compositionEntries.length - 1"> </span>
            </span>
          </dd>
          <dd v-else>{{ row.display }}</dd>
        </div>
      </template>
      <div v-for="extra in extras" :key="`extra-${extra.label}`" class="spec-item">
        <dt>{{ extra.label }}</dt>
        <dd>{{ extra.display }}</dd>
      </div>
    </dl>
  </div>
</template>

<style scoped>
.specs-panel {
  margin-top: 1.25rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.15);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
  animation: slideUp 0.4s ease-out;
}

.specs-title {
  margin: 0 0 1.2rem;
  font-family: var(--font-body);
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  padding-bottom: 10px;
  border-bottom: 2px solid rgba(59, 130, 246, 0.2);
}

.specs-grid {
  margin: 0;
  display: grid;
  gap: 1rem;
}

.spec-item {
  padding: 0.85rem;
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-sm);
  transition: all var(--transition);
}

.spec-item:hover {
  background: rgba(59, 130, 246, 0.06);
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}

.spec-item dt {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent);
}

.spec-item dd {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-ink-deep);
  line-height: 1.5;
}

.composition-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.mat-tag {
  display: inline-block;
  padding: 0.4rem 0.8rem;
  background: linear-gradient(135deg, #fff 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-pill);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-ink-soft);
  transition: all var(--transition);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}

.mat-tag:hover {
  background: linear-gradient(135deg, #fff 0%, rgba(59, 130, 246, 0.04) 100%);
  border-color: rgba(59, 130, 246, 0.3);
  box-shadow: 0 4px 8px rgba(59, 130, 246, 0.1);
  transform: translateY(-1px);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
