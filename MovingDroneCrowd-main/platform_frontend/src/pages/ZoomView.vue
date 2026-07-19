<template>
  <div class="zoom-page">
    <div class="main-content">
      <!-- 左侧任务选择 + 帧控制 -->
      <aside class="left-panel">
        <div class="panel">
          <h3>☰ 已完成任务</h3>
          <div class="task-list">
            <div v-for="task in doneTasks" :key="task.task_id"
                 class="task-item" :class="{ active: selectedTaskId === task.task_id }"
                 @click="selectTask(task.task_id)">
              <span class="status-dot status-done"></span>
              <span style="font-family:monospace;font-size:11px">{{ task.task_id }}</span>
              <span style="color:var(--text-dim);font-size:10px;margin-left:auto">{{ task.result?.total_frames }}帧</span>
            </div>
            <div v-if="doneTasks.length === 0" style="color:var(--text-dim);font-size:12px;text-align:center;padding:20px">
              暂无已完成任务，请先在仪表盘运行分析
            </div>
          </div>
        </div>

        <div class="panel" v-if="selectedTaskId">
          <h3>⊟ 帧控制</h3>
          <div style="text-align:center;margin-bottom:8px">
            <span class="digital" style="font-size:20px;color:var(--accent)">{{ currentFrame }} / {{ totalFrames }}</span>
          </div>
          <input type="range" :min="1" :max="totalFrames" v-model.number="currentFrame"
                 style="width:100%;accent-color:var(--accent);margin-bottom:8px" />
          <div style="display:flex;gap:6px;margin-bottom:8px">
            <button class="btn" title="首帧" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = 1">⏮</button>
            <button class="btn" title="后退10帧" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = Math.max(1, currentFrame - 10)">◀10</button>
            <button class="btn" title="前进10帧" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = Math.min(totalFrames, currentFrame + 10)">10▶</button>
            <button class="btn" title="尾帧" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = totalFrames">⏭</button>
          </div>
          <div style="display:flex;gap:6px">
            <button class="btn" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="playSequence" v-if="!playing">▶ 播放</button>
            <button class="btn" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1;background:rgba(255,64,112,0.2);border-color:var(--danger);color:var(--danger)" @click="stopSequence" v-else>⏸ 停止</button>
            <button class="btn" style="flex:1;height:26px;font-size:11px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="downloadCurrentFrame">↓ 保存</button>
          </div>
        </div>

        <!-- ROI 参数控制 -->
        <div class="panel" v-if="selectedTaskId">
          <h3>⊕ ROI 参数</h3>
          <div style="margin-bottom:8px">
            <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:4px">放大倍数: {{ zoomScale.toFixed(1) }}x</label>
            <input type="range" min="1.5" max="5.0" step="0.1" v-model.number="zoomScale"
                   style="width:100%;accent-color:var(--accent)" />
          </div>
          <div style="margin-bottom:10px">
            <label style="font-size:11px;color:var(--text-dim);display:block;margin-bottom:4px">ROI 比例: {{ (autoRoiRatio * 100).toFixed(0) }}%</label>
            <input type="range" min="0.15" max="0.50" step="0.05" v-model.number="autoRoiRatio"
                   style="width:100%;accent-color:var(--accent)" />
          </div>
          <div style="display:flex;gap:6px;margin-bottom:8px">
            <button class="btn" :class="{ active: roiMode === 'auto' }" style="flex:1;font-size:11px;padding:6px" @click="setRoiMode('auto')">🤖 自动</button>
            <button class="btn" :class="{ active: roiMode === 'manual' || roiMode === 'viewing' }" style="flex:1;font-size:11px;padding:6px" @click="setRoiMode('manual')">✏️ 手绘</button>
          </div>
          <div v-if="roiMode === 'manual'" style="margin-top:8px;font-size:10px;color:var(--accent);line-height:1.5">
            ✏️ 在图片上按住鼠标拖拽画矩形 ROI
          </div>
          <div v-else-if="roiMode === 'viewing'" style="margin-top:8px;font-size:10px;color:var(--warning);line-height:1.5">
            👁️ 正在查看自定义 ROI 结果，点击"手绘"重新绘制
          </div>
          <div v-else style="margin-top:8px;font-size:10px;color:var(--text-dim);line-height:1.5">
            🤖 红色虚线框表示自动计算的 ROI 区域（以检测点中心为基准）
          </div>
          <div v-if="customRoi" style="margin-top:8px;font-size:10px;color:var(--warning)">
            📐 自定义 ROI: ({{ customRoi.x1 }}, {{ customRoi.y1 }}) → ({{ customRoi.x2 }}, {{ customRoi.y2 }})
            <button class="btn" style="font-size:10px;padding:2px 6px;margin-left:4px" @click="clearCustomRoi">清除</button>
          </div>
        </div>
      </aside>

      <!-- 中央：放大对比图 -->
      <main class="center-panel">
        <div class="panel" style="flex:1;display:flex;flex-direction:column;overflow:hidden">
          <h3>🔎 原图 + ROI 放大对比</h3>
          <div class="frame-container" ref="frameContainer">
            <div v-if="!zoomSrc && !frameSrc" class="frame-placeholder">
              <div style="font-size:40px">⊕</div>
              <div style="margin-top:12px;color:var(--text-dim)">选择已完成任务<br/>查看 ROI 放大对比效果</div>
            </div>
            <template v-if="zoomSrc || frameSrc">
              <!-- 显示放大对比图（zoomSrc），如果没有则用原图（frameSrc） -->
              <img ref="frameImg" :src="zoomSrc || frameSrc"
                   style="max-width:100%;max-height:100%;border-radius:4px;object-fit:contain"
                   @load="onImageLoad" draggable="false" />
              <!-- Canvas 覆盖层（仅在画 ROI 时显示，查看结果时隐藏） -->
              <canvas v-if="roiMode === 'manual' && !customRoi" ref="roiCanvas" class="roi-canvas"
                      @mousedown="onMouseDown" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseUp"
                      draggable="false" />
            </template>
          </div>
        </div>
      </main>

      <!-- 右侧统计 -->
      <aside class="right-panel">
        <div class="panel">
          <h3>≡ 当前帧统计</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value digital">{{ frameData.count || 0 }}</div>
              <div class="stat-label">检测人数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital">{{ frameData.frame || 0 }}</div>
              <div class="stat-label">帧号</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="font-size:18px">{{ avgCount }}</div>
              <div class="stat-label">平均人数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="color:var(--warning);font-size:18px">{{ maxCount }}</div>
              <div class="stat-label">最大人数</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <h3>↗ 全帧趋势</h3>
          <div ref="trendChart" style="height:200px"></div>
        </div>

        <div class="panel" v-if="frameData.peaks && frameData.peaks.length > 0">
          <h3>📍 检测点坐标 ({{ frameData.peaks.length }}个)</h3>
          <div class="peaks-table">
            <table>
              <thead><tr><th>#</th><th>X</th><th>Y</th></tr></thead>
              <tbody>
                <tr v-for="(p, i) in frameData.peaks.slice(0, 20)" :key="i">
                  <td>{{ i + 1 }}</td>
                  <td>{{ Math.round(p[0]) }}</td>
                  <td>{{ Math.round(p[1]) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="frameData.peaks.length > 20" style="font-size:10px;color:var(--text-dim);text-align:center;padding:4px">
              ... 仅显示前20个，共{{ frameData.peaks.length }}个
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onActivated, onDeactivated, onUnmounted, inject, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'

export default {
  name: 'ZoomView',
  setup() {
    const globalTasks = inject('globalTasks')
    const doneTasks = computed(() => globalTasks.value.filter(t => t.status === 'done'))
    const selectedTaskId = ref('')
    const currentFrame = ref(1)
    const totalFrames = ref(0)
    const frameSrc = ref('')
    const zoomSrc = ref('')
    const frameData = ref({})
    const allFrames = ref([])
    const playing = ref(false)
    const trendChart = ref(null)
    const zoomScale = ref(2.5)
    const autoRoiRatio = ref(0.25)
    const roiMode = ref('auto')  // 'auto' | 'manual'
    const customRoi = ref(null)  // { x1, y1, x2, y2 } 图像坐标
    const frameContainer = ref(null)
    const frameImg = ref(null)
    const roiCanvas = ref(null)
    let trendChartInst = null
    let playTimer = null
    const paramVersion = ref(0)

    // 拖拽画矩形状态
    let isDrawing = false
    let drawStart = { x: 0, y: 0 }
    let drawCurrent = { x: 0, y: 0 }
    let imgNaturalSize = { w: 0, h: 0 }
    let imgDisplaySize = { w: 0, h: 0 }
    let imgDisplayOffset = { x: 0, y: 0 }

    const avgCount = computed(() => {
      if (!allFrames.value.length) return 0
      return Math.round(allFrames.value.reduce((s, f) => s + f.count, 0) / allFrames.value.length)
    })
    const maxCount = computed(() => {
      if (!allFrames.value.length) return 0
      return Math.max(...allFrames.value.map(f => f.count))
    })

    async function selectTask(taskId) {
      selectedTaskId.value = taskId
      customRoi.value = null
      roiMode.value = 'auto'
      try {
        const res = await axios.get(`/api/v1/video/result/${taskId}`)
        allFrames.value = res.data.frames || []
        totalFrames.value = res.data.total_frames || 0
        currentFrame.value = 1
        initTrendChart()
        updateTrendChart()
        loadFrameData()
      } catch (e) { /* ignore */ }
    }

    function loadFrameData() {
      if (!allFrames.value.length || currentFrame.value < 1) return
      const idx = Math.min(currentFrame.value - 1, allFrames.value.length - 1)
      frameData.value = allFrames.value[idx]
      // 始终加载原图（用于手绘时显示），加时间戳强制刷新
      frameSrc.value = `/api/v1/video/frame/${selectedTaskId.value}/${currentFrame.value}?v=${Date.now()}`
      // 根据模式决定 zoomSrc
      if (customRoi.value && (roiMode.value === 'manual' || roiMode.value === 'viewing')) {
        // 有自定义 ROI：加载自定义放大图（传入 zoomScale）
        loadCustomZoom()
      } else if (roiMode.value === 'auto') {
        zoomSrc.value = `/api/v1/video/zoom/${selectedTaskId.value}/${currentFrame.value}?zoom_scale=${zoomScale.value}&roi_ratio=${autoRoiRatio.value}&t=${Date.now()}`
      } else {
        // manual 模式无 ROI：显示原图，清空 zoomSrc
        zoomSrc.value = ''
        // 手动模式下需要初始化 Canvas（图片可能已缓存，onImageLoad 不触发）
        nextTick(() => { initCanvas() })
      }
    }

    async function loadCustomZoom() {
      if (!customRoi.value) return
      try {
        const res = await axios.post(
          `/api/v1/video/zoom-custom/${selectedTaskId.value}/${currentFrame.value}`,
          null,
          {
            params: {
              x1: customRoi.value.x1,
              y1: customRoi.value.y1,
              x2: customRoi.value.x2,
              y2: customRoi.value.y2,
              zoom_scale: zoomScale.value
            },
            responseType: 'blob'
          }
        )
        zoomSrc.value = URL.createObjectURL(res.data)
      } catch (e) {
        console.error('自定义 ROI 加载失败:', e)
      }
    }

    function setRoiMode(mode) {
      roiMode.value = mode
      if (mode === 'auto') {
        customRoi.value = null
        clearCanvas()
      } else if (mode === 'manual') {
        // 切换到手动模式：清除之前的 ROI，显示原图+Canvas 以便重新手绘
        customRoi.value = null
        zoomSrc.value = ''
        clearCanvas()
        // 强制初始化 Canvas（图片可能已缓存，onImageLoad 不会触发）
        nextTick(() => {
          updateImageDisplayInfo()
          initCanvas()
        })
      }
      // viewing 模式：由 onMouseUp 触发，不需要额外处理
      loadFrameData()
    }

    function clearCustomRoi() {
      customRoi.value = null
      clearCanvas()
      loadFrameData()
    }

    // ========== Canvas ROI 绘制 ==========
    function onImageLoad() {
      if (!frameImg.value) return
      imgNaturalSize = {
        w: frameImg.value.naturalWidth,
        h: frameImg.value.naturalHeight
      }
      updateImageDisplayInfo()
      if (roiMode.value === 'manual') {
        initCanvas()
      }
    }

    function updateImageDisplayInfo() {
      if (!frameImg.value || !frameContainer.value) return
      const rect = frameImg.value.getBoundingClientRect()
      const containerRect = frameContainer.value.getBoundingClientRect()
      imgDisplaySize = { w: rect.width, h: rect.height }
      imgDisplayOffset = {
        x: rect.left - containerRect.left,
        y: rect.top - containerRect.top
      }
    }

    function initCanvas() {
      if (!roiCanvas.value || !frameContainer.value) return
      const canvas = roiCanvas.value
      const container = frameContainer.value
      canvas.width = container.clientWidth
      canvas.height = container.clientHeight
      clearCanvas()
    }

    function clearCanvas() {
      if (!roiCanvas.value) return
      const ctx = roiCanvas.value.getContext('2d')
      ctx.clearRect(0, 0, roiCanvas.value.width, roiCanvas.value.height)
    }

    function drawRoiRect() {
      if (!roiCanvas.value) return
      const ctx = roiCanvas.value.getContext('2d')
      clearCanvas()

      const x = Math.min(drawStart.x, drawCurrent.x)
      const y = Math.min(drawStart.y, drawCurrent.y)
      const w = Math.abs(drawCurrent.x - drawStart.x)
      const h = Math.abs(drawCurrent.y - drawStart.y)

      if (w < 5 || h < 5) return

      // 红色虚线框
      ctx.strokeStyle = '#ff3333'
      ctx.lineWidth = 2
      ctx.setLineDash([8, 6])
      ctx.strokeRect(x, y, w, h)
      ctx.setLineDash([])

      // 半透明填充
      ctx.fillStyle = 'rgba(255, 51, 51, 0.08)'
      ctx.fillRect(x, y, w, h)

      // 角标
      ctx.fillStyle = '#ff3333'
      ctx.font = '11px monospace'
      ctx.fillText(`(${Math.round(x)}, ${Math.round(y)})`, x, y - 4)
    }

    function onMouseDown(e) {
      if (roiMode.value !== 'manual') return
      updateImageDisplayInfo()
      isDrawing = true
      drawStart = { x: e.offsetX, y: e.offsetY }
      drawCurrent = { x: e.offsetX, y: e.offsetY }
    }

    function onMouseMove(e) {
      if (!isDrawing || roiMode.value !== 'manual') return
      drawCurrent = { x: e.offsetX, y: e.offsetY }
      drawRoiRect()
    }

    function onMouseUp(e) {
      if (!isDrawing || roiMode.value !== 'manual') return
      isDrawing = false
      drawCurrent = { x: e.offsetX, y: e.offsetY }
      drawRoiRect()

      // 计算图像坐标（当前显示的是原图 frameSrc）
      const x1 = Math.min(drawStart.x, drawCurrent.x)
      const y1 = Math.min(drawStart.y, drawCurrent.y)
      const x2 = Math.max(drawStart.x, drawCurrent.x)
      const y2 = Math.max(drawStart.y, drawCurrent.y)

      // 转换为原始图像坐标
      const scaleX = imgNaturalSize.w / imgDisplaySize.w
      const scaleY = imgNaturalSize.h / imgDisplaySize.h

      const imgX1 = Math.round((x1 - imgDisplayOffset.x) * scaleX)
      const imgY1 = Math.round((y1 - imgDisplayOffset.y) * scaleY)
      const imgX2 = Math.round((x2 - imgDisplayOffset.x) * scaleX)
      const imgY2 = Math.round((y2 - imgDisplayOffset.y) * scaleY)

      // 确保在图像范围内
      const clampedX1 = Math.max(0, Math.min(imgX1, imgNaturalSize.w))
      const clampedY1 = Math.max(0, Math.min(imgY1, imgNaturalSize.h))
      const clampedX2 = Math.max(clampedX1 + 1, Math.min(imgX2, imgNaturalSize.w))
      const clampedY2 = Math.max(clampedY1 + 1, Math.min(imgY2, imgNaturalSize.h))

      if (clampedX2 - clampedX1 >= 10 && clampedY2 - clampedY1 >= 10) {
        customRoi.value = {
          x1: clampedX1,
          y1: clampedY1,
          x2: clampedX2,
          y2: clampedY2
        }
        // 加载完成后切换为"查看结果"状态，隐藏 Canvas
        loadCustomZoom().then(() => {
          // 切换到查看结果模式：保留 customRoi 但切回 auto-like 显示
          roiMode.value = 'viewing'
        })
      }
    }

    function playSequence() {
      if (playing.value) return
      playing.value = true
      playTimer = setInterval(() => {
        if (currentFrame.value >= totalFrames.value) { stopSequence(); return }
        currentFrame.value++
      }, 200)
    }
    function stopSequence() {
      playing.value = false
      if (playTimer) { clearInterval(playTimer); playTimer = null }
    }
    function downloadCurrentFrame() {
      const src = zoomSrc.value || frameSrc.value
      if (!src) return
      const a = document.createElement('a')
      a.href = src; a.download = `zoom_frame_${currentFrame.value}.jpg`; a.click()
    }

    function updateTrendChart() {
      if (!trendChartInst) return
      const c = getChartColors()
      trendChartInst.setOption({
        tooltip: { trigger: 'axis' },
        grid: { top: 8, right: 16, bottom: 20, left: 44 },
        xAxis: { type: 'category', data: allFrames.value.map(f => f.frame), axisLabel: { color: c.axis, fontSize: 9, interval: Math.max(1, Math.floor(allFrames.value.length / 6)) } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 9 } },
        series: [{
          data: allFrames.value.map(f => f.count), type: 'line', smooth: true,
          lineStyle: { color: c.blue, width: 1.5 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[
            { offset:0, color: c.gradientStart }, { offset:1, color: c.gradientEnd }
          ]) },
          symbol: 'none',
          markLine: { silent: true, data: [{ xAxis: currentFrame.value, lineStyle: { color: c.orange, type: 'dashed', width: 1 } }] }
        }]
      })
    }

    function initTrendChart() {
      if (!trendChart.value) return
      if (trendChartInst) trendChartInst.dispose()
      trendChartInst = echarts.init(trendChart.value, getEchartsTheme())
      if (allFrames.value.length) updateTrendChart()
    }

    function resizeCharts() {
      if (trendChartInst) trendChartInst.resize()
      updateImageDisplayInfo()
      if (roiMode.value === 'manual') initCanvas()
    }

    watch(currentFrame, () => { loadFrameData(); updateTrendChart() })
    watch(zoomScale, () => { paramVersion.value++; loadFrameData() })
    watch(autoRoiRatio, () => { paramVersion.value++; loadFrameData() })

    function onThemeChange() {
      initTrendChart()
      resizeCharts()
      if (allFrames.value.length) updateTrendChart()
    }

    onMounted(() => {
      setTimeout(() => {
        initTrendChart()
        if (doneTasks.value.length > 0 && !selectedTaskId.value) {
          selectTask(doneTasks.value[0].task_id)
        }
      }, 100)
      window.addEventListener('resize', resizeCharts)
      window.addEventListener('themechange', onThemeChange)
    })

    onActivated(() => {
      setTimeout(() => {
        initTrendChart()
        resizeCharts()
        if (selectedTaskId.value) loadFrameData()
      }, 150)
    })

    onDeactivated(() => {
      stopSequence()
    })

    onUnmounted(() => {
      stopSequence()
      trendChartInst?.dispose()
      window.removeEventListener('resize', resizeCharts)
      window.removeEventListener('themechange', onThemeChange)
    })

    return {
      doneTasks, selectedTaskId, currentFrame, totalFrames, frameSrc, zoomSrc, frameData, playing,
      zoomScale, autoRoiRatio, roiMode, customRoi, trendChart, frameContainer, frameImg, roiCanvas,
      avgCount, maxCount,
      selectTask, playSequence, stopSequence, downloadCurrentFrame, setRoiMode, clearCustomRoi,
      onImageLoad, onMouseDown, onMouseMove, onMouseUp
    }
  }
}
</script>

<style scoped>
.zoom-page { height: 100%; }
.main-content { display: flex; height: 100%; overflow: hidden; }
.left-panel { width: 230px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; }
.center-panel { flex: 1; display: flex; flex-direction: column; padding: 8px; overflow-y: auto; }
.right-panel { width: 240px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; padding: 8px; overflow-y: auto; }

.frame-container {
  flex: 1; display: flex; align-items: center; justify-content: center;
  min-height: 200px; background: rgba(0,0,0,0.3); border-radius: 4px; overflow: hidden;
  position: relative;
}
.frame-placeholder { text-align: center; color: var(--text-dim); }

/* ROI Canvas 覆盖在图片上 */
.roi-canvas {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  cursor: crosshair;
  pointer-events: auto;
}

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 3px; padding: 8px; text-align: center; }

.task-list { max-height: 200px; overflow-y: auto; }

.peaks-table { max-height: 240px; overflow-y: auto; }
.peaks-table table { width: 100%; border-collapse: collapse; font-size: 10px; }
.peaks-table th, .peaks-table td { padding: 3px 6px; text-align: center; color: var(--text-dim); border-bottom: 1px solid rgba(20,60,160,0.1); }
.peaks-table th { color: var(--accent); font-weight: 400; }

/* 按钮激活状态 */
.btn.active {
  background: var(--accent-glow);
  border-color: var(--accent);
  color: var(--accent);
}
</style>
