<template>
<div class="w-full min-h-screen flex items-start justify-center py-8 bg-transparent">
  <div class="w-full max-w-6xl">
    <h1 class="text-2xl font-bold mb-4">Portfolio</h1>
    <div class="bg-white dark:bg-gray-800 shadow rounded p-4 mb-8 w-full">
      <h2 class="text-xl font-semibold mb-2">Portfolio Summary</h2>
      <div v-if="portfolioLoading" class="text-center py-4">Loading...</div>
      <div v-else>
        <table class="min-w-full bg-white dark:bg-gray-800 rounded shadow w-full">
          <thead>
            <tr>
              <th class="px-2 py-1">Symbol</th>
              <th class="px-2 py-1">Shares</th>
              <th class="px-2 py-1">Avg Cost</th>
              <th class="px-2 py-1">Total Cost</th>
              <th class="px-2 py-1">Buys</th>
              <th class="px-2 py-1">Sells</th>
              <th class="px-2 py-1">Dividends</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in portfolio" :key="row.symbol" class="border-t border-gray-200 dark:border-gray-700">
              <td class="px-2 py-1">{{ row.symbol }}</td>
              <td class="px-2 py-1">{{ row.shares }}</td>
              <td class="px-2 py-1">{{ row.avg_cost }}</td>
              <td class="px-2 py-1">{{ row.total_cost }}</td>
              <td class="px-2 py-1">{{ row.buys }}</td>
              <td class="px-2 py-1">{{ row.sells }}</td>
              <td class="px-2 py-1">{{ row.dividends }}</td>
            </tr>
            <tr v-if="portfolio.length === 0">
              <td colspan="7" class="text-center py-4">No portfolio data.</td>
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
        <div v-if="showReportsModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70">
          <div class="absolute inset-0" @click="showReportsModal = false"></div>
          <div class="relative w-full h-full max-w-5xl max-h-full bg-white dark:bg-gray-900 rounded shadow-lg overflow-y-auto flex flex-col">
            <PortfolioResearchModal :show="showReportsModal" @close="showReportsModal = false" />
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
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import PortfolioResearchModal from '../components/PortfolioResearchModal.vue'
// --- Portfolio Analysis State ---
const analyzing = ref(false)
const showReportsModal = ref(false)

const analyzePortfolio = async () => {
  analyzing.value = true
  try {
    await axios.post('/api/portfolio/analyze')
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
    const res = await axios.get('/api/cash/balance')
    cashBalance.value = res.data.data.balance
  } catch (e) {
    cashBalance.value = null
  }
}

const fetchCashTransactions = async () => {
  try {
    const res = await axios.get('/api/cash/transactions')
    cashTransactions.value = res.data.data || []
  } catch (e) {
    cashTransactions.value = []
  }
}

const addCashTransaction = async () => {
  if (!cashForm.value.action || !cashForm.value.amount || !cashForm.value.transaction_date) return
  try {
    await axios.post('/api/cash/transaction', cashForm.value)
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
    const res = await axios.get('/api/transactions')
    transactions.value = res.data.data || []
  } catch (e) {
    transactions.value = []
  }
  loading.value = false
}

const fetchPortfolio = async () => {
  portfolioLoading.value = true
  try {
    const res = await axios.get('/api/portfolio')
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
      await axios.post('/api/transactions', entry)
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
    await axios.delete(`/api/transaction/${id}`)
    await fetchTransactions()
    await fetchPortfolio()
  } catch (e) {
    alert('Failed to delete transaction')
  }
}

onMounted(() => {
  fetchTransactions()
  fetchPortfolio()
  fetchCashBalance()
  fetchCashTransactions()
})
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
</style>
