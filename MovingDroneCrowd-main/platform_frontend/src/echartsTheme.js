import { ref, readonly, reactive, computed } from 'vue'
import * as echarts from 'echarts'

const theme = ref('dark')

// ===== 深色 ECharts 主题 =====
echarts.registerTheme('dronecrowd-dark', {
  textStyle: {
    fontFamily: 'Rajdhani, Inter, sans-serif',
  },
  title: {
    textStyle: { fontFamily: 'Rajdhani, sans-serif', color: '#c8ddf8' },
  },
  legend: {
    textStyle: { fontFamily: 'Rajdhani, Inter, sans-serif', color: '#5a80b0' },
  },
  color: ['#4da6ff', '#40d870', '#ffa040', '#ff4070', '#a040ff', '#40d0ff', '#ffb054'],
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: 'rgba(6, 20, 44, 0.94)',
    borderColor: 'rgba(30, 80, 180, 0.3)',
    textStyle: { color: '#c8ddf8', fontSize: 11 },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    axisTick: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    axisLabel: { fontFamily: 'Rajdhani, Inter, sans-serif', color: '#5a80b0', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    axisTick: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    axisLabel: { fontFamily: 'Rajdhani, Inter, sans-serif', color: '#5a80b0', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } },
  },
  grid: {
    containLabel: false,
  },
})

// ===== 城市环境 ECharts 主题 =====
echarts.registerTheme('dronecrowd-city', {
  textStyle: {
    fontFamily: 'Rajdhani, Inter, sans-serif',
  },
  title: {
    textStyle: { fontFamily: 'Rajdhani, sans-serif', color: '#1f2937' },
  },
  legend: {
    textStyle: { fontFamily: 'Rajdhani, Inter, sans-serif', color: '#64748b' },
  },
  color: ['#5b9df9', '#55c2c3', '#8b8ff5', '#f2a65a', '#e97b5c', '#34d399', '#f5c842'],
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderColor: 'rgba(91, 157, 249, 0.3)',
    textStyle: { color: '#1f2937', fontSize: 11 },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
    axisTick: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
    axisLabel: { fontFamily: 'Rajdhani, Inter, sans-serif', color: '#64748b', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
    axisTick: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
    axisLabel: { fontFamily: 'Rajdhani, Inter, sans-serif', color: '#64748b', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)' } },
  },
  grid: {
    containLabel: false,
  },
})

// ===== 主题感知的图表颜色 =====
const darkColors = {
  blue: '#4da6ff',
  cyan: '#40d0ff',
  green: '#40d870',
  orange: '#ffa040',
  red: '#ff4070',
  purple: '#a040ff',
  yellow: '#ffb054',
  bg: '#020b18',
  grid: 'rgba(255,255,255,0.03)',
  axis: '#5a80b0',
  gradientStart: 'rgba(77,166,255,0.35)',
  gradientEnd: 'rgba(77,166,255,0.02)',
  gradientStartOrange: 'rgba(255,160,64,0.35)',
  gradientEndOrange: 'rgba(255,160,64,0.02)',
  gradientStartGreen: 'rgba(64,216,112,0.3)',
  gradientEndGreen: 'rgba(64,216,112,0.02)',
}

const cityColors = {
  blue: '#5b9df9', cyan: '#55c2c3', green: '#34d399', orange: '#f2a65a',
  red: '#e97b5c', purple: '#8b8ff5', yellow: '#f5c842', bg: '#f4f6f8',
  grid: 'rgba(0,0,0,0.04)', axis: '#64748b',
  gradientStart: 'rgba(91,157,249,0.25)', gradientEnd: 'rgba(91,157,249,0.02)',
  gradientStartOrange: 'rgba(242,166,90,0.25)', gradientEndOrange: 'rgba(242,166,90,0.02)',
  gradientStartGreen: 'rgba(52,211,153,0.25)', gradientEndGreen: 'rgba(52,211,153,0.02)',
}

const colors = reactive({ ...darkColors })

export function useChartColors() {
  return readonly(colors)
}

export function getChartColors() {
  return colors
}

export function useEchartsTheme() {
  return readonly(theme)
}

export function getEchartsTheme() {
  return theme.value === 'city' ? 'dronecrowd-city' : 'dronecrowd-dark'
}

export function setEchartsTheme(newTheme) {
  theme.value = newTheme
  const source = newTheme === 'city' ? cityColors : darkColors
  Object.assign(colors, source)
}

/**
 * 创建 ECharts 线性渐变（主题感知）
 * @param {'blue'|'orange'|'green'|'purple|'red'} colorKey - 主色调
 * @param {number} startOpacity - 起始透明度
 * @param {number} endOpacity - 结束透明度
 * @param {number} x0 - 渐变起点 x
 * @param {number} y0 - 渐变起点 y
 * @param {number} x2 - 渐变终点 x
 * @param {number} y2 - 渐变终点 y
 */
export function makeGradient(colorKey = 'blue', startOpacity = 0.35, endOpacity = 0.02, x0 = 0, y0 = 0, x2 = 0, y2 = 1) {
  const colorMap = {
    blue: colors.blue,
    orange: colors.orange,
    green: colors.green,
    purple: colors.purple,
    red: colors.red,
    cyan: colors.cyan,
  }
  const base = colorMap[colorKey] || colors.blue
  // 将 hex 转为 rgb 以支持透明度
  const r = parseInt(base.slice(1, 3), 16)
  const g = parseInt(base.slice(3, 5), 16)
  const b = parseInt(base.slice(5, 7), 16)
  return new echarts.graphic.LinearGradient(x0, y0, x2, y2, [
    { offset: 0, color: `rgba(${r},${g},${b},${startOpacity})` },
    { offset: 1, color: `rgba(${r},${g},${b},${endOpacity})` },
  ])
}
