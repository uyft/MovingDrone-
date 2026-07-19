"""
改进版轨迹追踪：使用卡尔曼滤波 + IOU匹配 + 外观特征
对自有视频逐帧用 STEERER 推理 → 人数检测 + 稳定追踪

改进点：
1. 卡尔曼滤波预测行人位置，处理遮挡和快速移动
2. IOU + 距离双重匹配，提高匹配准确率
3. 外观特征辅助（颜色直方图），处理人群交叉
4. 轨迹平滑，减少抖动
5. 更美观的可视化

用法: python track_my_video_v2.py --video your_video.mp4 --output track_v2.mp4
"""
import cv2, os, sys, time, argparse, numpy as np, torch, torch.nn.functional as F
from collections import defaultdict, deque
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
parser.add_argument('--max_long', type=int, default=1920)
parser.add_argument('--max_short', type=int, default=1080)
parser.add_argument('--min_distance', type=int, default=8)
parser.add_argument('--threshold_rel', type=float, default=0.12)
parser.add_argument('--max_frames', type=int, default=0)
parser.add_argument('--start_frame', type=int, default=0)
parser.add_argument('--fps_out', type=int, default=10)
parser.add_argument('--trail_length', type=int, default=20)
parser.add_argument('--trail_fade', type=float, default=0.7, help='轨迹线渐变透明度')
parser.add_argument('--gpu', type=str, default='0')
parser.add_argument('--max_age', type=int, default=5, help='轨迹保留的最大帧数')
parser.add_argument('--min_hits', type=int, default=3, help='最小确认帧数')
parser.add_argument('--iou_threshold', type=float, default=0.3, help='IOU匹配阈值')
parser.add_argument('--dist_threshold', type=float, default=100.0, help='距离匹配阈值')
args = parser.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu


# ============================================================
# 卡尔曼滤波器（简化版，用于单点跟踪）
# ============================================================
class KalmanFilter:
    """2D 点跟踪的简化卡尔曼滤波器"""
    def __init__(self, init_pos):
        self.state = np.array([init_pos[0], init_pos[1], 0.0, 0.0], dtype=np.float32)  # [x, y, vx, vy]
        self.P = np.eye(4, dtype=np.float32) * 100  # 协方差
        self.Q = np.eye(4, dtype=np.float32) * 0.1  # 过程噪声
        self.R = np.eye(2, dtype=np.float32) * 10   # 观测噪声
        self.F = np.array([[1, 0, 1, 0],
                           [0, 1, 0, 1],
                           [0, 0, 1, 0],
                           [0, 0, 0, 1]], dtype=np.float32)  # 状态转移
        self.H = np.array([[1, 0, 0, 0],
                           [0, 1, 0, 0]], dtype=np.float32)  # 观测矩阵
        
    def predict(self):
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.state[:2]
    
    def update(self, measurement):
        z = np.array(measurement, dtype=np.float32)
        y = z - self.H @ self.state  # 残差
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)  # 卡尔曼增益
        self.state = self.state + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        return self.state[:2]


# ============================================================
# 轨迹类
# ============================================================
class Track:
    _id_counter = 0
    
    def __init__(self, init_pos, appearance=None):
        Track._id_counter += 1
        self.id = Track._id_counter
        self.kf = KalmanFilter(init_pos)
        self.positions = deque(maxlen=args.trail_length)
        self.positions.append(init_pos)
        self.appearance = appearance  # 外观特征（颜色直方图）
        self.age = 0  # 存活帧数
        self.time_since_update = 0  # 未更新帧数
        self.hits = 1  # 命中次数
        self.confirmed = False
        
    def predict(self):
        pred = self.kf.predict()
        self.time_since_update += 1
        return pred
    
    def update(self, pos, appearance=None):
        self.kf.update(pos)
        self.positions.append(pos)
        self.time_since_update = 0
        self.hits += 1
        if appearance is not None:
            self.appearance = appearance
        if self.hits >= args.min_hits:
            self.confirmed = True
    
    def get_position(self):
        return self.kf.state[:2]
    
    def is_active(self):
        return self.time_since_update <= args.max_age


# ============================================================
# 外观特征提取
# ============================================================
def extract_appearance(frame, pos, box_size=30):
    """提取行人区域的颜色直方图特征"""
    x, y = int(pos[0]), int(pos[1])
    h, w = frame.shape[:2]
    x1, y1 = max(0, x - box_size), max(0, y - box_size)
    x2, y2 = min(w, x + box_size), min(h, y + box_size)
    
    if x2 <= x1 or y2 <= y1:
        return None
    
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    
    # HSV 颜色直方图
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten()


def appearance_similarity(app1, app2):
    """计算外观相似度 (0-1)"""
    if app1 is None or app2 is None:
        return 0.5
    # 巴氏距离
    dist = cv2.compareHist(app1.astype(np.float32), app2.astype(np.float32), cv2.HISTCMP_BHATTACHARYYA)
    return max(0, 1 - dist)


# ============================================================
# 匹配算法
# ============================================================
def compute_iou(box1, box2):
    """计算两个框的IOU，输入为 (x, y, w, h) 中心点格式"""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # 转为左上角右下角
    b1_x1, b1_y1 = x1 - w1/2, y1 - h1/2
    b1_x2, b1_y2 = x1 + w1/2, y1 + h1/2
    b2_x1, b2_y1 = x2 - w2/2, y2 - h2/2
    b2_x2, b2_y2 = x2 + w2/2, y2 + h2/2
    
    # 交集
    xi1, yi1 = max(b1_x1, b2_x1), max(b1_y1, b2_y1)
    xi2, yi2 = min(b1_x2, b2_x2), min(b1_y2, b2_y2)
    
    if xi2 <= xi1 or yi2 <= yi1:
        return 0.0
    
    inter = (xi2 - xi1) * (yi2 - yi1)
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0.0


def match_detections_to_tracks(detections, tracks, frame=None):
    """
    级联匹配：先IOU匹配，再距离+外观匹配
    返回: matches, unmatched_dets, unmatched_tracks
    """
    if len(tracks) == 0:
        return [], list(range(len(detections))), []
    if len(detections) == 0:
        return [], [], list(range(len(tracks)))
    
    # 提取外观特征
    det_appearances = []
    if frame is not None:
        for det in detections:
            det_appearances.append(extract_appearance(frame, det))
    
    # 构建代价矩阵
    cost_matrix = np.zeros((len(detections), len(tracks)), dtype=np.float32)
    
    for i, det in enumerate(detections):
        for j, track in enumerate(tracks):
            # 距离代价
            track_pos = track.get_position()
            dist = np.linalg.norm(det - track_pos)
            dist_cost = min(dist / args.dist_threshold, 1.0)
            
            # IOU代价
            det_box = (det[0], det[1], 40, 40)  # 假设40x40的检测框
            track_box = (track_pos[0], track_pos[1], 40, 40)
            iou = compute_iou(det_box, track_box)
            iou_cost = 1 - iou
            
            # 外观代价
            app_sim = appearance_similarity(det_appearances[i] if i < len(det_appearances) else None, track.appearance)
            app_cost = 1 - app_sim
            
            # 综合代价 (距离权重最高)
            cost_matrix[i, j] = 0.5 * dist_cost + 0.3 * iou_cost + 0.2 * app_cost
    
    # 匈牙利匹配
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    
    matches = []
    unmatched_dets = list(range(len(detections)))
    unmatched_tracks = list(range(len(tracks)))
    
    for r, c in zip(row_ind, col_ind):
        if cost_matrix[r, c] < 0.8:  # 阈值过滤
            matches.append((r, c))
            if r in unmatched_dets:
                unmatched_dets.remove(r)
            if c in unmatched_tracks:
                unmatched_tracks.remove(c)
    
    return matches, unmatched_dets, unmatched_tracks


# ============================================================
# 可视化
# ============================================================
np.random.seed(42)
COLORS = [
    (255, 107, 107), (78, 205, 196), (255, 230, 109), (26, 83, 92),
    (247, 255, 247), (255, 159, 28), (46, 196, 182), (231, 29, 54),
    (255, 203, 242), (12, 202, 74), (255, 170, 0), (0, 150, 199),
    (187, 62, 3), (174, 32, 18), (155, 197, 61), (0, 119, 182),
    (255, 0, 110), (131, 56, 236), (255, 190, 11), (251, 86, 7),
    (58, 134, 255), (6, 214, 160), (255, 140, 66), (118, 200, 147),
    (172, 243, 157), (255, 112, 166), (76, 201, 240), (247, 37, 133),
    (114, 9, 183), (72, 12, 168), (63, 55, 201), (67, 97, 238)
]

def get_color(pid):
    return COLORS[pid % len(COLORS)]


def draw_rounded_rect(img, pt1, pt2, color, thickness=2, radius=5):
    """画圆角矩形"""
    x1, y1 = pt1
    x2, y2 = pt2
    
    # 画四条边
    cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness)
    cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness)
    cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness)
    cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness)
    
    # 画四个角
    cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness)
    cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness)
    cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness)
    cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness)


def draw_trail(img, trail, color, thickness=3):
    """画渐变轨迹线"""
    if len(trail) < 2:
        return
    
    for i in range(1, len(trail)):
        alpha = i / len(trail)
        line_color = tuple(int(c * alpha + 255 * (1 - alpha) * 0.3) for c in color)
        pt1 = (int(trail[i-1][0]), int(trail[i-1][1]))
        pt2 = (int(trail[i][0]), int(trail[i][1]))
        cv2.line(img, pt1, pt2, line_color, thickness, lineType=cv2.LINE_AA)


# ============================================================
# 主程序
# ============================================================
print("=" * 60)
print("轨迹追踪 v2 - 改进版")
print("=" * 60)

# 1. 加载模型
print("[1/4] 加载 STEERER 模型...")
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

# 2. 读取视频
print("[2/4] 读取视频...")
cap = cv2.VideoCapture(args.video)
if not cap.isOpened():
    print(f"无法打开: {args.video}")
    sys.exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"  视频: {width}x{height}, {fps:.1f}fps, {total_frames}帧")

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
print(f"  读取 {len(frames)} 帧")

# 3. 逐帧推理
print("[3/4] 逐帧推理...")
start_time = time.time()

all_detections = {}  # frame_idx -> [(x, y), ...]
all_appearances = {}  # frame_idx -> [appearance, ...]

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

    den_map = F.interpolate(density_map, size=(th + pad_h, tw + pad_w),
                            mode='bilinear', align_corners=False)[0, 0]
    if pad_h > 0 or pad_w > 0:
        den_map = den_map[:th, :tw]
    den_np = den_map.cpu().numpy()

    threshold_abs = den_np.max() * args.threshold_rel
    peaks = peak_local_max(den_np, min_distance=args.min_distance,
                           threshold_abs=threshold_abs)
    peaks_xy = peaks[:, ::-1].astype(np.float32)

    if scale != 1.0:
        peaks_xy = peaks_xy / scale

    # 提取外观特征
    appearances = []
    for peak in peaks_xy:
        app = extract_appearance(frame, peak)
        appearances.append(app)

    all_detections[fi] = peaks_xy
    all_appearances[fi] = appearances

    if (fi + 1) % 50 == 0 or fi == 0:
        elapsed = time.time() - start_time
        fps_infer = (fi + 1) / elapsed if elapsed > 0 else 0
        print(f"  帧 {fi+1}/{len(frames)} | 检测 {len(peaks_xy)} 人 | {fps_infer:.1f} fps")

print(f"  推理完成, 耗时 {time.time() - start_time:.1f}s")

# 4. 追踪
print("[4/4] 追踪 + 合成视频...")
tracks = []
frame_tracks = {}  # fi -> [(track_id, x, y), ...]

for fi in range(len(frames)):
    detections = all_detections[fi]
    appearances = all_appearances[fi]
    frame = frames[fi]

    # 预测所有轨迹
    for track in tracks:
        track.predict()

    # 匹配
    active_tracks = [t for t in tracks if t.is_active()]
    matches, unmatched_dets, unmatched_tracks = match_detections_to_tracks(
        detections, active_tracks, frame
    )

    # 更新匹配的轨迹
    for det_idx, track_idx in matches:
        track = active_tracks[track_idx]
        track.update(detections[det_idx], appearances[det_idx])

    # 未匹配的检测 -> 新轨迹
    for det_idx in unmatched_dets:
        new_track = Track(detections[det_idx], appearances[det_idx])
        tracks.append(new_track)

    # 清理死亡轨迹
    tracks = [t for t in tracks if t.is_active()]

    # 记录当前帧的轨迹
    frame_tracks[fi] = []
    for track in tracks:
        if track.confirmed:
            pos = track.get_position()
            frame_tracks[fi].append((track.id, pos[0], pos[1]))

# 5. 合成视频
fh, fw = frames[0].shape[:2]
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(args.output, fourcc, args.fps_out, (fw, fh))

# 重新组织轨迹历史用于绘制
trail_history = defaultdict(list)
for fi in range(len(frames)):
    for tid, x, y in frame_tracks.get(fi, []):
        trail_history[tid].append((x, y, fi))

# 过滤轨迹，只保留足够长的
min_trail_len = 5
for tid in list(trail_history.keys()):
    if len(trail_history[tid]) < min_trail_len:
        del trail_history[tid]

print(f"  共 {len(trail_history)} 条有效轨迹")

for fi, frame in enumerate(frames):
    result = frame.copy()
    persons = frame_tracks.get(fi, [])

    # 画轨迹线（渐变效果）
    for tid, trail in trail_history.items():
        # 找到当前帧在轨迹中的位置
        current_idx = None
        for i, (x, y, tf) in enumerate(trail):
            if tf == fi:
                current_idx = i
                break
        
        if current_idx is None:
            continue

        # 画历史轨迹（从过去到现在）
        color = get_color(tid)
        start_idx = max(0, current_idx - args.trail_length + 1)
        
        for i in range(start_idx + 1, current_idx + 1):
            pt1 = (int(trail[i-1][0]), int(trail[i-1][1]))
            pt2 = (int(trail[i][0]), int(trail[i][1]))
            # 渐变：越近越亮
            progress = (i - start_idx) / (current_idx - start_idx + 1)
            alpha = 0.3 + 0.7 * progress
            line_color = tuple(int(c * alpha + 50 * (1 - alpha)) for c in color)
            thickness = max(2, int(3 * progress))
            cv2.line(result, pt1, pt2, line_color, thickness, lineType=cv2.LINE_AA)

    # 画检测点和ID
    box_size = 12  # 从 25 缩小到 12
    for tid, x, y in persons:
        color = get_color(tid)
        cx, cy = int(x), int(y)

        # 小圆点（中心）- 缩小
        cv2.circle(result, (cx, cy), 4, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(result, (cx, cy), 5, (255, 255, 255), 1, lineType=cv2.LINE_AA)

        # 小方框 - 缩小
        x1, y1 = max(0, cx - box_size), max(0, cy - box_size)
        x2, y2 = min(fw, cx + box_size), min(fh, cy + box_size)
        cv2.rectangle(result, (x1, y1), (x2, y2), color, 1, lineType=cv2.LINE_AA)

        # ID 标签（紧凑背景）
        label = str(tid)
        font_scale = 0.5
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        
        # 标签放在框的右上方，紧凑布局
        label_x1 = cx + 8
        label_y1 = cy - 8
        label_x2 = label_x1 + tw + 4
        label_y2 = label_y1 + th + 3
        
        # 标签背景 - 半透明黑色
        overlay = result.copy()
        cv2.rectangle(overlay, (label_x1, label_y1), (label_x2, label_y2), color, -1)
        cv2.addWeighted(overlay, 0.9, result, 0.1, 0, result)
        cv2.putText(result, label, (label_x1 + 2, label_y2 - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, lineType=cv2.LINE_AA)

    # 信息栏
    info_text = f'Frame {fi+1}/{len(frames)} | Active: {len(persons)} | Trails: {len(trail_history)}'
    cv2.rectangle(result, (10, 10), (350, 45), (0, 0, 0), -1)
    cv2.putText(result, info_text, (20, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, lineType=cv2.LINE_AA)

    out.write(result)

out.release()

elapsed_total = time.time() - start_time
print(f"\n完成! 输出: {args.output}")
print(f"共 {len(frames)} 帧, 总耗时 {elapsed_total:.1f}s")
print(f"文件大小: {os.path.getsize(args.output)/1024/1024:.1f} MB")
