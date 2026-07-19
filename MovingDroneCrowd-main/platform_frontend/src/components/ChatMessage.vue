<template>
  <div :class="['chat-message', role]">
    <!-- AI 消息头像 -->
    <div v-if="role === 'agent'" class="avatar agent-avatar">🤖</div>

    <div class="message-body">
      <!-- 工具调用卡片 -->
      <div v-if="type === 'tool_call'" class="tool-card">
        <div class="tool-header">
          <span class="tool-icon">⊹</span>
          <span class="tool-name">{{ toolName }}</span>
          <span class="tool-badge">工具调用</span>
        </div>
        <div v-if="toolArgs && Object.keys(toolArgs).length" class="tool-args">
          <code>{{ formatArgs(toolArgs) }}</code>
        </div>
        <div class="tool-status" :class="toolOk ? 'ok' : 'err'">
          {{ toolOk ? '✓ 执行完成' : '✗ 执行失败' }}
        </div>
      </div>

      <!-- 状态消息 -->
      <div v-else-if="type === 'status'" class="status-msg">
        <span class="spinner"></span>
        <span>{{ content }}</span>
      </div>

      <!-- 错误消息 -->
      <div v-else-if="type === 'error'" class="error-msg">
        <span>⚠️</span>
        <span>{{ content }}</span>
      </div>

      <!-- 普通文本消息 -->
      <div v-else class="text-bubble" v-html="renderMarkdown(content)"></div>

      <!-- 时间戳 -->
      <div class="msg-time">{{ time }}</div>
    </div>

    <!-- 用户消息头像 -->
    <div v-if="role === 'user'" class="avatar user-avatar">👤</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  role: { type: String, default: 'agent' },  // 'user' | 'agent'
  type: { type: String, default: 'text' },    // 'text' | 'tool_call' | 'tool_result' | 'status' | 'error'
  content: { type: String, default: '' },
  toolName: { type: String, default: '' },
  toolArgs: { type: Object, default: null },
  toolOk: { type: Boolean, default: true },
  time: { type: String, default: '' },
})

function formatArgs(args) {
  if (!args) return ''
  const parts = []
  for (const [k, v] of Object.entries(args)) {
    parts.push(`${k}=${JSON.stringify(v)}`)
  }
  return parts.join(', ')
}

function renderMarkdown(text) {
  if (!text) return ''
  // 简单 Markdown 渲染
  let html = text
    // 行内代码
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    // 粗体
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // 换行
    .replace(/\n/g, '<br>')
  return html
}
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  animation: msgIn 0.25s ease-out;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  background: var(--bg-card, rgba(255,255,255,0.06));
  border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
}

.message-body {
  max-width: 78%;
}

/* 文本气泡 */
.text-bubble {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-primary, #e0e0e0);
  word-break: break-word;
}

.user .text-bubble {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.agent .text-bubble {
  background: var(--bg-card, rgba(255,255,255,0.06));
  border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
  border-bottom-left-radius: 4px;
}

.text-bubble :deep(.inline-code) {
  background: rgba(0,0,0,0.3);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12.5px;
  font-family: 'Courier New', monospace;
}

.text-bubble :deep(strong) {
  color: #fcd34d;
}

/* 工具调用卡片 */
.tool-card {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.25);
  font-size: 12.5px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.tool-icon { font-size: 14px; }
.tool-name {
  font-weight: 600;
  color: #fcd34d;
  font-family: 'Courier New', monospace;
}

.tool-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(245, 158, 11, 0.3);
  color: #fcd34d;
  margin-left: auto;
}

.tool-args {
  margin-bottom: 4px;
}

.tool-args code {
  font-size: 11px;
  color: #8899aa;
  word-break: break-all;
}

.tool-status {
  font-size: 11px;
}
.tool-status.ok { color: #4ade80; }
.tool-status.err { color: #f87171; }

/* 状态消息 */
.status-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12.5px;
  color: #8899aa;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(245, 158, 11, 0.3);
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 错误消息 */
.error-msg {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.25);
  font-size: 13px;
  color: #f87171;
}

.msg-time {
  font-size: 10px;
  color: #556;
  margin-top: 3px;
  padding: 0 4px;
}

.user .msg-time { text-align: right; }

@keyframes msgIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
