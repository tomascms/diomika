<script setup>
import { ref, computed, watch } from 'vue'
const props = defineProps({ modelValue: { type: String, default: '' }, multiple: { type: Boolean, default: false }, disabled: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'file-selected'])
const displayPath = ref('')
const previewUrl = ref('')
const errorMessage = ref('')
const isUrl = (v) => /^https?:\/\//i.test(v || '')
const isSignedUrl = computed(() => String(props.modelValue || '').includes('/object/sign/'))
const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif'])
const allowedExtension = /\.(jpe?g|png|webp|gif)$/i
watch(() => props.modelValue, (v) => {
  if (isUrl(v)) { displayPath.value = 'Imagem carregada'; previewUrl.value = v }
  else { displayPath.value = v || ''; if (!v || !previewUrl.value?.startsWith('blob:')) previewUrl.value = '' }
}, { immediate: true })
const pickLabel = computed(() => (props.multiple ? 'Escolher ficheiros…' : 'Escolher ficheiro…'))
function validate(file) {
  if (file.size > 5 * 1024 * 1024) return `${file.name}: o ficheiro excede 5 MB.`
  if (!allowedTypes.has(file.type) && !allowedExtension.test(file.name)) return `${file.name}: formato não suportado. Use JPEG, PNG, WebP ou GIF.`
  return ''
}
const onPick = (e) => {
  const files = [...(e.target.files || [])]
  errorMessage.value = ''
  if (!files.length) return
  const invalid = files.map(validate).find(Boolean)
  if (invalid) { errorMessage.value = invalid; e.target.value = ''; return }
  if (props.multiple) {
    const paths = files.map((f) => f.name).join('; '); displayPath.value = paths; emit('update:modelValue', paths); emit('file-selected', files)
  } else {
    const file = files[0]; displayPath.value = file.name; emit('update:modelValue', file.name); emit('file-selected', file)
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
      <label v-if="!disabled" class="btn btn-primary pick">{{ pickLabel }}<input type="file" accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif" :multiple="multiple" hidden @change="onPick" /></label>
    </div>
    <p v-if="errorMessage" class="field-error" role="alert">{{ errorMessage }}</p>
    <p v-if="isSignedUrl" class="field-warning">Não grave URLs assinadas — use upload ou path do storage</p>
    <img v-if="previewUrl" :src="previewUrl" alt="" class="thumb" />
  </div>
</template>
<style scoped>
.image-field {
  display: grid;
  gap: 14px;
}

.row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.row:focus-within {
  background: var(--bg-hover);
}

.path {
  flex: 1;
  min-width: 200px;
  color: var(--text-secondary);
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  font-size: 13px;
  transition: all var(--transition);
}

.path:hover {
  border-color: var(--accent-light);
  background: var(--bg-hover);
}

.pick {
  cursor: pointer;
  white-space: nowrap;
  margin: 0;
  padding: 10px 18px;
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.2px;
  transition: all var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.pick::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: width var(--transition), height var(--transition);
}

.pick:active::after {
  width: 100%;
  height: 100%;
}

.pick:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.pick input {
  display: none;
}

.field-error,
.field-warning {
  margin: 0;
  font-size: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-weight: 500;
  animation: slideDown 0.3s ease-out;
}

.field-error {
  color: var(--danger);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 3px solid var(--danger);
}

.field-warning {
  color: var(--warning);
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-left: 3px solid var(--warning);
}

.thumb {
  margin: 0;
  width: min(240px, 100%);
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: var(--radius-md);
  border: 2px solid var(--border);
  background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--surface) 100%);
  box-shadow: var(--shadow-md);
  transition: all var(--transition);
  animation: thumbIn 0.4s ease-out;
}

.thumb:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-lg), 0 0 0 4px rgba(59, 130, 246, 0.1);
  transform: scale(1.02);
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

@keyframes thumbIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
