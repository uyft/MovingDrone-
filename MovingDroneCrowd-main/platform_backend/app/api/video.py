"""
视频处理 API
注意: inference_service 重型依赖全部延迟导入，避免启动时 500
"""
import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import UPLOAD_DIR, RESULT_DIR, ALLOWED_EXTENSIONS, MAX_VIDEO_SIZE_MB
from app.schemas.models import VideoUploadResponse, TaskSubmitResponse

router = APIRouter()


# ============================================================
#  POST /upload  上传视频
# ============================================================
@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"error": f"不支持格式 {ext}, 允许: {ALLOWED_EXTENSIONS}"}

    safe_name = file.filename.replace(" ", "_")
    filepath = os.path.join(UPLOAD_DIR, safe_name)

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)

    return VideoUploadResponse(
        filename=safe_name,
        filepath=filepath,
        size_mb=size_mb,
        task_id="",
    )


# ============================================================
#  POST /analyze  发起分析
# ============================================================
@router.post("/analyze", response_model=TaskSubmitResponse)
async def analyze_video(
    filename: str = Query(..., description="视频文件名"),
    mode: str = Query("counting", description="模式: counting / tracking"),
    model: str = Query("STEERER", description="模型: STEERER / GD3A_VGG16 / GD3A_ResNet50 / YOLO11"),
):
    from app.services.inference_service import (
        create_task, run_counting_async, MODE_COUNTING, MODE_TRACKING
    )

    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return TaskSubmitResponse(task_id="", status="error", message=f"文件不存在: {filename}")

    if mode not in [MODE_COUNTING, MODE_TRACKING, "detection"]:
        return TaskSubmitResponse(task_id="", status="error", message=f"未知模式: {mode}")

    # STNNet 走独立的管线 (tracking / detection)
    if model == "STNNet":
        from app.services.stnnet_video import create_stnnet_video_task, run_stnnet_video_async
        stn_mode = mode if mode in ("tracking", "detection") else "tracking"
        task_id = create_stnnet_video_task(filename=filename, mode=stn_mode,
                                           size_mb=round(os.path.getsize(filepath) / (1024 * 1024), 2))
        run_stnnet_video_async(task_id, filepath)
        mode_label = "追踪" if stn_mode == "tracking" else "检测"
        return TaskSubmitResponse(
            task_id=task_id, status="submitted",
            message=f"STNNet 视频{mode_label}任务已提交"
        )

    task_id = create_task(mode, filename=filename, size_mb=round(os.path.getsize(filepath) / (1024 * 1024), 2))

    if mode == MODE_COUNTING:
        run_counting_async(task_id, filepath, model)
    else:
        return TaskSubmitResponse(
            task_id=task_id, status="pending",
            message="MODE_TRACKING 暂未接入，请使用 counting 模式"
        )

    return TaskSubmitResponse(
        task_id=task_id, status="submitted", message="推理任务已提交"
    )


# ============================================================
#  GET /task/{task_id}  查询进度
# ============================================================
@router.get("/task/{task_id}")
async def get_task(task_id: str):
    from app.services.inference_service import get_task_status
    from app.services.stnnet_video import get_stnnet_video_task
    from app.db import db_get_task
    if task_id.startswith("stv_"):
        status = get_stnnet_video_task(task_id)
        # 内存中没有则从DB回退(服务重启后)
        if status is None:
            status = db_get_task(task_id)
    else:
        status = get_task_status(task_id)
    if status is None:
        return {"error": "任务不存在"}
    return status


# ============================================================
#  GET /result/{task_id}  查询结果
# ============================================================
@router.get("/result/{task_id}")
async def get_result(task_id: str):
    from app.services.inference_service import get_task_result
    from app.services.stnnet_video import get_stnnet_video_result
    from app.db import db_get_result
    if task_id.startswith("stv_"):
        result = get_stnnet_video_result(task_id)
        # 内存中没有则从DB回退(服务重启后)
        if result is None:
            result = db_get_result(task_id)
        # 兼容旧数据: points → peaks
        if result and result.get("frames"):
            need_reload = False
            for f in result["frames"]:
                if "points" in f:
                    # 有 points 字段时直接转换
                    if not f.get("peaks"):
                        f["peaks"] = [[p["x"], p["y"]] for p in f["points"]]
                elif not f.get("peaks"):
                    # DB 瘦身格式丢弃了 points, peaks 为空时从 JSON 文件恢复
                    need_reload = True
                    break
            if need_reload:
                import json, os
                from app.services.stnnet_video import STNNET_VIDEO_RESULT_DIR
                json_path = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}_result.json")
                if os.path.exists(json_path):
                    with open(json_path) as jf:
                        disk_data = json.load(jf)
                    disk_frames = {f["frame"]: f for f in disk_data.get("frames", [])}
                    for f in result["frames"]:
                        df = disk_frames.get(f["frame"])
                        if df and "points" in df:
                            f["peaks"] = [[p["x"], p["y"]] for p in df["points"]]
                        elif df and "peaks" in df:
                            f["peaks"] = df["peaks"]
    else:
        result = get_task_result(task_id)
    if result is None:
        return {"error": "结果不存在，任务可能未完成"}
    return result


# ============================================================
#  GET /list  历史任务
# ============================================================
@router.get("/list")
async def list_tasks():
    from app.services.inference_service import list_tasks as list_infer_tasks
    from app.services.stnnet_video import _stnnet_video_tasks
    tasks = list_infer_tasks()
    # 合并 STNNet 视频任务(内存中的)
    seen_ids = {t.get('task_id') for t in tasks}
    for tid, t in _stnnet_video_tasks.items():
        if tid not in seen_ids:
            tasks.append(t)
            seen_ids.add(tid)
    return tasks


# ============================================================
#  DELETE /task/{task_id}  删除任务
# ============================================================
@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    import shutil
    from app.db import db_delete_task
    from app.services.inference_service import RESULT_DIR as INFER_RESULT_DIR

    # 1. 删除数据库记录
    db_delete_task(task_id)

    # 2. 如果是 STNNet 视频任务，清理内存中的任务
    from app.services.stnnet_video import _stnnet_video_tasks, STNNET_VIDEO_RESULT_DIR
    if task_id.startswith("stv_"):
        _stnnet_video_tasks.pop(task_id, None)
        # 清理 STNNet 结果文件
        stnnet_dir = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}_density")
        if os.path.exists(stnnet_dir):
            shutil.rmtree(stnnet_dir)
        for suffix in ["_tracking.mp4", "_result.json"]:
            p = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}{suffix}")
            if os.path.exists(p):
                os.remove(p)
    else:
        # 清理普通推理结果文件
        for suffix in ["_result.mp4", "_result.json", "_density"]:
            p = os.path.join(INFER_RESULT_DIR, f"{task_id}{suffix}")
            if os.path.exists(p):
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)

    return {"ok": True, "task_id": task_id}


# ============================================================
#  GET /download/{task_id}  下载标注视频
# ============================================================
@router.get("/download/{task_id}")
async def download_video(task_id: str):
    # STNNet 视频路径不同
    if task_id.startswith("stv_"):
        from app.services.stnnet_video import STNNET_VIDEO_RESULT_DIR
        video_path = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}_tracking.mp4")
    else:
        video_path = os.path.join(RESULT_DIR, f"{task_id}_result.mp4")
    if not os.path.exists(video_path):
        return {"error": "视频不存在"}
    return FileResponse(video_path, media_type="video/mp4",
                        filename=f"{task_id}_result.mp4")


# ============================================================
#  POST /image/upload  上传单张图片
# ============================================================
@router.post("/image/upload")
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        return {"error": f"不支持格式 {ext}, 允许: .jpg/.png/.bmp/.tiff"}

    safe_name = f"img_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    return {"filename": safe_name, "filepath": filepath}


# ============================================================
#  POST /image/analyze  分析单张图片
# ============================================================
@router.post("/image/analyze")
async def analyze_image(filename: str = Query(..., description="图片文件名")):
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return {"error": f"文件不存在: {filename}"}

    from app.services.inference_service import run_single_image
    result = run_single_image(filepath)
    return result


# ============================================================
#  GET /image/result/{image_id}  获取结果图片
# ============================================================
@router.get("/image/result/{image_id}")
async def get_result_image(image_id: str):
    result_path = os.path.join(RESULT_DIR, f"{image_id}_result.jpg")
    if not os.path.exists(result_path):
        return {"error": "结果图片不存在"}
    return FileResponse(result_path, media_type="image/jpeg",
                        filename=f"{image_id}_result.jpg")


# ============================================================
#  GET /zoom/{task_id}/{frame_idx}  获取单帧 ROI 放大对比图
# ============================================================
@router.get("/zoom/{task_id}/{frame_idx}")
async def get_zoom_image(
    task_id: str, frame_idx: int,
    zoom_scale: float = Query(2.5, description="放大倍数"),
    roi_ratio: float = Query(0.25, description="ROI 区域占图像比例"),
):
    from app.services.inference_service import generate_zoom_image, get_task_result
    result = get_task_result(task_id)
    if result is None:
        return {"error": "任务结果不存在"}

    video_path = result.get("video_path", "")
    if not os.path.exists(video_path):
        return {"error": "原始视频不存在"}

    zoom_path = os.path.join(
        RESULT_DIR,
        f"{task_id}_zoom_{frame_idx:06d}_s{zoom_scale:.1f}_r{roi_ratio:.2f}.jpg"
    )

    # 缓存
    if os.path.exists(zoom_path):
        return FileResponse(zoom_path, media_type="image/jpeg")

    try:
        output_path = generate_zoom_image(task_id, video_path, frame_idx, zoom_scale, roi_ratio)
        return FileResponse(output_path, media_type="image/jpeg")
    except Exception as e:
        return {"error": f"生成放大对比图失败: {str(e)}"}


# ============================================================
#  POST /zoom-custom/{task_id}/{frame_idx}  自定义 ROI 放大对比图
# ============================================================
@router.post("/zoom-custom/{task_id}/{frame_idx}")
async def get_zoom_custom_image(
    task_id: str, frame_idx: int,
    x1: int = Query(..., description="ROI 左上角 X 坐标"),
    y1: int = Query(..., description="ROI 左上角 Y 坐标"),
    x2: int = Query(..., description="ROI 右下角 X 坐标"),
    y2: int = Query(..., description="ROI 右下角 Y 坐标"),
    zoom_scale: float = Query(2.5, description="放大倍数"),
):
    from app.services.inference_service import generate_zoom_custom, get_task_result
    result = get_task_result(task_id)
    if result is None:
        return {"error": "任务结果不存在"}

    video_path = result.get("video_path", "")
    if not os.path.exists(video_path):
        return {"error": "原始视频不存在"}

    if x2 <= x1 or y2 <= y1:
        return {"error": "ROI 坐标无效，请确保 x2 > x1 且 y2 > y1"}

    zoom_path = os.path.join(
        RESULT_DIR,
        f"{task_id}_zoom_custom_{frame_idx:06d}_{x1}_{y1}_{x2}_{y2}_s{zoom_scale:.1f}.jpg"
    )

    # 缓存
    if os.path.exists(zoom_path):
        return FileResponse(zoom_path, media_type="image/jpeg")

    try:
        output_path = generate_zoom_custom(task_id, video_path, frame_idx, x1, y1, x2, y2, zoom_scale)
        return FileResponse(output_path, media_type="image/jpeg")
    except Exception as e:
        return {"error": f"生成自定义 ROI 放大对比图失败: {str(e)}"}


# ============================================================
#  GET /frame/{task_id}/{frame_idx}  获取单帧标注图片
# ============================================================
@router.get("/frame/{task_id}/{frame_idx}")
async def get_frame_image(task_id: str, frame_idx: int):
    from app.services.inference_service import generate_frame_image, get_task_result
    result = get_task_result(task_id)
    if result is None:
        return {"error": "任务结果不存在"}
    
    video_path = result.get("video_path", "")
    if not os.path.exists(video_path):
        return {"error": "原始视频不存在"}
    
    frame_path = os.path.join(RESULT_DIR, f"{task_id}_frame_{frame_idx:06d}.jpg")
    
    # 如果已生成则直接返回
    if os.path.exists(frame_path):
        return FileResponse(frame_path, media_type="image/jpeg")
    
    # 否则实时生成
    try:
        output_path = generate_frame_image(task_id, video_path, frame_idx)
        return FileResponse(output_path, media_type="image/jpeg")
    except Exception as e:
        return {"error": f"生成帧图片失败: {str(e)}"}


# ============================================================
#  GET /density/{task_id}/{frame_idx}  获取单帧密度热力图
# ============================================================
@router.get("/density/{task_id}/{frame_idx}")
async def get_density_image(
    task_id: str, frame_idx: int,
    cmap: str = Query("jet", description="配色方案: jet/hot/plasma/inferno/viridis/cool"),
    peaks: bool = Query(True, description="是否叠加检测点"),
    contour: bool = Query(False, description="是否叠加等高线"),
    alpha: float = Query(0.6, description="热力图透明度"),
):
    from app.services.inference_service import generate_density_image, get_task_result

    # STNNet 任务: 推理时已保存热力图，直接返回
    if task_id.startswith("stv_"):
        stn_heatmap = os.path.join(
            RESULT_DIR, "stnnet_videos", f"{task_id}_density",
            f"heatmap_{frame_idx:06d}.jpg")
        if os.path.exists(stn_heatmap):
            return FileResponse(stn_heatmap, media_type="image/jpeg")
        return {"error": f"密度热力图不存在 (frame={frame_idx})"}

    result = get_task_result(task_id)
    if result is None:
        return {"error": "任务结果不存在"}
    
    video_path = result.get("video_path", "")
    if not os.path.exists(video_path):
        return {"error": "原始视频不存在"}
    
    density_path = os.path.join(
        RESULT_DIR,
        f"{task_id}_density_{frame_idx:06d}_{cmap}_{int(peaks)}_{int(contour)}_{alpha:.1f}.jpg"
    )
    
    # 缓存
    if os.path.exists(density_path):
        return FileResponse(density_path, media_type="image/jpeg")
    
    try:
        output_path = generate_density_image(task_id, video_path, frame_idx, cmap, peaks, contour, alpha)
        return FileResponse(output_path, media_type="image/jpeg")
    except Exception as e:
        return {"error": f"生成密度图失败: {str(e)}"}


# ============================================================
#  GET /density-grid/{task_id}/{frame_idx}  STNNet 密度网格 (3D 地形)
# ============================================================
@router.get("/density-grid/{task_id}/{frame_idx}")
async def get_density_grid(task_id: str, frame_idx: int):
    if not task_id.startswith("stv_"):
        return {"error": "仅支持 STNNet 任务"}
    grid_path = os.path.join(
        RESULT_DIR, "stnnet_videos", f"{task_id}_density",
        f"grid_{frame_idx:06d}.json")
    if os.path.exists(grid_path):
        return FileResponse(grid_path, media_type="application/json")
    return {"error": "密度网格不存在"}


# ============================================================
#  POST /heatmap-video/{task_id}  生成热力图视频
# ============================================================
@router.post("/heatmap-video/{task_id}")
async def create_heatmap_video(
    task_id: str,
    cmap: str = Query("jet"),
    peaks: bool = Query(True),
    contour: bool = Query(False),
    alpha: float = Query(0.6),
    sample_every: int = Query(1, description="每隔N帧采样"),
):
    from app.services.inference_service import get_task_result, generate_heatmap_video
    result = get_task_result(task_id)
    if result is None:
        return {"error": "任务结果不存在，请先完成推理"}

    video_path = result.get("video_path", "")
    if not os.path.exists(video_path):
        return {"error": "原始视频不存在"}

    total_frames = result.get("total_frames", 0)
    fps = result.get("fps", 10)

    heatmap_task_id = generate_heatmap_video(
        task_id, video_path, total_frames, fps,
        cmap=cmap, peaks=peaks, contour=contour, alpha=alpha,
        sample_every=sample_every,
    )
    return {
        "heatmap_task_id": heatmap_task_id,
        "status": "submitted",
        "message": "热力图视频生成任务已提交",
    }


# ============================================================
#  GET /heatmap-video/{heatmap_task_id}/status  查询热力图视频进度
# ============================================================
@router.get("/heatmap-video/{heatmap_task_id}/status")
async def get_heatmap_video_status(heatmap_task_id: str):
    from app.services.inference_service import get_heatmap_video_status
    status = get_heatmap_video_status(heatmap_task_id)
    if status is None:
        return {"error": "热力图视频任务不存在"}
    return status


# ============================================================
#  GET /heatmap-video/{heatmap_task_id}/download  下载热力图视频
# ============================================================
@router.get("/heatmap-video/{heatmap_task_id}/download")
async def download_heatmap_video(heatmap_task_id: str):
    from app.services.inference_service import get_heatmap_video_status
    status = get_heatmap_video_status(heatmap_task_id)
    if status is None or status.get("status") != "done":
        return {"error": "热力图视频尚未生成完成"}

    video_path = status.get("output_video", "")
    if not os.path.exists(video_path):
        return {"error": "视频文件不存在"}

    return FileResponse(video_path, media_type="video/mp4",
                        filename=f"{heatmap_task_id}.mp4")


# ============================================================
#  WS /ws/{task_id}  WebSocket 实时进度
# ============================================================
@router.websocket("/ws/{task_id}")
async def websocket_progress(ws: WebSocket, task_id: str):
    from app.services.inference_service import register_progress_callback, unregister_progress_callback
    import asyncio
    import json as json_module

    await ws.accept()

    queue = asyncio.Queue()

    def on_progress(data):
        asyncio.run_coroutine_threadsafe(queue.put(data), asyncio.get_event_loop())

    register_progress_callback(task_id, on_progress)

    try:
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=5.0)
                await ws.send_text(json_module.dumps(data, ensure_ascii=False))
                queue.task_done()
            except asyncio.TimeoutError:
                await ws.send_text(json_module.dumps({"type": "ping"}))

            try:
                await ws.receive_text()
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        unregister_progress_callback(task_id)


# ============================================================
#  结果导出 / 下载中心
# ============================================================

@router.get("/export/csv/{task_id}")
async def export_csv(task_id: str):
    """导出每帧人数统计 CSV（frame, count, peak_count）"""
    import io, csv
    from fastapi.responses import StreamingResponse
    from app.db import db_get_result

    result = db_get_result(task_id)
    if not result:
        return {"error": "结果不存在"}

    frames = result.get("frames", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["frame", "count", "peak_count"])
    for f in frames:
        writer.writerow([f.get("frame", 0), f.get("count", 0), len(f.get("peaks", []))])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_counts.csv"'},
    )


@router.get("/export/peaks/{task_id}")
async def export_peaks(task_id: str):
    """导出所有检测点坐标 CSV（frame, x, y）"""
    import io, csv
    from fastapi.responses import StreamingResponse
    from app.db import db_get_result

    result = db_get_result(task_id)
    if not result:
        return {"error": "结果不存在"}

    frames = result.get("frames", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["frame", "x", "y"])
    for f in frames:
        frame_idx = f.get("frame", 0)
        for peak in f.get("peaks", []):
            writer.writerow([frame_idx, peak[0], peak[1]])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_peaks.csv"'},
    )


@router.get("/export/json/{task_id}")
async def export_json(task_id: str):
    """下载完整结果 JSON 文件"""
    import os
    from fastapi.responses import FileResponse

    json_path = os.path.join(RESULT_DIR, f"{task_id}_result.json")
    if not os.path.exists(json_path):
        return {"error": "JSON 结果文件不存在"}

    return FileResponse(
        json_path,
        media_type="application/json",
        filename=f"{task_id}_result.json",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_result.json"'},
    )


# ============================================================
#  GET /export/pdf/{task_id}  下载 PDF 报告
# ============================================================
@router.get("/export/pdf/{task_id}")
async def export_report(task_id: str):
    """生成并下载任务报告（DOCX 格式）"""
    from app.services.docx_report import build_task_report
    docx_path = build_task_report(task_id)
    if docx_path is None:
        return {"error": "无法生成报告，请确认任务已完成且结果存在"}
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{task_id}_report.docx",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_report.docx"'},
    )


# ============================================================
#  ZIP 打包下载（异步生成 + 下载）
# ============================================================
import threading

_zip_tasks = {}  # {zip_task_id: {"status": "creating"|"done"|"failed", "zip_path": str}}


@router.post("/export/zip/{task_id}")
async def create_zip(task_id: str):
    """触发 ZIP 打包（异步），返回 zip_task_id"""
    import uuid

    zip_task_id = f"zip_{uuid.uuid4().hex[:8]}"
    _zip_tasks[zip_task_id] = {"status": "creating", "zip_path": ""}

    thread = threading.Thread(target=_build_zip, args=(task_id, zip_task_id), daemon=True)
    thread.start()

    return {"zip_task_id": zip_task_id, "status": "creating", "message": "ZIP 打包已开始"}


@router.get("/export/zip/{zip_task_id}/status")
async def get_zip_status(zip_task_id: str):
    """查询 ZIP 打包进度"""
    info = _zip_tasks.get(zip_task_id)
    if not info:
        return {"error": "ZIP 任务不存在"}
    return info


@router.get("/export/zip/{zip_task_id}/download")
async def download_zip(zip_task_id: str):
    """下载已生成的 ZIP 文件"""
    from fastapi.responses import FileResponse

    info = _zip_tasks.get(zip_task_id)
    if not info or info["status"] != "done":
        return {"error": "ZIP 尚未生成完成"}

    return FileResponse(
        info["zip_path"],
        media_type="application/zip",
        filename=f"{zip_task_id}.zip",
    )


def _build_zip(task_id: str, zip_task_id: str):
    """后台线程：打包结果文件"""
    import os, zipfile, json as json_module

    try:
        zip_path = os.path.join(RESULT_DIR, f"{zip_task_id}.zip")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. 结果 JSON
            json_path = os.path.join(RESULT_DIR, f"{task_id}_result.json")
            if os.path.exists(json_path):
                zf.write(json_path, f"{task_id}_result.json")

            # 2. 标注视频
            video_path = os.path.join(RESULT_DIR, f"{task_id}_result.mp4")
            if os.path.exists(video_path):
                zf.write(video_path, f"{task_id}_result.mp4")

            # 3. CSV 统计（内联生成）
            from app.db import db_get_result
            import io, csv
            result = db_get_result(task_id)
            if result and result.get("frames"):
                frames = result["frames"]
                csv_buf = io.StringIO()
                writer = csv.writer(csv_buf)
                writer.writerow(["frame", "count", "peak_count"])
                for f in frames:
                    writer.writerow([f.get("frame", 0), f.get("count", 0), len(f.get("peaks", []))])
                zf.writestr(f"{task_id}_counts.csv", csv_buf.getvalue())

                # 4. 采样帧图片（每 30 帧一张）
                import cv2
                cap = cv2.VideoCapture(result.get("video_path", ""))
                if cap.isOpened():
                    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    sample_rate = max(1, total // 10)
                    for fi in range(1, total + 1, sample_rate):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, fi - 1)
                        ret, frame = cap.read()
                        if ret:
                            _, img_bytes = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            zf.writestr(f"frames/frame_{fi:06d}.jpg", img_bytes.tobytes())
                    cap.release()

        _zip_tasks[zip_task_id] = {"status": "done", "zip_path": zip_path}
    except Exception as e:
        _zip_tasks[zip_task_id] = {"status": "failed", "zip_path": "", "error": str(e)}
