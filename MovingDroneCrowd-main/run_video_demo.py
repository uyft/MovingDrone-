#!/usr/bin/env python3
"""从数据集帧序列合成视频 → 跑 video_demo 推理"""
import cv2
import os
import sys
import subprocess

scene = "scene_1"
clip = "1"
frame_dir = f"MovingDroneCrowd++/frames/{scene}/{clip}"
video_path = f"dataset/{scene}_{clip}.mp4"
output_path = f"dataset/{scene}_{clip}_result.mp4"

# Step 1: 帧序列 → 视频
print(f"[1/2] 合成视频: {video_path}")
imgs = sorted([f for f in os.listdir(frame_dir) if f.endswith(('.jpg', '.png'))])
if not imgs:
    print(f"错误: {frame_dir} 下没有图片")
    sys.exit(1)

first = cv2.imread(os.path.join(frame_dir, imgs[0]))
h, w = first.shape[:2]
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter(video_path, fourcc, 10, (w, h))  # 10fps

for img_name in imgs:
    img = cv2.imread(os.path.join(frame_dir, img_name))
    writer.write(img)
writer.release()
print(f"  合成完成: {video_path} ({len(imgs)} 帧, {w}x{h})")

# Step 2: 跑 video_demo
print(f"\n[2/2] 运行 video_demo...")
cmd = [
    "python", "video_demo.py",
    "--video", video_path,
    "--output", output_path,
    "--interval", "4"
]
subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
print(f"\n✅ 完成！结果视频: {output_path}")
