<template>
<!-- Add Stock Modal -->
<div v-if="showModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
    <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
    <h3 class="text-lg font-bold mb-4 dark:text-gray-100">Add New Stock</h3>
    <input
        v-model="newStockSymbol"
        type="text"
        placeholder="Enter stock symbol"
        class="border p-2 rounded mb-4 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-300"
        @keyup.enter="addStock"
    >
    <div class="flex justify-end space-x-2">
        <button @click="closeModal" class="px-4 py-2 rounded bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-300">
        Cancel
        </button>
        <button @click="addStock" class="px-4 py-2 rounded bg-primary-600 text-white hover:bg-primary-700 dark:bg-primary-700 dark:hover:bg-primary-600">
        Add
        </button>
    </div>
    </div>
</div>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { useStockStore } from '@/stores/stock'

const props = defineProps({
  showModal: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:showModal', 'stockAdded'])

const stockStore = useStockStore()
const newStockSymbol = ref('')

const closeModal = () => {
  emit('update:showModal', false)
}

const addStock = async () => {
  const symbol = newStockSymbol.value.toUpperCase().trim()
  if (symbol) {
    console.log('Adding stock:', symbol)
    await stockStore.addStock({ symbol })
    newStockSymbol.value = ''
    emit('stockAdded', symbol)
    closeModal()
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Escape') {
    closeModal()
  }
}

watch(() => props.showModal, (val) => {
  if (val) {
    window.addEventListener('keydown', handleKeydown)
  } else {
    window.removeEventListener('keydown', handleKeydown)
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>