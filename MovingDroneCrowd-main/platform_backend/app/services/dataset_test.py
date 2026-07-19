"""
数据集测试服务 —— 集成 test.py 逻辑，跑 MovingDroneCrowd++ 数据集
对测试集每个场景逐帧推理，对比 GT（ground truth）和预测结果

输出结构（per scene_clip）:
{
  "scene_name": "scene_8/1",
  "density_label": "0",       # 密度等级 (0/1/2/3)
  "scene_type": "Nighttime, Urban Commercial Walking Area",
  "frames": [
    {"frame": 1, "gt_count": 25, "pred_count": 23, "gt_peaks": [...], "pred_peaks": [...]},
    ...
  ],
  "mae": 2.5,
  "mse": 3.1,
  "total_gt": 2500,
  "total_pred": 2450,
}
"""
import os
import sys
import json
import time
import threading
import uuid
from enum import Enum

# ============================================================
#  基础配置
# ============================================================
# BASE_DIR: 从 platform_backend/app/services/ 往上推 2 层 → platform_backend/
_UPLOAD_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULT_DIR = os.path.join(_UPLOAD_BASE, "results")
DATASET_RESULT_DIR = os.path.join(RESULT_DIR, "dataset_tests")
os.makedirs(DATASET_RESULT_DIR, exist_ok=True)

# 数据集根路径
DATASET_PATH = '/workspace/MovingDroneCrowd++'

# ============================================================
#  任务缓存
# ============================================================
_dataset_task_cache = {}  # task_id → {status, progress, message, ...}
_dataset_result_cache = {}  # task_id → result dict
_dataset_lock = threading.Lock()


def _emit_dataset_progress(task_id):
    """推送数据集测试进度（预留 WebSocket 接口）"""
    pass  # 后续可接 WebSocket


# ============================================================
#  GT 数据加载
# ============================================================
def load_gt_for_scene(scene_name):
    """
    加载某个场景的 GT 标注数据。
    scene_name 格式: "scene_8/1"
    
    返回: dict, {frame_id: count}
      frame_id 从 1 开始（对应 frames/scene_8/1/1.jpg）
    """
    import pandas as pd
    
    csv_path = os.path.join(DATASET_PATH, 'annotations', f'{scene_name}.csv')
    if not os.path.exists(csv_path):
        return {}
    
    df = pd.read_csv(csv_path, header=None)
    # 列: frame_id, person_id, x, y, w, h, -1, -1, -1, -1
    # frame_id 在 CSV 中从 0 开始，图像文件名从 1 开始
    grouped = df.groupby(0)
    gt_counts = {}
    for frame_id, group in grouped:
        # frame_id 0 对应 1.jpg, frame_id 1 对应 2.jpg
        gt_counts[int(frame_id) + 1] = len(group)
    
    return gt_counts


def load_scene_labels():
    """加载场景标签: scene_name → [density_level, time_of_day, scene_type, ...]"""
    labels_path = os.path.join(DATASET_PATH, 'scene_labels.txt')
    labels = {}
    if not os.path.exists(labels_path):
        return labels
    
    with open(labels_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                scene_name = parts[0]  # e.g. "scene_8/1"
                density_level = parts[1]  # "0"/"1"/"2"/"3"
                time_of_day = parts[2]
                scene_type = parts[3] if len(parts) > 3 else ""
                labels[scene_name] = {
                    "density": density_level,
                    "time_of_day": time_of_day,
                    "scene_type": scene_type,
                }
    return labels


def get_test_scenes():
    """
    获取测试集场景列表，展开为 scene/clip 格式
    返回: list of scene_clip_name
    """
    test_list_path = os.path.join(DATASET_PATH, 'MDC_test.txt')
    if not os.path.exists(test_list_path):
        return []
    
    scene_names = []
    with open(test_list_path, 'r') as f:
        for line in f:
            name = line.strip()
            if name:
                scene_names.append(name)
    
    # 展开 scene → scene/clip
    all_clips = []
    for scene_name in scene_names:
        root = os.path.join(DATASET_PATH, 'frames', scene_name)
        if '/' in scene_name:
            # 已经是 scene/clip 格式
            all_clips.append(scene_name)
        elif os.path.isdir(root):
            clip_names = [d for d in os.listdir(root) if d.isdigit()]
            clip_names = sorted(clip_names, key=int)
            for clip in clip_names:
                all_clips.append(f"{scene_name}/{clip}")
    
    return all_clips


def count_frames_in_scene(scene_name):
    """统计某个场景的帧数"""
    frames_dir = os.path.join(DATASET_PATH, 'frames', scene_name)
    if not os.path.isdir(frames_dir):
        return 0
    files = [f for f in os.listdir(frames_dir) if f.endswith('.jpg')]
    return len(files)


# ============================================================
#  创建和管理数据集测试任务
# ============================================================
def create_dataset_task(test_split="test", test_interval=4):
    """创建数据集测试任务，返回 task_id"""
    task_id = f"dts_{uuid.uuid4().hex[:8]}"
    
    # 获取测试场景列表
    scenes = get_test_scenes()
    
    task = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": f"待测试: {len(scenes)} 个场景",
        "test_split": test_split,
        "test_interval": test_interval,
        "total_scenes": len(scenes),
        "scene_list": scenes,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _dataset_task_cache[task_id] = task
    return task_id


def get_dataset_task_status(task_id):
    """查询数据集测试任务状态"""
    return _dataset_task_cache.get(task_id)


def get_dataset_task_result(task_id):
    """查询数据集测试结果"""
    return _dataset_result_cache.get(task_id)


def list_dataset_tasks():
    """列出所有数据集测试任务"""
    return sorted(
        list(_dataset_task_cache.values()),
        key=lambda t: t.get("created_at", ""),
        reverse=True,
    )


# ============================================================
#  核心: 运行数据集测试
# ============================================================
def run_dataset_test(task_id, test_split="test", test_interval=4, model_name="STEERER"):
    """
    核心推理函数：对测试集每个场景逐帧推理，对比 GT。
    
    由于完整的 VIC/SDNet/GD3A 模型依赖太重（需要训练好的权重），
    这里使用平台已有的 STEERER counter 做逐帧推理。
    
    对于每个场景：
    1. 加载 GT 标注
    2. 逐帧读取图像 → counter 推理 → 获取预测人数
    3. 对比 GT vs Pred
    4. 计算 MAE, MSE 等指标
    """
    import cv2
    import numpy as np
    from app.services.inference_service import _init_heavy, load_counter, preprocess_frame, extract_peaks, _get_device
    
    _init_heavy()
    
    task = _dataset_task_cache.get(task_id)
    if not task:
        return None
    
    task["status"] = "running"
    task["progress"] = 0
    task["message"] = "加载模型..."
    
    # 加载模型
    counter = load_counter()
    device = _get_device()
    
    scenes = task["scene_list"]
    scene_labels = load_scene_labels()
    total_scenes = len(scenes)
    
    all_results = []
    total_frames_processed = 0
    total_frames_all = sum(count_frames_in_scene(s) for s in scenes)
    start_time = time.time()
    
    for scene_idx, scene_name in enumerate(scenes):
        # 加载 GT
        gt_counts = load_gt_for_scene(scene_name)
        if not gt_counts:
            task["message"] = f"跳过 {scene_name}: 无 GT 数据"
            continue
        
        frames_dir = os.path.join(DATASET_PATH, 'frames', scene_name)
        if not os.path.isdir(frames_dir):
            continue
        
        frame_files = sorted(
            [f for f in os.listdir(frames_dir) if f.endswith('.jpg')],
            key=lambda x: int(x.split('.')[0])
        )
        
        # 获取场景标签
        label = scene_labels.get(scene_name, {})
        
        scene_frames = []
        gt_total = 0
        pred_total = 0
        abs_errors = []
        
        for i, frame_file in enumerate(frame_files):
            frame_idx = int(frame_file.split('.')[0])
            
            # 间隔采样
            if (frame_idx - 1) % test_interval != 0 and frame_idx != 1:
                continue
            
            img_path = os.path.join(frames_dir, frame_file)
            frame = cv2.imread(img_path)
            if frame is None:
                continue
            
            # 推理
            tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)
            import torch
            with torch.no_grad():
                density_map = counter(tensor.to(device))
            peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
            pred_count = len(peaks_xy)
            
            # GT
            gt_count = gt_counts.get(frame_idx, 0)
            
            # 记录
            scene_frames.append({
                "frame": frame_idx,
                "gt_count": gt_count,
                "pred_count": pred_count,
                "gt_peaks": [],  # GT peaks 可从 bbox 中心点获取
                "pred_peaks": peaks_xy.tolist() if len(peaks_xy) > 0 else [],
            })
            
            gt_total += gt_count
            pred_total += pred_count
            abs_errors.append(abs(gt_count - pred_count))
            
            total_frames_processed += 1
            
            # 每处理 5 帧释放一次 GIL，防止推理阻塞 HTTP 服务
            if total_frames_processed % 5 == 0:
                time.sleep(0)
        
        # 计算指标
        mae = np.mean(abs_errors) if abs_errors else 0
        mse = np.sqrt(np.mean([e**2 for e in abs_errors])) if abs_errors else 0
        
        scene_result = {
            "scene_name": scene_name,
            "density_label": label.get("density", "unknown"),
            "time_of_day": label.get("time_of_day", ""),
            "scene_type": label.get("scene_type", ""),
            "frames": scene_frames,
            "total_frames": len(scene_frames),
            "mae": round(mae, 2),
            "mse": round(mse, 2),
            "total_gt": gt_total,
            "total_pred": pred_total,
            "accuracy": round(pred_total / gt_total * 100, 1) if gt_total > 0 else 0,
        }
        all_results.append(scene_result)
        
        # 更新进度
        task["progress"] = int((scene_idx + 1) / total_scenes * 100)
        task["message"] = f"测试中 {scene_idx + 1}/{total_scenes}: {scene_name} (MAE={mae:.1f})"
        _emit_dataset_progress(task_id)
    
    elapsed = time.time() - start_time
    
    # 汇总指标
    all_gt = sum(r["total_gt"] for r in all_results)
    all_pred = sum(r["total_pred"] for r in all_results)
    all_frame_count = sum(r["total_frames"] for r in all_results)
    overall_mae = round(sum(r["mae"] * r["total_frames"] for r in all_results) / all_frame_count, 2) if all_frame_count > 0 else 0
    overall_mse = round(np.sqrt(sum(r["mse"]**2 * r["total_frames"] for r in all_results) / all_frame_count), 2) if all_frame_count > 0 else 0
    
    # 按密度分组
    by_density = {}
    for r in all_results:
        d = r["density_label"]
        if d not in by_density:
            by_density[d] = {"mae": 0, "mse": 0, "frames": 0, "gt": 0, "pred": 0, "scenes": 0}
        by_density[d]["mae"] += r["mae"] * r["total_frames"]
        by_density[d]["mse"] += r["mse"]**2 * r["total_frames"]
        by_density[d]["frames"] += r["total_frames"]
        by_density[d]["gt"] += r["total_gt"]
        by_density[d]["pred"] += r["total_pred"]
        by_density[d]["scenes"] += 1
    
    for d in by_density:
        f = by_density[d]["frames"]
        if f > 0:
            by_density[d]["mae"] = round(by_density[d]["mae"] / f, 2)
            by_density[d]["mse"] = round(np.sqrt(by_density[d]["mse"] / f), 2)
    
    result = {
        "task_id": task_id,
        "test_split": test_split,
        "test_interval": test_interval,
        "model": model_name,
        "total_scenes": len(all_results),
        "total_frames": all_frame_count,
        "total_gt": all_gt,
        "total_pred": all_pred,
        "overall_mae": overall_mae,
        "overall_mse": overall_mse,
        "overall_accuracy": round(all_pred / all_gt * 100, 1) if all_gt > 0 else 0,
        "by_density": by_density,
        "scenes": all_results,
        "elapsed": round(elapsed, 1),
    }
    
    # 保存到 JSON 文件
    output_json = os.path.join(DATASET_RESULT_DIR, f"{task_id}.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 更新状态
    task["status"] = "done"
    task["progress"] = 100
    task["message"] = f"完成! {len(all_results)} 场景, MAE={overall_mae}, 耗时 {elapsed:.1f}s"
    _dataset_result_cache[task_id] = result
    
    return result


def run_dataset_test_async(task_id, test_split="test", test_interval=4, model_name="STEERER"):
    """异步启动数据集测试"""
    t = threading.Thread(
        target=run_dataset_test,
        args=(task_id, test_split, test_interval, model_name),
        daemon=True,
    )
    t.start()
    return task_id
