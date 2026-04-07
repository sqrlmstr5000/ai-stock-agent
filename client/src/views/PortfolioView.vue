<template>
<div class="w-full min-h-screen flex items-start justify-center py-8 bg-transparent">
  <div class="w-full max-w-6xl">
    <h1 class="text-2xl font-bold mb-4">Portfolio</h1>
    <div class="mb-4 flex items-center gap-4">
      <label class="font-semibold">Select Portfolio:</label>
      <div class="flex flex-row gap-2 overflow-x-auto py-1">
        <button
          v-for="p in portfolios"
          :key="p.id"
          type="button"
          class="chip"
          :class="{ 'chip-selected': selectedPortfolioId === p.id }"
          @click="selectedPortfolioId = p.id"
        >
          {{ p.name }}
        </button>
      </div>
      <PencilOutlineIcon
        v-if="selectedPortfolioId"
        class="ml-2 w-5 h-5 cursor-pointer text-gray-600 hover:text-primary-600 transition"
        title="Edit Portfolio"
        role="button"
        tabindex="0"
        @click="editCurrentPortfolio"
        @keyup="onEditIconKeyup"
      />
      <PlusIcon
        class="ml-2 w-5 h-5 cursor-pointer text-gray-600 hover:text-primary-600 transition"
        title="New Portfolio"
        role="button"
        tabindex="0"
        @click="newPortfolio"
      />
    </div>
    <div class="bg-white dark:bg-gray-800 shadow rounded p-4 mb-8 w-full">
      <h2 class="text-xl font-semibold mb-2">Portfolio Summary</h2>
      <div v-if="portfolioLoading" class="text-center py-4">Loading...</div>
      <div v-else>
        <table class="min-w-full bg-white dark:bg-gray-800 rounded shadow w-full">
          <thead>
            <tr>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('symbol')">
                <span class="inline-block align-middle">Symbol</span>
                <span v-if="sortKey === 'symbol'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('shares')">
                <span class="inline-block align-middle">Shares</span>
                <span v-if="sortKey === 'shares'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('avg_cost')">
                <span class="inline-block align-middle">Avg Cost</span>
                <span v-if="sortKey === 'avg_cost'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('total_cost')">
                <span class="inline-block align-middle">Total Cost</span>
                <span v-if="sortKey === 'total_cost'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('close')">
                <span class="inline-block align-middle">Close</span>
                <span v-if="sortKey === 'close'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('historical.final_recommendation')">
                <span class="inline-block align-middle">Recommendation</span>
                <span v-if="sortKey === 'historical.final_recommendation'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('historical.final_confidence_score')">
                <span class="inline-block align-middle">Confidence</span>
                <span v-if="sortKey === 'historical.final_confidence_score'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('historical.price_target_percent')">
                <span class="inline-block align-middle">Target %</span>
                <span v-if="sortKey === 'historical.price_target_percent'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1 cursor-pointer" @click="sortPortfolio('gain_loss')">
                <span class="inline-block align-middle">Gain/Loss</span>
                <span v-if="sortKey === 'gain_loss'" class="inline-block align-middle ml-1" style="font-size:0.9em;">
                  <span v-if="sortAsc">▲</span>
                  <span v-else>▼</span>
                </span>
              </th>
              <th class="px-2 py-1">Info</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in portfolio" :key="row.symbol" class="border-t border-gray-200 dark:border-gray-700">
              <td class="px-2 py-1">
                <router-link :to="`/analysis/${row.symbol}`" class="text-primary-600 hover:underline">
                  {{ row.symbol }}
                </router-link>
              </td>
              <td class="px-2 py-1">{{ row.shares }}</td>
              <td class="px-2 py-1">{{ row.avg_cost }}</td>
              <td class="px-2 py-1">{{ row.total_cost }}</td>
              <td class="px-2 py-1">{{ row.close ?? '-' }}</td>
              <td class="px-2 py-1">{{ row.historical?.final_recommendation ?? '-' }}</td>
              <td class="px-2 py-1">{{ row.historical?.final_confidence_score ?? '-' }}</td>
              <td class="px-2 py-1">{{ row.historical?.price_target_percent ?? '-' }}</td>
              <td class="px-2 py-1">{{ row.gain_loss !== undefined && row.gain_loss !== null ? row.gain_loss : '-' }}</td>
              <td class="px-2 py-1">
                <span class="relative group">
                  <svg xmlns="http://www.w3.org/2000/svg" class="inline w-4 h-4 text-gray-500 cursor-pointer" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M12 20a8 8 0 100-16 8 8 0 000 16z" />
                  </svg>
                  <div class="absolute left-1/2 z-10 hidden group-hover:block bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap -translate-x-1/2 mt-1 shadow-lg min-w-max">
                    <div>Last Updated: <span>{{ row.data_updated_at ? new Date(row.data_updated_at).toLocaleString() : '-' }}</span></div>
                    <div>Report Date: <span>{{ row.historical?.report_date ?? '-' }}</span></div>
                  </div>
                </span>
              </td>
            </tr>
            <tr v-if="portfolio.length === 0">
              <td colspan="12" class="text-center py-4">No portfolio data.</td>
            </tr>
          </tbody>
        </table>
        <!-- Portfolio Analysis Buttons -->
        <div class="flex gap-4 mt-6">
            <button class="btn-primary" :disabled="analyzing" @click="analyzePortfolio">
                <span v-if="analyzing">Analyzing...</span>
                <span v-else>Analyze</span>
            </button>
            <button class="btn-secondary" @click="showReportsModal = true">View Reports</button>
        </div>
        <div v-if="showPortfolioEditModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
          <div class="absolute inset-0" @click="showPortfolioEditModal = false"></div>
          <div class="relative w-full max-w-5xl max-h-full bg-white dark:bg-gray-900 rounded shadow-lg overflow-y-auto flex flex-col">
            <PortfolioEditModal :show="showPortfolioEditModal" :portfolio-id="editPortfolioId" @close="showPortfolioEditModal = false" @saved="onPortfolioSaved" />
          </div>
        </div>
        <div v-if="showReportsModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
          <div class="absolute inset-0" @click="showReportsModal = false"></div>
          <div 
            class="relative w-full h-full max-w-5xl max-h-full bg-white dark:bg-gray-900 rounded shadow-lg overflow-y-auto flex flex-col"
            tabindex="0"
            @keydown.esc="showReportsModal = false"
            ref="reportsModalRef"
          >
            <PortfolioResearchModal :show="showReportsModal" :portfolio-id="selectedPortfolioId" @close="showReportsModal = false" />
          </div>
        </div>
        </div>
    </div>
    <form @submit.prevent="addTransactions" class="bg-white dark:bg-gray-800 shadow rounded p-4 mb-6 flex flex-col gap-4 w-full">
      <div v-for="(entry, idx) in forms" :key="idx" class="flex flex-nowrap gap-2 md:gap-4 mb-2 w-full">
        <input v-model="entry.symbol" placeholder="Symbol" class="input" required maxlength="10" />
        <select v-model="entry.action" class="input" required>
          <option value="">Action</option>
          <option value="BUY">Buy</option>
          <option value="SELL">Sell</option>
          <option value="DIVIDEND_REINVESTMENT">Dividend Reinvestment</option>
        </select>
        <input v-model.number="entry.shares" type="number" min="0.0001" step="0.0001" placeholder="Shares" class="input" required />
        <input v-model.number="entry.price" type="number" min="0.0001" step="0.0001" placeholder="Price" class="input" required />
        <input v-model="entry.purchase_date" type="date" class="input" required />
        <button v-if="forms.length > 1" type="button" class="btn-secondary" @click="removeForm(idx)">-</button>
        <button v-if="idx === forms.length - 1" type="button" class="btn-secondary" @click="addForm">+</button>
      </div>
      <button type="submit" class="btn-primary self-end">Add All</button>
    </form>
    <div class="bg-white dark:bg-gray-800 shadow rounded p-4 mb-6 w-full">
      <h3 class="font-semibold mb-2">Import Transactions</h3>
      <p class="text-xs text-gray-500 mb-1 border border-gray-200 dark:border-gray-700 rounded px-2 py-1 inline-block bg-gray-50 dark:bg-gray-900">
        <span class="font-mono">{symbol} {shares} {price} {date}</span>
      </p>
      <textarea v-model="importText" class="input w-full mb-2" rows="3" placeholder="Paste tab-separated transactions in the format here..."></textarea>
      <button class="btn-primary" @click="parseImport">Parse & Fill</button>
    </div>
    <div v-if="loading" class="text-center py-4">Loading...</div>
    <div v-else class="w-full">
      <h2 class="text-xl font-semibold mb-2">Transaction Log</h2>
      <table class="min-w-full bg-white dark:bg-gray-800 rounded shadow w-full">
        <thead>
          <tr>
            <th class="px-2 py-1">Symbol</th>
            <th class="px-2 py-1">Action</th>
            <th class="px-2 py-1">Shares</th>
            <th class="px-2 py-1">Price</th>
            <th class="px-2 py-1">Date</th>
            <th class="px-2 py-1">Delete</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="txn in transactions" :key="txn.id" class="border-t border-gray-200 dark:border-gray-700">
            <td class="px-2 py-1">{{ txn.symbol }}</td>
            <td class="px-2 py-1">{{ txn.action }}</td>
            <td class="px-2 py-1">{{ txn.shares }}</td>
            <td class="px-2 py-1">{{ txn.price }}</td>
            <td class="px-2 py-1">{{ txn.purchase_date }}</td>
            <td class="px-2 py-1">
              <button @click="deleteTransaction(txn.id)" class="text-red-500 hover:underline">Delete</button>
            </td>
          </tr>
          <tr v-if="transactions.length === 0">
            <td colspan="6" class="text-center py-4">No transactions found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Cash Balance Section -->
    <div class="bg-white dark:bg-gray-800 shadow rounded p-4 mt-8 w-full">
      <h2 class="text-xl font-semibold mb-2">Cash Balance</h2>
      <div class="flex flex-col md:flex-row md:items-center md:gap-8 mb-4">
        <div class="mb-2 md:mb-0">
          <span class="font-semibold">Current Cash Balance:</span>
          <span class="text-lg font-mono">${{ cashBalance !== null ? cashBalance.toFixed(2) : '...' }}</span>
        </div>
        <form @submit.prevent="addCashTransaction" class="flex flex-wrap gap-2 items-end">
          <select v-model="cashForm.action" class="input" required>
            <option value="">Action</option>
            <option value="DEPOSIT">Deposit</option>
            <option value="WITHDRAWAL">Withdrawal</option>
          </select>
          <input v-model.number="cashForm.amount" type="number" min="0.01" step="0.01" placeholder="Amount" class="input" required />
          <input v-model="cashForm.transaction_date" type="date" class="input" :max="today" required />
          <input v-model="cashForm.note" type="text" class="input" placeholder="Note (optional)" />
          <button type="submit" class="btn-primary">Add</button>
        </form>
      </div>
      <div>
        <h3 class="font-semibold mb-2">Cash Transaction History</h3>
        <table class="min-w-full bg-white dark:bg-gray-800 rounded shadow w-full">
          <thead>
            <tr>
              <th class="px-2 py-1">Action</th>
              <th class="px-2 py-1">Amount</th>
              <th class="px-2 py-1">Date</th>
              <th class="px-2 py-1">Note</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="txn in cashTransactions" :key="txn.id" class="border-t border-gray-200 dark:border-gray-700">
              <td class="px-2 py-1">{{ txn.action }}</td>
              <td class="px-2 py-1">${{ txn.amount.toFixed(2) }}</td>
              <td class="px-2 py-1">{{ txn.transaction_date }}</td>
              <td class="px-2 py-1">{{ txn.note }}</td>
            </tr>
            <tr v-if="cashTransactions.length === 0">
              <td colspan="4" class="text-center py-4">No cash transactions found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
</template>


<script setup>
// Sorting state
const sortKey = ref('symbol')
const sortAsc = ref(true)

function getNestedValue(obj, path) {
  return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : null), obj)
}

function sortPortfolio(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
  portfolio.value = [...portfolio.value].sort((a, b) => {
    let aVal = key.includes('.') ? getNestedValue(a, key) : a[key]
    let bVal = key.includes('.') ? getNestedValue(b, key) : b[key]
    // Handle nulls and undefined
    if (aVal == null && bVal == null) return 0
    if (aVal == null) return sortAsc.value ? 1 : -1
    if (bVal == null) return sortAsc.value ? -1 : 1
    // Numeric sort if both are numbers
    if (!isNaN(parseFloat(aVal)) && !isNaN(parseFloat(bVal))) {
      return sortAsc.value ? aVal - bVal : bVal - aVal
    }
    // Date sort for Last Updated and Report Date
    if (key === 'data_updated_at' || key === 'historical.report_date') {
      // Use dayjs to parse '%Y-%m-%d %H:%M' format
      let aDate = aVal ? dayjs(aVal, 'YYYY-MM-DD HH:mm').valueOf() : -Infinity
      let bDate = bVal ? dayjs(bVal, 'YYYY-MM-DD HH:mm').valueOf() : -Infinity
      if (isNaN(aDate)) aDate = -Infinity
      if (isNaN(bDate)) bDate = -Infinity
      return sortAsc.value ? aDate - bDate : bDate - aDate
    }
    // String sort
    return sortAsc.value ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal))
  })
}
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import axios from 'axios'
import dayjs from 'dayjs'
import customParseFormat from 'dayjs/plugin/customParseFormat'
dayjs.extend(customParseFormat)
import PortfolioResearchModal from '../components/PortfolioResearchModal.vue'
import PortfolioEditModal from '../components/PortfolioEditModal.vue'
import PencilOutlineIcon from 'vue-material-design-icons/PencilOutline.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
const portfolios = ref([])
const selectedPortfolioId = ref(null)
const editPortfolioId = ref(null)

const fetchPortfolios = async () => {
  try {
    const res = await axios.get('/api/portfolios')
    portfolios.value = res.data.data || []
    if (portfolios.value.length > 0 && selectedPortfolioId.value === null) {
      selectedPortfolioId.value = portfolios.value[0].id
    }
  } catch (e) {
    portfolios.value = []
  }
}

// --- Portfolio Analysis State ---
const analyzing = ref(false)
const showReportsModal = ref(false)
const showPortfolioEditModal = ref(false)
function editCurrentPortfolio() {
  if (selectedPortfolioId.value) {
    editPortfolioId.value = selectedPortfolioId.value
    showPortfolioEditModal.value = true
  }
}

function newPortfolio() {
  editPortfolioId.value = null
  showPortfolioEditModal.value = true
}
// Handler for when a new portfolio is saved
const onPortfolioSaved = () => {
  showPortfolioEditModal.value = false
  // Optionally, refresh portfolio list or show a notification
}

const analyzePortfolio = async () => {
  analyzing.value = true
  try {
    await axios.post(`/api/portfolio/${selectedPortfolioId.value}/analyze`)
    // Optionally, show a toast or notification
    // Optionally, refresh reports modal if open
  } catch (e) {
    alert('Failed to analyze portfolio')
  }
  analyzing.value = false
}

const portfolio = ref([])
const portfolioLoading = ref(false)

const emptyForm = () => ({ symbol: '', action: 'BUY', shares: '', price: '', purchase_date: '' })
const forms = ref([emptyForm()])
const importText = ref('')
const transactions = ref([])

const loading = ref(false)

// --- Cash Balance State ---
const cashBalance = ref(null)
const cashTransactions = ref([])
const cashForm = ref({
  action: '',
  amount: '',
  transaction_date: '',
  note: ''
})
const today = computed(() => new Date().toISOString().slice(0, 10))
// --- Cash Balance Methods ---
const fetchCashBalance = async () => {
  try {
    const res = await axios.get(`/api/portfolio/${selectedPortfolioId.value}/cash/balance`)
    cashBalance.value = res.data.data.balance
  } catch (e) {
    cashBalance.value = null
  }
}

const fetchCashTransactions = async () => {
  try {
    const res = await axios.get(`/api/portfolio/${selectedPortfolioId.value}/cash/transactions`)
    cashTransactions.value = res.data.data || []
  } catch (e) {
    cashTransactions.value = []
  }
}

const addCashTransaction = async () => {
  if (!cashForm.value.action || !cashForm.value.amount || !cashForm.value.transaction_date) return
  try {
    await axios.post(`/api/portfolio/${selectedPortfolioId.value}/cash/transaction`, cashForm.value)
    await fetchCashBalance()
    await fetchCashTransactions()
    cashForm.value = { action: '', amount: '', transaction_date: '', note: '' }
  } catch (e) {
    alert('Failed to add cash transaction')
  }
}

const fetchTransactions = async () => {
  loading.value = true
  try {
    const res = await axios.get(`/api/portfolio/${selectedPortfolioId.value}/transactions`)
    transactions.value = res.data.data || []
  } catch (e) {
    transactions.value = []
  }
  loading.value = false
}

const fetchPortfolio = async () => {
  portfolioLoading.value = true
  try {
    const res = await axios.get(`/api/portfolio/${selectedPortfolioId.value}/holdings`)
    portfolio.value = res.data.data || []
  } catch (e) {
    portfolio.value = []
  }
  portfolioLoading.value = false
}

const addForm = () => {
  forms.value.push(emptyForm())
}
const removeForm = (idx) => {
  if (forms.value.length > 1) forms.value.splice(idx, 1)
}

const addTransactions = async () => {
  try {
    for (const entry of forms.value) {
      await axios.post(`/api/portfolio/${selectedPortfolioId.value}/transactions`, entry)
    }
    await fetchTransactions()
    await fetchPortfolio()
    forms.value = [emptyForm()]
  } catch (e) {
    alert('Failed to add transaction(s)')
  }
}

const parseImport = () => {
  if (!importText.value.trim()) return
  const lines = importText.value.trim().split(/\r?\n/)
  const parsed = lines.map(line => {
    // Format: SYMBOL\tSHARES\tPRICE\tMM/DD/YYYY
    const [symbol, shares, price, date] = line.split(/\t|\s{2,}/)
    return {
      symbol: symbol ? symbol.trim().toUpperCase() : '',
      action: 'BUY',
      shares: shares ? parseFloat(shares) : '',
      price: price ? parseFloat(price) : '',
      purchase_date: date ? toISODate(date) : ''
    }
  })
  // Append parsed entries to forms
  forms.value.push(...parsed)
}

function toISODate(dateStr) {
  // Accepts MM/DD/YYYY or M/D/YYYY or M/D/YY
  const [m, d, y] = dateStr.split('/')
  let year = y.length === 2 ? '20' + y : y
  return `${year}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`
}

const deleteTransaction = async (id) => {
  if (!confirm('Delete this transaction?')) return
  try {
    await axios.delete(`/api/portfolio/${selectedPortfolioId.value}/transaction/${id}`)
    await fetchTransactions()
    await fetchPortfolio()
  } catch (e) {
    alert('Failed to delete transaction')
  }
}

// Ref for modal to focus for esc key
const reportsModalRef = ref(null)

onMounted(() => {
  fetchPortfolios()
})

watch(showReportsModal, async (val) => {
  if (val) {
    await nextTick()
    if (reportsModalRef.value) reportsModalRef.value.focus()
  }
})

// Watch for selectedPortfolioId changes and load data when set
watch(selectedPortfolioId, (newVal) => {
  if (newVal) {
    fetchTransactions()
    fetchPortfolio()
    fetchCashBalance()
    fetchCashTransactions()
  }
}, { immediate: true })
</script>

<style scoped>
.fixed {
  position: fixed;
}
.inset-0 {
  top: 0; left: 0; right: 0; bottom: 0;
}
.z-50 {
  z-index: 50;
}
.bg-black.bg-opacity-70 {
  background: rgba(0,0,0,0.7);
}
.max-w-5xl {
  max-width: 80vw;
}
.max-h-full {
  max-height: 100vh;
}
.overflow-y-auto {
  overflow-y: auto;
}
.input {
  @apply border rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-100 dark:border-gray-600;
}
.btn-primary {
  @apply bg-primary-600 text-white px-3 py-1 rounded hover:bg-primary-700 transition;
}
.btn-secondary {
  @apply bg-gray-200 text-gray-700 px-2 py-1 rounded hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 transition;
}
.chip {
  @apply px-3 py-1 rounded-full border border-gray-300 bg-gray-100 text-gray-700 cursor-pointer transition hover:bg-primary-100 hover:border-primary-400 dark:bg-gray-700 dark:text-gray-100 dark:border-gray-600 dark:hover:bg-primary-900 dark:hover:border-primary-400;
  outline: none;
}
.chip-selected {
  @apply bg-primary-600 text-white border-primary-600 dark:bg-primary-700 dark:text-white dark:border-primary-700;
}
</style>
