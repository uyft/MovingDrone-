"""
DroneCrowd AI Agent — 核心引擎

DeepSeek V4 Pro (OpenAI 兼容) 客户端 + 函数调用循环 + SSE streaming
"""
import json
import time
import uuid
from typing import AsyncGenerator
from openai import OpenAI

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tools import get_tool_definitions, execute_tool

# ============================================================
#  会话管理
# ============================================================
_sessions: dict[str, list[dict]] = {}  # session_id -> messages
MAX_HISTORY = 40  # 保留最近 40 条消息
MAX_TOOL_ROUNDS = 5  # 最多 5 轮工具调用
REQUEST_TIMEOUT = 60  # 整个请求最长 60 秒


def _get_client() -> OpenAI:
    """延迟初始化 DeepSeek 客户端"""
    return OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )


def get_or_create_session(session_id: str | None = None) -> tuple[str, list[dict]]:
    """获取或创建会话"""
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]

    new_id = session_id or uuid.uuid4().hex[:12]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    _sessions[new_id] = messages
    return new_id, messages


def reset_session(session_id: str) -> bool:
    """重置会话"""
    if session_id in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return True
    return False


async def chat_stream(
    message: str,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE 流式对话生成器

    流程:
    1. 用户消息加入历史
    2. 调用 DeepSeek API (带工具定义)
    3. 如果 LLM 返回 tool_calls → 执行工具 → 结果追加到历史 → 回到步骤 2
    4. 如果 LLM 返回文本 → 逐 token SSE 流式输出
    """
    sid, messages = get_or_create_session(session_id)
    yield _sse_event("start", {"session_id": sid})

    # 追加用户消息
    messages.append({"role": "user", "content": message})

    # 裁剪历史（保留 system prompt + 最近 N 条）
    if len(messages) > MAX_HISTORY + 1:
        messages[1:-MAX_HISTORY] = []

    client = _get_client()
    tools = get_tool_definitions()
    start_time = time.time()

    # --- 工具调用循环 ---
    for round_num in range(MAX_TOOL_ROUNDS):
        if time.time() - start_time > REQUEST_TIMEOUT:
            yield _sse_event("error", {"message": "请求超时，请稍后重试"})
            return

        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                tools=tools,
                temperature=0.3,
                max_tokens=2048,
            )
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "auth" in error_msg.lower():
                error_msg = "API Key 配置错误，请联系管理员"
            elif "timeout" in error_msg.lower():
                error_msg = "AI 服务响应超时，请稍后重试"
            yield _sse_event("error", {"message": f"AI 服务异常: {error_msg}"})
            return

        choice = response.choices[0]
        msg = choice.message

        # LLM 返回了工具调用
        if msg.tool_calls:
            # 将 assistant 消息（含 tool_calls）加入历史
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                # 通知前端工具调用
                yield _sse_event("tool_call", {
                    "name": tool_name,
                    "args": tool_args,
                })

                # 执行工具
                exec_result = execute_tool(tool_name, tool_args)

                # 通知前端工具结果
                yield _sse_event("tool_result", {
                    "name": tool_name,
                    "ok": exec_result.get("ok", False),
                })

                # 将工具结果追加到历史
                result_str = json.dumps(exec_result, ensure_ascii=False)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

            continue  # 回到循环，让 LLM 基于工具结果继续回答

        # LLM 返回了最终文本回复
        final_text = msg.content or ""
        messages.append({"role": "assistant", "content": final_text})

        # 逐字符分块流式输出（模拟 token 级别 streaming）
        chunk_size = 12
        for i in range(0, len(final_text), chunk_size):
            chunk = final_text[i:i + chunk_size]
            yield _sse_event("text", {"content": chunk})

        yield _sse_event("done", {})
        return

    # 超过最大工具调用轮数
    yield _sse_event("error", {"message": "工具调用次数过多，请简化问题重试"})


def _sse_event(event_type: str, data: dict) -> str:
    """构造 SSE 事件字符串"""
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"
