<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-semibold"></h2>
      <div class="flex gap-2">
        <button class="btn-secondary" @click="prevReport" :disabled="currentIndex === 0">Previous</button>
        <button class="btn-secondary" @click="nextReport" :disabled="currentIndex === reports.length - 1">Next</button>
        <button class="btn-secondary" @click="deleteCurrentReport" :disabled="loading || !currentReport">Delete</button>
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
import markdownItAnchor from 'markdown-it-anchor'

const props = defineProps({
  show: Boolean,
  portfolioId: [String, Number]
})
const emit = defineEmits(['close'])


const reports = ref([])
const currentIndex = ref(0)
const loading = ref(false)
const currentReport = ref(null)
const md = new MarkdownIt()
md.use(markdownItAnchor, {
  slugify: s => s.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-'),
})

const renderedReport = computed(() => {
  if (!currentReport.value) return ''
  const report = currentReport.value
  let mdText = `# Portfolio Research Report\n\n`
  mdText += `**Date:** ${report.created_at}\n\n`
  // Table of Contents with anchor links matching markdown-it-anchor slugs
  let toc = '## Table of Contents\n';
  if (report.portfolio_analysis) toc += '- [Portfolio Analysis](#portfolio-analysis)\n';
  if (report.dca_analysis) toc += '- [DCA Analysis](#dca-analysis)\n';
  if (report.economic_analysis) toc += '- [Economic Analysis](#economic-analysis)\n';
  if (report.notes) toc += '- [Notes](#notes)\n';
  mdText += toc + '\n';
  if (report.portfolio_analysis) {
    mdText += `## Portfolio Analysis\n${report.portfolio_analysis}\n\n`
  }
  if (report.dca_analysis) {
    mdText += `## DCA Analysis\n${report.dca_analysis}\n\n`
  }
  if (report.economic_analysis) {
    mdText += `## Economic Analysis\n${report.economic_analysis}\n\n`
  }
  if (report.notes) {
    mdText += `## Notes\n${report.notes}\n\n`
  }
  return md.render(mdText)
})

const fetchReports = async () => {
  if (!props.portfolioId) return
  loading.value = true
  try {
    const res = await axios.get(`/api/portfolio/${props.portfolioId}/research?limit=20`)
    reports.value = res.data.data || []
    currentIndex.value = 0
    if (reports.value.length > 0) {
      await fetchReportByIndex(0)
    } else {
      currentReport.value = null
    }
  } catch (e) {
    reports.value = []
    currentReport.value = null
  }
  loading.value = false
}

const fetchReportByIndex = async (idx) => {
  if (!reports.value[idx] || !props.portfolioId) return
  loading.value = true
  try {
    const reportId = reports.value[idx].id
    const res = await axios.get(`/api/portfolio/${props.portfolioId}/research/${reportId}`)
    currentReport.value = res.data.data || null
  } catch (e) {
    currentReport.value = null
  }
  loading.value = false
}

const nextReport = async () => {
  if (currentIndex.value < reports.value.length - 1) {
    currentIndex.value++
    await fetchReportByIndex(currentIndex.value)
  }
}
const prevReport = async () => {
  if (currentIndex.value > 0) {
    currentIndex.value--
    await fetchReportByIndex(currentIndex.value)
  }
}

const deleteCurrentReport = async () => {
  if (!currentReport.value || !props.portfolioId) return;
  if (!confirm('Delete this report?')) return;
  loading.value = true;
  try {
    await axios.delete(`/api/portfolio/${props.portfolioId}/research/${currentReport.value.id}`);
    // Remove from reports list and update currentIndex
    const idx = currentIndex.value;
    reports.value.splice(idx, 1);
    if (reports.value.length === 0) {
      currentReport.value = null;
      currentIndex.value = 0;
    } else if (idx >= reports.value.length) {
      currentIndex.value = reports.value.length - 1;
      await fetchReportByIndex(currentIndex.value);
    } else {
      await fetchReportByIndex(currentIndex.value);
    }
  } catch (e) {
    alert('Failed to delete report');
  }
  loading.value = false;
}


watch([
  () => props.show,
  () => props.portfolioId
], ([show, portfolioId]) => {
  if (show && portfolioId) fetchReports()
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
