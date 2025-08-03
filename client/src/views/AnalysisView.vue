<template>

  <div class="flex h-full">
    <!-- Stock Navigation -->
    <aside class="border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
      <nav>
        <ul>
          <li>
            <button @click="showModal = true" title="Add Stock" class="w-full flex justify-center items-center hover:bg-gray-200 dark:hover:bg-gray-700 px-4 py-2 rounded text-primary-600 dark:text-primary-500">
              <plus-icon class="h-6 w-6" />
              <span class="sr-only">Add Stock</span>
            </button>
          </li>
          <li v-for="stock in stocks" :key="stock.symbol">
            <a
              href="#"
              @click.prevent="goToSymbol(stock.symbol)"
              :class="[
                'block px-4 py-2 rounded',
                activeSymbol === stock.symbol
                  ? 'bg-gray-100 text-primary-600 dark:bg-gray-700 dark:text-primary-500'
                  : 'hover:bg-gray-200 text-gray-500 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-primary-500'
              ]"
            >
              <span>{{ stock.symbol }}</span>
            </a>
          </li>
        </ul>
      </nav>
    </aside>

    <!-- Sub Navigation (Same style as main nav) -->
    <nav class="flex flex-col items-center space-y-4 border-r border-gray-200 dark:border-gray-700 p-2">
      <a
        @click="activeComponent = StockResearch"
        title="Research"
        :class="[
          'cursor-pointer rounded p-2',
          activeComponent === StockResearch
            ? 'bg-gray-100 text-primary-600 dark:bg-gray-700 dark:text-primary-500'
            : 'text-gray-500 hover:bg-gray-100 hover:text-primary-600 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-primary-500'
        ]"
      >
        <chart-bar-icon class="h-6 w-6" />
        <span class="sr-only">Research</span>
      </a>
      <a
        @click="activeComponent = StockSettings"
        title="Settings"
        :class="[
          'cursor-pointer rounded p-2',
          activeComponent === StockSettings
            ? 'bg-gray-100 text-primary-600 dark:bg-gray-700 dark:text-primary-500'
            : 'text-gray-500 hover:bg-gray-100 hover:text-primary-600 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-primary-500'
        ]"
      >
        <cog-icon class="h-6 w-6" />
        <span class="sr-only">Settings</span>
      </a>
    </nav>

    <!-- Analysis Content Area -->
    <main class="flex-1 p-6 dark:bg-gray-800 rounded-lg overflow-y-auto">
      <component :is="activeComponent" :symbol="activeSymbol" v-if="activeComponent" />
      <div v-else>
        <h2 class="text-2xl font-bold mb-4 dark:text-gray-100">Analysis Dashboard</h2>
        <p class="dark:text-gray-300">Select a stock and a category to view detailed information.</p>
      </div>
    </main>

    <add-stock-modal 
      v-model:showModal="showModal"
      @stock-added="loadStocks"
    />
  </div>
</template>

<script setup>
import { onMounted, computed, shallowRef, ref, watch } from 'vue'
import { useStockStore } from '@/stores/stock'
import { useRouter, useRoute } from 'vue-router'
import HomeIcon from 'vue-material-design-icons/Home.vue'
import ChartBarIcon from 'vue-material-design-icons/ChartBar.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import CogIcon from 'vue-material-design-icons/Cog.vue'
import StockHome from '@/components/StockHome.vue'
import StockResearch from '@/components/StockResearch.vue'    
import StockSettings from '@/components/StockSettings.vue'
import AddStockModal from '@/components/AddStockModal.vue'

const stockStore = useStockStore()
const router = useRouter()
const route = useRoute()

const stocks = computed(() => stockStore.stocks)
const activeComponent = shallowRef(StockResearch)
const activeSymbol = ref(null)
const showModal = ref(false)

const loadStocks = async () => {
  await stockStore.fetchStocks()
}

const goToSymbol = (symbol) => {
  // Always set activeComponent to StockResearch, even if symbol is already active
  activeSymbol.value = symbol
  activeComponent.value = null
  // Next tick, set to StockResearch to force reload
  setTimeout(() => {
    activeComponent.value = StockResearch
  }, 0)
  router.push(`/analysis/${symbol}`)
}


onMounted(() => {
  loadStocks()
  if (route.params.symbol) {
    activeSymbol.value = route.params.symbol
    activeComponent.value = StockResearch
  }
})

watch(() => route.params.symbol, (newSymbol) => {
  if (newSymbol) {
    activeSymbol.value = newSymbol
    activeComponent.value = StockResearch
  }
})
</script>