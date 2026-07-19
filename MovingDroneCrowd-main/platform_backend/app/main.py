"""
FastAPI 主入口 - 启动服务、挂载路由
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import UPLOAD_DIR, RESULT_DIR
from app.api.router import api_router

app = FastAPI(
    title="无人机视角动态密集人群计数与跟踪系统",
    description="MovingDroneCrowd Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.on_event("startup")
async def startup():
    """启动时初始化数据库，加载历史任务到缓存"""
    from app.db import init_db_sync, db_list_tasks, db_get_result
    init_db_sync()

    # 预热缓存：加载所有历史任务
    from app.services.inference_service import _task_cache, _result_cache
    tasks = db_list_tasks()
    for t in tasks:
        tid = t["task_id"]
        _task_cache[tid] = t
    # 加载已完成任务的结果
    for t in tasks:
        tid = t["task_id"]
        r = db_get_result(tid)
        if r:
            _result_cache[tid] = r
    print(f"[Startup] 加载了 {len(tasks)} 个历史任务到缓存")

# CORS（开发阶段全放行）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api/v1")

# 静态文件（结果预览）
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/results", StaticFiles(directory=RESULT_DIR), name="results")

# 数据集静态文件（帧图像）
DATASET_FRAMES_DIR = '/workspace/MovingDroneCrowd++/frames'
if os.path.isdir(DATASET_FRAMES_DIR):
    app.mount("/dataset_frames", StaticFiles(directory=DATASET_FRAMES_DIR), name="dataset_frames")

# 前端静态文件
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "platform_frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str = ""):
        """回退到前端 SPA"""
        import os as _os
        # API 路径不拦截
        if full_path.startswith("api/") or full_path.startswith("docs") or \
           full_path.startswith("redoc") or full_path.startswith("uploads/") or \
           full_path.startswith("results/") or full_path.startswith("assets/") or \
           full_path.startswith("dataset_frames/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        file_path = _os.path.join(FRONTEND_DIST, full_path or "index.html")
        if _os.path.exists(file_path) and _os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(_os.path.join(FRONTEND_DIST, "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "service": "MovingDroneCrowd Platform",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
        }
