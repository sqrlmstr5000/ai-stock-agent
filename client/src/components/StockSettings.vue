<template>
  <div>
    <h2>Stock Settings</h2>
    <p v-if="symbol">Displaying settings for {{ symbol }}</p>
    <p v-else>No stock selected.</p>

    <div class="mt-4" v-if="portfolios.length > 0">
      <label for="portfolio-select" class="block mb-1">Monitor for Swing Trades:</label>
      <select id="portfolio-select" v-model="selectedPortfolioId" class="border rounded py-1 px-10 bg-white text-gray-900 text-left focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option v-for="p in portfolios" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button class="ml-2 px-3 py-1 bg-blue-600 rounded" :disabled="!selectedPortfolioId || saving" @click="saveSwing">
        {{ saving ? 'Saving...' : 'Save Swing' }}
      </button>
    </div>

    <div v-else class="mt-4">
      <p>No portfolios available.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps({
  symbol: {
    type: String,
    required: true,
  },
})

const portfolios = ref([])
const selectedPortfolioId = ref(null)
const saving = ref(false)

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

onMounted(() => {
  fetchPortfolios()
})

const saveSwing = async () => {
  if (!props.symbol || !selectedPortfolioId.value) return
  saving.value = true
  try {
    const res = await axios.post(`/api/stock/${props.symbol}/swing/${selectedPortfolioId.value}`)
    alert(res.data.message || 'Swing saved')
  } catch (e) {
    console.error(e)
    alert('Error saving swing')
  } finally {
    saving.value = false
  }
}
</script>