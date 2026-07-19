<template>
  <!-- 收起态：圆形按钮 -->
  <button
    v-if="!open"
    class="chat-fab"
    @click="openChat"
    title="DroneCrowd AI 智能管家"
  >
    <svg class="fab-drone" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg" fill="none" aria-hidden="true">
      <g opacity="0.25"><path d="M35 34L55 53M93 34L73 53M34 94L55 75M94 94L73 75" class="drone-line" stroke-width="9"/><path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-fill"/></g>
      <path d="M35 34L55 53M93 34L73 53M34 94L55 75M94 94L73 75" class="drone-line" stroke-width="5.5"/>
      <path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-fill" opacity="0.18"/>
      <path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-line" stroke-width="4.5"/>
      <path d="M58 55L56 75M70 55L72 75" class="drone-line" stroke-width="2" opacity="0.45"/>
      <path d="M60 49H68" class="drone-accent" stroke-width="3.5" stroke-linecap="round"/>
      <path d="M57 82H71" class="drone-line" stroke-width="3.5" opacity="0.75"/>
      <path d="M50 75L56 76" class="drone-accent" stroke-width="3" stroke-linecap="round"/>
      <path d="M78 75L72 76" class="drone-accent" stroke-width="3" stroke-linecap="round"/>
      <rect x="54" y="87" width="20" height="17" rx="5" class="drone-line" stroke-width="4"/>
      <circle cx="64" cy="96" r="7" class="drone-line" stroke-width="3.5"/>
      <circle cx="64" cy="96" r="2.4" class="drone-accent"/>
      <g class="fd-rotor hd-rotor wd-rotor" transform="translate(30 30)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(-38)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
      <g class="fd-rotor hd-rotor wd-rotor" transform="translate(98 30)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(42)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
      <g class="fd-rotor hd-rotor wd-rotor" transform="translate(30 98)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(138)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
      <g class="fd-rotor hd-rotor wd-rotor" transform="translate(98 98)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(-138)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
    </svg>
    <span v-if="unreadCount" class="fab-badge">{{ unreadCount }}</span>
  </button>

  <!-- 展开态：浮动面板 -->
  <transition name="panel">
    <div v-if="open" class="chat-panel">
      <!-- 头部 -->
      <div class="chat-header">
        <div class="header-left">
          <span class="header-drone">
            <svg viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg" fill="none" aria-hidden="true">
              <g opacity="0.25"><path d="M35 34L55 53M93 34L73 53M34 94L55 75M94 94L73 75" class="drone-line" stroke-width="9"/><path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-fill"/></g>
              <path d="M35 34L55 53M93 34L73 53M34 94L55 75M94 94L73 75" class="drone-line" stroke-width="5.5"/>
              <path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-fill" opacity="0.18"/>
              <path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-line" stroke-width="4.5"/>
              <path d="M58 55L56 75M70 55L72 75" class="drone-line" stroke-width="2" opacity="0.45"/>
              <path d="M60 49H68" class="drone-accent" stroke-width="3.5" stroke-linecap="round"/>
              <path d="M57 82H71" class="drone-line" stroke-width="3.5" opacity="0.75"/>
              <path d="M50 75L56 76" class="drone-accent" stroke-width="3" stroke-linecap="round"/>
              <path d="M78 75L72 76" class="drone-accent" stroke-width="3" stroke-linecap="round"/>
              <rect x="54" y="87" width="20" height="17" rx="5" class="drone-line" stroke-width="4"/>
              <circle cx="64" cy="96" r="7" class="drone-line" stroke-width="3.5"/>
              <circle cx="64" cy="96" r="2.4" class="drone-accent"/>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(30 30)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(-38)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(98 30)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(42)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(30 98)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(138)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(98 98)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(-138)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
            </svg>
          </span>
          <div>
            <div class="header-title">DroneCrowd 智能管家</div>
            <div class="header-status">
              <span class="status-dot" :class="connected ? 'on' : 'off'"></span>
              {{ connected ? '在线' : '连接中...' }}
            </div>
          </div>
        </div>
        <button class="btn-close" @click="closeChat">✕</button>
      </div>

      <!-- 消息区 -->
      <div class="chat-messages" ref="msgContainer">
        <!-- 欢迎消息 -->
        <div v-if="messages.length === 0" class="welcome">
          <div class="welcome-drone">
            <svg viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg" fill="none" aria-hidden="true">
              <g opacity="0.25"><path d="M35 34L55 53M93 34L73 53M34 94L55 75M94 94L73 75" class="drone-line" stroke-width="9"/><path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-fill"/></g>
              <path d="M35 34L55 53M93 34L73 53M34 94L55 75M94 94L73 75" class="drone-line" stroke-width="5.5"/>
              <path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-fill" opacity="0.18"/>
              <path d="M55 45C59 39 69 39 73 45L78 76C79 83 73 90 64 90C55 90 49 83 50 76L55 45Z" class="drone-line" stroke-width="4.5"/>
              <path d="M58 55L56 75M70 55L72 75" class="drone-line" stroke-width="2" opacity="0.45"/>
              <path d="M60 49H68" class="drone-accent" stroke-width="3.5" stroke-linecap="round"/>
              <path d="M57 82H71" class="drone-line" stroke-width="3.5" opacity="0.75"/>
              <path d="M50 75L56 76" class="drone-accent" stroke-width="3" stroke-linecap="round"/>
              <path d="M78 75L72 76" class="drone-accent" stroke-width="3" stroke-linecap="round"/>
              <rect x="54" y="87" width="20" height="17" rx="5" class="drone-line" stroke-width="4"/>
              <circle cx="64" cy="96" r="7" class="drone-line" stroke-width="3.5"/>
              <circle cx="64" cy="96" r="2.4" class="drone-accent"/>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(30 30)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(-38)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(98 30)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(42)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(30 98)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(138)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
              <g class="fd-rotor hd-rotor wd-rotor" transform="translate(98 98)"><circle r="18" class="drone-line" stroke-width="4" stroke-dasharray="82 32" transform="rotate(-138)" opacity="0.9"/><ellipse cx="-9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><ellipse cx="9" cy="0" rx="13" ry="3.2" class="drone-fill" transform="rotate(-22)"/><circle r="6.5" class="drone-line" stroke-width="4"/><circle r="2.6" class="drone-accent"/></g>
            </svg>
          </div>
          <div class="welcome-title">你好！我是 DroneCrowd 智能管家</div>
          <div class="welcome-desc">我可以帮你管理无人机人群分析平台</div>
          <div class="quick-actions">
            <button
              v-for="cmd in quickCommands"
              :key="cmd.label"
              class="quick-btn"
              @click="sendQuick(cmd.label)"
            >{{ cmd.icon }} {{ cmd.label }}</button>
          </div>
        </div>

        <!-- 消息列表 -->
        <ChatMessage
          v-for="(msg, idx) in messages"
          :key="idx"
          v-bind="msg"
        />

        <!-- 加载指示器 -->
        <div v-if="loading" class="loading-indicator">
          <span class="spinner"></span>
          <span>思考中...</span>
        </div>

        <!-- 自动滚动锚点 -->
        <div ref="scrollAnchor"></div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input-area">
        <input
          v-model="input"
          class="chat-input"
          placeholder="输入消息，管理你的平台..."
          :disabled="loading"
          @keydown.enter="sendMessage"
        />
        <button
          class="btn-send"
          :disabled="!input.trim() || loading"
          @click="sendMessage"
        >发送</button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, nextTick, watch, onBeforeUnmount } from 'vue'
import ChatMessage from './ChatMessage.vue'

const API_BASE = ''  // Vite proxy 自动代理到后端

const quickCommands = [
  { icon: '⊕', label: '平台运行状态' },
  { icon: '☰', label: '最近的推理任务' },
  { icon: '≡', label: '浏览数据集场景' },
  { icon: '🤖', label: '模型对比分析' },
]

// ---- 状态 ----
const open = ref(false)
const input = ref('')
const loading = ref(false)
const connected = ref(false)
const messages = ref([])
const unreadCount = ref(0)
const sessionId = ref(null)

const msgContainer = ref(null)
const scrollAnchor = ref(null)

// ---- SSE 连接 ----
let abortController = null

async function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''

  // 添加用户消息
  messages.value.push({
    role: 'user',
    type: 'text',
    content: text,
    time: formatTime(),
  })

  loading.value = true
  await scrollBottom()

  // 添加 AI 占位消息（用于流式追加）
  const aiMsgIdx = messages.value.length
  messages.value.push({
    role: 'agent',
    type: 'text',
    content: '',
    time: formatTime(),
  })

  try {
    abortController = new AbortController()

    const resp = await fetch(`${API_BASE}/api/v1/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sessionId.value }),
      signal: abortController.signal,
    })

    connected.value = true
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''  // 保留未完成的行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        try {
          const event = JSON.parse(data)
          handleSSEEvent(event, aiMsgIdx)
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') return
    messages.value[aiMsgIdx].type = 'error'
    messages.value[aiMsgIdx].content = `连接失败: ${err.message}`
  } finally {
    loading.value = false
    abortController = null
    await scrollBottom()
  }
}

function handleSSEEvent(event, textMsgIdx) {
  switch (event.type) {
    case 'start':
      sessionId.value = event.session_id
      break

    case 'status':
      // 追加状态消息（用独立消息）
      messages.value.push({
        role: 'agent',
        type: 'status',
        content: event.content,
        time: formatTime(),
      })
      break

    case 'tool_call':
      messages.value.push({
        role: 'agent',
        type: 'tool_call',
        toolName: event.name,
        toolArgs: event.args,
        toolOk: true,
        time: formatTime(),
      })
      break

    case 'tool_result':
      // 更新最近一个工具卡片的状态
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].type === 'tool_call' && messages.value[i].toolName === event.name) {
          messages.value[i].toolOk = event.ok
          break
        }
      }
      break

    case 'text':
      // 流式追加到 AI 回复
      if (messages.value[textMsgIdx]) {
        messages.value[textMsgIdx].content += event.content
      }
      scrollBottom()
      break

    case 'done':
      break

    case 'error':
      messages.value.push({
        role: 'agent',
        type: 'error',
        content: event.message,
        time: formatTime(),
      })
      break
  }
}

function sendQuick(text) {
  input.value = text
  sendMessage()
}

function openChat() {
  open.value = true
  unreadCount.value = 0
  nextTick(() => scrollBottom())
}

function closeChat() {
  open.value = false
}

async function scrollBottom() {
  await nextTick()
  if (scrollAnchor.value) {
    scrollAnchor.value.scrollIntoView({ behavior: 'smooth' })
  }
}

function formatTime() {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// 关闭时清理
onBeforeUnmount(() => {
  if (abortController) abortController.abort()
})
</script>

<style scoped>
/* ---- FAB 按钮 ---- */
.chat-fab {
  --drone-accent: #fbbf24;
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(245, 158, 11, 0.4);
  z-index: 1000;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chat-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 28px rgba(245, 158, 11, 0.55);
}
.fab-drone { width: 36px; height: 36px; color: #fff; }
.fab-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 20px;
  height: 20px;
  line-height: 20px;
  border-radius: 10px;
  background: #f87171;
  font-size: 11px;
  font-weight: 600;
  text-align: center;
  padding: 0 5px;
}

/* ---- 浮动面板 ---- */
.chat-panel {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 400px;
  height: 560px;
  max-height: calc(100vh - 60px);
  border-radius: 16px;
  background: var(--bg-panel, #0f1225);
  border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
  box-shadow: 0 8px 40px rgba(0,0,0,0.5);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 面板进入/离开动画 */
.panel-enter-active {
  animation: panelIn 0.3s ease-out;
}
.panel-leave-active {
  animation: panelOut 0.2s ease-in;
}
@keyframes panelIn {
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes panelOut {
  from { opacity: 1; transform: translateY(0) scale(1); }
  to { opacity: 0; transform: translateY(20px) scale(0.95); }
}

/* ---- 头部 ---- */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.06));
  background: rgba(245, 158, 11, 0.08);
  flex-shrink: 0;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-drone { width: 32px; height: 32px; color: #fcd34d; display: flex; align-items: center; --drone-accent: #fbbf24; }
.header-drone svg { width: 100%; height: 100%; }
.header-title { font-size: 15px; font-weight: 600; color: var(--text-primary, #e0e0e0); }
.header-status {
  font-size: 11px;
  color: #8899aa;
  display: flex;
  align-items: center;
  gap: 5px;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.status-dot.on { background: #4ade80; }
.status-dot.off { background: #f59e0b; }

.btn-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #8899aa;
  cursor: pointer;
  font-size: 18px;
  transition: background 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-close:hover { background: rgba(255,255,255,0.08); color: #e0e0e0; }

/* ---- 消息区 ---- */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  scroll-behavior: smooth;
}

/* 欢迎页 */
.welcome { text-align: center; padding: 20px 0; }
.welcome-drone { width: 56px; height: 56px; margin: 0 auto 10px auto; color: #8899aa; --drone-accent: #fbbf24; }
.welcome-drone svg { width: 100%; height: 100%; }
.welcome-title { font-size: 16px; font-weight: 600; color: var(--text-primary, #e0e0e0); margin-bottom: 6px; }
.welcome-desc { font-size: 13px; color: #8899aa; margin-bottom: 16px; }
.quick-actions { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.quick-btn {
  padding: 6px 12px;
  border-radius: 16px;
  border: 1px solid var(--border-subtle, rgba(255,255,255,0.1));
  background: var(--bg-card, rgba(255,255,255,0.04));
  color: var(--text-primary, #e0e0e0);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}
.quick-btn:hover {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.35);
}

/* 加载指示器 */
.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  font-size: 12.5px;
  color: #8899aa;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(245, 158, 11, 0.3);
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ---- 输入区 ---- */
.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--border-subtle, rgba(255,255,255,0.06));
  flex-shrink: 0;
}
.chat-input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 20px;
  border: 1px solid var(--border-subtle, rgba(255,255,255,0.1));
  background: var(--bg-card, rgba(255,255,255,0.04));
  color: var(--text-primary, #e0e0e0);
  font-size: 13.5px;
  outline: none;
  transition: border-color 0.2s;
}
.chat-input:focus { border-color: rgba(245, 158, 11, 0.5); }
.chat-input::placeholder { color: #556; }
.btn-send {
  padding: 10px 18px;
  border-radius: 20px;
  border: none;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
  flex-shrink: 0;
}
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-send:not(:disabled):hover { transform: scale(1.04); }
</style>

<!-- Drone SVG 样式（非 scoped，供内联 SVG 元素使用） -->
<style>
.drone-line { stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; }
.drone-fill { fill: currentColor; }
.drone-accent { stroke: var(--drone-accent, #fbbf24); fill: var(--drone-accent, #fbbf24); }
.fd-rotor, .hd-rotor, .wd-rotor { transform-box: fill-box; transform-origin: center; }
</style>
