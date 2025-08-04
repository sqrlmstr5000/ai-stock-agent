<template>
  <div class="px-4 py-6 sm:px-6 lg:px-8 dark:bg-gray-800 min-h-screen">
    <!-- Market overview section -->
    <div class="mb-8">
      <h2 class="text-2xl font-bold leading-7 text-gray-900 dark:text-gray-100 sm:truncate sm:text-3xl sm:tracking-tight mb-6">
        Market Overview
      </h2>
      <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="index in marketIndices" :key="index.symbol" 
             class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-6 shadow-sm">
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ index.name }}</h3>
            <div :class="[index.change >= 0 ? 'text-green-600' : 'text-red-600', 'flex items-center']">
              <component 
                :is="index.change >= 0 ? ChevronUpIcon : ChevronDownIcon"
                class="h-5 w-5 mr-1"
              />
              {{ index.change }}%
            </div>
          </div>
          <p class="mt-2 text-2xl font-semibold text-gray-900 dark:text-gray-100">{{ index.value }}</p>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Volume: {{ index.volume }}</p>
        </div>
      </div>
    </div>

    <!-- Recent Analysis section -->
    <div class="mb-8">
      <h2 class="text-2xl font-bold leading-7 text-gray-900 dark:text-gray-100 sm:truncate sm:text-3xl sm:tracking-tight mb-6">
        Recent Analysis
      </h2>
      <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <router-link
          v-for="analysis in recentAnalysis"
          :key="analysis.symbol + '-' + (analysis.id || '')"
          :to="`/analysis/${analysis.symbol}/fundamental/${analysis.id}`"
          class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-6 shadow-sm block hover:bg-gray-50 dark:hover:bg-gray-800 transition"
        >
          <div class="flex items-start justify-between space-x-3">
            <div class="flex items-center">
              <ChartBarIcon class="h-6 w-6 text-primary-600 mr-2" aria-hidden="true" />
              <div class="min-w-0 flex-1">
                <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ analysis.symbol }}</h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Analyzed on {{ analysis.date }}</p>
                <p v-if="analysis.price_target_percent !== undefined" class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Price Target Change: {{ analysis.price_target_percent }}%
                </p>
              </div>
            </div>
            <div v-if="analysis.final_recommendation" class="flex-shrink-0 flex items-start ml-2">
              <span class="inline-block px-3 py-1 rounded-full text-sm font-bold bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 mt-1">
                {{ analysis.final_recommendation }}
              </span>
            </div>
          </div>
        </router-link>
      </div>
    </div>

    <!-- Watchlist section -->
    <div>
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold leading-7 text-gray-900 dark:text-gray-100 sm:truncate sm:text-3xl sm:tracking-tight">
          Watchlist
        </h2>
        <button type="button" class="rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
          Add Stock
        </button>
      </div>
      
      <!-- Stock list -->
      <div class="mt-6 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <ul role="list" class="divide-y divide-gray-200 dark:divide-gray-700">
          <li v-for="stock in watchlist" :key="stock.symbol" class="relative py-5 px-4 hover:bg-gray-50 dark:hover:bg-gray-800 sm:px-6">
            <router-link :to="`/symbol/${stock.symbol}`" class="block">
              <div class="flex items-center justify-between">
                <div>
                  <div class="flex items-center">
                    <p class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ stock.symbol }}</p>
                    <p class="ml-2 text-sm text-gray-500 dark:text-gray-400">{{ stock.name }}</p>
                  </div>
                  <div class="mt-1">
                    <p class="text-sm text-gray-500 dark:text-gray-400">{{ stock.sector }}</p>
                  </div>
                </div>
                <div class="text-right">
                  <p class="text-lg font-semibold text-gray-900 dark:text-gray-100">${{ stock.price }}</p>
                  <div :class="[stock.change >= 0 ? 'text-green-600' : 'text-red-600', 'flex items-center justify-end mt-1']">
                    <component 
                      :is="stock.change >= 0 ? ChevronUpIcon : ChevronDownIcon"
                      class="h-4 w-4 mr-1"
                    />
                    <span class="text-sm">{{ stock.change }}%</span>
                  </div>
                </div>
              </div>
            </router-link>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ChartBar from 'vue-material-design-icons/ChartBar.vue'
import ChevronUp from 'vue-material-design-icons/ChevronUp.vue'
import ChevronDown from 'vue-material-design-icons/ChevronDown.vue'

// Market indices data
const marketIndices = ref([
  { 
    symbol: 'SPY',
    name: 'S&P 500',
    value: '4,783.45',
    change: 1.2,
    volume: '85.2M'
  },
  {
    symbol: 'QQQ',
    name: 'NASDAQ',
    value: '16,245.32',
    change: -0.5,
    volume: '92.1M'
  },
  {
    symbol: 'DIA',
    name: 'Dow Jones',
    value: '37,654.23',
    change: 0.8,
    volume: '64.8M'
  }
])

// Recent analysis data (fetched from API)
const recentAnalysis = ref([])

onMounted(async () => {
  try {
    const res = await fetch('/api/stocks/research')
    const json = await res.json()
    if (json.data && Array.isArray(json.data)) {
      recentAnalysis.value = json.data.map(entry => ({
        id: entry.id,
        symbol: entry.symbol,
        date: new Date(entry.created_at).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        final_recommendation: entry.final_recommendation,
        price_target_percent: entry.price_target_percent
      }))
    }
  } catch (e) {
    // fallback or error handling
    recentAnalysis.value = []
  }
})

// Watchlist data
const watchlist = ref([
  { 
    symbol: 'AAPL',
    name: 'Apple Inc.',
    sector: 'Technology',
    price: '180.25',
    change: 2.5
  },
  { 
    symbol: 'MSFT',
    name: 'Microsoft Corp.',
    sector: 'Technology',
    price: '370.50',
    change: -0.5
  },
  { 
    symbol: 'NVDA',
    name: 'NVIDIA Corp.',
    sector: 'Technology',
    price: '485.90',
    change: 3.2
  },
  { 
    symbol: 'GOOGL',
    name: 'Alphabet Inc.',
    sector: 'Technology',
    price: '140.75',
    change: 1.8
  }
])
</script>
