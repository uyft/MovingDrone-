"""
STNNet 视频推理服务 —— 严格遵循官方 mytest.py + image_test.py 逻辑
v2 优化版：直接 tensor 预处理 + 优化相关性采样器

核心流程（与官方完全一致）：
1. 每帧 FiveCrop 4 个子图（crop_factor=0.5）
2. 4 个子图分别送入 STNNet 推理
3. 密度图水平+垂直拼接，除以 100
4. 追踪头坐标偏移修正（4 个 crop 偏移量不同）
5. calc_trkpt 合并密度图 NMS + 追踪头 top-k 点
6. 帧间贪心最近邻匹配，生成追踪 ID 和轨迹

注意：保留 4 次独立 model() 调用。
因为 STNNet 追踪头中有大量串行 Python NMS/PointConv 循环，
batch 合并不会提升 GPU 利用率，反而让串行循环加倍运行。
瓶颈在空间相关性采样器 (已优化) 和 GCN PointConv。
"""
import os
import sys
import json
import time
import uuid
import threading
import cv2
import numpy as np
from typing import Dict, List, Optional
from app.db import db_create_task, db_update_task, db_save_result

# 添加 STNNet 路径
STNNET_PATH = '/workspace/STNNet'
if STNNET_PATH not in sys.path:
    sys.path.insert(0, STNNET_PATH)

# ============================================================
#  Pure-PyTorch Spatial Correlation Sampler (优化版)
#  跳过逐 channel chunk 循环，直接 unfold 全通道
# ============================================================
import torch
import torch.nn.functional as F


class SpatialCorrelationSamplerPure(torch.nn.Module):
    """Optimized pure-PyTorch SpatialCorrelationSampler.

    与 C 扩展 SpatialCorrelationSampler(kernel_size=1, patch_size=11,
        stride=1, padding=0, dilation=1) 等价。

    优化: 用一个 unfold 操作取代逐 channel 循环，减少 kernel launch 开销。
    """
    def __init__(self, kernel_size=1, patch_size=11, stride=1, padding=0, dilation=1,
                 chunk_size=256):
        super().__init__()
        self.kernel_size = kernel_size
        self.patch_size = patch_size
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.chunk_size = chunk_size

    def forward(self, input1, input2):
        B, C, H, W = input1.shape
        patch = self.patch_size
        pad = patch // 2
        P2 = patch * patch

        input2_padded = F.pad(input2, (pad, pad, pad, pad))

        # unfold: (B, C, H, W) -> (B, C*patch^2, H*W) -> (B, C, P2, H, W)
        patches = F.unfold(input2_padded, kernel_size=(patch, patch),
                           stride=1, padding=0)
        patches = patches.view(B, C, P2, H * W).view(B, C, P2, H, W)

        # (B, C, 1, H, W) * (B, C, P2, H, W) -> sum over C -> (B, P2, H, W)
        output = (input1.unsqueeze(2) * patches).sum(dim=1)

        return output


def _patch_spatial_correlation():
    """Monkey-patch STNNet's stnmodel to use pure-PyTorch SpatialCorrelationSampler."""
    try:
        from spatial_correlation_sampler import SpatialCorrelationSampler
        return
    except ImportError:
        pass
    import types
    fake_module = types.ModuleType('spatial_correlation_sampler')
    fake_module.SpatialCorrelationSampler = SpatialCorrelationSamplerPure
    sys.modules['spatial_correlation_sampler'] = fake_module
    print("[STNNetVideo] Using pure-PyTorch SpatialCorrelationSampler (C extension not available)")


# ============================================================
#  快速 tensor 预处理（跳过 PIL 往返）
# ============================================================
_IMAGENET_MEAN = None
_IMAGENET_STD = None


def _get_norm_params():
    global _IMAGENET_MEAN, _IMAGENET_STD
    if _IMAGENET_MEAN is None:
        _IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406], device='cuda').view(1, 3, 1, 1)
        _IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225], device='cuda').view(1, 3, 1, 1)
    return _IMAGENET_MEAN, _IMAGENET_STD


def _preprocess_single(rgb):
    """numpy RGB [H,W,3] → normalized tensor [1, 3, H, W] on GPU"""
    mean, std = _get_norm_params()
    t = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0).unsqueeze(0).cuda()
    t = (t - mean) / std
    return t


# ============================================================
#  配置
# ============================================================
RESULT_DIR = '/workspace/MovingDroneCrowd-main/platform_backend/results'
STNNET_VIDEO_RESULT_DIR = os.path.join(RESULT_DIR, "stnnet_videos")
os.makedirs(STNNET_VIDEO_RESULT_DIR, exist_ok=True)

STNNET_MODEL_PATH = os.path.join(STNNET_PATH, "models", "cyc_model_best.pth.tar")

# 全局模型缓存
_stnnet_video_model = None
_stnnet_lock = threading.Lock()

# 任务缓存
_stnnet_video_tasks: Dict[str, dict] = {}
_stnnet_video_results: Dict[str, dict] = {}

# ============================================================
#  可视化参数 —— 采用 DroneCrowdVisualizer 风格
# ============================================================
TRAIL_LENGTH = 20
BOX_SIZE = 14
TRACKING_DIST_THRESH = 50

# DroneCrowdVisualizer 风格: 每个 track_id 独立颜色
# hue = (track_id * 47) % 360, s=100%, v=85%  (提亮)
def _track_color(track_id):
    """为每个 track ID 生成唯一颜色 (BGR, 亮色系)"""
    hue = (track_id * 47) % 360
    # HSV(hue, 1.0, 0.85) → BGR, S和V提亮
    hsv = np.uint8([[[hue // 2, 255, 217]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0]
    return tuple(int(c) for c in bgr)

def _blend_overlay(bg, overlay, alpha):
    """Alpha 混合: overlay 混合到 bg 上"""
    return (alpha * overlay.astype(np.float32) + (1 - alpha) * bg.astype(np.float32)).astype(np.uint8)

# ============================================================
#  模型加载
# ============================================================
def _load_stnnet_model():
    global _stnnet_video_model
    if _stnnet_video_model is not None:
        return _stnnet_video_model

    with _stnnet_lock:
        if _stnnet_video_model is not None:
            return _stnnet_video_model

        _patch_spatial_correlation()
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
        _stnnet_video_model = model
        print("[STNNetVideo] Model loaded: cyc_model_best.pth.tar")
        return _stnnet_video_model


# ============================================================
#  官方 calc_trkpt —— 从 mytest.py 第 349 行直接移植
# ============================================================
def _calc_trkpt(outpts, outscs, thre, ourmap, neighbor_thre, ratio):
    import scipy.ndimage as ndimage
    import scipy.ndimage.filters as filters

    binamap = ourmap > 0
    ourmap[binamap == 0] = 0
    data_max = filters.maximum_filter(ourmap, neighbor_thre)
    data_min = filters.minimum_filter(ourmap, neighbor_thre)
    maxima = ourmap == data_max
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
        sc.append(ourmap[int(y_center / ratio), int(x_center / ratio)])

    for k in range(outpts.shape[0]):
        if outscs[k] >= thre:
            x_center = outpts[k, 1] * ratio
            y_center = outpts[k, 0] * ratio
            x.append(x_center)
            y.append(y_center)
            sc.append(outscs[k])

    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    sc = np.asarray(sc, dtype=np.float32)
    return x, y, sc


# ============================================================
#  帧间匹配（贪心最近邻）
# ============================================================
def _match_points(prev_points, curr_x, curr_y, dist_thresh=TRACKING_DIST_THRESH):
    n_prev = len(prev_points) if prev_points else 0
    n_curr = len(curr_x)

    matched_ids = [-1] * n_curr
    next_id = 0
    if prev_points and n_prev > 0:
        next_id = max(p['id'] for p in prev_points) + 1
        prev_pts = np.array([[p['x'], p['y']] for p in prev_points])
        used_prev = set()

        order = np.argsort(-np.array([s for _, _, s in zip(curr_x, curr_y,
                np.ones(n_curr) if n_curr > 0 else [])])) if n_curr > 0 else []

        for ci in order[:n_curr]:
            cx, cy = curr_x[ci], curr_y[ci]
            best_prev = -1
            best_dist = dist_thresh
            for pi in range(n_prev):
                if pi in used_prev:
                    continue
                d = np.sqrt((cx - prev_pts[pi][0]) ** 2 + (cy - prev_pts[pi][1]) ** 2)
                if d < best_dist:
                    best_dist = d
                    best_prev = pi
            if best_prev >= 0:
                matched_ids[ci] = prev_points[best_prev]['id']
                used_prev.add(best_prev)

    return matched_ids, next_id


# ============================================================
#  核心：STNNet 视频推理
# ============================================================
def _run_stnnet_video_inference(task_id: str, video_path: str):
    """
    对视频做 STNNet 推理。

    严格遵循 mytest.py + image_test.py 的官方流程：
    1. 每帧 FiveCrop 4 个子图
    2. 4 个子图分别推理（4 次 model() 调用，与官方一致）
    3. 密度图拼接 + 除以 100
    4. 追踪点坐标偏移修正
    5. calc_trkpt 合并点
    """
    task = _stnnet_video_tasks.get(task_id)
    if not task:
        return None

    task["status"] = "running"
    task["progress"] = 0
    task["message"] = "加载 STNNet 模型..."

    model = _load_stnnet_model()
    task["progress"] = 5
    task["message"] = "打开视频..."

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        task["status"] = "failed"
        task["message"] = f"无法打开视频: {video_path}"
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    task["total_frames"] = total_frames
    task["message"] = f"STNNet 追踪推理中 (优化版), 共 {total_frames} 帧, {orig_w}x{orig_h}"
    try: db_update_task(task_id, status="running", message=task["message"])
    except: pass

    output_video = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}_tracking.mp4")
    output_json = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}_result.json")
    density_dir = os.path.join(STNNET_VIDEO_RESULT_DIR, f"{task_id}_density")
    os.makedirs(density_dir, exist_ok=True)

    stn_mode = task.get("mode", "tracking")
    is_detection = stn_mode == "detection"

    out_writer = None
    frame_idx = 0
    all_frame_data = []
    start_time = time.time()

    prev_points = None
    next_track_id = 0
    trajectory_history: Dict[int, list] = {}

    prev_frame_bgr = None

    TARGET_W, TARGET_H = 1920, 1080
    CROP_FACTOR = 0.5

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # 缩放到目标分辨率
        fh, fw = frame.shape[:2]
        scale_to_target = min(TARGET_W / fw, TARGET_H / fh, 1.0)
        if scale_to_target < 1.0:
            new_w, new_h = int(fw * scale_to_target), int(fh * scale_to_target)
            frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            frame_resized = frame.copy()
            new_w, new_h = fw, fh

        crop_w = int(new_w * CROP_FACTOR)
        crop_h = int(new_h * CROP_FACTOR)
        g1_w = crop_w // 2
        g1_h = crop_h // 2

        # 4 个角裁剪
        img1 = frame_resized[0:crop_h, 0:crop_w]
        img2 = frame_resized[0:crop_h, new_w - crop_w:new_w]
        img3 = frame_resized[new_h - crop_h:new_h, 0:crop_w]
        img4 = frame_resized[new_h - crop_h:new_h, new_w - crop_w:new_w]

        # BGR → RGB
        curr_rgbs = [cv2.cvtColor(c, cv2.COLOR_BGR2RGB) for c in [img1, img2, img3, img4]]

        if prev_frame_bgr is not None:
            prev_crops = [
                prev_frame_bgr[0:crop_h, 0:crop_w],
                prev_frame_bgr[0:crop_h, new_w - crop_w:new_w],
                prev_frame_bgr[new_h - crop_h:new_h, 0:crop_w],
                prev_frame_bgr[new_h - crop_h:new_h, new_w - crop_w:new_w],
            ]
            prev_rgbs = [cv2.cvtColor(c, cv2.COLOR_BGR2RGB) for c in prev_crops]
        else:
            prev_rgbs = curr_rgbs

        # ★ 直接 tensor 预处理（跳过 PIL）
        with torch.no_grad():
            with torch.amp.autocast('cuda'):
                # 4 组分别推理（与官方 mytest.py 一致）
                imgs1_t = [_preprocess_single(prev_rgbs[0]), _preprocess_single(curr_rgbs[0])]
                imgs2_t = [_preprocess_single(prev_rgbs[1]), _preprocess_single(curr_rgbs[1])]
                imgs3_t = [_preprocess_single(prev_rgbs[2]), _preprocess_single(curr_rgbs[2])]
                imgs4_t = [_preprocess_single(prev_rgbs[3]), _preprocess_single(curr_rgbs[3])]

                den_g11, den_g12, den_g13, loc_g11, loc_g12, loc_g13, loc_g14, \
                    reg_g11, reg_g12, reg_g13, reg_g14, trk_s14, trk_o14, trk_p14 = model(imgs1_t)
                den_g21, den_g22, den_g23, loc_g21, loc_g22, loc_g23, loc_g24, \
                    reg_g21, reg_g22, reg_g23, reg_g24, trk_s24, trk_o24, trk_p24 = model(imgs2_t)
                den_g31, den_g32, den_g33, loc_g31, loc_g32, loc_g33, loc_g34, \
                    reg_g31, reg_g32, reg_g33, reg_g34, trk_s34, trk_o34, trk_p34 = model(imgs3_t)
                den_g41, den_g42, den_g43, loc_g41, loc_g42, loc_g43, loc_g44, \
                    reg_g41, reg_g42, reg_g43, reg_g44, trk_s44, trk_o44, trk_p44 = model(imgs4_t)

        # 密度图拼接
        data12 = np.hstack((
            den_g11[1].float().cpu().numpy().squeeze(),
            den_g21[1].float().cpu().numpy().squeeze()
        ))
        data34 = np.hstack((
            den_g31[1].float().cpu().numpy().squeeze(),
            den_g41[1].float().cpu().numpy().squeeze()
        ))
        out_data = np.vstack((data12, data34))
        out_data = np.maximum(out_data, 0)

        # ★ 保存密度数据 (供热力图 + 3D 地形)
        if frame_idx % 2 == 0:  # 每2帧保存一次，节省空间
            # 密度热力图 PNG
            den_vis = out_data / max(out_data.max(), 1e-8) * 255.0
            den_vis = np.clip(den_vis, 0, 255).astype(np.uint8)
            heatmap_bgr = cv2.applyColorMap(den_vis, cv2.COLORMAP_JET)
            cv2.imwrite(os.path.join(density_dir, f"heatmap_{frame_idx:06d}.jpg"),
                        heatmap_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            # 密度网格 JSON (降采样到 48x48 供 3D 地形)
            grid_sz = 48
            h, w = out_data.shape
            den_small = cv2.resize(out_data, (grid_sz, grid_sz), interpolation=cv2.INTER_AREA)
            import json as _json
            with open(os.path.join(density_dir, f"grid_{frame_idx:06d}.json"), 'w') as gf:
                _json.dump(den_small.tolist(), gf)

        # 追踪点坐标偏移修正
        p1 = (trk_p14[0] - trk_o14[0] * 5.0).float().cpu().numpy().squeeze()
        p2 = (trk_p24[0] - trk_o24[0] * 5.0).float().cpu().numpy().squeeze()
        p2[:, 1] = p2[:, 1] + g1_w
        p3 = (trk_p34[0] - trk_o34[0] * 5.0).float().cpu().numpy().squeeze()
        p3[:, 0] = p3[:, 0] + g1_h
        p4 = (trk_p44[0] - trk_o44[0] * 5.0).float().cpu().numpy().squeeze()
        p4[:, 0] = p4[:, 0] + g1_h
        p4[:, 1] = p4[:, 1] + g1_w

        outpts = np.vstack((p1, p2, p3, p4))

        s1 = trk_s14[0].float().cpu().numpy().squeeze()
        s2 = trk_s24[0].float().cpu().numpy().squeeze()
        s3 = trk_s34[0].float().cpu().numpy().squeeze()
        s4 = trk_s44[0].float().cpu().numpy().squeeze()
        outscs = np.hstack((s1, s2, s3, s4))

        # 过滤 NaN/Inf
        valid_mask = np.isfinite(outpts).all(axis=1) & np.isfinite(outscs)
        outpts = outpts[valid_mask]
        outscs = outscs[valid_mask]

        # 提取最终点
        xp, yp, sc = _calc_trkpt(outpts, outscs, thre=0.5,
                                   ourmap=out_data / 100.0,
                                   neighbor_thre=8, ratio=2.0)

        # 裁剪到有效范围
        valid = (xp >= 0) & (xp < new_w) & (yp >= 0) & (yp < new_h)
        xp = xp[valid]
        yp = yp[valid]
        sc = sc[valid]

        # 映射到原始分辨率
        if scale_to_target < 1.0:
            xp = xp / scale_to_target
            yp = yp / scale_to_target

        count = len(xp)

        # ============================================================
        #  检测点构建 (tracking 模式做帧间匹配, detection 模式每帧独立)
        # ============================================================
        if is_detection:
            # 检测模式: 无帧间匹配, 按置信度排序给 index 作为显示 ID
            order = np.argsort(-sc) if len(sc) > 0 else np.array([], dtype=int)
            curr_points = [
                {'id': int(idx), 'x': float(xp[oi]), 'y': float(yp[oi]), 'conf': float(sc[oi])}
                for idx, oi in enumerate(order)
            ]
            active_ids = set()
        else:
            # 追踪模式: 帧间贪心匹配
            matched_ids, next_track_id_new = _match_points(prev_points, xp, yp)
            if prev_points is None or len(prev_points) == 0:
                next_track_id = 0
            curr_points = []
            for pi in range(count):
                tid = matched_ids[pi] if matched_ids[pi] >= 0 else next_track_id
                if matched_ids[pi] < 0:
                    next_track_id += 1
                curr_points.append({
                    'id': tid, 'x': float(xp[pi]), 'y': float(yp[pi]), 'conf': float(sc[pi]),
                })
            if prev_points is not None and len(prev_points) > 0:
                next_track_id = max(next_track_id, next_track_id_new)
            # 更新轨迹历史
            for pt in curr_points:
                tid = pt['id']
                if tid not in trajectory_history:
                    trajectory_history[tid] = []
                trajectory_history[tid].append((pt['x'], pt['y']))
                if len(trajectory_history[tid]) > TRAIL_LENGTH:
                    trajectory_history[tid] = trajectory_history[tid][-TRAIL_LENGTH:]
            active_ids = {pt['id'] for pt in curr_points}
            stale_ids = [tid for tid in trajectory_history if tid not in active_ids]
            for tid in stale_ids:
                if len(trajectory_history[tid]) > 0:
                    trajectory_history[tid].pop(0)
                if len(trajectory_history[tid]) == 0:
                    del trajectory_history[tid]

        # ============================================================
        #  绘制可视化 —— DroneCrowdVisualizer 风格
        # ============================================================
        vis = frame.copy()

        # --- 1. 轨迹拖尾 (仅 tracking 模式) ---
        if not is_detection:
            trail_canvas = np.zeros_like(vis, dtype=np.float32)
            for tid, traj in trajectory_history.items():
                if len(traj) < 2:
                    continue
                color = _track_color(tid)
                alpha_base = 1.0 if tid in active_ids else 0.35
                for i in range(1, len(traj)):
                    t_val = i / max(len(traj) - 1, 1)
                    alpha = alpha_base * (0.25 + 0.75 * t_val)
                    pt1 = (int(traj[i - 1][0]), int(traj[i - 1][1]))
                    pt2 = (int(traj[i][0]), int(traj[i][1]))
                    thickness = max(1, int(3.0 * alpha))
                    cv2.line(trail_canvas, pt1, pt2,
                             tuple(c * alpha for c in color), thickness, cv2.LINE_AA)
            if np.any(trail_canvas > 0):
                trail_mask = (trail_canvas.max(axis=2) > 0).astype(np.float32)
                trail_mask_3ch = np.stack([trail_mask] * 3, axis=-1)
                vis = (trail_mask_3ch * trail_canvas + (1 - trail_mask_3ch) * vis.astype(np.float32)).astype(np.uint8)

        # --- 2. 检测框 (per-ID color, 半透明填充 + 实线边框 + ID 标签) ---
        overlay = vis.copy()
        for pt in curr_points:
            x, y = int(pt['x']), int(pt['y'])
            color = _track_color(pt['id'])
            hs = BOX_SIZE // 2
            x1, y1 = max(0, x - hs), max(0, y - hs)
            x2, y2 = min(orig_w, x + hs), min(orig_h, y + hs)

            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            label = str(pt['id'])
            font_scale = 0.45
            thickness = 1
            (lw, lh), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness)
            pad_w, pad_h = 6, 3
            chip_y1 = y1 - lh - pad_h * 2
            chip_y2 = y1
            chip_x1, chip_x2 = x1, x1 + lw + pad_w * 2
            chip_x1 = max(0, chip_x1)
            chip_x2 = min(orig_w, chip_x2)
            cv2.rectangle(vis, (chip_x1, max(0, chip_y1)),
                          (chip_x2, min(orig_h, chip_y2)), color, -1)
            text_x = chip_x1 + pad_w
            text_y = chip_y2 - pad_h
            if text_y > 0 and text_y < orig_h:
                cv2.putText(vis, label, (text_x, text_y),
                            cv2.FONT_HERSHEY_DUPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        vis = _blend_overlay(vis, overlay, 0.35)

        # --- 3. 人数 badge + 底部信息栏 ---
        overlay = vis.copy()
        text = str(count)
        badge_font_scale = 1.0
        badge_thickness = 2
        (bw, bh), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, badge_font_scale, badge_thickness)
        badge_margin = 14
        badge_x1 = orig_w - bw - badge_margin * 2 - 10
        badge_y1 = orig_h - bh - badge_margin * 2 - 10
        badge_x2 = orig_w - 10
        badge_y2 = orig_h - 10
        cv2.rectangle(overlay, (badge_x1, badge_y1), (badge_x2, badge_y2), (0, 0, 0), -1)
        vis = _blend_overlay(vis, overlay, 0.55)
        cv2.putText(vis, text,
                    (badge_x1 + badge_margin, badge_y2 - badge_margin),
                    cv2.FONT_HERSHEY_DUPLEX, badge_font_scale, (255, 255, 255), badge_thickness, cv2.LINE_AA)

        bar_h = 38
        bar_y1 = orig_h - bar_h
        cv2.rectangle(overlay, (0, bar_y1), (orig_w, orig_h), (0, 0, 0), -1)
        vis = _blend_overlay(vis, overlay, 0.55)

        mode_label = "Detection" if is_detection else "Tracking"
        info_text = f"STNNet {mode_label}  |  Frame {frame_idx} / {total_frames}"
        cv2.putText(vis, info_text, (16, orig_h - 13),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        count_text = f"{count} people"
        (cw, _), _ = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
        cv2.putText(vis, count_text, (orig_w - cw - 16, orig_h - 13),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (200, 210, 220), 1, cv2.LINE_AA)

        if out_writer is None:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_writer = cv2.VideoWriter(output_video, fourcc, fps, (orig_w, orig_h))

        out_writer.write(vis)

        all_frame_data.append({
            "frame": frame_idx,
            "count": count,
            "peaks": [[p['x'], p['y']] for p in curr_points],
            "points": [{"id": p['id'], "x": p['x'], "y": p['y'], "conf": p['conf']}
                       for p in curr_points],
        })

        prev_points = curr_points
        prev_frame_bgr = frame_resized.copy()

        progress = 5 + int(frame_idx / total_frames * 90)
        elapsed = time.time() - start_time
        fps_avg = frame_idx / elapsed if elapsed > 0 else 0
        task["progress"] = progress
        task["message"] = (f"STNNet 追踪中 {frame_idx}/{total_frames}, "
                          f"当前 {count} 人, ~{fps_avg:.1f} fps")
        # 每30帧写入一次进度到SQLite
        if frame_idx % 30 == 0:
            try: db_update_task(task_id, progress=progress, message=task["message"])
            except: pass

    # 收尾
    cap.release()
    if out_writer:
        out_writer.release()

    # 转码 H.264
    try:
        import subprocess
        h264_video = output_video.replace(".mp4", "_h264.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", output_video,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an", h264_video
        ], check=True, capture_output=True)
        os.replace(h264_video, output_video)
    except Exception as e:
        print(f"[STNNetVideo] ffmpeg 转码失败: {e}")

    elapsed = time.time() - start_time
    total_detections = sum(f["count"] for f in all_frame_data)

    result = {
        "task_id": task_id,
        "video_path": video_path,
        "output_video": output_video,
        "model": "STNNet",
        "fps": fps,
        "total_frames": frame_idx,
        "width": orig_w,
        "height": orig_h,
        "total_time": round(elapsed, 1),
        "avg_count": round(total_detections / max(frame_idx, 1), 1),
        "total_detections": total_detections,
        "frames": all_frame_data,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    _stnnet_video_results[task_id] = result
    task["status"] = "done"
    task["progress"] = 100
    task["message"] = (f"STNNet 追踪完成! {frame_idx} 帧, 耗时 {elapsed:.1f}s, "
                      f"均速 {frame_idx/elapsed:.1f} fps")

    # 持久化结果到 SQLite
    try:
        db_update_task(task_id, status="done", progress=100, message=task["message"])
        db_save_result(task_id, result)
    except Exception as e:
        print(f"[STNNetVideo] DB save failed: {e}")

    return result


# ============================================================
#  任务管理 API
# ============================================================
def create_stnnet_video_task(filename: str, size_mb: float = 0, mode: str = "tracking") -> str:
    task_id = f"stv_{uuid.uuid4().hex[:8]}"
    mode_label = "追踪" if mode == "tracking" else "检测"
    _stnnet_video_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": f"等待 STNNet 视频{mode_label}...",
        "model": "STNNet",
        "mode": mode,
        "filename": filename,
        "size_mb": size_mb,
        "total_frames": 0,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # 持久化到 SQLite
    try:
        db_create_task(task_id, status="pending", message=f"等待 STNNet 视频{mode_label}...",
                       mode=mode, model="STNNet", filename=filename, size_mb=size_mb)
    except Exception:
        pass
    return task_id


def get_stnnet_video_task(task_id: str):
    return _stnnet_video_tasks.get(task_id)


def get_stnnet_video_result(task_id: str):
    return _stnnet_video_results.get(task_id)


def run_stnnet_video_async(task_id: str, video_path: str):
    t = threading.Thread(
        target=_run_stnnet_video_inference,
        args=(task_id, video_path),
        daemon=True,
    )
    t.start()
    return task_id
