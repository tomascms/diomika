<script setup>
import { ref, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { supabaseConfigured } from '@/lib/supabaseConfig'
import AppErrorBoundary from '@/components/AppErrorBoundary.vue'
import { useCart } from '@/composables/useCart'
import { useCategories } from '@/composables/useCategories'
import { categoryProductsRoute } from '@/lib/catalogRoutes'
import { prefetchRoute } from '@/router'

const CookieBanner = defineAsyncComponent(() => import('@/components/CookieBanner.vue'))

const isMenuOpen = ref(false)
const { categories, load: loadCategories } = useCategories()
const cartCount = ref(0)
const cart = useCart()

const pretty = (name) => {
  const t = String(name || '').trim()
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : ''
}

const refreshCartCount = () => {
  cartCount.value = cart.count()
}

const closeMenu = () => {
  isMenuOpen.value = false
}

const onEscape = (e) => {
  if (e.key === 'Escape') closeMenu()
}

let categoriesSubscription = null

onMounted(async () => {
  try {
    await loadCategories()
  } catch {
    /* footer / home mostram o estado */
  }
  refreshCartCount()
  window.addEventListener('storage', refreshCartCount)
  window.addEventListener('diomika-cart-updated', refreshCartCount)
  window.addEventListener('keydown', onEscape)

  if (supabaseConfigured) {
    const startRealtime = async () => {
      if (categoriesSubscription) return
      const { ensureSupabase, subscribeRealtime } = await import('@/lib/supabase')
      const supabase = await ensureSupabase()
      if (!supabase) return
      const channel = supabase
        .channel('categories_channel')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'categories' }, () => {
          loadCategories(true)
        })
      categoriesSubscription = subscribeRealtime(channel)
    }
    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(() => {
        startRealtime().catch(() => {})
      }, { timeout: 4000 })
    } else {
      setTimeout(() => {
        startRealtime().catch(() => {})
      }, 2000)
    }
  }
})

onUnmounted(() => {
  if (categoriesSubscription) {
    import('@/lib/supabase').then(({ ensureSupabase }) =>
      ensureSupabase().then((supabase) => {
        if (supabase) supabase.removeChannel(categoriesSubscription)
      }),
    )
  }
  window.removeEventListener('storage', refreshCartCount)
  window.removeEventListener('diomika-cart-updated', refreshCartCount)
  window.removeEventListener('keydown', onEscape)
})
</script>

<template>
  <div class="app-container">
    <a href="#main-content" class="skip-link">Saltar para conteúdo</a>

    <header class="app-header">
      <div class="page-shell header-inner">
        <RouterLink to="/" class="logo-link" @click="closeMenu">
          <img src="/brand/logo.svg" alt="Diomika" class="brand-logo" width="200" height="36" fetchpriority="high" decoding="async" />
        </RouterLink>

        <button
          type="button"
          class="menu-btn"
          :aria-label="isMenuOpen ? 'Fechar menu' : 'Abrir menu'"
          :aria-expanded="isMenuOpen"
          @click="isMenuOpen = !isMenuOpen"
        >
          {{ isMenuOpen ? 'Fechar' : 'Menu' }}
        </button>

        <nav class="main-nav" :class="{ open: isMenuOpen }" aria-label="Principal">
          <RouterLink
            to="/categorias"
            @click="closeMenu"
            @pointerenter="prefetchRoute('categories')"
          >Categorias</RouterLink>
          <RouterLink to="/sobre" @click="closeMenu">Sobre nós</RouterLink>
          <RouterLink
            to="/carrinho"
            class="nav-cart"
            @click="refreshCartCount(); closeMenu()"
          >
            Carrinho
            <span v-if="cartCount > 0" class="cart-badge">{{ cartCount }}</span>
          </RouterLink>
          <RouterLink to="/contact" class="btn nav-cta" @click="closeMenu">
            Contacto
          </RouterLink>
        </nav>
      </div>
    </header>

    <main id="main-content" class="app-main">
      <AppErrorBoundary>
        <RouterView v-slot="{ Component, route }">
          <Transition name="page-fade" mode="out-in">
            <component :is="Component" :key="route.path" />
          </Transition>
        </RouterView>
      </AppErrorBoundary>
    </main>

    <footer class="app-footer">
      <div class="page-shell footer-grid">
        <div class="footer-brand">
          <img src="/brand/logo.svg" alt="Diomika" width="170" height="30" />
          <p>
            Catálogo B2B de almofadas e assentos. Consulte modelos e variantes
            e peça orçamento online.
          </p>
        </div>

        <div>
          <h3 class="footer-title">Navegação</h3>
          <ul class="footer-links">
            <li><RouterLink to="/categorias">Categorias</RouterLink></li>
            <li><RouterLink to="/sobre">Sobre nós</RouterLink></li>
            <li><RouterLink to="/contact">Contacto</RouterLink></li>
            <li><RouterLink to="/carrinho">Pedido de orçamento</RouterLink></li>
            <li><RouterLink to="/privacidade">Privacidade</RouterLink></li>
          </ul>
        </div>

        <div>
          <h3 class="footer-title">Categorias</h3>
          <ul class="footer-links">
            <li v-for="cat in categories" :key="cat.id">
              <RouterLink :to="categoryProductsRoute(cat)">
                {{ pretty(cat.nome) }}
              </RouterLink>
            </li>
            <li v-if="!categories.length">
              <RouterLink to="/categorias">Ver categorias</RouterLink>
            </li>
          </ul>
        </div>

        <div>
          <h3 class="footer-title">Contacto</h3>
          <ul class="footer-links footer-contact">
            <li>
              <a href="tel:+351935745663">935 745 663</a>
            </li>
            <li>Rua da Quintã, n.º 89<br />4805-116 Caldas das Taipas</li>
            <li>NIF 508 651 557</li>
          </ul>
        </div>

        <div>
          <h3 class="footer-title">Orçamento</h3>
          <p class="footer-note">
            Sem preços no site — monte o pedido no carrinho ou envie mensagem
            pelo formulário de contacto.
          </p>
          <RouterLink to="/carrinho" class="footer-cta">Pedir orçamento</RouterLink>
        </div>
      </div>

      <div class="footer-bottom page-shell">
        <p>© {{ new Date().getFullYear() }} Diomika. Todos os direitos reservados.</p>
      </div>
    </footer>

    <CookieBanner />
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 2000;
  padding: 0.75rem 1rem;
  background: #fff;
  color: var(--color-ink-deep);
  text-decoration: none;
  font-weight: 600;
}

.skip-link:focus { left: 0; }

.app-header {
  background: var(--color-ink-deep);
  position: sticky;
  top: 0;
  z-index: 1000;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  padding-top: 0.95rem;
  padding-bottom: 0.95rem;
}

.logo-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  flex-shrink: 0;
}

.brand-logo {
  width: min(200px, 52vw);
  height: auto;
  filter: brightness(0) invert(1);
}

.menu-btn {
  display: none;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: transparent;
  border-radius: 8px;
  padding: 0.45rem 0.8rem;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
}

.main-nav {
  display: flex;
  align-items: center;
  gap: 0.35rem 1.4rem;
}

.main-nav > a {
  color: rgba(255, 255, 255, 0.92);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.95rem;
}

.main-nav > a:hover,
.main-nav > a.router-link-active {
  color: #fff;
}

.nav-cart { position: relative; }

.cart-badge {
  margin-left: 0.25rem;
  background: #e85d4c;
  color: #fff;
  border-radius: 999px;
  padding: 0.05rem 0.4rem;
  font-size: 0.7rem;
  font-weight: 700;
}

.nav-cta {
  background: #fff !important;
  color: var(--color-ink-deep) !important;
  border: 0 !important;
  padding: 0.5rem 1.15rem !important;
}

.nav-cta:hover {
  background: #eef2f6 !important;
  color: var(--color-ink-deep) !important;
}

.app-main { flex: 1; width: 100%; min-width: 0; }

.app-footer {
  background: #071526;
  color: rgba(255, 255, 255, 0.82);
  margin-top: auto;
  padding-top: 3rem;
}

.footer-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 1.5rem 1rem;
  padding-top: 0;
  padding-bottom: 2.25rem;
  max-width: 1320px;
}

.footer-brand img {
  width: 170px;
  height: auto;
  margin-bottom: 1rem;
  filter: brightness(0) invert(1);
}

.footer-brand p,
.footer-note {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.72);
  max-width: 32ch;
}

.footer-title {
  margin: 0 0 0.9rem;
  color: #fff;
  font-size: 0.95rem;
  font-weight: 700;
}

.footer-links {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}

.footer-links a,
.footer-links span {
  color: rgba(255, 255, 255, 0.78);
  text-decoration: none;
  font-size: 0.92rem;
}

.footer-links a:hover { color: #fff; }

.footer-contact li {
  line-height: 1.55;
}

.footer-cta {
  display: inline-flex;
  margin-top: 1rem;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  background: #fff;
  color: var(--color-ink-deep);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9rem;
}

.footer-cta:hover {
  background: #eef2f6;
  color: var(--color-ink-deep);
}

.footer-bottom {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 1.15rem;
  padding-bottom: 1.15rem;
  text-align: center;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.5);
}

.footer-bottom p { margin: 0; }

@media (max-width: 992px) {
  .footer-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .footer-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .menu-btn { display: inline-flex; }

  .main-nav {
    display: none;
    position: absolute;
    left: 0;
    right: 0;
    top: 100%;
    background: var(--color-ink-deep);
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    flex-direction: column;
    align-items: stretch;
    padding: 0.75rem 1rem 1rem;
    gap: 0.15rem;
    box-shadow: var(--shadow-md);
  }

  .main-nav.open { display: flex; }

  .main-nav > a {
    padding: 0.75rem 0.5rem;
    border-radius: 8px;
  }

  .main-nav > a:hover {
    background: rgba(255, 255, 255, 0.08);
  }

  .nav-cta {
    margin-top: 0.4rem;
    text-align: center;
    justify-content: center;
  }
}

@media (max-width: 560px) {
  .footer-grid { grid-template-columns: 1fr; }
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .page-fade-enter-active,
  .page-fade-leave-active {
    transition: none;
  }
}
</style>
