import { createRouter, createWebHistory } from 'vue-router'
import SplashPage from './pages/SplashPage.vue'
import TransitionPage from './pages/TransitionPage.vue'
import HomeNew from './pages/HomeNew.vue'
import Overview from './pages/Overview.vue'
import Dashboard from './pages/Dashboard.vue'
import HeatmapView from './pages/HeatmapView.vue'
import SpatialAnalysis from './pages/SpatialAnalysis.vue'
import TrajectoryView from './pages/TrajectoryView.vue'
import ComparisonView from './pages/ComparisonView.vue'
import TemporalAnalysis from './pages/TemporalAnalysis.vue'
import ZoomView from './pages/ZoomView.vue'

const routes = [
  { path: '/', name: 'Splash', component: SplashPage, meta: { title: 'DroneCrowd', fullscreen: true, hideNav: true } },
  { path: '/transition', name: 'Transition', component: TransitionPage, meta: { title: 'DroneCrowd', fullscreen: true, hideNav: true } },
  { path: '/home', name: 'Home', component: HomeNew, meta: { title: '首页', fullscreen: true, hideNav: true } },
  { path: '/overview', name: 'Overview', component: Overview, meta: { title: '总览', icon: '⊡' } },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard, meta: { title: '仪表盘', icon: '⊿' } },
  { path: '/zoom', name: 'ZoomView', component: ZoomView, meta: { title: '放大对比', icon: '⊕' } },
  { path: '/heatmap', name: 'HeatmapView', component: HeatmapView, meta: { title: '热力图', icon: '⊚' } },
  { path: '/trajectory', name: 'TrajectoryView', component: TrajectoryView, meta: { title: '轨迹追踪', icon: '⟐' } },
  { path: '/spatial', name: 'SpatialAnalysis', component: SpatialAnalysis, meta: { title: '空间分析', icon: '⬡' } },
  { path: '/temporal', name: 'TemporalAnalysis', component: TemporalAnalysis, meta: { title: '时序分析', icon: '↻' } },
  { path: '/compare', name: 'ComparisonView', component: ComparisonView, meta: { title: '对比分析', icon: '⇔' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
export { routes }
