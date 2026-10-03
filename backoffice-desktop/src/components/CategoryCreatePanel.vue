<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/lib/api'
import ImageField from '@/components/ImageField.vue'

const emit = defineEmits(['created', 'error'])

const tipos = ref([])
const tipoCatalogo = ref('')
const nome = ref('')
const imagem = ref('')
const imageFile = ref(null)
const carrinhoStep = ref('')
const carrinhoMin = ref('')
const saving = ref(false)
const loadingTipos = ref(true)

onMounted(async () => {
  try {
    const data = await api.categoryTipos()
    tipos.value = data.tipos || []
    if (tipos.value.length) tipoCatalogo.value = tipos.value[0].tipo
  } catch (e) {
    emit('error', e.message)
  } finally {
    loadingTipos.value = false
  }
})

const onImageFile = (file) => {
  imageFile.value = file
}

const create = async () => {
  saving.value = true
  emit('error', '')
  try {
    if (!nome.value.trim()) throw new Error('Indique o nome da categoria.')
    if (!tipoCatalogo.value) throw new Error('Escolha a família de produto.')
    let imageUrl = imagem.value
    if (imageFile.value) {
      const up = await api.uploadImage('categories', 'imagem', imageFile.value)
      imageUrl = up.url
    }
    if (!imageUrl) throw new Error('Escolha uma imagem para a categoria.')
    await api.createRecord('categories', {
      nome: nome.value.trim(),
      imagem: imageUrl,
      tipo_catalogo: tipoCatalogo.value,
      carrinho_step: carrinhoStep.value ? Number(carrinhoStep.value) : undefined,
      carrinho_min: carrinhoMin.value ? Number(carrinhoMin.value) : undefined,
    })
    nome.value = ''
    imagem.value = ''
    imageFile.value = null
    carrinhoStep.value = ''
    carrinhoMin.value = ''
    emit('created')
  } catch (e) {
    emit('error', e.message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="card panel">
    <h3>Nova categoria</h3>
    <p class="hint">
      Dá-lhe um nome e uma imagem, e escolhe a família de produto que vai conter (define que
      campos os modelos desta categoria têm). Podes criar quantas categorias quiseres para a
      mesma família — ex.: "Almofadas" e "Almofadas de Natal" podem coexistir.
    </p>

    <label for="cat-nome">Nome</label>
    <input id="cat-nome" v-model="nome" class="input" placeholder="ex: Almofadas de Natal" />

    <label for="cat-imagem">Imagem</label>
    <ImageField id="cat-imagem" v-model="imagem" @file-selected="onImageFile" />

    <label for="cat-tipo">Família de produto</label>
    <select id="cat-tipo" v-model="tipoCatalogo" class="input" :disabled="loadingTipos">
      <option v-for="t in tipos" :key="t.tipo" :value="t.tipo">{{ t.label }}</option>
    </select>
    <p class="hint small">
      Uma família nova (com campos diferentes das 12 atuais) precisa de uma alteração de código —
      todo o resto de uma categoria é livre.
    </p>

    <div class="grid-2">
      <div>
        <label for="cat-step">Passo carrinho</label>
        <input id="cat-step" v-model="carrinhoStep" class="input" type="number" placeholder="6" />
      </div>
      <div>
        <label for="cat-min">Mínimo carrinho</label>
        <input id="cat-min" v-model="carrinhoMin" class="input" type="number" placeholder="6" />
      </div>
    </div>

    <button class="btn btn-primary" :disabled="saving || loadingTipos" @click="create">
      {{ saving ? 'A criar…' : 'Criar categoria' }}
    </button>
  </div>
</template>

<style scoped>
.panel {
  padding: 20px;
  margin-bottom: 16px;
  display: grid;
  gap: 14px;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.panel h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.hint {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
  line-height: 1.5;
  font-weight: 500;
}

.hint.small {
  font-size: 0.78rem;
  color: var(--text-muted);
  padding: 10px;
  background: rgba(59, 130, 246, 0.04);
  border: 1px solid rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--accent);
}

label {
  display: block;
  font-size: 0.85rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--accent);
  margin-bottom: 6px;
}

.panel .input {
  padding: 11px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 0.95rem;
  background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.01) 100%);
  color: var(--text-primary);
  transition: all var(--transition);
}

.panel .input::placeholder {
  color: var(--text-muted);
}

.panel .input:hover {
  border-color: var(--accent-light);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.08);
  background: linear-gradient(135deg, var(--surface), rgba(59, 130, 246, 0.03));
}

.panel .input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12), inset 0 0 0 1px rgba(59, 130, 246, 0.1);
  background: linear-gradient(135deg, var(--surface), rgba(59, 130, 246, 0.04));
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.grid-2 > div {
  display: grid;
  gap: 6px;
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
