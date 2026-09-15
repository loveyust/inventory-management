<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-control">
          <input
            type="range"
            class="budget-slider"
            min="0"
            :max="maxBudget"
            step="1"
            v-model.number="budget"
          />
          <div class="budget-readout">
            <div class="budget-readout-item">
              <span class="budget-readout-label">{{ t('restocking.budgetLabel') }}</span>
              <span class="budget-readout-value">{{ formatCurrency(budget, currentCurrency) }}</span>
            </div>
            <div class="budget-readout-item">
              <span class="budget-readout-label">{{ t('restocking.remainingBudget') }}</span>
              <span class="budget-readout-value">{{ formatCurrency(remainingBudget, currentCurrency) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ recommendedItems.length }})</h3>
        </div>
        <div v-if="recommendedItems.length === 0" class="loading">
          {{ t('restocking.noCandidates') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="candidate in recommendedItems" :key="candidate.sku">
                <td><strong>{{ candidate.sku }}</strong></td>
                <td>{{ translateProductName(candidate.name) }}</td>
                <td>{{ candidate.quantity }}</td>
                <td>{{ formatCurrencyWithDecimals(candidate.unit_cost, currentCurrency, 2) }}</td>
                <td><strong>{{ formatCurrencyWithDecimals(candidate.line_cost, currentCurrency, 2) }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="restocking-summary">
          <div class="total-cost-line">
            {{ t('restocking.totalCost') }}: <strong>{{ formatCurrency(totalCost, currentCurrency) }}</strong>
          </div>
          <button
            class="place-order-btn"
            :disabled="recommendedItems.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="submitSuccess" class="success-message">
          {{ t('restocking.orderSuccess', { orderNumber: submitSuccess }) }}
        </div>
        <div v-if="submitError" class="error">{{ submitError }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const demandForecasts = ref([])
    const inventoryItems = ref([])

    const budget = ref(0)

    const submitting = ref(false)
    const submitError = ref(null)
    const submitSuccess = ref(null)

    const loadData = async () => {
      try {
        loading.value = true
        error.value = null
        const [forecastsData, inventoryData] = await Promise.all([
          api.getDemandForecasts(),
          api.getInventory()
        ])
        demandForecasts.value = forecastsData
        inventoryItems.value = inventoryData
      } catch (err) {
        error.value = 'Failed to load restocking data: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const rankedCandidates = computed(() => {
      const candidates = []

      demandForecasts.value.forEach(forecastRow => {
        const inventoryItem = inventoryItems.value.find(item => item.sku === forecastRow.item_sku)
        if (!inventoryItem) return

        const gap = forecastRow.forecasted_demand - inventoryItem.quantity_on_hand
        if (gap <= 0) return

        candidates.push({
          sku: forecastRow.item_sku,
          name: forecastRow.item_name,
          quantity: gap,
          unit_cost: inventoryItem.unit_cost,
          line_cost: gap * inventoryItem.unit_cost
        })
      })

      return candidates.sort((a, b) => b.quantity - a.quantity)
    })

    const maxBudget = computed(() => {
      return rankedCandidates.value.reduce((sum, candidate) => sum + candidate.line_cost, 0)
    })

    watch(maxBudget, (newMax) => {
      if (budget.value === 0 && newMax > 0) {
        budget.value = Math.round(newMax / 2)
      }
    }, { once: true })

    const recommendedItems = computed(() => {
      const result = []
      let remaining = budget.value

      rankedCandidates.value.forEach(candidate => {
        if (candidate.line_cost <= remaining) {
          result.push(candidate)
          remaining -= candidate.line_cost
        }
      })

      return result
    })

    const totalCost = computed(() => {
      return recommendedItems.value.reduce((sum, candidate) => sum + candidate.line_cost, 0)
    })

    const remainingBudget = computed(() => budget.value - totalCost.value)

    const placeOrder = async () => {
      if (recommendedItems.value.length === 0) return

      submitting.value = true
      submitError.value = null
      submitSuccess.value = null

      try {
        const createdOrder = await api.createPurchaseOrder({
          items: recommendedItems.value.map(candidate => ({
            sku: candidate.sku,
            name: candidate.name,
            quantity: candidate.quantity,
            unit_cost: candidate.unit_cost
          }))
        })
        submitSuccess.value = createdOrder.order_number
        budget.value = 0
      } catch (err) {
        submitError.value = 'Failed to place order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadData)

    return {
      t,
      currentCurrency,
      translateProductName,
      formatCurrency,
      formatCurrencyWithDecimals,
      loading,
      error,
      budget,
      maxBudget,
      rankedCandidates,
      recommendedItems,
      totalCost,
      remainingBudget,
      submitting,
      submitError,
      submitSuccess,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-control {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.budget-slider {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  transition: transform 0.15s ease;
}

.budget-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

.budget-readout {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.budget-readout-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.budget-readout-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-readout-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.restocking-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.total-cost-line {
  font-size: 0.938rem;
  color: #334155;
}

.place-order-btn {
  padding: 0.625rem 1.5rem;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #2563eb;
}

.place-order-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.success-message {
  margin-top: 1rem;
  padding: 1rem;
  background: #d1fae5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  border-radius: 8px;
  font-size: 0.938rem;
}
</style>
