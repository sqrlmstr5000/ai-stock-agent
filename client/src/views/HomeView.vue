<template>
  <div class="px-4 py-6 sm:px-6 lg:px-8">
    <!-- Market overview section -->
    <div class="mb-8">
      <h2 class="text-2xl font-bold leading-7 text-gray-900 sm:truncate sm:text-3xl sm:tracking-tight mb-6">
        Market Overview
      </h2>
      <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="index in marketIndices" :key="index.symbol" 
             class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-900">{{ index.name }}</h3>
            <div :class="[index.change >= 0 ? 'text-green-600' : 'text-red-600', 'flex items-center']">
              <component 
                :is="index.change >= 0 ? ChevronUpIcon : ChevronDownIcon"
                class="h-5 w-5 mr-1"
              />
              {{ index.change }}%
            </div>
          </div>
          <p class="mt-2 text-2xl font-semibold text-gray-900">{{ index.value }}</p>
          <p class="mt-1 text-sm text-gray-500">Volume: {{ index.volume }}</p>
        </div>
      </div>
    </div>

    <!-- Recent Analysis section -->
    <div class="mb-8">
      <h2 class="text-2xl font-bold leading-7 text-gray-900 sm:truncate sm:text-3xl sm:tracking-tight mb-6">
        Recent Analysis
      </h2>
      <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="analysis in recentAnalysis" :key="analysis.symbol" 
             class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div class="flex items-center space-x-3">
            <div class="flex-shrink-0">
              <ChartBarIcon class="h-6 w-6 text-primary-600" aria-hidden="true" />
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="text-lg font-semibold text-gray-900">{{ analysis.symbol }}</h3>
              <p class="mt-1 text-sm text-gray-500">Analyzed on {{ analysis.date }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Watchlist section -->
    <div>
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold leading-7 text-gray-900 sm:truncate sm:text-3xl sm:tracking-tight">
          Watchlist
        </h2>
        <button type="button" class="rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
          Add Stock
        </button>
      </div>
      
      <!-- Stock list -->
      <div class="mt-6 overflow-hidden rounded-xl border border-gray-200 bg-white">
        <ul role="list" class="divide-y divide-gray-200">
          <li v-for="stock in watchlist" :key="stock.symbol" class="relative py-5 px-4 hover:bg-gray-50 sm:px-6">
            <router-link :to="`/symbol/${stock.symbol}`" class="block">
              <div class="flex items-center justify-between">
                <div>
                  <div class="flex items-center">
                    <p class="text-lg font-semibold text-gray-900">{{ stock.symbol }}</p>
                    <p class="ml-2 text-sm text-gray-500">{{ stock.name }}</p>
                  </div>
                  <div class="mt-1">
                    <p class="text-sm text-gray-500">{{ stock.sector }}</p>
                  </div>
                </div>
                <div class="text-right">
                  <p class="text-lg font-semibold text-gray-900">${{ stock.price }}</p>
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
import { ref } from 'vue'
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

// Recent analysis data
const recentAnalysis = ref([
  { symbol: 'TSLA', date: 'July 16, 2025' },
  { symbol: 'META', date: 'July 15, 2025' },
  { symbol: 'AMD', date: 'July 15, 2025' }
])

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
