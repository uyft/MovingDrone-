"""
DroneCrowd AI Agent — FastAPI 路由

POST /api/v1/agent/chat   — 对话（SSE 流式）
POST /api/v1/agent/reset  — 重置会话
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.agent import chat_stream, reset_session
from app.config import AGENT_ENABLED

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ResetRequest(BaseModel):
    session_id: str


@router.post("/chat")
async def agent_chat(req: ChatRequest):
    """AI 智能管家对话接口 — SSE 流式返回"""
    if not AGENT_ENABLED:
        return {"error": "AI 助手未启用。请设置 DEEPSEEK_API_KEY 环境变量。"}

    async def event_generator():
        async for event in chat_stream(req.message, req.session_id):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/reset")
async def agent_reset(req: ResetRequest):
    """重置对话会话"""
    ok = reset_session(req.session_id)
    return {"ok": ok, "session_id": req.session_id}


@router.get("/status")
async def agent_status():
    """查询 Agent 是否可用"""
    return {
        "enabled": AGENT_ENABLED,
        "message": "AI 助手已就绪" if AGENT_ENABLED else "未配置 API Key",
    }
