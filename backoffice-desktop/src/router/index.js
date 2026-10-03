import { createRouter, createWebHashHistory } from 'vue-router'
import {
  bootstrapSettings,
  isAuthenticated,
  clearSession,
  readSessionToken,
  saveSettings,
  writeSessionUser,
} from '@/lib/settings'
import { loadWorkspace, workspace } from '@/composables/useWorkspace'
import { api, clearApiCaches } from '@/lib/api'

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

  // Auto-login sem verificação
  if (!isAuthenticated()) {
    saveSettings({ accessToken: 'dev-mode' })
    writeSessionUser({ username: 'admin', role: 'admin' })
  }

  if (!workspace.value) {
    await loadWorkspace().catch(() => {})
  }
})

export default router
