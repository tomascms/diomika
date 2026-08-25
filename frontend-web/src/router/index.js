import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import ProductsView from '@/views/ProductsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, _from, savedPosition) {
    if (to.hash) {
      return {
        el: to.hash,
        behavior: 'smooth',
        top: 80,
      }
    }
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
  routes: [
    {
      path: '/', // Rota para a página inicial
      name: 'home',
      component: HomeView
    },
    {
      path: '/categorias',
      name: 'categories',
      component: () => import('@/views/CategoriesView.vue')
    },
    {
      path: '/produtos/:categoryId?',
      name: 'products',
      component: ProductsView
    },
    {
      path: '/produto/:id',
      name: 'product-detail',
      component: () => import('@/views/ProductDetailView.vue')
    },
    {
      path: '/carrinho',
      name: 'cart',
      component: () => import('@/views/CartView.vue'),
    },
    {
      path: '/contacto',
      name: 'contact',
      component: () => import('@/views/ContactView.vue'),
      alias: ['/contact'],
    },
    {
      path: '/sobre',
      name: 'about',
      component: () => import('@/views/AboutView.vue')
    },
    {
      path: '/privacidade',
      name: 'privacy',
      component: () => import('@/views/PrivacyView.vue')
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue')
    }
  ],
})


export default router
