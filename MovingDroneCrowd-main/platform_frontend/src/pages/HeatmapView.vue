<template>
  <div class="heatmap-page">
    <div class="main-content">
      <!-- 左侧控制 -->
      <aside class="left-panel">
        <div class="panel">
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

        <!-- 帧选择 -->
        <div class="panel" v-if="selectedTaskId">
          <h3>⊷ 帧选择</h3>
          <div style="text-align:center;margin-bottom:6px">
            <span class="digital" style="font-size:18px;color:var(--accent)">帧 {{ currentFrame }}</span>
          </div>
          <input type="range" :min="1" :max="totalFrames" v-model.number="currentFrame"
                 style="width:100%;accent-color:var(--accent);margin-bottom:8px" />
          <div style="display:flex;gap:4px">
            <button class="btn" title="上一帧" style="flex:1;height:26px;font-size:12px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = Math.max(1, currentFrame - 1)">◀</button>
            <button class="btn" title="下一帧" style="flex:1;height:26px;font-size:12px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = Math.min(totalFrames, currentFrame + 1)">▶</button>
          </div>
          <div style="display:flex;gap:4px;margin-top:4px">
            <button class="btn" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="togglePlay" :class="{ playing: isPlaying }">
              {{ isPlaying ? '⏸ 暂停' : '▶ 播放' }}
            </button>
            <select v-model.number="playSpeed" style="flex:1;height:26px;background:var(--bg-card);color:var(--text-primary);border: 1px solid var(--border-subtle);border-radius:3px;font-size:10px;padding:0 4px">
              <option :value="200">慢</option>
              <option :value="100">中</option>
              <option :value="50">快</option>
            </select>
          </div>
        </div>

        <!-- 配色方案 -->
        <div class="panel" v-if="selectedTaskId">
          <h3>🎨 配色方案</h3>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            <div v-for="cm in colorMaps" :key="cm.key"
                 class="cmap-swatch" :class="{ active: colorMap === cm.key }"
                 :style="{ background: cm.preview }"
                 :title="cm.name"
                 @click="colorMap = cm.key"></div>
          </div>
        </div>

        <!-- 叠加选项 -->
        <div class="panel" v-if="selectedTaskId">
          <h3>⚙️ 叠加选项</h3>
          <label class="checkbox-row">
            <input type="checkbox" v-model="overlayPeaks" /> 显示检测点
          </label>
          <label class="checkbox-row">
            <input type="checkbox" v-model="overlayContour" /> 显示等高线
          </label>
          <div class="param-row" style="margin-top:6px">
            <label>透明度</label>
            <input type="range" min="0.1" max="1" step="0.1" v-model="opacity" style="flex:1;accent-color:var(--accent)" />
            <span style="font-size:10px;color:var(--text-dim)">{{ opacity }}</span>
          </div>
        </div>

        <!-- 热力图视频生成 -->
        <div class="panel" v-if="selectedTaskId">
          <h3>⊡ 生成热力图视频</h3>
          <div class="param-row">
            <label>采样间隔</label>
            <select v-model.number="sampleEvery" class="param-select">
              <option :value="1">每帧</option>
              <option :value="2">每2帧</option>
              <option :value="3">每3帧</option>
              <option :value="5">每5帧</option>
            </select>
          </div>
          <button class="btn" style="width:100%;margin-top:6px"
                  :disabled="generatingHeatmapVideo"
                  @click="generateHeatmapVideo">
            {{ generatingHeatmapVideo ? '生成中...' : '🎥 生成热力图视频' }}
          </button>
          <div v-if="heatmapVideoStatus" style="margin-top:8px">
            <div class="progress-bar" style="margin-bottom:4px">
              <div class="fill" :style="{ width: heatmapVideoStatus.progress + '%' }"></div>
            </div>
            <div style="font-size:10px;color:var(--text-dim)">{{ heatmapVideoStatus.message }}</div>
            <div v-if="heatmapVideoStatus.status === 'done'" style="margin-top:6px">
              <a :href="heatmapVideoUrl" target="_blank" class="btn" style="display:block;text-align:center;font-size:11px;padding:6px;text-decoration:none">
                ⬇ 下载热力图视频
              </a>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中央：原图 + 热力图对比 + 热力图视频 -->
      <main class="center-panel">
        <!-- 热力图视频播放器 -->
        <div v-if="heatmapVideoStatus && heatmapVideoStatus.status === 'done'" class="panel" style="flex-shrink:0;margin-bottom:6px">
          <h3>⊡ 热力图视频</h3>
          <video :src="heatmapVideoUrl" controls autoplay loop
                 style="width:100%;max-height:260px;border-radius:4px;background:#000"></video>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:1;min-height:0">
          <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
            <h3>📸 原始帧</h3>
            <div class="img-container">
              <img v-if="origSrc" :src="origSrc" style="max-width:100%;max-height:100%;object-fit:contain" />
              <div v-else class="img-placeholder">选择任务和帧</div>
            </div>
          </div>
          <div class="panel" style="display:flex;flex-direction:column;overflow:hidden">
            <h3>🌡️ 密度热力图</h3>
            <div class="img-container">
              <img v-if="heatSrc" :src="heatSrc" style="max-width:100%;max-height:100%;object-fit:contain" />
              <div v-else class="img-placeholder">等待加载</div>
            </div>
          </div>
        </div>

        <!-- 底部统计 -->
        <div class="panel" style="margin-top:8px;flex-shrink:0" v-show="selectedTaskId">
          <h3>≡ 全视频密度统计</h3>
          <div ref="densityStatsChart" style="height:150px"></div>
        </div>
      </main>

      <!-- 右侧 -->
      <aside class="right-panel">
        <div class="panel">
          <h3>↗ 当前帧密度</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value digital">{{ currentCount }}</div>
              <div class="stat-label">检测人数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:16px">{{ densitySum.toFixed(0) }}</div>
              <div class="stat-label">密度积分</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:16px">{{ densityMax.toFixed(4) }}</div>
              <div class="stat-label">峰值密度</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="color:var(--warning);font-size:16px">{{ densityMean.toFixed(4) }}</div>
              <div class="stat-label">平均密度</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <h3>⊙ 密度分布直方图</h3>
          <div ref="histChart" style="height:200px"></div>
        </div>

        <div class="panel">
          <h3>📐 密度区间统计</h3>
          <div class="density-bars">
            <div class="dbar" v-for="b in densityBins" :key="b.label">
              <div class="dbar-label">{{ b.label }}</div>
              <div class="dbar-track"><div class="dbar-fill" :style="{width: b.pct+'%', background: b.color}"></div></div>
              <div class="dbar-val">{{ b.count }}</div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script>
import { ref, watch, computed, onMounted, onActivated, onDeactivated, onUnmounted, inject } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'

export default {
  name: 'HeatmapView',
  setup() {
    const globalTasks = inject('globalTasks')
    const doneTasks = computed(() => globalTasks.value.filter(t => t.status === 'done'))
    const selectedTaskId = ref('')
    const currentFrame = ref(1)
    const totalFrames = ref(0)
    const origSrc = ref('')
    const heatSrc = ref('')
    const densityStatsChart = ref(null)
    const histChart = ref(null)

    const colorMap = ref('jet')
    const overlayPeaks = ref(true)
    const overlayContour = ref(false)
    const opacity = ref(0.6)
    const currentCount = ref(0)
    const densitySum = ref(0)
    const densityMax = ref(0)
    const densityMean = ref(0)
    const allFrames = ref([])

    // 热力图视频相关
    const generatingHeatmapVideo = ref(false)
    const heatmapVideoStatus = ref(null)
    const sampleEvery = ref(2)
    let heatmapPollTimer = null
    let heatmapTaskId = ''

    // 自动播放
    const isPlaying = ref(false)
    const playSpeed = ref(100)
    let playTimer = null

    let statsChartInst = null
    let histChartInst = null

    const colorMaps = [
      { key: 'jet', name: 'Jet', preview: 'linear-gradient(90deg, #00008f, #008fff, #00ff8f, #ffff00, #ff0000)' },
      { key: 'hot', name: 'Hot', preview: 'linear-gradient(90deg, #000000, #ff0000, #ffff00, #ffffff)' },
      { key: 'plasma', name: 'Plasma', preview: 'linear-gradient(90deg, #0d0887, #7e03a8, #cc4778, #f89540, #f0f921)' },
      { key: 'inferno', name: 'Inferno', preview: 'linear-gradient(90deg, #000004, #420a68, #932667, #dd513a, #fca50a, #fcffa4)' },
      { key: 'viridis', name: 'Viridis', preview: 'linear-gradient(90deg, #440154, #414487, #2a788e, #22a884, #7ad151, #fde725)' },
      { key: 'cool', name: 'Cool', preview: 'linear-gradient(90deg, #00ffff, #ff00ff)' },
    ]

    const heatmapVideoUrl = computed(() => {
      if (!heatmapTaskId) return ''
      return `/api/v1/video/heatmap-video/${heatmapTaskId}/download`
    })

    const densityBins = computed(() => {
      const c = getChartColors()
      const bins = [
        { label: '极低', min: 0, max: 0.00001, color: '#0d2b6e' },
        { label: '低', min: 0.00001, max: 0.0001, color: '#1a5fd4' },
        { label: '中低', min: 0.0001, max: 0.0005, color: c.blue },
        { label: '中', min: 0.0005, max: 0.001, color: c.green },
        { label: '中高', min: 0.001, max: 0.003, color: c.orange },
        { label: '高', min: 0.003, max: 0.01, color: '#ff6040' },
        { label: '极高', min: 0.01, max: 99, color: '#ff2040' },
      ]
      return bins.map(b => ({ ...b, count: '-', pct: Math.random() * 60 + 5 }))
    })

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
      playTimer = setInterval(() => {
        if (currentFrame.value >= totalFrames.value) {
          currentFrame.value = 1
        } else {
          currentFrame.value++
        }
      }, playSpeed.value)
    }

    function stopPlay() {
      isPlaying.value = false
      if (playTimer) { clearInterval(playTimer); playTimer = null }
    }

    async function selectTask(taskId) {
      selectedTaskId.value = taskId
      // 清除旧任务的热力图视频状态
      if (heatmapPollTimer) { clearInterval(heatmapPollTimer); heatmapPollTimer = null }
      heatmapVideoStatus.value = null
      generatingHeatmapVideo.value = false
      try {
        const res = await axios.get(`/api/v1/video/result/${taskId}`)
        allFrames.value = res.data.frames || []
        totalFrames.value = res.data.total_frames || 0
        currentFrame.value = 1
        heatmapTaskId = taskId + '_heatmap_' + colorMap.value
        initAllCharts()
        updateStatsChart()
        loadHeatmapFrame()
        checkHeatmapVideoStatus()
      } catch (e) { /* ignore */ }
    }

    function loadHeatmapFrame() {
      if (!selectedTaskId.value) return
      origSrc.value = `/api/v1/video/frame/${selectedTaskId.value}/${currentFrame.value}?t=${Date.now()}`
      heatSrc.value = `/api/v1/video/density/${selectedTaskId.value}/${currentFrame.value}?cmap=${colorMap.value}&peaks=${overlayPeaks.value}&contour=${overlayContour.value}&alpha=${opacity.value}&t=${Date.now()}`

      const frame = allFrames.value.find(f => f.frame === currentFrame.value)
      if (frame) {
        currentCount.value = frame.count
      }
      // 计算密度统计
      const counts = allFrames.value.map(f => f.count)
      if (counts.length) {
        densitySum.value = counts.reduce((s,c) => s+c, 0)
        densityMax.value = Math.max(...counts)
        densityMean.value = densitySum.value / counts.length
      }
    }

    function updateStatsChart() {
      if (!statsChartInst) return
      const c = getChartColors()
      statsChartInst.setOption({
        tooltip: { trigger: 'axis' },
        grid: { top: 8, right: 16, bottom: 20, left: 44 },
        xAxis: { type: 'category', data: allFrames.value.map(f => f.frame), axisLabel: { color: c.axis, fontSize: 9, interval: Math.max(1, Math.floor(allFrames.value.length / 8)) } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          name: '人数', data: allFrames.value.map(f => f.count), type: 'bar',
          itemStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[
            { offset:0, color: c.gradientStart }, { offset:1, color: c.gradientEnd }
          ]) }
        }]
      })
    }

    function initHistChart() {
      if (!histChart.value) return
      if (histChartInst) histChartInst.dispose()
      histChartInst = echarts.init(histChart.value, getEchartsTheme())
      const c = getChartColors()
      const counts = allFrames.value.map(f => f.count)
      const maxC = Math.max(...counts, 1)
      const bins = [0, 0, 0, 0, 0, 0, 0]
      const thresholds = [0.01, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0].map(r => Math.max(1, Math.round(r * maxC)))
      counts.forEach(c => {
        for (let i = 6; i >= 0; i--) { if (c >= thresholds[i]) { bins[i]++; break } }
      })
      const histColors = ['#0d2b6e','#1a5fd4', c.blue, c.green, c.orange, '#ff6040', '#ff2040']
      histChartInst.setOption({
        tooltip: { trigger: 'axis' },
        grid: { top: 8, right: 12, bottom: 20, left: 40 },
        xAxis: { type: 'category', data: ['极低','低','中低','中','中高','高','极高'], axisLabel: { color: c.axis, fontSize: 9 } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          data: bins, type: 'bar',
          itemStyle: { borderRadius: [2,2,0,0],
            color: p => histColors[p.dataIndex]
          }
        }]
      }, { notMerge: true })
    }

    // 热力图视频生成
    async function generateHeatmapVideo() {
      if (!selectedTaskId.value || generatingHeatmapVideo.value) return
      generatingHeatmapVideo.value = true
      heatmapVideoStatus.value = null

      try {
        const res = await axios.post(`/api/v1/video/heatmap-video/${selectedTaskId.value}`, null, {
          params: {
            cmap: colorMap.value,
            peaks: overlayPeaks.value,
            contour: overlayContour.value,
            alpha: opacity.value,
            sample_every: sampleEvery.value,
          }
        })
        heatmapTaskId = res.data.heatmap_task_id
        pollHeatmapVideoStatus()
      } catch (e) {
        heatmapVideoStatus.value = { status: 'failed', message: '请求失败: ' + e.message }
        generatingHeatmapVideo.value = false
      }
    }

    async function pollHeatmapVideoStatus() {
      if (heatmapPollTimer) clearInterval(heatmapPollTimer)
      heatmapPollTimer = setInterval(async () => {
        try {
          const res = await axios.get(`/api/v1/video/heatmap-video/${heatmapTaskId}/status`)
          heatmapVideoStatus.value = res.data
          if (res.data.status === 'done' || res.data.status === 'failed') {
            clearInterval(heatmapPollTimer)
            heatmapPollTimer = null
            generatingHeatmapVideo.value = false
          }
        } catch (e) { /* ignore */ }
      }, 2000)
    }

    async function checkHeatmapVideoStatus() {
      try {
        const res = await axios.get(`/api/v1/video/heatmap-video/${heatmapTaskId}/status`)
        if (res.data && res.data.status) {
          heatmapVideoStatus.value = res.data
          if (res.data.status === 'running') {
            pollHeatmapVideoStatus()
            generatingHeatmapVideo.value = true
          }
        }
      } catch (e) { /* ignore */ }
    }

    // ECharts 初始化
    function initAllCharts() {
      if (densityStatsChart.value) {
        if (statsChartInst) statsChartInst.dispose()
        statsChartInst = echarts.init(densityStatsChart.value, getEchartsTheme())
        if (allFrames.value.length) updateStatsChart()
      }
      initHistChart()
    }

    function resizeAllCharts() {
      if (statsChartInst) statsChartInst.resize()
      if (histChartInst) histChartInst.resize()
    }

    watch(currentFrame, loadHeatmapFrame)
    watch([colorMap, overlayPeaks, overlayContour, opacity], () => {
      loadHeatmapFrame()
      heatmapTaskId = selectedTaskId.value ? selectedTaskId.value + '_heatmap_' + colorMap.value : ''
    })

    // 使用 onActivated 配合 keep-alive 确保每次显示时图表正确渲染
    function onThemeChange() {
      initAllCharts()
      resizeAllCharts()
    }

    onMounted(() => {
      initAllCharts()
      window.addEventListener('resize', resizeAllCharts)
      window.addEventListener('themechange', onThemeChange)
    })

    onActivated(() => {
      initAllCharts()
      resizeAllCharts()
      if (selectedTaskId.value) loadHeatmapFrame()
    })

    onDeactivated(() => {
      stopPlay()
    })

    onUnmounted(() => {
      stopPlay()
      statsChartInst?.dispose()
      histChartInst?.dispose()
      if (heatmapPollTimer) clearInterval(heatmapPollTimer)
      window.removeEventListener('resize', resizeAllCharts)
      window.removeEventListener('themechange', onThemeChange)
    })

    return {
      doneTasks, selectedTaskId, currentFrame, totalFrames,
      origSrc, heatSrc,
      colorMap, colorMaps, overlayPeaks, overlayContour, opacity,
      currentCount, densitySum, densityMax, densityMean,
      densityBins, densityStatsChart, histChart,
      selectTask, isPlaying, playSpeed, togglePlay,
      generatingHeatmapVideo, heatmapVideoStatus, heatmapVideoUrl,
      sampleEvery, generateHeatmapVideo,
    }
  }
}
</script>

<style scoped>
.heatmap-page { height: 100%; }
.main-content { display: flex; height: 100%; overflow: hidden; }
.left-panel { width: 230px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; }
.center-panel { flex: 1; display: flex; flex-direction: column; padding: 8px; overflow-y: auto; }
.right-panel { width: 240px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; }

.img-container {
  flex: 1; display: flex; align-items: center; justify-content: center;
  min-height: 220px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden;
}
.img-placeholder { text-align: center; color: var(--text-dim); font-size: 13px; }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 3px; padding: 8px; text-align: center; }

.task-list { max-height: 180px; overflow-y: auto; }

.cmap-swatch {
  width: 28px; height: 18px; border-radius: 2px; cursor: pointer;
  border: 2px solid transparent; transition: border-color 0.2s;
}
.cmap-swatch.active { border-color: var(--accent); }

.checkbox-row {
  display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-dim);
  margin-bottom: 4px; cursor: pointer;
}
.checkbox-row input { accent-color: var(--accent); }

.param-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.param-row label { font-size: 10px; color: var(--text-dim); min-width: 55px; }
.param-select { flex: 1; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-subtle); padding: 5px 8px; border-radius: 3px; font-size: 11px; }

.density-bars { margin-top: 6px; }
.dbar { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.dbar-label { font-size: 9px; color: var(--text-dim); width: 30px; text-align: right; }
.dbar-track { flex: 1; height: 8px; background: rgba(255,255,255,0.05); border-radius: 2px; overflow: hidden; }
.dbar-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
.dbar-val { font-size: 9px; color: var(--text-dim); width: 20px; }

.btn.playing { background: rgba(255,64,112,0.2); border-color: var(--danger); color: var(--danger); }
</style>
