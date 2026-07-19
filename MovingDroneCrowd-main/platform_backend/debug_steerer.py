bimport sys
sys.path.insert(0, '/workspace/MovingDroneCrowd-main')
import torch
import torch.nn.functional as F
import cv2
import numpy as np
from PIL import Image

from config import cfg
from cusdatasets.setting import MovingDroneCrowd
from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from mmcv import Config

cfg.MODEL = "GD3A"
cfg.encoder = "VGG16_FPN"

counter_cfg = Config.fromfile("/workspace/MovingDroneCrowd-main/model/density_estimator/STEERER/configs/MDC.py")
counter = STEERER(counter_cfg.network, counter_cfg.dataset.den_factor, counter_cfg.train.route_size)

ckpt = torch.load("/workspace/MovingDroneCrowd-main/pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth", map_location='cpu')
clean_ckpt = {}
for k, v in ckpt.items():
    clean_ckpt[k[7:] if k.startswith("module.") else k] = v
counter.load_state_dict(clean_ckpt, strict=True)
counter = counter.cuda().eval()

# 读取 Frame 8
img = cv2.imread('/workspace/MovingDroneCrowd-main/platform_backend/uploads/frame_tests/ft_e5d4daf1/frames/8.jpg')
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
pil = Image.fromarray(img_rgb)
w, h = pil.size
print(f"Original size: {w}x{h}")

# 预处理
max_long, max_short = 1920, 1080
scale = 1.0
if max(w, h) > max_long:
    scale = max_long / max(w, h)
    w, h = int(w * scale), int(h * scale)
if min(w, h) > max_short:
    s = max_short / min(w, h)
    w, h = int(w * s), int(h * s)

pil = pil.resize((w, h), Image.BILINEAR)
arr = np.array(pil).transpose(2, 0, 1).astype(np.float32) / 255.0
mean = np.array([0.459, 0.431, 0.412], dtype=np.float32).reshape(3, 1, 1)
std = np.array([0.263, 0.257, 0.260], dtype=np.float32).reshape(3, 1, 1)
arr = (arr - mean) / std
tensor = torch.from_numpy(arr).unsqueeze(0).cuda()
print(f"Tensor shape: {tensor.shape}")

# Pad
pad_h = (32 - h % 32) % 32
pad_w = (32 - w % 32) % 32
max_h_p, max_w_p = h + pad_h, w + pad_w
t_p = F.pad(tensor, (0, max_w_p - w, 0, max_h_p - h), "constant")
print(f"Padded shape: {t_p.shape}")

with torch.no_grad():
    den = counter(t_p)
print(f"Counter output shape: {den.shape}")
print(f"Counter output min={den.min().item():.6f}, max={den.max().item():.6f}, sum={den.sum().item():.6f}")

# Interpolate
den_interp = F.interpolate(den, scale_factor=8, mode='bilinear', align_corners=False) / 64.0
print(f"Interpolated shape: {den_interp.shape}")
print(f"Interpolated min={den_interp.min().item():.6f}, max={den_interp.max().item():.6f}, sum={den_interp.sum().item():.6f}")

# Crop
den_crop = den_interp[0, 0, :h, :w]
print(f"Cropped shape: {den_crop.shape}")
print(f"Cropped min={den_crop.min().item():.6f}, max={den_crop.max().item():.6f}, sum={den_crop.sum().item():.6f}")
