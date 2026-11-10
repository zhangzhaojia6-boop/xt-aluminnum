export const XT_HUD_THEME_NAME = 'xt-hud'

const AXIS = { color: '#9aa8bd' }
const GRID_LINE = '#1a2740'

const HUD_THEME = {
  color: ['#4d8eff', '#3ecf8e', '#f5b544', '#b18cff', '#5fd3e6', '#ff6b6b'],
  backgroundColor: 'transparent',
  textStyle: { color: '#e6edf7' },
  title: {
    textStyle: { color: '#e6edf7' },
    subtextStyle: AXIS
  },
  legend: { textStyle: AXIS },
  grid: { borderColor: GRID_LINE },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#2c3f5e' } },
    axisTick: { lineStyle: { color: GRID_LINE } },
    axisLabel: AXIS,
    splitLine: { lineStyle: { color: GRID_LINE } }
  },
  valueAxis: {
    axisLine: { lineStyle: { color: '#2c3f5e' } },
    axisTick: { lineStyle: { color: GRID_LINE } },
    axisLabel: AXIS,
    splitLine: { lineStyle: { color: GRID_LINE } }
  },
  line: {
    itemStyle: { borderWidth: 2 },
    lineStyle: { width: 2 }
  },
  bar: {
    itemStyle: { borderRadius: [2, 2, 0, 0] }
  },
  tooltip: {
    backgroundColor: '#111e33',
    borderColor: '#2c3f5e',
    textStyle: { color: '#e6edf7' }
  }
}

export function registerHudEchartsTheme(echarts) {
  if (!echarts || typeof echarts.registerTheme !== 'function') return
  echarts.registerTheme(XT_HUD_THEME_NAME, HUD_THEME)
}
