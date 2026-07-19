<template>
  <div class="trajectory-page">
    <div class="main-content">
      <!-- 左侧 -->
      <aside class="left-panel">
        <div class="panel task-panel">
          <h3>☰ 已完成任务</h3>
          <div class="task-list">
            <div v-for="task in doneTasks" :key="task.task_id"
                 class="task-item" :class="{ active: selectedTaskId === task.task_id }"
                 @click="selectTask(task.task_id)">
              <span class="status-dot status-done"></span>
              <span style="font-family:monospace;font-size:11px">{{ task.task_id }}</span>
            </div>
            <div v-if="doneTasks.length === 0" style="color:var(--text-dim);font-size:12px;text-align:center;padding:20px">
              暂无已完成任务
            </div>
          </div>
        </div>

        <div class="panel" v-if="selectedTaskId">
          <h3>⊷ 轨迹参数</h3>
          <div class="param-row">
            <label>帧范围</label>
            <div style="display:flex;gap:4px;align-items:center;flex:1">
              <input type="number" v-model.number="frameStart" :min="1" :max="totalFrames"
                     style="width:50px;background:var(--bg-card);color:var(--text-primary);border: 1px solid var(--border-subtle);border-radius:3px;font-size:11px;padding:4px;text-align:center" />
              <span style="color:var(--text-dim)">-</span>
              <input type="number" v-model.number="frameEnd" :min="1" :max="totalFrames"
                     style="width:50px;background:var(--bg-card);color:var(--text-primary);border: 1px solid var(--border-subtle);border-radius:3px;font-size:11px;padding:4px;text-align:center" />
            </div>
          </div>
          <div class="param-row">
            <label>轨迹线长</label>
            <select v-model.number="trailLength" class="param-select">
              <option :value="5">5 帧</option>
              <option :value="10">10 帧</option>
              <option :value="20">20 帧</option>
              <option :value="30">30 帧</option>
            </select>
          </div>
          <div class="param-row">
            <label>显示模式</label>
            <select v-model="displayMode" class="param-select">
              <option value="trails">轨迹拖尾</option>
              <option value="flow">光流箭头</option>
              <option value="heat">运动热力</option>
            </select>
          </div>
          <div style="margin-top:8px">
            <button class="btn" style="width:100%;font-size:11px" @click="togglePlay">
              {{ isPlaying ? '⏹ 暂停' : '▸ 播放轨迹动画' }}
            </button>
          </div>
          <div v-if="isPlaying" style="margin-top:6px">
            <div class="progress-bar">
              <div class="fill" :style="{ width: animProgress + '%' }"></div>
            </div>
            <div style="text-align:center;font-size:10px;color:var(--accent);margin-top:4px">
              帧 {{ currentAnimFrame }} / {{ frameEnd }}
            </div>
          </div>
        </div>

        <div class="panel" v-if="selectedTaskId">
          <h3>≡ 运动统计</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:16px">{{ motionStats.totalTracks }}</div>
              <div class="stat-label">总轨迹数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:16px">{{ motionStats.avgMovement.toFixed(1) }}</div>
              <div class="stat-label">平均位移(px)</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:16px;color:var(--success)">{{ motionStats.dominantDir }}</div>
              <div class="stat-label">主导方向</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:16px;color:var(--warning)">{{ motionStats.activity }}%</div>
              <div class="stat-label">活跃度</div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中央 -->
      <main class="center-panel">
        <!-- 轨迹可视化 -->
        <div class="panel" style="flex:1;display:flex;flex-direction:column;overflow:hidden">
          <h3>🛤️ 人群移动轨迹 ({{ displayModeLabel }})</h3>
          <div ref="trajectoryChart" style="flex:1;min-height:300px"></div>
        </div>

        <!-- 底部图表 -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;height:180px">
          <!-- 运动方向直方图 -->
          <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
            <h3>🧭 运动方向分布</h3>
            <div ref="directionChart" style="flex:1"></div>
          </div>
          <!-- 位移量分布 -->
          <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
            <h3>📏 位移量分布</h3>
            <div ref="displacementChart" style="flex:1"></div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onUnmounted, inject } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'

export default {
  name: 'TrajectoryView',
  setup() {
    const c = getChartColors()
    const globalTasks = inject('globalTasks')
    const doneTasks = computed(() => globalTasks.value.filter(t => t.status === 'done'))
    const selectedTaskId = ref('')
    const allFrames = ref([])
    const totalFrames = ref(0)
    const videoWidth = ref(1920)
    const videoHeight = ref(1080)

    const frameStart = ref(1)
    const frameEnd = ref(60)
    const trailLength = ref(10)
    const displayMode = ref('trails')
    const isPlaying = ref(false)
    const currentAnimFrame = ref(1)
    const animProgress = ref(0)

    const trajectoryChart = ref(null)
    const directionChart = ref(null)
    const displacementChart = ref(null)
    let trajChartInst = null, dirChartInst = null, dispChartInst = null
    let playTimer = null

    const displayModeLabel = computed(() => {
      const m = { trails: '轨迹拖尾', flow: '光流箭头', heat: '运动热力' }
      return m[displayMode.value] || displayMode.value
    })

    const rangeFrames = computed(() => {
      if (!allFrames.value.length) return []
      return allFrames.value.slice(
        Math.max(0, frameStart.value - 1),
        Math.min(allFrames.value.length, frameEnd.value)
      )
    })

    // 动画播放时只取到当前帧的数据，否则取全范围
    const animFrames = computed(() => {
      if (isPlaying.value) {
        return rangeFrames.value.slice(0, Math.max(0, currentAnimFrame.value - frameStart.value + 1))
      }
      return rangeFrames.value
    })

    // 从相邻帧的检测点匹配计算运动信息
    const motionStats = computed(() => {
      const frames = rangeFrames.value
      let totalTracks = 0
      let totalDisplacement = 0
      let n = 0
      const dirBins = Array(8).fill(0) // N, NE, E, SE, S, SW, W, NW

      for (let i = 1; i < frames.length; i++) {
        const prev = frames[i - 1]
        const curr = frames[i]
        if (!prev.peaks || !curr.peaks || !prev.peaks.length || !curr.peaks.length) continue

        // 简单的最近邻匹配
        const used = new Set()
        for (let pi = 0; pi < Math.min(prev.peaks.length, curr.peaks.length); pi++) {
          let bestJ = -1, bestDist = Infinity
          for (let ci = 0; ci < curr.peaks.length; ci++) {
            if (used.has(ci)) continue
            const dx = curr.peaks[ci][0] - prev.peaks[pi][0]
            const dy = curr.peaks[ci][1] - prev.peaks[pi][1]
            const d = Math.sqrt(dx * dx + dy * dy)
            if (d < 50 && d < bestDist) { bestDist = d; bestJ = ci }
          }
          if (bestJ >= 0) {
            used.add(bestJ)
            totalDisplacement += bestDist
            n++
            // 方向分箱
            const dx = curr.peaks[bestJ][0] - prev.peaks[pi][0]
            const dy = curr.peaks[bestJ][1] - prev.peaks[pi][1]
            const angle = Math.atan2(dy, dx) * 180 / Math.PI
            const idx = Math.floor(((angle + 180 + 22.5) % 360) / 45)
            dirBins[idx % 8]++
          }
        }
        totalTracks += used.size
      }

      const avgMovement = n > 0 ? totalDisplacement / n : 0
      const maxDir = dirBins.indexOf(Math.max(...dirBins))
      const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
      const activePairs = frames.filter(f => f.peaks && f.peaks.length > 0).length
      const activity = frames.length > 0 ? Math.round(activePairs / frames.length * 100) : 0

      return { totalTracks, avgMovement, dominantDir: dirs[maxDir], activity, dirBins }
    })

    async function selectTask(taskId) {
      selectedTaskId.value = taskId
      try {
        const res = await axios.get(`/api/v1/video/result/${taskId}`)
        allFrames.value = res.data.frames || []
        totalFrames.value = res.data.total_frames || 0
        videoWidth.value = res.data.width || 1920
        videoHeight.value = res.data.height || 1080
        frameStart.value = 1
        frameEnd.value = Math.min(totalFrames.value, 60)
        updateAllCharts()
      } catch (e) { /* ignore */ }
    }

    function updateAllCharts() {
      updateTrajectoryChart()
      updateDirectionChart()
      updateDisplacementChart()
    }

    function updateTrajectoryChart() {
      if (!trajChartInst) return
      const frames = animFrames.value

      if (displayMode.value === 'heat') {
        // 运动热力模式
        const gridSize = 30
        const heatData = Array.from({ length: gridSize }, () => Array(gridSize).fill(0))
        frames.forEach(f => {
          if (f.peaks) f.peaks.forEach(([x, y]) => {
            const col = Math.min(gridSize - 1, Math.floor(x / videoWidth.value * gridSize))
            const row = Math.min(gridSize - 1, Math.floor(y / videoHeight.value * gridSize))
            heatData[row][col]++
          })
        })
        const flatData = []
        for (let r = 0; r < gridSize; r++)
          for (let c = 0; c < gridSize; c++)
            flatData.push([c, r, heatData[r][c]])

        const maxVal = Math.max(1, ...flatData.map(d => d[2]))
        trajChartInst.setOption({
          tooltip: { trigger: 'item' },
          grid: { top: 8, right: 16, bottom: 28, left: 28 },
          xAxis: { type: 'category', data: Array.from({length:gridSize},(_,i)=>''), axisLabel:{show:false}, splitLine:{show:false} },
          yAxis: { type: 'category', data: Array.from({length:gridSize},(_,i)=>''), axisLabel:{show:false}, splitLine:{show:false} },
          visualMap: { min: 0, max: maxVal, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
            inRange: { color: ['#081832','#1a5fd4','#4da6ff','#40d870','#ffa040','#ff2040'] }, textStyle: { color: '#5a80b0' } },
          series: [{ type: 'heatmap', data: flatData, label: { show: false } }]
        })
        return
      }

      // 轨迹/光流模式
      const allPoints = []
      const allLines = []
      frames.forEach(f => {
        if (f.peaks) f.peaks.forEach(([x, y]) => {
          allPoints.push([x, videoHeight.value - y])
        })
      })

      // 生成轨迹线
      for (let i = 1; i < frames.length; i++) {
        const prev = frames[i - 1]
        const curr = frames[i]
        if (!prev.peaks || !curr.peaks) continue
        const used = new Set()
        for (let pi = 0; pi < Math.min(prev.peaks.length, curr.peaks.length, 100); pi++) {
          let bestJ = -1, bestDist = Infinity
          for (let ci = 0; ci < curr.peaks.length; ci++) {
            if (used.has(ci)) continue
            const dx = curr.peaks[ci][0] - prev.peaks[pi][0]
            const dy = curr.peaks[ci][1] - prev.peaks[pi][1]
            const d = Math.sqrt(dx * dx + dy * dy)
            if (d < 50 && d < bestDist) { bestDist = d; bestJ = ci }
          }
          if (bestJ >= 0) {
            used.add(bestJ)
            allLines.push([
              [prev.peaks[pi][0], videoHeight.value - prev.peaks[pi][1]],
              [curr.peaks[bestJ][0], videoHeight.value - curr.peaks[bestJ][1]],
            ])
          }
        }
      }

      const series = [
        {
          type: 'scatter', data: allPoints.slice(0, 5000),
          symbolSize: displayMode.value === 'flow' ? 6 : 3,
          itemStyle: { color: c.blue, opacity: 0.7 },
          z: 2,
        }
      ]

      if (displayMode.value === 'trails') {
        series.push({
          type: 'lines', coordinateSystem: 'cartesian2d',
          data: allLines.slice(0, 2000).map(l => ({ coords: l })),
          lineStyle: { color: c.orange, width: 0.8, opacity: 0.5 },
          z: 1,
        })
      }

      trajChartInst.setOption({
        tooltip: { trigger: 'item', formatter: p => p.seriesType === 'lines' ? '轨迹段' : `(${Math.round(p.value[0])},${Math.round(videoHeight.value - p.value[1])})` },
        grid: { top: 8, right: 20, bottom: 28, left: 50 },
        xAxis: { type: 'value', name: 'X', max: videoWidth.value, axisLabel: { color: c.axis, fontSize: 9 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } } },
        yAxis: { type: 'value', name: 'Y', max: videoHeight.value, axisLabel: { color: c.axis, fontSize: 9 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } } },
        series,
      })
    }

    function updateDirectionChart() {
      if (!dirChartInst) return
      const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
      dirChartInst.setOption({
        tooltip: { trigger: 'item' },
        polar: { radius: ['30%', '75%'] },
        angleAxis: { type: 'category', data: dirs, axisLabel: { color: c.axis, fontSize: 9 } },
        radiusAxis: { axisLabel: { show: false } },
        series: [{
          type: 'bar', data: motionStats.value.dirBins.map((v, i) => ({ value: v, name: dirs[i] })),
          coordinateSystem: 'polar',
          itemStyle: { borderRadius: 2, color: p => ['#4da6ff','#5ea6ee','#40d870','#70e090','#ffa040','#ffb060','#ff4070','#ff6080'][p.dataIndex] }
        }]
      })
    }

    function updateDisplacementChart() {
      if (!dispChartInst) return
      // 模拟位移分布数据
      const bins = ['0-5', '5-10', '10-20', '20-30', '30-50', '50+']
      dispChartInst.setOption({
        tooltip: { trigger: 'axis' },
        grid: { top: 8, right: 12, bottom: 20, left: 40 },
        xAxis: { type: 'category', data: bins, axisLabel: { color: c.axis, fontSize: 9 } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          data: [40, 25, 18, 10, 5, 2], type: 'bar',
          itemStyle: { borderRadius: [2,2,0,0],
            color: new echarts.graphic.LinearGradient(0,0,0,1,[
              { offset:0, color:'rgba(77,166,255,0.8)' }, { offset:1, color:'rgba(77,166,255,0.1)' }
            ])
          }
        }]
      })
    }

    function initAllCharts() {
      if (trajectoryChart.value) {
        if (trajChartInst) trajChartInst.dispose()
        trajChartInst = echarts.init(trajectoryChart.value, getEchartsTheme())
      }
      if (directionChart.value) {
        if (dirChartInst) dirChartInst.dispose()
        dirChartInst = echarts.init(directionChart.value, getEchartsTheme())
      }
      if (displacementChart.value) {
        if (dispChartInst) dispChartInst.dispose()
        dispChartInst = echarts.init(displacementChart.value, getEchartsTheme())
      }
      if (allFrames.value.length) updateAllCharts()
    }

    function resizeAllCharts() {
      trajChartInst?.resize()
      dirChartInst?.resize()
      dispChartInst?.resize()
    }

    function togglePlay() {
      if (isPlaying.value) {
        stopPlay()
      } else {
        startPlay()
      }
    }

    function startPlay() {
      if (isPlaying.value) return
      isPlaying.value = true
      currentAnimFrame.value = frameStart.value

      playTimer = setInterval(() => {
        if (currentAnimFrame.value >= frameEnd.value) {
          currentAnimFrame.value = frameStart.value
        } else {
          currentAnimFrame.value++
        }
        animProgress.value = ((currentAnimFrame.value - frameStart.value) / (frameEnd.value - frameStart.value)) * 100
        updateTrajectoryChart()
      }, 200)
    }

    function stopPlay() {
      isPlaying.value = false
      if (playTimer) { clearInterval(playTimer); playTimer = null }
    }

    watch([displayMode, frameStart, frameEnd], updateAllCharts)

    function onThemeChange() {
      initAllCharts()
      resizeAllCharts()
      if (allFrames.value.length) updateAllCharts()
    }

    onMounted(() => {
      setTimeout(() => initAllCharts(), 200)
      window.addEventListener('resize', resizeAllCharts)
      window.addEventListener('themechange', onThemeChange)
    })

    onUnmounted(() => {
      stopPlay()
      trajChartInst?.dispose(); dirChartInst?.dispose(); dispChartInst?.dispose()
      window.removeEventListener('resize', resizeAllCharts)
      window.removeEventListener('themechange', onThemeChange)
    })

    return {
      doneTasks, selectedTaskId, totalFrames,
      frameStart, frameEnd, trailLength, displayMode, displayModeLabel,
      isPlaying, currentAnimFrame, animProgress, motionStats,
      trajectoryChart, directionChart, displacementChart,
      selectTask, togglePlay,
    }
  }
}
</script>

<style scoped>
.trajectory-page { height: 100%; width: 100%; position: relative; }
.main-content { display: flex; height: 100%; overflow: hidden; position: absolute; top: 0; left: 0; right: 0; bottom: 0; }
.left-panel { width: 230px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; }
.center-panel { flex: 1; display: flex; flex-direction: column; padding: 8px; overflow: hidden; min-width: 0; }

.task-panel { flex: 1; min-height: 200px; display: flex; flex-direction: column; overflow: hidden; }
.task-list { flex: 1; overflow-y: auto; min-height: 160px; }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 3px; padding: 8px; text-align: center; }

.param-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.param-row label { font-size: 11px; color: var(--text-dim); min-width: 60px; }
.param-select { flex: 1; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-subtle); padding: 5px 8px; border-radius: 3px; font-size: 11px; }
</style>
