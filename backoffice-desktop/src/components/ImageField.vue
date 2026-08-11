<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  multiple: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'file-selected'])

const displayPath = ref('')
const previewUrl = ref('')

const isUrl = (v) => /^https?:\/\//i.test(v || '')

watch(
  () => props.modelValue,
  (v) => {
    if (isUrl(v)) {
      displayPath.value = 'Imagem carregada'
      previewUrl.value = v
    } else {
      displayPath.value = v || ''
      if (!v || !previewUrl.value?.startsWith('blob:')) previewUrl.value = ''
    }
  },
  { immediate: true },
)

const pickLabel = computed(() => (props.multiple ? 'Escolher ficheiros…' : 'Escolher ficheiro…'))

const onPick = (e) => {
  const files = [...(e.target.files || [])]
  if (!files.length) return
  if (props.multiple) {
    const paths = files.map((f) => f.name).join('; ')
    displayPath.value = paths
    emit('update:modelValue', paths)
    emit('file-selected', files)
  } else {
    const file = files[0]
    displayPath.value = file.name
    emit('update:modelValue', file.name)
    emit('file-selected', file)
    if (previewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = URL.createObjectURL(file)
  }
  e.target.value = ''
}
</script>

<template>
  <div class="image-field">
    <div class="row">
      <input class="input path" :value="displayPath" readonly placeholder="Nenhum ficheiro selecionado" />
      <label v-if="!disabled" class="btn btn-primary pick">
        {{ pickLabel }}
        <input type="file" accept="image/*" :multiple="multiple" hidden @change="onPick" />
      </label>
    </div>
    <img v-if="previewUrl" :src="previewUrl" alt="" class="thumb" />
  </div>
</template>

<style scoped>
.image-field { display: grid; gap: 0.65rem; }
.row { display: flex; gap: 0.55rem; align-items: center; flex-wrap: wrap; }
.path { flex: 1; min-width: 160px; color: var(--text-muted); }
.pick { cursor: pointer; white-space: nowrap; margin: 0; }
.pick input { display: none; }
.thumb {
  margin: 0;
  width: min(220px, 100%);
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-soft);
}
</style>
