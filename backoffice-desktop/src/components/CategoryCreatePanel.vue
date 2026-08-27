<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '@/lib/api'
import ImageField from '@/components/ImageField.vue'

const props = defineProps({
  plan: { type: Object, required: true },
})

const emit = defineEmits(['created', 'error'])

const selectedSlug = ref('')
const nome = ref('')
const slug = ref('')
const carrinhoStep = ref('')
const carrinhoMin = ref('')
const imagem = ref('')
const imageFile = ref(null)
const saving = ref(false)

const selected = computed(() => props.plan.missing.find((m) => m.slug === selectedSlug.value) || props.plan.missing[0])

const tipoLabel = computed(() => {
  const tipo = selected.value?.tipo_catalogo
  if (!tipo) return '—'
  const map = {
    almofada: 'Almofadas',
    assento: 'Assentos',
    guarda_chuva: 'Guarda-chuvas',
    oculo: 'Óculos',
    toalha_mesa: 'Toalhas de mesa',
    material_cozinha: 'Material de cozinha',
    regional: 'Regional',
  }
  return map[tipo] || String(tipo).replace(/_/g, ' ')
})

const fillFromSelection = () => {
  const item = selected.value
  if (!item) return
  selectedSlug.value = item.slug
  nome.value = item.nome || ''
  // Slug canónico da definição — evita drift com o plano / URLs
  slug.value = item.slug || ''
  carrinhoStep.value = String(item.carrinho_step ?? '')
  carrinhoMin.value = String(item.carrinho_min ?? '')
  imagem.value = ''
  imageFile.value = null
}

watch(() => props.plan, () => {
  if (props.plan?.missing?.length) selectedSlug.value = props.plan.missing[0].slug
  fillFromSelection()
}, { immediate: true })
watch(selectedSlug, fillFromSelection)

const onImageFile = (file) => {
  imageFile.value = file
}

const create = async () => {
  saving.value = true
  emit('error', '')
  try {
    let imageUrl = imagem.value
    if (imageFile.value) {
      const up = await api.uploadImage('categories', 'imagem', imageFile.value)
      imageUrl = up.url
    }
    if (!imageUrl) throw new Error('Escolha uma imagem para a categoria.')
    await api.createCategory({
      definition_slug: selected.value.slug,
      nome: nome.value.trim(),
      // Sempre o slug da definição — não permitir override livre
      slug_override: selected.value.slug,
      imagem: imageUrl,
      carrinho_step: carrinhoStep.value ? Number(carrinhoStep.value) : undefined,
      carrinho_min: carrinhoMin.value ? Number(carrinhoMin.value) : undefined,
    })
    emit('created')
    fillFromSelection()
  } catch (e) {
    emit('error', e.message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="card panel">
    <h3>Criar categorias em falta</h3>
    <p class="hint">{{ plan.message }}</p>

    <label>Categoria pendente</label>
    <select v-model="selectedSlug" class="input">
      <option v-for="item in plan.missing" :key="item.slug" :value="item.slug">
        {{ item.nome }}
      </option>
    </select>

    <label>Nome</label>
    <input v-model="nome" class="input" />

    <label>Slug (URL)</label>
    <input v-model="slug" class="input" readonly />

    <label>Imagem</label>
    <ImageField v-model="imagem" @file-selected="onImageFile" />

    <div class="grid-2">
      <div>
        <label>Passo carrinho</label>
        <input v-model="carrinhoStep" class="input" type="number" />
      </div>
      <div>
        <label>Mínimo carrinho</label>
        <input v-model="carrinhoMin" class="input" type="number" />
      </div>
    </div>

    <p class="tipo">Família: <strong>{{ tipoLabel }}</strong></p>

    <button class="btn btn-primary" :disabled="saving" @click="create">
      {{ saving ? 'A criar…' : 'Criar categoria selecionada' }}
    </button>
  </div>
</template>

<style scoped>
.panel { padding: 1.2rem 1.25rem; margin-bottom: 1rem; display: grid; gap: 0.65rem; }
.panel h3 { margin: 0; font-family: var(--font-display); font-weight: 560; }
.hint { color: var(--text-muted); font-size: 0.9rem; margin: 0; }
label { font-size: 0.84rem; font-weight: 600; color: var(--text-muted); }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.tipo { font-size: 0.85rem; color: var(--accent-hover); margin: 0; font-weight: 600; }
</style>
