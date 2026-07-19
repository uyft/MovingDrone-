<template>
  <div class="home-new">
    <!-- 背景画布：飞行动画无人机 -->
    <canvas ref="bgCanvas" class="bg-canvas"></canvas>

    <!-- 扫描线效果 -->
    <div class="scan-line"></div>

    <!-- Hero 区域 -->
    <section class="hero">
      <!-- 飞行无人机装饰 (CSS) -->
      <div class="fly-drone drone-1" title="Drone">
        <svg viewBox="0 0 60 60" class="drone-svg">
          <g class="rotor r1"><ellipse cx="12" cy="12" rx="8" ry="3" fill="none" stroke=c.blue stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r2"><ellipse cx="48" cy="12" rx="8" ry="3" fill="none" stroke=c.blue stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r3"><ellipse cx="12" cy="48" rx="8" ry="3" fill="none" stroke=c.blue stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r4"><ellipse cx="48" cy="48" rx="8" ry="3" fill="none" stroke=c.blue stroke-width="1.5" opacity="0.8"/></g>
          <line x1="16" y1="16" x2="30" y2="30" stroke=c.blue stroke-width="1" opacity="0.6"/>
          <line x1="44" y1="16" x2="30" y2="30" stroke=c.blue stroke-width="1" opacity="0.6"/>
          <line x1="16" y1="44" x2="30" y2="30" stroke=c.blue stroke-width="1" opacity="0.6"/>
          <line x1="44" y1="44" x2="30" y2="30" stroke=c.blue stroke-width="1" opacity="0.6"/>
          <circle cx="30" cy="30" r="5" fill="#1a3d7c" stroke=c.blue stroke-width="1.5"/>
          <circle cx="30" cy="30" r="2" fill=c.blue opacity="0.9">
            <animate attributeName="opacity" values="0.4;1;0.4" dur="1.5s" repeatCount="indefinite"/>
          </circle>
        </svg>
        <div class="drone-beam"></div>
      </div>
      <div class="fly-drone drone-2" title="Drone">
        <svg viewBox="0 0 60 60" class="drone-svg">
          <g class="rotor r1"><ellipse cx="12" cy="12" rx="7" ry="2.5" fill="none" stroke="#00d4aa" stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r2"><ellipse cx="48" cy="12" rx="7" ry="2.5" fill="none" stroke="#00d4aa" stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r3"><ellipse cx="12" cy="48" rx="7" ry="2.5" fill="none" stroke="#00d4aa" stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r4"><ellipse cx="48" cy="48" rx="7" ry="2.5" fill="none" stroke="#00d4aa" stroke-width="1.5" opacity="0.8"/></g>
          <line x1="16" y1="16" x2="30" y2="30" stroke="#00d4aa" stroke-width="1" opacity="0.6"/>
          <line x1="44" y1="16" x2="30" y2="30" stroke="#00d4aa" stroke-width="1" opacity="0.6"/>
          <line x1="16" y1="44" x2="30" y2="30" stroke="#00d4aa" stroke-width="1" opacity="0.6"/>
          <line x1="44" y1="44" x2="30" y2="30" stroke="#00d4aa" stroke-width="1" opacity="0.6"/>
          <circle cx="30" cy="30" r="5" fill="#0d4d40" stroke="#00d4aa" stroke-width="1.5"/>
          <circle cx="30" cy="30" r="2" fill="#00d4aa" opacity="0.9">
            <animate attributeName="opacity" values="0.4;1;0.4" dur="1.2s" repeatCount="indefinite"/>
          </circle>
        </svg>
        <div class="drone-beam"></div>
      </div>
      <div class="fly-drone drone-3" title="Drone">
        <svg viewBox="0 0 60 60" class="drone-svg">
          <g class="rotor r1"><ellipse cx="12" cy="12" rx="6" ry="2" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r2"><ellipse cx="48" cy="12" rx="6" ry="2" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r3"><ellipse cx="12" cy="48" rx="6" ry="2" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.8"/></g>
          <g class="rotor r4"><ellipse cx="48" cy="48" rx="6" ry="2" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.8"/></g>
          <line x1="16" y1="16" x2="30" y2="30" stroke="#a78bfa" stroke-width="1" opacity="0.6"/>
          <line x1="44" y1="16" x2="30" y2="30" stroke="#a78bfa" stroke-width="1" opacity="0.6"/>
          <line x1="16" y1="44" x2="30" y2="30" stroke="#a78bfa" stroke-width="1" opacity="0.6"/>
          <line x1="44" y1="44" x2="30" y2="30" stroke="#a78bfa" stroke-width="1" opacity="0.6"/>
          <circle cx="30" cy="30" r="4" fill="#2d1a40" stroke="#a78bfa" stroke-width="1.5"/>
          <circle cx="30" cy="30" r="2" fill="#a78bfa" opacity="0.9">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="1.8s" repeatCount="indefinite"/>
          </circle>
        </svg>
        <div class="drone-beam"></div>
      </div>

      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-dot"></span> AI-Powered Crowd Analysis
        </div>
        <h1 class="hero-title">
          <span class="grad-text">DroneCrowd</span>
        </h1>
        <p class="hero-subtitle">无人机视角 · 智能人群感知 · 时空分布分析</p>
        <p class="hero-desc">基于深度学习的无人机航拍人群计数与多维可视化平台</p>
        <div class="hero-actions">
          <button class="btn-primary" @click="$router.push('/overview')">
            <span class="btn-icon">◈</span> 进入分析平台
          </button>
          <button class="btn-ghost" @click="$router.push('/compare')">
            <span class="btn-icon">◉</span> 模型对比
          </button>
        </div>
        <div class="hero-stats">
          <div class="hstat" v-for="s in heroStats" :key="s.label">
            <strong>{{ s.value }}</strong>
            <span>{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- 底部雷达波 -->
      <div class="radar-rings">
        <div class="ring r1"></div>
        <div class="ring r2"></div>
        <div class="ring r3"></div>
      </div>
    </section>

    <!-- 数据集展示 -->
    <section class="showcase-section">
      <h2 class="section-title">
        <span class="title-icon">◆</span>
        <span class="title-text">MDC++ 数据集</span>
        <span class="title-line"></span>
      </h2>
      <p class="section-sub">首个无人机视角动态密集人群数据集，覆盖多场景、多尺度、多密度</p>
      <div class="showcase-grid">
        <div class="showcase-card" v-for="(img, i) in showcaseImages" :key="i"
             @mouseenter="hoverCard = i" @mouseleave="hoverCard = -1"
             :class="{ hovered: hoverCard === i }">
          <div class="showcase-img-wrap">
            <img :src="img.src" :alt="img.title" class="showcase-img" />
            <div class="showcase-overlay">
              <span class="showcase-zoom">⊕ 查看详情</span>
            </div>
            <!-- 光效边框 -->
            <div class="glow-border"></div>
          </div>
          <div class="showcase-info">
            <h4>{{ img.title }}</h4>
            <p>{{ img.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 核心功能 -->
    <section class="features-section">
      <h2 class="section-title">
        <span class="title-icon">◆</span>
        <span class="title-text">核心能力</span>
        <span class="title-line"></span>
      </h2>
      <div class="features-grid">
        <div class="feature-card" v-for="f in features" :key="f.title"
             @click="$router.push(f.route)"
             :style="{ animationDelay: f.delay + 's' }">
          <div class="feature-icon-wrap">
            <svg viewBox="0 0 40 40" class="feature-drone-icon">
              <ellipse cx="10" cy="10" rx="5" ry="1.8" fill="none" :stroke="f.color" stroke-width="1.2" opacity="0.7"/>
              <ellipse cx="30" cy="10" rx="5" ry="1.8" fill="none" :stroke="f.color" stroke-width="1.2" opacity="0.7"/>
              <ellipse cx="10" cy="30" rx="5" ry="1.8" fill="none" :stroke="f.color" stroke-width="1.2" opacity="0.7"/>
              <ellipse cx="30" cy="30" rx="5" ry="1.8" fill="none" :stroke="f.color" stroke-width="1.2" opacity="0.7"/>
              <line x1="13" y1="13" x2="20" y2="20" :stroke="f.color" stroke-width="0.8" opacity="0.5"/>
              <line x1="27" y1="13" x2="20" y2="20" :stroke="f.color" stroke-width="0.8" opacity="0.5"/>
              <line x1="13" y1="27" x2="20" y2="20" :stroke="f.color" stroke-width="0.8" opacity="0.5"/>
              <line x1="27" y1="27" x2="20" y2="20" :stroke="f.color" stroke-width="0.8" opacity="0.5"/>
              <circle cx="20" cy="20" r="3.5" fill="none" :stroke="f.color" stroke-width="1.2"/>
              <circle cx="20" cy="20" r="1.5" :fill="f.color" opacity="0.9">
                <animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite"/>
              </circle>
            </svg>
          </div>
          <h4>{{ f.title }}</h4>
          <p>{{ f.desc }}</p>
          <div class="card-glow"></div>
        </div>
      </div>
    </section>

    <!-- 页脚 -->
    <footer class="home-footer">
      <div class="footer-line"></div>
      <p>DroneCrowd Platform · UAV-based Crowd Analysis</p>
    </footer>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { getChartColors } from '../echartsTheme.js'

export default {
  name: 'HomeNew',
  setup() {
    const c = getChartColors()
    const bgCanvas = ref(null)
    const hoverCard = ref(-1)
    let animId = null
    let canvasCtx = null
    let drones = []
    let stars = []
    let signalRings = []
    let width = 0, height = 0

    const heroStats = [
      { value: '4+', label: 'AI 模型' },
      { value: '实时', label: '推理速度' },
      { value: '6', label: '分析维度' },
      { value: '3D', label: '可视化' },
    ]

    const showcaseImages = [
      { src: '/figures/dataset_example.png', title: '数据集样本', desc: '多场景无人机航拍人群标注' },
      { src: '/figures/datasets_comparison.png', title: '数据集对比', desc: 'MDC++ 与其他数据集全面对比' },
      { src: '/figures/Tracking_results_on_MDC++.png', title: '追踪效果', desc: 'MDC++ 上多目标追踪结果' },
      { src: '/figures/VIC_results_on_MDC++.png', title: '计数结果', desc: 'VIC 模型在 MDC++ 上的表现' },
    ]

    const features = [
      { title: '人群计数', desc: 'STEERER · GD³A · STNNet 多模型协同', route: '/dashboard', color: c.blue, delay: 0 },
      { title: '密度热力图', desc: '六种配色 · 等高线叠加 · 实时渲染', route: '/heatmap', color: '#00d4aa', delay: 0.1 },
      { title: '3D 空间分析', desc: '密度地形 · 运动玫瑰图 · 空间热力网格', route: '/spatial', color: '#a78bfa', delay: 0.2 },
      { title: '多模型对比', desc: '雷达图 · 柱状图 · 散点对比分析', route: '/compare', color: '#f59e0b', delay: 0.3 },
    ]

    // --- Canvas 无人机动画 ---
    class CanvasDrone {
      constructor(w, h) {
        this.w = w; this.h = h
        this.reset()
      }
      reset() {
        this.x = Math.random() * this.w
        this.y = Math.random() * this.h * 0.7
        this.size = 6 + Math.random() * 8
        this.speed = 0.3 + Math.random() * 0.8
        this.angle = Math.random() * Math.PI * 2
        this.waypointX = Math.random() * this.w
        this.waypointY = Math.random() * this.h * 0.7
        this.rotorAngle = Math.random() * Math.PI * 2
        this.rotorSpeed = 0.08 + Math.random() * 0.15
        this.hue = [195, 165, 260, 35][Math.floor(Math.random() * 4)]
        this.trail = []
        this.beamPulse = Math.random() * Math.PI * 2
      }
      update() {
        // 飞向航点
        const dx = this.waypointX - this.x
        const dy = this.waypointY - this.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < 20) {
          this.waypointX = Math.random() * this.w
          this.waypointY = Math.random() * this.h * 0.7
        }
        const vx = (dx / dist) * this.speed
        const vy = (dy / dist) * this.speed
        // 加一些波动
        this.x += vx + Math.sin(Date.now() * 0.002 + this.y * 0.01) * 0.3
        this.y += vy + Math.cos(Date.now() * 0.003 + this.x * 0.01) * 0.2
        this.rotorAngle += this.rotorSpeed
        this.beamPulse += 0.03

        // 尾迹
        this.trail.push({ x: this.x, y: this.y, life: 1 })
        if (this.trail.length > 25) this.trail.shift()
        this.trail.forEach(t => t.life -= 0.04)
      }
      draw(ctx) {
        const s = this.size
        const x = this.x, y = this.y

        // 光束（向下照射）
        const beamAlpha = 0.06 + Math.sin(this.beamPulse) * 0.03
        const beamGrad = ctx.createRadialGradient(x, y, s * 0.5, x, y + s * 8, s * 6)
        beamGrad.addColorStop(0, `hsla(${this.hue}, 80%, 65%, ${beamAlpha * 2})`)
        beamGrad.addColorStop(1, 'transparent')
        ctx.fillStyle = beamGrad
        ctx.beginPath()
        ctx.ellipse(x, y + s * 5, s * 6, s * 12, 0, 0, Math.PI * 2)
        ctx.fill()

        // 尾迹
        for (let i = 0; i < this.trail.length; i++) {
          const t = this.trail[i]
          if (t.life <= 0) continue
          ctx.fillStyle = `hsla(${this.hue}, 80%, 65%, ${t.life * 0.5})`
          ctx.beginPath()
          ctx.arc(t.x, t.y, s * 0.25 * t.life, 0, Math.PI * 2)
          ctx.fill()
        }

        ctx.save()
        ctx.translate(x, y)

        // 旋翼旋转光晕
        const armLen = s * 1.2
        const armAngles = [Math.PI / 4, -Math.PI / 4, Math.PI + Math.PI / 4, Math.PI - Math.PI / 4]
        const color = `hsl(${this.hue}, 80%, 65%)`

        // 四个旋翼
        for (let i = 0; i < 4; i++) {
          const ax = Math.cos(armAngles[i]) * armLen
          const ay = Math.sin(armAngles[i]) * armLen

          // 旋翼光盘
          ctx.save()
          ctx.translate(ax, ay)
          ctx.rotate(this.rotorAngle * (i % 2 === 0 ? 1 : -1))
          ctx.strokeStyle = color
          ctx.lineWidth = 1
          ctx.globalAlpha = 0.35 + Math.sin(this.beamPulse + i) * 0.15
          ctx.beginPath()
          ctx.ellipse(0, 0, s * 0.9, s * 0.25, 0, 0, Math.PI * 2)
          ctx.stroke()
          ctx.beginPath()
          ctx.ellipse(0, 0, s * 0.5, s * 0.15, 0, 0, Math.PI * 2)
          ctx.stroke()
          ctx.globalAlpha = 1
          ctx.restore()

          // 机臂
          ctx.strokeStyle = color
          ctx.lineWidth = 0.8
          ctx.globalAlpha = 0.5
          ctx.beginPath()
          ctx.moveTo(0, 0)
          ctx.lineTo(ax, ay)
          ctx.stroke()
          ctx.globalAlpha = 1
        }

        // 中心机体
        const bodyGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, s * 0.6)
        bodyGrad.addColorStop(0, '#fff')
        bodyGrad.addColorStop(0.3, color)
        bodyGrad.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = bodyGrad
        ctx.beginPath()
        ctx.arc(0, 0, s * 0.55, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = color
        ctx.lineWidth = 1.2
        ctx.stroke()

        // LED 闪烁点
        ctx.fillStyle = '#fff'
        ctx.beginPath()
        ctx.arc(0, 0, s * 0.2, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = color
        ctx.globalAlpha = 0.5 + Math.sin(this.beamPulse * 3) * 0.5
        ctx.beginPath()
        ctx.arc(0, 0, s * 0.35, 0, Math.PI * 2)
        ctx.fill()
        ctx.globalAlpha = 1

        ctx.restore()
      }
    }

    function initCanvas() {
      const cvs = bgCanvas.value
      if (!cvs) return
      canvasCtx = cvs.getContext('2d')
      resize()
      window.addEventListener('resize', resize)

      // 初始化星星
      stars = []
      for (let i = 0; i < 150; i++) {
        stars.push({
          x: Math.random() * width,
          y: Math.random() * height,
          r: Math.random() * 1.5,
          twinkle: Math.random() * Math.PI * 2,
          speed: 0.01 + Math.random() * 0.03,
        })
      }

      // 初始化信号环
      signalRings = []
      for (let i = 0; i < 3; i++) {
        signalRings.push({
          x: width * (0.25 + Math.random() * 0.5),
          y: height * (0.2 + Math.random() * 0.5),
          radius: 0,
          maxRadius: 80 + Math.random() * 120,
          speed: 0.4 + Math.random() * 0.8,
          life: 1,
        })
      }

      // 初始化无人机
      drones = []
      for (let i = 0; i < 6; i++) {
        drones.push(new CanvasDrone(width, height))
      }

      animate()
    }

    function resize() {
      const cvs = bgCanvas.value
      if (!cvs) return
      width = window.innerWidth
      height = window.innerHeight
      cvs.width = width
      cvs.height = height
    }

    function animate() {
      const ctx = canvasCtx
      if (!ctx) return

      ctx.clearRect(0, 0, width, height)

      // 背景渐变
      const bgGrad = ctx.createRadialGradient(width * 0.5, height * 0.3, 0, width * 0.5, height * 0.5, Math.max(width, height))
      bgGrad.addColorStop(0, '#0d1b3e')
      bgGrad.addColorStop(0.5, '#060d1a')
      bgGrad.addColorStop(1, '#02040a')
      ctx.fillStyle = bgGrad
      ctx.fillRect(0, 0, width, height)

      // 星星
      stars.forEach(s => {
        s.twinkle += s.speed
        const alpha = 0.25 + Math.sin(s.twinkle) * 0.25
        ctx.fillStyle = `rgba(180,210,255,${alpha})`
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fill()
      })

      // 信号环
      signalRings.forEach(ring => {
        ring.radius += ring.speed
        ring.life = 1 - ring.radius / ring.maxRadius
        if (ring.life <= 0) {
          ring.radius = 0
          ring.life = 1
          ring.x = width * (0.2 + Math.random() * 0.6)
          ring.y = height * (0.15 + Math.random() * 0.55)
          ring.maxRadius = 60 + Math.random() * 140
        }
        ctx.strokeStyle = `rgba(77,166,255,${ring.life * 0.25})`
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(ring.x, ring.y, ring.radius, 0, Math.PI * 2)
        ctx.stroke()
      })

      // 无人机
      drones.forEach(d => {
        d.w = width; d.h = height
        d.update()
        d.draw(ctx)
      })

      animId = requestAnimationFrame(animate)
    }

    onMounted(() => {
      nextTick(() => initCanvas())
    })

    onUnmounted(() => {
      if (animId) cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    })

    return { bgCanvas, hoverCard, heroStats, showcaseImages, features }
  }
}
</script>

<style scoped>
/* ========== 基础 ========== */
.home-new {
  position: relative; min-height: 100vh;
  background: #02040a; color: var(--text-primary);
  overflow-x: hidden;
}

.bg-canvas {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  z-index: 0; pointer-events: none;
}

/* 扫描线 */
.scan-line {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: repeating-linear-gradient(
    0deg,
    transparent, transparent 2px,
    rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px
  );
  z-index: 1; pointer-events: none;
}

/* ========== 飞行无人机装饰 (CSS) ========== */
.fly-drone {
  position: absolute; z-index: 2; pointer-events: none;
  width: 80px; height: 80px;
}
.drone-svg { width: 100%; height: 100%; }
.drone-beam {
  position: absolute; bottom: -60px; left: 50%; transform: translateX(-50%);
  width: 40px; height: 70px;
  background: radial-gradient(ellipse at center, rgba(77,166,255,0.25) 0%, transparent 70%);
  border-radius: 50%;
}

.drone-1 {
  top: 12%; left: 10%;
  animation: fly-path-1 14s ease-in-out infinite;
}
.drone-2 {
  top: 20%; right: 8%;
  animation: fly-path-2 16s ease-in-out infinite;
}
.drone-3 {
  top: 55%; left: 5%;
  animation: fly-path-3 18s ease-in-out infinite;
}

@keyframes fly-path-1 {
  0%, 100% { transform: translate(0, 0) rotate(-3deg); }
  25% { transform: translate(60px, -30px) rotate(2deg); }
  50% { transform: translate(120px, 20px) rotate(-2deg); }
  75% { transform: translate(40px, 40px) rotate(3deg); }
}
@keyframes fly-path-2 {
  0%, 100% { transform: translate(0, 0) rotate(4deg); }
  25% { transform: translate(-80px, -20px) rotate(-2deg); }
  50% { transform: translate(-140px, 30px) rotate(3deg); }
  75% { transform: translate(-50px, 50px) rotate(-4deg); }
}
@keyframes fly-path-3 {
  0%, 100% { transform: translate(0, 0) rotate(-2deg); }
  33% { transform: translate(100px, -50px) rotate(3deg); }
  66% { transform: translate(60px, -10px) rotate(-2deg); }
}

/* 旋翼旋转 */
.rotor { transform-origin: center; }
.r1 { animation: spin-rotor 0.3s linear infinite; }
.r2 { animation: spin-rotor 0.35s linear infinite reverse; }
.r3 { animation: spin-rotor 0.32s linear infinite reverse; }
.r4 { animation: spin-rotor 0.28s linear infinite; }
@keyframes spin-rotor {
  to { transform: rotate(360deg); }
}

/* ========== Hero ========== */
.hero {
  position: relative; z-index: 2;
  min-height: 100vh; display: flex; align-items: center;
  justify-content: center; overflow: hidden;
}

.hero-content {
  text-align: center; max-width: 720px; padding: 0 24px;
  display: flex; flex-direction: column; align-items: center;
}

.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; font-weight: 700; letter-spacing: 0.14em;
  padding: 6px 18px; border-radius: 24px;
  border: 1px solid rgba(77,166,255,0.3);
  background: rgba(77,166,255,0.06);
  color: #6db6ff;
  margin-bottom: 28px;
  text-transform: uppercase;
  font-family: Rajdhani, sans-serif;
}
.badge-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent), 0 0 16px var(--accent);
  animation: badge-pulse 2s ease-in-out infinite;
}
@keyframes badge-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.hero-title { margin: 0 0 12px; }
.grad-text {
  font-family: Rajdhani, sans-serif;
  font-size: 72px; font-weight: 900; letter-spacing: 0.04em;
  background: linear-gradient(135deg, var(--accent) 0%, #00d4aa 40%, #a78bfa 70%, var(--accent) 100%);
  background-size: 300% 300%;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: grad-shift 4s ease-in-out infinite;
  filter: drop-shadow(0 0 30px rgba(77,166,255,0.4)) drop-shadow(0 0 60px rgba(0,212,170,0.2));
}
@keyframes grad-shift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.hero-subtitle {
  font-size: 20px; font-weight: 600; letter-spacing: 0.06em;
  color: #b0c8e8;
  margin: 0 0 10px;
  text-shadow: 0 0 20px rgba(77,166,255,0.3);
}
.hero-desc {
  font-size: 15px; color: rgba(255,255,255,0.4);
  margin: 0 0 36px; letter-spacing: 0.03em;
}

.hero-actions {
  display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
}

.btn-primary, .btn-ghost {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 36px; border-radius: 10px;
  font-size: 15px; font-weight: 700; letter-spacing: 0.04em;
  cursor: pointer; transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  border: none; font-family: inherit;
  position: relative; overflow: hidden;
}
.btn-icon { font-size: 16px; }
.btn-primary {
  background: linear-gradient(135deg, #1a5ce0, #3d8bff);
  color: #fff;
  box-shadow: 0 0 30px rgba(47,111,237,0.4), 0 8px 32px rgba(0,0,0,0.4);
}
.btn-primary::after {
  content: '';
  position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  transition: left 0.6s;
}
.btn-primary:hover::after { left: 100%; }
.btn-primary:hover {
  transform: translateY(-3px);
  box-shadow: 0 0 50px rgba(47,111,237,0.6), 0 12px 40px rgba(0,0,0,0.5);
}

.btn-ghost {
  background: transparent; color: #7a9ec8;
  border: 1px solid rgba(122,158,200,0.3);
}
.btn-ghost:hover {
  border-color: var(--accent); color: var(--accent);
  box-shadow: 0 0 20px var(--accent-glow);
  transform: translateY(-2px);
}

.hero-stats {
  display: flex; gap: 40px; justify-content: center; margin-top: 56px; flex-wrap: wrap;
}
.hstat { text-align: center; }
.hstat strong {
  display: block; font-size: 32px; color: #fff; font-weight: 900;
  font-family: Rajdhani, sans-serif;
  text-shadow: 0 0 20px rgba(77,166,255,0.4);
}
.hstat span {
  font-size: 11px; color: var(--text-dim); text-transform: uppercase;
  letter-spacing: 0.12em; margin-top: 4px; display: block;
}

/* 底部雷达波 */
.radar-rings {
  position: absolute; bottom: -40px; left: 50%; transform: translateX(-50%);
  z-index: 1;
}
.ring {
  position: absolute; border-radius: 50%;
  border: 1px solid var(--accent-glow);
  top: 50%; left: 50%; transform: translate(-50%, -50%);
  animation: ring-expand 4s ease-out infinite;
}
.r1 { width: 100px; height: 100px; animation-delay: 0s; }
.r2 { width: 100px; height: 100px; animation-delay: 1.3s; }
.r3 { width: 100px; height: 100px; animation-delay: 2.6s; }
@keyframes ring-expand {
  0% { width: 60px; height: 60px; opacity: 0.6; }
  100% { width: 600px; height: 600px; opacity: 0; }
}

/* ========== Section Titles ========== */
.section-title {
  display: flex; align-items: center; justify-content: center; gap: 14px;
  margin: 0 0 12px;
}
.title-icon {
  color: var(--accent); font-size: 14px;
  text-shadow: 0 0 12px var(--accent);
}
.title-text {
  font-family: Rajdhani, sans-serif;
  font-size: 28px; font-weight: 700; letter-spacing: 0.06em;
  color: #e0e8f0;
  text-shadow: 0 0 24px rgba(77,166,255,0.3);
}
.title-line {
  display: inline-block; width: 60px; height: 1px;
  background: linear-gradient(90deg, rgba(77,166,255,0.6), transparent);
}
.section-sub {
  text-align: center; color: var(--text-dim); font-size: 14px;
  margin: 0 0 40px; letter-spacing: 0.03em;
}

/* ========== 数据集展示 ========== */
.showcase-section {
  position: relative; z-index: 2;
  padding: 80px 24px; max-width: 1200px; margin: 0 auto;
}
.showcase-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;
}
.showcase-card {
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px; overflow: hidden;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
}
.showcase-card:hover {
  transform: translateY(-6px);
  border-color: rgba(77,166,255,0.3);
  box-shadow: 0 16px 48px rgba(0,0,0,0.5), 0 0 30px rgba(77,166,255,0.1);
}
.showcase-img-wrap {
  position: relative; overflow: hidden; aspect-ratio: 16/10;
  background: #0a1226;
}
.showcase-img {
  width: 100%; height: 100%; object-fit: cover;
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
.showcase-card:hover .showcase-img {
  transform: scale(1.06);
}
.showcase-overlay {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.35s;
}
.showcase-card:hover .showcase-overlay { opacity: 1; }
.showcase-zoom {
  color: #fff; font-size: 14px; font-weight: 600;
  padding: 8px 20px; border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.3);
  background: rgba(0,0,0,0.5);
}
.glow-border {
  position: absolute; inset: 0;
  border-radius: 0;
  box-shadow: inset 0 0 0 0 rgba(77,166,255,0);
  transition: box-shadow 0.4s;
  pointer-events: none;
}
.showcase-card:hover .glow-border {
  box-shadow: inset 0 0 40px var(--accent-glow);
}
.showcase-info { padding: 16px 18px; }
.showcase-info h4 {
  font-size: 15px; margin: 0 0 4px; color: #e0e8f0; font-weight: 700;
}
.showcase-info p {
  font-size: 12px; color: var(--text-dim); margin: 0;
}

/* ========== 核心功能 ========== */
.features-section {
  position: relative; z-index: 2;
  padding: 80px 24px 100px; max-width: 1000px; margin: 0 auto;
}
.features-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;
}
.feature-card {
  position: relative;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px; padding: 32px 22px; cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  animation: card-in 0.6s ease-out both;
  overflow: hidden;
  text-align: center;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
.card-glow {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 120px; height: 120px; border-radius: 50%;
  background: radial-gradient(circle, rgba(77,166,255,0.08) 0%, transparent 70%);
  opacity: 0; transition: opacity 0.4s;
  pointer-events: none;
}
.feature-card:hover .card-glow { opacity: 1; }
.feature-card:hover {
  transform: translateY(-6px);
  border-color: rgba(77,166,255,0.3);
  box-shadow: 0 16px 48px rgba(0,0,0,0.5);
  background: rgba(47,111,237,0.04);
}
.feature-icon-wrap {
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 16px;
}
.feature-drone-icon {
  width: 44px; height: 44px;
  filter: drop-shadow(0 0 8px currentColor);
}
.feature-card h4 {
  font-size: 17px; margin: 0 0 8px; color: #fff; font-weight: 700;
  letter-spacing: 0.04em;
}
.feature-card p {
  color: var(--text-dim); font-size: 13px; margin: 0; line-height: 1.6;
}

/* ========== 页脚 ========== */
.home-footer {
  position: relative; z-index: 2;
  text-align: center; padding: 40px 24px;
  color: rgba(255,255,255,0.15); font-size: 12px;
  letter-spacing: 0.06em;
}
.footer-line {
  width: 80px; height: 1px; margin: 0 auto 16px;
  background: linear-gradient(90deg, transparent, rgba(77,166,255,0.3), transparent);
}

/* ========== 响应式 ========== */
@media (max-width: 900px) {
  .showcase-grid { grid-template-columns: repeat(2, 1fr); }
  .features-grid { grid-template-columns: repeat(2, 1fr); }
  .grad-text { font-size: 48px; }
  .hero-stats { gap: 24px; }
  .fly-drone { display: none; }
}
@media (max-width: 500px) {
  .showcase-grid { grid-template-columns: 1fr; }
  .features-grid { grid-template-columns: 1fr; }
  .grad-text { font-size: 36px; }
  .hero-badge { font-size: 10px; padding: 4px 12px; }
}
</style>
