// Mock API para desenvolvimento offline
const mockCategorias = [
  { id: 1, nome: 'Almofada', slug: 'almofada', imagem: null, tipo_catalogo: 'almofada' },
  { id: 2, nome: 'Assento', slug: 'assento', imagem: null, tipo_catalogo: 'assento' },
]

const mockProdutos = [
  { id: 1, nome: 'Almofada Premium', categoria_id: 1, ean: '123456789', ativo: true },
  { id: 2, nome: 'Assento Confortável', categoria_id: 2, ean: '987654321', ativo: true },
]

export function mockApiCall(endpoint) {
  if (endpoint === '/health') return Promise.resolve({ status: 'ok' })
  if (endpoint === '/auth/status') return Promise.resolve({ login_required: false })
  if (endpoint === '/me') return Promise.resolve({ username: 'admin', role: 'admin' })
  if (endpoint === '/workspace/schema') return Promise.resolve({ tables: {} })
  if (endpoint === '/categorias') return Promise.resolve(mockCategorias)
  if (endpoint === '/produtos') return Promise.resolve(mockProdutos)

  return Promise.reject(new Error(`Mock: ${endpoint} not found`))
}
