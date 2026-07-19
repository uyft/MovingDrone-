<template>
  <main class="splash" :class="{ leaving }">
    <div ref="stageRef" class="stage" aria-hidden="true"></div>

    <div class="grain" aria-hidden="true"></div>
    <div class="vignette" aria-hidden="true"></div>
    <div class="scanlines" aria-hidden="true"></div>

    <header class="topbar">
      <div class="brand">
        <span class="brand-icon">
          <svg viewBox="0 0 48 48" aria-hidden="true">
            <path d="M19 19 10 10M29 19l9-9M19 29l-9 9M29 29l9 9" />
            <circle cx="24" cy="24" r="5" />
            <ellipse cx="8" cy="8" rx="6" ry="2.5" transform="rotate(45 8 8)" />
            <ellipse cx="40" cy="8" rx="6" ry="2.5" transform="rotate(-45 40 8)" />
            <ellipse cx="8" cy="40" rx="6" ry="2.5" transform="rotate(-45 8 40)" />
            <ellipse cx="40" cy="40" rx="6" ry="2.5" transform="rotate(45 40 40)" />
          </svg>
        </span>
        <div>
          <strong>DroneCrowd</strong>
          <small>UAV CROWD INTELLIGENCE</small>
        </div>
      </div>

      <button class="skip" type="button" @click="enterPlatform">
        SKIP INTRO <span>↗</span>
      </button>
    </header>

    <aside class="chapter-rail">
      <span class="rail-title">SYSTEM SEQUENCE</span>
      <div
        v-for="(item, index) in chapters"
        :key="item.code"
        class="chapter"
        :class="{ active: index === chapterIndex, passed: index < chapterIndex }"
      >
        <i>{{ item.code }}</i>
        <span>{{ item.short }}</span>
      </div>
    </aside>

    <section v-if="chapterIndex !== chapters.length - 1" class="story" :key="activeChapter.code">
      <div class="kicker">
        <span>{{ activeChapter.code }}</span>
        <i></i>
        <span>{{ activeChapter.kicker }}</span>
      </div>
      <h1 v-html="activeChapter.title"></h1>
      <p>{{ activeChapter.description }}</p>
    </section>

    <section class="telemetry" :class="{ visible: chapterIndex >= 1 }">
      <div class="telemetry-head">
        <span>LIVE TELEMETRY</span>
        <i></i>
      </div>
      <div class="metrics">
        <article>
          <small>DETECTED</small>
          <strong>{{ animatedPeople.toLocaleString() }}</strong>
          <span>PERSONS</span>
        </article>
        <article>
          <small>DENSITY</small>
          <strong>{{ densityValue }}</strong>
          <span>PERSON / m²</span>
        </article>
        <article>
          <small>RISK</small>
          <strong :class="riskClass">{{ riskText }}</strong>
          <span>REAL-TIME</span>
        </article>
        <article>
          <small>INFERENCE</small>
          <strong>{{ inferenceValue }}</strong>
          <span>MS / FRAME</span>
        </article>
      </div>
    </section>

    <div class="status" :class="{ visible: chapterIndex >= 1 }">
      <span class="status-dot"><i></i></span>
      <div>
        <small>{{ activeChapter.statusLabel }}</small>
        <strong>{{ activeChapter.statusValue }}</strong>
      </div>
      <em>{{ String(progress).padStart(3, '0') }}%</em>
    </div>

    <section class="final" :class="{ visible: chapterIndex === chapters.length - 1 }">
      <div class="final-eyebrow">MULTI-SCALE CROWD ANALYSIS & VISUALIZATION</div>
      <h2>DroneCrowd</h2>
      <p>无人机人群智能感知平台</p>
      <div class="features">
        <span>人群计数</span><i></i><span>密度热力</span><i></i><span>轨迹追踪</span><i></i><span>空间分析</span>
      </div>
      <button class="enter" type="button" @click="enterPlatform">
        <span>ENTER PLATFORM</span>
        <b>进入平台</b>
        <i>→</i>
      </button>
    </section>

    <footer class="footer">
      <div class="footer-meta">
        <span>{{ activeChapter.footer }}</span>
        <span>{{ timecode }}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
        <span
          v-for="n in chapters.length"
          :key="n"
          class="progress-node"
          :class="{ active: n - 1 <= chapterIndex }"
          :style="{ left: `${((n - 1) / (chapters.length - 1)) * 100}%` }"
        ></span>
      </div>
    </footer>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as THREE from 'three'

const router = useRouter()
const stageRef = ref(null)
const progress = ref(0)
const chapterIndex = ref(0)
const animatedPeople = ref(0)
const densityValue = ref('0.00')
const inferenceValue = ref('—')
const elapsedUi = ref(0)
const leaving = ref(false)

const DURATION = 15.5
const CROWD_COUNT = 980

const chapters = [
  {
    code: '01', short: 'FLIGHT', kicker: 'AUTONOMOUS FLIGHT PATH',
    title: '穿越现场，<br><em>飞向目标区域。</em>',
    description: '无人机沿三维航线高速入场，实时调整姿态并持续锁定地面目标。',
    statusLabel: 'FLIGHT CONTROL', statusValue: 'ROUTE LOCKED',
    footer: 'CALCULATING OPTIMAL OBSERVATION PATH',
  },
  {
    code: '02', short: 'SCAN', kicker: 'CROWD FIELD ACQUIRED',
    title: '一次俯瞰，<br><em>识别人群分布。</em>',
    description: '扫描光束覆盖现场，逐步锁定行人目标并建立空间坐标。',
    statusLabel: 'CROWD SCANNING', statusValue: 'FIELD ACQUIRED',
    footer: 'EXTRACTING MULTI-SCALE CROWD FEATURES',
  },
  {
    code: '03', short: 'DENSITY', kicker: 'DENSITY FIELD ONLINE',
    title: '从位置到密度，<br><em>看见拥挤风险。</em>',
    description: '低密度到高密度区域以蓝、绿、黄、红热力层级实时呈现。',
    statusLabel: 'DENSITY ENGINE', statusValue: 'HEAT FIELD READY',
    footer: 'GENERATING DENSITY HEAT FIELD',
  },
  {
    code: '04', short: 'TRACK', kicker: 'TRAJECTORY MODEL ONLINE',
    title: '不止知道多少，<br><em>更理解如何流动。</em>',
    description: '连续追踪行人运动方向、速度和轨迹，辅助判断潜在拥堵趋势。',
    statusLabel: 'TRAJECTORY MODEL', statusValue: 'PREDICTING',
    footer: 'MODELING CROWD FLOW AND CONGESTION RISK',
  },
  {
    code: '05', short: 'READY', kicker: 'INTELLIGENCE READY',
    title: '让每一次俯瞰，<br><em>成为安全决策。</em>',
    description: '从无人机画面到实时态势，完成计数、密度、轨迹与空间分析。',
    statusLabel: 'SYSTEM STATUS', statusValue: 'ALL MODULES READY',
    footer: 'DRONECROWD INTELLIGENCE PLATFORM READY',
  },
]

const activeChapter = computed(() => chapters[chapterIndex.value])
const riskText = computed(() => {
  if (chapterIndex.value < 1) return '—'
  if (chapterIndex.value < 3) return 'MEDIUM'
  return 'CONTROLLED'
})
const riskClass = computed(() => (riskText.value === 'MEDIUM' ? 'risk-medium' : 'risk-safe'))
const timecode = computed(() => `00:${Math.min(DURATION, elapsedUi.value).toFixed(1).padStart(4, '0')} / 00:${DURATION.toFixed(1)}`)

let scene
let camera
let renderer
let clock
let rafId
let resizeObserver
let uiTimer
let disposed = false

let drone
let rotorNodes = []
let flightCurve
let scanBeam
let scanRing
let sweepLine
let groundGrid
let bodyInstances
let headInstances
let crowdData = []
let heatZones = []
let detectionFrames = []
let trajectoryLines = []
let trajectoryDots = []

const tempObject = new THREE.Object3D()
const tempColor = new THREE.Color()
const lookMatrix = new THREE.Matrix4()
const cameraTarget = new THREE.Vector3()
const cameraDesired = new THREE.Vector3()

function enterPlatform() {
  if (leaving.value) return
  leaving.value = true
  window.setTimeout(() => router.push('/transition'), 650)
}

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function densityColor(value) {
  if (value < 0.33) return new THREE.Color('#38bdf8')
  if (value < 0.58) return new THREE.Color('#34d399')
  if (value < 0.78) return new THREE.Color('#facc15')
  return new THREE.Color('#fb5f68')
}

function createScene() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#060a0c')
  scene.fog = new THREE.FogExp2('#071012', 0.026)

  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 160)
  camera.position.set(-17, 9, 24)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.08
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  stageRef.value.appendChild(renderer.domElement)

  const hemi = new THREE.HemisphereLight('#d9f8ff', '#111816', 1.55)
  scene.add(hemi)

  const key = new THREE.DirectionalLight('#e8fbff', 3.2)
  key.position.set(-8, 18, 10)
  key.castShadow = true
  key.shadow.mapSize.set(2048, 2048)
  key.shadow.camera.left = -28
  key.shadow.camera.right = 28
  key.shadow.camera.top = 28
  key.shadow.camera.bottom = -28
  scene.add(key)

  const rim = new THREE.PointLight('#4fdcff', 20, 45, 2)
  rim.position.set(8, 7, 2)
  scene.add(rim)

  createGround()
  createCrowd()
  createDrone()
  createScanSystem()
  createHeatField()
  createTrajectories()
  createDetectionFrames()

  flightCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-25, 13, 30),
    new THREE.Vector3(-17, 11, 18),
    new THREE.Vector3(-8, 9.5, 9),
    new THREE.Vector3(2, 8.2, 4),
    new THREE.Vector3(7, 7.1, -1.5),
    new THREE.Vector3(3.5, 6.6, -4.5),
    new THREE.Vector3(0, 6.2, -1.2),
  ], false, 'catmullrom', 0.45)
}

function createGround() {
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(70, 50),
    new THREE.MeshStandardMaterial({ color: '#111a18', roughness: 0.96, metalness: 0.04 }),
  )
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  scene.add(ground)

  groundGrid = new THREE.GridHelper(62, 62, '#385b56', '#1c2b29')
  groundGrid.position.y = 0.018
  groundGrid.material.transparent = true
  groundGrid.material.opacity = 0.25
  scene.add(groundGrid)

  const pad = new THREE.Mesh(
    new THREE.CircleGeometry(11.5, 96),
    new THREE.MeshBasicMaterial({ color: '#0b1717', transparent: true, opacity: 0.58 }),
  )
  pad.rotation.x = -Math.PI / 2
  pad.position.y = 0.025
  scene.add(pad)
}

function randomGaussian() {
  let u = 0
  let v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

function createCrowd() {
  const clusters = [
    { x: -5.3, z: -2.4, sx: 3.0, sz: 2.2, weight: 0.82 },
    { x: 1.0, z: 1.5, sx: 3.5, sz: 2.6, weight: 1.00 },
    { x: 6.0, z: -1.1, sx: 2.4, sz: 2.0, weight: 0.9 },
    { x: -0.8, z: -5.4, sx: 2.8, sz: 1.8, weight: 0.76 },
  ]

  const bodyGeometry = new THREE.CylinderGeometry(0.09, 0.12, 0.48, 6)
  const headGeometry = new THREE.SphereGeometry(0.105, 8, 6)
  const material = new THREE.MeshStandardMaterial({ color: '#9da8a4', roughness: 0.72, metalness: 0.02 })

  bodyInstances = new THREE.InstancedMesh(bodyGeometry, material.clone(), CROWD_COUNT)
  headInstances = new THREE.InstancedMesh(headGeometry, material.clone(), CROWD_COUNT)
  bodyInstances.castShadow = true
  headInstances.castShadow = true
  bodyInstances.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
  headInstances.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
  scene.add(bodyInstances, headInstances)

  crowdData = []
  for (let i = 0; i < CROWD_COUNT; i += 1) {
    const c = clusters[Math.floor(Math.random() * clusters.length)]
    const x = c.x + randomGaussian() * c.sx
    const z = c.z + randomGaussian() * c.sz
    const distance = Math.sqrt(((x - c.x) / c.sx) ** 2 + ((z - c.z) / c.sz) ** 2)
    const density = clamp01((1.08 - distance * 0.52) * c.weight + Math.random() * 0.13)
    const scale = 0.82 + Math.random() * 0.38
    const angle = Math.random() * Math.PI * 2
    crowdData.push({ x, z, density, scale, angle, revealed: 0 })

    tempObject.position.set(x, 0.26 * scale, z)
    tempObject.rotation.y = angle
    tempObject.scale.set(scale, scale, scale)
    tempObject.updateMatrix()
    bodyInstances.setMatrixAt(i, tempObject.matrix)

    tempObject.position.set(x, 0.61 * scale, z)
    tempObject.updateMatrix()
    headInstances.setMatrixAt(i, tempObject.matrix)

    tempColor.set('#67706e')
    bodyInstances.setColorAt(i, tempColor)
    headInstances.setColorAt(i, tempColor)
  }
  bodyInstances.instanceColor.needsUpdate = true
  headInstances.instanceColor.needsUpdate = true
}

function createDrone() {
  drone = new THREE.Group()
  scene.add(drone)

  const white = new THREE.MeshStandardMaterial({ color: '#edf4f2', roughness: 0.26, metalness: 0.42 })
  const dark = new THREE.MeshStandardMaterial({ color: '#0b1113', roughness: 0.3, metalness: 0.65 })
  const cyan = new THREE.MeshStandardMaterial({ color: '#57e7ff', emissive: '#2acbe9', emissiveIntensity: 3.5 })

  const body = new THREE.Mesh(new THREE.BoxGeometry(1.65, 0.45, 1.05), white)
  body.geometry.translate(0, 0.02, 0)
  body.castShadow = true
  drone.add(body)

  const canopy = new THREE.Mesh(new THREE.SphereGeometry(0.52, 24, 12), dark)
  canopy.scale.set(1.15, 0.42, 0.88)
  canopy.position.set(0, 0.25, 0.02)
  drone.add(canopy)

  const frontLight = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.035, 0.045), cyan)
  frontLight.position.set(0, 0.08, -0.55)
  drone.add(frontLight)

  const cameraHousing = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.32, 0.34), dark)
  cameraHousing.position.set(0, -0.38, -0.46)
  drone.add(cameraHousing)

  const lens = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.08, 24), cyan)
  lens.rotation.x = Math.PI / 2
  lens.position.set(0, -0.38, -0.66)
  drone.add(lens)

  const armMaterial = white.clone()
  const armGeometry = new THREE.BoxGeometry(1.75, 0.11, 0.14)
  const motorGeometry = new THREE.CylinderGeometry(0.18, 0.2, 0.22, 20)
  const bladeGeometry = new THREE.BoxGeometry(1.25, 0.025, 0.09)

  const armAngles = [Math.PI / 4, -Math.PI / 4, Math.PI * 3 / 4, -Math.PI * 3 / 4]
  armAngles.forEach((angle, index) => {
    const arm = new THREE.Mesh(armGeometry, armMaterial)
    arm.position.set(Math.cos(angle) * 0.8, 0.01, Math.sin(angle) * 0.8)
    arm.rotation.y = -angle
    arm.castShadow = true
    drone.add(arm)

    const motor = new THREE.Mesh(motorGeometry, dark)
    motor.position.set(Math.cos(angle) * 1.6, 0.05, Math.sin(angle) * 1.6)
    motor.castShadow = true
    drone.add(motor)

    const rotor = new THREE.Group()
    rotor.position.copy(motor.position)
    rotor.position.y += 0.16

    const bladeA = new THREE.Mesh(bladeGeometry, white)
    const bladeB = new THREE.Mesh(bladeGeometry, white)
    bladeB.rotation.y = Math.PI / 2
    rotor.add(bladeA, bladeB)

    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.78, 0.018, 8, 64),
      new THREE.MeshBasicMaterial({ color: index % 2 === 0 ? '#76f3ff' : '#d8fbff', transparent: true, opacity: 0.45 }),
    )
    ring.rotation.x = Math.PI / 2
    rotor.add(ring)

    rotorNodes.push(rotor)
    drone.add(rotor)
  })

  drone.scale.setScalar(1.18)
}

function createScanSystem() {
  scanBeam = new THREE.Mesh(
    new THREE.ConeGeometry(5.8, 8.5, 64, 1, true),
    new THREE.MeshBasicMaterial({ color: '#4ee9ff', transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }),
  )
  scanBeam.rotation.x = Math.PI
  scene.add(scanBeam)

  scanRing = new THREE.Mesh(
    new THREE.RingGeometry(0.92, 1.0, 96),
    new THREE.MeshBasicMaterial({ color: '#66efff', transparent: true, opacity: 0, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }),
  )
  scanRing.rotation.x = -Math.PI / 2
  scanRing.position.y = 0.05
  scene.add(scanRing)

  sweepLine = new THREE.Mesh(
    new THREE.PlaneGeometry(18, 0.08),
    new THREE.MeshBasicMaterial({ color: '#8af6ff', transparent: true, opacity: 0, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }),
  )
  sweepLine.rotation.x = -Math.PI / 2
  sweepLine.position.y = 0.08
  scene.add(sweepLine)
}

function makeHeatTexture(color) {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  const context = canvas.getContext('2d')
  const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128)
  gradient.addColorStop(0, `${color}e0`)
  gradient.addColorStop(0.28, `${color}8c`)
  gradient.addColorStop(0.65, `${color}35`)
  gradient.addColorStop(1, `${color}00`)
  context.fillStyle = gradient
  context.fillRect(0, 0, 256, 256)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function createHeatField() {
  const configs = [
    { x: -5.3, z: -2.4, size: 8.0, color: '#34d399' },
    { x: 1.0, z: 1.5, size: 10.5, color: '#fb5f68' },
    { x: 6.0, z: -1.1, size: 7.0, color: '#facc15' },
    { x: -0.8, z: -5.4, size: 6.5, color: '#38bdf8' },
  ]

  configs.forEach((cfg) => {
    const material = new THREE.MeshBasicMaterial({
      map: makeHeatTexture(cfg.color),
      transparent: true,
      opacity: 0,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(cfg.size, cfg.size), material)
    plane.rotation.x = -Math.PI / 2
    plane.position.set(cfg.x, 0.035, cfg.z)
    scene.add(plane)
    heatZones.push(plane)
  })
}

function createTrajectories() {
  const paths = [
    [[-10, -4], [-6, -2], [-2, 0], [3, 1], [8, 4]],
    [[-8, 5], [-4, 3], [0, 2], [4, 0], [9, -2]],
    [[-9, 0], [-5, 1], [-1, -1], [3, -3], [7, -5]],
    [[-3, 7], [-1, 4], [2, 2], [5, -1], [7, -4]],
    [[7, 6], [4, 4], [1, 1], [-2, -2], [-6, -4]],
  ]
  const pathColors = ['#54e9ff', '#34d399', '#facc15', '#60a5fa', '#fb7185']

  paths.forEach((points, index) => {
    const curve = new THREE.CatmullRomCurve3(points.map(([x, z]) => new THREE.Vector3(x, 0.2, z)))
    const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(90))
    const material = new THREE.LineBasicMaterial({ color: pathColors[index], transparent: true, opacity: 0, blending: THREE.AdditiveBlending })
    const line = new THREE.Line(geometry, material)
    scene.add(line)
    trajectoryLines.push({ line, curve })

    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 12, 8),
      new THREE.MeshBasicMaterial({ color: pathColors[index], transparent: true, opacity: 0 }),
    )
    scene.add(dot)
    trajectoryDots.push({ dot, curve, offset: index / paths.length })
  })
}

function createDetectionFrames() {
  const frameMaterial = new THREE.LineBasicMaterial({ color: '#7ff5ff', transparent: true, opacity: 0, blending: THREE.AdditiveBlending })
  for (let i = 0; i < 34; i += 1) {
    const person = crowdData[Math.floor(Math.random() * crowdData.length)]
    const geometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(0.42, 0.9, 0.42))
    const frame = new THREE.LineSegments(geometry, frameMaterial.clone())
    frame.position.set(person.x, 0.46, person.z)
    scene.add(frame)
    detectionFrames.push(frame)
  }
}

function updateDrone(elapsed) {
  const flightT = clamp01(elapsed / 5.4)
  const eased = easeInOut(flightT)
  const point = flightCurve.getPointAt(eased)
  const tangent = flightCurve.getTangentAt(Math.min(0.999, eased + 0.002)).normalize()

  if (flightT < 1) {
    drone.position.copy(point)
    lookMatrix.lookAt(new THREE.Vector3(), tangent, new THREE.Vector3(0, 1, 0))
    drone.quaternion.slerp(new THREE.Quaternion().setFromRotationMatrix(lookMatrix), 0.18)
    drone.rotation.z = -tangent.x * 0.34
    drone.rotation.x += Math.sin(elapsed * 4) * 0.002
  } else {
    const hover = elapsed - 5.4
    drone.position.set(
      Math.sin(hover * 0.35) * 1.2,
      6.2 + Math.sin(hover * 1.4) * 0.16,
      -1.2 + Math.cos(hover * 0.3) * 0.85,
    )
    drone.rotation.y = Math.sin(hover * 0.28) * 0.2
    drone.rotation.z = Math.sin(hover * 0.7) * 0.025
    drone.rotation.x = Math.cos(hover * 0.55) * 0.018
  }

  rotorNodes.forEach((rotor, index) => {
    rotor.rotation.y += (index % 2 === 0 ? 1 : -1) * 0.62
  })
}

function updateCamera(elapsed) {
  if (elapsed < 5.4) {
    const t = clamp01(elapsed / 5.4)
    const p = flightCurve.getPointAt(easeInOut(t))
    const tangent = flightCurve.getTangentAt(Math.min(0.999, t + 0.003)).normalize()
    cameraDesired.copy(p).add(new THREE.Vector3(-tangent.x * 6 - 4, 3.3, -tangent.z * 6 + 7))
    cameraTarget.copy(p).add(tangent.clone().multiplyScalar(3.5))
  } else if (elapsed < 9.4) {
    const t = (elapsed - 5.4) / 4
    const angle = -0.8 + t * 1.45
    cameraDesired.set(Math.cos(angle) * 16, 9.5 - t * 2, Math.sin(angle) * 16)
    cameraTarget.set(0, 1.25, -0.6)
  } else if (elapsed < 12.6) {
    const t = (elapsed - 9.4) / 3.2
    cameraDesired.set(12 - t * 4, 6.2 + t * 4.8, 13 - t * 4)
    cameraTarget.set(0, 0.8, -0.5)
  } else {
    const t = clamp01((elapsed - 12.6) / 2.9)
    cameraDesired.set(10 + t * 6, 11 + t * 3, 18 + t * 5)
    cameraTarget.set(0, 1.4, -0.8)
  }

  camera.position.lerp(cameraDesired, 0.055)
  camera.lookAt(cameraTarget)
}

function updateScan(elapsed) {
  const active = clamp01((elapsed - 5.15) / 0.8) * (1 - clamp01((elapsed - 10.2) / 0.65))
  scanBeam.visible = active > 0.001
  scanBeam.material.opacity = active * (0.09 + Math.sin(elapsed * 4.2) * 0.018)
  scanBeam.position.set(drone.position.x, drone.position.y - 4.05, drone.position.z)
  scanBeam.scale.set(0.72 + active * 0.28, 1, 0.72 + active * 0.28)

  const ringT = clamp01((elapsed - 5.4) / 4.5)
  scanRing.material.opacity = ringT < 1 ? 0.62 * (1 - ringT) : 0
  scanRing.scale.setScalar(0.6 + ringT * 13.5)
  scanRing.position.x = drone.position.x
  scanRing.position.z = drone.position.z

  const sweepT = clamp01((elapsed - 5.55) / 3.85)
  sweepLine.material.opacity = sweepT > 0 && sweepT < 1 ? 0.75 : 0
  sweepLine.position.x = -9 + sweepT * 18
  sweepLine.position.z = 0

  if (elapsed > 5.4 && elapsed < 9.7) {
    const scanX = -10 + clamp01((elapsed - 5.4) / 4.3) * 20
    crowdData.forEach((person, index) => {
      const reveal = clamp01((scanX - person.x + 0.9) / 1.8)
      if (reveal <= person.revealed) return
      person.revealed = reveal
      tempColor.copy(densityColor(person.density)).lerp(new THREE.Color('#6b7471'), 1 - reveal)
      bodyInstances.setColorAt(index, tempColor)
      headInstances.setColorAt(index, tempColor)
    })
    bodyInstances.instanceColor.needsUpdate = true
    headInstances.instanceColor.needsUpdate = true
  }
}

function updateAnalysis(elapsed) {
  const heatAlpha = clamp01((elapsed - 7.0) / 2.2)
  heatZones.forEach((zone, index) => {
    zone.material.opacity = heatAlpha * (0.58 + Math.sin(elapsed * 1.5 + index) * 0.06)
  })

  const frameAlpha = clamp01((elapsed - 6.2) / 1.1) * (1 - clamp01((elapsed - 10.8) / 1.1))
  detectionFrames.forEach((frame, index) => {
    frame.material.opacity = frameAlpha * (index % 3 === 0 ? 0.78 : 0.46)
    frame.position.y = 0.46 + Math.sin(elapsed * 2 + index) * 0.012
  })

  const trackAlpha = clamp01((elapsed - 9.1) / 1.3)
  trajectoryLines.forEach(({ line }) => {
    line.material.opacity = trackAlpha * 0.72
  })
  trajectoryDots.forEach(({ dot, curve, offset }, index) => {
    dot.material.opacity = trackAlpha
    const t = (elapsed * 0.09 + offset) % 1
    dot.position.copy(curve.getPointAt(t))
    dot.position.y += 0.11 + Math.sin(elapsed * 4 + index) * 0.025
  })
}

function updateUi(elapsed) {
  elapsedUi.value = elapsed
  progress.value = Math.min(100, Math.round((elapsed / DURATION) * 100))

  const boundaries = [0, 3.1, 6.0, 9.3, 12.5]
  let nextIndex = 0
  boundaries.forEach((boundary, index) => {
    if (elapsed >= boundary) nextIndex = index
  })
  chapterIndex.value = Math.min(chapters.length - 1, nextIndex)

  const detectionProgress = clamp01((elapsed - 5.5) / 4.5)
  animatedPeople.value = Math.round(CROWD_COUNT * detectionProgress)
  densityValue.value = detectionProgress > 0 ? (0.42 + detectionProgress * 1.31).toFixed(2) : '0.00'
  inferenceValue.value = detectionProgress > 0 ? String(22 + Math.floor(Math.sin(elapsed * 3) * 3 + 4)) : '—'
}

function animate() {
  if (disposed) return
  const elapsed = Math.min(clock.getElapsedTime(), DURATION)

  updateDrone(elapsed)
  updateCamera(elapsed)
  updateScan(elapsed)
  updateAnalysis(elapsed)

  groundGrid.material.opacity = 0.19 + Math.sin(elapsed * 0.8) * 0.035
  renderer.render(scene, camera)
  rafId = requestAnimationFrame(animate)
}

function resize() {
  if (!renderer || !stageRef.value) return
  const { clientWidth, clientHeight } = stageRef.value
  renderer.setSize(clientWidth, clientHeight, false)
  camera.aspect = clientWidth / Math.max(clientHeight, 1)
  camera.updateProjectionMatrix()
}

function disposeScene() {
  scene?.traverse((object) => {
    object.geometry?.dispose?.()
    if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose?.())
    else object.material?.dispose?.()
    object.material?.map?.dispose?.()
  })
  renderer?.dispose()
  renderer?.domElement?.remove()
}

onMounted(() => {
  createScene()
  resize()
  clock = new THREE.Clock()
  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(stageRef.value)
  uiTimer = window.setInterval(() => updateUi(Math.min(clock.getElapsedTime(), DURATION)), 80)
  animate()
})

onBeforeUnmount(() => {
  disposed = true
  cancelAnimationFrame(rafId)
  clearInterval(uiTimer)
  resizeObserver?.disconnect()
  disposeScene()
})
</script>

<style scoped>
.splash {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: 9999;
  color: #e7f0ed;
  background: #060a0c;
  font-family: Inter, "Noto Sans SC", "Microsoft YaHei", sans-serif;
  transition: opacity 0.65s ease, filter 0.65s ease;
}
.splash.leaving { opacity: 0; filter: blur(12px); }
.stage { position: absolute; inset: 0; }
.stage :deep(canvas) { display: block; width: 100%; height: 100%; }
.grain,
.vignette,
.scanlines { position: absolute; inset: 0; pointer-events: none; }
.grain {
  opacity: 0.09;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.45'/%3E%3C/svg%3E");
  mix-blend-mode: soft-light;
  animation: grainShift 0.23s steps(2) infinite;
}
.vignette { box-shadow: inset 0 0 190px 70px rgba(0, 0, 0, 0.72); }
.scanlines {
  opacity: 0.055;
  background: repeating-linear-gradient(to bottom, transparent 0, transparent 3px, rgba(255,255,255,.14) 4px);
}
.topbar {
  position: absolute;
  z-index: 5;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28px 38px;
}
.brand { display: flex; align-items: center; gap: 13px; }
.brand-icon {
  width: 43px;
  height: 43px;
  display: grid;
  place-items: center;
  color: #8cecf5;
  border: 1px solid rgba(140,236,245,.28);
  background: rgba(13, 25, 25, .56);
  backdrop-filter: blur(16px);
}
.brand-icon svg { width: 27px; fill: none; stroke: currentColor; stroke-width: 1.65; }
.brand strong { display: block; font-size: 17px; letter-spacing: .08em; }
.brand small { display: block; margin-top: 4px; color: rgba(220,240,235,.48); font-size: 9px; letter-spacing: .28em; }
.skip {
  border: 0;
  background: transparent;
  color: rgba(226,242,238,.62);
  font-size: 10px;
  letter-spacing: .24em;
  cursor: pointer;
}
.skip span { margin-left: 8px; color: #8cecf5; }
.chapter-rail {
  position: absolute;
  z-index: 5;
  left: 38px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.rail-title { margin-bottom: 10px; color: rgba(220,240,235,.34); font-size: 8px; letter-spacing: .28em; }
.chapter { position: relative; display: flex; align-items: center; gap: 11px; color: rgba(220,240,235,.28); transition: color .35s ease; }
.chapter::before { content: ""; width: 14px; height: 1px; background: currentColor; transition: width .35s ease; }
.chapter i { font-style: normal; font: 600 10px/1 Rajdhani, sans-serif; }
.chapter span { font-size: 8px; letter-spacing: .18em; }
.chapter.active { color: #a8f4f5; }
.chapter.active::before { width: 29px; box-shadow: 0 0 14px #77eff4; }
.chapter.passed { color: rgba(168,244,245,.5); }
.story {
  position: absolute;
  z-index: 5;
  left: 16%;
  top: 20%;
  width: min(560px, 38vw);
  animation: copyIn .8s cubic-bezier(.2,.8,.2,1) both;
}
.kicker { display: flex; align-items: center; gap: 12px; color: #96e8eb; font-size: 9px; letter-spacing: .24em; }
.kicker i { width: 52px; height: 1px; background: linear-gradient(90deg, #80e8ec, transparent); }
.story h1 { margin: 22px 0 15px; font: 600 clamp(34px, 4vw, 67px)/1.06 Rajdhani, "Noto Sans SC", sans-serif; letter-spacing: -.025em; }
.story h1 :deep(em) { color: #9ceef0; font-style: normal; font-weight: 400; text-shadow: 0 0 34px rgba(114,231,236,.2); }
.story p { max-width: 480px; color: rgba(222,238,234,.56); font-size: 13px; line-height: 1.85; letter-spacing: .045em; }
.telemetry {
  position: absolute;
  z-index: 5;
  right: 38px;
  top: 29%;
  width: 218px;
  padding: 17px;
  border: 1px solid rgba(139,231,234,.16);
  background: rgba(8, 18, 18, .57);
  backdrop-filter: blur(18px);
  opacity: 0;
  transform: translateX(26px);
  transition: .65s ease;
}
.telemetry.visible { opacity: 1; transform: translateX(0); }
.telemetry-head { display: flex; align-items: center; gap: 9px; color: #8de7e9; font-size: 8px; letter-spacing: .23em; }
.telemetry-head i { flex: 1; height: 1px; background: linear-gradient(90deg, rgba(133,234,238,.5), transparent); }
.metrics { margin-top: 11px; display: grid; grid-template-columns: 1fr 1fr; }
.metrics article { min-height: 78px; padding: 12px 9px; border-top: 1px solid rgba(255,255,255,.055); }
.metrics article:nth-child(odd) { border-right: 1px solid rgba(255,255,255,.055); }
.metrics small, .metrics span { display: block; color: rgba(222,239,235,.34); font-size: 7px; letter-spacing: .15em; }
.metrics strong { display: block; margin: 7px 0 5px; color: #a8f4f5; font: 600 23px/1 Rajdhani, sans-serif; }
.metrics .risk-medium { color: #ffd26a; }
.metrics .risk-safe { color: #68e6ad; }
.status {
  position: absolute;
  z-index: 5;
  right: 38px;
  bottom: 122px;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 250px;
  padding: 13px 15px;
  border: 1px solid rgba(137,232,235,.15);
  background: rgba(8,17,17,.54);
  backdrop-filter: blur(15px);
  opacity: 0;
  transform: translateY(16px);
  transition: .55s ease;
}
.status.visible { opacity: 1; transform: translateY(0); }
.status-dot { width: 26px; height: 26px; display: grid; place-items: center; border: 1px solid rgba(135,238,241,.28); border-radius: 50%; }
.status-dot i { width: 6px; height: 6px; border-radius: 50%; background: #8ff4f5; box-shadow: 0 0 13px #8ff4f5; animation: pulse 1.1s infinite; }
.status div { flex: 1; }
.status small { display: block; color: rgba(221,239,235,.34); font-size: 7px; letter-spacing: .17em; }
.status strong { display: block; margin-top: 4px; color: #a7eef0; font-size: 9px; letter-spacing: .13em; }
.status em { color: #a6f3f4; font: 600 20px/1 Rajdhani, sans-serif; font-style: normal; }
.final {
  position: absolute;
  z-index: 8;
  left: 50%;
  top: 50%;
  width: min(760px, 88vw);
  text-align: center;
  transform: translate(-50%, -43%);
  opacity: 0;
  pointer-events: none;
  transition: opacity .85s ease, transform .85s ease;
}
.final.visible { opacity: 1; transform: translate(-50%, -50%); pointer-events: auto; }
.final-eyebrow { color: #94e9ec; font-size: 9px; letter-spacing: .36em; }
.final h2 { margin: 18px 0 4px; color: #eef8f5; font: 700 clamp(66px, 9vw, 134px)/.9 Rajdhani, sans-serif; letter-spacing: -.02em; text-shadow: 0 0 60px rgba(130,235,239,.15); }
.final p { color: rgba(224,241,237,.72); font-size: 20px; letter-spacing: .18em; }
.features { margin-top: 22px; display: flex; justify-content: center; align-items: center; gap: 12px; color: rgba(225,242,238,.46); font-size: 10px; letter-spacing: .13em; }
.features i { width: 3px; height: 3px; border-radius: 50%; background: #86e7ea; }
.enter {
  margin-top: 30px;
  min-width: 248px;
  padding: 14px 18px;
  display: inline-grid;
  grid-template-columns: 1fr auto;
  text-align: left;
  border: 1px solid rgba(143,237,240,.4);
  color: #eaf7f4;
  background: rgba(10,23,23,.72);
  backdrop-filter: blur(18px);
  cursor: pointer;
  transition: .3s ease;
}
.enter span { font-size: 9px; letter-spacing: .2em; }
.enter b { grid-column: 1; margin-top: 5px; font-size: 12px; letter-spacing: .16em; }
.enter i { grid-column: 2; grid-row: 1 / 3; align-self: center; font-size: 24px; font-style: normal; color: #9af2f3; }
.enter:hover { transform: translateY(-2px); border-color: #9af2f3; box-shadow: 0 0 40px rgba(105,229,233,.15); }
.footer { position: absolute; z-index: 5; left: 38px; right: 38px; bottom: 29px; }
.footer-meta { display: flex; justify-content: space-between; margin-bottom: 9px; color: rgba(220,238,234,.32); font-size: 8px; letter-spacing: .17em; }
.progress-track { position: relative; height: 1px; background: rgba(223,240,236,.12); }
.progress-fill { height: 1px; background: linear-gradient(90deg, #4cabb0, #9ef3f4); box-shadow: 0 0 12px rgba(122,233,236,.6); transition: width .12s linear; }
.progress-node { position: absolute; top: 50%; width: 5px; height: 5px; border: 1px solid rgba(205,235,230,.3); border-radius: 50%; background: #0b1313; transform: translate(-50%, -50%); }
.progress-node.active { border-color: #94eff1; background: #94eff1; box-shadow: 0 0 11px #94eff1; }
@keyframes copyIn { from { opacity: 0; transform: translateY(20px); filter: blur(8px); } to { opacity: 1; transform: translateY(0); filter: blur(0); } }
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: .32; transform: scale(.55); } }
@keyframes grainShift { 0% { transform: translate(0,0); } 25% { transform: translate(1%,-1%); } 50% { transform: translate(-1%,1%); } 75% { transform: translate(1%,1%); } }
@media (max-width: 1050px) {
  .chapter-rail, .telemetry { display: none; }
  .story { left: 7%; top: 18%; width: 55vw; }
}
@media (max-width: 700px) {
  .topbar { padding: 20px; }
  .brand small { display: none; }
  .story { left: 24px; right: 24px; top: 17%; width: auto; }
  .story h1 { font-size: 39px; }
  .status { left: 20px; right: 20px; bottom: 105px; min-width: 0; }
  .footer { left: 20px; right: 20px; bottom: 22px; }
  .footer-meta span:first-child { max-width: 70%; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .features { flex-wrap: wrap; }
}
</style>
