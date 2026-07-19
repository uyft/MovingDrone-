#!/usr/bin/env python3
"""
离线视频人群检测+跟踪脚本
用法: python video_demo.py --video /path/to/video.mp4 --output output.mp4
"""
import argparse
import cv2
import os
import sys
import time
import numpy as np
from collections import defaultdict
from copy import deepcopy

import torch
import torch.nn.functional as F
from PIL import Image
import torchvision.transforms as standard_transforms

# 项目内部模块
from config import cfg
from model.VIC import Video_Counter
from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from mmcv import Config
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from skimage.feature import peak_local_max

parser = argparse.ArgumentParser(description='离线视频人群检测与跟踪')
parser.add_argument('--video', type=str, required=True, help='输入视频路径')
parser.add_argument('--output', type=str, default='output_video.mp4', help='输出视频路径')
parser.add_argument('--model_path', type=str, default='./pretrained/GD3A_MDC++_best_model_VGG16.pth', help='主模型权重')
parser.add_argument('--counter_path', type=str, default='./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth', help='全局计数器权重')
parser.add_argument('--interval', type=int, default=4, help='帧间隔（每隔多少帧做一次匹配推理）')
parser.add_argument('--GPU_ID', type=str, default='0')
parser.add_argument('--max_long', type=int, default=1920, help='推理时图像长边最大尺寸')
parser.add_argument('--max_short', type=int, default=1080, help='推理时图像短边最大尺寸')
parser.add_argument('--zoom', action='store_true', default=True, help='是否生成局部放大效果')
parser.add_argument('--zoom_scale', type=float, default=2.5, help='局部放大倍数')
parser.add_argument('--show_fps', action='store_true', default=True, help='显示 FPS')
parser.add_argument('--threshold_rel', type=float, default=0.1, help='密度图峰值检测相对阈值（越高越严格，减少误检）')
parser.add_argument('--min_distance', type=int, default=8, help='峰值最小间距（像素，越大越少框）')
args = parser.parse_args()

os.environ["CUDA_VISIBLE_DEVICES"] = args.GPU_ID

# ─── 加载模型 ─────────────────────────────────────────────
print("[1/4] 加载模型...")
cfg.MODEL = "GD3A"
# 根据权重文件名自动选择 backbone
if "ResNet" in args.model_path or "resnet" in args.model_path.lower():
    cfg.encoder = "ResNet_50_FPN"
    print("  使用 ResNet50 骨干网络")
else:
    cfg.encoder = "VGG16_FPN"
    print("  使用 VGG16 骨干网络")
cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
cfg_data.DATA_PATH = os.path.dirname(args.counter_path)  # 不需要数据集，随便设

model = Video_Counter(cfg, cfg_data).cuda()
state_dict = torch.load(args.model_path, map_location='cpu')
# 去掉 module. 前缀
clean_sd = {}
for k, v in state_dict.items():
    while k.startswith("module."):
        k = k[7:]
    clean_sd[k] = v
model.load_state_dict(clean_sd, strict=True)
model.eval()

counter_config = Config.fromfile("model/density_estimator/STEERER/configs/MDC.py")
global_counter = STEERER(counter_config.network,
                         counter_config.dataset.den_factor,
                         counter_config.train.route_size).cuda()
counter_sd = torch.load(args.counter_path, map_location='cpu')
clean_cs = {}
for k, v in counter_sd.items():
    while k.startswith("module."):
        k = k[7:]
    clean_cs[k] = v
global_counter.load_state_dict(clean_cs, strict=True)
global_counter.eval()

# 图像预处理
mean_std = cfg_data.MEAN_STD
img_transform = standard_transforms.Compose([
    standard_transforms.ToTensor(),
    standard_transforms.Normalize(*mean_std)
])

# 反归一化（用于可视化）
denorm = standard_transforms.Compose([
    standard_transforms.Normalize(mean=[0, 0, 0], std=[1 / s for s in mean_std[1]]),
    standard_transforms.Normalize(mean=[-m for m in mean_std[0]], std=[1, 1, 1])
])

print(f"  模型: GD3A (VGG16), 计数器: STEERER")
print(f"  GPU: {args.GPU_ID}")


# ─── 跟踪器（简化版，基于密度图峰值） ─────────────────────
class SimpleTracker:
    """基于密度图峰值的轻量跟踪器，适合无标注视频"""
    def __init__(self, proximity_radius=20, threshold_rel=0.1, min_distance=8):
        self.next_id = 0
        self.active_tracks = {}  # {id: (x, y)}
        self.proximity_radius = proximity_radius
        self.threshold_rel = threshold_rel
        self.min_distance = min_distance

    def _get_peaks(self, density_map, threshold_rel=None):
        if threshold_rel is None:
            threshold_rel = self.threshold_rel
        if isinstance(density_map, torch.Tensor):
            density_map = density_map.detach().cpu().numpy()
        if density_map.ndim == 3:
            density_map = np.squeeze(density_map)
        threshold_abs = density_map.max() * threshold_rel
        peaks = peak_local_max(density_map, min_distance=self.min_distance, threshold_abs=threshold_abs)
        if len(peaks) > 0:
            return peaks[:, ::-1].astype(np.float32)  # (x, y)
        return np.empty((0, 2))

    def initialize(self, density_map):
        peaks = self._get_peaks(density_map)
        self.active_tracks = {}
        for p in peaks:
            self.active_tracks[self.next_id] = tuple(p)
            self.next_id += 1
        return self.active_tracks

    def update(self, density_map):
        peaks = self._get_peaks(density_map)
        if len(peaks) == 0:
            self.active_tracks = {}
            return self.active_tracks

        if len(self.active_tracks) == 0:
            return self.initialize(density_map)

        prev_ids = list(self.active_tracks.keys())
        prev_pos = np.array(list(self.active_tracks.values()))

        if len(prev_pos) == 0:
            return self.initialize(density_map)

        # 匈牙利匹配
        dist = cdist(prev_pos, peaks)
        cost = dist.copy()
        # 超过 proximity_radius 的距离设为很大
        cost[dist > self.proximity_radius] = 1e9

        row_ind, col_ind = linear_sum_assignment(cost)

        new_tracks = {}
        matched_dst = set()
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] < 1e8:
                tid = prev_ids[r]
                new_tracks[tid] = tuple(peaks[c])
                matched_dst.add(c)

        # 新出现的人
        for i in range(len(peaks)):
            if i not in matched_dst:
                new_tracks[self.next_id] = tuple(peaks[i])
                self.next_id += 1

        self.active_tracks = new_tracks
        return self.active_tracks


# ─── 可视化函数 ───────────────────────────────────────────
def plot_on_frame(frame, tracks, counts_text=""):
    """在帧上绘制检测框和ID"""
    vis = frame.copy()
    for tid, (x, y) in tracks.items():
        x, y = int(x), int(y)
        # 绿色框
        w, h = 16, 16
        cv2.rectangle(vis, (x - w // 2, y - h // 2), (x + w // 2, y + h // 2),
                      (0, 255, 0), 2)
        # 黄色 ID
        cv2.putText(vis, str(tid), (x - 10, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    # 左上角计数
    if counts_text:
        cv2.putText(vis, counts_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
    return vis


def draw_dashed_rect(img, pt1, pt2, color, thickness, dash=15, gap=10):
    x1, y1 = pt1
    x2, y2 = pt2
    for x in range(x1, x2, dash + gap):
        cv2.line(img, (x, y1), (min(x + dash, x2), y1), color, thickness)
    for x in range(x1, x2, dash + gap):
        cv2.line(img, (x, y2), (min(x + dash, x2), y2), color, thickness)
    for y in range(y1, y2, dash + gap):
        cv2.line(img, (x1, y), (x1, min(y + dash, y2)), color, thickness)
    for y in range(y1, y2, dash + gap):
        cv2.line(img, (x2, y), (x2, min(y + dash, y2)), color, thickness)


def make_zoom_frame(frame, tracks, zoom_scale=2.5, roi_ratio=0.3):
    """在帧上绘制检测框（不包含放大区域）"""
    if not tracks:
        return frame
    vis = plot_on_frame(frame, tracks)
    return vis


# ─── 主推理函数 ───────────────────────────────────────────
def preprocess_frame(frame):
    """将 OpenCV BGR 帧转为模型输入 tensor"""
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(img)

    w, h = img.size
    ori_w, ori_h = w, h
    long_side = max(w, h)
    short_side = min(w, h)
    max_long, max_short = args.max_long, args.max_short
    scale = 1.0
    scale_long = max_long / long_side if long_side > 0 else 1
    scale_short = max_short / short_side if short_side > 0 else 1
    if scale_long < 1 or scale_short < 1:
        scale = min(scale_long, scale_short)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    tensor = img_transform(img)  # [C, H, W], normalized
    return tensor, scale, ori_w, ori_h


def infer_pair(model, global_counter, img0_t, img1_t):
    """对一对帧进行推理，返回密度图（只用全局计数器）"""
    B = 2
    img = torch.stack([img0_t, img1_t], dim=0).cuda()

    _, _, h, w = img.shape
    pad_h = (32 - h % 32) % 32
    pad_w = (32 - w % 32) % 32
    if pad_h > 0 or pad_w > 0:
        img = F.pad(img, (0, pad_w, 0, pad_h), "constant")

    with torch.no_grad():
        pre_den = global_counter(img)  # [2, 1, H_ds, W_ds]

    # 上采样回原分辨率
    den_h, den_w = pre_den.shape[2], pre_den.shape[3]
    pre_map = F.interpolate(pre_den, size=(h + pad_h, w + pad_w),
                            mode='bilinear', align_corners=False)

    pre_map0 = pre_map[0:1] if pad_h == 0 and pad_w == 0 else pre_map[0:1, :, :h, :w]
    pre_map1 = pre_map[1:2] if pad_h == 0 and pad_w == 0 else pre_map[1:2, :, :h, :w]

    return pre_map0, pre_map1


# ─── 主流程 ───────────────────────────────────────────────
def main():
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"无法打开视频: {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"\n[2/4] 视频信息: {width}x{height}, {fps:.1f} FPS, 共 {total_frames} 帧")

    # 输出视频
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None
    print(f"[3/4] 输出视频: {args.output}")

    # 帧缓存
    frame_buffer = {}  # {frame_idx: (tensor, scale, ori_w, ori_h)}
    tracker = SimpleTracker(proximity_radius=30, threshold_rel=args.threshold_rel, min_distance=args.min_distance)
    tracker_initialized = False
    pre_den_map = None  # 上一帧的密度图（用于当前帧显示）

    frame_idx = 0
    print(f"\n[4/4] 开始推理...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # 预处理当前帧
        tensor, scale, ori_w, ori_h = preprocess_frame(frame)

        # 判断是否需要做推理（每 interval 帧一次）
        need_infer = (frame_idx == 1 or frame_idx % args.interval == 0 or args.interval <= 1)

        if need_infer:
            # 每帧独立推理（和 test_single_image.py 一样的逻辑）
            t0 = time.time()
            B = 1
            img = tensor.unsqueeze(0).cuda()
            _, _, h, w = img.shape
            pad_h = (32 - h % 32) % 32
            pad_w = (32 - w % 32) % 32
            if pad_h > 0 or pad_w > 0:
                img = F.pad(img, (0, pad_w, 0, pad_h), "constant")

            with torch.no_grad():
                pre_den = global_counter(img)
                # 上采样回原分辨率
                pre_map = F.interpolate(pre_den, size=(h + pad_h, w + pad_w),
                                        mode='bilinear', align_corners=False)
                if pad_h > 0 or pad_w > 0:
                    pre_map = pre_map[:, :, :h, :w]

            pre_den_map = pre_map[0]
            infer_time = (time.time() - t0) * 1000

            # 跟踪：用当前帧密度图更新
            if not tracker_initialized:
                tracks = tracker.initialize(pre_den_map)
                tracker_initialized = True
            else:
                tracks = tracker.update(pre_den_map)
        else:
            # 非推理帧，保持上一帧的跟踪结果
            tracks = tracker.active_tracks if tracker_initialized else {}

        # 可视化
        count = len(tracks) if tracks else 0
        fps_text = ""
        if args.show_fps and need_infer and frame_idx > args.interval:
            fps_text = f" | Infer: {infer_time:.0f}ms"

        counts_text = f"Frame {frame_idx} | Count: {count}{fps_text}"

        if args.zoom:
            vis_frame = make_zoom_frame(frame, tracks, zoom_scale=args.zoom_scale)
        else:
            vis_frame = plot_on_frame(frame, tracks, counts_text)

        # 第一帧时初始化 VideoWriter
        if out is None:
            vh, vw = vis_frame.shape[:2]
            out = cv2.VideoWriter(args.output, fourcc, fps, (vw, vh))
            if not out.isOpened():
                print(f"错误: 无法创建输出视频 {args.output}")
                sys.exit(1)
            print(f"  输出尺寸: {vw}x{vh}")

        out.write(vis_frame)

        # 缓存当前帧
        if need_infer or frame_idx == 1:
            frame_buffer[frame_idx] = (tensor, scale, ori_w, ori_h)
            # 清理旧缓存
            keys_to_del = [k for k in frame_buffer if k < frame_idx - args.interval * 2]
            for k in keys_to_del:
                del frame_buffer[k]

        if frame_idx % 50 == 0 or frame_idx == 1:
            print(f"  已处理 {frame_idx}/{total_frames} 帧, 当前检测 {count} 人")

    cap.release()
    out.release()
    print(f"\n完成！输出: {args.output}")
    print(f"共处理 {frame_idx} 帧")


if __name__ == '__main__':
    main()
