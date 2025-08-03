<template>
  <div>
    <h2>Stock Settings</h2>
    <p v-if="symbol">Displaying settings for {{ symbol }}</p>
    <p v-else>No stock selected.</p>
  </div>
</template>

<script setup>
const props = defineProps({
  symbol: {
    type: String,
    required: true,
  },
});
</script>