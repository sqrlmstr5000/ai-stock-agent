<template>
  <div>
    <div class="p-4 bg-gray-100 border-b border-gray-200 flex flex-wrap gap-4 justify-between items-center">
      <button @click="generateResearch" class="px-4 py-2 font-semibold text-white bg-blue-500 rounded hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50">
        Generate Research
      </button>
      <div class="relative" ref="dropdownContainer">
        <button @click="toggleDropdown" class="px-4 py-2 font-semibold text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200">
          Select Research
          <svg class="inline-block w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
        </button>
        <ul v-if="isDropdownOpen" class="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-md shadow-lg z-10">
          <li v-if="researchHistory.length === 0">
            <a class="block px-4 py-2 text-sm text-gray-500">No research available</a>
          </li>
          <li v-for="item in researchHistory" :key="item.id">
            <a @click="selectResearch(item)" href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">{{ item.symbol }} - {{ formatDate(item.created_at) }}</a>
          </li>
        </ul>
      </div>
      <div class="flex gap-2">
        <button @click="generateTechnical" class="px-4 py-2 font-semibold text-white bg-green-600 rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-opacity-50">
          Generate Technical Analysis
        </button>
        <div class="relative" ref="techDropdownContainer">
          <button @click="toggleTechDropdown" class="px-4 py-2 font-semibold text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200">
            Select Technical
            <svg class="inline-block w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
          </button>
          <ul v-if="isTechDropdownOpen" class="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-md shadow-lg z-10">
            <li v-if="technicalHistory.length === 0">
              <a class="block px-4 py-2 text-sm text-gray-500">No technical analysis available</a>
            </li>
            <li v-for="item in technicalHistory" :key="item.id">
              <a @click="selectTechnical(item)" href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">{{ item.symbol }} - {{ formatDate(item.created_at) }}</a>
            </li>
          </ul>
        </div>
      </div>
    </div>
    <!-- Rendered markdown report (used for both research and technical) -->
    <div v-if="selectedReport" class="prose max-w-none p-4" v-html="renderedReport"></div>
  </div>
</template>

<script>
import axios from 'axios';
import MarkdownIt from 'markdown-it';

export default {
  name: 'StockResearch',
  props: {
    symbol: {
      type: String,
      required: true
    },
    reportId: {
      type: [String, Number],
      required: false
    }
  },
  data() {
    return {
      researchHistory: [],
      isDropdownOpen: false,
      selectedReport: null,
      technicalHistory: [],
      isTechDropdownOpen: false,
      md: null
    };
  },
  computed: {
    renderedReport() {
      if (this.md && this.selectedReport) {
        return this.md.render(this.selectedReport);
      }
      return '';
    }
  },
  watch: {
    // Watch for changes to symbol or reportId
    symbol: {
      immediate: true,
      handler(newSymbol) {
        if (newSymbol) {
          this.fetchResearchHistory()
          this.fetchTechnicalHistory()
        }
      }
    },
    reportId: {
      immediate: true,
      handler(newReportId) {
        if (newReportId && this.researchHistory.length > 0) {
          const found = this.researchHistory.find(r => String(r.id) === String(newReportId))
          if (found) {
            this.selectResearch(found)
          }
        }
      }
    }
  },
  methods: {
    toggleDropdown() {
      this.isDropdownOpen = !this.isDropdownOpen;
    },
    closeDropdown() {
      this.isDropdownOpen = false;
    },
    toggleTechDropdown() {
      this.isTechDropdownOpen = !this.isTechDropdownOpen;
    },
    closeTechDropdown() {
      this.isTechDropdownOpen = false;
    },
    async generateResearch() {
      try {
        this.closeDropdown();
        console.log(`Generating research for ${this.symbol}...`);
        const response = await axios.get(`/api/analyze/${this.symbol}`);
        console.log('Research generated:', response.data);
        await this.fetchResearchHistory();
      } catch (error) {
        console.error('Error generating research:', error);
      }
    },
    async generateTechnical() {
      try {
        this.closeTechDropdown();
        console.log(`Generating technical analysis for ${this.symbol}...`);
        const response = await axios.get(`/api/technical/generate/${this.symbol}`);
        console.log('Technical analysis generated:', response.data);
        await this.fetchTechnicalHistory();
      } catch (error) {
        console.error('Error generating technical analysis:', error);
      }
    },
    async fetchResearchHistory() {
      try {
        console.log(`Fetching research history for ${this.symbol}...`);
        const response = await axios.get(`/api/stock/${this.symbol}/research`);
        this.researchHistory = response.data.data;
        console.log('Research history:', this.researchHistory);
        // If reportId is set, auto-select that report
        if (this.reportId && this.researchHistory.length > 0) {
          const found = this.researchHistory.find(r => String(r.id) === String(this.reportId))
          if (found) {
            await this.selectResearch(found)
            return
          }
        }
        // Auto-select first report if available
        if (this.researchHistory.length > 0) {
          await this.selectResearch(this.researchHistory[0]);
        }
      } catch (error) {
        console.error('Error fetching research history:', error);
      }
    },
    async fetchTechnicalHistory() {
      try {
        console.log(`Fetching technical analysis history for ${this.symbol}...`);
        const response = await axios.get(`/api/stock/${this.symbol}/technical`);
        this.technicalHistory = response.data.data;
        console.log('Technical history:', this.technicalHistory);
      } catch (error) {
        console.error('Error fetching technical history:', error);
      }
    },
    async selectResearch(item) {
      try {
        console.log('Selected research item:', item);
        const response = await axios.get(`/api/stock/research/${item.id}`);
        this.selectedReport = response.data.data;
        console.log('Fetched report:', this.selectedReport);
        this.closeDropdown();
        this.$emit('research-selected', item);
      } catch (error) {
        console.error('Error fetching research report:', error);
        this.selectedReport = '### Error loading report. Please try again.';
      }
    },
    async selectTechnical(item) {
      try {
        console.log('Selected technical item:', item);
        const response = await axios.get(`/api/stock/technical/${item.id}`);
        this.selectedReport = response.data.data;
        console.log('Fetched technical report:', this.selectedReport);
        this.closeTechDropdown();
        this.$emit('technical-selected', item);
      } catch (error) {
        console.error('Error fetching technical report:', error);
        this.selectedReport = '### Error loading technical report. Please try again.';
      }
    },
    formatDate(dateString) {
      const options = { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
      return new Date(dateString).toLocaleDateString(undefined, options);
    },
    handleClickOutside(event) {
      if (this.$refs.dropdownContainer && !this.$refs.dropdownContainer.contains(event.target)) {
        this.closeDropdown();
      }
      if (this.$refs.techDropdownContainer && !this.$refs.techDropdownContainer.contains(event.target)) {
        this.closeTechDropdown();
      }
    }
  },
  created() {
    this.md = new MarkdownIt();
  },
  mounted() {
    this.fetchResearchHistory();
    this.fetchTechnicalHistory();
    document.addEventListener('click', this.handleClickOutside);
  },
  beforeUnmount() {
    document.removeEventListener('click', this.handleClickOutside);
  }
};
</script>

<style>
/* Basic styling for rendered markdown if @tailwindcss/typography is not used */
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
