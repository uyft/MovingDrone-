#!/usr/bin/env python3
"""分析密度图，找出漏检原因"""
import os, sys
import numpy as np
from skimage.feature import peak_local_max
import torch
import torch.nn.functional as F
from PIL import Image
import torchvision.transforms as standard_transforms

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
mean_std = cfg_data.MEAN_STD

from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from mmcv import Config

counter_config = Config.fromfile('model/density_estimator/STEERER/configs/MDC.py')
global_counter = STEERER(counter_config.network,
                         counter_config.dataset.den_factor,
                         counter_config.train.route_size).cuda()
counter_sd = torch.load(
    './pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth',
    map_location='cpu')
clean_cs = {}
for k, v in counter_sd.items():
    while k.startswith('module.'):
        k = k[7:]
    clean_cs[k] = v
global_counter.load_state_dict(clean_cs, strict=True)
global_counter.eval()

img_transform = standard_transforms.Compose([
    standard_transforms.ToTensor(),
    standard_transforms.Normalize(*mean_std)
])

img_pil = Image.open('dataset/test.png').convert('RGB')
ori_w, ori_h = img_pil.size
tensor = img_transform(img_pil).unsqueeze(0).cuda()
_, _, h, w = tensor.shape
pad_h = (32 - h % 32) % 32
pad_w = (32 - w % 32) % 32
if pad_h > 0 or pad_w > 0:
    tensor = F.pad(tensor, (0, pad_w, 0, pad_h), 'constant')

with torch.no_grad():
    density_map = global_counter(tensor)

den_map = F.interpolate(density_map, size=(h + pad_h, w + pad_w),
                        mode='bilinear', align_corners=False)
den_map = den_map[0, 0]
if pad_h > 0 or pad_w > 0:
    den_map = den_map[:h, :w]
den_np = den_map.cpu().numpy()

print(f'密度图 shape: {den_np.shape}')
print(f'密度图 max: {den_np.max():.6f}')
print(f'密度图 sum: {den_np.sum():.4f}')
print(f'密度图 >0 像素比例: {(den_np > 0).sum() / den_np.size * 100:.2f}%')
print()

# 不同阈值
print('=== 不同 threshold_rel 下的检测数量 (min_distance=10) ===')
for th in [0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20]:
    th_abs = den_np.max() * th
    peaks = peak_local_max(den_np, min_distance=10, threshold_abs=th_abs)
    print(f'  thr={th:.2f} (abs={th_abs:.6f}) → {len(peaks)} 人')

# 不同 min_distance
print()
print('=== 不同 min_distance (threshold_rel=0.15) ===')
for md in [4, 6, 8, 10, 12, 15]:
    th_abs = den_np.max() * 0.15
    peaks = peak_local_max(den_np, min_distance=md, threshold_abs=th_abs)
    print(f'  md={md} → {len(peaks)} 人')

# 密度值分布
print()
print('=== 密度值百分位 (非零区域) ===')
flat = den_np[den_np > 0]
for p in [50, 70, 80, 90, 95, 97, 99]:
    print(f'  P{p}: {np.percentile(flat, p):.6f}')

# 低密度区域分析
print()
print('=== 密度图低值区域 ===')
count_bins = [(0, 0.0001), (0.0001, 0.0005), (0.0005, 0.001), (0.001, 0.002), (0.002, 0.005), (0.005, 0.01)]
for lo, hi in count_bins:
    mask = (den_np > lo) & (den_np <= hi)
    print(f'  ({lo:.4f}, {hi:.4f}]: {mask.sum()} 像素, 贡献={den_np[mask].sum():.4f}')
