import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { registerTheme } from 'echarts/core'

import { registerHudEchartsTheme, XT_HUD_THEME_NAME } from '../design/echarts-hud.js'

registerHudEchartsTheme({ registerTheme })

function readHudActive() {
  return typeof document !== 'undefined' && document.documentElement.dataset.xtTheme === 'hud'
}

export function useHudChartTheme() {
  const active = ref(readHudActive())
  let observer = null

  function update() {
    active.value = readHudActive()
  }

  onMounted(() => {
    update()
    if (typeof MutationObserver !== 'undefined') {
      observer = new MutationObserver(update)
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-xt-theme']
      })
    }
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return computed(() => (active.value ? XT_HUD_THEME_NAME : undefined))
}
