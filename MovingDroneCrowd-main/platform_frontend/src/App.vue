<template>
  <!-- 首页：全屏模式，不显示 header 和 nav -->
  <div v-if="isFullscreen" class="app-fullscreen">
    <router-view v-slot="{ Component, route }">
      <component :is="Component" :key="route.path" />
    </router-view>
  </div>

  <!-- 其他页面：标准布局（header + nav + content） -->
  <div v-else class="app-shell">
    <!-- 顶部标题栏 -->
    <header class="header">
      <div class="header-left">
        <router-link to="/" class="logo-link">
          <svg class="logo-drone" viewBox="0 0 40 40" fill="none">
            <g class="ld-rotor1"><ellipse cx="10" cy="10" rx="6" ry="2" fill="none" stroke="currentColor" stroke-width="1.3" opacity="0.7"/></g>
            <g class="ld-rotor2"><ellipse cx="30" cy="10" rx="6" ry="2" fill="none" stroke="currentColor" stroke-width="1.3" opacity="0.7"/></g>
            <g class="ld-rotor3"><ellipse cx="10" cy="30" rx="6" ry="2" fill="none" stroke="currentColor" stroke-width="1.3" opacity="0.7"/></g>
            <g class="ld-rotor4"><ellipse cx="30" cy="30" rx="6" ry="2" fill="none" stroke="currentColor" stroke-width="1.3" opacity="0.7"/></g>
            <line x1="13" y1="13" x2="20" y2="20" stroke="currentColor" stroke-width="0.8" opacity="0.5"/>
            <line x1="27" y1="13" x2="20" y2="20" stroke="currentColor" stroke-width="0.8" opacity="0.5"/>
            <line x1="13" y1="27" x2="20" y2="20" stroke="currentColor" stroke-width="0.8" opacity="0.5"/>
            <line x1="27" y1="27" x2="20" y2="20" stroke="currentColor" stroke-width="0.8" opacity="0.5"/>
            <circle cx="20" cy="20" r="4" fill="none" stroke="currentColor" stroke-width="1.3"/>
            <circle cx="20" cy="20" r="1.5" fill="currentColor" opacity="0.9">
              <animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite"/>
            </circle>
          </svg>
        </router-link>
        <div class="header-text">
          <h1>DroneCrowd<span class="h1-sub"> · 无人机人群智能感知平台</span></h1>
          <div class="subtitle">Multi-Scale Crowd Analysis &amp; Visualization</div>
        </div>
      </div>
      <div class="header-right">
        <!-- ↓ 全局下载 -->
        <div class="header-download" v-if="doneTasks.length > 0">
          <button class="hd-btn" @click="showDownload = !showDownload" title="下载中心">
            ↓
            <span class="hd-badge">{{ doneTasks.length }}</span>
          </button>
          <transition name="fade">
            <div v-if="showDownload" class="hd-dropdown" @mouseleave="showDownload = false">
              <div class="hd-dropdown-title">下载中心</div>
              <div
                v-for="t in doneTasks.slice(0, 6)"
                :key="t.task_id"
                class="hd-task-group"
              >
                <div class="hd-task-name">{{ t.filename || t.task_id }}</div>
                <div class="hd-links">
                  <a :href="'/api/v1/video/download/' + t.task_id" class="hd-link">⬡ 视频</a>
                  <a :href="'/api/v1/video/export/csv/' + t.task_id" class="hd-link">≡ CSV</a>
                  <a :href="'/api/v1/video/export/peaks/' + t.task_id" class="hd-link">📍 坐标</a>
                  <a :href="'/api/v1/video/export/json/' + t.task_id" class="hd-link">⊡ JSON</a>
                  <a :href="'/api/v1/video/export/pdf/' + t.task_id" class="hd-link">📄 报告</a>
                </div>
              </div>
              <div v-if="doneTasks.length > 6" class="hd-more">还有 {{ doneTasks.length - 6 }} 个任务...</div>
            </div>
          </transition>
        </div>

        <div class="theme-picker" :title="'当前: ' + themeNames[theme]">
          <span class="theme-current" @click="toggleThemePicker">{{ themeIcons[theme] }}</span>
          <transition name="fade">
            <div v-if="showThemePicker" class="theme-dropdown" @mouseleave="showThemePicker = false">
              <div
                v-for="t in THEME_LIST"
                :key="t.key"
                class="theme-option"
                :class="{ active: theme === t.key }"
                @click="selectTheme(t.key)"
              >
                <span class="theme-opt-icon">{{ t.icon }}</span>
                <span class="theme-opt-name">{{ t.name }}</span>
                <span v-if="theme === t.key" class="theme-opt-check">✓</span>
              </div>
            </div>
          </transition>
        </div>
        <span class="system-status">
          <span class="dot online"></span>
          系统运行中
        </span>
      </div>
    </header>

    <!-- 导航栏 -->
    <nav class="nav-bar">
      <router-link
        v-for="r in navRoutes"
        :key="r.path"
        :to="r.path"
        class="nav-item"
        active-class="nav-active"
      >
        <span class="nav-icon">{{ r.meta.icon }}</span>
        <span class="nav-label">{{ r.meta.title }}</span>
      </router-link>
    </nav>

    <!-- 页面内容：TrajectoryView 不做缓存，避免 echarts 容器高度问题 -->
    <main class="page-content">
      <router-view v-slot="{ Component, route }">
        <keep-alive :exclude="['TrajectoryView']">
          <component :is="Component" :key="route.path" />
        </keep-alive>
      </router-view>
    </main>
  </div>

  <!-- AI 智能讲解员 -->
  <VirtualGuideAssistant />
</template>

<script>
import { ref, computed, provide, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { routes } from './router'
import { setEchartsTheme } from './echartsTheme.js'
import VirtualGuideAssistant from './components/VirtualGuideAssistant.vue'

export default {
  name: 'AppShell',
  components: { VirtualGuideAssistant },
  setup() {
    const route = useRoute()

    // 过滤出非全屏的路由（用于导航栏）
    const navRoutes = routes.filter(r => !r.meta?.fullscreen)

    // 判断当前路由是否为全屏模式
    const isFullscreen = computed(() => !!route.meta?.fullscreen)

    // ===== 主题选择器（5 套主题） =====
    const THEME_LIST = [
      { key: 'dark', icon: '🌌', name: '深空科技' },
      { key: 'city', icon: '🌃', name: '城市环境' },
    ]
    const themeIcons = Object.fromEntries(THEME_LIST.map(t => [t.key, t.icon]))
    const themeNames = Object.fromEntries(THEME_LIST.map(t => [t.key, t.name]))
    const THEME_KEYS = THEME_LIST.map(t => t.key)

    const theme = ref('dark')
    const showThemePicker = ref(false)
    const showDownload = ref(false)

    // 下载中心：已完成任务列表
    const doneTasks = computed(() => tasks.value.filter(t => t.status === 'done'))
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme && THEME_KEYS.includes(savedTheme)) {
      theme.value = savedTheme === 'light' ? 'city' : savedTheme
    }
    document.documentElement.setAttribute('data-theme', theme.value)
    setEchartsTheme(theme.value)

    function toggleThemePicker() {
      showThemePicker.value = !showThemePicker.value
    }
    function selectTheme(key) {
      theme.value = key
      showThemePicker.value = false
      document.documentElement.setAttribute('data-theme', theme.value)
      localStorage.setItem('theme', theme.value)
      setEchartsTheme(theme.value)
      window.dispatchEvent(new Event('themechange'))
    }

    // ===== 全局共享状态（所有子页面通过 inject 读取） =====
    const tasks = ref([])
    const currentTaskId = ref('')
    const currentTask = ref(null)
    const currentResult = ref(null)

    let refreshTimer = null

    async function loadTasks() {
      try {
        const res = await axios.get('/api/v1/video/list')
        tasks.value = res.data
      } catch (e) { /* ignore */ }
    }

    async function loadTaskDetail(taskId) {
      try {
        const res = await axios.get(`/api/v1/video/task/${taskId}`)
        currentTask.value = res.data
        if (res.data.status === 'done') {
          try {
            const resultRes = await axios.get(`/api/v1/video/result/${taskId}`)
            currentResult.value = resultRes.data
          } catch (e) { currentResult.value = null }
        }
      } catch (e) { /* ignore */ }
    }

    function selectTask(taskId) {
      currentTaskId.value = taskId
      loadTaskDetail(taskId)
    }

    function onTaskCompleted(taskId) {
      loadTasks()
      if (currentTaskId.value === taskId) {
        loadTaskDetail(taskId)
      }
    }

    async function deleteTask(taskId) {
      try {
        await axios.delete(`/api/v1/video/task/${taskId}`)
        if (currentTaskId.value === taskId) {
          currentTaskId.value = ''
          currentTask.value = null
          currentResult.value = null
        }
        await loadTasks()
      } catch (e) {
        console.error('删除任务失败', e)
      }
    }

    provide('globalTasks', tasks)
    provide('globalCurrentTaskId', currentTaskId)
    provide('globalCurrentTask', currentTask)
    provide('globalCurrentResult', currentResult)
    provide('selectTask', selectTask)
    provide('loadTasks', loadTasks)
    provide('loadTaskDetail', loadTaskDetail)
    provide('onTaskCompleted', onTaskCompleted)
    provide('deleteTask', deleteTask)

    function startAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer)
      refreshTimer = setInterval(() => { loadTasks() }, 5000)
    }

    onMounted(() => {
      loadTasks()
      startAutoRefresh()
    })
    onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })

    return { navRoutes, isFullscreen, theme, showThemePicker, THEME_LIST, themeIcons, themeNames, toggleThemePicker, selectTheme, showDownload, doneTasks }
  }
}
</script>

<style scoped>
/* ===== 全屏模式（首页） ===== */
.app-fullscreen {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-deep);
}

/* ===== 标准布局 ===== */
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-deep);
  background-image:
    radial-gradient(ellipse at 15% 50%, rgba(20, 60, 160, 0.12) 0%, transparent 55%),
    radial-gradient(ellipse at 85% 25%, rgba(30, 80, 200, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, rgba(10, 40, 100, 0.06) 0%, transparent 45%);
  overflow: hidden;
}
[data-theme="city"] .app-shell {
  background-image:
    radial-gradient(ellipse at 15% 50%, rgba(117, 169, 199, 0.04) 0%, transparent 55%),
    radial-gradient(ellipse at 85% 25%, rgba(85, 194, 195, 0.03) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, rgba(139, 143, 245, 0.03) 0%, transparent 45%);
}

/* ===== 顶部 ===== */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 24px;
  background: rgba(2, 11, 24, 0.97);
  border-bottom: 1px solid rgba(30, 80, 180, 0.18);
  flex-shrink: 0;
  z-index: 10;
}
[data-theme="city"] .header {
  background: rgba(255, 255, 255, 0.97);
  border-bottom: 1px solid #dce3e9;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.logo-link {
  text-decoration: none;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.logo-drone {
  width: 40px; height: 40px;
  color: var(--accent);
  filter: drop-shadow(0 0 10px rgba(77,166,255,0.6)) drop-shadow(0 0 20px rgba(77,166,255,0.3));
  transition: all 0.3s;
}
[data-theme="city"] .logo-drone {
  filter: drop-shadow(0 0 6px rgba(91,157,249,0.3)) drop-shadow(0 0 12px rgba(91,157,249,0.15));
}
.logo-drone:hover {
  filter: drop-shadow(0 0 16px rgba(77,166,255,0.8)) drop-shadow(0 0 32px rgba(77,166,255,0.5));
  transform: scale(1.08);
}
[data-theme="city"] .logo-drone:hover {
  filter: drop-shadow(0 0 10px rgba(91,157,249,0.5)) drop-shadow(0 0 18px rgba(91,157,249,0.25));
}
/* Rotor spin */
.ld-rotor1 { animation: ldr-spin 0.4s linear infinite; transform-origin: 10px 10px; }
.ld-rotor2 { animation: ldr-spin 0.45s linear infinite reverse; transform-origin: 30px 10px; }
.ld-rotor3 { animation: ldr-spin 0.42s linear infinite reverse; transform-origin: 10px 30px; }
.ld-rotor4 { animation: ldr-spin 0.38s linear infinite; transform-origin: 30px 30px; }
@keyframes ldr-spin { to { transform: rotate(360deg); } }

.header-text { display: flex; flex-direction: column; gap: 2px; }
.header-left h1 {
  font-size: 16px; font-weight: 700; margin: 0;
  letter-spacing: 0.04em;
  background: linear-gradient(135deg, #e8f0ff 0%, #7ab8f0 50%, #e8f0ff 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: h1-shimmer 4s ease-in-out infinite;
  text-shadow: none;
  font-family: Rajdhani, sans-serif;
}
@keyframes h1-shimmer {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
.h1-sub {
  font-weight: 400; font-size: 14px;
  background: linear-gradient(90deg, #7ab8f0, #a0c8e8);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  font-family: system-ui, -apple-system, sans-serif;
  animation: none;
}
[data-theme="city"] .header-left h1 {
  background: linear-gradient(135deg, #1f2937 0%, #75A9C7 50%, #3F4749 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
[data-theme="city"] .h1-sub {
  background: linear-gradient(90deg, #3b7de9, #55c2c3);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.subtitle {
  font-size: 10px; color: rgba(255,255,255,0.3);
  letter-spacing: 0.08em;
  font-family: Rajdhani, sans-serif;
}
[data-theme="city"] .subtitle { color: rgba(0,0,0,0.3); }
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 下载中心按钮 */
.header-download { position: relative; }
.hd-btn {
  width: 34px; height: 34px; border-radius: 8px;
  border: 1px solid #f59e0b; background: rgba(245,158,11,0.15);
  color: #fbbf24; cursor: pointer; font-size: 16px; position: relative;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.25s ease; line-height: 1;
  box-shadow: 0 0 10px rgba(245,158,11,0.2);
}
.hd-btn:hover { background: rgba(245,158,11,0.3); border-color: #fbbf24; box-shadow: 0 0 18px rgba(245,158,11,0.45); }
.hd-badge {
  position: absolute; top: -5px; right: -5px;
  min-width: 16px; height: 16px; line-height: 16px;
  border-radius: 8px; background: #f87171; color: #fff;
  font-size: 9px; font-weight: 700; text-align: center; padding: 0 4px;
}
.hd-dropdown {
  position: absolute; top: 42px; right: 0; width: 280px; max-height: 400px;
  overflow-y: auto; padding: 8px; background: var(--bg-panel);
  border: 1px solid var(--border-glow); border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.45); z-index: 1100;
  backdrop-filter: blur(12px);
}
.hd-dropdown-title { font-size: 11px; font-weight: 600; color: var(--text-secondary); padding: 4px 8px 8px; letter-spacing: 1px; }
.hd-task-group { margin-bottom: 6px; padding: 6px 8px; border-radius: 6px; background: var(--bg-card); }
.hd-task-name { font-size: 10px; color: var(--text-dim); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hd-links { display: flex; flex-wrap: wrap; gap: 4px; }
.hd-link {
  padding: 2px 8px; border-radius: 10px; font-size: 10px;
  background: var(--bg-hover); color: var(--text-primary);
  text-decoration: none; transition: all 0.15s; white-space: nowrap;
}
.hd-link:hover { background: var(--accent); color: #fff; }
.hd-more { font-size: 10px; color: var(--text-dim); text-align: center; padding: 4px; }

.theme-picker {
  position: relative;
}
.theme-current {
  width: 34px; height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-card);
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s ease;
  line-height: 1;
}
.theme-current:hover {
  background: var(--bg-hover);
  border-color: var(--accent);
  box-shadow: 0 0 12px var(--accent-glow);
}
.theme-dropdown {
  position: absolute;
  top: 42px;
  right: 0;
  min-width: 160px;
  padding: 6px;
  background: var(--bg-panel);
  border: 1px solid var(--border-glow);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.45);
  z-index: 1100;
  backdrop-filter: blur(12px);
}
.theme-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  transition: all 0.15s ease;
}
.theme-option:hover {
  background: var(--bg-hover);
}
.theme-option.active {
  background: var(--bg-card);
  border: 1px solid var(--border-bright);
}
.theme-opt-icon { font-size: 16px; }
.theme-opt-name { flex: 1; }
.theme-opt-check { color: var(--accent); font-weight: 700; font-size: 14px; }

.fade-enter-active { animation: fadeIn 0.15s ease-out; }
.fade-leave-active { animation: fadeOut 0.1s ease-in; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeOut { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-4px); } }
.system-status {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  display: inline-block;
}
.dot.online {
  background: var(--success);
  box-shadow: 0 0 8px rgba(60, 232, 133, 0.5);
}

/* ===== 导航栏 ===== */
.nav-bar {
  display: flex;
  background: rgba(4, 16, 34, 0.95);
  border-bottom: 1px solid rgba(30, 80, 180, 0.12);
  flex-shrink: 0;
  padding: 0 20px;
}
[data-theme="city"] .nav-bar {
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid #dce3e9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  font-size: 13px;
  color: var(--text-dim);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  transition: all 0.25s;
  cursor: pointer;
}
.nav-item:hover {
  color: #88b8e8;
  background: rgba(20, 60, 160, 0.08);
}
[data-theme="city"] .nav-item:hover {
  color: #5b9df9;
  background: rgba(91, 157, 249, 0.06);
}
.nav-active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  background: rgba(20, 60, 160, 0.1);
}
[data-theme="city"] .nav-active {
  background: rgba(91, 157, 249, 0.08);
}
.nav-icon {
  font-size: 18px;
  filter: drop-shadow(0 0 4px rgba(77,166,255,0.3));
  transition: all 0.3s;
}
.nav-item:hover .nav-icon {
  filter: drop-shadow(0 0 10px rgba(77,166,255,0.6));
  transform: scale(1.15);
}
.nav-active .nav-icon {
  filter: drop-shadow(0 0 12px rgba(77,166,255,0.7));
}
.nav-label {
  letter-spacing: 1px;
  font-family: Rajdhani, sans-serif;
  font-weight: 500;
  font-size: 13px;
}

/* ===== 页面内容 ===== */
.page-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ===== 滚动条 ===== */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(30, 100, 255, 0.25); border-radius: 2px; }
[data-theme="city"] ::-webkit-scrollbar-thumb { background: rgba(117, 169, 199, 0.2); }
</style>