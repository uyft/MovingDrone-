"""
API 路由汇总
"""
from fastapi import APIRouter
from app.api.video import router as video_router
from app.api.dataset import router as dataset_router
from app.agent.chat_router import router as agent_router

api_router = APIRouter()

api_router.include_router(video_router, prefix="/video", tags=["视频处理"])
api_router.include_router(dataset_router, prefix="/dataset", tags=["数据集测试"])
api_router.include_router(agent_router, prefix="/agent", tags=["AI 助手"])
