// Web Worker for background text search and filtering
// Offloads heavy text processing from the main thread

self.onmessage = (event) => {
  const { type, payload } = event.data

  if (type === 'search') {
    const { items, query, fields } = payload
    const results = performSearch(items, query, fields)
    self.postMessage({ type: 'search-results', results })
  } else if (type === 'filter') {
    const { items, predicate } = payload
    const results = items.filter((item) => {
      // Safely evaluate the filter function
      try {
        return Function('"use strict"; return (' + predicate + ')')()(item)
      } catch {
        return false
      }
    })
    self.postMessage({ type: 'filter-results', results })
  }
}

function performSearch(items, query, fields) {
  if (!query.trim()) return items

  const normalizedQuery = query.toLowerCase().trim()
  const terms = normalizedQuery.split(/\s+/).filter(Boolean)

  return items.filter((item) => {
    for (const field of fields) {
      const value = String(getNestedValue(item, field) || '').toLowerCase()
      if (terms.every((term) => value.includes(term))) {
        return true
      }
    }
    return false
  })
}

function getNestedValue(obj, path) {
  return path.split('.').reduce((acc, part) => acc && acc[part], obj)
}
