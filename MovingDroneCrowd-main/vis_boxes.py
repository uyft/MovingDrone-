"""
基于 MovingDroneCrowd++ 数据集 GT 标注 / DVTracker 预测结果生成带框+ID 的可视化图片
用法:
  # 可视化 GT 标注
  python vis_boxes.py --mode gt
  
  # 可视化 DVTracker 预测结果
  python vis_boxes.py --mode pred --pred_root test_results/MovingDroneCrowd/gd3a_vgg16_test_4_STEERER_ep_201_best_model
"""
import cv2
import os
import numpy as np
from collections import defaultdict
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str, default='MovingDroneCrowd++')
parser.add_argument('--split', type=str, default='test.txt')
parser.add_argument('--output', type=str, default='vis_boxes')
parser.add_argument('--max_scenes', type=int, default=5, help='最多处理几个场景')
parser.add_argument('--max_frames', type=int, default=30, help='每个场景最多几帧')
parser.add_argument('--mode', type=str, default='gt', choices=['gt', 'pred'],
                    help='gt=可视化GT标注, pred=可视化DVTracker预测结果')
parser.add_argument('--pred_root', type=str, default='test_results/MovingDroneCrowd/gd3a_vgg16_test_4_STEERER_ep_201_best_model',
                    help='DVTracker 预测结果目录')
args = parser.parse_args()

DATA_ROOT = args.dataset
FRAMES_DIR = os.path.join(DATA_ROOT, 'frames')
ANNO_DIR = os.path.join(DATA_ROOT, 'annotations')
OUTPUT_DIR = args.output
MODE = args.mode
PRED_ROOT = args.pred_root

# 读取测试场景列表
with open(args.split, 'r') as f:
    scenes = [line.strip() for line in f if line.strip()]
print(f"模式: {MODE.upper()} | 共 {len(scenes)} 个场景，处理前 {min(args.max_scenes, len(scenes))} 个")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def plot_boxes(img, boxes, ids, points=None):
    """在图像上绘制框和ID数字"""
    result = img.copy()
    for i, (box, pid) in enumerate(zip(boxes, ids)):
        x, y, w, h = [int(v) for v in box]
        # 绿色矩形框
        cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # 黄色ID数字
        cx, cy = x + w // 2, y
        cv2.putText(result, str(int(pid)), (cx - 10, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    if points is not None:
        for p in points:
            px, py = int(p[0]), int(p[1])
            cv2.circle(result, (px, py), 2, (0, 0, 255), 2)
    return result


def make_filmstrip(vis_frames, cols=5):
    """
    将多张可视化帧拼接成胶卷风格大图
    """
    if not vis_frames:
        return None
    # 统一缩放到固定大小
    h, w = 300, 400
    resized = [cv2.resize(f, (w, h)) for f in vis_frames]
    # 补齐到 cols 的倍数
    while len(resized) % cols != 0:
        resized.append(np.zeros_like(resized[0]))
    rows = len(resized) // cols
    row_imgs = []
    for r in range(rows):
        row_imgs.append(np.hstack(resized[r * cols:(r + 1) * cols]))
    filmstrip = np.vstack(row_imgs)
    
    # 添加胶卷边框（上下黑条 + 白色齿孔）
    fh, fw = filmstrip.shape[:2]
    border_h = 20
    bordered = np.zeros((fh + 2 * border_h, fw + 10, 3), dtype=np.uint8)
    bordered[border_h:border_h + fh, 5:5 + fw] = filmstrip
    # 白色齿孔
    tooth_w = 30
    for i in range(0, fw - tooth_w // 2, tooth_w * 2):
        bordered[0:border_h, 5 + i:5 + i + tooth_w] = 255
        bordered[border_h + fh:, 5 + i:5 + i + tooth_w] = 255
    
    return bordered


def draw_zoom_in(img, boxes, ids, zoom_scale=3.0, roi_ratio=0.25):
    """
    在主图上画红虚线ROI框，右侧拼接放大的局部区域
    返回: [主图(带红虚线框) | 放大图] 拼接后的图像
    """
    if not boxes:
        return img.copy()
    
    img_h, img_w = img.shape[:2]
    
    # 找到所有框的中心，计算密集区域的中心作为 ROI 中心
    centers = []
    for box in boxes:
        x, y, w, h = [int(v) for v in box]
        cx = x + w // 2
        cy = y + h // 2
        centers.append((cx, cy))
    
    if not centers:
        return img.copy()
    
    # ROI 中心 = 所有框中心的几何平均
    mean_cx = int(np.mean([c[0] for c in centers]))
    mean_cy = int(np.mean([c[1] for c in centers]))
    
    # ROI 大小基于图像尺寸的比例
    roi_w = min(int(img_w * roi_ratio), 400)
    roi_h = min(int(img_h * roi_ratio), 300)
    
    # 确保中心在图像范围内
    x1 = max(0, mean_cx - roi_w // 2)
    y1 = max(0, mean_cy - roi_h // 2)
    x2 = min(img_w, x1 + roi_w)
    y2 = min(img_h, y1 + roi_h)
    # 如果边界被裁剪了，调整另一侧
    if x2 - x1 < roi_w:
        x1 = max(0, x2 - roi_w)
    if y2 - y1 < roi_h:
        y1 = max(0, y2 - roi_h)
    
    # 绘制主图：先画绿框+ID，再画红虚线 ROI 框
    result = plot_boxes(img, boxes, ids)
    
    # 红色虚线 ROI 框
    dash_len = 15
    gap_len = 10
    def draw_dashed_rect(img, pt1, pt2, color, thickness, dash, gap):
        x1_, y1_ = pt1
        x2_, y2_ = pt2
        # 上边
        for x in range(x1_, x2_, dash + gap):
            e = min(x + dash, x2_)
            cv2.line(img, (x, y1_), (e, y1_), color, thickness)
        # 下边
        for x in range(x1_, x2_, dash + gap):
            e = min(x + dash, x2_)
            cv2.line(img, (x, y2_), (e, y2_), color, thickness)
        # 左边
        for y in range(y1_, y2_, dash + gap):
            e = min(y + dash, y2_)
            cv2.line(img, (x1_, y), (x1_, e), color, thickness)
        # 右边
        for y in range(y1_, y2_, dash + gap):
            e = min(y + dash, y2_)
            cv2.line(img, (x2_, y), (x2_, e), color, thickness)
    
    draw_dashed_rect(result, (x1, y1), (x2, y2), (0, 0, 255), 2, dash_len, gap_len)
    
    # 连接线（从 ROI 到放大图的视觉引导）
    line_x_start = x2
    line_y_mid = (y1 + y2) // 2
    
    # 裁剪并放大 ROI 区域
    roi_crop = result[y1:y2, x1:x2]
    zoomed = cv2.resize(roi_crop, None, fx=zoom_scale, fy=zoom_scale,
                        interpolation=cv2.INTER_LANCZOS4)
    
    # 在放大图上重新绘制框和 ID（因为原图上的框在缩小后看不清）
    zh, zw = zoomed.shape[:2]
    scale_x = zw / (x2 - x1)
    scale_y = zh / (y2 - y1)
    for box, pid in zip(boxes, ids):
        bx, by, bw, bh = [int(v) for v in box]
        # 判断框是否与 ROI 有重叠
        bx2, by2 = bx + bw, by + bh
        overlap_x = max(0, min(bx2, x2) - max(bx, x1))
        overlap_y = max(0, min(by2, y2) - max(by, y1))
        if overlap_x > 5 and overlap_y > 5:
            # 将坐标映射到放大图
            zx1 = max(0, int((bx - x1) * scale_x))
            zy1 = max(0, int((by - y1) * scale_y))
            zx2 = min(zw, int((bx2 - x1) * scale_x))
            zy2 = min(zh, int((by2 - y1) * scale_y))
            if zx2 > zx1 and zy2 > zy1:
                cv2.rectangle(zoomed, (zx1, zy1), (zx2, zy2), (0, 255, 0), 2)
                cx_z = (zx1 + zx2) // 2
                cv2.putText(zoomed, str(int(pid)), (cx_z - 10, zy1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # 给放大图加白色/浅灰色边框
    pad = 6
    zoomed_padded = cv2.copyMakeBorder(zoomed, pad, pad, pad, pad,
                                        cv2.BORDER_CONSTANT, value=(220, 220, 220))
    
    # 调整放大图高度与主图一致（居中对齐）
    zh_p, zw_p = zoomed_padded.shape[:2]
    target_h = img_h
    if zh_p < target_h:
        top_pad = (target_h - zh_p) // 2
        bottom_pad = target_h - zh_p - top_pad
        zoomed_padded = cv2.copyMakeBorder(zoomed_padded, top_pad, bottom_pad, 0, 0,
                                            cv2.BORDER_CONSTANT, value=(40, 40, 40))
    elif zh_p > target_h:
        crop_top = (zh_p - target_h) // 2
        zoomed_padded = zoomed_padded[crop_top:crop_top + target_h, :]
    
    # 拼接主图 + 放大图
    combined = np.hstack([result, zoomed_padded])
    
    return combined


for scene_line in scenes[:args.max_scenes]:
    scene_parts = scene_line.split('/')
    scene_name = scene_parts[0]
    sub_name = scene_parts[1] if len(scene_parts) > 1 else '1'

    frame_dir = os.path.join(FRAMES_DIR, scene_name, sub_name)

    if MODE == 'gt':
        # --- GT 模式：从数据集读取标注 ---
        anno_path = os.path.join(ANNO_DIR, scene_name, f'{sub_name}.csv')
        if not os.path.exists(anno_path):
            print(f"跳过 {scene_line}: GT标注文件不存在")
            continue
        annotations = defaultdict(list)
        with open(anno_path, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 6:
                    continue
                frame_id = int(parts[0])
                person_id = float(parts[1])
                x, y, w, h = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
                annotations[frame_id].append((x, y, w, h, person_id))
    else:
        # --- PRED 模式：从 DVTracker 预测结果读取 ---
        pred_path = os.path.join(PRED_ROOT, scene_name, f'{sub_name}.txt')
        if not os.path.exists(pred_path):
            print(f"跳过 {scene_line}: 预测文件不存在 ({pred_path})")
            continue
        annotations = defaultdict(list)
        with open(pred_path, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 6:
                    continue
                frame_id = int(parts[0])
                person_id = int(parts[1])
                x, y, w, h = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
                annotations[frame_id].append((x, y, w, h, person_id))

    # 读取帧图像
    if not os.path.exists(frame_dir):
        print(f"跳过 {scene_line}: 帧目录不存在 ({frame_dir})")
        continue
    all_frames = sorted([f for f in os.listdir(frame_dir) if f.endswith('.jpg')],
                        key=lambda x: int(x.replace('.jpg', '')))

    scene_out = os.path.join(OUTPUT_DIR, f'{MODE}_{scene_name}_{sub_name}')
    os.makedirs(scene_out, exist_ok=True)

    vis_frames = []
    count = 0

    # DVTracker 预测结果帧号从 1 开始，图片文件名也从 1 开始
    # GT 标注帧号从 0 开始，图片文件名从 1 开始
    frame_offset = 0 if MODE == 'pred' else -1
    
    for frame_file in all_frames[:args.max_frames]:
        img_frame_id = int(frame_file.replace('.jpg', ''))
        anno_frame_id = img_frame_id + frame_offset  # pred: 帧号一致; gt: 图片帧号 = CSV帧号 + 1
        img_path = os.path.join(frame_dir, frame_file)
        img = cv2.imread(img_path)
        if img is None:
            continue

        if anno_frame_id in annotations:
            anns = annotations[anno_frame_id]
            boxes = [(a[0], a[1], a[2], a[3]) for a in anns]
            ids = [a[4] for a in anns]
            points = [(a[0] + a[2] / 2, a[1] + a[3] / 2) for a in anns]
        else:
            boxes, ids, points = [], [], []

        # 左上角添加帧号和人数
        h, w = img.shape[:2]
        label_text = f'{MODE.upper()} Frame {img_frame_id} | Count: {len(ids)}'
        cv2.putText(img, label_text,
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

        vis = plot_boxes(img, boxes, ids, points)
        
        # 生成带局部放大的版本
        vis_zoom = draw_zoom_in(img, boxes, ids, zoom_scale=3.0, roi_ratio=0.28)
        cv2.imwrite(os.path.join(scene_out, f'{img_frame_id:04d}_vis.jpg'), vis)
        cv2.imwrite(os.path.join(scene_out, f'{img_frame_id:04d}_zoom.jpg'), vis_zoom)
        
        vis_frames.append(vis)
        count += 1

    # 生成胶卷拼接大图
    if len(vis_frames) >= 5:
        strip = make_filmstrip(vis_frames, cols=5)
        if strip is not None:
            cv2.imwrite(os.path.join(scene_out, f'filmstrip.jpg'), strip)
            print(f"  -> 胶卷大图已保存: {scene_out}/filmstrip.jpg")

    print(f"已处理 {scene_name}/{sub_name}: {count} 帧 -> {scene_out}")

print(f"\n全部完成！结果保存在 {OUTPUT_DIR}/")
