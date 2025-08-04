<template>
  <div class="p-8">
    <div class="mb-8">
      <h2 class="text-xl font-semibold mb-2">Scheduled Jobs</h2>
      <table class="min-w-full bg-white dark:bg-gray-800 border rounded mb-4">
        <thead>
          <tr>
            <th class="px-4 py-2 border-b">Job ID</th>
            <th class="px-4 py-2 border-b">Name</th>
            <th class="px-4 py-2 border-b">Next Run</th>
            <th class="px-4 py-2 border-b">Trigger</th>
            <th class="px-4 py-2 border-b">Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td class="px-4 py-2 border-b">{{ job.id }}</td>
            <td class="px-4 py-2 border-b">{{ job.name }}</td>
            <td class="px-4 py-2 border-b">{{ job.next_run_time }}</td>
            <td class="px-4 py-2 border-b">{{ job.trigger }}</td>
            <td class="px-4 py-2 border-b">
              <button @click="runJob(job.id)" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-3 rounded">Run</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="jobMessage" class="text-green-600 mb-2">{{ jobMessage }}</div>
    </div>
    <h1 class="text-2xl font-bold mb-6">Settings & Usage</h1>
    <div class="mb-8">
    <h2 class="text-xl font-semibold mb-2">Provider Usage</h2>
      <div class="flex items-center mb-2">
        <label for="providerStart" class="mr-2">Start Date:</label>
        <input id="providerStart" type="date" v-model="providerStart" class="border rounded px-2 py-1 mr-4" />
        <label for="providerEnd" class="mr-2">End Date:</label>
        <input id="providerEnd" type="date" v-model="providerEnd" class="border rounded px-2 py-1" />
      </div>
      <table class="min-w-full bg-white dark:bg-gray-800 border rounded">
        <thead>
          <tr>
            <th class="px-4 py-2 border-b">Date</th>
            <th class="px-4 py-2 border-b">Step</th>
            <th class="px-4 py-2 border-b">Provider</th>
            <th class="px-4 py-2 border-b">Count</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredProviderUsage" :key="row.date + row.provider">
            <td class="px-4 py-2 border-b">{{ row.created_at }}</td>
            <td class="px-4 py-2 border-b">{{ row.step }}</td>
            <td class="px-4 py-2 border-b">{{ row.provider }}</td>
            <td class="px-4 py-2 border-b">{{ row.count }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td class="px-4 py-2 font-bold" colspan="2">Total</td>
            <td class="px-4 py-2 font-bold">{{ providerTotal }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div>
      <h2 class="text-xl font-semibold mb-2">Token Usage</h2>
      <div class="flex items-center mb-2">
        <label for="tokenStart" class="mr-2">Start Date:</label>
        <input id="tokenStart" type="date" v-model="tokenStart" class="border rounded px-2 py-1 mr-4" />
        <label for="tokenEnd" class="mr-2">End Date:</label>
        <input id="tokenEnd" type="date" v-model="tokenEnd" class="border rounded px-2 py-1" />
      </div>
      <table class="min-w-full bg-white dark:bg-gray-800 border rounded">
        <thead>
          <tr>
            <th class="px-4 py-2 border-b">Date</th>
            <th class="px-4 py-2 border-b">Step</th>
            <th class="px-4 py-2 border-b">Total Tokens</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredTokenUsage" :key="row.date + row.step">
            <td class="px-4 py-2 border-b">{{ row.date }}</td>
            <td class="px-4 py-2 border-b">{{ row.step }}</td>
            <td class="px-4 py-2 border-b">{{ row.total_tokens }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td class="px-4 py-2 font-bold" colspan="2">Total</td>
            <td class="px-4 py-2 font-bold">{{ tokenTotal }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<script setup>

import { ref, computed, onMounted } from 'vue'
const jobs = ref([])
const jobMessage = ref('')

const providerUsage = ref([])
const tokenUsage = ref([])
const providerStart = ref('')
const providerEnd = ref('')
const tokenStart = ref('')
const tokenEnd = ref('')

onMounted(async () => {
  const providerRes = await fetch('/api/usage/provider')
  const providerJson = await providerRes.json()
  providerUsage.value = providerJson.data || []
const tokenRes = await fetch('/api/usage/token')
const tokenJson = await tokenRes.json()
tokenUsage.value = tokenJson.data || []
  // Fetch scheduled jobs
  const jobsRes = await fetch('/api/scheduler/jobs')
  const jobsJson = await jobsRes.json()
  jobs.value = jobsJson.data || []
})
async function runJob(jobId) {
  jobMessage.value = ''
  try {
    const res = await fetch(`/api/scheduler/trigger/${jobId}`, { method: 'POST' })
    if (res.ok) {
      const json = await res.json()
      jobMessage.value = json.message || `Job ${jobId} triggered.`
    } else {
      const err = await res.json()
      jobMessage.value = err.detail || `Failed to trigger job ${jobId}`
    }
  } catch (e) {
    jobMessage.value = `Error triggering job: ${e}`
  }
}

const filteredProviderUsage = computed(() => {
  return providerUsage.value.filter(row => {
    const d = new Date(row.date)
    const start = providerStart.value ? new Date(providerStart.value) : null
    const end = providerEnd.value ? new Date(providerEnd.value) : null
    return (!start || d >= start) && (!end || d <= end)
  })
})
const providerTotal = computed(() => filteredProviderUsage.value.reduce((sum, row) => sum + row.count, 0))

const filteredTokenUsage = computed(() => {
  return tokenUsage.value.filter(row => {
    const d = new Date(row.date)
    const start = tokenStart.value ? new Date(tokenStart.value) : null
    const end = tokenEnd.value ? new Date(tokenEnd.value) : null
    return (!start || d >= start) && (!end || d <= end)
  })
})
const tokenTotal = computed(() => filteredTokenUsage.value.reduce((sum, row) => sum + (row.total_tokens || 0), 0))
</script>

<style scoped>
table {
  border-collapse: collapse;
}
th, td {
  border: 1px solid #e5e7eb;
}
</style>
