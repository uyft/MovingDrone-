"""
Pydantic 数据模型
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str           # pending / running / done / failed
    progress: float = 0   # 0~100
    message: str = ""


class VideoUploadResponse(BaseModel):
    """视频上传响应"""
    filename: str
    filepath: str
    size_mb: float
    task_id: str


class TaskSubmitResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    status: str
    message: str


class ResultFrame(BaseModel):
    """单帧结果"""
    frame_idx: int
    count: int
    peaks: List[List[float]]  # [[x1, y1], [x2, y2], ...]


class TaskResult(BaseModel):
    """任务完成结果"""
    task_id: str
    status: str
    total_frames: int
    total_time: float
    output_video: str           # 相对路径
    frames: List[ResultFrame]   # 每帧统计
