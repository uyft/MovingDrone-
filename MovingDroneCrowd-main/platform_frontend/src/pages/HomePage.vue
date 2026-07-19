<template>
  <div class="home-page" ref="scrollContainer">
    <!-- ===== 粒子背景画布 ===== -->
    <canvas ref="particleCanvas" class="particle-bg"></canvas>

    <!-- ===== 顶部导航条 ===== -->
    <header class="top-bar" :class="{ scrolled: isScrolled }">
      <div class="top-bar-inner">
        <div class="logo-area">
          <div class="logo-hex">◈</div>
          <span class="logo-text">MovingDroneCrowd</span>
        </div>
        <nav class="top-nav">
          <a v-for="item in navItems" :key="item.id" :href="item.href" class="top-nav-link">
            {{ item.label }}
          </a>
          <router-link to="/dashboard" class="top-nav-cta">进入系统</router-link>
        </nav>
      </div>
    </header>

    <!-- ===== Hero 主视觉区 ===== -->
    <section class="hero-section">
      <div class="hero-bg-grid"></div>
      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-dot"></span> AI-Powered Crowd Analysis
        </div>
        <h1 class="hero-title">
          <span class="title-line1">无人机视角</span>
          <span class="title-line2">
            <span class="gradient-text" ref="gradientTitle">动态密集人群</span>
          </span>
          <span class="title-line3">计数与时空分析系统</span>
        </h1>
        <p class="hero-desc">
          基于深度学习的实时人群密度估计 · 多模型融合 · 时空分布可视化
        </p>
        <div class="hero-actions">
          <router-link to="/dashboard" class="hero-btn primary">
            <span>↗ 开始使用</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </router-link>
          <a href="#features" class="hero-btn secondary">
            <span>了解更多</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          </a>
        </div>
      </div>
      <!-- 漂浮装饰 -->
      <div class="floating-shapes">
        <div class="float-shape s1"></div>
        <div class="float-shape s2"></div>
        <div class="float-shape s3"></div>
        <div class="float-shape s4"></div>
        <div class="float-shape s5"></div>
        <div class="float-shape s6"></div>
      </div>
      <!-- 滚动提示 -->
      <div class="scroll-hint" @click="scrollToSection('#stats')">
        <span>向下滚动</span>
        <div class="scroll-arrow">⌄</div>
      </div>
    </section>

    <!-- ===== 核心指标统计区 ===== -->
    <section id="stats" class="stats-section">
      <div class="section-header">
        <h2 class="section-title">平台核心能力</h2>
        <p class="section-sub">Core Capabilities</p>
      </div>
      <div class="stats-grid">
        <div class="stat-card" v-for="(stat, i) in statsData" :key="i"
             :style="{ animationDelay: i * 0.1 + 's' }"
             ref="statCards">
          <div class="stat-icon-wrap">
            <div class="stat-icon-bg" :style="{ background: stat.gradient }"></div>
            <span class="stat-icon-emoji">{{ stat.icon }}</span>
          </div>
          <div class="stat-info">
            <div class="stat-number">
              <span class="count-up" ref="countUps">{{ animatedCounts[i] || 0 }}</span>
              <span class="stat-unit">{{ stat.unit }}</span>
            </div>
            <div class="stat-desc">{{ stat.label }}</div>
          </div>
          <div class="stat-bar">
            <div class="stat-bar-fill" :style="{ width: stat.barPercent + '%', background: stat.gradient }"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== 功能特性展示（轮播） ===== -->
    <section id="features" class="features-section">
      <div class="section-header">
        <h2 class="section-title">核心功能特性</h2>
        <p class="section-sub">Feature Highlights</p>
      </div>

      <!-- 轮播 -->
      <div class="carousel-wrap" ref="carouselWrap">
        <button class="carousel-arrow left" @click="carouselPrev">‹</button>
        <button class="carousel-arrow right" @click="carouselNext">›</button>

        <div class="carousel-track" :style="{ transform: `translateX(-${carouselIndex * 100}%)` }">
          <div class="carousel-slide" v-for="(feat, i) in featuresData" :key="i">
            <div class="feature-card">
              <div class="feature-visual">
                <div class="feature-mock" :style="{ background: feat.bgGradient }">
                  <div class="mock-inner">
                    <div class="mock-icon">{{ feat.icon }}</div>
                    <div class="mock-title">{{ feat.title }}</div>
                    <div class="mock-preview">
                      <div class="mock-dot" v-for="d in feat.dots" :key="d"
                           :style="{
                             left: d.x + '%', top: d.y + '%',
                             animationDelay: d.delay + 's',
                             width: d.size + 'px', height: d.size + 'px'
                           }"></div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="feature-detail">
                <h3>{{ feat.title }}</h3>
                <p>{{ feat.desc }}</p>
                <ul class="feature-tags">
                  <li v-for="tag in feat.tags" :key="tag">{{ tag }}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- 指示器 -->
        <div class="carousel-dots">
          <span v-for="(feat, i) in featuresData" :key="i"
                class="carousel-dot" :class="{ active: i === carouselIndex }"
                @click="carouselIndex = i"></span>
        </div>
      </div>
    </section>

    <!-- ===== 技术亮点展示区 ===== -->
    <section id="tech" class="tech-section">
      <div class="section-header">
        <h2 class="section-title">技术架构亮点</h2>
        <p class="section-sub">Technical Architecture</p>
      </div>

      <div class="tech-grid">
        <div class="tech-card" v-for="(tech, i) in techData" :key="i"
             ref="techCards"
             :style="{ animationDelay: i * 0.12 + 's' }">
          <div class="tech-card-glow" :style="{ background: tech.glow }"></div>
          <div class="tech-card-content">
            <div class="tech-icon-box" :style="{ borderColor: tech.color }">
              <span>{{ tech.icon }}</span>
            </div>
            <h3>{{ tech.title }}</h3>
            <p>{{ tech.desc }}</p>
            <div class="tech-meta">
              <span class="tech-meta-item" v-for="m in tech.meta" :key="m">{{ m }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== 图片展示墙 ===== -->
    <section class="gallery-section">
      <div class="section-header">
        <h2 class="section-title">可视化效果展示</h2>
        <p class="section-sub">Visual Gallery</p>
      </div>

      <div class="gallery-grid">
        <div class="gallery-item" v-for="(img, i) in galleryImages" :key="i"
             :class="{ 'gallery-wide': img.wide, 'gallery-tall': img.tall }"
             @mouseenter="hoveredGallery = i" @mouseleave="hoveredGallery = -1">
          <div class="gallery-img-placeholder" :style="{ background: img.gradient }">
            <div class="gallery-overlay" :class="{ show: hoveredGallery === i }">
              <span>{{ img.label }}</span>
              <small>{{ img.desc }}</small>
            </div>
            <div class="gallery-shimmer"></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== CTA 底部 ===== -->
    <section class="cta-section">
      <div class="cta-bg-anim"></div>
      <div class="cta-content">
        <h2>准备好开始了吗？</h2>
        <p>上传您的无人机航拍视频，体验先进的密集人群计数与时空分析</p>
        <router-link to="/dashboard" class="cta-btn">
          <span>进入分析平台</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </router-link>
      </div>
      <div class="cta-particles">
        <span v-for="i in 20" :key="i" class="cta-particle"
              :style="{
                left: Math.random() * 100 + '%',
                animationDelay: Math.random() * 3 + 's',
                animationDuration: 2 + Math.random() * 4 + 's'
              }"></span>
      </div>
    </section>

    <!-- ===== Footer ===== -->
    <footer class="footer">
      <div class="footer-inner">
        <div class="footer-left">
          <span class="footer-logo">◈ MovingDroneCrowd</span>
          <span class="footer-desc">AI-Powered · 无人机人群计数与时空分析</span>
        </div>
        <div class="footer-right">
          <span>© MovingDroneCrowd Team</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { getChartColors } from '../echartsTheme.js'

export default {
  name: 'HomePage',
  setup() {
    const c = getChartColors()
    const scrollContainer = ref(null)
    const particleCanvas = ref(null)
    const isScrolled = ref(false)
    const carouselIndex = ref(0)
    const hoveredGallery = ref(-1)
    const animatedCounts = ref([0, 0, 0, 0])
    const statCards = ref([])
    const techCards = ref([])
    let carouselTimer = null
    let particleAnimId = null
    let countAnimFrames = []

    // ===== 导航项 =====
    const navItems = [
      { id: 'features', href: '#features', label: '功能特性' },
      { id: 'tech', href: '#tech', label: '技术架构' },
      { id: 'gallery', href: '#gallery', label: '效果展示' },
    ]

    // ===== 核心指标 =====
    const statsData = [
      { icon: '⊙', label: '支持检测模型', value: 8, unit: '+', gradient: 'linear-gradient(135deg, c.blue, #2068e0)', barPercent: 80 },
      { icon: '≡', label: '可视化分析维度', value: 6, unit: '', gradient: 'linear-gradient(135deg, #a78bfa, #7c3aed)', barPercent: 75 },
      { icon: '⚡', label: '实时处理帧率', value: 30, unit: 'FPS', gradient: 'linear-gradient(135deg, #34d399, #059669)', barPercent: 90 },
      { icon: '⊡', label: '支持视频格式', value: 4, unit: '+', gradient: 'linear-gradient(135deg, #f59e0b, #d97706)', barPercent: 65 },
    ]

    // ===== 功能特性 =====
    const featuresData = [
      {
        icon: '👥', title: '密集人群计数', dots: [
          { x: 20, y: 30, delay: 0, size: 6 },
          { x: 50, y: 20, delay: 0.3, size: 5 },
          { x: 70, y: 40, delay: 0.6, size: 7 },
          { x: 35, y: 55, delay: 0.9, size: 4 },
          { x: 60, y: 65, delay: 1.2, size: 6 },
          { x: 25, y: 70, delay: 1.5, size: 5 },
          { x: 80, y: 25, delay: 0.2, size: 6 },
          { x: 45, y: 75, delay: 0.7, size: 4 },
          { x: 15, y: 45, delay: 1.0, size: 5 },
          { x: 55, y: 10, delay: 0.4, size: 6 },
        ],
        bgGradient: 'linear-gradient(135deg, #0a1a3a 0%, #0d2b5e 50%, #0a1a3a 100%)',
        desc: '采用YOLO系列、RTMDet、SSD等先进目标检测模型，结合密度图回归方法，实现对无人机视角下高密度人群的精准计数。支持多种主流深度学习框架。',
        tags: ['YOLOv8/v9/v10', 'RTMDet', 'SSD', '密度图回归']
      },
      {
        icon: '🗺️', title: '时空热力图分析', dots: [
          { x: 15, y: 25, delay: 0, size: 8 },
          { x: 40, y: 35, delay: 0.4, size: 10 },
          { x: 65, y: 20, delay: 0.8, size: 7 },
          { x: 30, y: 55, delay: 0.3, size: 9 },
          { x: 55, y: 50, delay: 0.6, size: 8 },
          { x: 75, y: 60, delay: 1.0, size: 6 },
          { x: 20, y: 70, delay: 0.5, size: 7 },
          { x: 50, y: 75, delay: 0.9, size: 5 },
          { x: 80, y: 40, delay: 0.2, size: 8 },
          { x: 10, y: 50, delay: 0.7, size: 6 },
        ],
        bgGradient: 'linear-gradient(135deg, #1a0a2e 0%, #2d1b4e 50%, #1a0a2e 100%)',
        desc: '基于人群空间分布生成高精度热力图，直观展示人群聚集区域与密度分布。支持动态时序热力图，可追踪人群密度随时间的变化趋势。',
        tags: ['热力图', '密度分布', '时序变化', '空间聚类']
      },
      {
        icon: '↗', title: '轨迹追踪分析', dots: [
          { x: 25, y: 20, delay: 0, size: 5 },
          { x: 55, y: 30, delay: 0.3, size: 6 },
          { x: 70, y: 15, delay: 0.6, size: 4 },
          { x: 40, y: 45, delay: 0.2, size: 5 },
          { x: 60, y: 55, delay: 0.5, size: 6 },
          { x: 30, y: 65, delay: 0.8, size: 4 },
          { x: 75, y: 70, delay: 0.4, size: 5 },
          { x: 20, y: 40, delay: 0.7, size: 6 },
          { x: 50, y: 10, delay: 0.1, size: 5 },
          { x: 85, y: 45, delay: 0.9, size: 4 },
        ],
        bgGradient: 'linear-gradient(135deg, #0a2e1a 0%, #0d4e2b 50%, #0a2e1a 100%)',
        desc: '采用多目标跟踪算法(DeepSORT/Bytetrack/HybridSORT)，实现人群个体的精确轨迹追踪。可视化行人运动方向、速度及路径模式。',
        tags: ['DeepSORT', 'Bytetrack', 'HybridSORT', '运动模式']
      },
      {
        icon: '🔬', title: '多维度对比分析', dots: [
          { x: 10, y: 20, delay: 0, size: 5 },
          { x: 30, y: 35, delay: 0.3, size: 6 },
          { x: 55, y: 25, delay: 0.5, size: 5 },
          { x: 75, y: 15, delay: 0.2, size: 4 },
          { x: 20, y: 55, delay: 0.6, size: 5 },
          { x: 45, y: 60, delay: 0.1, size: 6 },
          { x: 65, y: 50, delay: 0.7, size: 5 },
          { x: 35, y: 75, delay: 0.4, size: 4 },
          { x: 80, y: 70, delay: 0.8, size: 5 },
          { x: 15, y: 10, delay: 0.3, size: 6 },
        ],
        bgGradient: 'linear-gradient(135deg, #2e1a0a 0%, #4e2b0d 50%, #2e1a0a 100%)',
        desc: '支持多种检测模型结果并排对比，可同时查看不同算法在同一视频上的表现差异。提供空间分析、时序分析等多维度对比视图。',
        tags: ['模型对比', '空间分析', '时序分析', 'ROI放大']
      },
    ]

    // ===== 技术亮点 =====
    const techData = [
      {
        icon: '🧠', title: '多模型融合架构', glow: 'radial-gradient(circle at 50% 0%, rgba(92,184,255,0.25), transparent 70%)',
        desc: '集成YOLOv5/v8/v9/v10、RTMDet、SSD、Faster R-CNN等多种目标检测模型，支持一键切换与结果对比。',
        meta: ['PyTorch', 'ONNX', 'TensorRT'], color: c.blue
      },
      {
        icon: '⚡', title: '实时GPU加速推理', glow: 'radial-gradient(circle at 50% 0%, rgba(52,211,153,0.25), transparent 70%)',
        desc: '基于CUDA加速的实时推理引擎，支持FP16精度推理，单帧处理低至30ms，满足实时分析需求。',
        meta: ['CUDA', 'FP16', '30FPS+'], color: '#34d399'
      },
      {
        icon: '🎨', title: '丰富可视化面板', glow: 'radial-gradient(circle at 50% 0%, rgba(167,139,250,0.25), transparent 70%)',
        desc: '提供热力图、轨迹追踪、空间分析、时序分析、对比分析等多维可视化面板，ECharts+3D GL渲染。',
        meta: ['ECharts', 'ECharts GL', '3D'], color: '#a78bfa'
      },
      {
        icon: '⇄', title: '端到端分析流水线', glow: 'radial-gradient(circle at 50% 0%, rgba(245,158,11,0.25), transparent 70%)',
        desc: '视频上传 → 模型推理 → 结果存储 → 可视化展示，全流程自动化，一键完成从原始数据到分析报告的转换。',
        meta: ['FastAPI', 'Vue 3', '自动化'], color: '#f59e0b'
      },
      {
        icon: '📐', title: '高精度密度估计', glow: 'radial-gradient(circle at 50% 0%, rgba(239,68,68,0.25), transparent 70%)',
        desc: '结合密度图回归与检测计数双通路，在密集场景下仍保持高精度。支持CSRNet、MCNN等密度估计模型。',
        meta: ['CSRNet', 'MCNN', 'MAE<15'], color: '#ef4444'
      },
      {
        icon: '🌐', title: '跨平台Web部署', glow: 'radial-gradient(circle at 50% 0%, rgba(6,182,212,0.25), transparent 70%)',
        desc: '基于Vue 3 + Vite构建的现代化前端，FastAPI高性能后端，支持本地部署与云端服务，响应式设计适配多终端。',
        meta: ['Vue 3', 'Vite', '响应式'], color: '#06b6d4'
      },
    ]

    // ===== 图片展示墙 =====
    const galleryImages = [
      { label: '密集人群检测', desc: 'YOLOv8 实时检测效果', gradient: 'linear-gradient(135deg, #0d1b3e 0%, #1a3a6e 50%, #0d1b3e 100%)', wide: true },
      { label: '热力图分析', desc: '人群密度热力分布', gradient: 'linear-gradient(135deg, #1e0d2e 0%, #3d1a6e 50%, #1e0d2e 100%)', tall: true },
      { label: '轨迹追踪', desc: '个体运动轨迹', gradient: 'linear-gradient(135deg, #0d2e1a 0%, #1a6e3a 50%, #0d2e1a 100%)' },
      { label: '模型对比', desc: '多模型结果对比', gradient: 'linear-gradient(135deg, #2e1a0d 0%, #6e3d1a 50%, #2e1a0d 100%)' },
      { label: '时序分析', desc: '人数变化趋势', gradient: 'linear-gradient(135deg, #0d2e2e 0%, #1a6e6e 50%, #0d2e2e 100%)', wide: true },
      { label: '空间分析', desc: '人群空间分布', gradient: 'linear-gradient(135deg, #2e0d2e 0%, #6e1a6e 50%, #2e0d2e 100%)' },
    ]

    // ===== 滚动监听 =====
    function handleScroll() {
      isScrolled.value = window.scrollY > 60
    }

    // ===== 平滑滚动 =====
    function scrollToSection(selector) {
      const el = document.querySelector(selector)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }

    // ===== 轮播 =====
    function carouselNext() {
      carouselIndex.value = (carouselIndex.value + 1) % featuresData.length
    }
    function carouselPrev() {
      carouselIndex.value = (carouselIndex.value - 1 + featuresData.length) % featuresData.length
    }
    function startCarousel() {
      carouselTimer = setInterval(carouselNext, 4000)
    }
    function stopCarousel() {
      if (carouselTimer) clearInterval(carouselTimer)
    }

    // ===== 数字滚动动画 =====
    function animateCounts() {
      const targets = [8, 6, 30, 4]
      const duration = 1500
      const startTime = performance.now()

      function update(timestamp) {
        const elapsed = timestamp - startTime
        const progress = Math.min(elapsed / duration, 1)
        // easeOutExpo
        const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)

        animatedCounts.value = targets.map(t => Math.round(t * eased))

        if (progress < 1) {
          requestAnimationFrame(update)
        }
      }
      requestAnimationFrame(update)
    }

    // ===== 粒子背景 =====
    function initParticles() {
      const canvas = particleCanvas.value
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const particles = []
      const count = 80

      function resize() {
        canvas.width = window.innerWidth
        canvas.height = document.querySelector('.home-page').scrollHeight || window.innerHeight * 3
      }
      resize()
      window.addEventListener('resize', resize)

      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          size: Math.random() * 2 + 0.5,
          alpha: Math.random() * 0.5 + 0.1,
        })
      }

      function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        particles.forEach(p => {
          p.x += p.vx
          p.y += p.vy
          if (p.x < 0) p.x = canvas.width
          if (p.x > canvas.width) p.x = 0
          if (p.y < 0) p.y = canvas.height
          if (p.y > canvas.height) p.y = 0

          ctx.beginPath()
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(92, 184, 255, ${p.alpha})`
          ctx.fill()
        })

        // 连线
        for (let i = 0; i < particles.length; i++) {
          for (let j = i + 1; j < particles.length; j++) {
            const dx = particles[i].x - particles[j].x
            const dy = particles[i].y - particles[j].y
            const dist = Math.sqrt(dx * dx + dy * dy)
            if (dist < 120) {
              ctx.beginPath()
              ctx.moveTo(particles[i].x, particles[i].y)
              ctx.lineTo(particles[j].x, particles[j].y)
              ctx.strokeStyle = `rgba(92, 184, 255, ${0.08 * (1 - dist / 120)})`
              ctx.lineWidth = 0.5
              ctx.stroke()
            }
          }
        }

        particleAnimId = requestAnimationFrame(draw)
      }
      draw()
    }

    // ===== 交叉观察器（滚动入场动画） =====
    function initScrollReveal() {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed')
          }
        })
      }, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' })

      nextTick(() => {
        document.querySelectorAll('.stat-card, .tech-card, .gallery-item, .section-header').forEach(el => {
          observer.observe(el)
        })
      })
    }

    onMounted(() => {
      window.addEventListener('scroll', handleScroll, { passive: true })
      initParticles()
      startCarousel()
      initScrollReveal()

      // 延迟触发数字动画
      setTimeout(animateCounts, 600)
    })

    onUnmounted(() => {
      window.removeEventListener('scroll', handleScroll)
      stopCarousel()
      if (particleAnimId) cancelAnimationFrame(particleAnimId)
    })

    return {
      scrollContainer,
      particleCanvas,
      isScrolled,
      carouselIndex,
      hoveredGallery,
      animatedCounts,
      statCards,
      techCards,
      navItems,
      statsData,
      featuresData,
      techData,
      galleryImages,
      carouselNext,
      carouselPrev,
      scrollToSection,
    }
  }
}
</script>

<style scoped>
/* ==========================================
   HomePage - 可视化大屏首页样式
   ========================================== */

.home-page {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  background: var(--bg-deep);
  font-family: 'Inter', 'Microsoft YaHei', sans-serif;
}

/* ===== 粒子背景 ===== */
.particle-bg {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 0;
}

/* ===== 顶部导航条 ===== */
.top-bar {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  padding: 14px 32px;
  transition: all 0.4s ease;
  background: transparent;
}
.top-bar.scrolled {
  background: rgba(2, 11, 24, 0.92);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(30, 80, 180, 0.15);
  padding: 10px 32px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
}
[data-theme="light"] .top-bar.scrolled {
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid rgba(180, 200, 230, 0.35);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.06);
}
.top-bar-inner {
  max-width: 1300px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.logo-area {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo-hex {
  font-size: 26px;
  color: var(--accent);
  text-shadow: 0 0 20px var(--accent-glow);
  animation: logoPulse 3s ease-in-out infinite;
}
@keyframes logoPulse {
  0%, 100% { text-shadow: 0 0 20px var(--accent-glow); }
  50% { text-shadow: 0 0 40px var(--accent-glow), 0 0 60px rgba(92,184,255,0.3); }
}
.logo-text {
  font-family: Rajdhani, monospace;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #c8ddf8, var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.top-nav {
  display: flex;
  align-items: center;
  gap: 28px;
}
.top-nav-link {
  font-size: 13px;
  color: var(--text-dim);
  text-decoration: none;
  letter-spacing: 1px;
  transition: color 0.25s;
  position: relative;
}
.top-nav-link::after {
  content: '';
  position: absolute;
  bottom: -4px; left: 0; right: 0;
  height: 1.5px;
  background: var(--accent);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}
.top-nav-link:hover {
  color: #b8dcff;
}
.top-nav-link:hover::after {
  transform: scaleX(1);
}
.top-nav-cta {
  padding: 7px 20px;
  border: 1px solid rgba(70, 150, 255, 0.4);
  border-radius: 20px;
  font-size: 13px;
  color: var(--accent);
  text-decoration: none;
  letter-spacing: 1px;
  transition: all 0.3s ease;
  background: rgba(12, 40, 90, 0.3);
}
.top-nav-cta:hover {
  background: rgba(20, 60, 140, 0.5);
  border-color: rgba(80, 170, 255, 0.7);
  box-shadow: 0 0 24px rgba(80, 160, 255, 0.3);
  transform: translateY(-1px);
}

/* ===== Hero 主视觉 ===== */
.hero-section {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  z-index: 1;
}
.hero-bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(30, 80, 180, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(30, 80, 180, 0.06) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse 70% 70% at 50% 50%, black 20%, transparent 70%);
}
.hero-content {
  position: relative;
  text-align: center;
  z-index: 2;
  padding: 0 24px;
  max-width: 900px;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 18px;
  border: 1px solid rgba(80, 160, 255, 0.25);
  border-radius: 20px;
  font-size: 12px;
  color: var(--accent);
  letter-spacing: 1.5px;
  margin-bottom: 32px;
  background: rgba(10, 30, 80, 0.3);
  backdrop-filter: blur(8px);
  animation: fadeInUp 0.8s ease-out;
}
.badge-dot {
  width: 6px; height: 6px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent-glow);
  animation: pulse 2s infinite;
}
.hero-title {
  font-family: Rajdhani, 'Microsoft YaHei', sans-serif;
  margin-bottom: 24px;
  animation: fadeInUp 0.8s ease-out 0.15s both;
}
.title-line1 {
  display: block;
  font-size: 22px;
  font-weight: 400;
  color: var(--text-dim);
  letter-spacing: 6px;
  margin-bottom: 8px;
}
.title-line2 {
  display: block;
  font-size: 52px;
  font-weight: 800;
  letter-spacing: 4px;
  margin-bottom: 6px;
  line-height: 1.2;
}
.gradient-text {
  background: linear-gradient(135deg, var(--accent) 0%, #a78bfa 40%, #34d399 70%, var(--accent) 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: gradientShift 4s ease-in-out infinite;
}
@keyframes gradientShift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
.title-line3 {
  display: block;
  font-size: 38px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 3px;
}
.hero-desc {
  font-size: 15px;
  color: var(--text-dim);
  letter-spacing: 1px;
  margin-bottom: 40px;
  animation: fadeInUp 0.8s ease-out 0.3s both;
}
.hero-actions {
  display: flex;
  gap: 18px;
  justify-content: center;
  flex-wrap: wrap;
  animation: fadeInUp 0.8s ease-out 0.45s both;
}
.hero-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 32px;
  border-radius: 28px;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  letter-spacing: 1px;
  transition: all 0.35s ease;
  cursor: pointer;
}
.hero-btn.primary {
  background: linear-gradient(135deg, #2068e0, var(--accent));
  color: #fff;
  border: none;
  box-shadow: 0 4px 24px rgba(32, 104, 224, 0.4);
}
.hero-btn.primary:hover {
  box-shadow: 0 6px 36px rgba(92, 184, 255, 0.5);
  transform: translateY(-2px);
}
.hero-btn.secondary {
  background: transparent;
  border: 1px solid rgba(80, 160, 255, 0.35);
  color: #b8dcff;
}
.hero-btn.secondary:hover {
  background: rgba(20, 60, 140, 0.3);
  border-color: rgba(80, 160, 255, 0.6);
  transform: translateY(-2px);
}

/* ===== 漂浮形状 ===== */
.floating-shapes {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}
.float-shape {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
}
.float-shape.s1 {
  width: 300px; height: 300px;
  background: radial-gradient(circle, var(--accent), transparent 70%);
  top: 10%; left: -5%;
  animation: floatShape 8s ease-in-out infinite;
}
.float-shape.s2 {
  width: 200px; height: 200px;
  background: radial-gradient(circle, #a78bfa, transparent 70%);
  top: 60%; right: -3%;
  animation: floatShape 10s ease-in-out 1s infinite;
}
.float-shape.s3 {
  width: 250px; height: 250px;
  background: radial-gradient(circle, #34d399, transparent 70%);
  bottom: 5%; left: 20%;
  animation: floatShape 9s ease-in-out 2s infinite;
}
.float-shape.s4 {
  width: 150px; height: 150px;
  background: radial-gradient(circle, #f59e0b, transparent 70%);
  top: 20%; right: 15%;
  animation: floatShape 7s ease-in-out 0.5s infinite;
}
.float-shape.s5 {
  width: 180px; height: 180px;
  background: radial-gradient(circle, #ef4444, transparent 70%);
  bottom: 30%; left: 50%;
  animation: floatShape 11s ease-in-out 1.5s infinite;
}
.float-shape.s6 {
  width: 120px; height: 120px;
  background: radial-gradient(circle, #06b6d4, transparent 70%);
  top: 40%; left: 35%;
  animation: floatShape 8.5s ease-in-out 3s infinite;
}
@keyframes floatShape {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(20px, -30px) scale(1.1); }
  50% { transform: translate(-15px, -15px) scale(0.95); }
  75% { transform: translate(10px, 25px) scale(1.05); }
}

/* ===== 滚动提示 ===== */
.scroll-hint {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  z-index: 2;
  animation: fadeInUp 1s ease-out 1s both;
}
.scroll-hint span {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 2px;
}
.scroll-arrow {
  font-size: 24px;
  color: var(--accent);
  animation: bounceDown 1.5s ease-in-out infinite;
}
@keyframes bounceDown {
  0%, 100% { transform: translateY(0); opacity: 0.6; }
  50% { transform: translateY(8px); opacity: 1; }
}

/* ===== Section 通用标题 ===== */
.section-header {
  text-align: center;
  margin-bottom: 50px;
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.7s ease-out;
}
.section-header.revealed {
  opacity: 1;
  transform: translateY(0);
}
.section-title {
  font-family: Rajdhani, monospace;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 3px;
  margin-bottom: 10px;
  background: linear-gradient(90deg, #c8ddf8, var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
[data-theme="light"] .section-title {
  background: linear-gradient(90deg, #2c3e60, var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.section-sub {
  font-size: 12px;
  color: var(--text-dim);
  letter-spacing: 4px;
  text-transform: uppercase;
}

/* ===== 统计区 ===== */
.stats-section {
  position: relative;
  z-index: 1;
  padding: 80px 32px 60px;
  max-width: 1200px;
  margin: 0 auto;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}
.stat-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 28px 20px;
  text-align: center;
  backdrop-filter: blur(8px);
  position: relative;
  overflow: hidden;
  opacity: 0;
  transform: translateY(40px);
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.stat-card.revealed {
  opacity: 1;
  transform: translateY(0);
}
.stat-card::before {
  content: '';
  position: absolute;
  top: -1px; left: 30px; right: 30px;
  height: 1px;
  background: var(--panel-top-line);
}
.stat-card:hover {
  transform: translateY(-4px);
  border-color: var(--border-glow);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
.stat-icon-wrap {
  position: relative;
  display: inline-block;
  margin-bottom: 16px;
}
.stat-icon-bg {
  width: 56px; height: 56px;
  border-radius: 14px;
  opacity: 0.15;
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
}
.stat-icon-emoji {
  position: relative;
  font-size: 28px;
  z-index: 1;
}
.stat-number {
  font-family: Rajdhani, monospace;
  font-size: 34px;
  font-weight: 700;
  color: #c8ddf8;
  margin-bottom: 6px;
}
.stat-unit {
  font-size: 16px;
  font-weight: 400;
  color: var(--text-dim);
  margin-left: 2px;
}
.stat-desc {
  font-size: 13px;
  color: var(--text-dim);
  letter-spacing: 1px;
  margin-bottom: 16px;
}
.stat-bar {
  height: 3px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  overflow: hidden;
}
.stat-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 1.5s cubic-bezier(0.16, 1, 0.3, 1);
  width: 0;
}
.stat-card.revealed .stat-bar-fill {
  /* width set by inline style */
}

/* ===== 功能特性轮播 ===== */
.features-section {
  position: relative;
  z-index: 1;
  padding: 80px 32px;
  max-width: 1200px;
  margin: 0 auto;
}
.carousel-wrap {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
}
.carousel-track {
  display: flex;
  transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.carousel-slide {
  min-width: 100%;
  padding: 0 4px;
}
.feature-card {
  display: flex;
  gap: 40px;
  align-items: center;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 40px;
  backdrop-filter: blur(8px);
}
.feature-visual {
  flex-shrink: 0;
  width: 280px;
}
.feature-mock {
  aspect-ratio: 4/3;
  border-radius: 12px;
  border: 1px solid rgba(80, 160, 255, 0.2);
  position: relative;
  overflow: hidden;
}
.mock-inner {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.mock-icon {
  font-size: 40px;
  margin-bottom: 8px;
}
.mock-title {
  font-size: 13px;
  color: rgba(200, 221, 248, 0.7);
  letter-spacing: 2px;
  margin-bottom: 12px;
}
.mock-preview {
  position: relative;
  width: 100%;
  height: 80px;
}
.mock-dot {
  position: absolute;
  border-radius: 50%;
  background: rgba(92, 184, 255, 0.5);
  animation: dotBlink 2s ease-in-out infinite;
}
@keyframes dotBlink {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.3); }
}
.feature-detail {
  flex: 1;
}
.feature-detail h3 {
  font-family: Rajdhani, monospace;
  font-size: 22px;
  margin-bottom: 12px;
  color: var(--text-primary);
  letter-spacing: 2px;
}
.feature-detail p {
  font-size: 14px;
  color: var(--text-dim);
  line-height: 1.8;
  margin-bottom: 16px;
}
.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  list-style: none;
}
.feature-tags li {
  padding: 4px 14px;
  border-radius: 12px;
  font-size: 11px;
  background: rgba(30, 80, 200, 0.15);
  color: var(--accent);
  border: 1px solid rgba(80, 160, 255, 0.2);
  letter-spacing: 0.5px;
}
/* 轮播箭头 */
.carousel-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 5;
  width: 44px; height: 44px;
  border-radius: 50%;
  border: 1px solid rgba(80, 160, 255, 0.25);
  background: rgba(6, 20, 44, 0.8);
  color: #8abef8;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
  backdrop-filter: blur(8px);
}
.carousel-arrow:hover {
  background: rgba(20, 60, 140, 0.6);
  border-color: rgba(80, 160, 255, 0.5);
  box-shadow: 0 0 20px rgba(80, 160, 255, 0.2);
}
.carousel-arrow.left { left: 12px; }
.carousel-arrow.right { right: 12px; }
/* 轮播指示器 */
.carousel-dots {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 20px;
}
.carousel-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: rgba(80, 160, 255, 0.2);
  cursor: pointer;
  transition: all 0.3s ease;
}
.carousel-dot.active {
  background: var(--accent);
  box-shadow: 0 0 10px var(--accent-glow);
  transform: scale(1.2);
}

/* ===== 技术架构 ===== */
.tech-section {
  position: relative;
  z-index: 1;
  padding: 80px 32px;
  max-width: 1200px;
  margin: 0 auto;
}
.tech-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.tech-card {
  position: relative;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 30px 24px;
  overflow: hidden;
  transition: all 0.4s ease;
  opacity: 0;
  transform: translateY(40px);
}
.tech-card.revealed {
  opacity: 1;
  transform: translateY(0);
}
.tech-card:hover {
  border-color: var(--border-glow);
  transform: translateY(-6px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
}
.tech-card-glow {
  position: absolute;
  top: 0; left: 50%;
  width: 200px; height: 100px;
  transform: translateX(-50%);
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
}
.tech-card:hover .tech-card-glow {
  opacity: 1;
}
.tech-card-content {
  position: relative;
  z-index: 1;
}
.tech-icon-box {
  width: 48px; height: 48px;
  border-radius: 12px;
  border: 2px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  margin-bottom: 16px;
  background: rgba(255, 255, 255, 0.03);
}
.tech-card h3 {
  font-family: Rajdhani, monospace;
  font-size: 15px;
  margin-bottom: 10px;
  color: var(--text-primary);
  letter-spacing: 1px;
}
.tech-card p {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.7;
  margin-bottom: 16px;
}
.tech-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tech-meta-item {
  padding: 3px 10px;
  border-radius: 10px;
  font-size: 10px;
  background: rgba(30, 80, 200, 0.12);
  color: var(--accent);
  letter-spacing: 0.5px;
}

/* ===== 图片展示墙 ===== */
.gallery-section {
  position: relative;
  z-index: 1;
  padding: 80px 32px;
  max-width: 1200px;
  margin: 0 auto;
}
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: 200px;
  gap: 16px;
}
.gallery-item {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--border-subtle);
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.5s ease;
}
.gallery-item.revealed {
  opacity: 1;
  transform: translateY(0);
}
.gallery-item:hover {
  transform: scale(1.03);
  border-color: var(--border-glow);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  z-index: 2;
}
.gallery-wide {
  grid-column: span 2;
}
.gallery-tall {
  grid-row: span 2;
}
.gallery-img-placeholder {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}
.gallery-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    105deg,
    transparent 40%,
    rgba(255, 255, 255, 0.05) 45%,
    rgba(255, 255, 255, 0.08) 50%,
    rgba(255, 255, 255, 0.05) 55%,
    transparent 60%
  );
  background-size: 200% 100%;
  animation: shimmer 3s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.gallery-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.3s ease;
}
.gallery-overlay.show {
  opacity: 1;
}
.gallery-overlay span {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 1px;
}
.gallery-overlay small {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
}

/* ===== CTA 区域 ===== */
.cta-section {
  position: relative;
  z-index: 1;
  padding: 100px 32px;
  text-align: center;
  overflow: hidden;
}
.cta-bg-anim {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 50%, rgba(32, 104, 224, 0.1) 0%, transparent 70%);
  animation: ctaGlow 3s ease-in-out infinite;
}
@keyframes ctaGlow {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
.cta-content {
  position: relative;
  z-index: 2;
}
.cta-content h2 {
  font-family: Rajdhani, monospace;
  font-size: 34px;
  margin-bottom: 16px;
  letter-spacing: 2px;
  color: var(--text-primary);
}
.cta-content p {
  font-size: 15px;
  color: var(--text-dim);
  margin-bottom: 36px;
  letter-spacing: 1px;
}
.cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 16px 40px;
  border-radius: 30px;
  font-size: 16px;
  font-weight: 600;
  text-decoration: none;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #2068e0, var(--accent));
  color: #fff;
  border: none;
  box-shadow: 0 6px 30px rgba(32, 104, 224, 0.4);
  transition: all 0.35s ease;
}
.cta-btn:hover {
  box-shadow: 0 8px 44px rgba(92, 184, 255, 0.55);
  transform: translateY(-3px);
}
.cta-particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.cta-particle {
  position: absolute;
  bottom: -10px;
  width: 4px; height: 4px;
  background: var(--accent);
  border-radius: 50%;
  animation: riseUp linear infinite;
}
@keyframes riseUp {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0.8;
  }
  100% {
    transform: translateY(-400px) scale(0);
    opacity: 0;
  }
}

/* ===== Footer ===== */
.footer {
  position: relative;
  z-index: 1;
  border-top: 1px solid rgba(30, 80, 180, 0.12);
  padding: 24px 32px;
}
.footer-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.footer-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.footer-logo {
  font-family: Rajdhani, monospace;
  font-size: 13px;
  color: var(--accent);
  letter-spacing: 1px;
}
.footer-desc {
  font-size: 11px;
  color: var(--text-dim);
}
.footer-right {
  font-size: 11px;
  color: var(--text-dim);
}

/* ===== 动画关键帧 ===== */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .tech-grid { grid-template-columns: repeat(2, 1fr); }
  .gallery-grid { grid-template-columns: repeat(2, 1fr); }
  .feature-card { flex-direction: column; padding: 24px; }
  .feature-visual { width: 100%; }
  .hero-title .title-line2 { font-size: 36px; }
  .hero-title .title-line3 { font-size: 26px; }
}
@media (max-width: 640px) {
  .stats-grid { grid-template-columns: 1fr; }
  .tech-grid { grid-template-columns: 1fr; }
  .gallery-grid { grid-template-columns: 1fr; }
  .gallery-wide { grid-column: span 1; }
  .gallery-tall { grid-row: span 1; }
  .top-nav { display: none; }
  .hero-title .title-line2 { font-size: 28px; }
  .hero-title .title-line3 { font-size: 20px; }
  .section-title { font-size: 22px; }
}
</style>
