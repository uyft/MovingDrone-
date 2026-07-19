#!/usr/bin/env python3
"""
视频分帧 → 逐帧用 STEERER 单图推理 → 合成视频
效果和 test_single_image.py 完全一致
用法: python frame_by_frame_demo.py --video input.mp4 --output output.mp4
"""
import argparse
import cv2
import os
import sys
import time
import numpy as np

import torch
import torch.nn.functional as F
from PIL import Image
import torchvision.transforms as standard_transforms

from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from mmcv import Config
from skimage.feature import peak_local_max

parser = argparse.ArgumentParser(description='逐帧推理视频')
parser.add_argument('--video', type=str, required=True)
parser.add_argument('--output', type=str, default='frame_result.mp4')
parser.add_argument('--counter_path', type=str,
                    default='./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth')
parser.add_argument('--GPU_ID', type=str, default='0')
parser.add_argument('--max_long', type=int, default=1920)
parser.add_argument('--max_short', type=int, default=1080)
parser.add_argument('--min_distance', type=int, default=10)
parser.add_argument('--threshold_rel', type=float, default=0.15)
args = parser.parse_args()

os.environ["CUDA_VISIBLE_DEVICES"] = args.GPU_ID

print(f"输入: {args.video}")
print(f"[1/4] 加载计数器模型...")
cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
cfg_data.DATA_PATH = os.path.dirname(args.counter_path)

counter_config = Config.fromfile("model/density_estimator/STEERER/configs/MDC.py")
global_counter = STEERER(counter_config.network,
                         counter_config.dataset.den_factor,
                         counter_config.train.route_size).cuda()
sd = torch.load(args.counter_path, map_location='cpu')
clean_cs = {}
for k, v in sd.items():
    while k.startswith("module."):
        k = k[7:]
    clean_cs[k] = v
global_counter.load_state_dict(clean_cs, strict=True)
global_counter.eval()

mean_std = cfg_data.MEAN_STD
img_transform = standard_transforms.Compose([
    standard_transforms.ToTensor(),
    standard_transforms.Normalize(*mean_std)
])
print("  模型加载完成")

cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    print(f"无法打开: {args.video}")
    sys.exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"[2/4] 视频: {width}x{height}, {fps:.1f}fps, {total_frames}帧")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = None
print(f"[3/4] 输出: {args.output}")

frame_idx = 0
start_time = time.time()
print(f"[4/4] 开始逐帧推理...")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1

    # 预处理（和 test_single_image.py 完全一样）
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    w, h = img_pil.size
    long_side = max(w, h)
    short_side = min(w, h)
    scale_long = args.max_long / long_side if long_side > 0 else 1
    scale_short = args.max_short / short_side if short_side > 0 else 1
    scale = 1.0
    if scale_long < 1 or scale_short < 1:
        scale = min(scale_long, scale_short)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)

    tensor = img_transform(img_pil).unsqueeze(0)  # [1,C,H,W]
    _, _, th, tw = tensor.shape
    pad_h = (32 - th % 32) % 32
    pad_w = (32 - tw % 32) % 32
    if pad_h > 0 or pad_w > 0:
        tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "constant")

    # 推理
    with torch.no_grad():
        density_map = global_counter(tensor.cuda())

    # 上采样
    den_map = F.interpolate(density_map, size=(th + pad_h, tw + pad_w),
                            mode='bilinear', align_corners=False)[0, 0]
    if pad_h > 0 or pad_w > 0:
        den_map = den_map[:th, :tw]
    den_np = den_map.cpu().numpy()

    # 提取峰值
    threshold_abs = den_np.max() * args.threshold_rel
    peaks = peak_local_max(den_np, min_distance=args.min_distance,
                           threshold_abs=threshold_abs)
    peaks_xy = (peaks[:, ::-1].astype(np.float32))  # (x,y) in scaled space
    if scale != 1.0:
        peaks_xy = peaks_xy / scale  # 还原到原始分辨率

    count = len(peaks_xy)

    # 绘制检测框（直接在原始分辨率帧上画）
    vis = frame.copy()
    fh, fw = vis.shape[:2]
    for i, (x, y) in enumerate(peaks_xy):
        x, y = int(x), int(y)
        bw, bh = 16, 16
        cv2.rectangle(vis,
                      (max(0, x - bw // 2), max(0, y - bh // 2)),
                      (min(fw, x + bw // 2), min(fh, y + bh // 2)),
                      (0, 255, 0), 2)
        cv2.putText(vis, str(i + 1), (x - 8, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    cv2.putText(vis, f"Frame {frame_idx} | Count: {count}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

    # 写入视频
    if out is None:
        vh, vw = vis.shape[:2]
        out = cv2.VideoWriter(args.output, fourcc, fps, (vw, vh))
        print(f"  输出尺寸: {vw}x{vh}")
    out.write(vis)

    if frame_idx % 50 == 0 or frame_idx == 1:
        print(f"  已处理 {frame_idx}/{total_frames} 帧, 当前检测 {count} 人")

cap.release()
out.release()

elapsed = time.time() - start_time
print(f"\n完成！输出: {args.output}")
print(f"共处理 {frame_idx} 帧, 耗时 {elapsed:.1f}s")
