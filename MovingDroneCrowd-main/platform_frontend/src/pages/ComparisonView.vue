<template>
  <div class="compare-page">
    <div class="main-content">
      <!-- 左侧面板 -->
      <aside class="left-panel">
        <!-- 模式切换 -->
        <div class="panel">
          <h3>⇄ 分析模式</h3>
          <div class="mode-tabs">
            <button :class="{ active: mode === 'task' }" @click="mode = 'task'">☰ 任务对比</button>
            <button :class="{ active: mode === 'dataset' }" @click="mode = 'dataset'">⊠ 数据集测试</button>
          </div>
        </div>

        <!-- ====== 任务对比模式 ====== -->
        <template v-if="mode === 'task'">
          <div class="panel">
            <h3>☰ 已完成任务</h3>
            <div class="task-list">
              <div v-for="task in doneTasks" :key="task.task_id"
                   class="task-item" :class="{ selected: selectedIds.has(task.task_id) }"
                   @click="toggleTask(task.task_id)">
                <span class="status-dot status-done"></span>
                <span style="font-family:monospace;font-size:11px;flex:1">{{ task.task_id }}</span>
                <input type="checkbox" :checked="selectedIds.has(task.task_id)" style="accent-color:var(--accent);pointer-events:none" />
              </div>
              <div v-if="doneTasks.length === 0" style="color:var(--text-dim);font-size:12px;text-align:center;padding:20px">
                暂无已完成任务
              </div>
            </div>
            <div v-if="selectedIds.size > 0" style="margin-top:8px;font-size:10px;color:var(--accent);text-align:center">
              已选 {{ selectedIds.size }} 个任务
            </div>
          </div>

          <div class="panel" v-if="selectedIds.size > 0">
            <h3>≡ 对比指标</h3>
            <div class="stats-grid">
              <div class="stat-card" v-for="m in compareMetrics" :key="m.key">
                <div class="stat-label">{{ m.label }}</div>
                <div v-for="(val, tid) in m.values" :key="tid" class="metric-row">
                  <span class="metric-tag" :style="{ borderColor: taskColors.get(tid) }">{{ tid }}</span>
                  <span class="digital" style="font-size:14px">{{ val }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="panel" v-if="selectedIds.size > 0">
            <h3>⚙️ 图表切换</h3>
            <select v-model="bottomChartMode" class="param-select" style="width:100%">
              <option value="bar">≡ 柱状图对比</option>
              <option value="histogram">≡ 人数分布直方图</option>
              <option value="scatter">📍 帧间散点对比</option>
              <option value="box">⊠ 人数箱线图</option>
              <option value="heatmap">⊛ 帧人数热力图</option>
              <option value="stacked">↗ 堆叠面积图</option>
            </select>
          </div>
        </template>

        <!-- ====== 数据集测试模式 ====== -->
        <template v-if="mode === 'dataset'">
          <div class="panel">
            <h3>↗ 数据集测试</h3>
            <div class="param-row">
              <label>采样间隔</label>
              <select v-model.number="dsInterval" class="param-select">
                <option :value="1">每帧</option>
                <option :value="2">每2帧</option>
                <option :value="4">每4帧</option>
                <option :value="8">每8帧</option>
              </select>
            </div>
            <button class="btn-start" @click="startDatasetTest" :disabled="dsRunning">
              {{ dsRunning ? '↻ 测试中...' : '▸ 启动数据集测试' }}
            </button>
            <div v-if="dsRunning" class="progress-bar">
              <div class="progress-fill" :style="{ width: dsProgress + '%' }"></div>
            </div>
            <div v-if="dsMessage" class="ds-msg">{{ dsMessage }}</div>
          </div>

          <!-- 已完成的测试任务 -->
          <div class="panel">
            <h3>☰ 测试历史</h3>
            <div class="task-list">
              <div v-for="t in dsTasks" :key="t.task_id"
                   class="task-item" :class="{ selected: dsSelectedId === t.task_id }"
                   @click="selectDatasetTask(t.task_id)">
                <span class="status-dot" :class="t.status === 'done' ? 'status-done' : 'status-running'"></span>
                <span style="font-family:monospace;font-size:10px;flex:1">{{ t.task_id }}</span>
                <span v-if="t.status === 'done'" style="font-size:10px;color:var(--success)">✓</span>
                <span v-else style="font-size:10px;color:var(--warning)">{{ t.progress }}%</span>
              </div>
              <div v-if="dsTasks.length === 0" style="color:var(--text-dim);font-size:12px;text-align:center;padding:20px">
                暂无测试任务
              </div>
            </div>
          </div>

          <!-- 场景选择（数据集结果已加载时） -->
          <div class="panel" v-if="dsResult && dsResult.scenes">
            <h3>⊡ 场景选择</h3>
            <div class="scene-filter">
              <select v-model="dsDensityFilter" class="param-select" style="width:100%;margin-bottom:4px">
                <option value="all">全部密度等级</option>
                <option value="0">密度 0 (极低)</option>
                <option value="1">密度 1 (低)</option>
                <option value="2">密度 2 (中)</option>
                <option value="3">密度 3 (高)</option>
              </select>
              <select v-model="dsSceneFilter" class="param-select" style="width:100%;margin-bottom:4px">
                <option value="all">全部场景类型</option>
                <option v-for="t in dsSceneTypes" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
          </div>
        </template>
      </aside>

      <!-- 中央图表区 -->
      <main class="center-panel">
        <!-- ====== 任务对比模式 ====== -->
        <template v-if="mode === 'task'">
          <div class="panel" style="flex:1;display:flex;flex-direction:column;overflow:hidden">
            <h3 style="flex-shrink:0">↗ 人群数量变化对比</h3>
            <div ref="countCompareChart" style="flex:1;min-height:200px"></div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;height:210px">
            <div class="panel" style="display:flex;flex-direction:column;overflow:hidden;height:100%">
              <h3 style="flex-shrink:0">{{ bottomChartLabel }}</h3>
              <div :key="'mode-'+bottomChartMode" ref="modeChart" style="flex:1;min-height:100px;width:100%"></div>
            </div>
            <div class="panel" style="display:flex;flex-direction:column;overflow:hidden;height:100%">
              <h3 style="flex-shrink:0">≡ 密度分布对比</h3>
              <div ref="densityCompareChart" style="flex:1;min-height:100px"></div>
            </div>
          </div>
        </template>

        <!-- ====== 数据集测试模式 ====== -->
        <template v-if="mode === 'dataset'">
          <!-- 未选择时提示 -->
          <div v-if="!dsResult" class="panel" style="flex:1;display:flex;align-items:center;justify-content:center">
            <div style="text-align:center;color:var(--text-dim)">
              <div style="font-size:48px;margin-bottom:16px">⊠</div>
              <div>启动数据集测试，查看 GT vs 预测对比</div>
              <div style="font-size:12px;margin-top:8px;color:var(--text-dim)">
                测试集包含 {{ dsSceneCount || 0 }} 个场景
              </div>
            </div>
          </div>

          <!-- 已选择结果 -->
          <template v-if="dsResult">
            <!-- 顶部：总体指标 -->
            <div class="panel" style="flex-shrink:0;margin-bottom:8px">
              <h3>≡ 总体指标</h3>
              <div class="ds-summary">
                <div class="ds-summary-item">
                  <div class="ds-summary-val" style="color:var(--warning)">{{ dsResult.overall_mae }}</div>
                  <div class="ds-summary-label">整体 MAE</div>
                </div>
                <div class="ds-summary-item">
                  <div class="ds-summary-val" style="color:var(--danger)">{{ dsResult.overall_mse }}</div>
                  <div class="ds-summary-label">整体 RMSE</div>
                </div>
                <div class="ds-summary-item">
                  <div class="ds-summary-val" style="color:var(--success)">{{ dsResult.overall_accuracy }}%</div>
                  <div class="ds-summary-label">计数准确率</div>
                </div>
                <div class="ds-summary-item">
                  <div class="ds-summary-val" style="color:var(--accent)">{{ dsResult.total_scenes }}</div>
                  <div class="ds-summary-label">场景数</div>
                </div>
                <div class="ds-summary-item">
                  <div class="ds-summary-val" style="color:#a040ff">{{ dsResult.total_gt }}</div>
                  <div class="ds-summary-label">GT 总人数</div>
                </div>
                <div class="ds-summary-item">
                  <div class="ds-summary-val" style="color:#40d0ff">{{ dsResult.total_pred }}</div>
                  <div class="ds-summary-label">预测总人数</div>
                </div>
              </div>
            </div>

            <!-- 图表区：两行两列 -->
            <div style="flex:1;display:flex;flex-direction:column;gap:8px;overflow:hidden">
              <!-- 第一行：散点图 + 误差分布 -->
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:1;min-height:0">
                <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
                  <h3 style="flex-shrink:0">📍 预测 vs 真实人数散点图</h3>
                  <div ref="dsScatterChart" style="flex:1;min-height:100px"></div>
                </div>
                <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
                  <h3 style="flex-shrink:0">≡ 误差分布直方图</h3>
                  <div ref="dsErrorHistChart" style="flex:1;min-height:100px"></div>
                </div>
              </div>
              <!-- 第二行：密度分组箱线图 + 场景MAE排序 -->
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:1;min-height:0">
                <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
                  <h3 style="flex-shrink:0">⊠ 不同密度等级误差箱线图</h3>
                  <div ref="dsBoxChart" style="flex:1;min-height:100px"></div>
                </div>
                <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
                  <h3 style="flex-shrink:0">🏆 各场景 MAE 排序</h3>
                  <div ref="dsMaeBarChart" style="flex:1;min-height:100px"></div>
                </div>
              </div>
            </div>
          </template>
        </template>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onActivated, onUnmounted, inject, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'

export default {
  name: 'ComparisonView',
  setup() {
    const c = getChartColors()
    const globalTasks = inject('globalTasks')
    const doneTasks = computed(() => globalTasks.value.filter(t => t.status === 'done'))

    // ====== 模式切换 ======
    const mode = ref('task')  // 'task' | 'dataset'

    // ====== 任务对比模式 ======
    const selectedIds = ref(new Set())
    const taskResults = ref({})
    const bottomChartMode = ref('bar')

    const countCompareChart = ref(null)
    const modeChart = ref(null)
    const densityCompareChart = ref(null)
    let countCompInst = null, modeChartInst = null, densityCompInst = null

    const taskColors = new Map()
    const colorPalette = [c.blue, c.green, c.orange, c.red, '#a040ff', '#40d0ff']

    const bottomChartLabel = computed(() => {
      const m = { bar: '≡ 关键指标柱状图对比', histogram: '≡ 人数分布直方图', scatter: '📍 帧间散点对比', box: '⊠ 人数箱线图分布', heatmap: '⊛ 帧人数热力图', stacked: '↗ 堆叠面积图' }
      return m[bottomChartMode.value] || ''
    })

    // 取消正在进行的异步加载
    const _loadingTasks = new Map() // taskId → cancel function

    function toggleTask(taskId) {
      const s = new Set(selectedIds.value)
      if (s.has(taskId)) {
        // 移除：取消加载中的请求，立即清理
        if (_loadingTasks.has(taskId)) {
          _loadingTasks.get(taskId)()
          _loadingTasks.delete(taskId)
        }
        s.delete(taskId)
        delete taskResults.value[taskId]
        taskColors.delete(taskId)
        selectedIds.value = s
        // 立即更新（无防抖）
        if (_updateTimer) { clearTimeout(_updateTimer); _updateTimer = null }
        nextTick(() => updateAllCharts())
      } else {
        s.add(taskId)
        selectedIds.value = s
        taskColors.set(taskId, colorPalette[taskColors.size % colorPalette.length])
        loadTaskResult(taskId)
      }
    }

    async function loadTaskResult(taskId) {
      let cancelled = false
      _loadingTasks.set(taskId, () => { cancelled = true })
      try {
        const res = await axios.get(`/api/v1/video/result/${taskId}`)
        _loadingTasks.delete(taskId)
        if (cancelled || !selectedIds.value.has(taskId)) return
        taskResults.value[taskId] = res.data
        _ensureChartsInited()
        scheduleUpdate()
      } catch (e) {
        _loadingTasks.delete(taskId)
        if (cancelled) return
        const s = new Set(selectedIds.value)
        s.delete(taskId)
        selectedIds.value = s
        taskColors.delete(taskId)
        nextTick(() => updateAllCharts())
      }
    }

    const compareMetrics = computed(() => {
      const result = [
        { key: 'maxCount', label: '最大人数', values: {} },
        { key: 'avgCount', label: '平均人数', values: {} },
        { key: 'totalFrames', label: '总帧数', values: {} },
        { key: 'fps', label: '视频FPS', values: {} },
      ]
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const frames = r.frames || []
        const avg = frames.length > 0 ? Math.round(frames.reduce((s, f) => s + f.count, 0) / frames.length) : 0
        const max = frames.length > 0 ? Math.max(...frames.map(f => f.count)) : 0
        result[0].values[tid] = max
        result[1].values[tid] = avg
        result[2].values[tid] = r.total_frames || 0
        result[3].values[tid] = r.fps || 0
      }
      return result
    })

    // 防抖: 避免短时间内多次重绘
    let _updateTimer = null
    function scheduleUpdate() {
      if (_updateTimer) clearTimeout(_updateTimer)
      _updateTimer = setTimeout(() => {
        _updateTimer = null
        updateAllCharts()
      }, 80)
    }

    function _clearChart(inst) {
      if (!inst || inst.isDisposed()) return
      inst.setOption({ series: [], legend: { data: [] } }, true)
    }

    function updateAllCharts() {
      if (selectedIds.value.size === 0) {
        // 无选中任务 → 清空所有图表
        _clearChart(countCompInst)
        _clearChart(modeChartInst)
        _clearChart(densityCompInst)
        return
      }
      updateCountCompareChart()
      updateDensityCompareChart()
      updateModeChart()
    }

    function updateModeChart() {
      if (modeChart.value && (!modeChartInst || modeChartInst.isDisposed()))
        modeChartInst = echarts.init(modeChart.value, getEchartsTheme())
      if (!modeChartInst || selectedIds.value.size === 0) return
      const mode = bottomChartMode.value
      if (mode === 'bar') updateBarChart()
      else if (mode === 'histogram') updateHistogramChart()
      else if (mode === 'scatter') updateScatterChart()
      else if (mode === 'box') updateBoxChart()
      else if (mode === 'heatmap') updateHeatmapChart()
      else if (mode === 'stacked') updateStackedChart()
    }

    function updateCountCompareChart() {
      if (countCompareChart.value && (!countCompInst || countCompInst.isDisposed()))
        countCompInst = echarts.init(countCompareChart.value, getEchartsTheme())
      if (!countCompInst) return
      const series = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const frames = r.frames || []
        series.push({
          name: tid.substring(0, 8), type: 'line', smooth: true,
          data: frames.map(f => f.count),
          lineStyle: { color: taskColors.get(tid), width: 1.5 },
          symbol: 'none',
        })
      }
      countCompInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: series.length ? [...selectedIds.value].map(t => t.substring(0, 8)) : [], bottom: 0, textStyle: { color: c.axis, fontSize: 9 } },
        grid: { top: 8, right: 16, bottom: 30, left: 44 },
        xAxis: { type: 'category', axisLabel: { color: c.axis, fontSize: 9, interval: 'auto' } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series: series.length ? series : [{ type: 'line', data: [] }],
      }, true)
    }

    function updateBarChart() {
      if (!modeChartInst) return
      const metrics = compareMetrics.value
      const categories = metrics.map(m => m.label)
      const series = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        series.push({
          name: tid.substring(0, 8), type: 'bar',
          data: metrics.map(m => m.values[tid] || 0),
          itemStyle: { color: taskColors.get(tid), borderRadius: [2, 2, 0, 0] },
        })
      }
      modeChartInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: series.map(s => s.name), bottom: 0, textStyle: { color: c.axis, fontSize: 9 } },
        grid: { top: 8, right: 12, bottom: 30, left: 40 },
        xAxis: { type: 'category', data: categories, axisLabel: { color: c.axis, fontSize: 9 } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series,
      }, true)
    }

    function updateBoxChart() {
      if (!modeChartInst) return
      if (selectedIds.value.size === 0) { modeChartInst.setOption({ series: [] }, true); return }

      // 每个任务统计 min/Q1/median/Q3/max
      const categories = []
      const boxData = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const counts = (r.frames || []).map(f => f.count).sort((a, b) => a - b)
        if (!counts.length) continue
        const n = counts.length
        categories.push(tid.substring(0, 8))
        boxData.push([
          counts[0],
          counts[Math.floor(n * 0.25)],
          counts[Math.floor(n * 0.5)],
          counts[Math.floor(n * 0.75)],
          counts[n - 1],
        ])
      }

      if (!boxData.length) { modeChartInst.setOption({ series: [] }, true); return }

      // 重初始化（防 DOM 变化）
      if (modeChartInst && !modeChartInst.isDisposed()) modeChartInst.dispose()
      modeChartInst = echarts.init(modeChart.value, getEchartsTheme())

      modeChartInst.setOption({
        tooltip: { trigger: 'item', formatter: p => {
          const d = p.data
          return `${p.name}<br/>最小: ${d[0]}<br/>Q1: ${d[1]}<br/>中位数: ${d[2]}<br/>Q3: ${d[3]}<br/>最大: ${d[4]}`
        }},
        grid: { top: 8, right: 16, bottom: 30, left: 40 },
        xAxis: {
          type: 'category', data: categories,
          axisLabel: { color: c.axis, fontSize: 9, rotate: 15 },
        },
        yAxis: { type: 'value', name: '人数', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          type: 'boxplot',
          data: boxData.map((d, i) => ({
            value: d,
            itemStyle: { color: [...taskColors.values()][i] || '#4da6ff', borderColor: [...taskColors.values()][i] || '#4da6ff' }
          })),
        }],
      }, true)
    }

    function updateHeatmapChart() {
      if (!modeChartInst) return
      if (selectedIds.value.size === 0) { modeChartInst.setOption({ series: [] }, true); return }

      // 统一采样到相同帧数进行对比
      const maxFrames = 60
      const taskIds = [...selectedIds.value]
      const yLabels = taskIds.map(t => t.substring(0, 8))
      const heatData = []
      let globalMax = 1

      taskIds.forEach((tid, rowIdx) => {
        const r = taskResults.value[tid]
        if (!r) return
        const frames = r.frames || []
        if (!frames.length) return
        const step = Math.max(1, Math.floor(frames.length / maxFrames))
        for (let i = 0; i < maxFrames; i++) {
          const srcIdx = Math.min(i * step, frames.length - 1)
          const cnt = frames[srcIdx]?.count || 0
          if (cnt > globalMax) globalMax = cnt
          heatData.push([i, rowIdx, cnt])
        }
      })

      if (!heatData.length) { modeChartInst.setOption({ series: [] }, true); return }

      if (modeChartInst && !modeChartInst.isDisposed()) modeChartInst.dispose()
      modeChartInst = echarts.init(modeChart.value, getEchartsTheme())

      modeChartInst.setOption({
        tooltip: { position: 'top' },
        grid: { top: 4, right: 20, bottom: 30, left: 60 },
        xAxis: { type: 'category', data: Array.from({length:maxFrames},(_,i)=>i+1), axisLabel:{color:c.axis,fontSize:8,interval:9}, splitLine:{show:false} },
        yAxis: { type: 'category', data: yLabels, axisLabel:{color:c.axis,fontSize:9}, splitLine:{show:false} },
        visualMap: { min: 0, max: globalMax, calculable: true, orient: 'vertical', right: 4, top: '12%', bottom: '18%',
          inRange: { color: ['#0a1628','#1a3d7c','#2f6fed','#40d870','#f0c040','#ff6040'] },
          textStyle: { color: c.axis, fontSize: 8 } },
        series: [{ type: 'heatmap', data: heatData, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.4)' } } }],
      }, true)
    }

    function updateStackedChart() {
      if (!modeChartInst) return
      if (selectedIds.value.size === 0) { modeChartInst.setOption({ series: [] }, true); return }

      const maxFrames = 80
      const series = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const frames = r.frames || []
        if (!frames.length) continue
        const step = Math.max(1, Math.floor(frames.length / maxFrames))
        const data = []
        for (let i = 0; i < maxFrames; i++) {
          data.push(frames[Math.min(i * step, frames.length - 1)]?.count || 0)
        }
        series.push({
          name: tid.substring(0, 8), type: 'line', stack: 'total',
          areaStyle: { opacity: 0.4 },
          lineStyle: { width: 1 },
          data, smooth: true,
          symbol: 'none',
        })
      }

      if (!series.length) { modeChartInst.setOption({ series: [] }, true); return }

      if (modeChartInst && !modeChartInst.isDisposed()) modeChartInst.dispose()
      modeChartInst = echarts.init(modeChart.value, getEchartsTheme())

      modeChartInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: series.map(s=>s.name), bottom: 0, textStyle:{color:c.axis,fontSize:9} },
        grid: { top: 8, right: 16, bottom: 30, left: 44 },
        xAxis: { type: 'category', axisLabel:{show:false}, splitLine:{show:false} },
        yAxis: { type: 'value', axisLabel:{color:c.axis,fontSize:9} },
        series,
        color: [...taskColors.values()],
      }, true)
    }

    function updateHistogramChart() {
      if (!modeChartInst) return
      const series = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const frames = r.frames || []
        const counts = frames.map(f => f.count)
        if (!counts.length) continue
        const maxC = Math.max(...counts)
        const minC = Math.min(...counts)
        const binCount = 15
        const binWidth = Math.max(1, Math.ceil((maxC - minC) / binCount))
        const bins = Array(binCount).fill(0)
        for (let i = 0; i < binCount; i++) {
          const lo = minC + i * binWidth
          // labels not needed in series
        }
        counts.forEach(c => {
          const idx = Math.min(binCount - 1, Math.floor((c - minC) / binWidth))
          bins[idx]++
        })
        series.push({
          name: tid.substring(0, 8), type: 'bar',
          data: bins,
          itemStyle: { color: taskColors.get(tid), borderRadius: [2, 2, 0, 0] },
        })
      }
      modeChartInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: [...selectedIds.value].map(t => t.substring(0, 8)), bottom: 0, textStyle: { color: c.axis, fontSize: 9 } },
        grid: { top: 8, right: 12, bottom: 30, left: 40 },
        xAxis: { type: 'category', axisLabel: { color: c.axis, fontSize: 8, rotate: 30, interval: 2 } },
        yAxis: { type: 'value', name: '帧数', axisLabel: { color: c.axis, fontSize: 9 } },
        series,
      }, true)
    }

    function updateScatterChart() {
      if (!modeChartInst) return
      const series = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const frames = r.frames || []
        const data = frames.map((f, i) => [i + 1, f.count])
        series.push({
          name: tid.substring(0, 8), type: 'scatter',
          data: data.slice(0, 3000),
          symbolSize: 4,
          itemStyle: { color: taskColors.get(tid), opacity: 0.5 },
        })
      }
      modeChartInst.setOption({
        tooltip: { trigger: 'item', formatter: p => `${p.seriesName}: 帧${p.value[0]}, 人数${p.value[1]}` },
        legend: { data: [...selectedIds.value].map(t => t.substring(0, 8)), bottom: 0, textStyle: { color: c.axis, fontSize: 9 } },
        grid: { top: 8, right: 16, bottom: 30, left: 44 },
        xAxis: { type: 'value', name: '帧号', axisLabel: { color: c.axis, fontSize: 9 } },
        yAxis: { type: 'value', name: '人数', axisLabel: { color: c.axis, fontSize: 9 } },
        series,
      }, true)
    }

    function updateDensityCompareChart() {
      if (densityCompareChart.value && (!densityCompInst || densityCompInst.isDisposed()))
        densityCompInst = echarts.init(densityCompareChart.value, getEchartsTheme())
      if (!densityCompInst) return
      const categories = ['极低', '低', '中低', '中', '中高', '高', '极高']
      const series = []
      for (const tid of selectedIds.value) {
        const r = taskResults.value[tid]
        if (!r) continue
        const frames = r.frames || []
        const counts = frames.map(f => f.count)
        if (!counts.length) continue
        const maxC = Math.max(...counts)
        const ranges = [0.01, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0].map(r => Math.max(1, Math.round(r * maxC)))
        const bins = Array(7).fill(0)
        counts.forEach(c => {
          for (let i = 6; i >= 0; i--) { if (c >= ranges[i]) { bins[i]++; break } }
        })
        series.push({
          name: tid.substring(0, 8), type: 'bar',
          data: bins,
          itemStyle: { color: taskColors.get(tid), borderRadius: [2, 2, 0, 0] },
        })
      }
      densityCompInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: series.length ? [...selectedIds.value].map(t => t.substring(0, 8)) : [], bottom: 0, textStyle: { color: c.axis, fontSize: 9 } },
        grid: { top: 8, right: 12, bottom: 30, left: 40 },
        xAxis: { type: 'category', data: categories, axisLabel: { color: c.axis, fontSize: 9 } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series: series.length ? series : [{ type: 'bar', data: [] }],
      }, true)
    }

    // 初始化图表
    function _ensureChartsInited() {
      if (countCompareChart.value && !countCompInst)
        countCompInst = echarts.init(countCompareChart.value, getEchartsTheme())
      if (densityCompareChart.value && !densityCompInst)
        densityCompInst = echarts.init(densityCompareChart.value, getEchartsTheme())
      if (modeChart.value && !modeChartInst)
        modeChartInst = echarts.init(modeChart.value, getEchartsTheme())
    }
    function initAllCharts() {
      if (modeChartInst) { modeChartInst.dispose(); modeChartInst = null }
      _ensureChartsInited()
      if (selectedIds.value.size) updateAllCharts()
    }

    function resizeAllCharts() {
      [countCompInst, modeChartInst, densityCompInst].forEach(c => c?.resize())
    }

    let resizeObserver = null
    function observeResize() {
      if (resizeObserver) resizeObserver.disconnect()
      const el = document.querySelector('.compare-page .center-panel')
      if (!el || !window.ResizeObserver) return
      resizeObserver = new ResizeObserver(() => {
        resizeAllCharts()
        resizeDatasetCharts()
      })
      resizeObserver.observe(el)
    }

    // ====== 数据集测试模式 ======
    const dsRunning = ref(false)
    const dsProgress = ref(0)
    const dsMessage = ref('')
    const dsInterval = ref(4)
    const dsTasks = ref([])
    const dsSelectedId = ref('')
    const dsResult = ref(null)
    const dsDensityFilter = ref('all')
    const dsSceneFilter = ref('all')
    const dsSceneCount = ref(0)

    const dsScatterChart = ref(null)
    const dsErrorHistChart = ref(null)
    const dsBoxChart = ref(null)
    const dsMaeBarChart = ref(null)
    let dsScatterInst = null, dsErrorHistInst = null, dsBoxInst = null, dsMaeBarInst = null

    // 场景类型列表
    const dsSceneTypes = computed(() => {
      if (!dsResult.value?.scenes) return []
      const types = new Set()
      dsResult.value.scenes.forEach(s => types.add(s.scene_type))
      return [...types].filter(Boolean).sort()
    })

    // 过滤后的场景列表
    const dsFilteredScenes = computed(() => {
      if (!dsResult.value?.scenes) return []
      return dsResult.value.scenes.filter(s => {
        if (dsDensityFilter.value !== 'all' && s.density_label !== dsDensityFilter.value) return false
        if (dsSceneFilter.value !== 'all' && s.scene_type !== dsSceneFilter.value) return false
        return true
      })
    })

    async function loadDsTasks() {
      try {
        const res = await axios.get('/api/v1/dataset/test/list')
        dsTasks.value = res.data || []
      } catch (e) { /* ignore */ }
    }

    async function loadDsSceneCount() {
      try {
        const res = await axios.get('/api/v1/dataset/scenes')
        dsSceneCount.value = (res.data || []).length
      } catch (e) { dsSceneCount.value = 0 }
    }

    async function startDatasetTest() {
      dsRunning.value = true
      dsProgress.value = 0
      dsMessage.value = '正在初始化...'
      try {
        const res = await axios.post('/api/v1/dataset/test/start', null, {
          params: { test_interval: dsInterval.value, test_split: 'test', model: 'STEERER' }
        })
        const taskId = res.data.task_id
        dsSelectedId.value = taskId
        pollDatasetTask(taskId)
      } catch (e) {
        dsMessage.value = '启动失败: ' + (e.response?.data?.error || e.message)
        dsRunning.value = false
      }
    }

    function pollDatasetTask(taskId) {
      const interval = setInterval(async () => {
        try {
          const res = await axios.get(`/api/v1/dataset/test/status/${taskId}`)
          const t = res.data
          dsProgress.value = t.progress || 0
          dsMessage.value = t.message || ''
          if (t.status === 'done') {
            clearInterval(interval)
            dsRunning.value = false
            dsMessage.value = ''
            await loadDatasetResult(taskId)
            await loadDsTasks()
          }
          if (t.status === 'error') {
            clearInterval(interval)
            dsRunning.value = false
            dsMessage.value = '测试出错: ' + t.message
          }
        } catch (e) {
          clearInterval(interval)
          dsRunning.value = false
        }
      }, 2000)
    }

    async function selectDatasetTask(taskId) {
      dsSelectedId.value = taskId
      await loadDatasetResult(taskId)
    }

    async function loadDatasetResult(taskId) {
      try {
        const res = await axios.get(`/api/v1/dataset/test/result/${taskId}`)
        dsResult.value = res.data
        await nextTick()
        initDatasetCharts()
        updateDatasetCharts()
      } catch (e) {
        dsResult.value = null
      }
    }

    // ====== 数据集图表 ======
    function initDatasetCharts() {
      if (dsScatterChart.value) {
        if (dsScatterInst) dsScatterInst.dispose()
        dsScatterInst = echarts.init(dsScatterChart.value, getEchartsTheme())
      }
      if (dsErrorHistChart.value) {
        if (dsErrorHistInst) dsErrorHistInst.dispose()
        dsErrorHistInst = echarts.init(dsErrorHistChart.value, getEchartsTheme())
      }
      if (dsBoxChart.value) {
        if (dsBoxInst) dsBoxInst.dispose()
        dsBoxInst = echarts.init(dsBoxChart.value, getEchartsTheme())
      }
      if (dsMaeBarChart.value) {
        if (dsMaeBarInst) dsMaeBarInst.dispose()
        dsMaeBarInst = echarts.init(dsMaeBarChart.value, getEchartsTheme())
      }
      updateDatasetCharts()
    }

    function resizeDatasetCharts() {
      [dsScatterInst, dsErrorHistInst, dsBoxInst, dsMaeBarInst].forEach(c => c?.resize())
    }

    function updateDatasetCharts() {
      updateDsScatterChart()
      updateDsErrorHistChart()
      updateDsBoxChart()
      updateDsMaeBarChart()
    }

    function updateDsScatterChart() {
      if (!dsScatterInst || !dsResult.value) return
      const scenes = dsFilteredScenes.value
      const data = []
      scenes.forEach(s => {
        s.frames.forEach(f => {
          data.push([f.gt_count, f.pred_count])
        })
      })

      // 对角线
      const maxVal = Math.max(...data.map(d => Math.max(d[0], d[1])), 1)
      const diagData = [[0, 0], [maxVal, maxVal]]

      dsScatterInst.setOption({
        tooltip: {
          trigger: 'item',
          formatter: p => `GT: ${p.value[0]}<br/>预测: ${p.value[1]}`
        },
        grid: { top: 8, right: 20, bottom: 36, left: 48 },
        xAxis: { type: 'value', name: 'GT 真实人数', nameLocation: 'center', nameGap: 22, axisLabel: { color: c.axis, fontSize: 9 } },
        yAxis: { type: 'value', name: '预测人数', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [
          {
            type: 'line', data: diagData,
            lineStyle: { color: 'rgba(255,255,255,0.15)', type: 'dashed', width: 1 },
            symbol: 'none', silent: true,
          },
          {
            type: 'scatter', data,
            symbolSize: 5,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
                { offset: 0, color: c.blue },
                { offset: 1, color: '#a040ff' }
              ]),
              opacity: 0.6,
            },
          }
        ]
      })
    }

    function updateDsErrorHistChart() {
      if (!dsErrorHistInst || !dsResult.value) return
      const scenes = dsFilteredScenes.value
      const errors = []
      scenes.forEach(s => {
        s.frames.forEach(f => {
          errors.push(f.pred_count - f.gt_count)
        })
      })

      const minE = Math.min(...errors)
      const maxE = Math.max(...errors)
      const range = Math.max(Math.abs(minE), Math.abs(maxE), 10)
      const binCount = 30
      const binWidth = (2 * range) / binCount
      const bins = Array(binCount).fill(0)
      const labels = []
      for (let i = 0; i < binCount; i++) {
        labels.push(Math.round(-range + i * binWidth))
      }
      errors.forEach(e => {
        const idx = Math.min(binCount - 1, Math.max(0, Math.floor((e + range) / binWidth)))
        bins[idx]++
      })

      dsErrorHistInst.setOption({
        tooltip: { trigger: 'axis', formatter: p => `误差: ${p[0].name}<br/>频次: ${p[0].value}` },
        grid: { top: 8, right: 16, bottom: 30, left: 48 },
        xAxis: {
          type: 'category', data: labels,
          axisLabel: { color: c.axis, fontSize: 8, rotate: 45, interval: 4 },
          name: '误差 (预测 - 真实)',
        },
        yAxis: { type: 'value', name: '频次', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          type: 'bar', data: bins,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: c.red }, { offset: 1, color: c.blue }
            ]),
            borderRadius: [2, 2, 0, 0],
          },
          markLine: {
            silent: true,
            data: [{ xAxis: Math.floor(binCount / 2), lineStyle: { color: c.green, type: 'dashed' }, label: { formatter: '零误差' } }],
            lineStyle: { color: c.green, type: 'dashed' },
          }
        }]
      })
    }

    function updateDsBoxChart() {
      if (!dsBoxInst || !dsResult.value) return
      const byDensity = dsResult.value.by_density || {}

      // 为每个密度等级收集误差数据
      const densityOrder = ['0', '1', '2', '3']
      const densityNames = { '0': '极低密度', '1': '低密度', '2': '中密度', '3': '高密度' }

      // 重新从原始数据收集
      const allScenes = dsResult.value.scenes || []
      const densityErrors = { '0': [], '1': [], '2': [], '3': [] }
      allScenes.forEach(s => {
        const d = s.density_label
        if (densityErrors[d]) {
          s.frames.forEach(f => {
            densityErrors[d].push(Math.abs(f.pred_count - f.gt_count))
          })
        }
      })

      const seriesData = densityOrder.filter(d => densityErrors[d].length > 0).map(d => {
        const vals = densityErrors[d].sort((a, b) => a - b)
        const n = vals.length
        const min = vals[0]
        const max = vals[n - 1]
        const q1 = vals[Math.floor(n * 0.25)]
        const q2 = vals[Math.floor(n * 0.5)]
        const q3 = vals[Math.floor(n * 0.75)]
        const mean = vals.reduce((s, v) => s + v, 0) / n
        return { name: densityNames[d] || `密度${d}`, data: [min, q1, q2, q3, max, mean] }
      })

      dsBoxInst.setOption({
        tooltip: { trigger: 'item', formatter: p => {
          const d = p.data
          return `${p.name}<br/>最小值: ${d[0]}<br/>Q1: ${d[1]}<br/>中位数: ${d[2]}<br/>Q3: ${d[3]}<br/>最大值: ${d[4]}<br/>均值: ${d[5].toFixed(1)}`
        }},
        grid: { top: 8, right: 20, bottom: 30, left: 48 },
        xAxis: {
          type: 'category', data: seriesData.map(s => s.name),
          axisLabel: { color: c.axis, fontSize: 9 },
        },
        yAxis: { type: 'value', name: '绝对误差', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          type: 'boxplot',
          data: seriesData.map(s => [s.data[0], s.data[1], s.data[2], s.data[3], s.data[4]]),
          itemStyle: {
            color: c.blue,
            borderColor: c.blue,
            borderWidth: 1.5,
          },
          // 均值点
          markLine: {
            silent: true,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { color: c.orange, type: 'dotted' },
            data: seriesData.map((s, i) => ({ xAxis: s.name, yAxis: s.data[5], label: { formatter: `均值\n${s.data[5].toFixed(1)}` } }))
          }
        }]
      })
    }

    function updateDsMaeBarChart() {
      if (!dsMaeBarInst || !dsResult.value) return
      const scenes = [...dsFilteredScenes.value].sort((a, b) => b.mae - a.mae)
      const top20 = scenes.slice(0, 20)

      dsMaeBarInst.setOption({
        tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>MAE: ${p[0].value}<br/>GT: ${top20[p[0].dataIndex]?.total_gt}<br/>Pred: ${top20[p[0].dataIndex]?.total_pred}` },
        grid: { top: 8, right: 20, bottom: 50, left: 48 },
        xAxis: {
          type: 'category', data: top20.map(s => s.scene_name.replace('scene_', '')),
          axisLabel: { color: c.axis, fontSize: 8, rotate: 45 },
        },
        yAxis: { type: 'value', name: 'MAE', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          type: 'bar',
          data: top20.map(s => s.mae),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#a040ff' }, { offset: 1, color: c.blue }
            ]),
            borderRadius: [2, 2, 0, 0],
          },
        }]
      })
    }

    // ====== Watch 模式切换 ======
    watch(mode, async (newMode) => {
      if (newMode === 'task') {
        await nextTick()
        initAllCharts()
        resizeAllCharts()
        if (selectedIds.value.size) updateAllCharts()
      } else if (newMode === 'dataset') {
        await loadDsTasks()
        await loadDsSceneCount()
        if (dsSelectedId.value) {
          await loadDatasetResult(dsSelectedId.value)
        }
      }
    })

    watch([dsDensityFilter, dsSceneFilter], () => {
      updateDatasetCharts()
    })

    watch(bottomChartMode, async () => {
      // 销毁旧实例 (DOM 已被 :key 重建)
      if (modeChartInst) { modeChartInst.dispose(); modeChartInst = null }
      await nextTick()
      resizeAllCharts()
      updateAllCharts()
    })

    function onThemeChange() {
      // Dispose all chart instances
      [countCompInst, modeChartInst, densityCompInst].forEach(c => c?.dispose())
      countCompInst = null; modeChartInst = null; densityCompInst = null
      ;[dsScatterInst, dsErrorHistInst, dsBoxInst, dsMaeBarInst].forEach(c => c?.dispose())
      dsScatterInst = null; dsErrorHistInst = null; dsBoxInst = null; dsMaeBarInst = null
      initAllCharts()
      resizeAllCharts()
      if (selectedIds.value.size > 0) updateAllCharts()
      if (dsResult.value) { initDatasetCharts(); updateDatasetCharts() }
    }

    onMounted(() => {
      initAllCharts()
      window.addEventListener('resize', () => { resizeAllCharts(); resizeDatasetCharts() })
      window.addEventListener('themechange', onThemeChange)
      observeResize()
      loadDsSceneCount()
    })

    onActivated(() => {
      initAllCharts()
      resizeAllCharts()
      if (selectedIds.value.size > 0) updateAllCharts()
      loadDsTasks()
    })

    onUnmounted(() => {
      [countCompInst, modeChartInst, densityCompInst].forEach(c => c?.dispose())
      [dsScatterInst, dsErrorHistInst, dsBoxInst, dsMaeBarInst].forEach(c => c?.dispose())
      window.removeEventListener('resize', () => { resizeAllCharts(); resizeDatasetCharts() })
      window.removeEventListener('themechange', onThemeChange)
      if (resizeObserver) resizeObserver.disconnect()
    })

    return {
      mode,
      // 任务对比
      doneTasks, selectedIds, taskResults, taskColors, bottomChartMode, bottomChartLabel,
      compareMetrics,
      countCompareChart, modeChart, densityCompareChart,
      toggleTask,
      // 数据集测试
      dsRunning, dsProgress, dsMessage, dsInterval,
      dsTasks, dsSelectedId, dsResult,
      dsDensityFilter, dsSceneFilter, dsSceneCount, dsSceneTypes,
      dsScatterChart, dsErrorHistChart, dsBoxChart, dsMaeBarChart,
      startDatasetTest, selectDatasetTask,
    }
  }
}
</script>

<style scoped>
.compare-page { height: 100%; }
.main-content { display: flex; height: 100%; overflow: hidden; }
.left-panel { width: 250px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; }
.center-panel { flex: 1; display: flex; flex-direction: column; padding: 8px; overflow: hidden; }

/* 模式切换 */
.mode-tabs {
  display: flex; gap: 4px;
}
.mode-tabs button {
  flex: 1; padding: 6px 8px; border: 1px solid var(--border-subtle);
  background: var(--bg-card); color: var(--text-dim);
  border-radius: 3px; cursor: pointer; font-size: 11px; transition: all 0.2s;
}
.mode-tabs button.active {
  background: rgba(20,80,200,0.2); border-color: var(--accent); color: var(--accent);
}
.mode-tabs button:hover:not(.active) {
  background: var(--border-subtle);
}

.task-list { max-height: 200px; overflow-y: auto; }

.task-item.selected {
  border-left-color: var(--accent);
  background: var(--border-subtle);
}

.stats-grid { display: flex; flex-direction: column; gap: 8px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 3px; padding: 8px; }

.metric-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 3px 0;
}
.metric-tag {
  font-size: 9px; font-family: monospace;
  padding: 1px 5px; border: 1px solid;
  border-radius: 2px; color: var(--text-dim);
}

/* 数据集模式样式 */
.btn-start {
  width: 100%; padding: 10px; border: 1px solid var(--accent);
  background: rgba(20,80,200,0.15); color: var(--accent);
  border-radius: 3px; cursor: pointer; font-size: 13px;
  margin-top: 8px; transition: all 0.2s;
}
.btn-start:hover:not(:disabled) { background: rgba(20,80,200,0.25); }
.btn-start:disabled { opacity: 0.5; cursor: not-allowed; }

.progress-bar {
  height: 4px; background: var(--border-subtle); border-radius: 2px;
  margin-top: 8px; overflow: hidden;
}
.progress-fill {
  height: 100%; background: linear-gradient(90deg, var(--accent), #a040ff);
  border-radius: 2px; transition: width 0.5s ease;
}
.ds-msg { font-size: 11px; color: var(--text-dim); margin-top: 6px; text-align: center; }

.ds-summary {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.ds-summary-item { text-align: center; }
.ds-summary-val { font-size: 22px; font-family: monospace; font-weight: bold; }
.ds-summary-label { font-size: 10px; color: var(--text-dim); margin-top: 2px; }

.param-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px; font-size: 11px; color: var(--text-dim);
}
.param-select {
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  color: var(--text-primary); border-radius: 3px; padding: 4px 6px; font-size: 11px;
}
.param-select option {
  background: var(--bg-card); color: var(--text-primary);
}

.scene-filter { margin-top: 4px; }

.status-dot {
  width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; flex-shrink: 0;
}
.status-done { background: var(--success); }
.status-running { background: var(--warning); animation: pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
</style>

<!-- 全局：select 下拉选项颜色 -->
<style>
.param-select option,
.task-select option {
  background: #1a1f35;
  color: #e0e0e0;
}
</style>