<template>
  <div class="splash" @click="skip">
    <canvas ref="mainCanvas"></canvas>
    <div class="overlay">
      <!-- 标题 -->
      <div class="title-group">
        <h1 class="glitch" data-text="DroneCrowd">DroneCrowd</h1>
        <div class="divider"><span class="divider-dot"></span></div>
      </div>

      <!-- 进度 -->
      <div class="loader">
        <div class="loader-track"><div class="loader-fill" :style="{ width: progress + '%' }"></div></div>
        <span class="loader-num">{{ progress }}</span>
      </div>
    </div>

    <!-- 底部装饰线 -->
    <div class="bottom-deco">
      <span class="deco-line"></span>
      <span class="deco-diamond">◆</span>
      <span class="deco-line"></span>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

export default {
  name: 'TransitionPage',
  setup() {
    const router = useRouter()
    const mainCanvas = ref(null)
    const progress = ref(0)
    let animId = null, ctx = null, w = 0, h = 0

    // ── 无人机粒子 ──
    const drones = []
    const DRONE_COUNT = 60

    class Drone {
      constructor() {
        this.reset()
        this.y = Math.random() * h
      }
      reset() {
        this.x = -30
        this.y = Math.random() * h
        this.speed = 1.2 + Math.random() * 3.5
        this.size = 2 + Math.random() * 2.5
        this.hue = 200 + Math.random() * 50
        this.glow = 0.5 + Math.random() * 0.5
        this.phase = Math.random() * Math.PI * 2
        this.amplitude = 0.3 + Math.random() * 1.2
        this.trail = []
        this.trailLen = Math.floor(8 + Math.random() * 14)
      }
      update() {
        this.phase += 0.04 + Math.random() * 0.04
        this.x += this.speed
        this.y += Math.sin(this.phase) * this.amplitude
        this.trail.push({ x: this.x, y: this.y, life: 1 })
        if (this.trail.length > this.trailLen) this.trail.shift()
        this.trail.forEach(t => t.life -= 0.06)
        if (this.x > w + 40) this.reset()
      }
      draw(ctx) {
        for (let i = 0; i < this.trail.length; i++) {
          const t = this.trail[i]
          if (t.life <= 0) continue
          ctx.beginPath()
          ctx.arc(t.x, t.y, this.size * 0.3 * t.life, 0, Math.PI * 2)
          ctx.fillStyle = `hsla(${this.hue}, 90%, 60%, ${t.life * 0.45})`
          ctx.fill()
        }
        const alpha = this.glow * (0.65 + 0.35 * Math.sin(this.phase * 2))
        ctx.beginPath()
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2)
        ctx.fillStyle = `hsla(${this.hue}, 100%, 72%, ${alpha})`
        ctx.fill()
        ctx.beginPath()
        ctx.arc(this.x, this.y, this.size * 2.5, 0, Math.PI * 2)
        ctx.fillStyle = `hsla(${this.hue}, 100%, 60%, ${alpha * 0.12})`
        ctx.fill()
      }
    }

    // ── 背景星点 ──
    const stars = []
    const STAR_COUNT = 80
    class Star {
      constructor() {
        this.x = Math.random() * w
        this.y = Math.random() * h
        this.r = 0.3 + Math.random() * 0.8
        this.twinkle = Math.random() * Math.PI * 2
        this.speed = 0.008 + Math.random() * 0.025
      }
      update() { this.twinkle += this.speed }
      draw(ctx) {
        const a = 0.15 + 0.2 * Math.sin(this.twinkle)
        ctx.beginPath()
        ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(150,200,255,${a})`
        ctx.fill()
      }
    }

    // ── 信号波纹 ──
    const rings = []
    class SignalRing {
      constructor() {
        this.radius = 0
        this.maxRadius = Math.min(w, h) * 0.45
        this.speed = 0.4 + Math.random() * 0.6
        this.alpha = 0
        this.delay = Math.random() * 200
        this.timer = 0
      }
      update() {
        this.timer++
        if (this.timer < this.delay) return
        this.radius += this.speed
        this.alpha = Math.max(0, 1 - this.radius / this.maxRadius)
        if (this.radius > this.maxRadius) {
          this.radius = 0; this.timer = 0
          this.delay = 80 + Math.random() * 200
        }
      }
      draw(ctx) {
        if (this.timer < this.delay) return
        ctx.beginPath()
        ctx.arc(w / 2, h / 2, this.radius, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(47, 130, 237, ${this.alpha * 0.08})`
        ctx.lineWidth = 1
        ctx.stroke()
      }
    }

    function init() {
      const canvas = mainCanvas.value
      if (!canvas) return
      ctx = canvas.getContext('2d')
      resize()
      window.addEventListener('resize', resize)

      drones.length = 0
      for (let i = 0; i < DRONE_COUNT; i++) drones.push(new Drone())

      stars.length = 0
      for (let i = 0; i < STAR_COUNT; i++) stars.push(new Star())

      rings.length = 0
      for (let i = 0; i < 3; i++) rings.push(new SignalRing())

      animate()

      // 模拟加载 — 1 秒内完成
      const intv = setInterval(() => {
        progress.value = Math.min(100, Math.floor(progress.value + Math.random() * 2 + 9))
        if (progress.value >= 100) {
          clearInterval(intv)
          setTimeout(() => skip(), 200)
        }
      }, 100)

      onUnmounted(() => clearInterval(intv))
    }

    function resize() {
      const canvas = mainCanvas.value
      if (!canvas) return
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
    }

    function skip() { router.push('/home') }

    function animate() {
      if (!ctx) return
      ctx.fillStyle = 'rgba(2, 8, 22, 0.28)'
      ctx.fillRect(0, 0, w, h)

      stars.forEach(s => { s.update(); s.draw(ctx) })
      rings.forEach(r => { r.update(); r.draw(ctx) })
      drones.forEach(d => { d.update(); d.draw(ctx) })

      const cx = w / 2, cy = h / 2
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(w, h) * 0.38)
      grad.addColorStop(0, 'rgba(30, 80, 180, 0.05)')
      grad.addColorStop(0.5, 'rgba(10, 40, 120, 0.03)')
      grad.addColorStop(1, 'rgba(2, 8, 22, 0)')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, w, h)

      animId = requestAnimationFrame(animate)
    }

    onMounted(init)
    onUnmounted(() => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    })

    return { mainCanvas, progress, skip }
  }
}
</script>

<style scoped>
.splash {
  position: fixed; inset: 0; z-index: 9999;
  background: #020816; cursor: pointer; overflow: hidden;
}
.splash canvas { position: absolute; inset: 0; }

/* ── 覆盖层 ── */
.overlay {
  position: relative; z-index: 2;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  height: 100%; pointer-events: none;
}

/* ── 标题 ── */
.title-group { text-align: center; margin-bottom: 48px; }
.title-group h1 {
  font-size: 68px; font-weight: 900; letter-spacing: 0.06em;
  color: #fff; margin: 0;
  text-shadow: 0 0 50px rgba(47,111,237,0.45), 0 0 100px rgba(0,159,145,0.2);
}

/* Glitch */
.glitch { position: relative; }
.glitch::before, .glitch::after {
  content: attr(data-text); position: absolute; top: 0; left: 0;
  width: 100%; height: 100%;
}
.glitch::before {
  left: 2px; text-shadow: -2px 0 #ff3050;
  clip: rect(44px, 450px, 56px, 0);
  animation: glitch-a 5s infinite linear alternate-reverse;
}
.glitch::after {
  left: -2px; text-shadow: -2px 0 var(--accent, #4da6ff);
  clip: rect(44px, 450px, 56px, 0);
  animation: glitch-b 5s infinite linear alternate-reverse;
}
@keyframes glitch-a {
  0% { clip: rect(30px,9999px,48px,0); }
  20% { clip: rect(76px,9999px,110px,0); }
  40% { clip: rect(8px,9999px,28px,0); }
  60% { clip: rect(92px,9999px,108px,0); }
  80% { clip: rect(42px,9999px,66px,0); }
  100% { clip: rect(58px,9999px,84px,0); }
}
@keyframes glitch-b {
  0% { clip: rect(62px,9999px,78px,0); }
  20% { clip: rect(16px,9999px,38px,0); }
  40% { clip: rect(104px,9999px,118px,0); }
  60% { clip: rect(46px,9999px,70px,0); }
  80% { clip: rect(72px,9999px,96px,0); }
  100% { clip: rect(2px,9999px,22px,0); }
}

/* 分割线 */
.divider {
  display: flex; align-items: center; justify-content: center;
  margin-top: 20px;
}
.divider::before, .divider::after {
  content: ''; display: block; width: 50px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(77,166,255,0.35));
}
.divider::after {
  background: linear-gradient(90deg, rgba(77,166,255,0.35), transparent);
}
.divider-dot {
  display: block; width: 5px; height: 5px; border-radius: 50%;
  background: var(--accent, #4da6ff); margin: 0 14px;
  box-shadow: 0 0 10px rgba(77,166,255,0.6);
}

/* ── 进度条 ── */
.loader {
  display: flex; align-items: center; gap: 12px; width: 260px;
}
.loader-track {
  flex: 1; height: 2px; background: rgba(255,255,255,0.08);
  border-radius: 2px; overflow: hidden;
}
.loader-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(90deg, #2f6fed, var(--accent, #4da6ff), #009f91);
  background-size: 200% 100%;
  transition: width 0.3s;
  box-shadow: 0 0 12px rgba(47,111,237,0.5);
  animation: loader-shimmer 1.5s ease-in-out infinite;
}
@keyframes loader-shimmer {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
.loader-num {
  color: rgba(255,255,255,0.35); font-size: 12px; font-weight: 700;
  min-width: 28px; text-align: right; font-variant-numeric: tabular-nums;
}

/* ── 底部装饰 ── */
.bottom-deco {
  position: absolute; bottom: 28px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 10px;
  z-index: 2; pointer-events: none;
}
.deco-line {
  display: block; width: 80px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12));
}
.deco-line:last-child {
  background: linear-gradient(90deg, rgba(255,255,255,0.12), transparent);
}
.deco-diamond {
  font-size: 6px; color: rgba(255,255,255,0.15);
}

@media (max-width: 768px) {
  .title-group h1 { font-size: 40px; }
  .divider::before, .divider::after { width: 30px; }
}
</style>
