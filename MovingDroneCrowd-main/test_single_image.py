#!/usr/bin/env python3
"""
单张图片人群检测脚本
用法: python test_single_image.py --image dataset/test.png --output dataset/test_result.jpg
"""
import argparse
import cv2
import os
import sys
import numpy as np
from copy import deepcopy

import torch
import torch.nn.functional as F
from PIL import Image
import torchvision.transforms as standard_transforms

from config import cfg
from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from mmcv import Config
from skimage.feature import peak_local_max

parser = argparse.ArgumentParser(description='单张图片人群检测')
parser.add_argument('--image', type=str, default='dataset/test.png', help='输入图片路径')
parser.add_argument('--output', type=str, default='dataset/test_result.jpg', help='输出图片路径')
parser.add_argument('--counter_path', type=str,
                    default='./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth',
                    help='全局计数器权重')
parser.add_argument('--GPU_ID', type=str, default='0')
parser.add_argument('--max_long', type=int, default=1920, help='推理时图像长边最大尺寸')
parser.add_argument('--max_short', type=int, default=1080, help='推理时图像短边最大尺寸')
parser.add_argument('--min_distance', type=int, default=10, help='峰值最小间距（像素）')
parser.add_argument('--threshold_rel', type=float, default=0.15, help='峰值相对阈值')
args = parser.parse_args()

os.environ["CUDA_VISIBLE_DEVICES"] = args.GPU_ID

print(f"输入图片: {args.image}")

# ─── 加载模型 ─────────────────────────────────────────────
print("[1/3] 加载全局计数器模型...")
cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
cfg_data.DATA_PATH = os.path.dirname(args.counter_path)

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
print("  ✅ 模型加载完成")

# ─── 图像预处理 ───────────────────────────────────────────
mean_std = cfg_data.MEAN_STD
img_transform = standard_transforms.Compose([
    standard_transforms.ToTensor(),
    standard_transforms.Normalize(*mean_std)
])

print("[2/3] 预处理图片...")
img_pil = Image.open(args.image).convert('RGB')
ori_w, ori_h = img_pil.size
print(f"  原始尺寸: {ori_w} x {ori_h}")

# 按长边缩放
w, h = ori_w, ori_h
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
    img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)
    print(f"  缩放到: {new_w} x {new_h} (scale={scale:.3f})")

tensor = img_transform(img_pil).unsqueeze(0)  # [1, C, H, W]
_, _, h, w = tensor.shape

# Pad 到 32 的倍数
pad_h = (32 - h % 32) % 32
pad_w = (32 - w % 32) % 32
if pad_h > 0 or pad_w > 0:
    tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "constant")
    print(f"  Pad: ({pad_h}, {pad_w})")

# ─── 推理 ─────────────────────────────────────────────────
print("[3/3] 推理中...")
tensor = tensor.cuda()

with torch.no_grad():
    density_map = global_counter(tensor)  # [1, 1, H_ds, W_ds]

# 上采样回原分辨率
den_map = F.interpolate(density_map, size=(h + pad_h, w + pad_w),
                        mode='bilinear', align_corners=False)
den_map = den_map[0, 0]  # [H, W]
if pad_h > 0 or pad_w > 0:
    den_map = den_map[:h, :w]

den_map_np = den_map.cpu().numpy()

# ─── 提取峰值（人头位置） ─────────────────────────────────
threshold_abs = den_map_np.max() * args.threshold_rel
peaks = peak_local_max(den_map_np, min_distance=args.min_distance,
                       threshold_abs=threshold_abs)
# peaks 格式: (row, col) = (y, x)
peaks_xy = peaks[:, ::-1].astype(np.float32)  # → (x, y)

# 还原到原始分辨率
if scale != 1.0:
    peaks_xy = peaks_xy / scale

total_count = len(peaks_xy)
print(f"\n{'='*50}")
print(f"  📊 检测结果: {total_count} 人")
print(f"  密度图最大值: {den_map_np.max():.4f}")
print(f"  密度图总和: {den_map_np.sum():.2f}")
print(f"{'='*50}")

# ─── 可视化 ───────────────────────────────────────────────
print("\n绘制结果图...")
img_cv = cv2.imread(args.image)
if img_cv is None:
    print("  ⚠️ 无法用 OpenCV 读取原图，用 PIL 转换")
    img_cv = cv2.cvtColor(np.array(Image.open(args.image).convert('RGB')),
                          cv2.COLOR_RGB2BGR)

vis = img_cv.copy()
h_img, w_img = vis.shape[:2]

# 绘制绿色框和ID
for i, (x, y) in enumerate(peaks_xy):
    x, y = int(x), int(y)
    w_box, h_box = 16, 16
    cv2.rectangle(vis,
                  (max(0, x - w_box // 2), max(0, y - h_box // 2)),
                  (min(w_img, x + w_box // 2), min(h_img, y + h_box // 2)),
                  (0, 255, 0), 2)
    cv2.putText(vis, str(i + 1), (x - 8, y - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

# 左上角显示计数
cv2.putText(vis, f"Count: {total_count}", (15, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

# ─── 密度图热力图 ─────────────────────────────────────────
den_vis = (den_map_np / den_map_np.max() * 255).astype(np.uint8)
den_vis = cv2.applyColorMap(den_vis, cv2.COLORMAP_JET)
den_vis = cv2.resize(den_vis, (w_img, h_img), interpolation=cv2.INTER_LINEAR)

# 叠加密度图到原图
overlay = cv2.addWeighted(img_cv, 0.5, den_vis, 0.5, 0)
cv2.putText(overlay, f"Density Heatmap", (15, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

# 拼接：原图 | 检测结果 | 密度热力图
combined = np.hstack([img_cv, vis, overlay])

os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
cv2.imwrite(args.output, combined)
print(f"  ✅ 结果已保存到: {args.output}")
print(f"  输出尺寸: {combined.shape[1]} x {combined.shape[0]}")
