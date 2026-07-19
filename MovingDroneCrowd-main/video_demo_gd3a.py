#!/usr/bin/env python3
"""
离线视频人群检测+跟踪脚本（GD³A 描述符匹配版）
基于 video_demo.py 改造，用 GD³A 的 Optimal Transport 描述符匹配替代纯位置匹配

用法: python video_demo_gd3a.py --video /path/to/video.mp4 --output output.mp4
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

parser = argparse.ArgumentParser(description='离线视频人群检测与跟踪（GD³A描述符匹配版）')
parser.add_argument('--video', type=str, required=True, help='输入视频路径')
parser.add_argument('--output', type=str, default='output_video_gd3a.mp4', help='输出视频路径')
parser.add_argument('--model_path', type=str, default='./pretrained/GD3A_MDC++_best_model_VGG16.pth', help='主模型权重')
parser.add_argument('--counter_path', type=str, default='./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth', help='全局计数器权重')
parser.add_argument('--interval', type=int, default=4, help='帧间隔（每隔多少帧做一次匹配推理）')
parser.add_argument('--GPU_ID', type=str, default='0')
parser.add_argument('--max_long', type=int, default=1920, help='推理时图像长边最大尺寸')
parser.add_argument('--max_short', type=int, default=1080, help='推理时图像短边最大尺寸')
parser.add_argument('--zoom', action='store_true', default=True, help='是否生成局部放大效果')
parser.add_argument('--zoom_scale', type=float, default=2.5, help='局部放大倍数')
parser.add_argument('--show_fps', action='store_true', default=True, help='显示 FPS')
parser.add_argument('--threshold_rel', type=float, default=0.1, help='密度图峰值检测相对阈值')
parser.add_argument('--min_distance', type=int, default=8, help='峰值最小间距（像素）')
parser.add_argument('--proximity_radius', type=int, default=20, help='描述符归属行人的最大距离（像素）')
parser.add_argument('--min_votes', type=int, default=1, help='最少特征匹配数才建立关联')
args = parser.parse_args()

os.environ["CUDA_VISIBLE_DEVICES"] = args.GPU_ID

# ─── 加载模型 ─────────────────────────────────────────────
print("[1/4] 加载模型...")
cfg.MODEL = "GD3A"
if "ResNet" in args.model_path or "resnet" in args.model_path.lower():
    cfg.encoder = "ResNet_50_FPN"
    print("  使用 ResNet50 骨干网络")
else:
    cfg.encoder = "VGG16_FPN"
    print("  使用 VGG16 骨干网络")

cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
cfg_data.DATA_PATH = os.path.dirname(args.counter_path)

model = Video_Counter(cfg, cfg_data).cuda()
state_dict = torch.load(args.model_path, map_location='cpu')
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

print(f"  模型: GD³A ({cfg.encoder}), 计数器: STEERER")
print(f"  GPU: {args.GPU_ID}")
print(f"  跟踪模式: GD³A 描述符匹配 + 匈牙利算法")


# ─── GD³A 跟踪器（复用 DVTracker.py 的 PedestrianTracker） ───
class GD3ATracker:
    """
    基于 GD³A 描述符匹配的跟踪器。
    核心逻辑与 DVTracker.py 的 PedestrianTracker 一致：
    1. 密度图峰值提取 → 行人位置
    2. GD³A 描述符匹配结果 → 投票矩阵
    3. 匈牙利算法 → ID 传递
    """
    def __init__(self, proximity_radius=20, min_votes=1, stride=8.0,
                 threshold_rel=0.1, min_distance=8):
        self.next_id = 0
        self.active_tracks = {}  # {id: (x, y)}
        self.proximity_radius = proximity_radius
        self.min_votes = min_votes
        self.stride = stride
        self.threshold_rel = threshold_rel
        self.min_distance = min_distance

    def _get_peaks(self, density_map, tensor_shape=None, scale=1.0):
        """
        从密度图提取峰值坐标，并还原到原始图像分辨率。
        density_map: 模型输出的低分辨率密度图 (C, H, W) tensor 或 numpy
        tensor_shape: 预处理后的 tensor 尺寸 (H, W)，用于确定上采样目标尺寸
        scale: 预处理时的缩放比，用于还原到原始分辨率
        """
        if isinstance(density_map, torch.Tensor):
            density_map = density_map.detach().cpu().numpy()
        if density_map.ndim == 3:
            density_map = np.squeeze(density_map)  # (H_den, W_den)

        den_h, den_w = density_map.shape

        # 上采样密度图到预处理后的图像尺寸
        if tensor_shape is not None:
            target_h, target_w = tensor_shape
            # 用 scipy 放大（更精确的插值）
            from scipy.ndimage import zoom
            zoom_h = target_h / den_h
            zoom_w = target_w / den_w
            density_map_zoomed = zoom(density_map, (zoom_h, zoom_w), order=3)
        else:
            density_map_zoomed = density_map

        threshold_abs = density_map_zoomed.max() * self.threshold_rel
        peaks = peak_local_max(density_map_zoomed, min_distance=self.min_distance,
                               threshold_abs=threshold_abs)
        if len(peaks) > 0:
            # peaks 是 (row, col) 即 (y, x)，转为 (x, y)
            result = peaks[:, ::-1].astype(np.float32)
            # 还原缩放到原始图像分辨率
            if scale != 1.0:
                result = result / scale
            return result
        return np.empty((0, 2))

    def initialize(self, density_map, tensor_shape=None, scale=1.0):
        """首帧初始化"""
        peaks = self._get_peaks(density_map, tensor_shape=tensor_shape, scale=scale)
        self.active_tracks = {}
        for p in peaks:
            self.active_tracks[self.next_id] = tuple(p)
            self.next_id += 1
        print(f"  [Init] 检测到 {len(peaks)} 人")
        return self.active_tracks

    def update(self, density_map, matched_results, tensor_shape=None, scale=1.0):
        """
        用 GD³A 描述符匹配结果更新跟踪。
        density_map: 当前帧(I₂)的密度图
        matched_results: GD³A 模型输出的描述符匹配结果
        tensor_shape: 预处理后的 tensor 尺寸 (H, W)
        scale: 预处理缩放比
        """
        # 1. 提取当前帧行人位置（还原到原图分辨率）
        pts_dst = self._get_peaks(density_map, tensor_shape=tensor_shape, scale=scale)

        if len(pts_dst) == 0:
            self.active_tracks = {}
            return self.active_tracks

        if len(self.active_tracks) == 0:
            return self.initialize(density_map)

        # 2. 获取上一帧行人位置
        prev_ids = list(self.active_tracks.keys())
        pts_src = np.array(list(self.active_tracks.values()))

        # 3. 转换描述符坐标到原图尺度
        def to_numpy(x):
            return x.cpu().numpy() if torch.is_tensor(x) else x

        kptsa = to_numpy(matched_results['kpts0'][0]) * self.stride
        kptsb = to_numpy(matched_results['kpts1'][0]) * self.stride
        indicesa = to_numpy(matched_results['matches0'][0])
        indicesb = to_numpy(matched_results['matches1'][0])

        # 4. 描述符归属关联：I₁ 每个描述符属于哪个行人中心
        dist_a2p = cdist(kptsa, pts_src)
        kptsa_owner = np.argmin(dist_a2p, axis=1)
        kptsa_owner[np.min(dist_a2p, axis=1) > self.proximity_radius] = -1

        # I₂ 每个描述符属于哪个行人中心
        dist_b2p = cdist(kptsb, pts_dst)
        kptsb_owner = np.argmin(dist_b2p, axis=1)
        kptsb_owner[np.min(dist_b2p, axis=1) > self.proximity_radius] = -1

        # 5. 构建行人级投票矩阵
        score_matrix = np.zeros((len(pts_src), len(pts_dst)))
        for i, match_idx_in_b in enumerate(indicesa):
            if match_idx_in_b < 0:
                continue
            p_idx_a = kptsa_owner[i]
            p_idx_b = kptsb_owner[match_idx_in_b]
            if p_idx_a != -1 and p_idx_b != -1:
                score_matrix[p_idx_a, p_idx_b] += 1

        for i, match_idx_in_a in enumerate(indicesb):
            if match_idx_in_a < 0:
                continue
            person_idx_b = kptsb_owner[i]
            person_idx_a = kptsa_owner[match_idx_in_a]
            if person_idx_a != -1 and person_idx_b != -1:
                score_matrix[person_idx_a, person_idx_b] += 1

        # 6. 辅助位置约束
        dist_matrix = cdist(pts_src, pts_dst)
        spatial_bias = 1.0 / (1.0 + dist_matrix / 10)

        # 代价矩阵（负值，因为匈牙利算法求最小化）
        cost_matrix = -(score_matrix * 10.0 + spatial_bias)

        # 7. 匈牙利算法求解
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        # 8. ID 传递
        new_dst_ids = np.full(len(pts_dst), -1, dtype=int)
        for r, c in zip(row_indices, col_indices):
            if score_matrix[r, c] >= self.min_votes:
                new_dst_ids[c] = prev_ids[r]

        # 9. 新出现的人
        new_tracks = {}
        for i in range(len(pts_dst)):
            if new_dst_ids[i] == -1:
                new_dst_ids[i] = self.next_id
                self.next_id += 1
            new_tracks[int(new_dst_ids[i])] = tuple(pts_dst[i])

        self.active_tracks = new_tracks
        return self.active_tracks


# ─── 构建虚拟 target（推理时不需要真实标注） ─────────────
def make_dummy_target(img_h, img_w):
    """构建空的 target dict，满足 GD3A_forward 的输入要求"""
    return {
        'points': torch.zeros((0, 2), dtype=torch.long),
        'share_mask0': torch.zeros(0, dtype=torch.bool),
        'outflow_mask': torch.zeros(0, dtype=torch.bool),
        'share_mask1': torch.zeros(0, dtype=torch.bool),
        'inflow_mask': torch.zeros(0, dtype=torch.bool),
        'ori_width': img_w,
        'ori_height': img_h,
    }


# ─── 可视化函数 ───────────────────────────────────────────
def plot_on_frame(frame, tracks, counts_text=""):
    """在帧上绘制检测框和ID"""
    vis = frame.copy()
    for tid, (x, y) in tracks.items():
        x, y = int(x), int(y)
        w, h = 16, 16
        cv2.rectangle(vis, (x - w // 2, y - h // 2), (x + w // 2, y + h // 2),
                      (0, 255, 0), 2)
        cv2.putText(vis, str(tid), (x - 10, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    if counts_text:
        cv2.putText(vis, counts_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
    return vis


def make_zoom_frame(frame, tracks, zoom_scale=2.5, roi_ratio=0.3):
    """在帧上绘制检测框"""
    if not tracks:
        return frame
    vis = plot_on_frame(frame, tracks)
    return vis


# ─── 预处理 ───────────────────────────────────────────────
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

    tensor = img_transform(img)
    return tensor, scale, ori_w, ori_h


# ─── GD³A 帧对推理 ────────────────────────────────────────
def infer_gd3a_pair(model, global_counter, img0_t, img1_t, ori_h0, ori_w0, ori_h1, ori_w1):
    """
    用 GD³A 模型对一对帧进行推理。
    返回：两帧的密度图 + matched_results（描述符匹配结果）
    """
    B = 2
    img = torch.stack([img0_t, img1_t], dim=0).cuda()

    _, _, h, w = img.shape
    pad_h = (32 - h % 32) % 32
    pad_w = (32 - w % 32) % 32
    if pad_h > 0 or pad_w > 0:
        img = F.pad(img, (0, pad_w, 0, pad_h), "constant")

    # 构建虚拟 target（两帧）
    target = [
        make_dummy_target(ori_h0, ori_w0),
        make_dummy_target(ori_h1, ori_w1),
    ]

    with torch.no_grad():
        pre_global_den, gt_global_den, pre_share_den, gt_share_den, \
        pre_in_out_den, gt_in_out_den, loss_dict, matched_results, matched_metrics = \
            model(img, target, global_counter)

    # 上采样密度图回原分辨率
    _, _, den_h, den_w = pre_global_den.shape
    pre_map = F.interpolate(pre_global_den, size=(h + pad_h, w + pad_w),
                            mode='bilinear', align_corners=False)

    pre_map0 = pre_map[0:1] if pad_h == 0 and pad_w == 0 else pre_map[0:1, :, :h, :w]
    pre_map1 = pre_map[1:2] if pad_h == 0 and pad_w == 0 else pre_map[1:2, :, :h, :w]

    return pre_map0, pre_map1, matched_results


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

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = None
    print(f"[3/4] 输出视频: {args.output}")

    tracker = GD3ATracker(
        proximity_radius=args.proximity_radius,
        min_votes=args.min_votes,
        stride=8.0,
        threshold_rel=args.threshold_rel,
        min_distance=args.min_distance
    )
    tracker_initialized = False

    # 缓存上一帧的信息
    prev_tensor = None
    prev_ori_h = None
    prev_ori_w = None
    prev_density_map = None  # 上一帧的密度图（用于非推理帧显示）

    frame_idx = 0
    print(f"\n[4/4] 开始 GD³A 推理...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # 预处理当前帧
        tensor, scale, ori_w, ori_h = preprocess_frame(frame)

        # 判断是否需要做帧对推理（每 interval 帧一次）
        need_infer = (frame_idx % args.interval == 0 or frame_idx == 1)

        if need_infer and prev_tensor is not None:
            # ─── GD³A 帧对推理 ───
            t0 = time.time()

            pre_map0, pre_map1, matched_results = infer_gd3a_pair(
                model, global_counter,
                prev_tensor, tensor,
                prev_ori_h, prev_ori_w, ori_h, ori_w
            )

            infer_time = (time.time() - t0) * 1000

            # 当前帧密度图
            current_density = pre_map1[0]
            prev_density_map = current_density
            # 获取当前帧预处理后的 tensor 尺寸和缩放比（用于坐标还原）
            curr_tensor_shape = tensor.shape[1:]  # (H, W)
            curr_scale = scale

            # 跟踪更新（用 GD³A 描述符匹配）
            if not tracker_initialized:
                tracks = tracker.initialize(current_density, tensor_shape=curr_tensor_shape, scale=curr_scale)
                tracker_initialized = True
            else:
                tracks = tracker.update(current_density, matched_results, tensor_shape=curr_tensor_shape, scale=curr_scale)

        elif need_infer and prev_tensor is None:
            # 首帧：只用 STEERER 做单帧推理来初始化
            t0 = time.time()
            img_single = tensor.unsqueeze(0).cuda()
            _, _, h, w = img_single.shape
            pad_h = (32 - h % 32) % 32
            pad_w = (32 - w % 32) % 32
            if pad_h > 0 or pad_w > 0:
                img_single = F.pad(img_single, (0, pad_w, 0, pad_h), "constant")

            with torch.no_grad():
                pre_den = global_counter(img_single)
                pre_map = F.interpolate(pre_den, size=(h + pad_h, w + pad_w),
                                        mode='bilinear', align_corners=False)
                if pad_h > 0 or pad_w > 0:
                    pre_map = pre_map[:, :, :h, :w]

            prev_density_map = pre_map[0]
            infer_time = (time.time() - t0) * 1000

            tracks = tracker.initialize(prev_density_map, tensor_shape=img_single.shape[2:], scale=scale)
            tracker_initialized = True

        else:
            # 非推理帧，保持上一帧的跟踪结果
            tracks = tracker.active_tracks if tracker_initialized else {}

        # 缓存当前帧信息供下一轮帧对推理
        if need_infer:
            prev_tensor = tensor
            prev_ori_h = ori_h
            prev_ori_w = ori_w

        # 可视化
        count = len(tracks) if tracks else 0
        fps_text = ""
        if args.show_fps and need_infer and frame_idx > 1:
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

        if frame_idx % 50 == 0 or frame_idx == 1:
            mode_str = "GD³A匹配" if (need_infer and prev_tensor is not None) else "单帧初始化"
            print(f"  已处理 {frame_idx}/{total_frames} 帧 [{mode_str}], 当前检测 {count} 人")

    cap.release()
    out.release()
    print(f"\n完成！输出: {args.output}")
    print(f"共处理 {frame_idx} 帧, 跟踪 ID 总数: {tracker.next_id}")


if __name__ == '__main__':
    main()
