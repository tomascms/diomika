import { ref, onUnmounted } from 'vue'

let worker = null

function getWorker() {
  if (!worker) {
    worker = new Worker(new URL('@/workers/searchWorker.js', import.meta.url), { type: 'module' })
  }
  return worker
}

export function useSearchWorker() {
  const isSearching = ref(false)

  const search = async (items, query, fields) => {
    if (!items.length || !query.trim()) {
      return items
    }

    return new Promise((resolve) => {
      isSearching.value = true
      const w = getWorker()

      const handleMessage = (event) => {
        if (event.data.type === 'search-results') {
          w.removeEventListener('message', handleMessage)
          isSearching.value = false
          resolve(event.data.results)
        }
      }

      w.addEventListener('message', handleMessage)
      w.postMessage({
        type: 'search',
        payload: { items, query, fields },
      })
    })
  }

  const filter = async (items, predicate) => {
    if (!items.length) {
      return items
    }

    return new Promise((resolve) => {
      isSearching.value = true
      const w = getWorker()

      const handleMessage = (event) => {
        if (event.data.type === 'filter-results') {
          w.removeEventListener('message', handleMessage)
          isSearching.value = false
          resolve(event.data.results)
        }
      }

      w.addEventListener('message', handleMessage)
      w.postMessage({
        type: 'filter',
        payload: { items, predicate },
      })
    })
  }

  onUnmounted(() => {
    if (worker) {
      worker.terminate()
      worker = null
    }
  })

  return {
    search,
    filter,
    isSearching,
  }
}
