<template>
  <div class="p-8 max-w-screen-2xl w-full">
    <h2 class="text-2xl font-semibold mb-6">{{ props.portfolioId ? 'Edit Portfolio' : 'New Portfolio' }}</h2>
    <form @submit.prevent="submitPortfolio" class="flex flex-col gap-6">
      <input v-model="form.name" class="input text-lg py-2" placeholder="Portfolio Name" required />
      <textarea v-model="form.rules" class="input text-base min-h-[80px] w-full" placeholder="Rules (optional)" rows="8"></textarea>
      <textarea v-model="form.report" class="input text-base min-h-[100px] w-full" placeholder="Report (optional)" rows="8"></textarea>
      <div class="flex gap-3 mt-2">
        <button type="submit" class="btn-primary text-lg px-6 py-2">Save</button>
        <button type="button" class="btn-secondary text-lg px-6 py-2" @click="$emit('close')">Cancel</button>
      </div>
      <div v-if="error" class="text-red-500 text-base mt-2">{{ error }}</div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const props = defineProps({
  show: Boolean,
  portfolioId: [String, Number]
})
const emit = defineEmits(['close', 'saved'])

const form = ref({
  name: '',
  rules: '',
  report: ''
})

import { watch } from 'vue'
// Fetch portfolio data if editing
watch(() => props.portfolioId, async (id) => {
  if (id) {
    try {
      const res = await axios.get(`/api/portfolio/${id}`)
      const val = res.data.data
      form.value = {
        id: val.id,
        name: val.name || '',
        rules: val.rules || '',
        report: val.report || ''
      }
    } catch (e) {
      form.value = { name: '', rules: '', report: '' }
    }
  } else {
    form.value = { name: '', rules: '', report: '' }
  }
}, { immediate: true })
const error = ref('')

const submitPortfolio = async () => {
  error.value = ''
  try {
    await axios.post('/api/portfolio', form.value)
    emit('saved')
    emit('close')
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Failed to save portfolio'
  }
}
</script>

<style scoped>
.input {
  @apply border rounded px-3 py-2 text-base dark:bg-gray-700 dark:text-gray-100 dark:border-gray-600 w-full resize-vertical;
}
.btn-primary {
  @apply bg-primary-600 text-white px-6 py-2 rounded hover:bg-primary-700 transition;
}
.btn-secondary {
  @apply bg-gray-200 text-gray-700 px-6 py-2 rounded hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 transition;
}
.min-h-\[80px\] {
  min-height: 80px;
}
.min-h-\[100px\] {
  min-height: 100px;
}
.text-lg {
  font-size: 1.125rem;
}
.text-base {
  font-size: 1rem;
}
.text-2xl {
  font-size: 1.5rem;
}
.resize-vertical {
  resize: vertical;
}
</style>
