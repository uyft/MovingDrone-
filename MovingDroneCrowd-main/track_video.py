"""
将 DVTracker 追踪结果合成带轨迹线的视频
用法:
  python3 track_video.py --pred_root test_results/MovingDroneCrowd/gd3a_vgg16_test_4_STEERER_ep_201_best_model --scene scene_1/1
"""
import cv2
import os
import numpy as np
from collections import defaultdict
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--pred_root', type=str, 
                    default='test_results/MovingDroneCrowd/gd3a_vgg16_test_4_STEERER_ep_201_best_model')
parser.add_argument('--dataset', type=str, default='MovingDroneCrowd++')
parser.add_argument('--scene', type=str, default='scene_1/1', help='场景名，如 scene_1/1')
parser.add_argument('--output', type=str, default='track_video.mp4')
parser.add_argument('--max_frames', type=int, default=0, help='最多处理帧数，0=全部')
parser.add_argument('--trail_length', type=int, default=10, help='轨迹线保留帧数')
parser.add_argument('--fps', type=int, default=10, help='输出视频帧率')
parser.add_argument('--box_size', type=int, default=6, help='框大小')
args = parser.parse_args()

# 解析场景名
scene_parts = args.scene.split('/')
scene_name = scene_parts[0]
sub_name = scene_parts[1] if len(scene_parts) > 1 else '1'

# 读取预测结果
pred_path = os.path.join(args.pred_root, scene_name, f'{sub_name}.txt')
if not os.path.exists(pred_path):
    print(f"错误: 预测文件不存在 {pred_path}")
    exit(1)

print(f"读取追踪结果: {pred_path}")
track_data = defaultdict(list)
with open(pred_path, 'r') as f:
    for line in f:
        parts = line.strip().split(',')
        if len(parts) < 6:
            continue
        frame_id = int(parts[0])
        person_id = int(parts[1])
        x, y, w, h = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
        cx, cy = x + w / 2, y + h / 2
        track_data[frame_id].append((person_id, x, y, w, h, cx, cy))

# 读取帧图像
FRAMES_DIR = os.path.join(args.dataset, 'frames', scene_name, sub_name)
if not os.path.exists(FRAMES_DIR):
    print(f"错误: 帧目录不存在 {FRAMES_DIR}")
    exit(1)

all_frames = sorted([f for f in os.listdir(FRAMES_DIR) if f.endswith('.jpg')],
                    key=lambda x: int(x.replace('.jpg', '')))

if args.max_frames > 0:
    all_frames = all_frames[:args.max_frames]

print(f"共 {len(all_frames)} 帧图像, 追踪到 {len(set(t[0] for frm in track_data.values() for t in frm))} 个不同 ID")

# 颜色映射：为每个 ID 分配稳定颜色
np.random.seed(42)
id_colors = {}

def get_color(pid):
    if pid not in id_colors:
        id_colors[pid] = tuple(np.random.randint(50, 255, 3).tolist())
    return id_colors[pid]

# 构建轨迹历史
trail_history = defaultdict(list)  # pid -> [(cx, cy), ...] 按时间排序

# 初始化 VideoWriter
first_img_path = os.path.join(FRAMES_DIR, all_frames[0])
first_img = cv2.imread(first_img_path)
if first_img is None:
    print(f"错误: 无法读取第一帧 {first_img_path}")
    exit(1)
h, w = first_img.shape[:2]

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(args.output, fourcc, args.fps, (w, h))
print(f"输出视频: {args.output} ({w}x{h}, {args.fps}fps)")

# 逐帧绘制
for frame_file in all_frames:
    img_frame_id = int(frame_file.replace('.jpg', ''))
    img_path = os.path.join(FRAMES_DIR, frame_file)
    img = cv2.imread(img_path)
    if img is None:
        continue

    result = img.copy()
    persons = track_data.get(img_frame_id, [])

    # 更新轨迹历史
    for pid, x, y, bw, bh, cx, cy in persons:
        trail_history[pid].append((cx, cy))
        # 只保留最近 N 帧
        if len(trail_history[pid]) > args.trail_length:
            trail_history[pid] = trail_history[pid][-args.trail_length:]

    # 绘制轨迹线（先画线，再画框，这样框在最上层）
    for pid, trail in trail_history.items():
        if len(trail) < 2:
            continue
        color = get_color(pid)
        for i in range(1, len(trail)):
            pt1 = (int(trail[i-1][0]), int(trail[i-1][1]))
            pt2 = (int(trail[i][0]), int(trail[i][1]))
            # 越近的轨迹线越粗、越不透明
            alpha = 0.3 + 0.7 * (i / len(trail))
            thickness = max(1, int(3 * i / len(trail)))
            cv2.line(result, pt1, pt2, color, thickness)

    # 绘制当前帧的检测框和 ID
    for pid, x, y, bw, bh, cx, cy in persons:
        color = get_color(pid)
        x1, y1 = int(x), int(y)
        x2, y2 = int(x + bw), int(y + bh)
        
        # 实心圆点标记中心
        cv2.circle(result, (int(cx), int(cy)), 4, color, -1)
        # 矩形框
        cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
        # ID 标签
        cv2.putText(result, str(pid), (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

    # 帧号和人数
    cv2.putText(result, f'Frame {img_frame_id} | Tracked: {len(persons)}',
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    out.write(result)

out.release()
print(f"\n完成！视频保存在: {args.output}")
print(f"文件大小: {os.path.getsize(args.output) / 1024 / 1024:.1f} MB")
