import { ref, computed } from 'vue'

const BREAKPOINT = 1024
const STORAGE_KEY = 'sidebar-collapsed'

// Module-level singleton state, matching the useFilters/useI18n pattern in this
// codebase, so every component sharing this composable sees the same sidebar state.
const collapsed = ref(localStorage.getItem(STORAGE_KEY) === 'true')
const isSmallScreen = ref(window.innerWidth <= BREAKPOINT)

// Registered once at module load (not inside a component hook) since this state
// is a singleton shared app-wide, same reasoning as useI18n's localStorage read.
window.addEventListener('resize', () => {
  isSmallScreen.value = window.innerWidth <= BREAKPOINT
})

export function useSidebar() {
  // Icons-only whenever the user manually collapsed the sidebar OR the viewport
  // is too small for the expanded sidebar to make sense, whichever applies.
  const iconsOnly = computed(() => collapsed.value || isSmallScreen.value)

  const toggleCollapse = () => {
    collapsed.value = !collapsed.value
    localStorage.setItem(STORAGE_KEY, String(collapsed.value))
  }

  return {
    collapsed,
    isSmallScreen,
    iconsOnly,
    toggleCollapse
  }
}
