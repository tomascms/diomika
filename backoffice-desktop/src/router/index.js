import { createRouter, createWebHashHistory } from 'vue-router'
import {
  bootstrapSettings,
  isAuthenticated,
  clearSession,
  readSessionToken,
} from '@/lib/settings'
import { loadWorkspace } from '@/composables/useWorkspace'
import { api } from '@/lib/api'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      children: [
        { path: '', redirect: { name: 'workspace', params: { table: 'categories' } } },
        {
          path: 'workspace/:table',
          name: 'workspace',
          component: () => import('@/views/WorkspaceRouter.vue'),
        },
        {
          path: 'workspace/:table/new',
          name: 'record-new',
          component: () => import('@/views/RecordFormView.vue'),
        },
        {
          path: 'workspace/:table/new/:physicalTable',
          name: 'record-new-physical',
          component: () => import('@/views/RecordFormView.vue'),
        },
        {
          path: 'workspace/:table/:id',
          name: 'record-edit',
          component: () => import('@/views/RecordFormView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  bootstrapSettings()

  if (to.meta.public) return true

  let loginRequired = false
  try {
    const st = await api.authStatus()
    loginRequired = Boolean(st.login_required)
  } catch {
    loginRequired = Boolean(readSessionToken())
  }

  if (loginRequired && !isAuthenticated()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (loginRequired && readSessionToken()) {
    try {
      await api.me()
    } catch {
      clearSession()
      return { name: 'login' }
    }
  }

  await loadWorkspace().catch(() => {})
})

export default router
