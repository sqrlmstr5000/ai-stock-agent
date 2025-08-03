import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { title: 'Dashboard' }
    },
    {
      path: '/analysis',
      name: 'analysis',
      // route level code-splitting
      // this generates a separate chunk (Analysis.[hash].js) for this route
      component: () => import('../views/AnalysisView.vue'),
      meta: { title: 'Analysis' }
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
      meta: { title: 'Settings' }
    },
    {
      path: '/analysis/:symbol',
      name: 'analysis-symbol',
      // route level code-splitting
      // this generates a separate chunk (Analysis.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import('../views/AnalysisView.vue'),
      meta: { title: 'Analysis' }
    },
    {
      path: '/portfolio',
      name: 'portfolio',
      component: () => import('../views/PortfolioView.vue'),
      meta: { title: 'Portfolio' }
    },
  ]
})

// Update page title
router.beforeEach((to, from, next) => {
  const pageTitle = to.name === 'symbol' ? to.params.symbol.toUpperCase() : to.meta.title
  document.title = `${pageTitle} - AI Stock Agent`
  next()
})

export default router
