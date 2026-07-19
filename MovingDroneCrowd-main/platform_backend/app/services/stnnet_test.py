"""
STNNet 目标跟踪/定位模型集成服务

对数据集场景运行 STNNet 推理，输出：
- 密度图（原图大小 + 热力图 + 叠加图）
- 定位点可视化对比图（GT vs 预测，与 visualize_localization.py 一致）
- 每帧预测定位点 TXT

模型：STNNet (cyc_model_best.pth.tar) — 密度 + 定位 + 跟踪 + 循环一致性
"""
import os
import sys
import json
import time
import uuid
import threading
import cv2
import numpy as np
from typing import Dict, List
from copy import deepcopy

# 添加 STNNet 路径
STNNET_PATH = '/workspace/STNNet'
if STNNET_PATH not in sys.path:
    sys.path.insert(0, STNNET_PATH)

from app.config import UPLOAD_DIR, RESULT_DIR

# ============================================================
#  基础配置
# ============================================================
STNNET_RESULT_DIR = os.path.join(RESULT_DIR, "stnnet_tests")
os.makedirs(STNNET_RESULT_DIR, exist_ok=True)

# 数据集路径（与 MovingDroneCrowd++ 一致）
DATASET_PATH = '/workspace/MovingDroneCrowd++'

# STNNet 模型权重
STNNET_MODEL_PATH = os.path.join(STNNET_PATH, "models", "cyc_model_best.pth.tar")

# 全局模型缓存
_stnnet_model = None
_stnnet_lock = threading.Lock()

# 任务缓存
_stnnet_task_cache: Dict[str, dict] = {}
_stnnet_result_cache: Dict[str, dict] = {}


# ============================================================
#  NMS + 定位点提取（复用 STNNet mytest_visualization.py 逻辑）
# ============================================================
def _nms_torch(featmap, kernel=7):
    """PyTorch NMS: 保留局部最大值"""
    import torch
    import torch.nn.functional as F
    pad = (kernel - 1) // 2
    hmax = F.max_pool2d(featmap, (kernel, kernel), stride=1, padding=pad)
    keep = (hmax == featmap)
    return featmap * keep.float(), keep


def _calc_denpt(ourmap, neighbor_thre=8, ratio=2.0):
    """从密度图中提取定位点"""
    import scipy.ndimage as ndimage
    import scipy.ndimage.filters as filters
    ourmap = np.maximum(ourmap, 0)
    data_max = filters.maximum_filter(ourmap, neighbor_thre)
    data_min = filters.minimum_filter(ourmap, neighbor_thre)
    maxima = (ourmap == data_max)
    diffmap = ((data_max - data_min) > 0.001)
    maxima[diffmap == 0] = 0
    labeled, num_objects = ndimage.label(maxima)
    slices = ndimage.find_objects(labeled)
    x, y, sc = [], [], []
    for dy, dx in slices:
        x_center = (dx.start + dx.stop - 1) / 2 * ratio
        x.append(x_center)
        y_center = (dy.start + dy.stop - 1) / 2 * ratio
        y.append(y_center)
        sc.append(float(ourmap[int(y_center / ratio), int(x_center / ratio)]))
    return np.array(x), np.array(y), np.array(sc)


def _density_to_heatmap(density_map, percentile=99.5):
    """密度矩阵 -> JET 热力图 (BGR)"""
    density = np.asarray(density_map, dtype=np.float32)
    density = np.maximum(density, 0.0)
    positive = density[density > 0]
    if positive.size == 0:
        normalized = np.zeros_like(density, dtype=np.uint8)
    else:
        upper = float(np.percentile(positive, percentile))
        if not np.isfinite(upper) or upper <= 0:
            upper = float(positive.max())
        if upper <= 0:
            normalized = np.zeros_like(density, dtype=np.uint8)
        else:
            normalized = np.clip(density / upper * 255.0, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(normalized, cv2.COLORMAP_JET)


def _save_density_map(den_np, prefix, label, result_dir, frame_idx):
    """保存单张密度图为 JPG"""
    den_np = np.maximum(den_np, 0)
    den_norm = den_np / max(den_np.max(), 1e-8) * 255.0
    den_norm = np.clip(den_norm, 0, 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(den_norm, cv2.COLORMAP_JET)
    fname = f"frame_{frame_idx:06d}_{prefix}_{label}.jpg"
    cv2.imwrite(os.path.join(result_dir, fname), heatmap,
                [cv2.IMWRITE_JPEG_QUALITY, 90])
    return fname


def _draw_localization_compare(image, gt_boxes, pred_points, distance_threshold=10.0):
    """
    绘制 GT vs 预测点对比图（与 visualize_localization.py 一致）：
    - 绿色圆：匹配成功的 GT
    - 黄色十字：匹配成功的预测
    - 蓝色圆：漏检 GT
    - 红色十字：误检预测
    - 青色连线：匹配对
    """
    vis = image.copy()
    h, w = vis.shape[:2]

    if len(gt_boxes) == 0 and len(pred_points) == 0:
        return vis, 0, 0, 0, 0.0, 0.0, 0.0

    gt_centers = np.column_stack([
        (gt_boxes[:, 0] + gt_boxes[:, 2]) / 2.0,
        (gt_boxes[:, 1] + gt_boxes[:, 3]) / 2.0,
    ]) if len(gt_boxes) else np.empty((0, 2))

    # 置信度优先一对一匹配
    if len(pred_points) > 0 and len(gt_centers) > 0:
        order = np.argsort(-pred_points[:, 2])
        ordered_pred = pred_points[order]
        distances = np.linalg.norm(
            ordered_pred[:, None, :2] - gt_centers[None, :, :], axis=2)
        matched_gt = set()
        matched_pred = set()
        matches = []
        for oi, pi in enumerate(order):
            best_gt = -1
            best_dist = distance_threshold
            for gi in range(len(gt_centers)):
                if gi in matched_gt:
                    continue
                d = float(distances[oi, gi])
                if d <= best_dist:
                    best_dist = d
                    best_gt = gi
            if best_gt >= 0:
                matched_gt.add(best_gt)
                matched_pred.add(int(pi))
                matches.append((best_gt, int(pi), best_dist))
    else:
        matched_gt, matched_pred, matches = set(), set(), []

    tp = len(matches)
    fp = len(pred_points) - tp
    fn = len(gt_boxes) - tp

    # 连线
    for gi, pi, _ in matches:
        gx, gy = gt_centers[gi]
        px, py = pred_points[pi, :2]
        cv2.line(vis, (int(gx), int(gy)), (int(px), int(py)),
                 (255, 255, 0), 1, cv2.LINE_AA)

    # GT 点
    for gi, (gx, gy) in enumerate(gt_centers):
        color = (0, 255, 0) if gi in matched_gt else (255, 0, 0)
        cv2.circle(vis, (int(gx), int(gy)), 5, color, 2)

    # 预测点
    for pi, row in enumerate(pred_points):
        color = (0, 255, 255) if pi in matched_pred else (0, 0, 255)
        cv2.drawMarker(vis, (int(row[0]), int(row[1])), color,
                       markerType=cv2.MARKER_CROSS, markerSize=12, thickness=2)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    # 左上角图例
    x0, y0 = 16, 16
    entries = [
        ("Matched GT", "circle", (0, 255, 0)),
        ("Matched Pred", "cross", (0, 255, 255)),
        ("Missed GT", "circle", (255, 0, 0)),
        ("False Pred", "cross", (0, 0, 255)),
    ]
    overlay = vis.copy()
    cv2.rectangle(overlay, (x0, y0), (x0 + 240, y0 + 125), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, vis, 0.4, 0, vis)
    for idx, (label, shape, color) in enumerate(entries):
        y = y0 + 22 + idx * 26
        if shape == "circle":
            cv2.circle(vis, (x0 + 16, y), 5, color, 2)
        else:
            cv2.drawMarker(vis, (x0 + 16, y), color,
                           markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)
        cv2.putText(vis, label, (x0 + 36, y + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # 右上角指标
    lines = [
        f"TP:{tp} FP:{fp} FN:{fn}",
        f"Precision:{precision:.3f}",
        f"Recall:{recall:.3f} F1:{f1:.3f}",
    ]
    rx0 = max(16, w - 280)
    ry0 = 16
    roverlay = vis.copy()
    cv2.rectangle(roverlay, (rx0, ry0), (rx0 + 265, ry0 + 85), (0, 0, 0), -1)
    cv2.addWeighted(roverlay, 0.6, vis, 0.4, 0, vis)
    for idx, text in enumerate(lines):
        cv2.putText(vis, text, (rx0 + 10, ry0 + 22 + idx * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    return vis, tp, fp, fn, precision, recall, f1


# ============================================================
#  STNNet 模型加载
# ============================================================
def _load_stnnet_model():
    """加载 STNNet cyc_model，带缓存"""
    global _stnnet_model
    if _stnnet_model is not None:
        return _stnnet_model

    with _stnnet_lock:
        if _stnnet_model is not None:
            return _stnnet_model

        # Patch spatial correlation for PyTorch 2.7 compatibility
        try:
            from spatial_correlation_sampler import SpatialCorrelationSampler
        except ImportError:
            import types
            from app.services.stnnet_video import SpatialCorrelationSamplerPure
            fake_module = types.ModuleType('spatial_correlation_sampler')
            fake_module.SpatialCorrelationSampler = SpatialCorrelationSamplerPure
            sys.modules['spatial_correlation_sampler'] = fake_module

        import torch
        from stnmodel import STNNet

        use_loc = True
        use_trk = True
        model = STNNet(use_loc, use_trk).cuda()
        model.eval()

        checkpoint = torch.load(STNNET_MODEL_PATH, map_location='cuda', weights_only=False)
        my_models = model.state_dict()
        pre_models = list(checkpoint['state_dict'].items())
        count = 0
        for layer_name, value in my_models.items():
            prelayer_name, pre_weights = pre_models[count]
            my_models[layer_name] = pre_weights
            count += 1
        model.load_state_dict(my_models)
        _stnnet_model = model
        return _stnnet_model


# ============================================================
#  单帧 STNNet 推理（密度图 + 定位点）
# ============================================================
def _stnnet_infer_single_frame(model, img_bgr):
    """对单张图做 STNNet 推理，返回密度图和定位点"""
    import torch
    from torchvision import transforms

    with torch.no_grad():
        # 预处理
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])
        img_tensor = transform(img_rgb).unsqueeze(0).cuda()

        # STNNet 需要两个相邻帧输入（做空间相关性），单帧时复制自身
        imgs = [img_tensor, img_tensor]

        den_g1, den_g2, den_g3, loc_g1, loc_g2, loc_g3, loc_g4, \
            reg_g1, reg_g2, reg_g3, reg_g4, trk_g, trk_o, trk_p = model(imgs)

        # 密度图：拼接 FourCrop 结果（单帧没有 crop，用第一个输出即可）
        den = den_g1[0][0, 0].cpu().numpy()  # x2 resolution, batch=0, channel=0
        den = np.maximum(den, 0)

        # 定位点：从 loc_g4 提取
        loc_prob = torch.exp(loc_g4[0][:, 0, :, :]) / (
            torch.exp(loc_g4[0][:, 1, :, :]) + torch.exp(loc_g4[0][:, 0, :, :]))
        reg = reg_g4[0]

        loc_np = loc_prob[0].cpu().numpy()
        reg_np = reg[0].cpu().numpy()

    # 用定位图 + 密度图提取点（numpy 操作不需要梯度）
    import scipy.ndimage as ndimage
    import scipy.ndimage.filters as filters

    # 从密度图提取点
    x_d, y_d, sc_d = _calc_denpt(den / 100.0, 8, 2.0)

    # 从定位图提取点
    locmap = np.maximum(loc_np, 0)
    threshold = 0.5
    binamap = locmap > threshold
    locmap[~binamap] = 0
    data_max = filters.maximum_filter(locmap, 8)
    data_min = filters.minimum_filter(locmap, 8)
    maxima = (locmap == data_max)
    diffmap = ((data_max - data_min) > 0.001)
    maxima[~diffmap] = 0
    labeled, num_objects = ndimage.label(maxima)
    slices = ndimage.find_objects(labeled)
    x_l, y_l, sc_l = [], [], []
    ratio = 2.0
    for dy, dx in slices:
        x_center = (dx.start + dx.stop - 1) / 2 * ratio
        y_center = (dy.start + dy.stop - 1) / 2 * ratio
        xi, yi = int(y_center / ratio), int(x_center / ratio)
        if 0 <= xi < reg_np.shape[1] and 0 <= yi < reg_np.shape[2]:
            offset = reg_np[:, xi, yi]
            x_l.append(x_center + offset[1] * 5 * ratio)
            y_l.append(y_center + offset[0] * 5 * ratio)
            sc_l.append(float(locmap[xi, yi]))

    # 合并密度点 + 定位点
    x_all = np.concatenate([x_d, np.array(x_l)]) if len(x_l) > 0 else x_d
    y_all = np.concatenate([y_d, np.array(y_l)]) if len(y_l) > 0 else y_d
    sc_all = np.concatenate([sc_d, np.array(sc_l)]) if len(sc_l) > 0 else sc_d

    # 坐标裁剪到图像范围内
    valid = (x_all >= 0) & (x_all < w) & (y_all >= 0) & (y_all < h)
    x_all, y_all, sc_all = x_all[valid], y_all[valid], sc_all[valid]

    pred_points = np.column_stack([x_all, y_all, sc_all]) if len(x_all) > 0 else np.empty((0, 3))
    return den, pred_points


# ============================================================
#  任务管理
# ============================================================
def create_stnnet_task(scene_name: str) -> str:
    task_id = f"sn_{uuid.uuid4().hex[:8]}"
    _stnnet_task_cache[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": f"等待启动 STNNet 评测 scene={scene_name}",
        "scene_name": scene_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_frames": 0,
        "steps": [
            {"name": "加载模型", "status": "pending"},
            {"name": "STNNet 推理", "status": "pending"},
            {"name": "生成可视化", "status": "pending"},
        ],
    }
    return task_id


def get_stnnet_task_status(task_id: str):
    return _stnnet_task_cache.get(task_id)


def get_stnnet_task_result(task_id: str):
    return _stnnet_result_cache.get(task_id)


# ============================================================
#  核心：STNNet 场景测试
# ============================================================
def run_stnnet_test(task_id: str, scene_name: str, test_interval: int = 1):
    """对数据集场景运行 STNNet 推理并生成可视化"""
    import torch
    import pandas as pd

    task = _stnnet_task_cache.get(task_id)
    if not task:
        return None

    task["status"] = "running"
    task["progress"] = 0
    task["steps"][0]["status"] = "running"
    task["message"] = "加载 STNNet 模型..."
    t0 = time.time()

    # 加载模型
    model = _load_stnnet_model()
    task["steps"][0]["status"] = "done"
    task["progress"] = 5

    # 数据路径
    frames_dir = os.path.join(DATASET_PATH, "frames", scene_name)
    csv_path = os.path.join(DATASET_PATH, "annotations", f"{scene_name}.csv")
    result_dir = os.path.join(STNNET_RESULT_DIR, task_id)
    os.makedirs(result_dir, exist_ok=True)

    # 读取帧列表
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith('.jpg') or f.endswith('.png')],
                         key=lambda x: int(os.path.splitext(x)[0]))
    task["total_frames"] = len(frame_files)

    # 读取 GT 标注
    df_gt = pd.read_csv(csv_path, header=None)
    df_gt.columns = ['frame', 'person_id', 'x', 'y', 'w', 'h'] + [f'_{i}' for i in range(df_gt.shape[1] - 6)]

    task["steps"][1]["status"] = "running"
    task["message"] = f"STNNet 推理中 (0/{len(frame_files)})..."

    all_results = []
    gt_total = 0
    pred_total = 0
    abs_errors = []
    total_tp, total_fp, total_fn = 0, 0, 0
    total_precision_sum, total_recall_sum = 0.0, 0.0

    for idx, fname in enumerate(frame_files):
        frame_idx = int(os.path.splitext(fname)[0])
        img_path = os.path.join(frames_dir, fname)
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            continue
        h, w = img_bgr.shape[:2]

        # GT
        gt_frame = df_gt[df_gt['frame'] == frame_idx]
        gt_count = len(gt_frame)
        gt_boxes = gt_frame[['x', 'y', 'w', 'h']].values.copy()
        # x, y, w, h -> x1, y1, x2, y2
        gt_boxes[:, 2] = gt_boxes[:, 0] + gt_boxes[:, 2]
        gt_boxes[:, 3] = gt_boxes[:, 1] + gt_boxes[:, 3]

        # 判断是否需要推理（间隔采样 + 最后一帧）
        do_infer = (idx % test_interval == 0) or (idx == len(frame_files) - 1)

        density_maps = []
        pred_points = np.empty((0, 3))
        loc_vis_fname = None
        frame_tp, frame_fp, frame_fn = 0, 0, 0
        frame_precision, frame_recall, frame_f1 = 0.0, 0.0, 0.0
        pred_count = 0

        if do_infer:
            den_np, pred_points = _stnnet_infer_single_frame(model, img_bgr)
            pred_count = len(pred_points)

            # 密度图可视化
            # 原图缩放到密度图尺寸
            den_h, den_w = den_np.shape
            orig_small = cv2.resize(img_bgr, (den_w, den_h))
            orig_fname = f"frame_{frame_idx:06d}_original.jpg"
            cv2.imwrite(os.path.join(result_dir, orig_fname), orig_small,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
            density_maps.append({
                "type": "original", "label": "原图", "count": 0, "filename": orig_fname,
            })

            # GT Global 密度图（从 GT boxes 构建）
            gt_den = np.zeros((den_h, den_w), dtype=np.float32)
            for _, row in gt_frame.iterrows():
                gx = int(row['x'] / w * den_w)
                gy = int(row['y'] / h * den_h)
                if 0 <= gx < den_w and 0 <= gy < den_h:
                    gt_den[gy, gx] += 1.0
            if gt_den.sum() > 0:
                gt_den = cv2.GaussianBlur(gt_den, (15, 15), 4.0)
            gt_fname = _save_density_map(gt_den, "GT", "Density", result_dir, frame_idx)
            density_maps.append({
                "type": "gt_density", "label": "GT Density", "count": float(gt_den.sum()), "filename": gt_fname,
            })

            # Pre 密度图
            pre_fname = _save_density_map(den_np, "Pre", "Density", result_dir, frame_idx)
            density_maps.append({
                "type": "pre_density", "label": "Pre Density", "count": float(den_np.sum()), "filename": pre_fname,
            })

            # 叠加图（原图 + 热力图叠加）
            heatmap = _density_to_heatmap(den_np)
            heatmap_full = cv2.resize(heatmap, (w, h), interpolation=cv2.INTER_CUBIC)
            overlay_img = cv2.addWeighted(img_bgr, 0.55, heatmap_full, 0.45, 0)
            overlay_fname = f"frame_{frame_idx:06d}_overlay.jpg"
            cv2.imwrite(os.path.join(result_dir, overlay_fname), overlay_img,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
            density_maps.append({
                "type": "overlay", "label": "叠加图", "count": float(den_np.sum()), "filename": overlay_fname,
            })

            # 定位点对比可视化
            if gt_count > 0 or len(pred_points) > 0:
                vis_img, frame_tp, frame_fp, frame_fn, frame_precision, frame_recall, frame_f1 = \
                    _draw_localization_compare(img_bgr, gt_boxes, pred_points)
                loc_vis_fname = f"frame_{frame_idx:06d}_localization.jpg"
                cv2.imwrite(os.path.join(result_dir, loc_vis_fname), vis_img,
                            [cv2.IMWRITE_JPEG_QUALITY, 90])
                density_maps.append({
                    "type": "localization", "label": "定位对比",
                    "count": 0, "filename": loc_vis_fname,
                    "tp": frame_tp, "fp": frame_fp, "fn": frame_fn,
                    "precision": round(frame_precision, 4), "recall": round(frame_recall, 4),
                    "f1": round(frame_f1, 4),
                })
        else:
            # 非推理帧：仅 GT 信息
            pred_count = 0

        # 记录结果
        frame_result = {
            "frame": frame_idx,
            "filename": fname,
            "gt_count": gt_count,
            "pred_count": int(pred_count),
            "error": abs(gt_count - int(pred_count)),
            "tp": frame_tp, "fp": frame_fp, "fn": frame_fn,
            "precision": round(frame_precision, 4),
            "recall": round(frame_recall, 4),
            "f1": round(frame_f1, 4),
            "density_maps": density_maps,
            "inferred": do_infer,
        }
        all_results.append(frame_result)
        gt_total += gt_count
        pred_total += int(pred_count)
        abs_errors.append(abs(gt_count - int(pred_count)))
        total_tp += frame_tp
        total_fp += frame_fp
        total_fn += frame_fn
        if frame_precision > 0 or frame_recall > 0:
            total_precision_sum += frame_precision
            total_recall_sum += frame_recall

        # 更新进度
        progress = 5 + int((idx + 1) / len(frame_files) * 85)
        task["progress"] = progress
        task["message"] = f"STNNet 推理中 ({idx + 1}/{len(frame_files)})..."

    task["steps"][1]["status"] = "done"
    task["steps"][2]["status"] = "running"
    task["progress"] = 95
    task["message"] = "汇总结果..."

    # 汇总指标
    total = len(frame_files)
    inferred_frames = sum(1 for r in all_results if r["inferred"])
    overall_mae = round(sum(abs_errors) / max(total, 1), 2)
    overall_mse = round(np.sqrt(sum(e ** 2 for e in abs_errors) / max(total, 1)), 2)
    overall_accuracy = round(100 * (1 - sum(abs_errors) / max(gt_total, 1)), 2) if gt_total > 0 else 0
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0

    elapsed = round(time.time() - t0, 1)

    result = {
        "task_id": task_id,
        "scene_name": scene_name,
        "model_mode": "STNNet (CVPR2021)",
        "total_frames": total,
        "inferred_frames": inferred_frames,
        "total_gt": gt_total,
        "total_pred": pred_total,
        "overall_mae": overall_mae,
        "overall_mse": overall_mse,
        "overall_accuracy": overall_accuracy,
        "overall_precision": round(overall_precision, 4),
        "overall_recall": round(overall_recall, 4),
        "overall_f1": round(overall_f1, 4),
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "elapsed": elapsed,
        "frames": all_results,
    }

    _stnnet_result_cache[task_id] = result
    task["status"] = "done"
    task["progress"] = 100
    task["steps"][2]["status"] = "done"
    task["message"] = f"STNNet 评测完成，{total} 帧，MAE={overall_mae}，F1={overall_f1:.3f}"
    return result


def run_stnnet_test_async(task_id: str, scene_name: str, test_interval: int = 1):
    """异步启动 STNNet 测试"""
    t = threading.Thread(
        target=run_stnnet_test,
        args=(task_id, scene_name, test_interval),
        daemon=True,
    )
    t.start()


# ============================================================
#  STNNet 上传帧测试（复用 run_stnnet_test 逻辑，但用上传的帧）
# ============================================================
def run_stnnet_upload_test(task_id: str, task_dir: str):
    """对用户上传的帧图片运行 STNNet 推理"""
    import torch
    import pandas as pd

    task = _stnnet_task_cache.get(task_id)
    if not task:
        return None

    task["status"] = "running"
    task["progress"] = 0
    task["steps"][0]["status"] = "running"
    task["message"] = "加载 STNNet 模型..."
    t0 = time.time()

    model = _load_stnnet_model()
    task["steps"][0]["status"] = "done"
    task["progress"] = 5

    # 读取上传的帧图片和 CSV
    frames_dir = os.path.join(task_dir, "frames")
    csv_path = os.path.join(task_dir, "labels.csv")
    result_dir = os.path.join(STNNET_RESULT_DIR, task_id)
    os.makedirs(result_dir, exist_ok=True)

    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(('.jpg', '.png'))],
                         key=lambda x: int(os.path.splitext(x)[0]))
    task["total_frames"] = len(frame_files)

    df_gt = pd.read_csv(csv_path, header=None)
    # CSV 格式: frame,person_id,x,y,w,h 或 frame,count
    if df_gt.shape[1] >= 6:
        df_gt.columns = ['frame', 'person_id', 'x', 'y', 'w', 'h'] + [f'_{i}' for i in range(df_gt.shape[1] - 6)]
    else:
        df_gt.columns = ['frame', 'count']

    task["steps"][1]["status"] = "running"
    task["message"] = f"STNNet 推理中 (0/{len(frame_files)})..."

    all_results = []
    gt_total = 0
    pred_total = 0
    abs_errors = []
    total_tp, total_fp, total_fn = 0, 0, 0
    total_precision_sum, total_recall_sum = 0.0, 0.0

    for idx, fname in enumerate(frame_files):
        frame_idx = int(os.path.splitext(fname)[0])
        img_path = os.path.join(frames_dir, fname)
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            continue
        h, w = img_bgr.shape[:2]

        # GT
        if 'count' in df_gt.columns:
            # 简单计数格式：每帧只有总人数
            gt_row = df_gt[df_gt['frame'] == frame_idx]
            gt_count = int(gt_row['count'].values[0]) if len(gt_row) > 0 else 0
            gt_boxes = np.empty((0, 4))
        else:
            gt_frame = df_gt[df_gt['frame'] == frame_idx]
            gt_count = len(gt_frame)
            gt_boxes = gt_frame[['x', 'y', 'w', 'h']].values.copy()
            gt_boxes[:, 2] = gt_boxes[:, 0] + gt_boxes[:, 2]
            gt_boxes[:, 3] = gt_boxes[:, 1] + gt_boxes[:, 3]

        # STNNet 推理
        den_np, pred_points = _stnnet_infer_single_frame(model, img_bgr)
        pred_count = len(pred_points)

        density_maps = []
        loc_vis_fname = None
        frame_tp, frame_fp, frame_fn = 0, 0, 0
        frame_precision, frame_recall, frame_f1 = 0.0, 0.0, 0.0

        # 原图
        den_h, den_w = den_np.shape
        orig_small = cv2.resize(img_bgr, (den_w, den_h))
        orig_fname = f"frame_{frame_idx:06d}_original.jpg"
        cv2.imwrite(os.path.join(result_dir, orig_fname), orig_small,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        density_maps.append({
            "type": "original", "label": "原图", "count": 0, "filename": orig_fname,
        })

        # GT 密度图
        gt_den = np.zeros((den_h, den_w), dtype=np.float32)
        if len(gt_boxes) > 0:
            for _, row in gt_frame.iterrows():
                gx = int(row['x'] / w * den_w)
                gy = int(row['y'] / h * den_h)
                if 0 <= gx < den_w and 0 <= gy < den_h:
                    gt_den[gy, gx] += 1.0
            if gt_den.sum() > 0:
                gt_den = cv2.GaussianBlur(gt_den, (15, 15), 4.0)
        gt_fname = _save_density_map(gt_den, "GT", "Density", result_dir, frame_idx)
        density_maps.append({
            "type": "gt_density", "label": "GT Density", "count": float(gt_den.sum()), "filename": gt_fname,
        })

        # Pre 密度图
        pre_fname = _save_density_map(den_np, "Pre", "Density", result_dir, frame_idx)
        density_maps.append({
            "type": "pre_density", "label": "Pre Density", "count": float(den_np.sum()), "filename": pre_fname,
        })

        # 叠加图
        heatmap = _density_to_heatmap(den_np)
        heatmap_full = cv2.resize(heatmap, (w, h), interpolation=cv2.INTER_CUBIC)
        overlay_img = cv2.addWeighted(img_bgr, 0.55, heatmap_full, 0.45, 0)
        overlay_fname = f"frame_{frame_idx:06d}_overlay.jpg"
        cv2.imwrite(os.path.join(result_dir, overlay_fname), overlay_img,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        density_maps.append({
            "type": "overlay", "label": "叠加图", "count": float(den_np.sum()), "filename": overlay_fname,
        })

        # 定位点对比
        if gt_count > 0 or len(pred_points) > 0:
            vis_img, frame_tp, frame_fp, frame_fn, frame_precision, frame_recall, frame_f1 = \
                _draw_localization_compare(img_bgr, gt_boxes, pred_points)
            loc_vis_fname = f"frame_{frame_idx:06d}_localization.jpg"
            cv2.imwrite(os.path.join(result_dir, loc_vis_fname), vis_img,
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
            density_maps.append({
                "type": "localization", "label": "定位对比",
                "count": 0, "filename": loc_vis_fname,
                "tp": frame_tp, "fp": frame_fp, "fn": frame_fn,
                "precision": round(frame_precision, 4), "recall": round(frame_recall, 4),
                "f1": round(frame_f1, 4),
            })

        frame_result = {
            "frame": frame_idx,
            "filename": fname,
            "gt_count": gt_count,
            "pred_count": int(pred_count),
            "error": abs(gt_count - int(pred_count)),
            "tp": frame_tp, "fp": frame_fp, "fn": frame_fn,
            "precision": round(frame_precision, 4),
            "recall": round(frame_recall, 4),
            "f1": round(frame_f1, 4),
            "density_maps": density_maps,
            "inferred": True,
        }
        all_results.append(frame_result)
        gt_total += gt_count
        pred_total += int(pred_count)
        abs_errors.append(abs(gt_count - int(pred_count)))
        total_tp += frame_tp
        total_fp += frame_fp
        total_fn += frame_fn
        if frame_precision > 0 or frame_recall > 0:
            total_precision_sum += frame_precision
            total_recall_sum += frame_recall

        progress = 5 + int((idx + 1) / len(frame_files) * 85)
        task["progress"] = progress
        task["message"] = f"STNNet 推理中 ({idx + 1}/{len(frame_files)})..."

    task["steps"][1]["status"] = "done"
    task["steps"][2]["status"] = "running"
    task["progress"] = 95
    task["message"] = "汇总结果..."

    total = len(frame_files)
    overall_mae = round(sum(abs_errors) / max(total, 1), 2)
    overall_mse = round(np.sqrt(sum(e ** 2 for e in abs_errors) / max(total, 1)), 2)
    overall_accuracy = round(100 * (1 - sum(abs_errors) / max(gt_total, 1)), 2) if gt_total > 0 else 0
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0

    elapsed = round(time.time() - t0, 1)

    result = {
        "task_id": task_id,
        "scene_name": "用户上传帧",
        "model_mode": "STNNet (CVPR2021)",
        "total_frames": total,
        "inferred_frames": total,
        "total_gt": gt_total,
        "total_pred": pred_total,
        "overall_mae": overall_mae,
        "overall_mse": overall_mse,
        "overall_accuracy": overall_accuracy,
        "overall_precision": round(overall_precision, 4),
        "overall_recall": round(overall_recall, 4),
        "overall_f1": round(overall_f1, 4),
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "elapsed": elapsed,
        "frames": all_results,
    }

    _stnnet_result_cache[task_id] = result
    task["status"] = "done"
    task["progress"] = 100
    task["steps"][2]["status"] = "done"
    task["message"] = f"STNNet 评测完成，{total} 帧，MAE={overall_mae}，F1={overall_f1:.3f}"
    return result


def run_stnnet_upload_test_async(task_id: str, task_dir: str):
    """异步启动 STNNet 上传帧测试"""
    t = threading.Thread(
        target=run_stnnet_upload_test,
        args=(task_id, task_dir),
        daemon=True,
    )
    t.start()
