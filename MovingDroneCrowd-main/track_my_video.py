"""
对自有视频逐帧用 STEERER 推理 → 人数检测 + 简单位置追踪
与 frame_by_frame_demo.py 推理逻辑完全一致
用法: python3 track_my_video.py --video dataset/13423250_3840_2160_30fps.mp4 --output track_my.mp4
"""
import cv2, os, sys, time, argparse, numpy as np, torch, torch.nn.functional as F
from collections import defaultdict
from torchvision import transforms
from PIL import Image
from mmcv import Config
from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
from skimage.feature import peak_local_max
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

parser = argparse.ArgumentParser()
parser.add_argument('--video', type=str, required=True)
parser.add_argument('--output', type=str, default='track_my_video.mp4')
parser.add_argument('--counter_path', type=str,
                    default='pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth')
parser.add_argument('--max_long', type=int, default=1920)
parser.add_argument('--max_short', type=int, default=1080)
parser.add_argument('--min_distance', type=int, default=10)
parser.add_argument('--threshold_rel', type=float, default=0.15)
parser.add_argument('--max_frames', type=int, default=0)
parser.add_argument('--start_frame', type=int, default=0, help='从第几帧开始（用于断点续跑）')
parser.add_argument('--fps_out', type=int, default=10)
parser.add_argument('--trail_length', type=int, default=10)
parser.add_argument('--gpu', type=str, default='0')
args = parser.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

# ============================================================
# 1. 加载模型（和 frame_by_frame_demo.py 一样）
# ============================================================
print("[1/4] 加载 STEERER 计数器模型...")
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
print(f"[2/4] 视频: {width}x{height}, {fps:.1f}fps, {total_frames}帧")

frames = []
frame_idx = 0
while True:
    ret, frame = cap.read()
    if not ret: break
    if frame_idx >= args.start_frame:
        frames.append(frame)
    frame_idx += 1
    if args.max_frames > 0 and len(frames) >= args.max_frames: break
cap.release()
print(f"  读取 {len(frames)} 帧 (从原始第{args.start_frame}帧开始)")

# ============================================================
# 3. 逐帧 STEERER 推理（和 frame_by_frame_demo.py 完全一致）
# ============================================================
print("[3/4] 逐帧推理...")
start_time = time.time()

all_detections = {}  # frame_idx -> [(x_ori, y_ori), ...] 原始分辨率坐标

for fi, frame in enumerate(frames):
    # --- 预处理：缩放到 max_long x max_short ---
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

    # --- 推理密度图 ---
    with torch.no_grad():
        density_map = global_counter(tensor.cuda())

    # --- 上采样回原尺寸 ---
    den_map = F.interpolate(density_map, size=(th + pad_h, tw + pad_w),
                            mode='bilinear', align_corners=False)[0, 0]
    if pad_h > 0 or pad_w > 0:
        den_map = den_map[:th, :tw]
    den_np = den_map.cpu().numpy()

    # --- 提取峰值 ---
    threshold_abs = den_np.max() * args.threshold_rel
    peaks = peak_local_max(den_np, min_distance=args.min_distance,
                           threshold_abs=threshold_abs)
    peaks_xy = peaks[:, ::-1].astype(np.float32)  # (x,y) in scaled space

    # --- 坐标还原到原始分辨率（关键！）---
    if scale != 1.0:
        peaks_xy = peaks_xy / scale

    all_detections[fi] = peaks_xy

    if (fi + 1) % 50 == 0 or fi == 0:
        elapsed = time.time() - start_time
        fps_infer = (fi + 1) / elapsed if elapsed > 0 else 0
        print(f"  帧 {fi+1}/{len(frames)} | 检测 {len(peaks_xy)} 人 | 速度 {fps_infer:.1f} fps")

elapsed_infer = time.time() - start_time
print(f"  推理完成, 耗时 {elapsed_infer:.1f}s")

# ============================================================
# 4. 简单追踪：帧间位置最近邻匹配
# ============================================================
print("[4/4] 位置追踪 + 合成视频...")

np.random.seed(42)
id_colors = {}
def get_color(pid):
    if pid not in id_colors:
        h = (pid * 0.618033988749895) % 1.0
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.95)
        id_colors[pid] = (int(r*255), int(g*255), int(b*255))
    return id_colors[pid]

# 追踪状态
next_pid = 1
active_tracks = {}       # pid -> (x, y) 当前位置
frame_persons = {}       # fi -> [(pid, x, y)]
trail_history = defaultdict(list)  # pid -> [(x, y), ...]

for fi, detections in all_detections.items():
    if fi == 0:
        # 第一帧：全部分配新 ID
        frame_persons[fi] = []
        for x, y in detections:
            pid = next_pid
            next_pid += 1
            active_tracks[pid] = (x, y)
            frame_persons[fi].append((pid, x, y))
    else:
        # 后续帧：匈牙利匹配
        if len(detections) == 0:
            # 没有检测，保持上一帧状态
            frame_persons[fi] = frame_persons.get(fi-1, [])
            continue

        det_pts = np.array(detections, dtype=np.float32)
        prev_pids = list(active_tracks.keys())
        if len(prev_pids) == 0:
            # 全部新 ID
            frame_persons[fi] = []
            for x, y in detections:
                pid = next_pid
                next_pid += 1
                active_tracks[pid] = (x, y)
                frame_persons[fi].append((pid, x, y))
            continue

        prev_pts = np.array([active_tracks[p] for p in prev_pids], dtype=np.float32)
        cost = cdist(det_pts, prev_pts)  # [n_det, n_prev]
        row_ind, col_ind = linear_sum_assignment(cost)

        matched_prev = set()
        frame_persons[fi] = []

        for r, c in zip(row_ind, col_ind):
            dist = cost[r, c]
            if dist < 80:  # 80 像素以内视为同一个人（4K 分辨率下可调）
                pid = prev_pids[c]
                active_tracks[pid] = (det_pts[r][0], det_pts[r][1])
                frame_persons[fi].append((pid, det_pts[r][0], det_pts[r][1]))
                matched_prev.add(c)

        # 未匹配的检测 → 新 ID
        matched_det = set(row_ind)
        for d in range(len(detections)):
            if d not in matched_det:
                pid = next_pid
                next_pid += 1
                active_tracks[pid] = (det_pts[d][0], det_pts[d][1])
                frame_persons[fi].append((pid, det_pts[d][0], det_pts[d][1]))

        # 未匹配的旧轨迹 → 保留但标记为不活跃（保留几帧后清除）
        for c, pid in enumerate(prev_pids):
            if c not in matched_prev:
                # 保留旧位置
                frame_persons[fi].append((pid, prev_pts[c][0], prev_pts[c][1]))

# ============================================================
# 5. 合成视频（可视化）
# ============================================================
fh, fw = frames[0].shape[:2]
vis_scale = max(1.0, min(fh, fw) / 1080)
print(f"  图像分辨率: {fw}x{fh}, 可视化缩放: {vis_scale:.2f}x")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(args.output, fourcc, args.fps_out, (fw, fh))

for fi, frame in enumerate(frames):
    result = frame.copy()
    persons = frame_persons.get(fi, [])

    # 更新轨迹历史
    for pid, x, y in persons:
        trail_history[pid].append((x, y))
        if len(trail_history[pid]) > args.trail_length:
            trail_history[pid] = trail_history[pid][-args.trail_length:]

    # ---- 画轨迹线 ----
    for pid, trail in trail_history.items():
        if len(trail) < 2:
            continue
        color = get_color(pid)
        for j in range(1, len(trail)):
            pt1 = (int(trail[j-1][0]), int(trail[j-1][1]))
            pt2 = (int(trail[j][0]), int(trail[j][1]))
            thick = max(2, int(vis_scale * 4 * j / len(trail)))
            cv2.line(result, pt1, pt2, color, thick, lineType=cv2.LINE_AA)

    # ---- 画圆点和 ID ----
    circle_radius = max(5, int(vis_scale * 8))
    font_scale = max(0.7, vis_scale * 1.0)
    text_thickness = max(2, int(vis_scale * 2))
    box_size = int(vis_scale * 12)

    for pid, x, y in persons:
        color = get_color(pid)
        cx, cy = int(x), int(y)

        # 实心圆点
        cv2.circle(result, (cx, cy), circle_radius, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(result, (cx, cy), circle_radius + 2, (255, 255, 255), 1, lineType=cv2.LINE_AA)

        # 检测框
        x1, y1 = max(0, cx - box_size), max(0, cy - box_size)
        x2, y2 = min(fw, cx + box_size), min(fh, cy + box_size)
        cv2.rectangle(result, (x1, y1), (x2, y2), color, max(2, int(vis_scale * 2)), lineType=cv2.LINE_AA)

        # ID 标签
        label = str(pid)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_thickness)
        label_y1 = max(y1 - th - baseline - 4, 0)
        label_y2 = label_y1 + th + baseline + 4
        cv2.rectangle(result, (x1, label_y1), (x1 + tw + 6, label_y2), color, -1)
        cv2.putText(result, label, (x1 + 3, label_y2 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), text_thickness, lineType=cv2.LINE_AA)

    # 左上角信息栏
    info_text = f'Frame {fi+1}/{len(frames)} | Tracked: {len(persons)}'
    info_scale = max(1.0, vis_scale * 1.2)
    info_thick = max(2, int(vis_scale * 2))
    (tw, th), _ = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, info_scale, info_thick)
    cv2.rectangle(result, (10, 5), (20 + tw, 15 + th), (0, 0, 0), -1)
    cv2.putText(result, info_text, (18, 12 + th),
                cv2.FONT_HERSHEY_SIMPLEX, info_scale, (0, 255, 255), info_thick, lineType=cv2.LINE_AA)

    out.write(result)

out.release()

elapsed_total = time.time() - start_time
print(f"\n完成! 输出: {args.output}")
print(f"共 {len(frames)} 帧, 总耗时 {elapsed_total:.1f}s, 文件大小: {os.path.getsize(args.output)/1024/1024:.1f} MB")
