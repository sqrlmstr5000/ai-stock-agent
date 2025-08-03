import { defineStore } from 'pinia'
import axios from 'axios'

export const useStockStore = defineStore('stock', {
  state: () => ({
    loading: false,
    error: null,
    stockData: null,
    comparisonData: null,
    watchlist: [],
    stocks: []
  }),

  actions: {
    async fetchStocks() {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get('/api/stocks')
        this.stocks = response.data.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Error fetching stocks'
        throw error
      } finally {
        this.loading = false
      }
    },
    async analyzeStock(symbol) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get(`/api/analyze/${symbol}`)
        this.stockData = response.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Error analyzing stock'
        throw error
      } finally {
        this.loading = false
      }
    },

    async compareStocks(symbols) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.post('/api/compare', symbols)
        this.comparisonData = response.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Error comparing stocks'
        throw error
      } finally {
        this.loading = false
      }
    },

    async getStockData(symbol, endpoint) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get(`/api/${endpoint}/${symbol}`)
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || `Error fetching ${endpoint} data`
        throw error
      } finally {
        this.loading = false
      }
    },

    async addStock(symbolData) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.post('/api/stocks', symbolData)
        this.addToWatchlist(response.data.data.symbol)
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Error adding stock'
        throw error
      } finally {
        this.loading = false
      }
    },

    addToWatchlist(symbol) {
      if (!this.watchlist.includes(symbol)) {
        this.watchlist.push(symbol)
      }
    },

    removeFromWatchlist(symbol) {
      const index = this.watchlist.indexOf(symbol)
      if (index > -1) {
        this.watchlist.splice(index, 1)
      }
    }
  }
})
