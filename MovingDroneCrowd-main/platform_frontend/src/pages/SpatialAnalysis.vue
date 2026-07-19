<template>
  <div class="spatial-page">
    <!-- 左侧面板 -->
    <div class="left-panel">
      <h3 style="margin:0 0 8px;font-size:14px">🗺️ 空间分布分析</h3>
      <div style="margin-bottom:8px">
        <select v-model="selectedTaskId" class="task-select" @change="selectTask(selectedTaskId)">
          <option value="">-- 选择任务 --</option>
          <option v-for="task in doneTasks" :key="task.task_id" :value="task.task_id">{{ task.task_id }}</option>
        </select>
      </div>

      <div class="param-group">
        <label>当前帧: {{ currentFrame }} / {{ totalFrames }}</label>
        <input type="range" :min="1" :max="totalFrames" v-model.number="currentFrame"
               style="width:100%;accent-color:var(--accent)" />
        <div style="display:flex;gap:4px;margin-top:4px">
          <button class="btn" style="flex:1;height:24px;font-size:12px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = Math.max(1, currentFrame - 1)">◀</button>
          <button class="btn" style="flex:1;height:24px;font-size:12px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="currentFrame = Math.min(totalFrames, currentFrame + 1)">▶</button>
          <button class="btn" style="flex:1;height:24px;font-size:12px;padding:0;display:flex;align-items:center;justify-content:center;line-height:1" @click="togglePlay" :class="{ playing: isPlaying }">
            {{ isPlaying ? '⏹' : '▷' }}
          </button>
        </div>
      </div>

      <div class="param-group">
        <label>拖尾长度</label>
        <select v-model="trailLength" class="param-select">
          <option :value="5">5帧</option><option :value="10">10帧</option>
          <option :value="20">20帧</option><option :value="30">30帧</option>
        </select>
      </div>

      <div class="param-group">
        <label>网格分辨率</label>
        <select v-model="gridSize" class="param-select">
          <option value="8">8×8</option><option value="12">12×12</option>
          <option value="16">16×16</option><option value="20">20×20</option>
        </select>
      </div>

      <!-- 指标卡片 -->
      <div class="stat-cards" v-show="selectedTaskId">
        <div class="stat-card">
          <span class="sc-value">{{ currentFrameData?.count || 0 }}</span>
          <span class="sc-label">当前帧人数</span>
        </div>
        <div class="stat-card">
          <span class="sc-value">{{ motionStats.totalTracks }}</span>
          <span class="sc-label">轨迹数</span>
        </div>
        <div class="stat-card">
          <span class="sc-value" style="color:var(--warning)">{{ motionStats.avgDisplacement.toFixed(1) }}px</span>
          <span class="sc-label">平均位移</span>
        </div>
        <div class="stat-card">
          <span class="sc-value">{{ motionStats.dominantDir }}</span>
          <span class="sc-label">主方向</span>
        </div>
      </div>
    </div>

    <!-- 右侧图表区 -->
    <div class="right-panel" v-show="selectedTaskId">
      <!-- 上半区：空间热力叠加 + 轨迹流线 -->
      <div class="chart-row chart-row-top">
        <div class="panel chart-cell">
          <h3 class="chart-h3">🗺️ 空间热力分布 + 轨迹拖尾（叠加原图）</h3>
          <div class="canvas-wrap" ref="overlayWrap">
            <img v-if="frameSrc" :src="frameSrc" class="overlay-img" ref="overlayImg"
                 @load="onOverlayImgLoad" @error="onOverlayImgError" />
            <canvas ref="overlayCanvas" class="overlay-canvas"></canvas>
            <div v-if="!frameSrc || overlayError" class="overlay-placeholder">
              {{ overlayError || '加载原图...' }}
            </div>
          </div>
        </div>
        <div class="panel chart-cell">
          <h3 class="chart-h3">⛰️ 3D 密度地形图</h3>
          <div ref="terrainContainer" class="chart-inner" style="position:relative; overflow:hidden;">
            <div class="t3-legend">
              <div class="t3-legend-bar"></div>
              <div class="t3-legend-labels"><span>高</span><span>低</span></div>
            </div>
            <div class="t3-info">
              <div class="t3-info-kv"><span class="t3-info-val" id="t3GridSize">—</span><span class="t3-info-key">网格</span></div>
              <div class="t3-info-kv"><span class="t3-info-val" id="t3PeakVal">—</span><span class="t3-info-key">峰值</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下半区：人数时序 + 流线方向 -->
      <div class="chart-row chart-row-bottom">
        <div class="panel chart-cell">
          <h3 class="chart-h3">↗ 人数时序变化 + 周期分析</h3>
          <div ref="timeChart" class="chart-inner"></div>
        </div>
        <div class="panel chart-cell">
          <h3 class="chart-h3">🧭 人群移动方向分布</h3>
          <div ref="roseChart" class="chart-inner"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onActivated, onUnmounted, nextTick, inject } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'
import * as THREE from 'three'

export default {
  name: 'SpatialAnalysis',
  setup() {
    const c = getChartColors()
    const globalTasks = inject('globalTasks')
    const doneTasks = computed(() => globalTasks.value.filter(t => t.status === 'done'))
    const selectedTaskId = ref('')
    const currentFrame = ref(1)
    const totalFrames = ref(0)
    const trailLength = ref(10)
    const gridSize = ref(12)
    const allFrames = ref([])
    const videoWidth = ref(1920)
    const videoHeight = ref(1080)
    const frameSrc = ref('')
    const overlayError = ref('')

    const overlayWrap = ref(null)
    const overlayImg = ref(null)
    const overlayCanvas = ref(null)
    const terrainContainer = ref(null)
    const timeChart = ref(null)
    const roseChart = ref(null)
    let timeChartInst = null, roseChartInst = null
    // Three.js terrain state
    let terrainScene = null, terrainCamera = null, terrainRenderer = null
    let terrainGroup = null, terrainFrameId = null
    let terrainDragging = false, terrainLastX = 0, terrainLastY = 0
    let terrainMesh = null      // 缓存地形网格，只更新顶点不重建
    let terrainWire = null      // 缓存网格线

    const isPlaying = ref(false)
    let playTimer = null

    const currentFrameData = computed(() => {
      return allFrames.value.find(f => f.frame === currentFrame.value) || null
    })

    // 拖尾帧：当前帧往前 trailLength 帧
    const trailFrames = computed(() => {
      const start = Math.max(0, currentFrame.value - trailLength.value)
      return allFrames.value.filter(f => f.frame >= start && f.frame <= currentFrame.value)
    })

    // 轨迹匹配与运动统计
    const motionStats = computed(() => {
      const trail = trailFrames.value
      let totalTracks = 0
      let totalDisp = 0
      let dispCount = 0
      const dirBins = Array(8).fill(0)
      const dirNames = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

      // 相邻帧最近邻匹配计算位移
      for (let i = 1; i < trail.length; i++) {
        const prev = trail[i - 1]
        const curr = trail[i]
        if (!prev.peaks || !curr.peaks || !prev.peaks.length || !curr.peaks.length) continue
        totalTracks = Math.max(totalTracks, prev.peaks.length)
        const used = new Set()
        for (let pi = 0; pi < Math.min(prev.peaks.length, curr.peaks.length); pi++) {
          let bestJ = -1, bestDist = Infinity
          for (let ci = 0; ci < curr.peaks.length; ci++) {
            if (used.has(ci)) continue
            const dx = curr.peaks[ci][0] - prev.peaks[pi][0]
            const dy = curr.peaks[ci][1] - prev.peaks[pi][1]
            const d = Math.sqrt(dx * dx + dy * dy)
            if (d < 120 && d < bestDist) { bestDist = d; bestJ = ci }
          }
          if (bestJ >= 0) {
            used.add(bestJ)
            const dx = curr.peaks[bestJ][0] - prev.peaks[pi][0]
            const dy = curr.peaks[bestJ][1] - prev.peaks[pi][1]
            totalDisp += Math.sqrt(dx * dx + dy * dy)
            dispCount++
            const angle = Math.atan2(dy, dx) * 180 / Math.PI
            dirBins[Math.floor(((angle + 180 + 22.5) % 360) / 45) % 8]++
          }
        }
      }
      const dominantDir = dirBins.indexOf(Math.max(...dirBins))
      return {
        totalTracks,
        avgDisplacement: dispCount > 0 ? totalDisp / dispCount : 0,
        dominantDir: dirNames[dominantDir],
        dirBins,
        dirNames,
      }
    })

    // ==================== Canvas 叠加层绘制 ====================

    function onOverlayImgLoad() {
      overlayError.value = ''
      drawOverlay()
    }

    function onOverlayImgError() {
      overlayError.value = '图片加载失败'
    }

    function drawOverlay() {
      const img = overlayImg.value
      const canvas = overlayCanvas.value
      const wrap = overlayWrap.value
      if (!img || !canvas || !wrap) return

      const frame = currentFrameData.value
      if (!frame) return

      const w = img.naturalWidth || img.clientWidth
      const h = img.naturalHeight || img.clientHeight
      const wrapW = wrap.clientWidth
      const wrapH = wrap.clientHeight

      // 等比缩放
      const scale = Math.min(wrapW / w, wrapH / h)
      const cw = w * scale
      const ch = h * scale

      canvas.width = cw
      canvas.height = ch
      canvas.style.width = cw + 'px'
      canvas.style.height = ch + 'px'

      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, cw, ch)

      const scaleX = cw / videoWidth.value
      const scaleY = ch / videoHeight.value

      // 绘制热力：累积窗口内所有帧的 peaks
      const heatBins = new Map()
      const trail = trailFrames.value
      trail.forEach((f, fi) => {
        if (!f.peaks) return
        const alpha = 0.2 + 0.6 * (fi / trail.length) // 越新的帧越亮
        f.peaks.forEach(([px, py]) => {
          const key = `${Math.floor(px / videoWidth.value * gridSize.value)},${Math.floor(py / videoHeight.value * gridSize.value)}`
          heatBins.set(key, (heatBins.get(key) || 0) + 1)
        })
      })

      const maxHeat = Math.max(1, ...heatBins.values())

      // 先绘制热力网格背景
      const gs = gridSize.value
      const cellW = cw / gs
      const cellH = ch / gs
      const heatColors = [
        [0, 8, 50, 0.3],
        [13, 43, 110, 0.4],
        [26, 95, 212, 0.5],
        [77, 166, 255, 0.55],
        [64, 216, 112, 0.6],
        [255, 160, 64, 0.65],
        [255, 32, 64, 0.7],
      ]

      for (let r = 0; r < gs; r++) {
        for (let c = 0; c < gs; c++) {
          const key = `${c},${r}`
          const v = heatBins.get(key) || 0
          if (v === 0) continue
          const ratio = v / maxHeat
          const idx = Math.min(heatColors.length - 1, Math.floor(ratio * heatColors.length))
          const [cr, cg, cb, ca] = heatColors[idx]
          ctx.fillStyle = `rgba(${cr},${cg},${cb},${ca})`
          ctx.fillRect(c * cellW, r * cellH, cellW, cellH)
        }
      }

      // 绘制当前帧的检测点
      if (frame.peaks && frame.peaks.length > 0) {
        frame.peaks.forEach(([px, py]) => {
          const cx = px * scaleX
          const cy = py * scaleY
          ctx.beginPath()
          ctx.arc(cx, cy, 7, 0, Math.PI * 2)
          ctx.fillStyle = 'rgba(255,255,255,0.25)'
          ctx.fill()
          ctx.beginPath()
          ctx.arc(cx, cy, 3, 0, Math.PI * 2)
          ctx.fillStyle = '#00ff88'
          ctx.fill()
          ctx.strokeStyle = '#003322'
          ctx.lineWidth = 1
          ctx.stroke()
        })
      }

      // 绘制轨迹线（拖尾效果）
      if (trail.length >= 2) {
        const tracks = []
        const lastFrame = trail[trail.length - 1]
        if (lastFrame.peaks) {
          lastFrame.peaks.forEach(([px, py]) => {
            tracks.push({ points: [[px, py]], alive: true })
          })
        }

        for (let fi = trail.length - 2; fi >= 0; fi--) {
          const currF = trail[fi]
          if (!currF.peaks || !currF.peaks.length) continue

          tracks.forEach(track => {
            if (!track.alive) return
            const lastPt = track.points[0]
            let bestJ = -1, bestDist = Infinity
            for (let ci = 0; ci < currF.peaks.length; ci++) {
              const dx = currF.peaks[ci][0] - lastPt[0]
              const dy = currF.peaks[ci][1] - lastPt[1]
              const d = Math.sqrt(dx * dx + dy * dy)
              if (d < 120 && d < bestDist) { bestDist = d; bestJ = ci }
            }
            if (bestJ >= 0) {
              track.points.unshift(currF.peaks[bestJ])
            } else {
              track.alive = false
            }
          })
        }

        tracks.forEach(track => {
          if (track.points.length < 2) return
          for (let i = 1; i < track.points.length; i++) {
            const x1 = track.points[i - 1][0] * scaleX
            const y1 = track.points[i - 1][1] * scaleY
            const x2 = track.points[i][0] * scaleX
            const y2 = track.points[i][1] * scaleY
            const alpha = 0.3 + 0.7 * (i / track.points.length)
            ctx.beginPath()
            ctx.moveTo(x1, y1)
            ctx.lineTo(x2, y2)
            ctx.strokeStyle = `rgba(0,255,136,${alpha})`
            ctx.lineWidth = 1.5
            ctx.stroke()
          }
        })
      }

      ctx.fillStyle = 'rgba(0,0,0,0.6)'
      ctx.fillRect(cw - 170, ch - 52, 162, 44)
      ctx.font = '10px monospace'
      ctx.fillStyle = c.axis
      ctx.fillText(`帧 ${currentFrame.value} | 人数 ${frame.count} | 网格 ${gridSize.value}×${gridSize.value}`, cw - 162, ch - 32)
      ctx.fillText(`拖尾 ${trail.length} 帧 | 轨迹 ${motionStats.value.totalTracks} 条`, cw - 162, ch - 16)
    }

    // ==================== ECharts 图表 ====================

    function initAllCharts() {
      const t = getEchartsTheme()

      // ── Three.js 3D 地形初始化 ──
      if (terrainContainer.value && !terrainScene) {
        const el = terrainContainer.value
        const w = el.clientWidth || 600
        const h = el.clientHeight || 420

        const c = getChartColors()
        terrainScene = new THREE.Scene()
        const bgColor = c.bg === '#f4f6f8' ? 0xe8ecf0 : 0x060d18
        terrainScene.background = new THREE.Color(bgColor)
        terrainScene.fog = new THREE.Fog(bgColor, 70, 240)

        terrainCamera = new THREE.PerspectiveCamera(42, w / Math.max(h, 1), 0.1, 600)
        terrainCamera.position.set(0, 36, 88)
        terrainCamera.lookAt(0, 2.5, 0)

        terrainRenderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
        terrainRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
        terrainRenderer.setSize(w, h)
        el.appendChild(terrainRenderer.domElement)

        terrainGroup = new THREE.Group()
        terrainGroup.rotation.x = -0.25
        terrainScene.add(terrainGroup)

        // 一次性创建几何体结构（后续只更新顶点位置）
        ensureTerrainGeometry()

        terrainScene.add(new THREE.AmbientLight(0x334466, 0.58))
        const key = new THREE.DirectionalLight(0xffffff, 1.10)
        key.position.set(52, 65, 42)
        terrainScene.add(key)
        const fill = new THREE.DirectionalLight(0x335588, 0.25)
        fill.position.set(-28, 18, -24)
        terrainScene.add(fill)
        const rim = new THREE.DirectionalLight(0x335588, 0.32)
        rim.position.set(0, 6, -38)
        terrainScene.add(rim)

        terrainRenderer.domElement.style.position = 'absolute'
        terrainRenderer.domElement.style.top = '0'
        terrainRenderer.domElement.style.left = '0'
        terrainRenderer.domElement.addEventListener('mousedown', (e) => {
          terrainDragging = true; terrainLastX = e.clientX; terrainLastY = e.clientY
        })
        window.addEventListener('mouseup', () => { terrainDragging = false })
        terrainRenderer.domElement.addEventListener('mousemove', (e) => {
          if (!terrainDragging) return
          terrainGroup.rotation.y += (e.clientX - terrainLastX) * 0.006
          terrainGroup.rotation.x += (e.clientY - terrainLastY) * 0.004
          terrainGroup.rotation.x = Math.max(-0.55, Math.min(0.08, terrainGroup.rotation.x))
          terrainLastX = e.clientX; terrainLastY = e.clientY
        })
        terrainRenderer.domElement.addEventListener('wheel', (e) => {
          e.preventDefault()
          terrainCamera.position.z += e.deltaY * 0.06
          terrainCamera.position.z = Math.max(55, Math.min(180, terrainCamera.position.z))
        })

        function terrainAnimate() {
          if (!terrainGroup) return
          if (!terrainDragging) terrainGroup.rotation.y += 0.0012
          terrainRenderer.render(terrainScene, terrainCamera)
          terrainFrameId = requestAnimationFrame(terrainAnimate)
        }
        terrainAnimate()
      }

      // ── ECharts 2D 图表 ──
      ;[timeChart, roseChart].forEach(refEl => {
        const el = refEl.value
        if (!el) return
        if (el.offsetWidth === 0) el.style.width = '100%'
        if (el.offsetHeight === 0) el.style.height = '400px'
      })
      if (timeChart.value) {
        if (timeChartInst && !timeChartInst.isDisposed()) timeChartInst.dispose()
        timeChartInst = echarts.init(timeChart.value, t)
        requestAnimationFrame(() => timeChartInst?.resize())
      }
      if (roseChart.value) {
        if (roseChartInst && !roseChartInst.isDisposed()) roseChartInst.dispose()
        roseChartInst = echarts.init(roseChart.value, t)
        requestAnimationFrame(() => roseChartInst?.resize())
      }
    }

    const densityGrid = ref(null)
    async function loadDensityGrid() {
      if (!selectedTaskId.value || !selectedTaskId.value.startsWith('stv_')) return
      try {
        const res = await axios.get(`/api/v1/video/density-grid/${selectedTaskId.value}/${currentFrame.value}`)
        densityGrid.value = res.data
      } catch (e) { densityGrid.value = null }
    }

    function upsample2D(src, srcRows, srcCols, dstRows, dstCols) {
      const dst = Array.from({ length: dstRows }, () => new Float32Array(dstCols))
      const sx = (srcCols - 1) / Math.max(dstCols - 1, 1)
      const sy = (srcRows - 1) / Math.max(dstRows - 1, 1)
      for (let dr = 0; dr < dstRows; dr++) {
        for (let dc = 0; dc < dstCols; dc++) {
          const fx = dc * sx, fy = dr * sy
          const sc = Math.min(Math.floor(fx), srcCols - 2)
          const sr = Math.min(Math.floor(fy), srcRows - 2)
          const tx = fx - sc, ty = fy - sr
          const a = src[sr][sc], b = src[sr][sc + 1]
          const c = src[sr + 1][sc], d = src[sr + 1][sc + 1]
          dst[dr][dc] = (1 - ty) * ((1 - tx) * a + tx * b) + ty * ((1 - tx) * c + tx * d)
        }
      }
      return dst
    }

    function ensureTerrainGeometry() {
      // 一次性创建几何体结构，后续只更新顶点位置
      if (terrainMesh) return  // 已创建
      if (!terrainGroup) return

      const DST_COLS = 160, DST_ROWS = 90
      const scaleX = 100, scaleZ = 80

      // 顶点：全部初始化为 0 高度
      const posArr = new Float32Array(DST_ROWS * DST_COLS * 3)
      const colArr = new Float32Array(DST_ROWS * DST_COLS * 3)
      const idx = []
      for (let r = 0; r < DST_ROWS; r++) {
        for (let c = 0; c < DST_COLS; c++) {
          const i = (r * DST_COLS + c) * 3
          posArr[i]     = (c / (DST_COLS - 1) - 0.5) * scaleX
          posArr[i + 1] = 0
          posArr[i + 2] = (r / (DST_ROWS - 1) - 0.5) * scaleZ
          colArr[i] = colArr[i+1] = colArr[i+2] = 0.5
        }
      }
      for (let r = 0; r < DST_ROWS - 1; r++) {
        for (let c = 0; c < DST_COLS - 1; c++) {
          const a = r * DST_COLS + c, b = a + 1, d = a + DST_COLS, e = d + 1
          idx.push(a, b, e, a, e, d)
        }
      }

      const geom = new THREE.BufferGeometry()
      geom.setAttribute('position', new THREE.BufferAttribute(posArr, 3))
      geom.setAttribute('color', new THREE.BufferAttribute(colArr, 3))
      geom.setIndex(idx)
      geom.computeVertexNormals()

      terrainMesh = new THREE.Mesh(geom, new THREE.MeshPhongMaterial({
        vertexColors: true, side: THREE.DoubleSide, shininess: 30, specular: 0x0a0a0a
      }))
      terrainGroup.add(terrainMesh)

      // 轻量网格线
      const edgeVerts = []
      const step = 8
      for (let r = 0; r < DST_ROWS; r += step)
        for (let c = 0; c < DST_COLS - 1; c++) {
          const i0 = (r * DST_COLS + c) * 3, i1 = (r * DST_COLS + c + 1) * 3
          edgeVerts.push(posArr[i0], posArr[i0+1], posArr[i0+2], posArr[i1], posArr[i1+1], posArr[i1+2])
        }
      for (let c = 0; c < DST_COLS; c += step)
        for (let r = 0; r < DST_ROWS - 1; r++) {
          const i0 = (r * DST_COLS + c) * 3, i1 = ((r+1) * DST_COLS + c) * 3
          edgeVerts.push(posArr[i0], posArr[i0+1], posArr[i0+2], posArr[i1], posArr[i1+1], posArr[i1+2])
        }
      const edgeGeom = new THREE.BufferGeometry()
      edgeGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(edgeVerts), 3))
      terrainWire = new THREE.LineSegments(edgeGeom,
        new THREE.LineBasicMaterial({ color: 0x6699bb, transparent: true, opacity: 0.06 }))
      terrainGroup.add(terrainWire)
    }

    function updateTerrainHeights(srcGrid, srcRows, srcCols) {
      ensureTerrainGeometry()
      if (!terrainMesh) return

      const DST_COLS = 160, DST_ROWS = 90
      const values = upsample2D(srcGrid, srcRows, srcCols, DST_ROWS, DST_COLS)

      // 找上采样后的真实峰值
      let peak = 0
      for (let r = 0; r < DST_ROWS; r++)
        for (let c = 0; c < DST_COLS; c++)
          if (values[r][c] > peak) peak = values[r][c]
      if (peak <= 0) peak = 1

      const heightScale = 12, gamma = 1.8
      const pos = terrainMesh.geometry.attributes.position.array
      const col = terrainMesh.geometry.attributes.color.array
      const scaleX = 100, scaleZ = 80

      for (let r = 0; r < DST_ROWS; r++) {
        for (let c = 0; c < DST_COLS; c++) {
          const i = (r * DST_COLS + c) * 3
          const v = values[r][c] || 0
          const norm = Math.max(0, Math.min(v / peak, 1))
          const elev = Math.pow(norm, gamma) * heightScale
          pos[i]     = (c / (DST_COLS - 1) - 0.5) * scaleX
          pos[i + 1] = elev
          pos[i + 2] = (r / (DST_ROWS - 1) - 0.5) * scaleZ

          const color = new THREE.Color()
          if (norm > 0.82) {
            const t = (norm - 0.82) / 0.18
            color.setHSL(0.28 - t * 0.28, 0.94, 0.40 + t * 0.22)
          } else {
            color.setHSL(0.64 - norm * 0.36, 0.88, 0.34 + norm * 0.28)
          }
          col[i] = color.r; col[i+1] = color.g; col[i+2] = color.b
        }
      }

      terrainMesh.geometry.attributes.position.needsUpdate = true
      terrainMesh.geometry.attributes.color.needsUpdate = true
      terrainMesh.geometry.computeVertexNormals()

      // 更新网格线顶点
      if (terrainWire) {
        const wp = terrainWire.geometry.attributes.position.array
        let wi = 0
        const step = 8
        for (let r = 0; r < DST_ROWS; r += step)
          for (let c = 0; c < DST_COLS - 1; c++) {
            const i0 = (r * DST_COLS + c) * 3, i1 = (r * DST_COLS + c + 1) * 3
            wp[wi]=pos[i0]; wp[wi+1]=pos[i0+1]; wp[wi+2]=pos[i0+2]; wi+=3
            wp[wi]=pos[i1]; wp[wi+1]=pos[i1+1]; wp[wi+2]=pos[i1+2]; wi+=3
          }
        for (let c = 0; c < DST_COLS; c += step)
          for (let r = 0; r < DST_ROWS - 1; r++) {
            const i0 = (r * DST_COLS + c) * 3, i1 = ((r+1) * DST_COLS + c) * 3
            wp[wi]=pos[i0]; wp[wi+1]=pos[i0+1]; wp[wi+2]=pos[i0+2]; wi+=3
            wp[wi]=pos[i1]; wp[wi+1]=pos[i1+1]; wp[wi+2]=pos[i1+2]; wi+=3
          }
        terrainWire.geometry.attributes.position.needsUpdate = true
      }

      // 更新 UI 信息
      const gEl = document.getElementById('t3GridSize')
      const pEl = document.getElementById('t3PeakVal')
      if (gEl) gEl.textContent = `${DST_COLS}×${DST_ROWS}`
      if (pEl) pEl.textContent = peak.toFixed(3)
    }

    function updateTerrainChart() {
      if (!terrainScene || !terrainGroup) return

      // STNNet 密度网格
      if (selectedTaskId.value?.startsWith('stv_') && densityGrid.value) {
        const den = densityGrid.value
        const rows = den.length, cols = den[0]?.length || 0
        if (rows >= 2 && cols >= 2) updateTerrainHeights(den, rows, cols)
        return
      }

      if (!allFrames.value.length) return
      // 3D 地形固定 12x12，不随网格分辨率变化
      const gs = 12
      const grid = Array.from({ length: gs }, () => Array(gs).fill(0))
      let maxCount = 0
      trailFrames.value.forEach(f => {
        if (f.peaks) f.peaks.forEach(([x, y]) => {
          const col = Math.min(gs - 1, Math.floor(x / videoWidth.value * gs))
          const row = Math.min(gs - 1, Math.floor(y / videoHeight.value * gs))
          grid[row][col]++
          if (grid[row][col] > maxCount) maxCount = grid[row][col]
        })
      })
      if (maxCount <= 0) maxCount = 1
      updateTerrainHeights(grid, gs, gs)
    }

    function updateTimeChart() {
      if (!timeChartInst || !allFrames.value.length) return
      const counts = allFrames.value.map(f => f.count)

      const windowSize = Math.max(3, Math.floor(counts.length / 30))
      const smoothed = []
      for (let i = 0; i < counts.length; i++) {
        let sum = 0, n = 0
        for (let j = Math.max(0, i - windowSize); j <= Math.min(counts.length - 1, i + windowSize); j++) {
          sum += counts[j]; n++
        }
        smoothed.push(Math.round(sum / n * 10) / 10)
      }

      const mean = counts.reduce((a, b) => a + b, 0) / counts.length
      const acf = []
      const maxLag = Math.min(counts.length - 1, 150)
      for (let lag = 0; lag <= maxLag; lag++) {
        let num = 0, den1 = 0, den2 = 0
        for (let t = 0; t < counts.length - lag; t++) {
          num += (counts[t] - mean) * (counts[t + lag] - mean)
          den1 += (counts[t] - mean) ** 2
          den2 += (counts[t + lag] - mean) ** 2
        }
        acf.push(den1 * den2 > 0 ? num / Math.sqrt(den1 * den2) : 0)
      }

      let bestLag = 0, bestACF = 0
      for (let lag = 5; lag < acf.length; lag++) {
        if (acf[lag] > bestACF && acf[lag] > 0.15) {
          bestACF = acf[lag]
          bestLag = lag
        }
      }

      const markLine = currentFrame.value > 0 ? [{
        xAxis: currentFrame.value,
        lineStyle: { color: c.orange, type: 'dashed', width: 1 },
        label: { formatter: `当前帧 ${currentFrame.value}`, color: c.orange, fontSize: 10 },
      }] : []

      timeChartInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0, textStyle: { color: c.axis, fontSize: 10 }, itemWidth: 12, itemHeight: 8 },
        grid: { top: 8, right: 16, bottom: 36, left: 48 },
        xAxis: {
          type: 'category',
          data: allFrames.value.map(f => f.frame),
          axisLabel: { color: c.axis, fontSize: 9, interval: Math.max(1, Math.floor(allFrames.value.length / 12)) },
        },
        yAxis: [
          { type: 'value', name: '人数', axisLabel: { color: c.axis, fontSize: 9 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } } },
          { type: 'value', name: '自相关', min: -1, max: 1, axisLabel: { color: c.axis, fontSize: 9 }, splitLine: { show: false } },
        ],
        series: [
          {
            name: '原始人数', type: 'bar', data: counts,
            itemStyle: { color: 'rgba(77,166,255,0.25)', borderColor: 'rgba(77,166,255,0.4)', borderWidth: 0.5 },
            barWidth: '80%',
          },
          {
            name: '平滑趋势', type: 'line', data: smoothed,
            lineStyle: { color: c.green, width: 2 },
            itemStyle: { color: c.green },
            symbol: 'none', smooth: true,
            markLine: { silent: true, symbol: 'none', data: markLine },
          },
          {
            name: '自相关', type: 'line', yAxisIndex: 1,
            data: acf.map((v, i) => [i + 1, v]),
            lineStyle: { color: c.orange, width: 1.5, type: 'dashed' },
            itemStyle: { color: c.orange },
            symbol: 'none',
          },
        ],
      })

      if (bestLag > 0) {
        timeChartInst.setOption({
          graphic: [{
            type: 'text', left: 'center', bottom: 22,
            style: { text: `周期 ≈ ${bestLag} 帧 (ACF=${bestACF.toFixed(2)})`, fill: c.orange, fontSize: 10, fontWeight: 'bold' },
          }],
        })
      }
    }

    function updateRoseChart() {
      if (!roseChartInst) return
      const { dirBins, dirNames } = motionStats.value
      const hasData = dirBins.reduce((a, b) => a + b, 0) > 0
      const finalValues = hasData
        ? dirBins.map((v, i) => ({ value: v, name: dirNames[i] }))
        : dirNames.map((n, i) => ({ value: 0, name: n }))

      roseChartInst.setOption({
        tooltip: { trigger: 'item', formatter: p => `${p.name}: ${p.value}次` },
        legend: {
          bottom: 0, textStyle: { color: c.axis, fontSize: 9 },
          itemWidth: 8, itemHeight: 8,
        },
        polar: { radius: ['15%', '72%'] },
        angleAxis: {
          type: 'category', data: dirNames,
          axisLabel: { color: c.axis, fontSize: 10, fontWeight: 'bold' },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        },
        radiusAxis: { axisLabel: { show: false }, splitLine: { show: false } },
        series: [{
          type: 'bar', data: finalValues, coordinateSystem: 'polar',
          itemStyle: {
            borderRadius: 4,
            color: p => {
              const colors = ['#4da6ff','#5ea6ee','#40d870','#70e090','#ffa040','#ffb060','#ff4070','#ff6080']
              return colors[p.dataIndex]
            },
            shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)',
          },
          emphasis: { itemStyle: { shadowBlur: 16, shadowColor: 'rgba(0,0,0,0.6)' } },
        }],
      })
    }

    function updateAllCharts() {
      if (!terrainScene || !timeChartInst || !roseChartInst) initAllCharts()
      updateTerrainChart()
      updateTimeChart()
      updateRoseChart()
      // 对底部两个 echarts 图表做延迟 resize，确保 grid 布局已完成
      requestAnimationFrame(() => {
        timeChartInst?.resize()
        roseChartInst?.resize()
        requestAnimationFrame(() => {
          timeChartInst?.resize()
          roseChartInst?.resize()
        })
      })
      nextTick(() => drawOverlay())
    }

    function resizeAllCharts() {
      if (terrainRenderer && terrainContainer.value) {
        const w = terrainContainer.value.clientWidth
        const h = terrainContainer.value.clientHeight
        if (w > 0 && h > 0) {
          terrainCamera.aspect = w / h
          terrainCamera.updateProjectionMatrix()
          terrainRenderer.setSize(w, h)
        }
      }
      timeChartInst?.resize()
      roseChartInst?.resize()
    }

    // ==================== 播放控制 ====================

    function togglePlay() {
      if (isPlaying.value) {
        clearInterval(playTimer)
        isPlaying.value = false
      } else {
        isPlaying.value = true
        playTimer = setInterval(() => {
          if (currentFrame.value >= totalFrames.value) {
            currentFrame.value = 1
          } else {
            currentFrame.value++
          }
        }, 150)
      }
    }

    // ==================== 任务选择 ====================

    async function selectTask(taskId) {
      selectedTaskId.value = taskId
      if (!taskId) return
      try {
        const res = await axios.get(`/api/v1/video/result/${taskId}`)
        if (!res.data.frames || res.data.frames.length === 0) return
        allFrames.value = res.data.frames
        totalFrames.value = res.data.total_frames || 0
        videoWidth.value = res.data.width || 1920
        videoHeight.value = res.data.height || 1080
        currentFrame.value = 1
        loadFrame()
        nextTick(() => {
          initAllCharts()
          resizeAllCharts()
          updateAllCharts()
          if (taskId.startsWith('stv_')) loadDensityGrid().then(updateTerrainChart)
        })
      } catch (e) {
        console.error('[SpatialAnalysis] 获取结果失败:', e)
      }
    }

    function loadFrame() {
      if (!selectedTaskId.value) return
      overlayError.value = ''
      frameSrc.value = `/api/v1/video/frame/${selectedTaskId.value}/${currentFrame.value}?v=${Date.now()}`
    }

    // ==================== 生命周期 ====================

    watch(currentFrame, () => {
      loadFrame()
      updateTimeChart()
      updateRoseChart()
      if (selectedTaskId.value?.startsWith('stv_')) loadDensityGrid().then(updateTerrainChart)
    })

    watch([trailLength, gridSize], () => {
      updateAllCharts()
    })

    function onThemeChange() {
      if (terrainScene) {
        if (terrainFrameId) cancelAnimationFrame(terrainFrameId)
        if (terrainRenderer) { terrainRenderer.dispose(); terrainRenderer = null }
        terrainScene.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose()
          if (obj.material) obj.material.dispose()
        })
        terrainScene = null
      }
      terrainGroup = null; terrainCamera = null; terrainMesh = null; terrainWire = null
      initAllCharts()
      resizeAllCharts()
      if (allFrames.value.length > 0) updateAllCharts()
    }

    onMounted(() => {
      window.addEventListener('resize', resizeAllCharts)
      window.addEventListener('themechange', onThemeChange)
      setTimeout(() => {
        if (doneTasks.value.length > 0 && !selectedTaskId.value) {
          selectTask(doneTasks.value[0].task_id)
        }
      }, 100)
    })

    onActivated(() => {
      nextTick(() => {
        initAllCharts()
        resizeAllCharts()
        if (allFrames.value.length > 0) updateAllCharts()
      })
    })

    onUnmounted(() => {
      clearInterval(playTimer)
      if (terrainFrameId) cancelAnimationFrame(terrainFrameId)
      if (terrainRenderer) { terrainRenderer.dispose(); terrainRenderer = null }
      if (terrainScene) {
        terrainScene.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose()
          if (obj.material) obj.material.dispose()
        })
        terrainScene = null
      }
      terrainGroup = null; terrainCamera = null; terrainMesh = null; terrainWire = null
      timeChartInst?.dispose(); roseChartInst?.dispose()
      window.removeEventListener('resize', resizeAllCharts)
      window.removeEventListener('themechange', onThemeChange)
    })

    return {
      doneTasks, selectedTaskId, currentFrame, totalFrames,
      trailLength, gridSize, frameSrc, overlayError,
      overlayWrap, overlayImg, overlayCanvas,
      terrainContainer, timeChart, roseChart,
      isPlaying, togglePlay,
      currentFrameData, motionStats,
      selectTask, onOverlayImgLoad, onOverlayImgError,
    }
  }
}
</script>

<style scoped>
.spatial-page { height: 100%; width: 100%; display: flex; overflow: hidden; }

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

.btn {
  background: var(--border-subtle); color: var(--text-dim);
  border: 1px solid var(--border-subtle); border-radius: 3px;
  cursor: pointer; transition: all 0.15s;
}
.btn:hover { background: var(--accent-glow); color: #8ab8ff; }
.btn.playing { background: rgba(255,64,112,0.15); border-color: var(--danger); color: var(--danger); }

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

.right-panel {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 8px 12px 16px;
}
.right-panel::-webkit-scrollbar { width: 6px; }
.right-panel::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
.right-panel::-webkit-scrollbar-thumb { background: rgba(77,166,255,0.3); border-radius: 3px; }

.chart-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  margin-bottom: 10px;
}
.chart-cell {
  background: var(--bg-card); border: 1px solid var(--border-subtle);
  border-radius: 6px; padding: 10px;
}
.chart-h3 { margin: 0 0 8px; font-size: 12px; color: #8ab8ff; font-weight: 600; }
.chart-inner { width: 100%; height: 420px; }
.chart-row-bottom .chart-inner { height: 320px; }

.t3-legend {
  position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  display: flex; align-items: center; gap: 5px;
  z-index: 10; pointer-events: none;
}
.t3-legend-bar {
  width: 8px; height: 120px; border-radius: 4px;
  border: 1px solid rgba(255,255,255,0.06);
  background: linear-gradient(to bottom,
    #f97b2d 0%, #e8a820 8%, #82cc28 20%, #27c918 35%,
    #0fd856 50%, #09c8ae 65%, #06b8e8 80%, #0685d0 92%, #0533a8 100%);
}
.t3-legend-labels {
  display: flex; flex-direction: column; justify-content: space-between;
  height: 120px; font-size: 9px; color: rgba(255,255,255,0.35);
}
.t3-info {
  position: absolute; left: 12px; bottom: 10px;
  display: flex; gap: 16px;
  z-index: 10; pointer-events: none;
}
.t3-info-kv { display: flex; flex-direction: column; gap: 1px; }
.t3-info-val {
  font-family: Rajdhani, monospace;
  font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.60);
}
.t3-info-key { font-size: 9px; color: rgba(255,255,255,0.25); }

.canvas-wrap {
  position: relative; width: 100%; height: 420px;
  background: rgba(0,0,0,0.3); border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.overlay-img {
  position: absolute; top: 0; left: 0;
  width: 100%; height: 100%; object-fit: contain;
  opacity: 0.55;
}
.overlay-canvas {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  z-index: 2;
}
.overlay-placeholder {
  position: absolute; color: var(--text-dim); font-size: 14px;
}
</style>
