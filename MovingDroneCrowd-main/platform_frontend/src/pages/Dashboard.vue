<template>
  <div class="dashboard">
    <div class="main-content">
      <!-- 左侧面板 -->
      <aside class="left-panel">
        <div class="panel" style="padding:8px 12px">
          <div class="mode-tabs">
            <button class="mode-tab" :class="{ active: mode === 'video' }" @click="mode = 'video'">⬡ 视频</button>
            <button class="mode-tab" :class="{ active: mode === 'image' }" @click="mode = 'image'">⊞ 图片</button>
          </div>
        </div>

        <!-- 视频模式 -->
        <template v-if="mode === 'video'">
        <div class="panel upload-panel">
          <h3>⬡ 视频上传</h3>
          <div class="upload-zone" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
            <input ref="fileInput" type="file" accept=".mp4,.avi,.mov,.mkv" hidden @change="handleFile" />
            <template v-if="!uploading">
              <div style="font-size:28px; margin-bottom:6px">⊟</div>
              <div>点击或拖拽上传视频</div>
              <div style="font-size:10px; color:var(--text-dim); margin-top:4px">支持 MP4 / AVI / MOV / MKV</div>
            </template>
            <template v-else>
              <div style="font-size:28px; margin-bottom:6px">↻</div>
              <div>上传中...</div>
              <div class="progress-bar" style="margin-top:8px">
                <div class="fill" :style="{ width: uploadProgress + '%' }"></div>
              </div>
            </template>
          </div>
          <div v-if="uploadedFile" style="margin-top:6px; font-size:11px; color:var(--text-dim)">
            已上传: {{ uploadedFile }} ({{ uploadedSize }}MB)
          </div>
          <button class="btn" style="width:100%; margin-top:10px" :disabled="!uploadedFile || analyzing" @click="startAnalyze">
            {{ analyzing ? '分析中...' : '↗ 开始分析' }}
          </button>
        </div>
        </template>

        <!-- 帧测试模式 -->
        <template v-if="mode === 'image'">
        <div class="panel upload-panel">
          <h3>⊹ 帧测试上传</h3>

          <!-- 帧图片上传 -->
          <div class="upload-zone" @click="triggerFrameUpload" @dragover.prevent @drop.prevent="handleFrameDrop">
            <input ref="frameFileInput" type="file" accept=".jpg,.jpeg,.png,.bmp,.tiff" multiple hidden @change="handleFrameFile" />
            <template v-if="!frameUploading">
              <div style="font-size:28px; margin-bottom:6px">⊟</div>
              <div>点击或拖拽上传帧图片</div>
              <div style="font-size:10px; color:var(--text-dim); margin-top:4px">支持多选 JPG / PNG / BMP / TIFF</div>
            </template>
            <template v-else>
              <div style="font-size:28px; margin-bottom:6px">↻</div>
              <div>上传中...</div>
            </template>
          </div>
          <div v-if="frameFiles.length > 0" style="margin-top:6px; font-size:11px; color:var(--text-dim)">
            已选择 {{ frameFiles.length }} 帧
          </div>

          <!-- 标签 CSV 上传 -->
          <div class="upload-zone" style="margin-top:10px; min-height:70px" @click="triggerLabelUpload" @dragover.prevent @drop.prevent="handleLabelDrop">
            <input ref="labelFileInput" type="file" accept=".csv" hidden @change="handleLabelFile" />
            <template v-if="!labelFile">
              <div style="font-size:20px; margin-bottom:4px">⊡</div>
              <div>点击上传标签 CSV</div>
              <div style="font-size:10px; color:var(--text-dim); margin-top:2px">frame,count 或 frame,person_id,x,y,w,h</div>
            </template>
            <template v-else>
              <div style="font-size:20px; margin-bottom:4px">✓</div>
              <div>已上传: {{ labelFile.name }}</div>
            </template>
          </div>



          <button class="btn" style="width:100%; margin-top:6px" :disabled="frameFiles.length === 0 || !labelFile || frameTestRunning" @click="startFrameTest">
            {{ frameTestRunning ? '分析中...' : '⊕ 启动帧测试' }}
          </button>

          <!-- 数据集场景测试 -->
          <div style="margin-top:6px; display:flex; gap:6px; flex-wrap:wrap">
            <button class="btn" style="flex:1; min-width:120px; background:rgba(77,166,255,0.12); border-color:rgba(77,166,255,0.35); color:var(--accent); font-size:11px; white-space:nowrap"
                    :disabled="frameTestRunning" @click="startSceneTest('scene_1/1')">
              ⚡ GD³A + STEERER 场景评测
            </button>
          </div>

          <!-- 进度 -->
          <div v-if="frameTestRunning && frameTestTask" style="margin-top:10px">
            <div class="progress-bar" style="margin: 6px 0">
              <div class="fill" :style="{ width: frameTestTask.progress + '%' }"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px">
              <span style="color:var(--text-dim)">{{ frameTestTask.message }}</span>
              <span v-if="frameTestTask.elapsed" style="color:var(--text-dim)">{{ frameTestTask.elapsed }}s</span>
            </div>
            <!-- 步骤指示器 -->
            <div v-if="frameTestTask.steps" style="display:flex;flex-wrap:wrap;gap:3px 6px;margin-top:4px">
              <span v-for="(s, si) in frameTestTask.steps" :key="si"
                :style="{
                  fontSize:'10px',
                  padding:'2px 6px',
                  borderRadius:'3px',
                  color: s.status === 'done' ? chartColors.green : s.status === 'running' ? chartColors.orange : s.status === 'skipped' ? '#5a6070' : '#3a5070',
                  background: s.status === 'running' ? 'rgba(255,160,64,0.12)' : s.status === 'done' ? 'rgba(64,216,112,0.08)' : 'rgba(40,60,100,0.3)',
                  border: '1px solid ' + (s.status === 'running' ? 'rgba(255,160,64,0.3)' : s.status === 'done' ? 'rgba(64,216,112,0.2)' : 'rgba(40,60,100,0.2)'),
                }">
                {{ s.status === 'done' ? '✓' : s.status === 'running' ? '●' : s.status === 'skipped' ? '−' : '○' }} {{ s.name }}
              </span>
            </div>
          </div>

          <!-- 汇总指标 -->
          <div v-if="frameTestResult" class="img-result-stats" style="margin-top:10px">
            <div class="stat-row"><span>推理模型</span><span class="digital" style="color:var(--warning);font-size:11px">{{ frameTestResult.model_mode || 'GD3A' }}</span></div>
            <div class="stat-row"><span>总帧数</span><span class="digital" style="color:var(--accent);font-size:18px">{{ frameTestResult.total_frames }}</span></div>
            <div class="stat-row"><span>GT 总数</span><span class="digital" style="color:var(--success);font-size:18px">{{ frameTestResult.total_gt }}</span></div>
            <div class="stat-row"><span>预测总数</span><span class="digital" style="color:var(--warning);font-size:18px">{{ frameTestResult.total_pred }}</span></div>
            <div class="stat-row"><span>MAE</span><span class="digital" style="color:var(--danger);font-size:18px">{{ frameTestResult.overall_mae }}</span></div>
            <div class="stat-row"><span>MSE</span><span class="digital" style="color:var(--danger);font-size:12px">{{ frameTestResult.overall_mse }}</span></div>
            <div class="stat-row"><span>准确率</span><span class="digital" style="color:var(--success);font-size:12px">{{ frameTestResult.overall_accuracy }}%</span></div>
            <template v-if="frameTestResult.overall_precision !== undefined">
              <div class="stat-row"><span>Precision</span><span class="digital" style="color:var(--success);font-size:12px">{{ (frameTestResult.overall_precision * 100).toFixed(1) }}%</span></div>
              <div class="stat-row"><span>Recall</span><span class="digital" style="color:var(--warning);font-size:12px">{{ (frameTestResult.overall_recall * 100).toFixed(1) }}%</span></div>
              <div class="stat-row"><span>F1 Score</span><span class="digital" style="color:var(--accent);font-size:12px">{{ (frameTestResult.overall_f1 * 100).toFixed(1) }}%</span></div>
            </template>
            <div class="stat-row"><span>耗时</span><span class="digital" style="font-size:11px">{{ frameTestResult.elapsed }}s</span></div>
          </div>
        </div>
        </template>

        <div class="panel param-panel">
          <h3>⚙️ 参数设置</h3>
          <div class="param-row">
            <label>检测阈值</label>
            <input type="range" min="0.05" max="0.5" step="0.01" v-model="params.threshold" />
            <span class="digital" style="font-size:11px">{{ params.threshold }}</span>
          </div>
          <div class="param-row">
            <label>选择模型</label>
            <select v-model="selectedModel" class="param-select">
              <option value="STEERER">STEERER 密度估计器</option>
              <option value="YOLO11">YOLO11 行人检测</option>
              <option value="STNNet">STNNet 人群检测/追踪</option>
            </select>
          </div>
          <div class="param-row">
            <label>推理模式</label>
            <select v-model="params.mode" class="param-select">
              <option value="counting" v-if="selectedModel !== 'STNNet'">人群计数</option>
              <option value="tracking">{{ selectedModel === 'STNNet' ? '人群追踪' : '个体跟踪 (GD³A)' }}</option>
              <option value="detection" v-if="selectedModel === 'STNNet'">目标检测</option>
            </select>
          </div>
        </div>

        <!-- 任务列表 -->
        <div class="panel task-panel">
          <h3>☰ 任务列表 <span class="task-count">{{ tasks.length }}</span></h3>
          <div class="task-list">
            <div v-for="task in tasks" :key="task.task_id"
                 class="task-item"
                 :class="{ active: currentTaskId === task.task_id }"
                 @click="selectTask(task.task_id)">
              <span class="status-dot" :class="'status-' + task.status"></span>
              <div class="task-info">
                <span class="task-id">{{ task.task_id?.substring(0, 8) }}</span>
                <span class="task-msg">{{ task.message || '等待中...' }}</span>
              </div>
              <span class="task-status-tag" :class="'tag-' + task.status">
                {{ statusLabel(task.status) }}
              </span>
              <button class="task-delete-btn" title="删除任务" @click.stop="deleteTask(task.task_id)">✕</button>
            </div>
            <div v-if="tasks.length === 0" class="task-empty">
              <div style="font-size:28px;margin-bottom:8px;opacity:0.3">📭</div>
              <div>暂无任务</div>
              <div style="font-size:10px;color:var(--text-dim)">上传视频开始分析</div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中央区域 -->
      <main class="center-panel">
        <div class="panel video-panel">
          <h3>{{ mode === 'video' ? '📺 实时分析画面' : (mode === 'image' ? '⊹ 帧测试对比结果' : '⊞ 图片分析结果') }}</h3>
          <div class="video-container">
            <div v-if="mode === 'video' && !videoSrc" class="video-placeholder">
              <div style="font-size:40px">🎥</div>
              <div style="margin-top:12px; color:var(--text-dim)">上传视频并开始分析后<br/>在此查看标注结果</div>
            </div>
            <div v-if="mode === 'video' && videoSrc" class="video-wrapper" ref="videoWrapper">
              <video ref="videoPlayer" :src="videoSrc" autoplay loop playsinline
                     class="dashboard-video" />
            </div>
            <!-- 控制栏放在 video-container 内、video-wrapper 外，确保始终可见 -->
            <div v-if="mode === 'video' && videoSrc" class="video-controls-bar">
              <button class="video-ctrl-btn" @click="toggleVideoPlay" :title="videoPlaying ? '暂停' : '播放'">
                {{ videoPlaying ? '⏹' : '▸' }}
              </button>
              <button class="video-ctrl-btn" @click="toggleVideoFullscreen" :title="videoFullscreen ? '退出全屏' : '全屏播放'">
                ⛶
              </button>
            </div>

            <!-- 帧测试模式 -->
            <div v-if="mode === 'image' && !frameTestResult" class="video-placeholder">
              <div style="font-size:40px">⊟</div>
              <div style="margin-top:12px; color:var(--text-dim)">上传帧图片 + 标签 CSV 并启动测试<br/>在此查看 GT vs 预测对比结果</div>
            </div>
            <div v-if="mode === 'image' && frameTestResult" class="frame-test-result">
              <!-- 帧导航 + 信息（水平布局，紧凑） -->
              <div class="frame-test-bar">
                <button class="frame-test-btn" @click="prevFrameTestImage">‹</button>
                <span class="frame-test-info">帧 {{ currentFrameTestIndex + 1 }} / {{ frameTestResult.frames.length }}</span>
                <button class="frame-test-btn" @click="nextFrameTestImage">›</button>
                <span class="frame-sep">|</span>
                <span class="frame-badge">Frame {{ currentFrameData?.frame }}</span>
                <span class="frame-stat gt">GT {{ currentFrameData?.gt_count }}</span>
                <span class="frame-stat pred">Pred {{ currentFrameData?.pred_count }}</span>
                <span v-if="currentFrameData?.error !== undefined" class="frame-stat ae">AE {{ currentFrameData?.error }}</span>
                <template v-if="currentFrameData?.precision !== undefined">
                  <span class="frame-stat gt">P {{ (currentFrameData?.precision * 100).toFixed(1) }}%</span>
                  <span class="frame-stat pred">R {{ (currentFrameData?.recall * 100).toFixed(1) }}%</span>
                  <span class="frame-stat ae">F1 {{ (currentFrameData?.f1 * 100).toFixed(1) }}%</span>
                </template>
              </div>
              <!-- 三张主图：原图 / GT / Pred -->
              <div v-if="currentFrameMaps.length > 0" class="frame-main-images">
                <div v-for="map in getMapsByCategory('original_global')" :key="map.type" class="frame-main-card">
                  <div class="density-card-tag" :class="map.type === 'original' ? 'tag-orig' : (map.label.startsWith('GT') ? 'tag-gt' : 'tag-pred')">{{ map.label }}</div>
                  <img :src="getDensityImageUrl(map.filename)" class="frame-main-img" />
                </div>
              </div>
            </div>
          </div>
          <div v-if="mode === 'video' && currentTask" class="video-info">
            <div class="progress-bar" style="margin: 8px 0">
              <div class="fill" :style="{ width: currentTask.progress + '%' }"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-dim)">
              <span>{{ currentTask.message }}</span>
              <span v-if="currentTask.progress === 100" class="digital" style="color:var(--success)">✓ 完成</span>
              <span v-else class="digital">{{ currentTask.progress }}%</span>
            </div>
          </div>
        </div>
      </main>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <div class="panel">
          <h3>≡ 任务概要</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value digital" style="color:var(--accent)">{{ currentStats.avgCount }}</div>
              <div class="stat-label">平均人数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="color:var(--warning)">{{ currentStats.peakCount }}</div>
              <div class="stat-label">峰值人数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital" style="color:var(--success)">{{ currentStats.minCount }}</div>
              <div class="stat-label">最低人数</div>
            </div>
            <div class="stat-card">
              <div class="stat-value digital">{{ currentStats.totalFrames }}</div>
              <div class="stat-label">总帧数</div>
            </div>
            <div class="stat-card" style="grid-column: 1 / -1">
              <div class="stat-value digital" style="font-size:14px">{{ currentStats.elapsed }}</div>
              <div class="stat-label">推理总耗时</div>
            </div>
          </div>
        </div>

        <div class="panel">
          <h3>⊙ 密度分布</h3>
          <div ref="densityChart" style="height:160px"></div>
        </div>

      </aside>
    </div>

    <!-- 底部：视频模式显示曲线 / 图片模式显示密度图 -->
    <footer class="bottom-panel">
      <div v-if="mode === 'video'" class="panel chart-panel">
        <h3>↗ 人群数量变化曲线</h3>
        <div ref="countChart" style="height:160px"></div>
      </div>
      <div v-if="mode === 'image' && frameTestResult" class="density-groups-bottom">
        <!-- STNNet 布局：热力图叠加占满 -->
        <template v-if="getMapsByCategory('overlay').length > 0">
          <div class="density-group" style="flex:1; min-width:100%">
            <div class="group-title">⊛ 热力图叠加</div>
            <div class="group-maps cols-2" style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))">
              <div v-for="map in getMapsByCategory('overlay')" :key="map.type" class="density-card">
                <div class="density-card-tag tag-pred">{{ map.label }}</div>
                <img :src="getDensityImageUrl(map.filename)" class="density-img-bottom" style="max-height:240px" />
                <div class="density-card-count" v-if="map.count > 0">{{ map.count.toFixed(1) }}</div>
              </div>
            </div>
          </div>
        </template>
        <!-- GD3A 布局：Shared 图放底部 -->
        <template v-else>
          <div class="density-group">
            <div class="group-title">⏪ Shared(Prev) &amp; IN</div>
            <div class="group-maps cols-4">
              <div v-for="map in getMapsByCategory('prev_in')" :key="map.type" class="density-card">
                <div class="density-card-tag" :class="map.label.startsWith('GT') ? 'tag-gt' : 'tag-pred'">{{ map.label }}</div>
                <img :src="getDensityImageUrl(map.filename)" class="density-img-bottom" />
                <div class="density-card-count" v-if="map.count > 0">{{ map.count.toFixed(1) }}</div>
              </div>
            </div>
          </div>
          <div class="density-group">
            <div class="group-title">⏩ Shared(Next) &amp; OUT</div>
            <div class="group-maps cols-4">
              <div v-for="map in getMapsByCategory('next_out')" :key="map.type" class="density-card">
                <div class="density-card-tag" :class="map.label.startsWith('GT') ? 'tag-gt' : 'tag-pred'">{{ map.label }}</div>
                <img :src="getDensityImageUrl(map.filename)" class="density-img-bottom" />
                <div class="density-card-count" v-if="map.count > 0">{{ map.count.toFixed(1) }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </footer>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onActivated, onUnmounted, inject, watch, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { getEchartsTheme, getChartColors } from '../echartsTheme.js'

export default {
  name: 'Dashboard',
  setup() {
    const fileInput = ref(null)
    const frameFileInput = ref(null)
    const labelFileInput = ref(null)
    const videoPlayer = ref(null)
    const videoWrapper = ref(null)
    const densityChart = ref(null)
    const countChart = ref(null)
    const frameCompareChart = ref(null)

    const mode = ref('video')
    const uploadedFile = ref('')
    const uploadedSize = ref(0)
    const uploading = ref(false)
    const uploadProgress = ref(0)
    const analyzing = ref(false)

    // 帧测试相关状态
    const frameFiles = ref([])
    const labelFile = ref(null)
    const frameUploading = ref(false)
    const frameTestRunning = ref(false)
    const frameTestTask = ref(null)
    const frameTestResult = ref(null)
    const frameTestTaskId = ref('')
    const currentFrameTestIndex = ref(0)
    // 使用 selectedModel 作为帧测试模型
    const frameTestModel = computed(() => selectedModel.value)
    let frameTestPollingTimer = null

    // 使用全局共享状态（来自 App.vue 的 provide）
    const tasks = inject('globalTasks')
    const currentTaskId = inject('globalCurrentTaskId')
    const currentTask = inject('globalCurrentTask')
    const currentResult = inject('globalCurrentResult')

    const globalSelectTask = inject('selectTask')
    const globalLoadTasks = inject('loadTasks')
    const globalLoadTaskDetail = inject('loadTaskDetail')
    const globalOnTaskCompleted = inject('onTaskCompleted')
    const deleteTask = inject('deleteTask')

    const chartColors = computed(() => getChartColors())
    const videoSrc = ref('')
    const videoFullscreen = ref(false)
    const videoPlaying = ref(true)
    const params = reactive({ mode: 'counting', threshold: 0.15 })
    const selectedModel = ref('STEERER')
    // STNNet 选中时默认 tracking, 切换到其他模型时恢复 counting
    watch(selectedModel, (val) => {
      if (val === 'STNNet' && params.mode === 'counting') {
        params.mode = 'tracking'
      }
    })
    // 切回视频模式时重新初始化 countChart
    watch(mode, (val) => {
      if (val === 'video') {
        nextTick(() => {
          if (countChart.value) {
            if (countChartInst) countChartInst.dispose()
            countChartInst = echarts.init(countChart.value, getEchartsTheme())
            if (currentResult.value) {
              const frames = currentResult.value.frames || []
              if (frames.length) updateCountChart(frames)
            }
          }
        })
      }
    })
    const currentStats = reactive({ avgCount: 0, peakCount: 0, minCount: 0, totalFrames: 0, elapsed: '0s' })
    const densityData = ref([])

    let pollingTimer = null
    let densityChartInst = null
    let countChartInst = null
    let resizeObserver = null

    function observeResize() {
      if (resizeObserver) resizeObserver.disconnect()
      const el = document.querySelector('.dashboard .center-panel')
      if (!el || !window.ResizeObserver) return
      resizeObserver = new ResizeObserver(() => resizeCharts())
      resizeObserver.observe(el)
      // 同时观察 bottom-panel
      const bottomEl = document.querySelector('.dashboard .bottom-panel')
      if (bottomEl) resizeObserver.observe(bottomEl)
    }

    function triggerUpload() { fileInput.value?.click() }
    async function handleFile(e) { const f = e.target.files[0]; if (f) await doUpload(f) }
    async function handleDrop(e) { const f = e.dataTransfer.files[0]; if (f) await doUpload(f) }
    async function doUpload(file) {
      uploading.value = true; uploadProgress.value = 0
      const form = new FormData(); form.append('file', file)
      try {
        const res = await axios.post('/api/v1/video/upload', form, {
          onUploadProgress: (e) => { uploadProgress.value = Math.round((e.loaded / e.total) * 100) }
        })
        uploadedFile.value = res.data.filename; uploadedSize.value = res.data.size_mb
      } catch (e) { alert('上传失败: ' + e.message) }
      uploading.value = false
    }

    function triggerFrameUpload() { frameFileInput.value?.click() }
    function handleFrameFile(e) { frameFiles.value = Array.from(e.target.files || []) }
    function handleFrameDrop(e) { frameFiles.value = Array.from(e.dataTransfer.files || []) }

    function triggerLabelUpload() { labelFileInput.value?.click() }
    function handleLabelFile(e) {
      const f = e.target.files[0]
      if (f) labelFile.value = f
    }
    function handleLabelDrop(e) {
      const f = e.dataTransfer.files[0]
      if (f) labelFile.value = f
    }

    async function startFrameTest() {
      if (frameFiles.value.length === 0 || !labelFile.value) return
      frameUploading.value = true
      frameTestRunning.value = true
      frameTestResult.value = null
      frameTestTask.value = null
      currentFrameTestIndex.value = 0

      const form = new FormData()
      frameFiles.value.forEach(f => form.append('files', f))
      form.append('label_file', labelFile.value)

      // STNNet 模型走 stnnet-test 接口
      const apiPath = selectedModel.value === 'STNNet'
        ? '/api/v1/dataset/stnnet-test/upload'
        : '/api/v1/dataset/frame-test/upload'
      const pollingFn = selectedModel.value === 'STNNet'
        ? startSTNNetPolling
        : startFrameTestPolling

      try {
        const res = await axios.post(apiPath, form, {
          params: { model: selectedModel.value }
        })
        frameTestTaskId.value = res.data.task_id
        pollingFn()
      } catch (e) {
        alert('帧测试上传失败: ' + e.message)
        frameTestRunning.value = false
      }
      frameUploading.value = false
    }

    async function startSceneTest(sceneName) {
      mode.value = 'image'  // 自动切换到帧测试显示模式
      frameTestRunning.value = true
      frameTestResult.value = null
      frameTestTask.value = null
      currentFrameTestIndex.value = 0

      // STNNet 模型走 stnnet-test 接口
      const apiPath = selectedModel.value === 'STNNet'
        ? '/api/v1/dataset/stnnet-test/start'
        : '/api/v1/dataset/scene-test/start'
      const pollingFn = selectedModel.value === 'STNNet'
        ? startSTNNetPolling
        : startSceneTestPolling

      try {
        const res = await axios.post(apiPath, null, {
          params: { scene_name: sceneName, test_interval: selectedModel.value === 'STNNet' ? 1 : 4 }
        })
        frameTestTaskId.value = res.data.task_id
        pollingFn()
      } catch (e) {
        alert('Scene 测试启动失败: ' + e.message)
        frameTestRunning.value = false
      }
    }

    function startSceneTestPolling() {
      if (frameTestPollingTimer) clearInterval(frameTestPollingTimer)
      frameTestPollingTimer = setInterval(async () => {
        try {
          const statusRes = await axios.get(`/api/v1/dataset/scene-test/status/${frameTestTaskId.value}`)
          frameTestTask.value = statusRes.data
          if (statusRes.data.status === 'done') {
            clearInterval(frameTestPollingTimer)
            await loadSceneTestResult()
            frameTestRunning.value = false
          }
          if (statusRes.data.status === 'failed' || statusRes.data.status === 'error') {
            clearInterval(frameTestPollingTimer)
            frameTestRunning.value = false
          }
        } catch (e) {
          console.error('Scene test polling error:', e)
        }
      }, 2000)
    }

    async function loadSceneTestResult() {
      try {
        const res = await axios.get(`/api/v1/dataset/scene-test/result/${frameTestTaskId.value}`)
        frameTestResult.value = res.data
        await nextTick()
        renderFrameCompareChart()
      } catch (e) {
        console.error('Load scene test result error:', e)
      }
    }

    // ===== STNNet 测试 =====
    async function startSTNNetTest(sceneName) {
      frameTestRunning.value = true
      frameTestResult.value = null
      frameTestTask.value = null
      currentFrameTestIndex.value = 0

      try {
        const res = await axios.post('/api/v1/dataset/stnnet-test/start', null, {
          params: { scene_name: sceneName, test_interval: 1 }
        })
        frameTestTaskId.value = res.data.task_id
        startSTNNetPolling()
      } catch (e) {
        alert('STNNet 测试启动失败: ' + e.message)
        frameTestRunning.value = false
      }
    }

    function startSTNNetPolling() {
      if (frameTestPollingTimer) clearInterval(frameTestPollingTimer)
      frameTestPollingTimer = setInterval(async () => {
        try {
          const statusRes = await axios.get(`/api/v1/dataset/stnnet-test/status/${frameTestTaskId.value}`)
          frameTestTask.value = statusRes.data
          if (statusRes.data.status === 'done') {
            clearInterval(frameTestPollingTimer)
            await loadSTNNetTestResult()
            frameTestRunning.value = false
          }
          if (statusRes.data.status === 'failed' || statusRes.data.status === 'error') {
            clearInterval(frameTestPollingTimer)
            frameTestRunning.value = false
          }
        } catch (e) {
          console.error('STNNet test polling error:', e)
        }
      }, 2000)
    }

    async function loadSTNNetTestResult() {
      try {
        const res = await axios.get(`/api/v1/dataset/stnnet-test/result/${frameTestTaskId.value}`)
        frameTestResult.value = res.data
        updateStatsFromSTNNetTest(res.data)
        await nextTick()
        renderFrameCompareChart()
      } catch (e) {
        console.error('Load STNNet test result error:', e)
      }
    }

    function updateStatsFromSTNNetTest(result) {
      const frames = result.frames || []
      if (frames.length === 0) return
      currentStats.avgCount = Math.round((result.total_gt + result.total_pred) / (2 * frames.length))
      currentStats.peakCount = Math.max(...frames.map(f => Math.max(f.gt_count, f.pred_count)))
      currentStats.minCount = Math.min(...frames.map(f => Math.min(f.gt_count, f.pred_count)))
      currentStats.totalFrames = frames.length
      currentStats.elapsed = (result.elapsed || 0) + 's'
      updateCountChartDual(frames)
      updateDensityChart(frames.map(f => ({ count: f.pred_count })))
    }

    function startFrameTestPolling() {
      if (frameTestPollingTimer) clearInterval(frameTestPollingTimer)
      frameTestPollingTimer = setInterval(async () => {
        try {
          const statusRes = await axios.get(`/api/v1/dataset/frame-test/status/${frameTestTaskId.value}`)
          frameTestTask.value = statusRes.data
          if (statusRes.data.status === 'done') {
            clearInterval(frameTestPollingTimer)
            await loadFrameTestResult()
            frameTestRunning.value = false
          }
          if (statusRes.data.status === 'failed' || statusRes.data.status === 'error') {
            clearInterval(frameTestPollingTimer)
            frameTestRunning.value = false
          }
        } catch (e) {
          clearInterval(frameTestPollingTimer)
          frameTestRunning.value = false
        }
      }, 2000)
    }

    async function loadFrameTestResult() {
      try {
        const tid = frameTestTaskId.value
        const apiPath = tid.startsWith('sn_')
          ? `/api/v1/dataset/stnnet-test/result/${tid}`
          : `/api/v1/dataset/frame-test/result/${tid}`
        const res = await axios.get(apiPath)
        frameTestResult.value = res.data
        updateStatsFromFrameTest(res.data)
        await nextTick()
        renderFrameCompareChart()
      } catch (e) { /* ignore */ }
    }

    function updateStatsFromFrameTest(result) {
      const frames = result.frames || []
      if (frames.length === 0) return
      currentStats.avgCount = Math.round((result.total_gt + result.total_pred) / (2 * frames.length))
      currentStats.peakCount = Math.max(...frames.map(f => Math.max(f.gt_count, f.pred_count)))
      currentStats.minCount = Math.min(...frames.map(f => Math.min(f.gt_count, f.pred_count)))
      currentStats.totalFrames = frames.length
      currentStats.elapsed = (result.elapsed || 0) + 's'
      updateCountChartDual(frames)
      updateDensityChart(frames.map(f => ({ count: f.pred_count })))
    }

    function updateCountChartDual(frames) {
      if (!countChartInst) return
      const c = getChartColors()
      countChartInst.setOption({
        grid: { top: 8, right: 20, bottom: 20, left: 50 },
        legend: { data: ['GT', '预测'], textStyle: { color: c.axis, fontSize: 10 }, top: 0, right: 10 },
        xAxis: { type: 'category', data: frames.map(f => f.frame), axisLabel: { color: c.axis, fontSize: 10, interval: Math.max(1, Math.floor(frames.length / 8)) } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 10 } },
        series: [
          {
            name: 'GT', data: frames.map(f => f.gt_count), type: 'line', smooth: true,
            lineStyle: { color: c.green, width: 1.5 },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: c.gradientStartGreen }, { offset: 1, color: c.gradientEndGreen }
            ]) }, symbol: 'none'
          },
          {
            name: '预测', data: frames.map(f => f.pred_count), type: 'line', smooth: true,
            lineStyle: { color: c.orange, width: 1.5 },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: c.gradientStartOrange }, { offset: 1, color: c.gradientEndOrange }
            ]) }, symbol: 'none'
          }
        ]
      })
    }

    function nextFrameTestImage() {
      if (!frameTestResult.value) return
      currentFrameTestIndex.value = (currentFrameTestIndex.value + 1) % frameTestResult.value.frames.length
    }
    function prevFrameTestImage() {
      if (!frameTestResult.value) return
      currentFrameTestIndex.value = (currentFrameTestIndex.value - 1 + frameTestResult.value.frames.length) % frameTestResult.value.frames.length
    }

    const currentFrameTestImage = computed(() => {
      if (!frameTestResult.value || frameTestResult.value.frames.length === 0) return ''
      const frame = frameTestResult.value.frames[currentFrameTestIndex.value]
      // 兼容旧版：如果有 density_maps 就用第一张 density map，否则用旧版 image 字段
      if (frame.density_maps && frame.density_maps.length > 0) {
        return getDensityImageUrl(frame.density_maps[0].filename)
      }
      return `/api/v1/dataset/frame-test/image/${frameTestTaskId.value}/${frame.frame}`
    })

    // 当前帧数据
    const currentFrameData = computed(() => {
      if (!frameTestResult.value || frameTestResult.value.frames.length === 0) return null
      return frameTestResult.value.frames[currentFrameTestIndex.value]
    })

    // 当前帧的独立密度图列表
    const currentFrameMaps = computed(() => {
      const data = currentFrameData.value
      if (!data || !data.density_maps) return []
      return data.density_maps
    })

    function getDensityImageUrl(filename) {
      const tid = frameTestTaskId.value
      if (tid && tid.startsWith('sn_')) {
        return `/api/v1/dataset/stnnet-test/density/${tid}/${currentFrameData.value?.frame || 0}/${filename}`
      }
      if (tid && tid.startsWith('st_')) {
        return `/api/v1/dataset/scene-test/density/${tid}/${currentFrameData.value?.frame || 0}/${filename}`
      }
      return `/api/v1/dataset/frame-test/density/${tid}/${currentFrameData.value?.frame || 0}/${filename}`
    }

    // 按类别分组 density_maps（GD3A 和 STNNet 共用）
    function getMapsByCategory(category) {
      const maps = currentFrameMaps.value
      if (!maps || maps.length === 0) return []
      // 判断是否为 STNNet 结果（有 localization 类型）
      const isSTNNet = maps.some(m => m.type === 'localization' || m.type === 'overlay')
      if (isSTNNet) {
        switch (category) {
          case 'original_global':
            return maps.filter(m => m.type === 'original' || m.type === 'gt_density' || m.type === 'pre_density')
          case 'overlay':
            return maps.filter(m => m.type === 'overlay')
          case 'localization':
            return maps.filter(m => m.type === 'localization')
          default:
            return []
        }
      }
      // GD3A 分组
      switch (category) {
        case 'original_global':
          return maps.filter(m => m.type === 'original' || m.type === 'gt_global' || m.type === 'pre_global')
        case 'prev_in':
          return maps.filter(m => m.type === 'gt_shared_prev' || m.type === 'pre_shared_prev' ||
                                 m.type === 'gt_in' || m.type === 'pre_in')
        case 'next_out':
          return maps.filter(m => m.type === 'gt_shared_next' || m.type === 'pre_shared_next' ||
                                 m.type === 'gt_out' || m.type === 'pre_out')
        default:
          return maps
      }
    }

    async function startAnalyze() {
      if (!uploadedFile.value) return
      analyzing.value = true
      try {
        const res = await axios.post('/api/v1/video/analyze', null, {
          params: { filename: uploadedFile.value, mode: params.mode, model: selectedModel.value }
        })
        currentTaskId.value = res.data.task_id
        await globalLoadTasks()
        startPolling()
      } catch (e) { alert('分析失败: ' + e.message) }
      analyzing.value = false
    }

    function startPolling() {
      if (pollingTimer) clearInterval(pollingTimer)
      pollingTimer = setInterval(async () => {
        await globalLoadTasks()
        if (currentTaskId.value) await loadCurrentTaskDetail()
      }, 2000)
    }

    async function loadCurrentTaskDetail() {
      const tid = currentTaskId.value
      if (!tid) return
      await globalLoadTaskDetail(tid)
      // 同步 UI 状态
      if (currentTask.value && currentTask.value.status === 'done') {
        videoSrc.value = `/api/v1/video/download/${tid}`
        if (currentResult.value) {
          updateStatsFromResult(currentResult.value)
        }
        // 通知全局刷新（其他页面同步）
        globalOnTaskCompleted(tid)
      }
      if (currentTask.value && currentTask.value.status === 'failed') {
        clearInterval(pollingTimer)
      }
    }

    function updateStatsFromResult(result) {
      const frames = result.frames || []
      if (frames.length > 0) {
        const counts = frames.map(f => f.count)
        const avg = Math.round(counts.reduce((a, b) => a + b, 0) / counts.length)
        currentStats.avgCount = avg
        currentStats.peakCount = Math.max(...counts)
        currentStats.minCount = Math.min(...counts)
        currentStats.totalFrames = frames.length
        currentStats.elapsed = (result.total_time || 0) + 's'
        updateCountChart(frames)
        updateDensityChart(frames)
      }
    }

    function updateDensityChart(frames) {
      if (!densityChartInst || frames.length === 0) return
      densityChartInst.resize()
      const c = getChartColors()
      const counts = frames.map(f => f.count).sort((a, b) => a - b)
      const n = counts.length
      const t1 = counts[Math.floor(n / 3)] || 0
      const t2 = counts[Math.floor(n * 2 / 3)] || 0
      const low = counts.filter(c => c <= t1).length
      const mid = counts.filter(c => c > t1 && c <= t2).length
      const high = counts.filter(c => c > t2).length
      densityData.value = [
        { value: low, name: '低密度' },
        { value: mid, name: '中密度' },
        { value: high, name: '高密度' },
      ]
      densityChartInst.setOption({
        title: { show: false },
        tooltip: { trigger: 'item', formatter: '{b}: {c} 帧 ({d}%)' },
        series: [{
          type: 'pie', radius: ['40%', '72%'],
          label: {
            show: true,
            position: 'inside',
            formatter: '{b}\n{d}%',
            color: '#fff',
            fontSize: 11,
            lineHeight: 18,
            fontWeight: 'bold',
          },
          emphasis: {
            label: { fontSize: 14, fontWeight: 'bold' }
          },
          data: [
            { value: low, name: '低密度', itemStyle: { color: c.blue } },
            { value: mid, name: '中密度', itemStyle: { color: c.orange } },
            { value: high, name: '高密度', itemStyle: { color: c.red } },
          ]
        }]
      })
    }

    function selectTask(taskId) {
      globalSelectTask(taskId)
      loadCurrentTaskDetail()
    }

    function statusLabel(s) {
      const map = { pending: '等待', running: '运行中', done: '完成', failed: '失败' }
      return map[s] || s
    }

    function updateCountChart(frames) {
      if (!countChartInst) return
      const c = getChartColors()
      countChartInst.setOption({
        grid: { top: 8, right: 20, bottom: 20, left: 50 },
        xAxis: { type: 'category', data: frames.map(f => f.frame), axisLabel: { color: c.axis, fontSize: 10, interval: Math.max(1, Math.floor(frames.length / 8)) } },
        yAxis: { type: 'value', axisLabel: { color: c.axis, fontSize: 10 } },
        series: [{
          data: frames.map(f => f.count), type: 'line', smooth: true,
          lineStyle: { color: c.blue, width: 1.5 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: c.gradientStart }, { offset: 1, color: c.gradientEnd }
          ]) }, symbol: 'none'
        }]
      })
    }

    function renderFrameCompareChart() {
      if (!frameCompareChart.value || !frameTestResult.value) return
      const c = getChartColors()
      const frames = frameTestResult.value.frames || []
      if (frames.length === 0) return
      if (frameCompareChartInst) frameCompareChartInst.dispose()
      frameCompareChartInst = echarts.init(frameCompareChart.value, getEchartsTheme())
      const labels = frames.map(f => f.frame)
      const gtData = frames.map(f => f.gt_count)
      const predData = frames.map(f => f.pred_count)
      frameCompareChartInst.setOption({
        tooltip: { trigger: 'axis' },
        legend: {
          data: ['GT 真实', 'Pred 预测'],
          textStyle: { color: c.axis, fontSize: 10 },
          top: 0,
        },
        grid: { top: 28, right: 16, bottom: 24, left: 48 },
        xAxis: {
          type: 'category', data: labels,
          axisLabel: { color: c.axis, fontSize: 9, interval: Math.max(0, Math.floor(labels.length / 10) - 1) || 0 },
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: c.axis, fontSize: 9 },
        },
        series: [
          {
            name: 'GT 真实', type: 'bar', data: gtData,
            itemStyle: { color: c.green, borderRadius: [2, 2, 0, 0] },
            barMaxWidth: Math.max(6, Math.min(30, 600 / labels.length)),
          },
          {
            name: 'Pred 预测', type: 'bar', data: predData,
            itemStyle: { color: c.orange, borderRadius: [2, 2, 0, 0] },
            barMaxWidth: Math.max(6, Math.min(30, 600 / labels.length)),
          },
        ],
      })
    }
    let frameCompareChartInst = null

    function initCharts() {
      if (densityChart.value) {
        if (densityChartInst) densityChartInst.dispose()
        densityChartInst = echarts.init(densityChart.value, getEchartsTheme())
        const c = getChartColors()
        densityChartInst.setOption({
          title: { text: '等待分析完成', left: 'center', top: 'center', textStyle: { color: c.axis, fontSize: 12, fontWeight: 'normal' } },
          series: [{
            type: 'pie', radius: ['45%', '72%'],
            label: { show: false },
            data: [
              { value: 1, name: '', itemStyle: { color: c.gradientStart } },
            ],
            silent: true,
          }]
        })
      }
      if (countChart.value) {
        if (countChartInst) countChartInst.dispose()
        countChartInst = echarts.init(countChart.value, getEchartsTheme())
      }
    }

    function toggleVideoPlay() {
      const v = videoPlayer.value
      if (!v) return
      if (v.paused) { v.play(); videoPlaying.value = true }
      else { v.pause(); videoPlaying.value = false }
    }

    function toggleVideoFullscreen() {
      const wrapper = videoWrapper.value
      if (!wrapper) return
      if (!videoFullscreen.value) {
        // 进入全屏
        if (wrapper.requestFullscreen) {
          wrapper.requestFullscreen().catch(() => {})
        } else if (wrapper.webkitRequestFullscreen) {
          wrapper.webkitRequestFullscreen()
        }
      } else {
        // 退出全屏
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => {})
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen()
        }
      }
    }

    function onFullscreenChange() {
      videoFullscreen.value = !!document.fullscreenElement
    }

    function resizeCharts() {
      densityChartInst?.resize()
      countChartInst?.resize()
      frameCompareChartInst?.resize()
    }

    // 监听全局 currentTask 变化，同步到 UI
    watch(currentTask, (newVal) => {
      if (newVal && newVal.status === 'done') {
        const tid = currentTaskId.value
        if (tid) {
          videoSrc.value = `/api/v1/video/download/${tid}`
        }
      }
    })

    // 监听全局 currentResult 变化
    watch(currentResult, (newVal) => {
      if (newVal) {
        updateStatsFromResult(newVal)
      }
    })

    function onThemeChange() {
      initCharts()
      resizeCharts()
      if (currentResult.value) {
        const frames = currentResult.value.frames || []
        if (frames.length) updateCountChart(frames)
      }
      // 重新渲染图片模式下的帧对比图表
      if (frameTestResult.value) {
        renderFrameCompareChart()
      }
      if (allFrames.value && allFrames.value.length) {
        updateCountChartDual(allFrames.value)
        updateDensityChart(allFrames.value)
      }
    }

    onMounted(() => {
      setTimeout(() => {
        initCharts()
        resizeCharts()
      }, 100)
      window.addEventListener('resize', resizeCharts)
      window.addEventListener('themechange', onThemeChange)
      document.addEventListener('fullscreenchange', onFullscreenChange)
      document.addEventListener('webkitfullscreenchange', onFullscreenChange)
      observeResize()
    })

    onActivated(() => {
      // keep-alive 恢复时也重新初始化
      setTimeout(() => {
        initCharts()
        resizeCharts()
        if (currentResult.value) {
          const frames = currentResult.value.frames || []
          if (frames.length) updateCountChart(frames)
        }
        if (frameTestResult.value) {
          renderFrameCompareChart()
        }
      }, 150)
    })

    onUnmounted(() => {
      if (pollingTimer) clearInterval(pollingTimer)
      if (frameTestPollingTimer) clearInterval(frameTestPollingTimer)
      densityChartInst?.dispose()
      countChartInst?.dispose()
      frameCompareChartInst?.dispose()
      window.removeEventListener('resize', resizeCharts)
      window.removeEventListener('themechange', onThemeChange)
      document.removeEventListener('fullscreenchange', onFullscreenChange)
      document.removeEventListener('webkitfullscreenchange', onFullscreenChange)
      if (resizeObserver) resizeObserver.disconnect()
    })

    return {
      fileInput, frameFileInput, labelFileInput, videoPlayer, videoWrapper, densityChart, countChart, frameCompareChart,
      mode, uploadedFile, uploadedSize, uploading, uploadProgress, analyzing,
      frameFiles, labelFile, frameUploading, frameTestRunning, frameTestTask, frameTestResult,
      frameTestTaskId, currentFrameTestIndex, currentFrameTestImage, frameTestModel,
      currentTaskId, currentTask, videoSrc, videoFullscreen, videoPlaying, tasks, params, currentStats, selectedModel, densityData, chartColors,
      triggerUpload, handleFile, handleDrop, startAnalyze, selectTask: globalSelectTask, statusLabel,
      triggerFrameUpload, handleFrameFile, handleFrameDrop,
      triggerLabelUpload, handleLabelFile, handleLabelDrop,
      startFrameTest, startSceneTest, startSTNNetTest, nextFrameTestImage, prevFrameTestImage,
      toggleVideoPlay, toggleVideoFullscreen, deleteTask,
      currentFrameData, currentFrameMaps, getDensityImageUrl, getMapsByCategory,
    }
  }
}
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; height: 100%; }
.main-content { display: flex; flex: 1; overflow: hidden; }
.left-panel { width: 320px; flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; padding: 10px; overflow-y: auto; }
.upload-panel { flex-shrink: 0; }
.param-panel { flex-shrink: 0; }
.task-panel { flex-shrink: 0; min-height: 240px; display: flex; flex-direction: column; overflow: hidden; }
.task-panel .task-list { flex: 1; overflow-y: auto; }

.param-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.param-row label { font-size: 11px; color: var(--text-dim); white-space: nowrap; min-width: 55px; }
.param-row input[type="range"] { flex: 1; accent-color: var(--accent); }
.param-select { width: 100%; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-glow); padding: 6px 10px; border-radius: 4px; font-size: 12px; }

.center-panel { flex: 1; padding: 10px 0 10px 0; display: flex; flex-direction: column; overflow: hidden; }
.video-panel { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.video-container { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 280px; background: rgba(0,0,0,0.35); border-radius: 6px; overflow: hidden; position: relative; padding: 10px; }
.video-wrapper {
  position: relative; width: 100%; max-width: 100%;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px;
  cursor: default;
  background: #000;
}
/* 全屏时覆盖样式 */
.video-wrapper:fullscreen {
  width: 100vw; height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #000;
}
.video-wrapper:-webkit-full-screen {
  width: 100vw; height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #000;
}
.dashboard-video {
  width: 100%; max-height: 58vh; border-radius: 6px;
  display: block; outline: none;
}
/* 全屏时视频填满 */
.video-wrapper:fullscreen .dashboard-video {
  max-height: 100vh; width: auto; max-width: 100vw;
  border-radius: 0;
}
.video-wrapper:-webkit-full-screen .dashboard-video {
  max-height: 100vh; width: auto; max-width: 100vw;
  border-radius: 0;
}
/* 视频控制栏 - 绝对定位浮在右下角，始终可见 */
.video-controls-bar {
  position: absolute;
  bottom: 6px;
  right: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 5px 10px;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  z-index: 50;
  backdrop-filter: blur(4px);
}
.video-ctrl-btn {
  width: 28px; height: 28px; border-radius: 5px;
  background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15);
  color: #fff; font-size: 14px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s; line-height: 1; padding: 0;
}
.video-ctrl-btn:hover { background: rgba(77,166,255,0.4); border-color: var(--accent); box-shadow: 0 0 10px rgba(77,166,255,0.3); }
.video-ctrl-btn:active { transform: scale(0.93); }
.video-placeholder { text-align: center; color: var(--text-dim); }
.video-info { margin-top: 8px; }

/* ===== 帧测试结果展示 ===== */
.frame-test-result {
  width: 100%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.frame-main-images {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.frame-main-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  overflow: hidden;
}
.frame-main-img {
  width: 100%;
  max-height: 200px;
  object-fit: contain;
  background: #000;
}
.frame-test-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  flex-wrap: wrap;
}
.frame-sep {
  color: var(--border-subtle);
  font-size: 14px;
  margin: 0 2px;
}
.frame-test-btn {
  width: 30px; height: 30px;
  border-radius: 50%;
  border: 1px solid rgba(80, 160, 255, 0.3);
  background: rgba(12, 40, 90, 0.4);
  color: var(--accent);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}
.frame-test-btn:hover {
  background: rgba(20, 60, 140, 0.6);
  border-color: rgba(80, 160, 255, 0.6);
}
.frame-test-info {
  font-size: 12px;
  color: var(--text-dim);
  letter-spacing: 1px;
  min-width: 70px;
  text-align: center;
}
.frame-badge {
  font-family: Rajdhani, monospace;
  font-size: 12px;
  color: var(--accent);
  background: rgba(20, 60, 140, 0.3);
  padding: 2px 10px;
  border-radius: 3px;
  letter-spacing: 0.5px;
}
.frame-stat {
  font-family: Rajdhani, monospace;
  font-size: 13px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 3px;
}
.frame-stat.gt { color: var(--success); background: rgba(60,232,133,0.1); }
.frame-stat.pred { color: var(--warning); background: rgba(255,160,64,0.1); }
.frame-stat.ae { color: var(--danger); background: rgba(255,80,120,0.1); }

/* 底部密度图容器 */
.density-groups-bottom {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  overflow-y: auto;
  max-height: 40vh;
  padding: 4px;
}
.density-img-bottom {
  width: 100%;
  max-height: 160px;
  object-fit: contain;
  background: #000;
}
.density-img-bottom-wide {
  width: 100%;
  max-height: 200px;
  object-fit: contain;
  background: #000;
}

/* ===== 密度图分组布局 ===== */
.density-group {
  background: var(--bg-card);
  border: 1px solid rgba(30, 70, 180, 0.15);
  border-radius: 8px;
  padding: 8px 10px;
  flex-shrink: 0;
}
.group-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 6px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.group-maps {
  display: grid;
  gap: 8px;
}
.group-maps.cols-1 {
  grid-template-columns: 1fr;
}
.group-maps.cols-2 {
  grid-template-columns: repeat(2, 1fr);
}
.group-maps.cols-3 {
  grid-template-columns: repeat(3, 1fr);
}
.group-maps.cols-4 {
  grid-template-columns: repeat(4, 1fr);
}

.density-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  overflow: hidden;
  transition: all 0.2s;
  position: relative;
}
.density-card:hover {
  border-color: rgba(60, 130, 240, 0.45);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(40, 100, 220, 0.15);
}

.density-card-tag {
  font-size: 9px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 2px;
  letter-spacing: 0.3px;
  text-align: center;
}
.tag-gt { background: rgba(60,232,133,0.2); color: var(--success); border: 1px solid rgba(60,232,133,0.35); }
.tag-pred { background: rgba(255,160,64,0.2); color: var(--warning); border: 1px solid rgba(255,160,64,0.35); }
.tag-orig { background: rgba(160,170,200,0.2); color: #a0aac8; border: 1px solid rgba(160,170,200,0.35); }

.density-card-label {
  width: 100%;
  padding: 4px 6px;
  font-size: 10px;
  color: var(--text-dim);
  text-align: center;
  background: var(--bg-card);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.density-card-count {
  position: absolute;
  top: 4px;
  right: 4px;
  font-family: Rajdhani, monospace;
  font-size: 10px;
  font-weight: 600;
  color: var(--warning);
  background: rgba(0,0,0,0.6);
  padding: 1px 5px;
  border-radius: 2px;
  z-index: 2;
}

/* STNNet 定位对比 */
.localization-group {
  border-color: rgba(60, 232, 133, 0.25) !important;
  background: rgba(4, 24, 12, 0.5) !important;
}
.density-card-loc-metrics {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 4px 8px;
  font-family: Rajdhani, monospace;
  font-size: 11px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.4);
}

/* 旧的 density-grid 保留兼容 */
.density-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  width: 100%;
  max-height: 55vh;
  overflow-y: auto;
  padding: 4px;
}
.density-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.density-item:hover {
  border-color: rgba(60, 130, 240, 0.5);
}
.density-label {
  width: 100%;
  padding: 4px 8px;
  font-size: 10px;
  color: var(--text-dim);
  background: var(--bg-card);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.density-img {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: contain;
  background: #000;
}

.img-result-stats {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px;
}
.img-result-stats .stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 11px;
  color: var(--text-dim);
  border-bottom: 1px solid rgba(30, 80, 180, 0.08);
}
.img-result-stats .stat-row:last-child { border-bottom: none; }

.right-panel { width: 240px; flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; padding: 10px; overflow-y: auto; }
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 5px; padding: 12px 10px; text-align: center; }
.bottom-panel { padding: 0 10px 10px; flex-shrink: 0; }
.chart-panel { width: 100%; }

/* ===== 任务列表 ===== */
.task-list { overflow-y: auto; flex: 1; }
.task-count {
  font-family: Rajdhani, monospace;
  font-size: 10px;
  color: var(--accent);
  background: rgba(92, 184, 255, 0.12);
  padding: 2px 7px;
  border-radius: 10px;
  margin-left: 8px;
}
.task-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}
.task-id {
  font-family: Rajdhani, monospace;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}
.task-msg {
  font-size: 10px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}
.task-status-tag {
  font-size: 9px;
  padding: 2px 7px;
  border-radius: 3px;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}
.tag-pending { background: rgba(108, 154, 255, 0.15); color: var(--accent); }
.tag-running { background: rgba(92, 184, 255, 0.18); color: var(--accent); }
.tag-done    { background: rgba(60, 232, 133, 0.15); color: var(--success); }
.tag-failed  { background: rgba(255, 80, 120, 0.15); color: var(--danger); }
.task-empty { color: var(--text-dim); font-size: 12px; text-align: center; padding: 24px 0; }

.mode-tabs { display: flex; gap: 4px; }
.mode-tab { flex: 1; padding: 8px 0; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 4px; color: var(--text-dim); font-size: 12px; cursor: pointer; transition: all 0.2s; }
.mode-tab.active { background: var(--border-subtle); border-color: rgba(50, 120, 240, 0.4); color: var(--accent); font-weight: 600; }

.img-result-stats { background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 5px; padding: 8px 10px; }
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; font-size: 11px; color: var(--text-dim); }

.upload-zone { border: 1px dashed var(--border-subtle); border-radius: 6px; padding: 18px 16px; text-align: center; cursor: pointer; transition: all 0.2s; color: var(--text-dim); font-size: 12px; }
.upload-zone:hover { border-color: rgba(60, 130, 240, 0.45); background: rgba(20, 60, 160, 0.06); }

</style>
