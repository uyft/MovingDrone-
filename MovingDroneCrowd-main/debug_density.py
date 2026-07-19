#!/usr/bin/env python3
import torch
import torch.nn.functional as F
from PIL import Image
import torchvision.transforms as standard_transforms
import cv2
import numpy as np

from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from mmcv import Config

cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
counter_config = Config.fromfile('model/density_estimator/STEERER/configs/MDC.py')
global_counter = STEERER(counter_config.network, counter_config.dataset.den_factor,
                         counter_config.train.route_size).cuda()
sd = torch.load('./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth',
                map_location='cpu')
clean = {k[7:] if k.startswith('module.') else k: v for k, v in sd.items()}
global_counter.load_state_dict(clean, strict=True)
global_counter.eval()

mean_std = cfg_data.MEAN_STD
img_transform = standard_transforms.Compose([standard_transforms.ToTensor(),
                                              standard_transforms.Normalize(*mean_std)])

# === 单图方式 ===
frame = cv2.imread('dataset/a0efd725418009ad3b7838f4eb6b3ec4.png')
img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
img_pil = Image.fromarray(img)
w, h = img_pil.size
long_side, short_side = max(w, h), min(w, h)
scale_long = 1920 / long_side
scale_short = 1080 / short_side
scale = min(scale_long, scale_short) if (scale_long < 1 or scale_short < 1) else 1.0
new_w, new_h = int(w * scale), int(h * scale)
img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)
tensor = img_transform(img_pil).unsqueeze(0)
_, _, h2, w2 = tensor.shape
pad_h, pad_w = (32 - h2 % 32) % 32, (32 - w2 % 32) % 32
if pad_h > 0 or pad_w > 0:
    tensor = F.pad(tensor, (0, pad_w, 0, pad_h), 'constant')

with torch.no_grad():
    den = global_counter(tensor.cuda())
den_map = F.interpolate(den, size=(h2 + pad_h, w2 + pad_w), mode='bilinear', align_corners=False)[0, 0, :h2, :w2]
den_np = den_map.cpu().numpy()
print(f"=== 单图方式 (a0efd png) ===")
print(f"  shape={den_np.shape}, max={den_np.max():.6f}, sum={den_np.sum():.2f}")
print(f"  threshold_abs(0.25): {den_np.max() * 0.25:.6f}")

# === 视频第一帧方式 ===
cap = cv2.VideoCapture('dataset/13423250_3840_2160_30fps.mp4')
ret, vframe = cap.read()
vimg = cv2.cvtColor(vframe, cv2.COLOR_BGR2RGB)
vpil = Image.fromarray(vimg)
vw, vh = vpil.size
sl, ss = max(vw, vh), min(vw, vh)
sc_l = 1920 / sl; sc_s = 1080 / ss
sc = min(sc_l, sc_s) if (sc_l < 1 or sc_s < 1) else 1.0
vnw, vnh = int(vw * sc), int(vh * sc)
vpil = vpil.resize((vnw, vnh), Image.LANCZOS)
vtensor = img_transform(vpil).unsqueeze(0)
_, _, vh2, vw2 = vtensor.shape
vph, vpw = (32 - vh2 % 32) % 32, (32 - vw2 % 32) % 32
if vph > 0 or vpw > 0:
    vtensor = F.pad(vtensor, (0, vpw, 0, vph), 'constant')

with torch.no_grad():
    vden = global_counter(vtensor.cuda())
vmap = F.interpolate(vden, size=(vh2 + vph, vw2 + vpw), mode='bilinear', align_corners=False)[0, 0, :vh2, :vw2]
vnp = vmap.cpu().numpy()
print(f"\n=== 视频第一帧 (13423250 mp4) ===")
print(f"  shape={vnp.shape}, max={vnp.max():.6f}, sum={vnp.sum():.2f}")
print(f"  threshold_abs(0.25): {vnp.max() * 0.25:.6f}")

cap.release()
