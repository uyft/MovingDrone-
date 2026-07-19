"""
DroneCrowd AI Agent — 工具注册表

每个工具包含：
  - name:        工具名（LLM function calling 用）
  - description: 工具描述（LLM 据此决定何时调用）
  - parameters:  JSON Schema 参数定义
  - handler:     实际执行函数
  - require_confirm: 是否需要用户二次确认
"""

import os
import json
import subprocess

# ============================================================
#  工具执行函数
# ============================================================

def _check_platform_status() -> dict:
    """检查平台整体运行状态"""
    import torch

    # 检查后端端口
    backend_ok = False
    try:
        result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        backend_ok = ":8000" in result.stdout
    except Exception:
        pass

    # GPU 状态
    gpu_available = torch.cuda.is_available()
    gpu_info = {}
    if gpu_available:
        gpu_info = {
            "gpu_count": torch.cuda.device_count(),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "N/A",
            "gpu_memory": f"{torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB" if torch.cuda.device_count() > 0 else "N/A",
        }

    # 模型加载状态
    from app.services.inference_service import _counter, _gd3a_model, _yolo_model
    models = {
        "STEERER": _counter is not None,
        "GD3A": _gd3a_model is not None,
        "YOLO11": _yolo_model is not None,
    }

    # 数据库统计
    from app.db import db_list_tasks
    tasks = db_list_tasks()
    task_stats = {
        "total": len(tasks),
        "done": sum(1 for t in tasks if t.get("status") == "done"),
        "running": sum(1 for t in tasks if t.get("status") == "running"),
        "pending": sum(1 for t in tasks if t.get("status") == "pending"),
        "failed": sum(1 for t in tasks if t.get("status") == "failed"),
    }

    return {
        "backend": "运行中" if backend_ok else "未检测到",
        "gpu": gpu_info,
        "models_loaded": models,
        "task_stats": task_stats,
    }


def _list_tasks(status_filter: str = "all") -> dict:
    """列出所有历史推理任务"""
    from app.db import db_list_tasks
    tasks = db_list_tasks()

    if status_filter and status_filter != "all":
        tasks = [t for t in tasks if t.get("status") == status_filter]

    # 精简返回，避免 token 浪费
    summary = []
    for t in tasks[:20]:  # 最多返回 20 条
        summary.append({
            "task_id": t.get("task_id", ""),
            "status": t.get("status", ""),
            "progress": t.get("progress", 0),
            "model": t.get("model", ""),
            "mode": t.get("mode", ""),
            "filename": t.get("filename", ""),
            "created_at": t.get("created_at", ""),
            "total_frames": t.get("total_frames", 0),
        })

    return {
        "total": len(tasks),
        "shown": len(summary),
        "tasks": summary,
    }


def _get_task_status(task_id: str) -> dict:
    """查询指定任务状态"""
    from app.services.inference_service import get_task_status as _get_status
    from app.services.stnnet_video import get_stnnet_video_task
    from app.db import db_get_task

    if task_id.startswith("stv_"):
        status = get_stnnet_video_task(task_id)
        if status is None:
            status = db_get_task(task_id)
    else:
        status = _get_status(task_id)

    if status is None:
        return {"error": f"任务 {task_id} 不存在"}

    return {
        "task_id": status.get("task_id", task_id),
        "status": status.get("status", "unknown"),
        "progress": status.get("progress", 0),
        "message": status.get("message", ""),
        "model": status.get("model", ""),
        "mode": status.get("mode", ""),
        "filename": status.get("filename", ""),
    }


def _get_task_result(task_id: str) -> dict:
    """获取推理结果摘要"""
    from app.services.inference_service import get_task_result as _get_result
    from app.services.stnnet_video import get_stnnet_video_result
    from app.db import db_get_result

    if task_id.startswith("stv_"):
        result = get_stnnet_video_result(task_id)
        if result is None:
            result = db_get_result(task_id)
    else:
        result = _get_result(task_id)

    if result is None:
        return {"error": f"任务 {task_id} 结果不存在，可能尚未完成"}

    frames = result.get("frames", [])
    if not frames:
        return {"error": f"任务 {task_id} 没有帧数据"}

    counts = [f.get("count", 0) for f in frames]
    total_frames = len(counts)
    avg_count = sum(counts) / total_frames if total_frames > 0 else 0
    max_count = max(counts) if counts else 0
    min_count = min(counts) if counts else 0
    max_frame = counts.index(max_count) + 1 if counts else 0

    # 找出人数变化最大的相邻帧
    max_change = 0
    max_change_frame = 0
    for i in range(1, len(counts)):
        change = abs(counts[i] - counts[i-1])
        if change > max_change:
            max_change = change
            max_change_frame = i + 1

    return {
        "task_id": task_id,
        "status": result.get("status", "done"),
        "video_path": result.get("video_path", ""),
        "total_frames": total_frames,
        "total_time": result.get("total_time", 0),
        "fps": result.get("fps", 0),
        "resolution": f"{result.get('width', '?')}x{result.get('height', '?')}",
        "statistics": {
            "avg_count": round(avg_count, 1),
            "max_count": max_count,
            "max_count_frame": max_frame,
            "min_count": min_count,
            "max_frame_change": max_change,
            "max_change_frame": max_change_frame,
        },
        "sample_counts": counts[:5] if total_frames <= 10 else
                         counts[:3] + ["..."] + counts[-3:],
    }


def _analyze_video(filename: str, model: str = "STEERER", mode: str = "counting") -> dict:
    """触发视频分析"""
    from app.config import UPLOAD_DIR

    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return {"error": f"文件 {filename} 不存在。请先上传视频到平台。"}

    valid_models = ["STEERER", "GD3A_VGG16", "GD3A_ResNet50", "YOLO11", "STNNet"]
    if model not in valid_models:
        return {"error": f"不支持的模型 {model}，可选：{valid_models}"}

    if model == "STNNet":
        from app.services.stnnet_video import create_stnnet_video_task, run_stnnet_video_async
        stn_mode = mode if mode in ("tracking", "detection") else "tracking"
        task_id = create_stnnet_video_task(
            filename=filename, mode=stn_mode,
            size_mb=round(os.path.getsize(filepath) / (1024 * 1024), 2)
        )
        run_stnnet_video_async(task_id, filepath)
    else:
        from app.services.inference_service import create_task, run_counting_async, MODE_COUNTING
        if mode != "counting":
            return {"error": f"模型 {model} 暂仅支持 counting 模式"}
        task_id = create_task(MODE_COUNTING, filename=filename,
                             size_mb=round(os.path.getsize(filepath) / (1024 * 1024), 2))
        run_counting_async(task_id, filepath, model)

    return {
        "task_id": task_id,
        "status": "submitted",
        "model": model,
        "mode": mode,
        "message": f"推理任务已提交 (模型: {model}, 模式: {mode})。推理时间取决于视频长度和模型复杂度。",
    }


def _list_dataset_scenes(density_filter: str = "all") -> dict:
    """列出数据集场景"""
    from app.services.dataset_test import get_test_scenes, load_scene_labels, count_frames_in_scene

    scenes = get_test_scenes()
    labels = load_scene_labels()

    result = []
    for s in scenes:
        label = labels.get(s, {})
        density = label.get("density", "unknown")
        if density_filter != "all" and str(density) != str(density_filter):
            continue
        result.append({
            "name": s,
            "density": density,
            "time_of_day": label.get("time_of_day", ""),
            "scene_type": label.get("scene_type", ""),
            "frame_count": count_frames_in_scene(s),
        })

    # 按密度分组统计
    density_groups = {}
    for r in result:
        d = r["density"]
        density_groups[d] = density_groups.get(d, 0) + 1

    return {
        "total": len(result),
        "density_distribution": [{"level": k, "count": v} for k, v in sorted(density_groups.items())],
        "scenes": result[:15],  # 最多返回 15 条
    }


def _get_scene_detail(scene_name: str, frame_idx: int = 0) -> dict:
    """获取场景标注详情"""
    from app.services.dataset_test import load_gt_for_scene, count_frames_in_scene, load_scene_labels

    gt_counts = load_gt_for_scene(scene_name)
    if not gt_counts:
        return {"error": f"场景 {scene_name} 不存在或标注数据为空"}

    labels = load_scene_labels()
    label = labels.get(scene_name, {})

    total_frames = len(gt_counts)
    counts = list(gt_counts.values())
    total_people = sum(counts)

    result = {
        "scene_name": scene_name,
        "total_frames": total_frames,
        "total_annotated_people": total_people,
        "avg_per_frame": round(total_people / total_frames, 1) if total_frames > 0 else 0,
        "density_level": label.get("density", "unknown"),
        "time_of_day": label.get("time_of_day", ""),
        "scene_type": label.get("scene_type", ""),
    }

    if frame_idx > 0:
        if frame_idx in gt_counts:
            result["frame_detail"] = {
                "frame": frame_idx,
                "count": gt_counts[frame_idx],
            }
        else:
            result["frame_detail"] = {"error": f"帧 {frame_idx} 超出范围 (1-{total_frames})"}

    return result


def _run_dataset_test(test_split: str = "test", model: str = "STEERER", interval: int = 4) -> dict:
    """对数据集运行批量测试"""
    from app.services.dataset_test import create_dataset_task, run_dataset_test_async

    valid_splits = ["test", "val", "train"]
    if test_split not in valid_splits:
        return {"error": f"不支持的数据集划分 {test_split}，可选：{valid_splits}"}

    task_id = create_dataset_task(test_split=test_split, test_interval=interval)
    run_dataset_test_async(task_id, test_split=test_split, test_interval=interval, model_name=model)

    return {
        "task_id": task_id,
        "status": "submitted",
        "test_split": test_split,
        "model": model,
        "message": f"数据集批量测试已提交 ({test_split} 集, 模型: {model})。测试时间取决于场景数量。",
    }


def _get_system_info() -> dict:
    """获取系统整体信息"""
    import torch
    from app.config import (
        GPU_ID, COUNTER_WEIGHT, GD3A_WEIGHT, GD3A_WEIGHT_RESNET50,
        YOLO11_WEIGHT, MAX_LONG, MAX_SHORT
    )
    from app.db import db_list_tasks

    tasks = db_list_tasks()

    return {
        "platform": "DroneCrowd — 无人机视角动态密集人群计数与跟踪",
        "version": "1.0.0 (ICCV 2025 Highlight)",
        "python_version": f"{torch.__version__} (PyTorch)",
        "gpu": {
            "device": GPU_ID,
            "available": torch.cuda.is_available(),
            "name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        },
        "models": {
            "STEERER_counter": COUNTER_WEIGHT,
            "GD3A_VGG16": GD3A_WEIGHT,
            "GD3A_ResNet50": GD3A_WEIGHT_RESNET50,
            "YOLO11": YOLO11_WEIGHT,
        },
        "inference_config": {
            "max_resolution": f"{MAX_LONG}x{MAX_SHORT}",
        },
        "task_summary": {
            "total": len(tasks),
            "completed": sum(1 for t in tasks if t.get("status") == "done"),
        },
    }


def _explain_metric(metric_name: str) -> dict:
    """解释评估指标"""
    METRICS_KB = {
        "mae": {
            "name": "MAE (Mean Absolute Error)",
            "formula": "Σ|预测值 - 真实值| / N",
            "description": "平均绝对误差，衡量预测人数与真实人数的平均偏差。越低越好。",
            "typical_range": "在 MovingDroneCrowd++ 上，GD³A (VGG16) 约 45，ResNet50 约 40",
        },
        "mse": {
            "name": "MSE (Mean Squared Error)",
            "formula": "Σ(预测值 - 真实值)² / N",
            "description": "均方误差，对大误差施加更大惩罚。越低越好。",
            "typical_range": "GD³A (ResNet50) 约 72",
        },
        "wrae": {
            "name": "WRAE (Weighted Relative Absolute Error)",
            "formula": "Σ|预测值 - 真实值| / Σ真实值",
            "description": "加权相对绝对误差，用总人数归一化的误差。",
        },
        "hota": {
            "name": "HOTA (Higher Order Tracking Accuracy)",
            "formula": "综合考虑检测准确度 (DetA) 和关联准确度 (AssA)",
            "description": "高阶跟踪准确度，是目前最全面的跟踪评估指标。同时衡量检测质量和 ID 保持能力。",
        },
        "mota": {
            "name": "MOTA (Multiple Object Tracking Accuracy)",
            "formula": "1 - (FN + FP + IDSW) / GT",
            "description": "多目标跟踪准确度，综合漏检、误检和 ID 切换。",
        },
        "idf1": {
            "name": "IDF1 (ID F1 Score)",
            "formula": "2 * IDP * IDR / (IDP + IDR)",
            "description": "ID F1 分数，衡量跟踪器保持身份一致性的能力。越高表示 ID 越稳定。",
        },
    }

    key = metric_name.lower().strip()
    if key in METRICS_KB:
        return METRICS_KB[key]
    return {
        "error": f"未找到指标 '{metric_name}'",
        "available": list(METRICS_KB.keys()),
    }


# ============================================================
#  工具注册表
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_platform_status",
            "description": "检查平台整体运行状态：后端是否在线、GPU 状态、模型加载情况、任务统计",
            "parameters": {"type": "object", "properties": {}},
        },
        "handler": _check_platform_status,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "列出所有历史推理任务，可按状态过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["all", "pending", "running", "done", "failed"],
                        "description": "按状态过滤，默认 all"
                    }
                },
            },
        },
        "handler": _list_tasks,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_status",
            "description": "查询指定任务的详细状态和进度",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "任务 ID"}
                },
                "required": ["task_id"],
            },
        },
        "handler": _get_task_status,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_result",
            "description": "获取已完成任务的推理结果摘要（平均/最大/最小人数、帧间变化等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "任务 ID"}
                },
                "required": ["task_id"],
            },
        },
        "handler": _get_task_result,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_video",
            "description": "对已上传的视频触发人群分析推理。视频必须已存在于 uploads 目录中。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "uploads 目录中的视频文件名"},
                    "model": {
                        "type": "string",
                        "enum": ["STEERER", "GD3A_VGG16", "GD3A_ResNet50", "YOLO11", "STNNet"],
                        "description": "推理模型，默认 STEERER"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["counting", "tracking", "detection"],
                        "description": "推理模式，默认 counting"
                    },
                },
                "required": ["filename"],
            },
        },
        "handler": _analyze_video,
        "require_confirm": True,  # 耗时操作，需要确认
    },
    {
        "type": "function",
        "function": {
            "name": "list_dataset_scenes",
            "description": "列出 MovingDroneCrowd++ 数据集中的场景，可按密度等级过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "density_filter": {
                        "type": "string",
                        "enum": ["all", "0", "1", "2", "3"],
                        "description": "密度等级过滤 (0=稀疏, 3=极密集)，默认 all"
                    }
                },
            },
        },
        "handler": _list_dataset_scenes,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "get_scene_detail",
            "description": "获取指定场景的详细标注信息（帧数、人数统计、场景属性）",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_name": {"type": "string", "description": "场景名称，如 scene_1/1"},
                    "frame_idx": {"type": "integer", "description": "可选，指定帧号查看单帧数据"},
                },
                "required": ["scene_name"],
            },
        },
        "handler": _get_scene_detail,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "run_dataset_test",
            "description": "对数据集指定划分运行批量评估测试，计算 MAE/MSE 等指标",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_split": {
                        "type": "string",
                        "enum": ["test", "val", "train"],
                        "description": "数据集划分，默认 test"
                    },
                    "model": {
                        "type": "string",
                        "enum": ["STEERER", "GD3A_VGG16", "GD3A_ResNet50", "YOLO11", "STNNet"],
                        "description": "推理模型"
                    },
                    "interval": {"type": "integer", "description": "帧采样间隔，默认 4"},
                },
            },
        },
        "handler": _run_dataset_test,
        "require_confirm": True,  # 耗时操作，需要确认
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "获取平台版本、配置、可用模型等全局信息",
            "parameters": {"type": "object", "properties": {}},
        },
        "handler": _get_system_info,
        "require_confirm": False,
    },
    {
        "type": "function",
        "function": {
            "name": "explain_metric",
            "description": "解释评估指标的含义、计算公式和典型值",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "指标名称，如 mae, mse, hota, mota, idf1, wrae"
                    }
                },
                "required": ["metric_name"],
            },
        },
        "handler": _explain_metric,
        "require_confirm": False,
    },
]


def get_tool_definitions():
    """返回 OpenAI 兼容的工具定义列表"""
    return [{"type": t["type"], "function": t["function"]} for t in TOOLS]


def get_tool_by_name(name: str):
    """按名称查找工具"""
    for t in TOOLS:
        if t["function"]["name"] == name:
            return t
    return None


def execute_tool(name: str, arguments: dict) -> dict:
    """执行指定工具并返回结果"""
    tool = get_tool_by_name(name)
    if tool is None:
        return {"error": f"未知工具: {name}"}

    try:
        result = tool["handler"](**arguments)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
