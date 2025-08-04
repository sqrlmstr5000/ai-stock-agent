<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-semibold"></h2>
      <div class="flex gap-2">
        <button class="btn-secondary" @click="prevReport" :disabled="currentIndex === 0">Previous</button>
        <button class="btn-secondary" @click="nextReport" :disabled="currentIndex === reports.length - 1">Next</button>
        <button class="btn-secondary" @click="$emit('close')">Close</button>
      </div>
    </div>
    <div v-if="loading" class="text-center py-4">Loading...</div>
    <div v-else-if="reports.length === 0" class="text-center py-4">No portfolio research reports found.</div>
    <div v-else class="prose max-w-none p-4" v-html="renderedReport"></div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const props = defineProps({
  show: Boolean
})
const emit = defineEmits(['close'])

const reports = ref([])
const currentIndex = ref(0)
const loading = ref(false)
const md = new MarkdownIt()

const renderedReport = computed(() => {
  if (reports.value.length === 0) return ''
  const report = reports.value[currentIndex.value]
  let mdText = `# Portfolio Research Report\n\n`
  mdText += `**Date:** ${report.report_date}\n\n`
  if (report.dca_analysis) {
    mdText += `## DCA Analysis\n${report.dca_analysis}\n\n`
  }
  if (report.economic_analysis) {
    mdText += `## Economic Analysis\n${report.economic_analysis}\n\n`
  }
  if (report.portfolio_analysis) {
    mdText += `## Portfolio Analysis\n${report.portfolio_analysis}\n\n`
  }
  if (report.notes) {
    mdText += `## Notes\n${report.notes}\n\n`
  }
  return md.render(mdText)
})

const fetchReports = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/portfolio/research?limit=20')
    reports.value = res.data.data || []
    currentIndex.value = 0
  } catch (e) {
    reports.value = []
  }
  loading.value = false
}

const nextReport = () => {
  if (currentIndex.value < reports.value.length - 1) currentIndex.value++
}
const prevReport = () => {
  if (currentIndex.value > 0) currentIndex.value--
}

watch(() => props.show, (val) => {
  if (val) fetchReports()
})

onMounted(() => {
  if (props.show) fetchReports()
})
</script>

<style>
.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6 {
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}
.prose h1 { font-size: 2em; }
.prose h2 { font-size: 1.5em; }
.prose h3 { font-size: 1.25em; }
.prose p { margin-bottom: 1em; }
.prose ul { list-style-type: disc; padding-left: 2em; margin-bottom: 1em; }
.prose strong { font-weight: bold; }
</style>
