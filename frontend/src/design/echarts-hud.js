export const XT_HUD_THEME_NAME = 'xt-hud'

const HUD_THEME = {
  color: ['#5eb8ff', '#4ecb8a', '#f0b84a', '#ff6b78', '#c88f3c', '#8cb7ff'],
  backgroundColor: 'transparent',
  textStyle: { color: 'rgba(224, 236, 255, 0.92)' },
  title: {
    textStyle: { color: 'rgba(224, 236, 255, 0.92)' },
    subtextStyle: { color: 'rgba(176, 196, 224, 0.72)' }
  },
  legend: { textStyle: { color: 'rgba(176, 196, 224, 0.72)' } },
  grid: { borderColor: 'rgba(148, 196, 255, 0.18)' },
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.24)' } },
    axisTick: { lineStyle: { color: 'rgba(148, 196, 255, 0.18)' } },
    axisLabel: { color: 'rgba(176, 196, 224, 0.72)' },
    splitLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.08)' } }
  },
  valueAxis: {
    axisLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.24)' } },
    axisTick: { lineStyle: { color: 'rgba(148, 196, 255, 0.18)' } },
    axisLabel: { color: 'rgba(176, 196, 224, 0.72)' },
    splitLine: { lineStyle: { color: 'rgba(148, 196, 255, 0.08)' } }
  },
  line: {
    itemStyle: { borderWidth: 2 },
    lineStyle: { width: 2, shadowBlur: 8, shadowColor: 'rgba(94, 184, 255, 0.35)' }
  },
  bar: {
    itemStyle: { borderRadius: [4, 4, 0, 0] }
  },
  tooltip: {
    backgroundColor: 'rgba(6, 16, 32, 0.92)',
    borderColor: 'rgba(94, 184, 255, 0.36)',
    textStyle: { color: 'rgba(224, 236, 255, 0.92)' }
  }
}

export function registerHudEchartsTheme(echarts) {
  if (!echarts || typeof echarts.registerTheme !== 'function') return
  echarts.registerTheme(XT_HUD_THEME_NAME, HUD_THEME)
}
