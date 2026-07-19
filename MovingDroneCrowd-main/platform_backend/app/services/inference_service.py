"""
推理服务 —— 核心引擎
封装 frame_by_frame_demo.py 逻辑，提供可调用接口

支持两种模式:
  MODE_COUNTING  → 逐帧 STEERER 密度估计 + 峰值检测
  MODE_TRACKING  → GD³A + DVTrack 个体跟踪（后续接入）

注意: 重型依赖（torch/cv2/skimage）全部延迟加载，避免路由导入时 500
"""
import os
import sys
import time
import json
import uuid
import threading
from enum import Enum

# ============================================================
#  基础配置（不依赖重型库，可在导入期安全计算）
# ============================================================
GPU_ID = "0"
MAX_LONG = 1920
MAX_SHORT = 1080
MIN_DISTANCE = 10
THRESHOLD_REL = 0.15

# BASE_DIR: 从 platform_backend/app/services/ 往上推 2 层 → platform_backend/
_UPLOAD_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(_UPLOAD_BASE, "uploads")
RESULT_DIR = os.path.join(_UPLOAD_BASE, "results")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# ============================================================
#  延迟初始化标志
# ============================================================
_heavy_loaded = False


def _init_heavy():
    """首次调用时加载所有重型依赖 + 算法路径"""
    global _heavy_loaded, _mdc_cfg, cv2, torch, F, np, Image, standard_transforms, peak_local_max
    global _ALGORITHM_PATH, COUNTER_WEIGHT, GD3A_WEIGHT

    if _heavy_loaded:
        return
    _heavy_loaded = True

    import cv2 as _cv2; globals()["cv2"] = _cv2
    import torch as _torch; globals()["torch"] = _torch
    import torch.nn.functional as _F; globals()["F"] = _F
    import numpy as _np; globals()["np"] = _np
    from PIL import Image as _Image; globals()["Image"] = _Image
    import torchvision.transforms as _tt; globals()["standard_transforms"] = _tt
    from skimage.feature import peak_local_max as _plm; globals()["peak_local_max"] = _plm

    # 算法根目录：从 platform_backend/app/services/inference_service.py 往上推 4 层到项目根
    _ALGORITHM_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _ALGORITHM_PATH not in sys.path:
        sys.path.insert(0, _ALGORITHM_PATH)

    from cusdatasets.setting.MovingDroneCrowd import cfg_data as _mdc
    globals()["_mdc_cfg"] = _mdc

    COUNTER_WEIGHT = os.path.join(_ALGORITHM_PATH,
        "pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth")
    GD3A_WEIGHT = os.path.join(_ALGORITHM_PATH,
        "pretrained/GD3A_MDC++_best_model_VGG16.pth")

    # 构建图像预处理器
    _mean_std = _mdc_cfg.MEAN_STD
    globals()["_img_transform"] = standard_transforms.Compose([
        standard_transforms.ToTensor(),
        standard_transforms.Normalize(*_mean_std)
    ])


class TaskMode(str, Enum):
    COUNTING = "counting"
    TRACKING = "tracking"

MODE_COUNTING = TaskMode.COUNTING
MODE_TRACKING = TaskMode.TRACKING


# ============================================================
#  全局模型单例（只加载一次，线程安全）
# ============================================================
_counter = None
_gd3a_model = None
_yolo_model = None
_model_lock = threading.Lock()
_device = None


def _get_device():
    global _device
    if _device is None:
        _init_heavy()
        os.environ["CUDA_VISIBLE_DEVICES"] = GPU_ID
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[InferenceService] 设备: {_device}")
    return _device


def load_counter():
    """加载 STEERER 全局密度估计器"""
    global _counter
    if _counter is not None:
        return _counter

    _init_heavy()  # 延迟加载重型依赖

    with _model_lock:
        if _counter is not None:
            return _counter

        print("[InferenceService] 加载 STEERER 计数器...")
        from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
        from mmcv import Config

        counter_config = Config.fromfile(os.path.join(
            _ALGORITHM_PATH, "model/density_estimator/STEERER/configs/MDC.py"))

        device = _get_device()
        _counter = STEERER(
            counter_config.network,
            counter_config.dataset.den_factor,
            counter_config.train.route_size
        ).to(device)

        sd = torch.load(COUNTER_WEIGHT, map_location="cpu")
        clean = {}
        for k, v in sd.items():
            while k.startswith("module."):
                k = k[7:]
            clean[k] = v
        _counter.load_state_dict(clean, strict=True)
        _counter.eval()
        print(f"[InferenceService] STEERER 加载完成")
        return _counter


def load_gd3a(model_name="GD3A_VGG16"):
    """加载 GD³A 完整模型，支持不同 backbone"""
    global _gd3a_model, GD3A_WEIGHT, GD3A_WEIGHT_RESNET50
    if _gd3a_model is not None:
        return _gd3a_model

    _init_heavy()  # 延迟加载重型依赖

    with _model_lock:
        if _gd3a_model is not None:
            return _gd3a_model

        print(f"[InferenceService] 加载 GD³A 模型 ({model_name})...")
        from model.VIC import Video_Counter
        from config import cfg as model_cfg

        model_cfg.MODEL = "GD3A"
        model_cfg.global_counter = "STEERER"

        if model_name == "GD3A_ResNet50":
            model_cfg.encoder = "ResNet50_FPN"
            weight_path = os.path.join(_ALGORITHM_PATH,
                "pretrained/GD3A_MDC++_best_model_ResNet50.pth")
        else:
            model_cfg.encoder = "VGG16_FPN"
            weight_path = os.path.join(_ALGORITHM_PATH,
                "pretrained/GD3A_MDC++_best_model_VGG16.pth")

        device = _get_device()
        _gd3a_model = Video_Counter(model_cfg).to(device)
        sd = torch.load(weight_path, map_location="cpu")
        clean = {}
        for k, v in sd.items():
            while k.startswith("module."):
                k = k[7:]
            clean[k] = v
        _gd3a_model.load_state_dict(clean, strict=False)
        _gd3a_model.eval()
        print(f"[InferenceService] GD³A 加载完成")
        return _gd3a_model


def load_yolo():
    """加载 YOLO11 检测模型（VisDrone 行人检测）"""
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model

    _init_heavy()

    with _model_lock:
        if _yolo_model is not None:
            return _yolo_model

        print("[InferenceService] 加载 YOLO11 检测模型...")
        from ultralytics import YOLO

        # 权重路径
        yolo_weight = "/workspace/HybridSORT-master/yolo11_visdrone/runs/yolo11m_visdrone_person-2/weights/best.pt"

        _yolo_model = YOLO(yolo_weight)
        # 设置设备
        device = _get_device()
        _yolo_model.to(device)
        print(f"[InferenceService] YOLO11 加载完成")
        return _yolo_model


# ============================================================
#  YOLO 推理辅助函数
# ============================================================
def yolo_inference_frame(frame_bgr, yolo_model, conf_threshold=0.25):
    """
    使用 YOLO11 对单帧进行行人检测，返回检测框列表

    返回:
        list[tuple]: [(x1, y1, x2, y2, conf), ...] 检测框坐标和置信度
    """
    _init_heavy()
    results = yolo_model(frame_bgr, verbose=False)
    detections = []
    if results and len(results) > 0:
        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                # 只保留 person 类（cls=0）且置信度达标
                if cls_id == 0 and conf >= conf_threshold:
                    detections.append((int(x1), int(y1), int(x2), int(y2), conf))
    return detections


def draw_yolo_result(frame_bgr, detections, frame_idx):
    """在帧上绘制 YOLO 检测框"""
    _init_heavy()
    vis = frame_bgr.copy()
    fh, fw = vis.shape[:2]

    for i, (x1, y1, x2, y2, conf) in enumerate(detections):
        # 绿色检测框（区别于 STEERER 的蓝色）
        cv2.rectangle(vis, (x1, y1), (x2, y2), (51, 255, 51), 2)
        label = f"P{i + 1} {conf:.2f}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(vis, (x1, y1 - lh - 4), (x1 + lw + 4, y1), (51, 255, 51), -1)
        cv2.putText(vis, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    count = len(detections)
    # 左上角帧号 + 人数（绿色系，区别于 STEERER 蓝色）
    cv2.putText(vis, f"Frame {frame_idx} | Count: {count} | YOLO11",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (51, 255, 51), 3)
    return vis


# ============================================================
#  图像预处理器
# ============================================================
# _img_transform 在 _init_heavy() 中延迟构建


def preprocess_frame(frame_bgr, max_long=MAX_LONG, max_short=MAX_SHORT):
    """单帧预处理: BGR → RGB → resize → normalize → pad → tensor"""
    _init_heavy()
    img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    w, h = img_pil.size

    # 等比缩放
    scale = 1.0
    scale_long = max_long / max(w, h) if max(w, h) > 0 else 1
    scale_short = max_short / min(w, h) if min(w, h) > 0 else 1
    if scale_long < 1 or scale_short < 1:
        scale = min(scale_long, scale_short)
        new_w, new_h = int(w * scale), int(h * scale)
        img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)

    # 转 tensor + normalize
    tensor = _img_transform(img_pil).unsqueeze(0)  # [1, C, H, W]
    _, _, th, tw = tensor.shape

    # pad 到 32 的倍数
    pad_h = (32 - th % 32) % 32
    pad_w = (32 - tw % 32) % 32
    if pad_h > 0 or pad_w > 0:
        tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "constant")

    return tensor, (th, tw), (pad_h, pad_w), scale


def extract_peaks(density_map, original_hw, pad_hw, scale):
    """从密度图中提取峰值坐标（还原到原始分辨率）"""
    _init_heavy()
    th, tw = original_hw
    pad_h, pad_w = pad_hw

    # 上采样
    den = F.interpolate(density_map, size=(th + pad_h, tw + pad_w),
                        mode='bilinear', align_corners=False)[0, 0]
    if pad_h > 0 or pad_w > 0:
        den = den[:th, :tw]
    den_np = den.cpu().numpy()

    # 峰值检测
    threshold_abs = den_np.max() * THRESHOLD_REL
    peaks = peak_local_max(den_np, min_distance=MIN_DISTANCE,
                           threshold_abs=threshold_abs)
    peaks_xy = peaks[:, ::-1].astype(np.float32)  # (x, y)
    if scale != 1.0:
        peaks_xy = peaks_xy / scale  # 还原到原始分辨率

    return peaks_xy, den_np


def draw_result(frame_bgr, peaks_xy, frame_idx, count):
    """在帧上绘制检测框 + 人数统计（黄色系）"""
    _init_heavy()
    vis = frame_bgr.copy()
    fh, fw = vis.shape[:2]
    box_size = 16

    for i, (x, y) in enumerate(peaks_xy):
        x, y = int(x), int(y)
        # 黄色检测框
        cv2.rectangle(vis,
                      (max(0, x - box_size // 2), max(0, y - box_size // 2)),
                      (min(fw, x + box_size // 2), min(fh, y + box_size // 2)),
                      (0, 255, 255), 2)  # BGR: 黄色
        cv2.putText(vis, str(i + 1), (x - 8, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)  # 黄色编号

    # 左上角帧号 + 人数（黄色系）
    cv2.putText(vis, f"Frame {frame_idx} | Count: {count}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)  # 黄色文字
    return vis


# ============================================================
#  生成带 ROI 放大对比的图片（类似 vis_boxes.py 的 draw_zoom_in）
# ============================================================
def generate_zoom_image(task_id, video_path, frame_idx, zoom_scale=2.5, roi_ratio=0.25):
    """
    生成原图 + 红虚线 ROI 框 + 右侧放大图的拼接效果
    类似 vis_boxes.py 中 draw_zoom_in 的功能
    """
    _init_heavy()
    counter = load_counter()
    device = _get_device()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {video_path}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx - 1)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError(f"无法读取第 {frame_idx} 帧")

    # 推理获取密度图和峰值点
    tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)
    with torch.no_grad():
        density_map = counter(tensor.to(device))
    peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
    count = len(peaks_xy)

    img_h, img_w = frame.shape[:2]

    # 先绘制检测框和 ID
    vis = draw_result(frame, peaks_xy, frame_idx, count)

    # 如果没有检测到任何人，直接返回原图
    if len(peaks_xy) == 0:
        output_path = os.path.join(RESULT_DIR, f"{task_id}_zoom_{frame_idx:06d}_s{zoom_scale:.1f}_r{roi_ratio:.2f}.jpg")
        cv2.imwrite(output_path, vis, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return output_path

    # 计算 ROI 区域：以所有检测点中心的几何平均为中心
    centers = [(int(x), int(y)) for x, y in peaks_xy]
    mean_cx = int(np.mean([c[0] for c in centers]))
    mean_cy = int(np.mean([c[1] for c in centers]))

    # ROI 大小基于图像尺寸的比例（不再限制最大像素）
    roi_w = int(img_w * roi_ratio)
    roi_h = int(img_h * roi_ratio)

    # 确保 ROI 在图像范围内
    x1 = max(0, mean_cx - roi_w // 2)
    y1 = max(0, mean_cy - roi_h // 2)
    x2 = min(img_w, x1 + roi_w)
    y2 = min(img_h, y1 + roi_h)
    if x2 - x1 < roi_w:
        x1 = max(0, x2 - roi_w)
    if y2 - y1 < roi_h:
        y1 = max(0, y2 - roi_h)

    # 绘制红色虚线 ROI 框
    dash_len = 15
    gap_len = 10
    def draw_dashed_rect(img, pt1, pt2, color, thickness, dash, gap):
        x1_, y1_ = pt1
        x2_, y2_ = pt2
        # 上边
        for x in range(x1_, x2_, dash + gap):
            e = min(x + dash, x2_)
            cv2.line(img, (x, y1_), (e, y1_), color, thickness)
        # 下边
        for x in range(x1_, x2_, dash + gap):
            e = min(x + dash, x2_)
            cv2.line(img, (x, y2_), (e, y2_), color, thickness)
        # 左边
        for y in range(y1_, y2_, dash + gap):
            e = min(y + dash, y2_)
            cv2.line(img, (x1_, y), (x1_, e), color, thickness)
        # 右边
        for y in range(y1_, y2_, dash + gap):
            e = min(y + dash, y2_)
            cv2.line(img, (x2_, y), (x2_, e), color, thickness)

    draw_dashed_rect(vis, (x1, y1), (x2, y2), (0, 0, 255), 2, dash_len, gap_len)

    # 裁剪 ROI 区域并放大
    roi_crop = vis[y1:y2, x1:x2]
    zoomed = cv2.resize(roi_crop, None, fx=zoom_scale, fy=zoom_scale,
                        interpolation=cv2.INTER_LANCZOS4)

    # 在放大图上重新绘制检测框（因为原图上的框在放大后可能看不清或位置不对）
    zh, zw = zoomed.shape[:2]
    scale_x = zw / (x2 - x1)
    scale_y = zh / (y2 - y1)
    box_size = 16
    for i, (px, py) in enumerate(peaks_xy):
        px, py = int(px), int(py)
        # 判断点是否在 ROI 内
        if x1 <= px <= x2 and y1 <= py <= y2:
            # 映射到放大图坐标
            zx = int((px - x1) * scale_x)
            zy = int((py - y1) * scale_y)
            zbx1 = max(0, zx - int(box_size * scale_x // 2))
            zby1 = max(0, zy - int(box_size * scale_y // 2))
            zbx2 = min(zw, zx + int(box_size * scale_x // 2))
            zby2 = min(zh, zy + int(box_size * scale_y // 2))
            cv2.rectangle(zoomed, (zbx1, zby1), (zbx2, zby2), (0, 255, 255), 2)
            cv2.putText(zoomed, str(i + 1), (zx - 10, zby1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # 给放大图加白色边框
    pad = 6
    zoomed_padded = cv2.copyMakeBorder(zoomed, pad, pad, pad, pad,
                                        cv2.BORDER_CONSTANT, value=(220, 220, 220))

    # 调整放大图高度与主图一致（居中对齐）
    zh_p, zw_p = zoomed_padded.shape[:2]
    target_h = img_h
    if zh_p < target_h:
        top_pad = (target_h - zh_p) // 2
        bottom_pad = target_h - zh_p - top_pad
        zoomed_padded = cv2.copyMakeBorder(zoomed_padded, top_pad, bottom_pad, 0, 0,
                                            cv2.BORDER_CONSTANT, value=(40, 40, 40))
    elif zh_p > target_h:
        crop_top = (zh_p - target_h) // 2
        zoomed_padded = zoomed_padded[crop_top:crop_top + target_h, :]

    # 拼接主图 + 放大图
    combined = np.hstack([vis, zoomed_padded])

    # 保存
    output_path = os.path.join(RESULT_DIR, f"{task_id}_zoom_{frame_idx:06d}_s{zoom_scale:.1f}_r{roi_ratio:.2f}.jpg")
    cv2.imwrite(output_path, combined, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return output_path


# ============================================================
#  生成自定义 ROI 放大对比图（用户在前端画矩形）
# ============================================================
def generate_zoom_custom(task_id, video_path, frame_idx, x1, y1, x2, y2, zoom_scale=2.5):
    """
    根据用户自定义的 ROI 坐标生成放大对比图
    x1,y1,x2,y2: 原始图像坐标系中的 ROI 矩形（已确保在图像范围内）
    """
    _init_heavy()
    counter = load_counter()
    device = _get_device()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {video_path}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx - 1)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError(f"无法读取第 {frame_idx} 帧")

    # 推理获取密度图和峰值点
    tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)
    with torch.no_grad():
        density_map = counter(tensor.to(device))
    peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
    count = len(peaks_xy)

    img_h, img_w = frame.shape[:2]

    # 先绘制检测框和 ID
    vis = draw_result(frame, peaks_xy, frame_idx, count)

    # 确保坐标在图像范围内
    x1 = max(0, min(x1, img_w))
    y1 = max(0, min(y1, img_h))
    x2 = max(x1 + 1, min(x2, img_w))
    y2 = max(y1 + 1, min(y2, img_h))

    # 绘制红色虚线 ROI 框
    dash_len = 15
    gap_len = 10
    def draw_dashed_rect(img, pt1, pt2, color, thickness, dash, gap):
        x1_, y1_ = pt1
        x2_, y2_ = pt2
        for x in range(x1_, x2_, dash + gap):
            e = min(x + dash, x2_)
            cv2.line(img, (x, y1_), (e, y1_), color, thickness)
        for x in range(x1_, x2_, dash + gap):
            e = min(x + dash, x2_)
            cv2.line(img, (x, y2_), (e, y2_), color, thickness)
        for y in range(y1_, y2_, dash + gap):
            e = min(y + dash, y2_)
            cv2.line(img, (x1_, y), (x1_, e), color, thickness)
        for y in range(y1_, y2_, dash + gap):
            e = min(y + dash, y2_)
            cv2.line(img, (x2_, y), (x2_, e), color, thickness)

    draw_dashed_rect(vis, (x1, y1), (x2, y2), (0, 0, 255), 2, dash_len, gap_len)

    # 裁剪 ROI 区域并放大
    roi_crop = vis[y1:y2, x1:x2]
    if roi_crop.size == 0:
        # ROI 无效，返回原图
        output_path = os.path.join(RESULT_DIR, f"{task_id}_zoom_custom_{frame_idx:06d}_{x1}_{y1}_{x2}_{y2}_s{zoom_scale:.1f}.jpg")
        cv2.imwrite(output_path, vis, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return output_path

    zoomed = cv2.resize(roi_crop, None, fx=zoom_scale, fy=zoom_scale,
                        interpolation=cv2.INTER_LANCZOS4)

    # 在放大图上重新绘制检测框
    zh, zw = zoomed.shape[:2]
    scale_x = zw / (x2 - x1)
    scale_y = zh / (y2 - y1)
    box_size = 16
    for i, (px, py) in enumerate(peaks_xy):
        px, py = int(px), int(py)
        if x1 <= px <= x2 and y1 <= py <= y2:
            zx = int((px - x1) * scale_x)
            zy = int((py - y1) * scale_y)
            zbx1 = max(0, zx - int(box_size * scale_x // 2))
            zby1 = max(0, zy - int(box_size * scale_y // 2))
            zbx2 = min(zw, zx + int(box_size * scale_x // 2))
            zby2 = min(zh, zy + int(box_size * scale_y // 2))
            cv2.rectangle(zoomed, (zbx1, zby1), (zbx2, zby2), (0, 255, 255), 2)
            cv2.putText(zoomed, str(i + 1), (zx - 10, zby1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # 给放大图加白色边框
    pad = 6
    zoomed_padded = cv2.copyMakeBorder(zoomed, pad, pad, pad, pad,
                                        cv2.BORDER_CONSTANT, value=(220, 220, 220))

    # 调整放大图高度与主图一致
    zh_p, zw_p = zoomed_padded.shape[:2]
    target_h = img_h
    if zh_p < target_h:
        top_pad = (target_h - zh_p) // 2
        bottom_pad = target_h - zh_p - top_pad
        zoomed_padded = cv2.copyMakeBorder(zoomed_padded, top_pad, bottom_pad, 0, 0,
                                            cv2.BORDER_CONSTANT, value=(40, 40, 40))
    elif zh_p > target_h:
        crop_top = (zh_p - target_h) // 2
        zoomed_padded = zoomed_padded[crop_top:crop_top + target_h, :]

    # 拼接主图 + 放大图
    combined = np.hstack([vis, zoomed_padded])

    # 保存
    output_path = os.path.join(RESULT_DIR, f"{task_id}_zoom_custom_{frame_idx:06d}_{x1}_{y1}_{x2}_{y2}_s{zoom_scale:.1f}.jpg")
    cv2.imwrite(output_path, combined, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return output_path


# ============================================================
#  任务管理（内存缓存 + SQLite 持久化）
# ============================================================
_task_cache: dict = {}       # 内存缓存，加速频繁读取
_result_cache: dict = {}     # 结果内存缓存
_progress_callbacks: dict = {}  # task_id → callback(progress_dict)


def create_task(mode=TaskMode.COUNTING, filename="", size_mb=0):
    """创建新任务，返回 task_id"""
    from app.db import db_create_task
    task_id = str(uuid.uuid4())[:8]
    t = {
        "status": "pending",
        "progress": 0,
        "message": "等待处理",
        "mode": mode,
        "model": "",
        "filename": filename,
        "size_mb": size_mb,
        "created_at": "",
    }
    _task_cache[task_id] = t
    db_create_task(task_id, status="pending", message="等待处理",
                   mode=mode, filename=filename, size_mb=size_mb)
    return task_id


def get_task_status(task_id):
    """查询任务进度（优先缓存）"""
    if task_id in _task_cache:
        return _task_cache[task_id]
    # 缓存未命中，从 DB 加载
    from app.db import db_get_task
    t = db_get_task(task_id)
    if t:
        _task_cache[task_id] = t
    return t


def get_task_result(task_id):
    """查询任务结果（优先缓存）"""
    if task_id in _result_cache:
        return _result_cache[task_id]
    from app.db import db_get_result
    r = db_get_result(task_id)
    if r:
        _result_cache[task_id] = r
    return r


def list_tasks():
    """列出所有历史任务（轻量级，不加载完整 result）"""
    from app.db import db_list_tasks
    tasks = db_list_tasks()
    for t in tasks:
        tid = t["task_id"]
        if tid not in _task_cache:
            _task_cache[tid] = t
        # 附带 total_frames 供前端显示（从 JOIN 查询获取）
        tf = t.pop("total_frames", None)
        if tf is not None:
            t["result"] = {"total_frames": tf}
    return tasks


def register_progress_callback(task_id, callback):
    """注册 WebSocket 进度回调"""
    _progress_callbacks[task_id] = callback


def unregister_progress_callback(task_id):
    """取消注册"""
    _progress_callbacks.pop(task_id, None)


def _emit_progress(task_id):
    """向 WebSocket 推送进度"""
    cb = _progress_callbacks.get(task_id)
    if cb and task_id in _task_cache:
        cb(_task_cache[task_id])


# ============================================================
#  推理任务执行
# ============================================================
def run_counting(task_id, video_path, model_name="STEERER"):
    """
    执行人群计数任务（同步，调用方需开线程）
    
    参数:
        task_id: 任务ID
        video_path: 输入视频绝对路径
        model_name: 模型选择 ("STEERER", "GD3A_VGG16", "GD3A_ResNet50")
    
    返回:
        dict: {output_video, total_frames, total_time, frames[...]}
    """
    t = _task_cache[task_id]
    t["status"] = "running"
    t["progress"] = 0
    t["message"] = f"加载模型 {model_name}..."
    t["model"] = model_name
    from app.db import db_update_task
    db_update_task(task_id, status="running", progress=0, message=t["message"], model=model_name)
    _emit_progress(task_id)

    # 加载模型
    counter = load_counter()
    if model_name.startswith("GD3A"):
        gd3a_model = load_gd3a(model_name)
    device = _get_device()

    # 打开视频
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        t["status"] = "failed"
        t["message"] = f"无法打开视频: {video_path}"
        db_update_task(task_id, status="failed", message=t["message"])
        _emit_progress(task_id)
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 输出路径
    output_video = os.path.join(RESULT_DIR, f"{task_id}_result.mp4")
    output_json = os.path.join(RESULT_DIR, f"{task_id}_result.json")

    t["message"] = f"开始推理, 共 {total_frames} 帧, {width}x{height}"
    _emit_progress(task_id)

    out_writer = None
    frame_idx = 0
    all_frame_counts = []
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # 预处理
        tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)

        # 推理
        with torch.no_grad():
            density_map = counter(tensor.to(device))

        # 提取峰值
        peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
        count = len(peaks_xy)

        # 绘制结果帧
        vis = draw_result(frame, peaks_xy, frame_idx, count)

        # 写入输出视频（先用 mp4v 编码，完成后再用 ffmpeg 转 H.264）
        if out_writer is None:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            vh, vw = vis.shape[:2]
            out_writer = cv2.VideoWriter(output_video, fourcc, fps, (vw, vh))

        out_writer.write(vis)

        # 记录每帧统计
        all_frame_counts.append({
            "frame": frame_idx,
            "count": count,
            "peaks": peaks_xy.tolist() if len(peaks_xy) > 0 else []
        })

        # 更新进度（每10帧写一次 DB + 推送一次）
        progress = int(frame_idx / total_frames * 100)
        t["progress"] = progress
        t["message"] = f"处理中 {frame_idx}/{total_frames}, 当前 {count} 人"
        if frame_idx % 10 == 0:  # 每10帧推送 + 写DB
            db_update_task(task_id, progress=progress, message=t["message"])
            _emit_progress(task_id)

    # 收尾
    cap.release()
    if out_writer:
        out_writer.release()

    # 转码为 H.264，确保浏览器兼容
    h264_video = output_video.replace("_result.mp4", "_result_h264.mp4")
    try:
        import subprocess
        subprocess.run([
            "ffmpeg", "-y", "-i", output_video,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an", h264_video
        ], check=True, capture_output=True)
        # 替换原文件
        os.replace(h264_video, output_video)
    except Exception as e:
        print(f"[InferenceService] ffmpeg 转码失败或不可用，保留原始编码: {e}")

    elapsed = time.time() - start_time
    t["status"] = "done"
    t["progress"] = 100
    t["message"] = f"完成! 共 {frame_idx} 帧, 耗时 {elapsed:.1f}s"
    db_update_task(task_id, status="done", progress=100, message=t["message"])
    _emit_progress(task_id)

    # 保存结果 JSON
    result = {
        "task_id": task_id,
        "video_path": video_path,
        "output_video": output_video,
        "fps": fps,
        "total_frames": frame_idx,
        "width": width,
        "height": height,
        "total_time": round(elapsed, 1),
        "frames": all_frame_counts,
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    from app.db import db_save_result
    db_save_result(task_id, result)
    _result_cache[task_id] = result
    return result



def run_counting_async(task_id, video_path, model_name="STEERER"):
    """异步启动计数任务（在后台线程中运行）"""
    if model_name == "YOLO11":
        t = threading.Thread(
            target=run_yolo_counting,
            args=(task_id, video_path, model_name),
            daemon=True
        )
    else:
        t = threading.Thread(
            target=run_counting,
            args=(task_id, video_path, model_name),
            daemon=True
        )
    t.start()
    return task_id


# ============================================================
#  YOLO11 检测推理任务
# ============================================================
def run_yolo_counting(task_id, video_path, model_name="YOLO11"):
    """
    使用 YOLO11 执行行人检测计数任务

    参数:
        task_id: 任务ID
        video_path: 输入视频绝对路径
        model_name: 模型名称（用于日志）

    返回:
        dict: {output_video, total_frames, total_time, frames[...]}
    """
    t = _task_cache[task_id]
    t["status"] = "running"
    t["progress"] = 0
    t["message"] = f"加载模型 {model_name}..."
    t["model"] = model_name
    from app.db import db_update_task
    db_update_task(task_id, status="running", progress=0, message=t["message"], model=model_name)
    _emit_progress(task_id)

    # 加载 YOLO 模型
    yolo_model = load_yolo()
    device = _get_device()

    # 打开视频
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        t["status"] = "failed"
        t["message"] = f"无法打开视频: {video_path}"
        db_update_task(task_id, status="failed", message=t["message"])
        _emit_progress(task_id)
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 输出路径
    output_video = os.path.join(RESULT_DIR, f"{task_id}_result.mp4")
    output_json = os.path.join(RESULT_DIR, f"{task_id}_result.json")

    t["message"] = f"开始 YOLO 推理, 共 {total_frames} 帧, {width}x{height}"
    _emit_progress(task_id)

    out_writer = None
    frame_idx = 0
    all_frame_counts = []
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # YOLO 推理（直接在原始帧上）
        detections = yolo_inference_frame(frame, yolo_model)

        # 提取中心点作为 peaks 格式
        peaks = []
        for (x1, y1, x2, y2, conf) in detections:
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            peaks.append([float(cx), float(cy)])
        peaks_xy = np.array(peaks) if peaks else np.empty((0, 2))
        count = len(detections)

        # 绘制结果帧（YOLO 绿色框）
        vis = draw_yolo_result(frame, detections, frame_idx)

        # 写入输出视频
        if out_writer is None:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            vh, vw = vis.shape[:2]
            out_writer = cv2.VideoWriter(output_video, fourcc, fps, (vw, vh))

        out_writer.write(vis)

        # 记录每帧统计
        all_frame_counts.append({
            "frame": frame_idx,
            "count": count,
            "peaks": peaks_xy.tolist() if len(peaks_xy) > 0 else []
        })

        # 更新进度
        progress = int(frame_idx / total_frames * 100)
        t["progress"] = progress
        t["message"] = f"YOLO 处理中 {frame_idx}/{total_frames}, 检测到 {count} 人"
        if frame_idx % 10 == 0:
            db_update_task(task_id, progress=progress, message=t["message"])
            _emit_progress(task_id)

    # 收尾
    cap.release()
    if out_writer:
        out_writer.release()

    # 转码为 H.264
    h264_video = output_video.replace("_result.mp4", "_result_h264.mp4")
    try:
        import subprocess
        subprocess.run([
            "ffmpeg", "-y", "-i", output_video,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an", h264_video
        ], check=True, capture_output=True)
        os.replace(h264_video, output_video)
    except Exception as e:
        print(f"[InferenceService] ffmpeg 转码失败或不可用，保留原始编码: {e}")

    elapsed = time.time() - start_time
    t["status"] = "done"
    t["progress"] = 100
    t["message"] = f"YOLO 完成! 共 {frame_idx} 帧, 耗时 {elapsed:.1f}s"
    db_update_task(task_id, status="done", progress=100, message=t["message"])
    _emit_progress(task_id)

    # 保存结果 JSON
    result = {
        "task_id": task_id,
        "video_path": video_path,
        "output_video": output_video,
        "fps": fps,
        "total_frames": frame_idx,
        "width": width,
        "height": height,
        "total_time": round(elapsed, 1),
        "frames": all_frame_counts,
        "model": model_name,
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    from app.db import db_save_result
    db_save_result(task_id, result)
    _result_cache[task_id] = result
    return result


# ============================================================
#  单张图片推理
# ============================================================
def run_single_image(image_path):
    """
    对单张图片执行人群计数，返回结果图片路径 + 统计信息

    返回:
        dict: {result_image, count, peaks_count, elapsed}
    """
    start_time = time.time()

    # 加载模型
    counter = load_counter()
    device = _get_device()

    # 读取图片
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    h, w = img.shape[:2]

    # 预处理
    tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(img)

    # 推理
    with torch.no_grad():
        density_map = counter(tensor.to(device))

    # 提取峰值
    peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
    count = len(peaks_xy)

    # 绘制结果
    vis = draw_result(img, peaks_xy, 1, count)

    # 保存结果图片
    img_id = str(uuid.uuid4())[:8]
    result_img_path = os.path.join(RESULT_DIR, f"{img_id}_result.jpg")
    cv2.imwrite(result_img_path, vis, [cv2.IMWRITE_JPEG_QUALITY, 95])

    elapsed = round(time.time() - start_time, 2)

    return {
        "image_id": img_id,
        "result_image": result_img_path,
        "original_size": [w, h],
        "count": count,
        "peaks_count": count,
        "elapsed": elapsed,
    }


# ============================================================
#  逐帧分析：生成单帧标注图片
# ============================================================
def generate_frame_image(task_id, video_path, frame_idx):
    """从原始视频中提取指定帧并叠加检测标注"""
    _init_heavy()
    counter = load_counter()
    device = _get_device()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {video_path}")

    # 跳转到指定帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx - 1)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError(f"无法读取第 {frame_idx} 帧")

    # 推理
    tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)
    with torch.no_grad():
        density_map = counter(tensor.to(device))
    peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
    count = len(peaks_xy)

    # 绘制
    vis = draw_result(frame, peaks_xy, frame_idx, count)

    # 保存
    output_path = os.path.join(RESULT_DIR, f"{task_id}_frame_{frame_idx:06d}.jpg")
    cv2.imwrite(output_path, vis, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return output_path


# ============================================================
#  生成密度热力图
# ============================================================
def generate_density_image(task_id, video_path, frame_idx, cmap="jet", peaks=True, contour=False, alpha=0.6):
    """生成指定帧的密度热力图，叠加到原图上"""
    _init_heavy()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    counter = load_counter()
    device = _get_device()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {video_path}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx - 1)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError(f"无法读取第 {frame_idx} 帧")

    # 推理
    tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)
    with torch.no_grad():
        density_map = counter(tensor.to(device))
    peaks_xy, den_np = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)

    fh, fw = frame.shape[:2]

    # 如果密度图尺寸与原始帧不一致，resize
    if den_np.shape != (fh, fw):
        den_np = cv2.resize(den_np, (fw, fh), interpolation=cv2.INTER_LINEAR)

    # 使用 matplotlib 生成热力图叠加
    fig, ax = plt.subplots(1, 1, figsize=(fw / 100, fh / 100), dpi=100)
    ax.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    # 归一化密度图
    if den_np.max() > 0:
        norm_den = den_np / den_np.max()
    else:
        norm_den = den_np

    # 绘制热力图
    ax.imshow(norm_den, cmap=cmap, alpha=alpha, extent=[0, fw, fh, 0])

    # 叠加检测点
    if peaks and len(peaks_xy) > 0:
        ax.scatter(peaks_xy[:, 0], peaks_xy[:, 1], c='white', s=8, edgecolors='#003366', linewidths=0.5, alpha=0.9)

    # 叠加等高线
    if contour and den_np.max() > 0:
        X, Y = np.meshgrid(np.linspace(0, fw, den_np.shape[1]), np.linspace(0, fh, den_np.shape[0]))
        ax.contour(X, Y, den_np, levels=5, colors='#00ffff', alpha=0.9, linewidths=1.2)

    ax.set_title(f'Frame {frame_idx} | Count: {len(peaks_xy)} | Density Map ({cmap})',
                 fontsize=10, color='#4da6ff', pad=4)
    ax.axis('off')
    plt.tight_layout(pad=0)

    # 保存
    output_path = os.path.join(RESULT_DIR, f"{task_id}_density_{frame_idx:06d}_{cmap}_{int(peaks)}_{int(contour)}_{alpha:.1f}.jpg")
    fig.savefig(output_path, dpi=100, bbox_inches='tight', pad_inches=0.05, facecolor='#050d1a')
    plt.close(fig)

    return output_path


# ============================================================
#  生成热力图视频
# ============================================================
_HEATMAP_VIDEO_TASKS: dict = {}  # heatmap_video_task_id → 状态

def generate_heatmap_video(task_id, video_path, total_frames, fps,
                           cmap="jet", peaks=True, contour=False, alpha=0.6,
                           output_fps=None, sample_every=1):
    """
    生成连续播放的热力图视频

    参数:
        task_id: 原始推理任务 ID
        video_path: 原始视频路径
        total_frames: 总帧数
        fps: 原始视频帧率
        cmap: 配色方案
        peaks: 是否叠加检测点
        contour: 是否叠加等高线
        alpha: 热力图透明度
        output_fps: 输出视频帧率（默认同原始 fps）
        sample_every: 每隔 N 帧采样一次（加速生成）

    返回:
        heatmap_task_id
    """
    import subprocess

    heatmap_task_id = f"{task_id}_heatmap_{cmap}"
    if heatmap_task_id in _HEATMAP_VIDEO_TASKS:
        st = _HEATMAP_VIDEO_TASKS[heatmap_task_id]
        if st["status"] == "running" or st["status"] == "done":
            return heatmap_task_id

    output_fps = output_fps or fps
    output_video = os.path.join(RESULT_DIR, f"{heatmap_task_id}.mp4")
    temp_dir = os.path.join(RESULT_DIR, f"{heatmap_task_id}_frames")
    os.makedirs(temp_dir, exist_ok=True)

    _HEATMAP_VIDEO_TASKS[heatmap_task_id] = {
        "status": "running", "progress": 0, "message": "开始生成热力图视频...",
        "output_video": output_video,
    }

    def _run():
        try:
            st = _HEATMAP_VIDEO_TASKS[heatmap_task_id]

            # 批量生成热力图帧
            frame_indices = list(range(1, total_frames + 1, sample_every))
            actual_frames = len(frame_indices)

            for i, fi in enumerate(frame_indices):
                try:
                    out = generate_density_image(task_id, video_path, fi,
                                                 cmap=cmap, peaks=peaks,
                                                 contour=contour, alpha=alpha)
                    # 复制到临时目录统一命名
                    dst = os.path.join(temp_dir, f"frame_{i:06d}.jpg")
                    import shutil
                    shutil.copy(out, dst)
                except Exception as e:
                    print(f"[HeatmapVideo] 帧 {fi} 生成失败: {e}")
                    # 复制上一帧
                    prev = os.path.join(temp_dir, f"frame_{i-1:06d}.jpg")
                    if os.path.exists(prev) and i > 0:
                        import shutil
                        shutil.copy(prev, os.path.join(temp_dir, f"frame_{i:06d}.jpg"))

                progress = int((i + 1) / actual_frames * 100)
                st["progress"] = progress
                st["message"] = f"生成热力图帧 {i+1}/{actual_frames}"

            # 用 ffmpeg 合成视频
            st["message"] = "正在合成热力图视频..."
            actual_fps = fps / sample_every if output_fps is None else output_fps
            
            # 确保输出尺寸为偶数（H.264 要求）
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(actual_fps),
                "-i", os.path.join(temp_dir, "frame_%06d.jpg"),
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-an", output_video,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg 合成失败: {result.stderr}")

            # 清理临时帧
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

            st["status"] = "done"
            st["progress"] = 100
            st["message"] = f"热力图视频生成完成 ({actual_frames} 帧)"
        except Exception as e:
            st = _HEATMAP_VIDEO_TASKS[heatmap_task_id]
            st["status"] = "failed"
            st["message"] = f"生成失败: {str(e)}"
            import traceback
            traceback.print_exc()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return heatmap_task_id


def get_heatmap_video_status(heatmap_task_id):
    """查询热力图视频生成进度"""
    return _HEATMAP_VIDEO_TASKS.get(heatmap_task_id)
