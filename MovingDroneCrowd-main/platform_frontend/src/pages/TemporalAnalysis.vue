<template>
  <div class="temporal-page">
    <!-- 左侧面板 -->
    <div class="left-panel">
      <h3 style="margin:0 0 8px;font-size:14px">↗ 时序分析</h3>
      <div style="margin-bottom:8px">
        <select v-model="selectedTaskId" class="task-select" @change="selectTask(selectedTaskId)">
          <option value="">-- 选择任务 --</option>
          <option v-for="task in doneTasks" :key="task.task_id" :value="task.task_id">{{ task.task_id }}</option>
        </select>
      </div>

      <div class="param-group">
        <label>平滑窗口</label>
        <select v-model.number="smoothWindow" class="param-select">
          <option :value="1">无</option><option :value="5">5帧</option>
          <option :value="10">10帧</option><option :value="20">20帧</option>
        </select>
      </div>
      <div class="param-group">
        <label>趋势分解</label>
        <select v-model="decomposeMode" class="param-select">
          <option value="none">原始数据</option>
          <option value="trend">趋势+残差</option>
          <option value="period">周期性检测</option>
        </select>
      </div>
      <div class="param-group" v-if="decomposeMode === 'period'">
        <label>周期窗口</label>
        <select v-model.number="periodWindow" class="param-select">
          <option :value="10">10</option><option :value="20">20</option>
          <option :value="30">30</option><option :value="50">50</option><option :value="60">60</option>
        </select>
      </div>

      <!-- 指标卡片 -->
      <div class="stat-cards" v-show="selectedTaskId">
        <div class="stat-card">
          <span class="sc-value">{{ temporalStats.maxCount }}</span>
          <span class="sc-label">峰值人数</span>
        </div>
        <div class="stat-card">
          <span class="sc-value">{{ temporalStats.minCount }}</span>
          <span class="sc-label">最低人数</span>
        </div>
        <div class="stat-card">
          <span class="sc-value">{{ temporalStats.variance.toFixed(0) }}</span>
          <span class="sc-label">方差</span>
        </div>
        <div class="stat-card">
          <span class="sc-value" style="color:var(--warning)">{{ temporalStats.trend }}</span>
          <span class="sc-label">总体趋势</span>
        </div>
        <div class="stat-card" style="grid-column:1/-1">
          <span class="sc-value" style="font-size:11px;color:var(--success)">{{ temporalStats.periodHint }}</span>
          <span class="sc-label">周期提示</span>
        </div>
      </div>
    </div>

    <!-- 右侧图表区：可滚动 -->
    <div class="right-panel" v-show="selectedTaskId">
      <!-- 上半区：时序折线 + 周期图 -->
      <div class="chart-row chart-row-top">
        <div class="panel chart-cell">
          <h3 class="chart-h3">↗ 人群数量时序变化</h3>
          <div ref="timeSeriesChart" class="chart-inner"></div>
        </div>
        <div class="panel chart-cell">
          <h3 class="chart-h3">⇄ 周期性分析（自相关）</h3>
          <div ref="periodChart" class="chart-inner"></div>
        </div>
      </div>

      <!-- 下半区：趋势分解 + 变化率 -->
      <div class="chart-row chart-row-bottom">
        <div class="panel chart-cell">
          <h3 class="chart-h3">↘ 趋势分解</h3>
          <div ref="trendChart" class="chart-inner"></div>
        </div>
        <div class="panel chart-cell">
          <h3 class="chart-h3">≡ 人数分布直方图</h3>
          <div ref="histChart" class="chart-inner"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onActivated, onUnmounted, inject } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'

export default {
  name: 'TemporalAnalysis',
  setup() {
    const c = getChartColors()
    const globalTasks = inject('globalTasks')
    const doneTasks = computed(() => globalTasks.value.filter(t => t.status === 'done'))
    const selectedTaskId = ref('')
    const allFrames = ref([])
    const smoothWindow = ref(5)
    const decomposeMode = ref('none')
    const periodWindow = ref(30)

    const timeSeriesChart = ref(null)
    const periodChart = ref(null)
    const trendChart = ref(null)
    const histChart = ref(null)
    let tsInst = null, periodInst = null, trendInst = null, histInst = null

    const smoothCounts = computed(() => {
      const raw = allFrames.value.map(f => f.count)
      if (smoothWindow.value <= 1) return raw
      const result = []
      for (let i = 0; i < raw.length; i++) {
        const start = Math.max(0, i - Math.floor(smoothWindow.value / 2))
        const end = Math.min(raw.length, i + Math.ceil(smoothWindow.value / 2))
        result.push(Math.round(raw.slice(start, end).reduce((a, b) => a + b, 0) / (end - start)))
      }
      return result
    })

    const trendData = computed(() => {
      const raw = allFrames.value.map(f => f.count)
      if (raw.length < 20) return raw
      const win = Math.max(5, Math.floor(raw.length / 20))
      const result = []
      for (let i = 0; i < raw.length; i++) {
        const start = Math.max(0, i - Math.floor(win / 2))
        const end = Math.min(raw.length, i + Math.ceil(win / 2))
        result.push(raw.slice(start, end).reduce((a, b) => a + b, 0) / (end - start))
      }
      return result
    })

    const residualData = computed(() => {
      const raw = allFrames.value.map(f => f.count)
      const trend = trendData.value
      return raw.map((v, i) => v - trend[i])
    })

    const autoCorr = computed(() => {
      const raw = allFrames.value.map(f => f.count)
      if (raw.length < 30) return []
      const mean = raw.reduce((a, b) => a + b, 0) / raw.length
      const variance = raw.reduce((s, v) => s + (v - mean) ** 2, 0)
      if (variance === 0) return []
      const maxLag = Math.min(periodWindow.value * 3, Math.floor(raw.length / 2))
      const result = []
      for (let lag = 0; lag <= maxLag; lag++) {
        let cov = 0
        const n = raw.length - lag
        for (let i = 0; i < n; i++) cov += (raw[i] - mean) * (raw[i + lag] - mean)
        result.push(cov / variance / n * raw.length)
      }
      return result
    })

    const temporalStats = computed(() => {
      const counts = allFrames.value.map(f => f.count)
      if (!counts.length) return { maxCount: 0, minCount: 0, variance: 0, trend: '-', periodHint: '-' }
      const maxC = Math.max(...counts), minC = Math.min(...counts)
      const mean = counts.reduce((a, b) => a + b, 0) / counts.length
      const variance = counts.reduce((s, v) => s + (v - mean) ** 2, 0) / counts.length
      const firstQ = counts.slice(0, Math.floor(counts.length / 4)).reduce((a, b) => a + b, 0) / Math.max(1, Math.floor(counts.length / 4))
      const lastQ = counts.slice(Math.floor(counts.length * 3 / 4)).reduce((a, b) => a + b, 0) / Math.max(1, Math.ceil(counts.length / 4))
      const trendDir = lastQ > firstQ * 1.1 ? '↗ 上升' : lastQ < firstQ * 0.9 ? '↘ 下降' : '→ 平稳'
      const ac = autoCorr.value
      let periodHint = '数据不足'
      if (ac.length > 10) {
        let bestLag = 0, bestVal = 0
        for (let i = 5; i < ac.length; i++) { if (ac[i] > bestVal && ac[i] > 0.2) { bestVal = ac[i]; bestLag = i } }
        periodHint = bestLag > 0 ? `检测到约 ${bestLag} 帧的周期性 (相关度 ${bestVal.toFixed(2)})` : '无明显周期性'
      }
      return { maxCount: maxC, minCount: minC, variance: Math.round(variance), trend: trendDir, periodHint }
    })

    // ===================== 图表核心函数 =====================

    function initAllCharts() {
      const containers = [
        { ref: timeSeriesChart.value, inst: () => tsInst, set: (v) => { tsInst = v }, name: 'ts' },
        { ref: periodChart.value, inst: () => periodInst, set: (v) => { periodInst = v }, name: 'period' },
        { ref: trendChart.value, inst: () => trendInst, set: (v) => { trendInst = v }, name: 'trend' },
        { ref: histChart.value, inst: () => histInst, set: (v) => { histInst = v }, name: 'hist' },
      ]
      for (const c of containers) {
        const el = c.ref
        if (!el) continue
        // 强制确保容器可见且有尺寸
        const style = getComputedStyle(el)
        if (style.display === 'none') el.style.display = 'block'
        if (el.offsetWidth === 0) el.style.width = '100%'
        if (el.offsetHeight === 0) el.style.height = '400px'
        const old = c.inst()
        if (old && !old.isDisposed()) old.dispose()
        c.set(echarts.init(el, getEchartsTheme()))
      }
    }

    function updateTimeSeriesChart() {
      if (!tsInst) return
      const counts = smoothCounts.value
      if (!counts.length) return
      const series = [{
        name: '人数', type: 'line', smooth: true,
        data: counts, lineStyle: { color: c.blue, width: 2 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(77,166,255,0.35)' }, { offset: 1, color: 'rgba(77,166,255,0.02)' }
        ]) }, symbol: 'none',
        markLine: {
          silent: true, symbol: 'none',
          data: [
            { yAxis: Math.max(...counts), lineStyle: { color: c.orange, type: 'dashed' }, label: { formatter: '峰值', color: c.orange, fontSize: 11 } },
            { yAxis: Math.min(...counts), lineStyle: { color: c.green, type: 'dashed' }, label: { formatter: '谷值', color: c.green, fontSize: 11 } },
          ]
        }
      }]
      if (decomposeMode.value === 'trend') {
        series.push({ name: '趋势', type: 'line', smooth: true, data: trendData.value, lineStyle: { color: c.orange, width: 2, type: 'dashed' }, symbol: 'none' })
      }
      tsInst.setOption({
        tooltip: { trigger: 'axis' },
        grid: { top: 16, right: 24, bottom: 32, left: 48 },
        xAxis: { type: 'category', data: allFrames.value.map(f => f.frame), axisLabel: { color: c.axis, fontSize: 10, interval: Math.max(1, Math.floor(allFrames.value.length / 10)) } },
        yAxis: { type: 'value', name: '人数', axisLabel: { color: c.axis, fontSize: 10 } },
        series,
      })
    }

    function updatePeriodChart() {
      if (!periodInst) return
      const ac = autoCorr.value
      if (!ac.length) { periodInst.setOption({}); return }
      const peaks = []
      for (let i = 5; i < ac.length - 1; i++) { if (ac[i] > ac[i - 1] && ac[i] > ac[i + 1] && ac[i] > 0.15) peaks.push({ xAxis: i, yAxis: ac[i] }) }
      periodInst.setOption({
        tooltip: { trigger: 'axis', formatter: p => `滞后 ${p[0].axisValue} 帧: 相关度 ${p[0].value.toFixed(3)}` },
        grid: { top: 16, right: 24, bottom: 32, left: 48 },
        xAxis: { type: 'value', name: '滞后(帧)', axisLabel: { color: c.axis, fontSize: 10 } },
        yAxis: { type: 'value', name: '自相关', min: -1, max: 1, axisLabel: { color: c.axis, fontSize: 10 } },
        series: [
          { type: 'line', data: ac.map((v, i) => [i, v]), smooth: true, lineStyle: { color: c.blue, width: 1.5 }, symbol: 'none' },
          { type: 'scatter', data: peaks, symbolSize: 10, itemStyle: { color: '#ffa040' }, markLine: { silent: true, symbol: 'none', data: [{ yAxis: 0, lineStyle: { color: '#5a80b0', type: 'dashed', width: 1 } }] } }
        ]
      })
    }

    function updateTrendChart() {
      if (!trendInst) return
      const raw = allFrames.value.map(f => f.count), trend = trendData.value, residual = residualData.value
      const xData = allFrames.value.map(f => f.frame)
      if (!raw.length) return
      trendInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['原始', '趋势', '残差'], bottom: 0, textStyle: { color: c.axis, fontSize: 10 } },
        grid: { top: 16, right: 20, bottom: 36, left: 48 },
        xAxis: { type: 'category', data: xData, axisLabel: { color: c.axis, fontSize: 10, interval: Math.max(1, Math.floor(xData.length / 8)) } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 10 } },
        series: [
          { name: '原始', type: 'line', data: raw, smooth: true, lineStyle: { color: 'rgba(77,166,255,0.3)', width: 1 }, symbol: 'none' },
          { name: '趋势', type: 'line', data: trend, smooth: true, lineStyle: { color: '#ffa040', width: 2 }, symbol: 'none', areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(255,160,64,0.2)' }, { offset: 1, color: 'rgba(255,160,64,0)' }]) } },
          { name: '残差', type: 'bar', data: residual, itemStyle: { color: p => p.value >= 0 ? 'rgba(64,216,112,0.5)' : 'rgba(255,64,112,0.5)' } },
        ]
      })
    }

    function updateHistChart() {
      if (!histInst) return
      const counts = allFrames.value.map(f => f.count)
      if (counts.length === 0) return
      const min = Math.min(...counts), max = Math.max(...counts)
      const range = max - min || 1
      const binCount = Math.min(20, Math.max(5, Math.floor(Math.sqrt(counts.length))))
      const binWidth = range / binCount
      const bins = Array(binCount).fill(0)
      const binLabels = []
      for (let i = 0; i < binCount; i++) {
        const lo = Math.round(min + i * binWidth)
        const hi = Math.round(min + (i + 1) * binWidth)
        binLabels.push(`${lo}-${hi}`)
      }
      counts.forEach(v => {
        const idx = Math.min(binCount - 1, Math.floor((v - min) / binWidth))
        bins[idx]++
      })
      histInst.setOption({
        tooltip: { trigger: 'axis', formatter: p => `人数区间 ${p[0].name}: <b>${p[0].value} 帧</b>` },
        grid: { top: 16, right: 20, bottom: 36, left: 48 },
        xAxis: { type: 'category', data: binLabels, axisLabel: { color: c.axis, fontSize: 9, rotate: 30 }, name: '人数区间' },
        yAxis: { type: 'value', name: '帧数', axisLabel: { color: c.axis, fontSize: 10 } },
        series: [{
          type: 'bar', data: bins,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: c.blue }, { offset: 1, color: '#1a4080' }
            ]),
            borderRadius: [4, 4, 0, 0],
          },
          emphasis: { itemStyle: { color: c.orange } },
        }]
      })
    }

    function updateAllCharts() {
      if (!tsInst || !periodInst || !trendInst || !histInst) initAllCharts()
      updateTimeSeriesChart()
      updatePeriodChart()
      updateTrendChart()
      updateHistChart()
    }

    function resizeAllCharts() {
      tsInst?.resize()
      periodInst?.resize()
      trendInst?.resize()
      histInst?.resize()
    }

    // ===================== 选择任务 =====================

    async function selectTask(taskId) {
      selectedTaskId.value = taskId
      if (!taskId) return
      try {
        const res = await axios.get(`/api/v1/video/result/${taskId}`)
        if (!res.data.frames || res.data.frames.length === 0) return
        allFrames.value = res.data.frames
        // 直接初始化，和 HeatmapView 一样——await 本身已经给了足够时间
        initAllCharts()
        resizeAllCharts()
        updateAllCharts()
      } catch (e) {
        console.error('[TemporalAnalysis] 获取结果失败:', e)
      }
    }

    // ===================== 生命周期 =====================

    watch([smoothWindow, decomposeMode, periodWindow], () => {
      updateAllCharts()
    })

    function onThemeChange() {
      initAllCharts()
      resizeAllCharts()
      if (allFrames.value.length > 0) updateAllCharts()
    }

    onMounted(() => {
      window.addEventListener('resize', resizeAllCharts)
      window.addEventListener('themechange', onThemeChange)
      setTimeout(() => {
        initAllCharts()
        if (doneTasks.value.length > 0 && !selectedTaskId.value) {
          selectTask(doneTasks.value[0].task_id)
        }
      }, 100)
    })

    onActivated(() => {
      setTimeout(() => {
        initAllCharts()
        resizeAllCharts()
        if (allFrames.value.length > 0) updateAllCharts()
      }, 150)
    })

    onUnmounted(() => {
      tsInst?.dispose()
      periodInst?.dispose()
      trendInst?.dispose()
      histInst?.dispose()
      window.removeEventListener('resize', resizeAllCharts)
      window.removeEventListener('themechange', onThemeChange)
    })

    return {
      doneTasks, selectedTaskId, smoothWindow, decomposeMode, periodWindow,
      temporalStats, timeSeriesChart, periodChart, trendChart, histChart,
      selectTask,
    }
  }
}
</script>

<style scoped>
.temporal-page { height: 100%; width: 100%; display: flex; overflow: hidden; }

/* 左侧面板 */
.left-panel {
  width: 230px; flex-shrink: 0; overflow-y: auto;
  padding: 12px; background: var(--bg-card);
  border-right: 1px solid var(--border-subtle);
}
.left-panel::-webkit-scrollbar { width: 4px; }
.left-panel::-webkit-scrollbar-thumb { background: var(--accent-glow); border-radius: 2px; }

.task-select {
  width: 100%; padding: 6px 8px; background: var(--bg-card); color: var(--text-primary);
  border: 1px solid var(--border-subtle); border-radius: 4px; font-size: 12px;
}

.param-group { margin-bottom: 10px; }
.param-group label { display: block; font-size: 11px; color: var(--text-dim); margin-bottom: 4px; }
.param-select {
  width: 100%; padding: 5px 8px; background: var(--bg-card); color: var(--text-primary);
  border: 1px solid var(--border-subtle); border-radius: 3px; font-size: 11px;
}

.stat-cards {
  margin-top: 12px; padding-top: 10px;
  border-top: 1px solid var(--border-subtle);
  display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
}
.stat-card {
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  border-radius: 4px; padding: 6px 8px; text-align: center;
}
.sc-value { display: block; font-family: 'Courier New', monospace; font-size: 16px; color: var(--text-primary); font-weight: bold; }
.sc-label { display: block; font-size: 9px; color: var(--text-dim); margin-top: 2px; }

/* 右侧图表区：可滚动 */
.right-panel {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 8px 12px 16px;
}
.right-panel::-webkit-scrollbar { width: 6px; }
.right-panel::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
.right-panel::-webkit-scrollbar-thumb { background: rgba(77,166,255,0.3); border-radius: 3px; }

/* 图表行：一行两个 */
.chart-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  margin-bottom: 10px;
}

.chart-cell {
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  border-radius: 6px; padding: 10px;
}

.chart-h3 { margin: 0 0 8px; font-size: 12px; color: #8ab8ff; font-weight: 600; }

.chart-inner {
  width: 100%; height: 400px;
}
.chart-row-bottom .chart-inner { height: 320px; }
</style>
