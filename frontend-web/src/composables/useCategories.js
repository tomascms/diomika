import { ref } from 'vue'
import { apiGet } from '@/lib/api'
import { listCategories } from '@/lib/catalogSupabase'
import { supabaseConfigured } from '@/lib/supabase'
import { resolveImageUrl } from '@/lib/images'

/** Estado partilhado — App.vue e HomeView usam a mesma instância. */
const categories = ref([])
const loading = ref(false)
const error = ref('')
let loadPromise = null

export function useCategories() {
  const load = async (force = false) => {
    if (categories.value.length && !force) {
      return categories.value
    }
    if (categories.value.length === 0 && !force && loadPromise) {
      return loadPromise
    }

    loading.value = true
    error.value = ''
    loadPromise = (async () => {
      try {
        const data = supabaseConfigured
          ? await listCategories()
          : await apiGet('/categorias')
        const raw = (Array.isArray(data) ? data : []).filter((c) => c.visibilidade !== false)
        const list = await Promise.all(
          raw.map(async (c) => ({ ...c, imagem: await resolveImageUrl(c.imagem) })),
        )
        categories.value = list
        return list
      } catch (e) {
        error.value = e.message || 'Erro ao carregar categorias.'
        categories.value = []
        throw e
      } finally {
        loading.value = false
        loadPromise = null
      }
    })()

    return loadPromise
  }

  return { categories, loading, error, load }
}
