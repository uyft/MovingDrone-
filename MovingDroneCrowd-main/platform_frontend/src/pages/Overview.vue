<template>
  <div class="overview">
    <!-- 全局粒子特效背景 -->
    <div class="global-particles">
      <!-- 浮动光球 -->
      <div class="glow-orb orb-1"></div>
      <div class="glow-orb orb-2"></div>
      <div class="glow-orb orb-3"></div>
      <div class="glow-orb orb-4"></div>
      <!-- 上升粒子 -->
      <span v-for="i in 40" :key="'p'+i" class="float-particle"
            :style="{ left: (i*2.7)%100+'%', animationDelay: (i*0.35)%8+'s', animationDuration: (6+i%7)+'s', width: (1+i%3)+'px', height: (1+i%3)+'px' }"></span>
      <!-- 水平扫描线 -->
      <div class="scan-beam"></div>
    </div>

    <!-- ====== Hero: 可视化优先，图片展示为主 ====== -->
    <section class="ov-hero">
      <!-- 微妙背景粒子 -->
      <div class="hero-bg-particles">
        <span v-for="i in 20" :key="i" class="bg-dot"
              :style="{ left: Math.random()*100+'%', top: Math.random()*100+'%',
                       animationDelay: Math.random()*3+'s', opacity: 0.15+Math.random()*0.2 }"></span>
      </div>

      <div class="hero-container">
        <!-- 左侧：大图展示 - 浏览器窗口风格 -->
        <div class="hero-mockup">
          <div class="mockup-frame">
            <div class="mockup-bar">
              <span class="mockup-dot red"></span>
              <span class="mockup-dot yellow"></span>
              <span class="mockup-dot green"></span>
              <span class="mockup-title">MDC++ Dataset Preview</span>
            </div>
            <div class="mockup-body">
              <img src="/figures/dataset_example.png" alt="MDC++ Dataset" class="mockup-img" />
            </div>
          </div>
          <!-- 小悬浮卡片 -->
          <div class="float-card fc1">
            <img src="/images/im3.png" alt="3D" />
          </div>
          <div class="float-card fc2">
            <img src="/images/im1.png" alt="Zoom" />
          </div>
        </div>

        <!-- 右侧：简介 + 入口 -->
        <div class="hero-info">
          <div class="hero-badge">
            <span class="badge-pulse"></span> AI-Powered Crowd Analysis
          </div>
          <h1 class="hero-title">DroneCrowd</h1>
          <p class="hero-desc">
            无人机视角动态密集人群<br/>计数与时空分布分析平台
          </p>
          <div class="hero-tags">
            <span>人群计数</span><span>目标追踪</span><span>密度热力图</span><span>3D空间分析</span>
          </div>
          <button class="hero-cta" @click="$router.push('/dashboard')">
            ⊿ 进入分析平台
          </button>
          <div class="hero-stats">
            <div class="hstat" v-for="s in heroStats" :key="s.label">
              <strong>{{ s.value }}</strong><span>{{ s.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== 平台截图 Bento 画廊 ====== -->
    <section class="ov-gallery">
      <div class="gallery-header">
        <h2>平台功能预览</h2>
        <p>覆盖从数据标注到模型推理的全流程可视化分析</p>
      </div>
      <div class="gallery-grid">
        <div class="g-card gc-large" @click="$router.push('/heatmap')">
          <img src="/images/im2.png" alt="密度热力图" />
          <div class="gc-overlay">
            <strong>密度热力图</strong>
            <span>六种配色 · 等高线叠加</span>
          </div>
        </div>
        <div class="g-card" @click="$router.push('/spatial')">
          <img src="/images/im3.png" alt="3D空间分析" />
          <div class="gc-overlay">
            <strong>3D空间分析</strong>
            <span>密度地形渲染</span>
          </div>
        </div>
        <div class="g-card" @click="$router.push('/trajectory')">
          <img src="/images/im4.png" alt="轨迹追踪" />
          <div class="gc-overlay">
            <strong>轨迹追踪</strong>
            <span>人群移动路径回放</span>
          </div>
        </div>
        <div class="g-card" @click="$router.push('/zoom')">
          <img src="/images/im1.png" alt="放大对比" />
          <div class="gc-overlay">
            <strong>放大对比</strong>
            <span>帧级检测点精准定位</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== 模型 & 数据集展示 ====== -->
    <section class="ov-models">
      <div class="gallery-header">
        <h2>模型 & 数据集</h2>
        <p>支持多种前沿模型，MDC++ 数据集全面对比</p>
      </div>
      <div class="models-grid">
        <div class="model-card" v-for="m in models" :key="m.title">
          <div class="model-img-wrap">
            <img :src="m.img" :alt="m.title" />
            <div class="model-zoom-icon">⊕</div>
          </div>
          <div class="model-info">
            <strong>{{ m.title }}</strong>
            <span>{{ m.desc }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== 交互式预览：宽版布局 ====== -->
    <section class="ov-showcase">
      <div class="gallery-header">
        <h2>交互式预览</h2>
        <p>点击上方模块切换 · 点击大图全屏查看</p>
      </div>

      <div class="showcase-main" @mouseenter="pauseAuto" @mouseleave="resumeAuto">
        <!-- 上方：横向 Tab 选择器 -->
        <div class="showcase-tabs">
          <div
            class="sc-tab" v-for="(f, i) in features" :key="i"
            :class="{ active: activeFeature === i }"
            :style="{ '--accent': f.color }"
            @click="switchFeature(i)"
          >
            <div class="sc-tab-icon">
              <svg viewBox="0 0 36 36" class="tab-drone-svg">
                <ellipse cx="9" cy="9" rx="4.5" ry="1.5" fill="none" :stroke="f.color" stroke-width="1.1" opacity="0.7"/>
                <ellipse cx="27" cy="9" rx="4.5" ry="1.5" fill="none" :stroke="f.color" stroke-width="1.1" opacity="0.7"/>
                <ellipse cx="9" cy="27" rx="4.5" ry="1.5" fill="none" :stroke="f.color" stroke-width="1.1" opacity="0.7"/>
                <ellipse cx="27" cy="27" rx="4.5" ry="1.5" fill="none" :stroke="f.color" stroke-width="1.1" opacity="0.7"/>
                <line x1="12" y1="12" x2="18" y2="18" :stroke="f.color" stroke-width="0.7" opacity="0.4"/>
                <line x1="24" y1="12" x2="18" y2="18" :stroke="f.color" stroke-width="0.7" opacity="0.4"/>
                <line x1="12" y1="24" x2="18" y2="18" :stroke="f.color" stroke-width="0.7" opacity="0.4"/>
                <line x1="24" y1="24" x2="18" y2="18" :stroke="f.color" stroke-width="0.7" opacity="0.4"/>
                <circle cx="18" cy="18" r="3" fill="none" :stroke="f.color" stroke-width="1.1"/>
                <circle cx="18" cy="18" r="1.2" :fill="f.color" opacity="0.9">
                  <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/>
                </circle>
              </svg>
            </div>
            <div class="sc-tab-info">
              <strong>{{ f.title }}</strong>
              <span>{{ f.desc }}</span>
            </div>
            <div class="sc-tab-indicator"></div>
          </div>
        </div>

        <!-- 下方：宽版大图预览 -->
        <div class="showcase-preview" @click="openLightbox">
          <div class="preview-frame">
            <transition name="img-swap" mode="out-in">
              <img :src="features[activeFeature].img" :key="activeFeature"
                   :alt="features[activeFeature].title" class="preview-img" />
            </transition>
            <div class="preview-glow" :style="{ '--accent': features[activeFeature].color }"></div>
            <div class="corner tl"></div><div class="corner tr"></div>
            <div class="corner bl"></div><div class="corner br"></div>
            <div class="preview-hint"><span>⊕ 点击查看大图</span></div>
          </div>
          <div class="preview-caption">
            <span class="cap-dot" :style="{ background: features[activeFeature].color }"></span>
            <strong>{{ features[activeFeature].title }}</strong>
            <span class="cap-sep">—</span>
            <span>{{ features[activeFeature].desc }}</span>
          </div>
        </div>
      </div>

      <!-- 底部缩略图轮播条 -->
      <div class="showcase-strip">
        <button class="strip-btn" @click="prevFeature">◀</button>
        <div class="strip-track">
          <div class="strip-thumb" v-for="(f, i) in features" :key="i"
               :class="{ active: activeFeature === i }" :style="{ '--accent': f.color }"
               @click="switchFeature(i)">
            <img :src="f.img" :alt="f.title" />
          </div>
        </div>
        <button class="strip-btn" @click="nextFeature">▶</button>
        <div class="strip-progress">
          <span v-for="(f, i) in features" :key="'dot'+i"
                :class="{ active: activeFeature === i }" :style="{ '--accent': f.color }"
                @click="switchFeature(i)"></span>
        </div>
      </div>
    </section>

    <!-- ====== 快速入口 ====== -->
    <section class="ov-quick-section">
      <div class="gallery-header">
        <h2>快速入口</h2>
      </div>
      <div class="ov-quick-grid">
        <div class="ov-qcard" v-for="q in quickLinks" :key="q.path"
             @click="$router.push(q.path)" :style="{ '--accent': q.color }">
          <div class="ov-qicon">
            <svg viewBox="0 0 28 28" class="q-drone-mini">
              <ellipse cx="7" cy="7" rx="3.2" ry="1" fill="none" :stroke="q.color" stroke-width="1" opacity="0.6"/>
              <ellipse cx="21" cy="7" rx="3.2" ry="1" fill="none" :stroke="q.color" stroke-width="1" opacity="0.6"/>
              <ellipse cx="7" cy="21" rx="3.2" ry="1" fill="none" :stroke="q.color" stroke-width="1" opacity="0.6"/>
              <ellipse cx="21" cy="21" rx="3.2" ry="1" fill="none" :stroke="q.color" stroke-width="1" opacity="0.6"/>
              <line x1="9" y1="9" x2="14" y2="14" :stroke="q.color" stroke-width="0.6" opacity="0.35"/>
              <line x1="19" y1="9" x2="14" y2="14" :stroke="q.color" stroke-width="0.6" opacity="0.35"/>
              <line x1="9" y1="19" x2="14" y2="14" :stroke="q.color" stroke-width="0.6" opacity="0.35"/>
              <line x1="19" y1="19" x2="14" y2="14" :stroke="q.color" stroke-width="0.6" opacity="0.35"/>
              <circle cx="14" cy="14" r="2.2" fill="none" :stroke="q.color" stroke-width="1"/>
            </svg>
          </div>
          <strong>{{ q.label }}</strong>
          <span class="q-arrow">→</span>
        </div>
      </div>
    </section>

    <!-- ====== 灯箱 Modal ====== -->
    <Teleport to="body">
      <transition name="lightbox-fade">
        <div v-if="lightboxOpen" class="lightbox-overlay" @click="closeLightbox">
          <div class="lightbox-bg"></div>
          <button class="lightbox-close" @click="closeLightbox">✕</button>
          <button class="lightbox-nav prev" @click.stop="lightboxPrev">◀</button>
          <button class="lightbox-nav next" @click.stop="lightboxNext">▶</button>
          <div class="lightbox-content" @click.stop>
            <transition name="img-swap" mode="out-in">
              <img :src="features[lightboxIdx].img" :key="'lb-'+lightboxIdx"
                   :alt="features[lightboxIdx].title" class="lightbox-img" />
            </transition>
            <div class="lightbox-info">
              <strong>{{ features[lightboxIdx].title }}</strong>
              <span>{{ features[lightboxIdx].desc }}</span>
              <span class="lb-counter">{{ lightboxIdx + 1 }} / {{ features.length }}</span>
            </div>
          </div>
          <div class="lightbox-thumbs" @click.stop>
            <div class="lb-thumb" v-for="(f, i) in features" :key="'lb-'+i"
                 :class="{ active: lightboxIdx === i }" :style="{ '--accent': f.color }"
                 @click="lightboxIdx = i">
              <img :src="f.img" :alt="f.title" />
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <footer class="ov-footer"><p>DroneCrowd Platform · UAV-based Crowd Analysis</p></footer>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { getChartColors } from '../echartsTheme.js'

export default {
  name: 'Overview',
  setup() {
    const c = getChartColors()
    const activeFeature = ref(0)
    const lightboxOpen = ref(false)
    const lightboxIdx = ref(0)
    let autoTimer = null

    const heroStats = [
      { value: '4+', label: 'AI 模型' },
      { value: '实时', label: '推理速度' },
      { value: '6', label: '分析维度' },
      { value: '3D', label: '可视化' },
    ]

    const models = [
      { img: '/figures/GD3A.png', title: 'GD³A', desc: '全局密度感知锚框分配' },
      { img: '/figures/SDNet.jpg', title: 'SDNet', desc: '尺度解耦人群计数网络' },
      { img: '/figures/datasets_comparison.png', title: '数据集对比', desc: 'MDC++ 与其他数据集全面对比' },
      { img: '/figures/yolo11_arch.svg', title: 'YOLO11m', desc: 'VisDrone 重训练 · 行人检测模型' },
    ]

    const features = [
      { title: '仪表盘总览', desc: '多维度数据面板 · 实时指标监控', img: '/inter/in4.png', color: c.blue, route: '/dashboard' },
      { title: '密度热力图', desc: '六种配色方案 · 等高线叠加渲染', img: '/inter/in2.png', color: '#ff8c42', route: '/heatmap' },
      { title: '3D空间地形', desc: '密度曲面实时渲染 · 多角度观察', img: '/inter/in3.png', color: '#a855f7', route: '/spatial' },
      { title: '轨迹追踪', desc: '人群移动路径回放 · 时序分析', img: '/inter/in1.jpg', color: '#22c55e', route: '/trajectory' },
    ]

    const quickLinks = [
      { label: '仪表盘', path: '/dashboard', color: c.blue },
      { label: '热力图', path: '/heatmap', color: '#ff8c42' },
      { label: '空间分析', path: '/spatial', color: '#a855f7' },
      { label: '轨迹追踪', path: '/trajectory', color: '#22c55e' },
      { label: '放大对比', path: '/zoom', color: '#40d0ff' },
      { label: '对比分析', path: '/compare', color: '#f43f5e' },
    ]

    function switchFeature(i) { activeFeature.value = i; resetAutoTimer() }
    function nextFeature() { activeFeature.value = (activeFeature.value + 1) % features.length; resetAutoTimer() }
    function prevFeature() { activeFeature.value = (activeFeature.value - 1 + features.length) % features.length; resetAutoTimer() }
    function pauseAuto() { clearInterval(autoTimer) }
    function resumeAuto() { resetAutoTimer() }
    function resetAutoTimer() {
      clearInterval(autoTimer)
      autoTimer = setInterval(() => { activeFeature.value = (activeFeature.value + 1) % features.length }, 5000)
    }

    function openLightbox() {
      lightboxIdx.value = activeFeature.value
      lightboxOpen.value = true
      document.body.style.overflow = 'hidden'
    }
    function closeLightbox() {
      lightboxOpen.value = false
      document.body.style.overflow = ''
    }
    function lightboxPrev() { lightboxIdx.value = (lightboxIdx.value - 1 + features.length) % features.length }
    function lightboxNext() { lightboxIdx.value = (lightboxIdx.value + 1) % features.length }

    function onKeyDown(e) {
      if (!lightboxOpen.value) return
      if (e.key === 'Escape') closeLightbox()
      if (e.key === 'ArrowLeft') lightboxPrev()
      if (e.key === 'ArrowRight') lightboxNext()
    }

    onMounted(() => {
      resetAutoTimer()
      window.addEventListener('keydown', onKeyDown)
    })
    onUnmounted(() => {
      clearInterval(autoTimer)
      window.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
    })

    return {
      activeFeature, lightboxOpen, lightboxIdx,
      heroStats, models, features, quickLinks,
      switchFeature, nextFeature, prevFeature,
      pauseAuto, resumeAuto,
      openLightbox, closeLightbox, lightboxPrev, lightboxNext,
    }
  }
}
</script>

<style scoped>
.overview { background: var(--bg-deep); color: var(--text-primary); position: relative; }
[data-theme="city"] .overview { background: #f4f6f8; color: #1f2937; }

/* ========== 全局粒子特效 ========== */
.global-particles { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }

/* 浮动光球 */
.glow-orb {
  position: absolute; border-radius: 50%;
  filter: blur(60px); opacity: 0.12;
  animation: orb-float 12s ease-in-out infinite;
}
.orb-1 { width: 300px; height: 300px; background: var(--accent); top: 10%; left: -5%; animation-delay: 0s; }
.orb-2 { width: 250px; height: 250px; background: #a855f7; top: 50%; right: -8%; animation-delay: -4s; }
.orb-3 { width: 200px; height: 200px; background: #00d4aa; bottom: 20%; left: 30%; animation-delay: -8s; }
.orb-4 { width: 280px; height: 280px; background: #ff8c42; top: 70%; left: -5%; animation-delay: -2s; opacity: 0.07; }
@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(40px, -30px) scale(1.15); }
  50% { transform: translate(-20px, 20px) scale(0.9); }
  75% { transform: translate(30px, 10px) scale(1.1); }
}

/* 上升粒子 */
.float-particle {
  position: absolute; bottom: -10px; border-radius: 50%;
  background: var(--accent);
  animation: particle-rise linear infinite;
  box-shadow: 0 0 6px currentColor;
}
.float-particle:nth-child(odd) { background: #00d4aa; }
.float-particle:nth-child(3n) { background: #a855f7; }
@keyframes particle-rise {
  0% { transform: translateY(0); opacity: 0; }
  5% { opacity: 0.8; }
  90% { opacity: 0.1; }
  100% { transform: translateY(-100vh); opacity: 0; }
}

/* 扫描光束 */
.scan-beam {
  position: absolute; top: 0; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(77,166,255,0.03) 40%, rgba(77,166,255,0.06) 50%, rgba(77,166,255,0.03) 60%, transparent);
  animation: scan-sweep 8s linear infinite;
}
@keyframes scan-sweep {
  0% { left: -60%; }
  100% { left: 120%; }
}

/* ========== 分区光效装饰线 ========== */
.ov-gallery, .ov-models, .ov-showcase, .ov-quick-section {
  position: relative;
}
.ov-gallery::before, .ov-models::before, .ov-showcase::before {
  content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 200px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(77,166,255,0.25), transparent);
}

/* ========== Hero - 可视化为主 ========== */
.ov-hero {
  position: relative; padding: 60px 24px 70px;
  background: radial-gradient(ellipse at 30% 30%, rgba(47,111,237,0.12) 0%, transparent 55%),
              radial-gradient(ellipse at 70% 60%, rgba(0,159,145,0.08) 0%, transparent 50%);
  overflow: hidden;
}
[data-theme="city"] .ov-hero {
  background: radial-gradient(ellipse at 30% 30%, rgba(91,157,249,0.06) 0%, transparent 55%),
              radial-gradient(ellipse at 70% 60%, rgba(85,194,195,0.04) 0%, transparent 50%);
}
.hero-bg-particles { position: absolute; inset: 0; pointer-events: none; }
.bg-dot {
  position: absolute; width: 1.5px; height: 1.5px; border-radius: 50%;
  background: var(--accent);
  animation: dot-drift 6s linear infinite;
}
@keyframes dot-drift {
  0% { transform: translateY(0); opacity: 0; }
  10% { opacity: 0.8; }
  90% { opacity: 0.1; }
  100% { transform: translateY(-60px); opacity: 0; }
}

.hero-container {
  position: relative; z-index: 2;
  max-width: 1100px; margin: 0 auto;
  display: flex; gap: 50px; align-items: center;
}

/* 左侧：浏览器窗口 Mockup */
.hero-mockup { flex: 1; position: relative; }
.mockup-frame {
  background: var(--bg-card); border-radius: 12px; overflow: hidden;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 40px rgba(47,111,237,0.08);
  animation: mockup-glow 4s ease-in-out infinite;
}
[data-theme="city"] .mockup-frame {
  background: #ffffff;
  border: 1px solid #dce3e9;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08), 0 0 20px rgba(91,157,249,0.04);
}
@keyframes mockup-glow {
  0%, 100% { box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 40px rgba(47,111,237,0.08); }
  50% { box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 60px rgba(47,111,237,0.18); }
}
.mockup-bar {
  display: flex; align-items: center; gap: 6px; padding: 10px 14px;
  background: rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.06);
}
.mockup-dot { width: 10px; height: 10px; border-radius: 50%; }
.mockup-dot.red { background: #ff5f57; }
.mockup-dot.yellow { background: #febc2e; }
.mockup-dot.green { background: #28c840; }
.mockup-title {
  margin-left: 10px; font-size: 11px; color: rgba(255,255,255,0.35);
  letter-spacing: 0.05em;
}
.mockup-body { padding: 8px; }
.mockup-img {
  width: 100%; height: auto; border-radius: 6px; display: block;
}

/* 悬浮小卡片 */
.float-card {
  position: absolute; border-radius: 10px; overflow: hidden;
  border: 2px solid rgba(255,255,255,0.15);
  box-shadow: 0 8px 28px rgba(0,0,0,0.5);
  animation: float-card 5s ease-in-out infinite;
}
.float-card img { width: 100%; height: 100%; object-fit: cover; display: block; }
.fc1 {
  width: 120px; height: 80px; bottom: -20px; right: -30px;
  animation-delay: 0s;
}
.fc2 {
  width: 90px; height: 60px; top: -15px; right: -20px;
  animation-delay: 2.5s;
}
@keyframes float-card {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-8px) rotate(2deg); }
}

/* 右侧信息 */
.hero-info { flex: 0 0 340px; }
.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  padding: 5px 14px; border-radius: 20px;
  border: 1px solid rgba(77,166,255,0.25);
  background: rgba(77,166,255,0.06);
  color: #6db6ff; margin-bottom: 20px;
  font-family: Rajdhani, sans-serif;
}
.badge-pulse {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
  box-shadow: 0 0 8px var(--accent); animation: badge-pulse 2s ease-in-out infinite;
}
@keyframes badge-pulse { 0%,100%{opacity:0.6} 50%{opacity:1} }

.hero-title {
  font-family: Rajdhani, sans-serif; font-size: 42px; font-weight: 900;
  background: linear-gradient(135deg, var(--accent), #00d4aa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 12px;
  filter: drop-shadow(0 0 20px rgba(77,166,255,0.3));
}
.hero-desc {
  font-size: 17px; color: rgba(255,255,255,0.55); line-height: 1.7; margin: 0 0 20px;
}
[data-theme="city"] .hero-desc { color: #64748b; }
.hero-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
.hero-tags span {
  font-size: 11px; padding: 4px 12px; border-radius: 6px;
  background: rgba(255,255,255,0.04); color: var(--text-dim);
  border: 1px solid rgba(255,255,255,0.06);
}
.hero-cta {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 13px 30px; border: none; border-radius: 10px;
  font-size: 15px; font-weight: 700; cursor: pointer;
  background: linear-gradient(135deg, #1a5ce0, #3d8bff);
  color: #fff; box-shadow: 0 8px 30px rgba(47,111,237,0.35);
  transition: all 0.35s; letter-spacing: 0.04em;
  position: relative;
  animation: cta-pulse 3s ease-in-out infinite;
}
@keyframes cta-pulse {
  0%, 100% { box-shadow: 0 8px 30px rgba(47,111,237,0.35); }
  50% { box-shadow: 0 8px 50px rgba(47,111,237,0.55), 0 0 80px rgba(47,111,237,0.2); }
}
.hero-cta:hover { transform: translateY(-3px); box-shadow: 0 14px 44px rgba(47,111,237,0.5); animation: none; }

.hero-stats { display: flex; gap: 28px; margin-top: 30px; }
.hstat { text-align: center; }
.hstat strong { display: block; font-size: 24px; color: #fff; font-weight: 900; font-family: Rajdhani, sans-serif; }
.hstat span { font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; }

/* ========== 通用 Section Header ========== */
.gallery-header { text-align: center; margin-bottom: 30px; }
.gallery-header h2 {
  font-family: Rajdhani, sans-serif; font-size: 22px; font-weight: 700;
  color: #e0e8f0; margin: 0 0 8px;
  text-shadow: 0 0 18px var(--accent-glow);
}
.gallery-header p { color: var(--text-dim); font-size: 13px; margin: 0; }

/* ========== Bento 画廊 ========== */
.ov-gallery { max-width: 1100px; margin: 0 auto; padding: 50px 20px; }
.gallery-grid {
  display: grid; grid-template-columns: 1.4fr 1fr 1fr;
  grid-template-rows: 200px 200px;
  gap: 14px;
}
.g-card {
  position: relative; border-radius: 14px; overflow: hidden;
  cursor: pointer; background: #0a1226;
  border: 1px solid rgba(255,255,255,0.06);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
/* Shimmer sweep on hover */
.g-card::after {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 45%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 55%, transparent 60%);
  transform: translateX(-100%); transition: transform 0.6s;
}
.g-card:hover::after { transform: translateX(100%); }
.g-card img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s; }
.g-card:hover img { transform: scale(1.06); }
.g-card:hover {
  border-color: rgba(77,166,255,0.35);
  box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 30px rgba(77,166,255,0.08);
}
.gc-large { grid-row: span 2; }
.gc-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 24px 16px 14px;
  background: linear-gradient(transparent, rgba(0,0,0,0.85));
}
.gc-overlay strong { display: block; font-size: 15px; color: #fff; margin-bottom: 2px; }
.gc-overlay span { font-size: 11px; color: rgba(255,255,255,0.55); }

/* ========== 模型展示 ========== */
.ov-models { max-width: 1100px; margin: 0 auto; padding: 30px 20px 50px; }
.models-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.model-card {
  background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px; overflow: hidden; cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}
.model-card::after {
  content: ''; position: absolute; inset: 0; pointer-events: none; z-index: 2;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.03) 45%, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0.03) 55%, transparent 60%);
  transform: translateX(-100%); transition: transform 0.6s;
}
.model-card:hover::after { transform: translateX(100%); }
.model-card:hover {
  transform: translateY(-6px);
  border-color: rgba(77,166,255,0.3);
  box-shadow: 0 16px 44px rgba(0,0,0,0.6), 0 0 24px rgba(77,166,255,0.1);
}
.model-img-wrap { position: relative; overflow: hidden; aspect-ratio: 16/10; background: #0a1226; }
.model-img-wrap img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s; }
.model-card:hover .model-img-wrap img { transform: scale(1.06); }
.model-zoom-icon {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.5); opacity: 0; transition: opacity 0.3s; font-size: 28px;
}
.model-card:hover .model-zoom-icon { opacity: 1; }
.model-info { padding: 14px 16px; }
.model-info strong { display: block; font-size: 14px; color: #e0e8f0; margin-bottom: 2px; }
.model-info span { font-size: 12px; color: var(--text-dim); }

/* ========== 交互式预览 (水平布局) ========== */
.ov-showcase { max-width: 1100px; margin: 0 auto; padding: 30px 20px 40px; }
.showcase-main { display: flex; flex-direction: column; gap: 18px; }

/* 上方横向 Tab */
.showcase-tabs {
  display: flex; flex-direction: row; gap: 10px;
  justify-content: center; flex-wrap: wrap;
}
.sc-tab {
  position: relative; display: flex; align-items: center; gap: 10px;
  padding: 12px 18px; border-radius: 12px;
  background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);
  cursor: pointer; transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1); overflow: hidden;
  min-width: 150px; flex: 1; max-width: 240px;
}
.sc-tab::before {
  content: ''; position: absolute; inset: 0; background: var(--accent);
  opacity: 0; transition: opacity 0.35s;
}
.sc-tab:hover::before { opacity: 0.04; }
.sc-tab.active::before { opacity: 0.08; }
.sc-tab:hover { border-color: rgba(255,255,255,0.12); transform: translateY(-3px); }
.sc-tab.active {
  border-color: var(--accent);
  box-shadow: 0 0 24px color-mix(in srgb, var(--accent) 25%, transparent);
}
.sc-tab-indicator {
  position: absolute; bottom: 0; left: 20%; width: 60%; height: 3px;
  border-radius: 3px 3px 0 0; background: var(--accent);
  transform: scaleX(0); transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 10px var(--accent);
}
.sc-tab.active .sc-tab-indicator { transform: scaleX(1); }
.sc-tab-icon { width: 30px; height: 30px; flex-shrink: 0; }
.tab-drone-svg { width: 100%; height: 100%; }
.sc-tab-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.sc-tab-info strong { font-size: 13px; color: #e0e8f0; white-space: nowrap; }
.sc-tab.active .sc-tab-info strong { color: #fff; }
.sc-tab-info span { font-size: 10px; color: var(--text-dim); line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* 下方宽版预览 */
.showcase-preview { width: 100%; cursor: pointer; }
.preview-frame {
  position: relative; width: 100%;
  aspect-ratio: 16 / 9; max-height: 500px;
  border-radius: 16px; overflow: hidden;
  background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.08);
}
.preview-img { width: 100%; height: 100%; object-fit: contain; transition: transform 0.5s; }
.preview-frame:hover .preview-img { transform: scale(1.03); }
.preview-glow { position: absolute; inset: 0; pointer-events: none; border-radius: 16px; }
.preview-frame:hover .preview-glow {
  box-shadow: inset 0 0 0 rgba(0,0,0,0), 0 0 40px color-mix(in srgb, var(--accent) 30%, transparent);
}

.corner { position: absolute; width: 20px; height: 20px; pointer-events: none; }
.corner.tl { top: 12px; left: 12px; border-top: 2px solid rgba(255,255,255,0.2); border-left: 2px solid rgba(255,255,255,0.2); }
.corner.tr { top: 12px; right: 12px; border-top: 2px solid rgba(255,255,255,0.2); border-right: 2px solid rgba(255,255,255,0.2); }
.corner.bl { bottom: 12px; left: 12px; border-bottom: 2px solid rgba(255,255,255,0.2); border-left: 2px solid rgba(255,255,255,0.2); }
.corner.br { bottom: 12px; right: 12px; border-bottom: 2px solid rgba(255,255,255,0.2); border-right: 2px solid rgba(255,255,255,0.2); }

.preview-hint {
  position: absolute; bottom: 12px; right: 16px;
  font-size: 11px; color: rgba(255,255,255,0.4);
  background: rgba(0,0,0,0.5); padding: 4px 10px;
  border-radius: 6px; opacity: 0; transition: opacity 0.3s;
}
.preview-frame:hover .preview-hint { opacity: 1; }

.preview-caption { display: flex; align-items: center; gap: 8px; margin-top: 12px; padding: 0 4px; }
.cap-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 8px currentColor; }
.preview-caption strong { font-size: 15px; color: #e0e8f0; }
.cap-sep { color: rgba(255,255,255,0.2); }
.preview-caption span:last-child { font-size: 12px; color: var(--text-dim); }

.img-swap-enter-active, .img-swap-leave-active { transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); }
.img-swap-enter-from { opacity: 0; transform: scale(0.96) translateY(6px); }
.img-swap-leave-to { opacity: 0; transform: scale(1.02); }

/* 缩略图轮播 */
.showcase-strip { display: flex; align-items: center; gap: 12px; margin-top: 18px; padding: 0 4px; }
.strip-btn {
  width: 34px; height: 34px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.12); background: rgba(10,20,40,0.7);
  color: #fff; font-size: 13px; cursor: pointer; transition: all 0.3s; flex-shrink: 0;
}
.strip-btn:hover { background: rgba(47,111,237,0.3); border-color: var(--accent); }
.strip-track { display: flex; gap: 10px; flex: 1; justify-content: center; }
.strip-thumb {
  width: 100px; height: 64px; border-radius: 8px; overflow: hidden; cursor: pointer;
  border: 2px solid transparent; transition: all 0.35s; opacity: 0.5;
}
.strip-thumb.active { opacity: 1; border-color: var(--accent); box-shadow: 0 0 16px color-mix(in srgb, var(--accent) 40%, transparent); transform: translateY(-3px); }
.strip-thumb:hover { opacity: 0.85; }
.strip-thumb img { width: 100%; height: 100%; object-fit: cover; }

.strip-progress { display: flex; gap: 6px; margin-left: 8px; }
.strip-progress span {
  width: 6px; height: 6px; border-radius: 50%; background: rgba(255,255,255,0.15);
  cursor: pointer; transition: all 0.3s;
}
.strip-progress span.active { background: var(--accent); width: 20px; border-radius: 3px; box-shadow: 0 0 8px var(--accent); }

/* ========== 快速入口 ========== */
.ov-quick-section { max-width: 900px; margin: 0 auto; padding: 30px 20px 50px; }
.ov-quick-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 24px; }
.ov-qcard {
  background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px; padding: 20px 16px; cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex; align-items: center; gap: 12px; position: relative; overflow: hidden;
}
.ov-qcard::after {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.02) 45%, rgba(255,255,255,0.04) 50%, rgba(255,255,255,0.02) 55%, transparent 60%);
  transform: translateX(-100%); transition: transform 0.5s;
}
.ov-qcard:hover::after { transform: translateX(100%); }
.ov-qcard::before { content: ''; position: absolute; inset: 0; background: var(--accent); opacity: 0; transition: opacity 0.35s; }
.ov-qcard:hover::before { opacity: 0.05; }
.ov-qcard:hover { transform: translateY(-4px); border-color: color-mix(in srgb, var(--accent) 40%, transparent); box-shadow: 0 12px 32px rgba(0,0,0,0.5), 0 0 20px color-mix(in srgb, var(--accent) 15%, transparent); }
.ov-qicon { width: 28px; height: 28px; flex-shrink: 0; }
.q-drone-mini { width: 100%; height: 100%; }
.ov-qcard strong { font-size: 14px; color: var(--text-primary); flex: 1; }
.q-arrow { color: rgba(255,255,255,0.2); font-size: 14px; transition: all 0.3s; }
.ov-qcard:hover .q-arrow { color: var(--accent); transform: translateX(4px); }

/* ========== 灯箱 ========== */
.lightbox-overlay { position: fixed; inset: 0; z-index: 9999; display: flex; align-items: center; justify-content: center; flex-direction: column; }
.lightbox-bg { position: absolute; inset: 0; background: rgba(0,0,0,0.92); backdrop-filter: blur(16px); }
.lightbox-close {
  position: absolute; top: 20px; right: 24px; z-index: 2;
  width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.5);
  color: #fff; font-size: 20px; cursor: pointer; transition: all 0.3s;
}
.lightbox-close:hover { background: rgba(255,60,60,0.4); border-color: #f44; }
.lightbox-nav {
  position: absolute; top: 50%; transform: translateY(-50%); z-index: 2;
  width: 48px; height: 48px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.15); background: rgba(0,0,0,0.5);
  color: #fff; font-size: 18px; cursor: pointer; transition: all 0.3s;
}
.lightbox-nav:hover { background: rgba(47,111,237,0.3); border-color: var(--accent); }
.lightbox-nav.prev { left: 20px; } .lightbox-nav.next { right: 20px; }
.lightbox-content { position: relative; z-index: 1; max-width: 85vw; max-height: 75vh; display: flex; flex-direction: column; align-items: center; }
.lightbox-img { max-width: 85vw; max-height: 68vh; object-fit: contain; border-radius: 10px; box-shadow: 0 20px 60px rgba(0,0,0,0.8); }
.lightbox-info { display: flex; align-items: center; gap: 12px; margin-top: 14px; color: #fff; }
.lightbox-info strong { font-size: 16px; }
.lightbox-info span { font-size: 13px; color: rgba(255,255,255,0.5); }
.lb-counter { color: rgba(255,255,255,0.3) !important; margin-left: 4px; }
.lightbox-thumbs { position: relative; z-index: 1; display: flex; gap: 10px; margin-top: 18px; }
.lb-thumb {
  width: 64px; height: 44px; border-radius: 6px; overflow: hidden; cursor: pointer;
  border: 2px solid rgba(255,255,255,0.1); transition: all 0.3s; opacity: 0.5;
}
.lb-thumb.active { opacity: 1; border-color: var(--accent); box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 40%, transparent); }
.lb-thumb:hover { opacity: 0.85; }
.lb-thumb img { width: 100%; height: 100%; object-fit: cover; }

.lightbox-fade-enter-active, .lightbox-fade-leave-active { transition: opacity 0.3s; }
.lightbox-fade-enter-from, .lightbox-fade-leave-to { opacity: 0; }

/* ========== Footer ========== */
.ov-footer { text-align: center; padding: 28px; border-top: 1px solid rgba(255,255,255,0.04); color: rgba(255,255,255,0.15); font-size: 12px; letter-spacing: 0.05em; }

/* ========== 响应式 ========== */
@media (max-width: 900px) {
  .hero-container { flex-direction: column; }
  .hero-info { flex: auto; text-align: center; }
  .hero-stats { justify-content: center; }
  .hero-mockup { max-width: 500px; }
  .float-card { display: none; }
  .gallery-grid { grid-template-columns: 1fr 1fr; grid-template-rows: auto; }
  .gc-large { grid-row: span 1; }
  .models-grid { grid-template-columns: repeat(2, 1fr); }
  .sc-tab { flex: 1 1 45%; min-width: 140px; max-width: none; }
  .preview-frame { aspect-ratio: 4/3; }
  .strip-thumb { width: 70px; height: 48px; }
}
@media (max-width: 500px) {
  .gallery-grid { grid-template-columns: 1fr; }
  .models-grid { grid-template-columns: 1fr; }
  .sc-tab { flex: 1 1 100%; min-width: 0; }
  .sc-tab-info span { white-space: normal; }
  .ov-quick-grid { grid-template-columns: repeat(2, 1fr); }
  .lightbox-nav { width: 36px; height: 36px; font-size: 14px; }
}
</style>
