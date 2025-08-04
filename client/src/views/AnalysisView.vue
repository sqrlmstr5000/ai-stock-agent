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
          <li v-for="stock in stocks" :key="stock.symbol" class="group relative">
            <a
              href="#"
              @click.prevent="goToSymbol(stock.symbol)"
              :class="[
                'block px-4 py-2 rounded pr-8',
                activeSymbol === stock.symbol
                  ? 'bg-gray-100 text-primary-600 dark:bg-gray-700 dark:text-primary-500'
                  : 'hover:bg-gray-200 text-gray-500 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-primary-500'
              ]"
            >
              <span>{{ stock.symbol }}</span>
              <button
                class="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-500 p-1 rounded focus:outline-none"
                title="Delete Stock"
                @click.stop="deleteStock(stock.id, stock.symbol)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span class="sr-only">Delete</span>
              </button>
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
const reportId = ref(null)

const loadStocks = async () => {
  await stockStore.fetchStocks()
}

const deleteStock = async (id, symbol) => {
  if (!confirm(`Delete stock ${symbol}?`)) return;
  try {
    await fetch(`/api/stocks/${id}`, { method: 'DELETE' });
    await loadStocks();
    // If the deleted symbol was active, clear it
    if (activeSymbol.value === symbol) {
      activeSymbol.value = null;
      router.push('/analysis');
    }
  } catch (e) {
    alert('Failed to delete stock.');
  }
}

const goToSymbol = (symbol) => {
  // Always set activeComponent to StockResearch, even if symbol is already active
  activeSymbol.value = symbol
  activeComponent.value = null
  setTimeout(() => {
    activeComponent.value = StockResearch
  }, 0)
  router.push(`/analysis/${symbol}`)
}

function updateFromRoute() {
  const { symbol, reportId: rid } = route.params
  activeSymbol.value = symbol || null
  reportId.value = rid || null
  // Determine which component to show
  if (route.name === 'analysis-symbol-fundamental') {
    activeComponent.value = StockResearch
  } else if (route.name === 'analysis-symbol-technical') {
    // Uncomment and use StockTechnical if you have it
    // activeComponent.value = StockTechnical
    activeComponent.value = StockResearch
  } else {
    activeComponent.value = StockResearch
  }
}

onMounted(() => {
  loadStocks()
  updateFromRoute()
})

watch(
  () => [route.name, route.params.symbol, route.params.reportId],
  () => {
    updateFromRoute()
  }
)
</script>