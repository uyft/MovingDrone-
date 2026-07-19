"""
对自有视频逐帧用 STEERER 推理 → 人数检测 + 改进版位置追踪
优化点：
1) 加入全局相机运动补偿（无人机移动时非常关键）
2) 加入简单运动预测、轨迹寿命 max_age、确认帧 min_hits
3) 修复原脚本中“未匹配旧轨迹一直保留、ID越积越多”的问题
4) 修复“被匈牙利分配但距离过大而拒绝的检测没有重新生成新ID”的问题
5) 只绘制当前可见且确认的轨迹，避免幽灵轨迹

用法示例：
python3 track_my_video_optimized.py \
  --video dataset/13423250_3840_2160_30fps.mp4 \
  --output track_my_v2.mp4 \
  --threshold_rel 0.22 \
  --min_distance 12 \
  --max_match_dist 45 \
  --max_age 5 \
  --min_hits 2
"""

import cv2
import os
import sys
import time
import argparse
import csv
import colorsys
import numpy as np
import torch
import torch.nn.functional as F

from torchvision import transforms
from PIL import Image
from mmcv import Config
from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from skimage.feature import peak_local_max
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist


parser = argparse.ArgumentParser()
parser.add_argument('--video', type=str, required=True)
parser.add_argument('--output', type=str, default='track_my_video_v2.mp4')
parser.add_argument('--counter_path', type=str,
                    default='pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth')

# STEERER 推理相关
parser.add_argument('--max_long', type=int, default=1920)
parser.add_argument('--max_short', type=int, default=1080)
parser.add_argument('--min_distance', type=int, default=12,
                    help='密度图峰值之间的最小距离。720p建议10-14，4K建议18-28')
parser.add_argument('--threshold_rel', type=float, default=0.22,
                    help='密度图峰值相对阈值。误检多就调大，漏检多就调小')
parser.add_argument('--max_frames', type=int, default=0)
parser.add_argument('--start_frame', type=int, default=0, help='从第几帧开始')
parser.add_argument('--fps_out', type=int, default=10)
parser.add_argument('--gpu', type=str, default='0')

# 追踪相关
parser.add_argument('--max_match_dist', type=float, default=45.0,
                    help='720p下的匹配门限。4K会按分辨率自动放大')
parser.add_argument('--max_age', type=int, default=5,
                    help='轨迹最多允许连续丢失几帧，超过就删除')
parser.add_argument('--min_hits', type=int, default=2,
                    help='连续命中几帧后才认为是稳定轨迹')
parser.add_argument('--trail_length', type=int, default=12)
parser.add_argument('--ema_alpha', type=float, default=0.70,
                    help='轨迹平滑系数，越大越贴近当前检测点')
parser.add_argument('--score_weight', type=float, default=0.10,
                    help='匹配时对高置信峰值的轻微偏好，0表示不用')
parser.add_argument('--no_gmc', action='store_true',
                    help='关闭全局相机运动补偿。不建议无人机视频关闭')

# 可选保存
parser.add_argument('--save_dets', type=str, default='', help='可选：保存每帧检测点CSV')
parser.add_argument('--save_tracks', type=str, default='', help='可选：保存每帧轨迹CSV')
args = parser.parse_args()

os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu


# ============================================================
# 工具函数
# ============================================================

def identity_affine():
    return np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)


def apply_affine_pts(pts, M):
    """pts: [N,2], M: [2,3]"""
    if pts is None or len(pts) == 0:
        return pts
    pts = np.asarray(pts, dtype=np.float32)
    ones = np.ones((len(pts), 1), dtype=np.float32)
    pts_h = np.hstack([pts, ones])
    return pts_h @ M.T


def estimate_global_motion(prev_frame, curr_frame):
    """
    估计上一帧到当前帧的全局仿射变换，用于补偿无人机自身运动。
    返回 M，使得 prev_xy 经过 M 后尽量对齐到 curr_xy。
    """
    if prev_frame is None or curr_frame is None:
        return identity_affine()

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

    h, w = prev_gray.shape[:2]
    max_side = max(h, w)
    resize_scale = 0.5 if max_side > 1000 else 1.0

    if resize_scale != 1.0:
        prev_small = cv2.resize(prev_gray, None, fx=resize_scale, fy=resize_scale)
        curr_small = cv2.resize(curr_gray, None, fx=resize_scale, fy=resize_scale)
    else:
        prev_small, curr_small = prev_gray, curr_gray

    pts0 = cv2.goodFeaturesToTrack(
        prev_small,
        maxCorners=800,
        qualityLevel=0.01,
        minDistance=12,
        blockSize=7
    )

    if pts0 is None or len(pts0) < 20:
        return identity_affine()

    pts1, st, err = cv2.calcOpticalFlowPyrLK(
        prev_small, curr_small, pts0, None,
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    )

    if pts1 is None or st is None:
        return identity_affine()

    st = st.reshape(-1).astype(bool)
    pts0_good = pts0.reshape(-1, 2)[st]
    pts1_good = pts1.reshape(-1, 2)[st]

    if len(pts0_good) < 20:
        return identity_affine()

    M, inliers = cv2.estimateAffinePartial2D(
        pts0_good, pts1_good,
        method=cv2.RANSAC,
        ransacReprojThreshold=3.0,
        maxIters=2000,
        confidence=0.99
    )

    if M is None:
        return identity_affine()

    M = M.astype(np.float32)

    # 小图上的平移量需要还原到原图尺度
    if resize_scale != 1.0:
        M[0, 2] /= resize_scale
        M[1, 2] /= resize_scale

    # 简单异常过滤，避免光流估计失败时把轨迹整体甩飞
    A = M[:, :2]
    det = np.linalg.det(A)
    scale = np.sqrt(abs(det)) if det != 0 else 1.0
    tx, ty = M[0, 2], M[1, 2]
    if not (0.70 <= scale <= 1.30):
        return identity_affine()
    if abs(tx) > w * 0.35 or abs(ty) > h * 0.35:
        return identity_affine()

    return M


class Track:
    def __init__(self, tid, xy, score, frame_idx):
        self.id = tid
        self.xy = np.asarray(xy, dtype=np.float32)
        self.v = np.zeros(2, dtype=np.float32)     # 补偿相机运动后的残余速度
        self.pred = self.xy.copy()
        self.pred_base = self.xy.copy()
        self.score = float(score)
        self.hits = 1
        self.age = 1
        self.missed = 0
        self.last_frame = frame_idx
        self.trail = [tuple(self.xy)]

    def predict(self, M=None):
        if M is None:
            M = identity_affine()
        self.pred_base = apply_affine_pts(self.xy.reshape(1, 2), M)[0]
        self.pred = self.pred_base + self.v
        return self.pred

    def update(self, xy, score, frame_idx, alpha=0.70, trail_length=12):
        xy = np.asarray(xy, dtype=np.float32)

        # 先根据检测点平滑当前位置
        new_xy = alpha * xy + (1.0 - alpha) * self.pred

        # 速度只学习“相机运动补偿后”的残余运动
        residual_v = new_xy - self.pred_base
        self.v = 0.65 * residual_v + 0.35 * self.v

        self.xy = new_xy
        self.score = 0.80 * self.score + 0.20 * float(score)
        self.hits += 1
        self.age += 1
        self.missed = 0
        self.last_frame = frame_idx

        self.trail.append(tuple(self.xy))
        if len(self.trail) > trail_length:
            self.trail = self.trail[-trail_length:]

    def mark_missed(self):
        # 丢失时只更新预测位置，不把预测点加入 trail，避免画出幽灵轨迹
        self.xy = self.pred.copy()
        self.age += 1
        self.missed += 1

    def is_visible(self, frame_idx, min_hits):
        # 当前帧必须命中检测点；刚开始几帧允许显示未确认轨迹，避免第一帧全空
        return self.missed == 0 and (self.hits >= min_hits or frame_idx < min_hits)


def get_color(pid, cache):
    if pid not in cache:
        h = (pid * 0.618033988749895) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.95)
        cache[pid] = (int(r * 255), int(g * 255), int(b * 255))
    return cache[pid]


# ============================================================
# 1. 加载模型
# ============================================================
print("[1/5] 加载 STEERER 计数器模型...")
cfg_data = __import__('cusdatasets.setting.MovingDroneCrowd', fromlist=['cfg_data']).cfg_data
cfg_data.DATA_PATH = os.path.dirname(args.counter_path)

counter_config = Config.fromfile("model/density_estimator/STEERER/configs/MDC.py")
global_counter = STEERER(
    counter_config.network,
    counter_config.dataset.den_factor,
    counter_config.train.route_size
).cuda()

sd = torch.load(args.counter_path, map_location='cpu')
clean_cs = {}
for k, v in sd.items():
    while k.startswith("module."):
        k = k[7:]
    clean_cs[k] = v
global_counter.load_state_dict(clean_cs, strict=True)
global_counter.eval()

mean_std = cfg_data.MEAN_STD
img_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(*mean_std)
])
print("  模型加载完成")


# ============================================================
# 2. 读取视频
# ============================================================
cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    print(f"无法打开: {args.video}")
    sys.exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"[2/5] 视频: {width}x{height}, {fps:.1f}fps, {total_frames}帧")

frames = []
frame_idx = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    if frame_idx >= args.start_frame:
        frames.append(frame)
    frame_idx += 1
    if args.max_frames > 0 and len(frames) >= args.max_frames:
        break
cap.release()

if len(frames) == 0:
    print("没有读取到任何帧")
    sys.exit(1)

fh, fw = frames[0].shape[:2]
match_dist = args.max_match_dist * np.sqrt((fw * fh) / (1280 * 720))
print(f"  读取 {len(frames)} 帧，从原始第 {args.start_frame} 帧开始")
print(f"  当前分辨率 {fw}x{fh}，实际匹配门限 max_match_dist = {match_dist:.1f}px")


# ============================================================
# 3. 逐帧 STEERER 推理，提取检测点
# ============================================================
print("[3/5] 逐帧推理 + 峰值检测...")
start_time = time.time()

all_detections = {}  # fi -> ndarray [N,3], x,y,score

for fi, frame in enumerate(frames):
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

    tensor = img_transform(img_pil).unsqueeze(0)
    _, _, th, tw = tensor.shape

    pad_h = (32 - th % 32) % 32
    pad_w = (32 - tw % 32) % 32
    if pad_h > 0 or pad_w > 0:
        tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "constant")

    with torch.no_grad():
        density_map = global_counter(tensor.cuda())

    den_map = F.interpolate(
        density_map,
        size=(th + pad_h, tw + pad_w),
        mode='bilinear',
        align_corners=False
    )[0, 0]

    if pad_h > 0 or pad_w > 0:
        den_map = den_map[:th, :tw]

    den_np = den_map.detach().cpu().numpy()

    if den_np.size == 0 or den_np.max() <= 0:
        dets = np.empty((0, 3), dtype=np.float32)
    else:
        threshold_abs = den_np.max() * args.threshold_rel
        peaks = peak_local_max(
            den_np,
            min_distance=args.min_distance,
            threshold_abs=threshold_abs
        )

        if len(peaks) == 0:
            dets = np.empty((0, 3), dtype=np.float32)
        else:
            scores = den_np[peaks[:, 0], peaks[:, 1]].astype(np.float32)
            peaks_xy = peaks[:, ::-1].astype(np.float32)

            if scale != 1.0:
                peaks_xy = peaks_xy / scale

            dets = np.concatenate([peaks_xy, scores.reshape(-1, 1)], axis=1)

    all_detections[fi] = dets

    if (fi + 1) % 50 == 0 or fi == 0:
        elapsed = time.time() - start_time
        fps_infer = (fi + 1) / elapsed if elapsed > 0 else 0
        print(f"  帧 {fi+1}/{len(frames)} | 检测 {len(dets)} 人 | 速度 {fps_infer:.1f} fps")

elapsed_infer = time.time() - start_time
print(f"  推理完成，耗时 {elapsed_infer:.1f}s")

if args.save_dets:
    with open(args.save_dets, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'x', 'y', 'score'])
        for fi, dets in all_detections.items():
            for x, y, s in dets:
                writer.writerow([fi, float(x), float(y), float(s)])
    print(f"  检测点已保存: {args.save_dets}")


# ============================================================
# 4. 改进版追踪
# ============================================================
print("[4/5] 全局运动补偿 + 轨迹关联...")

tracks = []
next_tid = 1

frame_persons = {}   # fi -> [(tid, x, y, score)]
frame_trails = {}    # fi -> {tid: [(x,y), ...]}

prev_frame = None

for fi, frame in enumerate(frames):
    dets = all_detections.get(fi, np.empty((0, 3), dtype=np.float32))
    det_pts = dets[:, :2].astype(np.float32) if len(dets) else np.empty((0, 2), dtype=np.float32)
    det_scores = dets[:, 2].astype(np.float32) if len(dets) else np.empty((0,), dtype=np.float32)

    if args.no_gmc:
        M = identity_affine()
    else:
        M = estimate_global_motion(prev_frame, frame) if prev_frame is not None else identity_affine()

    # 预测已有轨迹当前位置
    for trk in tracks:
        trk.predict(M)

    matched_tracks = set()
    matched_dets = set()

    if len(tracks) > 0 and len(det_pts) > 0:
        pred_pts = np.array([trk.pred for trk in tracks], dtype=np.float32)
        dist_mat = cdist(pred_pts, det_pts)

        # 对高置信检测点稍微降低代价，防止低峰值抢匹配
        if args.score_weight > 0 and len(det_scores) > 0 and det_scores.max() > det_scores.min():
            norm_scores = (det_scores - det_scores.min()) / (det_scores.max() - det_scores.min() + 1e-6)
            cost_mat = dist_mat - args.score_weight * match_dist * norm_scores.reshape(1, -1)
        else:
            cost_mat = dist_mat

        row_ind, col_ind = linear_sum_assignment(cost_mat)

        for r, c in zip(row_ind, col_ind):
            real_dist = dist_mat[r, c]
            if real_dist <= match_dist:
                tracks[r].update(
                    det_pts[c],
                    det_scores[c],
                    frame_idx=fi,
                    alpha=args.ema_alpha,
                    trail_length=args.trail_length
                )
                matched_tracks.add(r)
                matched_dets.add(c)

    # 未匹配轨迹：只保留 max_age 帧，超过删除
    for ti, trk in enumerate(tracks):
        if ti not in matched_tracks:
            trk.mark_missed()

    # 未匹配检测：生成新轨迹。注意这里只用“真正接受匹配”的检测集合。
    for di, xy in enumerate(det_pts):
        if di not in matched_dets:
            tracks.append(Track(next_tid, xy, det_scores[di], frame_idx=fi))
            next_tid += 1

    # 删除丢失太久的轨迹
    tracks = [trk for trk in tracks if trk.missed <= args.max_age]

    # 当前帧显示的轨迹：必须当前帧命中检测点
    visible_tracks = [trk for trk in tracks if trk.is_visible(fi, args.min_hits)]
    frame_persons[fi] = [(trk.id, float(trk.xy[0]), float(trk.xy[1]), float(trk.score)) for trk in visible_tracks]
    frame_trails[fi] = {trk.id: list(trk.trail[-args.trail_length:]) for trk in visible_tracks}

    prev_frame = frame

    if (fi + 1) % 50 == 0 or fi == 0:
        print(f"  帧 {fi+1}/{len(frames)} | det={len(det_pts)} | visible={len(visible_tracks)} | active={len(tracks)}")

if args.save_tracks:
    with open(args.save_tracks, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'track_id', 'x', 'y', 'score'])
        for fi, persons in frame_persons.items():
            for tid, x, y, s in persons:
                writer.writerow([fi, tid, x, y, s])
    print(f"  轨迹结果已保存: {args.save_tracks}")


# ============================================================
# 5. 合成可视化视频
# ============================================================
print("[5/5] 合成视频...")
vis_scale = max(1.0, min(fh, fw) / 1080)
print(f"  图像分辨率: {fw}x{fh}, 可视化缩放: {vis_scale:.2f}x")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(args.output, fourcc, args.fps_out, (fw, fh))

id_colors = {}

for fi, frame in enumerate(frames):
    result = frame.copy()
    persons = frame_persons.get(fi, [])
    trails = frame_trails.get(fi, {})

    # 先画轨迹线
    for tid, trail in trails.items():
        if len(trail) < 2:
            continue
        color = get_color(tid, id_colors)
        for j in range(1, len(trail)):
            pt1 = (int(trail[j - 1][0]), int(trail[j - 1][1]))
            pt2 = (int(trail[j][0]), int(trail[j][1]))
            thick = max(2, int(vis_scale * 3 * j / max(1, len(trail))))
            cv2.line(result, pt1, pt2, color, thick, lineType=cv2.LINE_AA)

    circle_radius = max(4, int(vis_scale * 7))
    font_scale = max(0.55, vis_scale * 0.75)
    text_thickness = max(2, int(vis_scale * 2))
    box_size = max(8, int(vis_scale * 11))

    # 再画当前检测点与ID
    for tid, x, y, score in persons:
        color = get_color(tid, id_colors)
        cx, cy = int(x), int(y)

        cv2.circle(result, (cx, cy), circle_radius, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(result, (cx, cy), circle_radius + 2, (255, 255, 255), 1, lineType=cv2.LINE_AA)

        x1, y1 = max(0, cx - box_size), max(0, cy - box_size)
        x2, y2 = min(fw, cx + box_size), min(fh, cy + box_size)
        cv2.rectangle(result, (x1, y1), (x2, y2), color, max(1, int(vis_scale * 2)), lineType=cv2.LINE_AA)

        label = str(tid)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_thickness)
        label_y1 = max(y1 - th - baseline - 4, 0)
        label_y2 = label_y1 + th + baseline + 4
        cv2.rectangle(result, (x1, label_y1), (x1 + tw + 6, label_y2), color, -1)
        cv2.putText(result, label, (x1 + 3, label_y2 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255),
                    text_thickness, lineType=cv2.LINE_AA)

    info_text = f'Frame {fi+1}/{len(frames)} | Visible: {len(persons)}'
    info_scale = max(0.8, vis_scale * 1.0)
    info_thick = max(2, int(vis_scale * 2))
    (tw, th), _ = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, info_scale, info_thick)
    cv2.rectangle(result, (10, 5), (20 + tw, 15 + th), (0, 0, 0), -1)
    cv2.putText(result, info_text, (18, 12 + th),
                cv2.FONT_HERSHEY_SIMPLEX, info_scale, (0, 255, 255),
                info_thick, lineType=cv2.LINE_AA)

    out.write(result)

out.release()

elapsed_total = time.time() - start_time
print(f"\n完成! 输出: {args.output}")
print(f"共 {len(frames)} 帧，总耗时 {elapsed_total:.1f}s，文件大小: {os.path.getsize(args.output)/1024/1024:.1f} MB")
