<template>
  <!--
    VirtualGuideAssistant.vue
    DroneCrowd 智能讲解员 — 科技感可爱虚拟人物助手
    状态: idle / listening / thinking / speaking / guide / error
  -->
  <div class="vga-root">
    <!-- ============================================================
         收起态：右下角圆形按钮 — 虚拟人物形象
         ============================================================ -->
    <button
      v-if="!panelOpen"
      class="vga-fab"
      :class="characterState"
      @click="openPanel"
      :title="stateLabel"
    >
      <!-- SVG 人物形象 — 可爱机器人 -->
      <svg class="vga-character" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="vg-glow" cx="50%" cy="40%" r="50%">
            <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.25"/>
            <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
          </radialGradient>
          <linearGradient id="vg-body-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#2a2a3e"/>
            <stop offset="100%" stop-color="#1a1a2e"/>
          </linearGradient>
          <linearGradient id="vg-eye-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#fbbf24"/>
            <stop offset="100%" stop-color="#f59e0b"/>
          </linearGradient>
          <filter id="vg-glow-filter">
            <feGaussianBlur stdDeviation="2" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        <!-- 背景光晕 -->
        <circle cx="100" cy="85" r="72" fill="url(#vg-glow)" class="vg-bg-glow"/>

        <!-- 天线 -->
        <g class="vg-antenna">
          <line x1="100" y1="38" x2="100" y2="18" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" opacity="0.7"/>
          <circle cx="100" cy="16" r="5" fill="#fbbf24" filter="url(#vg-glow-filter)">
            <animate attributeName="opacity" values="0.5;1;0.5" dur="1.5s" repeatCount="indefinite"/>
          </circle>
        </g>

        <!-- 头部主体 — 圆角方形 -->
        <rect x="62" y="40" width="76" height="68" rx="14" fill="url(#vg-body-grad)" stroke="#f59e0b" stroke-width="2"/>

        <!-- 侧面板（耳朵） -->
        <rect x="52" y="62" width="10" height="28" rx="5" fill="#1e1e32" stroke="#fbbf24" stroke-width="1.2" class="vg-ear-glow"/>
        <rect x="138" y="62" width="10" height="28" rx="5" fill="#1e1e32" stroke="#fbbf24" stroke-width="1.2" class="vg-ear-glow"/>

        <!-- 眼睛 — 大圆眼 -->
        <g class="vg-eyes">
          <circle cx="81" cy="68" r="12" fill="#111" stroke="#f59e0b" stroke-width="1.5"/>
          <circle cx="81" cy="68" r="8" fill="url(#vg-eye-grad)" opacity="0.9"/>
          <circle cx="83" cy="65" r="3" fill="white" opacity="0.8"/>
          <circle cx="119" cy="68" r="12" fill="#111" stroke="#f59e0b" stroke-width="1.5"/>
          <circle cx="119" cy="68" r="8" fill="url(#vg-eye-grad)" opacity="0.9"/>
          <circle cx="121" cy="65" r="3" fill="white" opacity="0.8"/>
        </g>

        <!-- 眨眼 -->
        <g class="vg-blink">
          <rect x="69" y="60" width="24" height="16" rx="8" fill="#2a2a3e" opacity="0">
            <animate attributeName="opacity" values="0;0;0;1;0;0;0;0;0;0" dur="4s" repeatCount="indefinite"/>
          </rect>
          <rect x="107" y="60" width="24" height="16" rx="8" fill="#2a2a3e" opacity="0">
            <animate attributeName="opacity" values="0;0;0;1;0;0;0;0;0;0" dur="4s" repeatCount="indefinite"/>
          </rect>
        </g>

        <!-- 嘴巴 -->
        <g class="vg-mouth">
          <path class="mouth-idle" d="M92 90C95 94 105 94 108 90" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round" opacity="0.8"/>
          <rect class="mouth-speaking" x="94" y="88" width="12" height="6" rx="3" fill="#f59e0b" opacity="0">
            <animate attributeName="opacity" values="0" dur="0.1s" fill="freeze" begin="indefinite"/>
          </rect>
        </g>

        <!-- 身体（下半截） -->
        <rect x="74" y="110" width="52" height="10" rx="5" fill="#1e1e32" stroke="#f59e0b" stroke-width="1.2" opacity="0.8"/>

        <!-- 状态指示 -->
        <g class="vg-state-overlay">
          <g class="vg-thinking-dots" opacity="0">
            <circle cx="85" cy="38" r="3" fill="#fbbf24">
              <animate attributeName="opacity" values="0.3;1;0.3" dur="0.8s" repeatCount="indefinite" begin="0s"/>
            </circle>
            <circle cx="94" cy="36" r="3" fill="#fbbf24">
              <animate attributeName="opacity" values="0.3;1;0.3" dur="0.8s" repeatCount="indefinite" begin="0.2s"/>
            </circle>
            <circle cx="103" cy="38" r="3" fill="#fbbf24">
              <animate attributeName="opacity" values="0.3;1;0.3" dur="0.8s" repeatCount="indefinite" begin="0.4s"/>
            </circle>
          </g>
          <g class="vg-error-sweat" opacity="0">
            <path d="M130 46C130 46 133 54 130 58C127 54 130 46 130 46Z" fill="#fbbf24"/>
          </g>
        </g>

        <!-- 腮红 -->
        <circle cx="72" cy="85" r="5" fill="#f59e0b" opacity="0.15"/>
        <circle cx="128" cy="85" r="5" fill="#f59e0b" opacity="0.15"/>
      </svg>

      <!-- 状态标签 -->
      <span class="vga-fab-label">{{ stateLabel }}</span>

      <!-- 未读角标 -->
      <span v-if="unreadCount" class="vga-badge">{{ unreadCount }}</span>
    </button>

    <!-- ============================================================
         展开态：对话面板
         ============================================================ -->
    <transition name="vga-panel">
      <div v-if="panelOpen" class="vga-panel">
        <!-- 面板头部 -->
        <div class="vga-panel-header">
          <div class="vga-panel-char-wrapper">
            <!-- 面板内缩小版机器人 -->
            <svg class="vga-panel-char" viewBox="0 0 200 200">
              <circle cx="100" cy="85" r="60" fill="url(#vg-glow)" opacity="0.15"/>
              <line x1="100" y1="40" x2="100" y2="22" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
              <circle cx="100" cy="20" r="4" fill="#fbbf24" opacity="0.9"/>
              <rect x="66" y="44" width="68" height="58" rx="12" fill="#2a2a3e" stroke="#f59e0b" stroke-width="1.5"/>
              <rect x="58" y="62" width="8" height="24" rx="4" fill="#1e1e32" stroke="#fbbf24" stroke-width="1"/>
              <rect x="134" y="62" width="8" height="24" rx="4" fill="#1e1e32" stroke="#fbbf24" stroke-width="1"/>
              <circle cx="82" cy="68" r="10" fill="#111" stroke="#f59e0b" stroke-width="1.2"/>
              <circle cx="82" cy="68" r="7" fill="#f59e0b" opacity="0.8"/>
              <circle cx="84" cy="65" r="2.5" fill="white" opacity="0.7"/>
              <circle cx="118" cy="68" r="10" fill="#111" stroke="#f59e0b" stroke-width="1.2"/>
              <circle cx="118" cy="68" r="7" fill="#f59e0b" opacity="0.8"/>
              <circle cx="120" cy="65" r="2.5" fill="white" opacity="0.7"/>
              <path d="M93 88C95 91 105 91 107 88" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
              <rect x="76" y="106" width="48" height="8" rx="4" fill="#1e1e32" stroke="#f59e0b" stroke-width="1" opacity="0.7"/>
            </svg>
          </div>
          <div class="vga-panel-title-area">
            <div class="vga-panel-title">DroneCrowd 智能讲解员</div>
            <div class="vga-panel-subtitle">{{ stateLabel }}</div>
          </div>
          <button class="vga-panel-close" @click="closePanel">✕</button>
        </div>

        <!-- 消息列表 -->
        <div class="vga-messages" ref="msgContainer">
          <!-- 欢迎消息 -->
          <div v-if="messages.length === 0" class="vga-welcome">
            <div class="vga-welcome-text">
              你好！我是 DroneCrowd 平台的智能讲解员 ✨<br>
              可以问我关于平台操作、模型原理、数据分析的任何问题。
            </div>
            <div class="vga-quick-asks">
              <button v-for="q in quickQuestions" :key="q" class="vga-quick-btn" @click="askQuick(q)">
                {{ q }}
              </button>
            </div>
          </div>

          <!-- 历史消息 -->
          <div v-for="(msg, i) in messages" :key="i" :class="['vga-msg', msg.role]">
            <div class="vga-msg-bubble" v-html="renderMsg(msg.content)"></div>
            <div class="vga-msg-time">{{ msg.time }}</div>
          </div>

          <!-- 加载指示器 -->
          <div v-if="isLoading" class="vga-loading">
            <span class="vga-loading-dot"></span>
            <span class="vga-loading-dot"></span>
            <span class="vga-loading-dot"></span>
          </div>

          <div ref="scrollAnchor"></div>
        </div>

        <!-- 输入区 -->
        <div class="vga-input-area">
          <!-- 语音状态提示 -->
          <div v-if="isListening" class="vga-voice-bar">
            <div class="vga-voice-waves">
              <span v-for="n in 5" :key="n" class="vga-voice-wave"></span>
            </div>
            <span>正在聆听...</span>
          </div>

          <div class="vga-input-row">
            <button
              class="vga-voice-btn"
              :class="{ active: isListening, disabled: !voiceSupported }"
              @click="toggleVoice"
              :title="voiceSupported ? '语音输入' : '浏览器不支持语音识别'"
            >🎤</button>
            <input
              v-model="inputText"
              class="vga-input"
              placeholder="问我关于平台的问题..."
              :disabled="isLoading"
              @keydown.enter="sendMessage"
            />
            <button class="vga-send-btn" :disabled="!inputText.trim() || isLoading" @click="sendMessage">
              发送
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
/**
 * VirtualGuideAssistant.vue — DroneCrowd 智能讲解员
 *
 * 动画状态机:
 *   idle      — 待机，轻微浮动 + 眨眼
 *   listening — 正在听，耳机发光
 *   thinking  — 思考中，加载点出现
 *   speaking  — 正在回答，嘴巴动画
 *   guide     — 引导状态，抬手指向
 *   error     — 错误，汗滴 + 疑惑
 */

import { ref, nextTick, onBeforeUnmount, computed } from 'vue'

// ============================================================
//  状态管理
// ============================================================
const panelOpen = ref(false)
const inputText = ref('')
const isLoading = ref(false)
const isListening = ref(false)
const characterState = ref('idle')  // idle | listening | thinking | speaking | guide | error
const messages = ref([])
const unreadCount = ref(0)
const sessionId = ref(null)

const msgContainer = ref(null)
const scrollAnchor = ref(null)

// ============================================================
//  快捷问题
// ============================================================
const quickQuestions = [
  '平台运行步骤是什么？',
  '视频上传和图片上传流程？',
  '检测阈值是什么意思？',
  '人数统计结果怎么看？',
  '密度热力图怎么看？',
  '轨迹追踪怎么看？',
  '平台支持哪些模型？',
]

// ============================================================
//  状态标签
// ============================================================
const stateLabel = computed(() => {
  const map = {
    idle: '点击和我聊天',
    listening: '正在聆听...',
    thinking: '思考中...',
    speaking: '正在讲解...',
    guide: '看这里~',
    error: '请再说一次',
  }
  return map[characterState.value] || '点击和我聊天'
})


// ============================================================
//  语音支持检测
// ============================================================
const voiceSupported = computed(() => {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition)
})

// ============================================================
//  Web Speech: 语音识别
// ============================================================
let recognition = null

function toggleVoice() {
  if (!voiceSupported.value) {
    messages.value.push({
      role: 'agent', content: '当前浏览器不支持语音识别，请使用文字输入。', time: formatTime()
    })
    return
  }
  if (isListening.value) {
    stopListening()
  } else {
    startListening()
  }
}

function startListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) return

  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = false
  recognition.continuous = false

  recognition.onstart = () => {
    isListening.value = true
    setState('listening')
  }
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript
    inputText.value = transcript
    setState('idle')
    sendMessage()
  }
  recognition.onerror = () => {
    isListening.value = false
    setState('error')
    setTimeout(() => setState('idle'), 2000)
  }
  recognition.onend = () => {
    isListening.value = false
  }

  recognition.start()
}

function stopListening() {
  if (recognition) {
    recognition.stop()
    recognition = null
  }
  isListening.value = false
  setState('idle')
}

// ============================================================
//  Web Speech: 语音合成（朗读 AI 回复）
// ============================================================
function speakText(text) {
  if (!window.speechSynthesis) return
  // 去掉 markdown 标记
  const plain = text.replace(/[*_`#\[\]()]/g, '').replace(/\n/g, ' ')
  if (plain.length > 200) {
    // 长文本截断，只读前 200 字
    window.speechSynthesis.cancel()
    return
  }
  const utter = new SpeechSynthesisUtterance(plain)
  utter.lang = 'zh-CN'
  utter.rate = 1.1
  utter.pitch = 1.1
  utter.onstart = () => setState('speaking')
  utter.onend = () => setState('idle')
  utter.onerror = () => setState('idle')
  window.speechSynthesis.speak(utter)
}

// ============================================================
//  发送消息 → 调用 DeepSeek V4 Pro API
// ============================================================
let abortController = null

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return
  inputText.value = ''

  // 添加用户消息
  messages.value.push({ role: 'user', content: text, time: formatTime() })
  await scrollBottom()

  // AI 占位
  const aiIdx = messages.value.length
  messages.value.push({ role: 'agent', content: '', time: formatTime() })

  isLoading.value = true
  setState('thinking')

  try {
    abortController = new AbortController()
    const resp = await fetch('/api/v1/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: buildPlatformPrompt(text),
        session_id: sessionId.value,
      }),
      signal: abortController.signal,
    })

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'start') sessionId.value = event.session_id
          if (event.type === 'text') messages.value[aiIdx].content += event.content
          if (event.type === 'tool_call') {
            // 忽略工具调用细节，只展示结果
          }
          if (event.type === 'done') {
            // 完成
          }
          if (event.type === 'error') {
            messages.value[aiIdx].content = `抱歉，出了点问题：${event.message}`
          }
        } catch (e) { /* ignore */ }
      }
      scrollBottom()
    }
  } catch (err) {
    if (err.name === 'AbortError') return
    messages.value[aiIdx].content = `连接失败，请稍后重试。`
  } finally {
    isLoading.value = false
    setState('idle')
    // 朗读回复（如果语音可用）
    const reply = messages.value[aiIdx]?.content || ''
    if (reply) speakText(reply)
  }
}

/**
 * 构建平台知识增强提示词
 * 在用户消息前注入平台上下文，引导 DeepSeek 偏向平台讲解
 */
function buildPlatformPrompt(userMsg) {
  return `【系统指令】你是 DroneCrowd 平台的智能讲解员。请用友好、专业的中文回答。
你的定位：帮助用户理解无人机视角人群计数与跟踪平台的使用方法。
平台背景：基于 ICCV 2025 Highlight 论文，包含 STEERER（密度估计）、GD³A（视频个体计数）、STNNet（跟踪）、YOLO11（检测）四种模型，以及 MovingDroneCrowd++（44 场景无人机航拍数据集）。
请尽量结合平台功能回答，避免泛泛而谈。回答控制在 200 字以内，简洁明了。

【用户问题】${userMsg}`
}

async function askQuick(q) {
  inputText.value = q
  await sendMessage()
}

// ============================================================
//  状态切换
// ============================================================
function setState(state) {
  characterState.value = state
}

// ============================================================
//  面板控制
// ============================================================
function openPanel() {
  panelOpen.value = true
  unreadCount.value = 0
  setState('idle')
  nextTick(() => scrollBottom())
}

function closePanel() {
  panelOpen.value = false
  setState('idle')
}

// ============================================================
//  辅助函数
// ============================================================
function scrollBottom() {
  nextTick(() => {
    scrollAnchor.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

function formatTime() {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function renderMsg(text) {
  if (!text) return ''
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

onBeforeUnmount(() => {
  if (abortController) abortController.abort()
  if (recognition) recognition.stop()
  window.speechSynthesis?.cancel()
})
</script>

<style scoped>
/* ============================================================
   FAB 按钮 — 人物形象入口
   ============================================================ */
.vga-fab {
  position: fixed;
  bottom: 28px;
  right: 28px;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 2px solid rgba(245, 158, 11, 0.4);
  background: linear-gradient(145deg, rgba(15, 18, 37, 0.95), rgba(10, 10, 30, 0.95));
  box-shadow: 0 0 30px rgba(245, 158, 11, 0.2), inset 0 0 30px rgba(245, 158, 11, 0.05);
  cursor: pointer;
  z-index: 999;
  padding: 4px;
  transition: transform 0.3s, box-shadow 0.3s;
  overflow: visible;
}
.vga-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 0 45px rgba(245, 158, 11, 0.35), inset 0 0 40px rgba(245, 158, 11, 0.1);
}
.vga-character {
  width: 100%;
  height: 100%;
}

/* FAB 内的标签 */
.vga-fab-label {
  position: absolute;
  bottom: -22px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 10px;
  color: #8899bb;
  white-space: nowrap;
  pointer-events: none;
}

/* 未读角标 */
.vga-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  line-height: 20px;
  border-radius: 10px;
  background: #f87171;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
  padding: 0 5px;
}

/* ============================================================
   动画状态 — idle: 浮动
   ============================================================ */
.vga-fab.idle .vga-character {
  animation: vgaFloat 3s ease-in-out infinite;
}
@keyframes vgaFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

/* listening: 耳机发光脉冲 */
.vga-fab.listening .vg-ear-glow {
  animation: vgaGlow 0.6s ease-in-out infinite;
}
@keyframes vgaGlow {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.9; }
}

/* thinking: 人物缩小 + 思考点显隐 */
.vga-fab.thinking .vga-character {
  animation: vgaThink 1.2s ease-in-out infinite;
}
@keyframes vgaThink {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(0.93); }
}
.vga-fab.thinking .vg-thinking-dots { opacity: 1 !important; }

/* speaking: 身体微动 */
.vga-fab.speaking .vga-character {
  animation: vgaSpeak 0.5s ease-in-out infinite;
}
@keyframes vgaSpeak {
  0%, 100% { transform: translateY(0) scale(1); }
  25% { transform: translateY(-2px) scale(1.02); }
  75% { transform: translateY(2px) scale(0.98); }
}

/* error: 抖动 */
.vga-fab.error .vga-character {
  animation: vgaShake 0.4s ease-in-out;
}
@keyframes vgaShake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-3px); }
  40% { transform: translateX(3px); }
  60% { transform: translateX(-2px); }
  80% { transform: translateX(2px); }
}
.vga-fab.error .vg-error-sweat { opacity: 1 !important; }

/* 背景光晕呼吸 */
.vg-bg-glow {
  animation: vgaBreathe 3s ease-in-out infinite;
}
@keyframes vgaBreathe {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* ============================================================
   对话面板
   ============================================================ */
.vga-panel {
  position: fixed;
  bottom: 28px;
  right: 28px;
  width: 420px;
  height: 560px;
  max-height: calc(100vh - 70px);
  border-radius: 18px;
  background: linear-gradient(160deg, rgba(12, 15, 32, 0.97), rgba(8, 10, 24, 0.98));
  border: 1.5px solid rgba(245, 158, 11, 0.25);
  box-shadow: 0 0 40px rgba(245, 158, 11, 0.15), 0 12px 48px rgba(0, 0, 0, 0.5);
  z-index: 998;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(20px);
}

/* 面板进出动画 */
.vga-panel-enter-active { animation: vgaPanelIn 0.35s ease-out; }
.vga-panel-leave-active { animation: vgaPanelOut 0.25s ease-in; }
@keyframes vgaPanelIn {
  from { opacity: 0; transform: translateY(30px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes vgaPanelOut {
  from { opacity: 1; transform: translateY(0) scale(1); }
  to { opacity: 0; transform: translateY(30px) scale(0.9); }
}

/* ============================================================
   面板头部
   ============================================================ */
.vga-panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(245, 158, 11, 0.15);
  background: rgba(245, 158, 11, 0.04);
  flex-shrink: 0;
}
.vga-panel-char-wrapper { width: 44px; height: 44px; flex-shrink: 0; }
.vga-panel-char { width: 100%; height: 100%; }
.vga-panel-title-area { flex: 1; }
.vga-panel-title {
  font-size: 15px; font-weight: 700; color: #fef3c7;
  background: linear-gradient(90deg, #fcd34d, #fbbf24);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.vga-panel-subtitle { font-size: 11px; color: #6b7daa; margin-top: 1px; }
.vga-panel-close {
  width: 30px; height: 30px; border-radius: 50%; border: none;
  background: transparent; color: #6b7daa; font-size: 18px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.vga-panel-close:hover { background: rgba(255,255,255,0.06); color: #e0e0e0; }

/* ============================================================
   消息区
   ============================================================ */
.vga-messages {
  flex: 1; overflow-y: auto; padding: 16px;
  scroll-behavior: smooth;
}

/* 欢迎区 */
.vga-welcome { text-align: center; padding: 16px 0; }
.vga-welcome-text { font-size: 13px; color: #8899bb; line-height: 1.7; margin-bottom: 14px; }
.vga-quick-asks { display: flex; flex-wrap: wrap; gap: 7px; justify-content: center; }
.vga-quick-btn {
  padding: 7px 13px; border-radius: 16px;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.06); color: #fcd34d;
  font-size: 12px; cursor: pointer; transition: all 0.2s;
}
.vga-quick-btn:hover { background: rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.4); }

/* 消息气泡 */
.vga-msg { margin-bottom: 14px; animation: vgaMsgIn 0.3s ease-out; }
@keyframes vgaMsgIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.vga-msg.user { display: flex; flex-direction: column; align-items: flex-end; }
.vga-msg.agent { display: flex; flex-direction: column; align-items: flex-start; }

.vga-msg-bubble {
  max-width: 82%; padding: 10px 15px; border-radius: 16px;
  font-size: 13px; line-height: 1.6; word-break: break-word;
}
.vga-msg.user .vga-msg-bubble {
  background: linear-gradient(135deg, #f59e0b, #b45309);
  color: #fff; border-bottom-right-radius: 4px;
}
.vga-msg.agent .vga-msg-bubble {
  background: rgba(255,255,255,0.05); color: #d0d8f0;
  border: 1px solid rgba(255,255,255,0.06); border-bottom-left-radius: 4px;
}
.vga-msg-bubble :deep(code) {
  background: rgba(0,0,0,0.3); padding: 1px 6px; border-radius: 4px;
  font-size: 12px; font-family: monospace;
}
.vga-msg-bubble :deep(strong) { color: #fcd34d; }
.vga-msg-time { font-size: 10px; color: #556; margin-top: 4px; padding: 0 6px; }

/* 加载指示器 */
.vga-loading { display: flex; gap: 6px; padding: 12px 18px; }
.vga-loading-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #f59e0b;
  animation: vgaDot 1.2s ease-in-out infinite;
}
.vga-loading-dot:nth-child(2) { animation-delay: 0.2s; }
.vga-loading-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes vgaDot {
  0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* ============================================================
   输入区
   ============================================================ */
.vga-input-area { padding: 10px 14px; border-top: 1px solid rgba(245, 158, 11, 0.12); flex-shrink: 0; }

/* 语音状态条 */
.vga-voice-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; margin-bottom: 8px;
  border-radius: 10px; background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  font-size: 12px; color: #fbbf24;
}
.vga-voice-waves { display: flex; gap: 3px; align-items: flex-end; height: 16px; }
.vga-voice-wave {
  width: 3px; border-radius: 2px; background: #fbbf24;
  animation: vgaWave 0.6s ease-in-out infinite;
}
.vga-voice-wave:nth-child(1) { height: 8px; animation-delay: 0s; }
.vga-voice-wave:nth-child(2) { height: 14px; animation-delay: 0.1s; }
.vga-voice-wave:nth-child(3) { height: 10px; animation-delay: 0.2s; }
.vga-voice-wave:nth-child(4) { height: 16px; animation-delay: 0.3s; }
.vga-voice-wave:nth-child(5) { height: 6px; animation-delay: 0.4s; }
@keyframes vgaWave {
  0%, 100% { transform: scaleY(0.5); }
  50% { transform: scaleY(1); }
}

/* 输入行 */
.vga-input-row { display: flex; gap: 8px; align-items: center; }
.vga-voice-btn {
  width: 38px; height: 38px; border-radius: 50%;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.06); color: #fcd34d;
  font-size: 16px; cursor: pointer; flex-shrink: 0;
  transition: all 0.2s; display: flex; align-items: center; justify-content: center;
}
.vga-voice-btn:hover:not(.disabled) { background: rgba(245, 158, 11, 0.15); }
.vga-voice-btn.active { background: rgba(251, 191, 36, 0.2); border-color: #fbbf24; color: #fbbf24; }
.vga-voice-btn.disabled { opacity: 0.3; cursor: not-allowed; }

.vga-input {
  flex: 1; padding: 10px 14px; border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03); color: #e0e0e0;
  font-size: 13px; outline: none; transition: border-color 0.2s;
}
.vga-input:focus { border-color: rgba(245, 158, 11, 0.45); }
.vga-input::placeholder { color: #445; }
.vga-input:disabled { opacity: 0.5; }

.vga-send-btn {
  padding: 10px 18px; border-radius: 20px; border: none;
  background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff;
  font-size: 13px; font-weight: 600; cursor: pointer;
  flex-shrink: 0; transition: opacity 0.2s, transform 0.15s;
}
.vga-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.vga-send-btn:not(:disabled):hover { transform: scale(1.04); }
</style>
