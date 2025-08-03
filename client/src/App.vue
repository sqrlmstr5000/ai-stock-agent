<template>
  <div class="h-full dark:bg-gray-900 dark:text-gray-100">
    <!-- Static sidebar for desktop -->
    <div class="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-20 lg:flex-col">
      <!-- Sidebar component -->
      <div class="flex grow flex-col gap-y-5 overflow-y-auto overflow-x-hidden border-r border-gray-200 dark:border-gray-700 px-4 pb-4">
        <div class="flex h-16 shrink-0 items-center justify-center">
          <img class="h-8 w-auto" src="@/assets/logo.svg" alt="AI Stock Agent" />
        </div>
        <nav class="flex flex-1 flex-col">
          <ul role="list" class="flex flex-1 flex-col gap-y-7">
            <li>
              <ul role="list" class="space-y-1">
                <li v-for="item in navigation" :key="item.name" :title="item.name">
                  <router-link :to="item.href" :title="item.name" :class="[
                    item.current ? 'bg-gray-50 text-primary-600 dark:bg-gray-700 dark:text-primary-500' : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:text-primary-500 dark:hover:bg-gray-700',
                    'group flex justify-center rounded-md p-3 relative'
                  ]">
                    <component :is="item.icon" class="h-6 w-6 shrink-0" aria-hidden="true" />
                    <span class="sr-only">{{ item.name }}</span>
                    <div v-if="!item.current" class="absolute left-full top-1/2 -translate-y-1/2 ml-2 bg-gray-700 text-white text-xs rounded-md py-1 px-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 dark:bg-gray-300 dark:text-gray-900">{{ item.name }}</div>
                  </router-link>
                </li>
              </ul>
            </li>
            <li class="mt-auto">
              <router-link to="/settings" class="group flex justify-center rounded-md p-3 text-gray-700 hover:text-primary-600 hover:bg-gray-50">
                <cog-icon class="h-6 w-6 shrink-0 dark:text-gray-300" aria-hidden="true" />
                <span class="sr-only">Settings</span>
              </router-link>
            </li>
          </ul>
        </nav>
      </div>
    </div>

    <!-- Main content -->
    <div class="lg:pl-20 flex flex-col h-screen">
      <!-- Top bar -->
      <div class="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8 dark:border-gray-700">
        <!-- Mobile menu button -->
        <button type="button" class="text-gray-700 lg:hidden" @click="sidebarOpen = true">
          <span class="sr-only">Open sidebar</span>
          <bars-3-icon class="h-6 w-6" aria-hidden="true" />
        </button>

        <div class="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
          <!-- Search -->
          <form class="relative flex flex-1" @submit.prevent="searchStock">
            <label for="search-field" class="sr-only">Search</label>
            <magnifying-glass-icon class="pointer-events-none absolute inset-y-0 left-0 h-full w-5 text-gray-400" aria-hidden="true" />
            <input
              v-model="searchSymbol"
              id="search-field"
              class="block h-full w-full border-0 py-0 pl-8 pr-0 text-gray-900 placeholder:text-gray-400 focus:ring-0 sm:text-sm dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-300"
              placeholder="Search stocks..."
              type="search"
              name="search"
            />
          </form>

          <!-- Actions -->
          <div class="flex items-center gap-x-4 lg:gap-x-6">
            <!-- Profile dropdown -->
            <div class="relative">
              <button type="button" class="flex items-center gap-x-3 text-sm font-semibold leading-6 text-gray-900 dark:text-gray-100" @click="userMenuOpen = !userMenuOpen">
                <img class="h-8 w-8 rounded-full bg-gray-50" src="@/assets/avatar.jpg" alt="" />
                <span class="sr-only">User menu</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Dynamic content -->
      <main class="flex-1 overflow-y-auto">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- Mobile sidebar -->
    <transition enter-active-class="transition ease-out duration-300" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0">
      <div v-if="sidebarOpen" class="relative z-50 lg:hidden">
        <div class="fixed inset-0 bg-gray-900/80"></div>
        <div class="fixed inset-0 flex">
          <div class="relative flex w-full max-w-xs flex-1">
            <div class="absolute left-full top-0 flex w-16 justify-center pt-5 ">
              <button type="button" class="-m-2.5 p-2.5" @click="sidebarOpen = false">
                <span class="sr-only">Close sidebar</span>
                <x-mark-icon class="h-6 w-6 text-white" aria-hidden="true" />
              </button>
            </div>
            <!-- Mobile sidebar content -->
            <div class="flex grow flex-col gap-y-5 overflow-y-auto px-6 pb-4">
              <div class="flex h-16 shrink-0 items-center">
                <img class="h-8 w-auto" src="@/assets/logo.svg" alt="AI Stock Agent" />
              </div>
              <nav class="flex flex-1 flex-col">
                <ul role="list" class="flex flex-1 flex-col gap-y-7">
                  <li>
                    <ul role="list" class="-mx-2 space-y-1">
                      <li v-for="item in navigation" :key="item.name">
                        <router-link :to="item.href" :class="[
                          item.current ? 'bg-gray-50 text-primary-600 dark:bg-gray-700 dark:text-primary-500' : 'text-gray-700 hover:text-primary-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:text-primary-500 dark:hover:bg-gray-700',
                          'nav-link'
                        ]">
                          <component :is="item.icon" class="h-6 w-6 shrink-0" aria-hidden="true" />
                          {{ item.name }}
                        </router-link>
                      </li>
                    </ul>
                  </li>
                </ul>
              </nav>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import HomeIcon from 'vue-material-design-icons/Home.vue'
import ChartBarIcon from 'vue-material-design-icons/ChartBar.vue'
import CompareIcon from 'vue-material-design-icons/Compare.vue'
import StarIcon from 'vue-material-design-icons/Star.vue'
import InformationIcon from 'vue-material-design-icons/Information.vue'
import MagnifyIcon from 'vue-material-design-icons/Magnify.vue'
import CloseIcon from 'vue-material-design-icons/Close.vue'
import CogIcon from 'vue-material-design-icons/Cog.vue'
import MenuIcon from 'vue-material-design-icons/Menu.vue'
import BriefcaseIcon from 'vue-material-design-icons/Briefcase.vue'

const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(false)
const userMenuOpen = ref(false)
const searchSymbol = ref('')

const navigation = computed(() => [
  { name: 'Dashboard', href: '/', icon: HomeIcon, current: route.path === '/' },
  { name: 'Analysis', href: '/analysis', icon: ChartBarIcon, current: route.path.startsWith('/analysis') },
  { name: 'Compare', href: '/compare', icon: CompareIcon, current: route.path === '/compare' },
  { name: 'Portfolio', href: '/portfolio', icon: BriefcaseIcon, current: route.path === '/portfolio' },
  { name: 'Watchlist', href: '/watchlist', icon: StarIcon, current: route.path === '/watchlist' },
  { name: 'About', href: '/about', icon: InformationIcon, current: route.path === '/about' }
])

const searchStock = () => {
  if (searchSymbol.value) {
    router.push(`/symbol/${searchSymbol.value.toUpperCase()}`)
    searchSymbol.value = ''
  }
}
</script>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
