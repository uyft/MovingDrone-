"""
数据集测试 API
"""
import os
from typing import List
from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import FileResponse
from app.services.dataset_test import (
    create_dataset_task,
    get_dataset_task_status,
    get_dataset_task_result,
    list_dataset_tasks,
    run_dataset_test_async,
    get_test_scenes,
    load_scene_labels,
    load_gt_for_scene,
    count_frames_in_scene,
)
from app.services.frame_test import (
    create_frame_test_task,
    get_frame_test_task_status,
    get_frame_test_task_result,
    list_frame_test_tasks,
    save_frame_test_data,
    run_frame_test_async,
    FRAME_TEST_RESULT_DIR,
    create_scene_test_task,
    get_scene_test_status,
    get_scene_test_result,
    run_scene_test_async,
)
from app.services.stnnet_test import (
    STNNET_RESULT_DIR,
    create_stnnet_task,
    get_stnnet_task_status,
    get_stnnet_task_result,
    run_stnnet_test_async,
    run_stnnet_upload_test_async,
)

router = APIRouter()


# ============================================================
#  GET /scenes  列出测试集场景
# ============================================================
@router.get("/scenes")
async def list_test_scenes():
    scenes = get_test_scenes()
    scene_labels = load_scene_labels()
    result = []
    for s in scenes:
        label = scene_labels.get(s, {})
        result.append({
            "scene_name": s,
            "density": label.get("density", "unknown"),
            "time_of_day": label.get("time_of_day", ""),
            "scene_type": label.get("scene_type", ""),
            "frame_count": count_frames_in_scene(s),
        })
    return result


# ============================================================
#  GET /gt/{scene_name}  获取某场景的 GT 数据
# ============================================================
@router.get("/gt/{scene_name:path}")
async def get_scene_gt(scene_name: str):
    """获取场景的 GT 标注数据（每帧人数）"""
    gt_counts = load_gt_for_scene(scene_name)
    if not gt_counts:
        return {"error": "场景 GT 数据不存在", "scene_name": scene_name}
    
    frames = [{"frame": k, "count": v} for k, v in sorted(gt_counts.items())]
    return {
        "scene_name": scene_name,
        "total_frames": len(frames),
        "total_count": sum(v for v in gt_counts.values()),
        "frames": frames,
    }


# ============================================================
#  GET /gt/{scene_name}/{frame_idx}  获取某帧的 GT 标注详情
# ============================================================
@router.get("/gt/{scene_name:path}/{frame_idx}")
async def get_frame_gt(scene_name: str, frame_idx: int):
    """获取某一帧的 GT 标注详情（每个人的坐标）"""
    import pandas as pd
    import os
    
    csv_path = os.path.join(
        '/workspace/MovingDroneCrowd++', 'annotations', f'{scene_name}.csv'
    )
    if not os.path.exists(csv_path):
        return {"error": "标注文件不存在"}
    
    df = pd.read_csv(csv_path, header=None)
    # frame_id 在 CSV 中从 0 开始，图像从 1 开始
    frame_data = df[df[0] == (frame_idx - 1)]
    
    persons = []
    for _, row in frame_data.iterrows():
        persons.append({
            "person_id": int(row[1]),
            "x": int(row[2]),
            "y": int(row[3]),
            "w": int(row[4]),
            "h": int(row[5]),
        })
    
    return {
        "scene_name": scene_name,
        "frame": frame_idx,
        "count": len(persons),
        "persons": persons,
    }


# ============================================================
#  POST /test/start  发起数据集测试
# ============================================================
@router.post("/test/start")
async def start_dataset_test(
    test_split: str = Query("test", description="数据集划分: test/val/train"),
    test_interval: int = Query(4, description="帧采样间隔"),
    model: str = Query("STEERER", description="模型: STEERER"),
):
    task_id = create_dataset_task(test_split=test_split, test_interval=test_interval)
    run_dataset_test_async(task_id, test_split=test_split, test_interval=test_interval, model_name=model)
    
    return {
        "task_id": task_id,
        "status": "submitted",
        "message": "数据集测试已提交",
    }


# ============================================================
#  GET /test/status/{task_id}  查询测试任务进度
# ============================================================
@router.get("/test/status/{task_id}")
async def get_test_status(task_id: str):
    status = get_dataset_task_status(task_id)
    if status is None:
        return {"error": "任务不存在"}
    return status


# ============================================================
#  GET /test/result/{task_id}  查询测试结果
# ============================================================
@router.get("/test/result/{task_id}")
async def get_test_result(task_id: str):
    result = get_dataset_task_result(task_id)
    if result is None:
        return {"error": "结果不存在，任务可能未完成"}
    return result


# ============================================================
#  GET /test/list  列出所有测试任务
# ============================================================
@router.get("/test/list")
async def list_tests():
    return list_dataset_tasks()


# ============================================================
#  自定义帧测试 (Frame Test) API
# ============================================================

#  POST /frame-test/upload  上传帧图片 + 标签 CSV
# ============================================================
@router.post("/frame-test/upload")
async def upload_frame_test(
    files: List[UploadFile] = File(..., description="帧图片文件列表"),
    label_file: UploadFile = File(..., description="标签 CSV 文件"),
    model: str = Query("GD3A", description="推理模型: GD3A (时序,11列密度图) 或 STEERER (单帧,3列图)"),
):
    """
    上传自定义帧测试数据：多张帧图片 + 一个标签 CSV。

    CSV 支持两种格式：
    1. frame,count          （每帧总人数）
    2. frame,person_id,x,y,w,h  （每个人的坐标）

    frame 从 1 开始，对应 1.jpg, 2.jpg...

    model 参数：
    - GD3A: 完整时序模型，生成 Global/Shared/IN/OUT 密度图对比
    - STEERER: 单帧计数器，快速推理
    """
    task_id = create_frame_test_task()

    # 读取帧图片
    frame_files = []
    for f in files:
        content = await f.read()
        if not content:
            continue
        frame_files.append((f.filename, content))

    # 读取标签
    label_content = await label_file.read()

    # 保存数据
    task_dir = save_frame_test_data(task_id, frame_files, label_content)

    # 启动异步分析
    run_frame_test_async(task_id, task_dir, model_mode=model)

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": f"帧测试已提交 ({model})，共 {len(frame_files)} 帧",
        "total_frames": len(frame_files),
        "model": model,
    }


# ============================================================
#  GET /frame-test/status/{task_id}  查询帧测试任务进度
# ============================================================
@router.get("/frame-test/status/{task_id}")
async def get_frame_test_status(task_id: str):
    status = get_frame_test_task_status(task_id)
    if status is None:
        return {"error": "任务不存在"}
    return status


# ============================================================
#  GET /frame-test/result/{task_id}  查询帧测试结果
# ============================================================
@router.get("/frame-test/result/{task_id}")
async def get_frame_test_result(task_id: str):
    result = get_frame_test_task_result(task_id)
    if result is None:
        return {"error": "结果不存在，任务可能未完成"}
    return result


# ============================================================
#  GET /frame-test/image/{task_id}/{frame_idx}  获取单帧对比图（兼容旧版）
# ============================================================
@router.get("/frame-test/image/{task_id}/{frame_idx}")
async def get_frame_test_image(task_id: str, frame_idx: int):
    img_path = os.path.join(FRAME_TEST_RESULT_DIR, task_id, f"frame_{frame_idx:06d}.jpg")
    if not os.path.exists(img_path):
        return {"error": "图片不存在"}
    return FileResponse(img_path, media_type="image/jpeg", filename=f"{task_id}_frame_{frame_idx}.jpg")


# ============================================================
#  GET /frame-test/density/{task_id}/{frame_idx}/{map_name}
#  获取单张独立密度图（GT Global, Pre Global, GT Shared 等）
# ============================================================
@router.get("/frame-test/density/{task_id}/{frame_idx}/{map_name}")
async def get_frame_test_density(task_id: str, frame_idx: int, map_name: str):
    img_path = os.path.join(FRAME_TEST_RESULT_DIR, task_id, map_name)
    if not os.path.exists(img_path):
        return {"error": f"密度图不存在: {map_name}"}
    return FileResponse(img_path, media_type="image/jpeg", filename=map_name)


# ============================================================
#  GET /frame-test/list  列出所有帧测试任务
# ============================================================
@router.get("/frame-test/list")
async def list_frame_tests():
    return list_frame_test_tasks()


# ============================================================
#  Scene 直接测试 API（不走上传，直接用数据集路径）
# ============================================================

# POST /scene-test/start  用数据集 scene 跑 GD3A 推理
@router.post("/scene-test/start")
async def start_scene_test(
    scene_name: str = Query("scene_1/1", description="场景名称，如 scene_1/1"),
    test_interval: int = Query(4, description="帧采样间隔"),
):
    """
    直接用数据集中的 scene 跑 GD3A 时序推理，无需上传文件。
    适用于在前端快速测试已有数据集的场景。
    """
    import os
    dataset_path = '/workspace/MovingDroneCrowd++'
    frames_dir = os.path.join(dataset_path, "frames", scene_name)
    if not os.path.isdir(frames_dir):
        return {"error": f"场景不存在: {scene_name}", "frames_dir": frames_dir}

    csv_path = os.path.join(dataset_path, "annotations", f"{scene_name}.csv")
    if not os.path.exists(csv_path):
        return {"error": f"标注文件不存在: {csv_path}"}

    task_id = create_scene_test_task(scene_name)
    run_scene_test_async(task_id, scene_name, test_interval)

    frame_count = len([f for f in os.listdir(frames_dir) if f.endswith('.jpg')])

    return {
        "task_id": task_id,
        "status": "submitted",
        "scene_name": scene_name,
        "total_frames": frame_count,
        "message": f"Scene 测试已提交: {scene_name} ({frame_count} 帧)",
    }


# GET /scene-test/status/{task_id}
@router.get("/scene-test/status/{task_id}")
async def get_scene_test_status_api(task_id: str):
    status = get_scene_test_status(task_id)
    if status is None:
        return {"error": "任务不存在"}
    return status


# GET /scene-test/result/{task_id}
@router.get("/scene-test/result/{task_id}")
async def get_scene_test_result_api(task_id: str):
    result = get_scene_test_result(task_id)
    if result is None:
        return {"error": "结果不存在，任务可能未完成"}
    return result


# GET /scene-test/image/{task_id}/{frame_idx}
@router.get("/scene-test/image/{task_id}/{frame_idx}")
async def get_scene_test_image(task_id: str, frame_idx: int):
    img_path = os.path.join(FRAME_TEST_RESULT_DIR, task_id, f"frame_{frame_idx:06d}.jpg")
    if not os.path.exists(img_path):
        return {"error": "图片不存在"}
    return FileResponse(img_path, media_type="image/jpeg", filename=f"{task_id}_frame_{frame_idx}.jpg")


# GET /scene-test/density/{task_id}/{frame_idx}/{map_name}
@router.get("/scene-test/density/{task_id}/{frame_idx}/{map_name}")
async def get_scene_test_density(task_id: str, frame_idx: int, map_name: str):
    img_path = os.path.join(FRAME_TEST_RESULT_DIR, task_id, map_name)
    if not os.path.exists(img_path):
        return {"error": f"密度图不存在: {map_name}"}
    return FileResponse(img_path, media_type="image/jpeg", filename=map_name)


# ============================================================
#  STNNet 场景测试 API
# ============================================================

# POST /stnnet-test/upload  上传帧图片 + 标签 CSV（STNNet 推理）
@router.post("/stnnet-test/upload")
async def upload_stnnet_test(
    files: List[UploadFile] = File(..., description="帧图片文件列表"),
    label_file: UploadFile = File(..., description="标签 CSV 文件"),
    model: str = Query("STNNet", description="推理模型"),
):
    """上传自定义帧测试数据，使用 STNNet 模型推理"""
    from app.services.frame_test import save_frame_test_data
    from app.services.stnnet_test import create_stnnet_task

    task_id = create_stnnet_task("用户上传帧")

    # 读取帧图片
    frame_files = []
    for f in files:
        content = await f.read()
        if not content:
            continue
        frame_files.append((f.filename, content))

    # 读取标签
    label_content = await label_file.read()

    # 保存数据（复用 frame_test 的存储逻辑）
    task_dir = save_frame_test_data(task_id, frame_files, label_content)

    # 启动 STNNet 异步推理
    run_stnnet_upload_test_async(task_id, task_dir)

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": f"STNNet 帧测试已提交，共 {len(frame_files)} 帧",
        "total_frames": len(frame_files),
        "model": model,
    }


# POST /stnnet-test/start
@router.post("/stnnet-test/start")
async def start_stnnet_test(
    scene_name: str = Query("scene_1/1", description="场景名称，如 scene_1/1"),
    test_interval: int = Query(1, description="推理间隔，1=逐帧推理"),
):
    task_id = create_stnnet_task(scene_name)
    run_stnnet_test_async(task_id, scene_name, test_interval)
    return {"task_id": task_id, "scene_name": scene_name, "status": "started"}


# GET /stnnet-test/status/{task_id}
@router.get("/stnnet-test/status/{task_id}")
async def get_stnnet_test_status_api(task_id: str):
    status = get_stnnet_task_status(task_id)
    if not status:
        return {"error": "任务不存在"}
    return status


# GET /stnnet-test/result/{task_id}
@router.get("/stnnet-test/result/{task_id}")
async def get_stnnet_test_result_api(task_id: str):
    result = get_stnnet_task_result(task_id)
    if not result:
        return {"error": "结果不存在"}
    return result


# GET /stnnet-test/density/{task_id}/{frame_idx}/{map_name}
@router.get("/stnnet-test/density/{task_id}/{frame_idx}/{map_name}")
async def get_stnnet_test_density(task_id: str, frame_idx: int, map_name: str):
    img_path = os.path.join(STNNET_RESULT_DIR, task_id, map_name)
    if not os.path.exists(img_path):
        return {"error": f"密度图不存在: {map_name}"}
    return FileResponse(img_path, media_type="image/jpeg", filename=map_name)
