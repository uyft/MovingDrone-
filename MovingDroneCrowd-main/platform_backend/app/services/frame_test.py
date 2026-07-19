"""
自定义帧测试服务 —— 支持用户上传一组帧图片 + 标签 CSV，
使用 GD3A 时序模型做推理，返回每帧的多张独立密度图。

对齐 test.py 的 save_test_visual 逻辑，但每张图单独保存：
- 1 张原图 + 10 张密度图 = 11 张/帧
- 密度图：GT Global / Pre Global / GT Shared(Prev) / Pre Shared(Prev) /
           GT IN / Pre IN / GT Shared(Next) / Pre Shared(Next) / GT OUT / Pre OUT

输出: 每帧独立 JPG + 汇总 JSON
"""
import os
import sys
import csv
import json
import time
import uuid
import threading
import cv2
import numpy as np
from copy import deepcopy
from typing import List, Dict, Tuple

from app.config import UPLOAD_DIR, RESULT_DIR, ALGORITHM_PATH

# ============================================================
#  基础配置
# ============================================================
FRAME_TEST_DIR = os.path.join(UPLOAD_DIR, "frame_tests")
FRAME_TEST_RESULT_DIR = os.path.join(RESULT_DIR, "frame_tests")
os.makedirs(FRAME_TEST_DIR, exist_ok=True)
os.makedirs(FRAME_TEST_RESULT_DIR, exist_ok=True)

# GD3A 模型权重路径
GD3A_MODEL_PATH = os.path.join(ALGORITHM_PATH, "pretrained", "GD3A_MDC++_best_model_VGG16.pth")
GD3A_COUNTER_PATH = os.path.join(ALGORITHM_PATH, "pretrained",
    "GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth")

# 全局模型缓存
_gd3a_model = None
_gd3a_counter = None
_gd3a_cfg_data = None
_gd3a_model_lock = threading.Lock()

# ============================================================
#  任务缓存
# ============================================================
_frame_test_task_cache: Dict[str, dict] = {}
_frame_test_result_cache: Dict[str, dict] = {}


# ============================================================
#  Task CRUD
# ============================================================
def create_frame_test_task() -> str:
    task_id = f"ft_{uuid.uuid4().hex[:8]}"
    _frame_test_task_cache[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "等待上传数据",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_frames": 0,
        "frame_files": [],
        "steps": [
            {"name": "加载模型", "status": "pending"},
            {"name": "STEERER 全局密度估计", "status": "pending"},
            {"name": "GD3A 时序推理", "status": "pending"},
            {"name": "生成密度图", "status": "pending"},
        ],
    }
    return task_id


def get_frame_test_task_status(task_id: str):
    return _frame_test_task_cache.get(task_id)


def get_frame_test_task_result(task_id: str):
    return _frame_test_result_cache.get(task_id)


def list_frame_test_tasks():
    return sorted(
        list(_frame_test_task_cache.values()),
        key=lambda t: t.get("created_at", ""), reverse=True,
    )


def save_frame_test_data(task_id: str, frame_files: List[Tuple[str, bytes]],
                         label_content: bytes) -> str:
    task_dir = os.path.join(FRAME_TEST_DIR, task_id)
    frames_dir = os.path.join(task_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 保存标签 CSV
    label_path = os.path.join(task_dir, "labels.csv")
    with open(label_path, "wb") as f:
        f.write(label_content)

    # 保存帧图片
    saved_files = []
    for filename, content in frame_files:
        base = os.path.splitext(filename)[0]
        if not base.isdigit():
            base = str(len(saved_files) + 1)
        save_name = f"{int(base)}.jpg"
        save_path = os.path.join(frames_dir, save_name)
        with open(save_path, "wb") as f:
            f.write(content)
        saved_files.append(save_name)

    saved_files = sorted(saved_files, key=lambda n: int(os.path.splitext(n)[0]))

    task = _frame_test_task_cache.get(task_id)
    if task:
        task["frame_files"] = saved_files
        task["total_frames"] = len(saved_files)
        task["message"] = f"已上传 {len(saved_files)} 帧，等待分析"

    return task_dir


# ============================================================
#  标签解析
# ============================================================
def parse_labels(label_path: str) -> Dict[int, dict]:
    labels: Dict[int, dict] = {}
    if not os.path.exists(label_path):
        return labels

    import pandas as pd
    try:
        df = pd.read_csv(label_path, header=None)
    except Exception:
        return labels

    # 自动检测表头
    header_keywords = {"frame", "frame_id", "frame_idx", "idx", "image",
                       "count", "gt_count", "num", "number", "total",
                       "person_id", "id", "pid", "x", "cx", "center_x",
                       "y", "cy", "center_y", "w", "width", "h", "height"}
    first_row = [str(v).strip().lower() for v in df.iloc[0].tolist()]
    has_header = any(v in header_keywords for v in first_row)

    if has_header:
        df = pd.read_csv(label_path)
        col_map = {}
        for c in df.columns:
            key = str(c).strip().lower()
            if key in ("frame", "frame_id", "frame_idx", "idx", "image"):
                col_map["frame"] = c
            elif key in ("count", "gt_count", "num", "number", "total"):
                col_map["count"] = c
            elif key in ("person_id", "id", "pid"):
                col_map["person_id"] = c
            elif key in ("x", "cx", "center_x"):
                col_map["x"] = c
            elif key in ("y", "cy", "center_y"):
                col_map["y"] = c
            elif key in ("w", "width"):
                col_map["w"] = c
            elif key in ("h", "height"):
                col_map["h"] = c
        if col_map:
            df = df.rename(columns={v: k for k, v in col_map.items()})
    else:
        if len(df.columns) >= 6:
            df.columns = ["frame", "person_id", "x", "y", "w", "h"] + \
                         [f"c{i}" for i in range(len(df.columns) - 6)]
        elif len(df.columns) >= 2:
            df.columns = ["frame", "count"] + \
                         [f"c{i}" for i in range(len(df.columns) - 2)]
        else:
            return labels

    for _, row in df.iterrows():
        try:
            frame_idx = int(row.get("frame", row.iloc[0]))
        except Exception:
            continue
        if frame_idx not in labels:
            labels[frame_idx] = {"count": 0, "persons": []}
        if "count" in df.columns:
            try:
                labels[frame_idx]["count"] = int(float(row["count"]))
            except Exception:
                pass
        if all(c in df.columns for c in ("x", "y")):
            try:
                x, y = float(row["x"]), float(row["y"])
                w = float(row.get("w", 10)) if "w" in df.columns else 10
                h = float(row.get("h", 10)) if "h" in df.columns else 10
                labels[frame_idx]["persons"].append({"x": x, "y": y, "w": w, "h": h})
            except Exception:
                pass

    # 如果 frame 从 0 开始，偏移到 1
    all_frames = [int(k) for k in labels.keys()]
    if all_frames and min(all_frames) == 0:
        labels = {k + 1: v for k, v in labels.items()}

    for data in labels.values():
        if data["count"] == 0 and data["persons"]:
            data["count"] = len(data["persons"])

    return labels


# ============================================================
#  GD3A 模型加载（全局单例，对齐 test.py）
# ============================================================
def _load_gd3a_model():
    global _gd3a_model, _gd3a_counter, _gd3a_cfg_data

    with _gd3a_model_lock:
        if _gd3a_model is not None:
            return _gd3a_model, _gd3a_counter, _gd3a_cfg_data

        if ALGORITHM_PATH not in sys.path:
            sys.path.insert(0, ALGORITHM_PATH)

        import torch
        from config import cfg
        from cusdatasets.setting import MovingDroneCrowd
        from model.VIC import Video_Counter
        from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
        from mmcv import Config

        cfg.MODEL = "GD3A"
        cfg.encoder = "VGG16_FPN"
        cfg_data = MovingDroneCrowd.cfg_data

        # GD3A 主模型
        model = Video_Counter(cfg, cfg_data)
        state_dict = torch.load(GD3A_MODEL_PATH, map_location='cpu')
        clean = {}
        for k, v in state_dict.items():
            clean[k[7:] if k.startswith("module.") else k] = v
        model.load_state_dict(clean, strict=True)
        model.eval()

        # STEERER counter
        counter_cfg = Config.fromfile(
            os.path.join(ALGORITHM_PATH, "model/density_estimator/STEERER/configs/MDC.py"))
        counter = STEERER(counter_cfg.network, counter_cfg.dataset.den_factor,
                          counter_cfg.train.route_size)
        ckpt = torch.load(GD3A_COUNTER_PATH, map_location='cpu')
        clean_ckpt = {}
        for k, v in ckpt.items():
            clean_ckpt[k[7:] if k.startswith("module.") else k] = v
        counter.load_state_dict(clean_ckpt, strict=True)
        counter.eval()

        _gd3a_model = model
        _gd3a_counter = counter
        _gd3a_cfg_data = cfg_data
        return model, counter, cfg_data


# ============================================================
#  密度图可视化工具（对齐 misc/utils.py 的 change2map / show_visual_count）
# ============================================================
def _change2map(den_np):
    """密度图 numpy → JET 热力图 BGR"""
    den_np = den_np.squeeze()
    vmin, vmax = den_np.min(), den_np.max()
    if vmax - vmin < 1e-5:
        vis = (den_np * 0).astype(np.uint8)
    else:
        vis = ((den_np - vmin) / (vmax - vmin) * 255).astype(np.uint8)
    return cv2.applyColorMap(vis, cv2.COLORMAP_JET)


def _show_visual_count(vis_map, count_val, text):
    """在密度图上叠加计数文本"""
    txt = f"{text} {int(count_val)}"
    font = cv2.FONT_HERSHEY_TRIPLEX
    pos = (50, 150)
    cv2.putText(vis_map, txt, pos, font, 4, (0, 0, 0), 10, cv2.LINE_AA)
    cv2.putText(vis_map, txt, pos, font, 4, (255, 255, 255), 5, cv2.LINE_AA)
    return vis_map


def _save_single_density_map(den_np, prefix, label, count_val, result_dir,
                             frame_idx, jpeg_quality=90):
    """保存单张密度图为 JPG"""
    vis = _change2map(den_np)
    vis = _show_visual_count(vis, count_val, f"{prefix} {label}")
    fname = f"frame_{frame_idx:06d}_{prefix.lower()}_{label.lower().replace(' ','_').replace('(','').replace(')','')}.jpg"
    cv2.imwrite(os.path.join(result_dir, fname), vis,
                [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    return fname, float(den_np.sum())


# ============================================================
#  预处理（对齐 cusdatasets 的 test_transform）
# ============================================================
def _preprocess_frame(frame_bgr):
    """缩放 + Normalize，对齐 cusdatasets test_transform"""
    import torch
    from PIL import Image

    img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(img_rgb)
    w, h = pil.size

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

    return torch.from_numpy(arr).unsqueeze(0), (w, h)  # (1,3,H,W), (W,H)


# ============================================================
#  GT 密度图构建
# ============================================================
def _build_gt_density_map(persons, den_h, den_w, orig_w, orig_h, sigma=4):
    dot = np.zeros((den_h, den_w), dtype=np.float32)
    sx, sy = den_w / orig_w, den_h / orig_h
    for p in persons:
        px = min(max(int(p["x"] * sx), 0), den_w - 1)
        py = min(max(int(p["y"] * sy), 0), den_h - 1)
        dot[py, px] = 1.0
    if dot.sum() > 0:
        ksize = int(sigma * 6 + 1) | 1
        return cv2.GaussianBlur(dot, (ksize, ksize), sigmaX=sigma)
    return dot


def _build_gt_share_inout(persons, next_persons, den_h, den_w, orig_w, orig_h,
                          dist_thresh=30, sigma=4):
    """构建 GT Shared / IN-OUT 密度图"""
    share_dot = np.zeros((den_h, den_w), dtype=np.float32)
    inout_dot = np.zeros((den_h, den_w), dtype=np.float32)
    sx, sy = den_w / orig_w, den_h / orig_h

    if len(persons) == 0:
        return share_dot, inout_dot

    px_arr = np.array([min(max(int(p["x"] * sx), 0), den_w - 1) for p in persons], dtype=np.int32)
    py_arr = np.array([min(max(int(p["y"] * sy), 0), den_h - 1) for p in persons], dtype=np.int32)

    if len(next_persons) == 0:
        inout_dot[py_arr, px_arr] = 1.0
    else:
        npx = np.array([min(max(int(p["x"] * sx), 0), den_w - 1) for p in next_persons], dtype=np.int32)
        npy = np.array([min(max(int(p["y"] * sy), 0), den_h - 1) for p in next_persons], dtype=np.int32)
        is_shared = np.zeros(len(persons), dtype=bool)
        for i in range(len(persons)):
            d = np.sqrt((px_arr[i] - npx) ** 2 + (py_arr[i] - npy) ** 2)
            if d.min() < dist_thresh:
                is_shared[i] = True
        share_dot[py_arr[is_shared], px_arr[is_shared]] = 1.0
        inout_dot[py_arr[~is_shared], px_arr[~is_shared]] = 1.0

    ksize = int(sigma * 6 + 1) | 1
    sm = cv2.GaussianBlur(share_dot, (ksize, ksize), sigmaX=sigma) if share_dot.sum() > 0 else share_dot
    io = cv2.GaussianBlur(inout_dot, (ksize, ksize), sigmaX=sigma) if inout_dot.sum() > 0 else inout_dot
    return sm, io


# ============================================================
#  核心推理函数（对齐 test.py 的 test() 函数逻辑）
# ============================================================
def run_frame_test(task_id: str, task_dir: str, model_mode: str = "GD3A"):
    """
    对上传的帧进行 GD3A 推理，逐帧生成独立密度图。

    对齐 test.py 的 test() 逻辑：
    1. 加载 GD3A + STEERER counter
    2. 逐帧预处理
    3. model(img, label, global_counter) 做时序推理
    4. 提取 10 张密度图，逐张保存
    """
    import torch
    import torch.nn.functional as F

    task = _frame_test_task_cache.get(task_id)
    if not task:
        return None

    task["status"] = "running"
    task["progress"] = 0
    task["message"] = "加载 GD3A 模型..."
    # 更新 steps 状态（如果之前是 pending）
    for s in task.get("steps", []):
        if s["status"] == "pending":
            s["status"] = "pending"
    task["steps"][0]["status"] = "running"

    frames_dir = os.path.join(task_dir, "frames")
    label_path = os.path.join(task_dir, "labels.csv")
    result_dir = os.path.join(FRAME_TEST_RESULT_DIR, task_id)
    os.makedirs(result_dir, exist_ok=True)

    labels = parse_labels(label_path)
    frame_files = task.get("frame_files", [])
    total = len(frame_files)
    test_interval = 4  # 对齐 test.py 默认值

    all_results = []
    abs_errors = []
    gt_total = 0
    pred_total = 0
    start_time = time.time()

    # ---- 1. 加载模型 ----
    gd3a_model, gd3a_counter, cfg_data = _load_gd3a_model()
    gd3a_model = gd3a_model.cuda()
    gd3a_counter = gd3a_counter.cuda()
    device = next(gd3a_counter.parameters()).device
    task["steps"][0]["status"] = "done"
    task["elapsed"] = round(time.time() - start_time, 1)
    task["message"] = "GD3A 模型就绪，开始 STEERER 全局密度估计..."

    # ---- 2. 预读所有帧 + STEERER 批量推理 ----
    task["steps"][1]["status"] = "running"
    print(f"[FrameTest:{task_id}] 步骤2: STEERER 全局密度估计开始 ({total} 帧)")
    all_frames_bgr = []
    for filename in frame_files:
        img = cv2.imread(os.path.join(frames_dir, filename))
        all_frames_bgr.append(img)

    # 批量预处理
    preprocessed = []
    for fb in all_frames_bgr:
        t, (w, h) = _preprocess_frame(fb)
        preprocessed.append((t, w, h))

    # Pad 到 32 倍数（找最大尺寸）
    max_h = max(p[0].shape[2] for p in preprocessed)
    max_w = max(p[0].shape[3] for p in preprocessed)
    pad_h = (32 - max_h % 32) % 32
    pad_w = (32 - max_w % 32) % 32
    max_h_p, max_w_p = max_h + pad_h, max_w + pad_w

    # 批量 STEERER 推理
    batch_size = 4
    steerer_global = []  # 每帧的 STEERER 全局密度 (numpy)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_tensors = []
        for i in range(start, end):
            t = preprocessed[i][0]
            batch_tensors.append(F.pad(t, (0, max_w_p - t.shape[3], 0, max_h_p - t.shape[2]), "constant"))
        batch = torch.cat(batch_tensors, dim=0).to(device)
        with torch.no_grad():
            den = gd3a_counter(batch)  # (B, 1, H, W) — STEERER 输出全尺寸
        # STEERER 输出已经是全尺寸密度图，不需要上采样
        for j in range(den.shape[0]):
            oh, ow = preprocessed[start + j][0].shape[2], preprocessed[start + j][0].shape[3]
            steerer_global.append(den[j, 0, :oh, :ow].cpu().numpy())
        task["progress"] = int(end / total * 20)
        task["message"] = f"STEERER 密度估计 {end}/{total}"
        task["elapsed"] = round(time.time() - start_time, 1)

    task["steps"][1]["status"] = "done"
    print(f"[FrameTest:{task_id}] 步骤2完成, 耗时 {time.time() - start_time:.1f}s")

    # ---- 3. GD3A 时序推理（对齐 test.py 逐 pair 推理） ----
    task["steps"][2]["status"] = "running"
    task["message"] = "GD3A 时序推理中..."
    print(f"[FrameTest:{task_id}] 步骤3: GD3A 时序推理开始 (interval={test_interval}, pairs={total - 1})")

    # 构建 labels for GD3A（需要 person 坐标的 target dict）
    def _make_target(persons_a, persons_b):
        """构建两帧的 target，计算 share/outflow/inflow mask"""
        def _single_target(persons, share_mask, outflow_mask, is_target1=True):
            if not persons:
                return {"points": torch.zeros((0, 2), dtype=torch.float32).cuda(),
                        "person_id": torch.zeros(0, dtype=torch.int64).cuda(),
                        "share_mask0": torch.zeros(0, dtype=torch.bool).cuda(),
                        "share_mask1": torch.zeros(0, dtype=torch.bool).cuda(),
                        "outflow_mask": torch.zeros(0, dtype=torch.bool).cuda(),
                        "inflow_mask": torch.zeros(0, dtype=torch.bool).cuda()}
            pts = torch.tensor([[p["x"], p["y"]] for p in persons], dtype=torch.float32)
            # 使用 person_id 如果存在，否则用索引
            ids = torch.tensor([p.get("person_id", i) for i, p in enumerate(persons)], dtype=torch.int64)
            if is_target1:
                return {"points": pts.cuda(), "person_id": ids.cuda(),
                        "share_mask0": share_mask.cuda(),
                        "outflow_mask": outflow_mask.cuda()}
            else:
                return {"points": pts.cuda(), "person_id": ids.cuda(),
                        "share_mask1": share_mask.cuda(),
                        "inflow_mask": outflow_mask.cuda()}

        if not persons_a and not persons_b:
            return [_single_target([], None, None, True), _single_target([], None, None, False)]

        # 提取 IDs
        ids_a = torch.tensor([p.get("person_id", i) for i, p in enumerate(persons_a)], dtype=torch.int64) if persons_a else torch.tensor([], dtype=torch.int64)
        ids_b = torch.tensor([p.get("person_id", i) for i, p in enumerate(persons_b)], dtype=torch.int64) if persons_b else torch.tensor([], dtype=torch.int64)

        # 计算 share mask（基于 person_id 匹配）
        if len(ids_a) > 0 and len(ids_b) > 0:
            share_mask_a = torch.isin(ids_a, ids_b)
            share_mask_b = torch.isin(ids_b, ids_a)
        else:
            share_mask_a = torch.zeros(len(ids_a), dtype=torch.bool)
            share_mask_b = torch.zeros(len(ids_b), dtype=torch.bool)

        outflow_mask_a = torch.logical_not(share_mask_a)
        inflow_mask_b = torch.logical_not(share_mask_b)

        return [_single_target(persons_a, share_mask_a, outflow_mask_a, True),
                _single_target(persons_b, share_mask_b, inflow_mask_b, False)]

    # 存储每帧的 GD3A 输出（对齐 test.py 的 visual_maps 结构）
    # 每个 matched frame: (gt_den, pre_map, gt_share_before, pre_share_before,
    #                       gt_in, pre_in, gt_share_next, pre_share_next, gt_out, pre_out)
    gd3a_outputs = {}  # frame_idx -> 10 张密度图

    # 按 pair 进行 GD3A 推理
    for pair_start in range(0, total - 1, test_interval):
        pair_end = min(pair_start + test_interval, total - 1)

        # 准备两帧
        t1, w1, h1 = preprocessed[pair_start]
        t2, w2, h2 = preprocessed[pair_end]

        # Pad
        max_h_pair = max(t1.shape[2], t2.shape[2])
        max_w_pair = max(t1.shape[3], t2.shape[3])
        ph = (32 - max_h_pair % 32) % 32
        pw = (32 - max_w_pair % 32) % 32
        max_h_pp, max_w_pp = max_h_pair + ph, max_w_pair + pw

        t1_p = F.pad(t1, (0, max_w_pp - t1.shape[3], 0, max_h_pp - t1.shape[2]), "constant")
        t2_p = F.pad(t2, (0, max_w_pp - t2.shape[3], 0, max_h_pp - t2.shape[2]), "constant")

        # 构建 label（空 target，GD3A 推理不需要 GT，只需要 image pair）
        frame_idx_1 = int(os.path.splitext(frame_files[pair_start])[0])
        frame_idx_2 = int(os.path.splitext(frame_files[pair_end])[0])
        gt1 = labels.get(frame_idx_1, {"persons": []})
        gt2 = labels.get(frame_idx_2, {"persons": []})

        img_pair = torch.stack([t1_p[0], t2_p[0]], dim=0).cuda()  # (2, 3, H, W)
        label_list = _make_target(gt1["persons"], gt2["persons"])

        # 调用 GD3A 模型
        with torch.no_grad():
            pre_map, gt_den, pre_share_map, gt_share_den, pre_in_out_map, gt_in_out_den, *_ = \
                gd3a_model(img_pair, label_list, gd3a_counter)

        # 裁剪回原始尺寸
        oh1, ow1 = t1.shape[2], t1.shape[3]
        oh2, ow2 = t2.shape[2], t2.shape[3]

        # Frame A (pair_start) 的密度图
        gt_global_a = gt_den[0, 0, :oh1, :ow1].cpu().numpy()
        pre_global_a = pre_map[0, 0, :oh1, :ow1].cpu().numpy()
        gt_share_a = gt_share_den[0, 0, :oh1, :ow1].cpu().numpy()
        pre_share_a = pre_share_map[0, 0, :oh1, :ow1].cpu().numpy()
        gt_out_a = gt_in_out_den[0, 0, :oh1, :ow1].cpu().numpy()
        pre_out_a = pre_in_out_map[0, 0, :oh1, :ow1].cpu().numpy()

        # Frame B (pair_end) 的密度图
        gt_global_b = gt_den[1, 0, :oh2, :ow2].cpu().numpy()
        pre_global_b = pre_map[1, 0, :oh2, :ow2].cpu().numpy()
        gt_share_b = gt_share_den[1, 0, :oh2, :ow2].cpu().numpy()
        pre_share_b = pre_share_map[1, 0, :oh2, :ow2].cpu().numpy()
        gt_in_b = gt_in_out_den[1, 0, :oh2, :ow2].cpu().numpy()
        pre_in_b = pre_in_out_map[1, 0, :oh2, :ow2].cpu().numpy()

        # 存 Frame A 的结果
        if pair_start not in gd3a_outputs:
            gd3a_outputs[pair_start] = {}
        gd3a_outputs[pair_start].update({
            "pre_global": pre_global_a,
            "gt_global": gt_global_a,
            "pre_share": pre_share_a,
            "gt_share": gt_share_a,
            "pre_out": pre_out_a,
            "gt_out": gt_out_a,
        })

        # 存 Frame B 的结果
        if pair_end not in gd3a_outputs:
            gd3a_outputs[pair_end] = {}
        gd3a_outputs[pair_end].update({
            "pre_global": pre_global_b,
            "gt_global": gt_global_b,
            "pre_share": pre_share_b,
            "gt_share": gt_share_b,
            "pre_in": pre_in_b,
            "gt_in": gt_in_b,
        })

        task["progress"] = 20 + int((pair_start / (total - 1)) * 20)
        task["message"] = f"GD3A 推理 {pair_start + 1}-{pair_end}/{total}"
        task["elapsed"] = round(time.time() - start_time, 1)
        print(f"[FrameTest:{task_id}] GD3A pair {pair_start + 1}-{pair_end}/{total} 完成, 耗时 {task['elapsed']}s")

        # 释放显存
        del img_pair, pre_map, gt_den, pre_share_map, gt_share_den, pre_in_out_map, gt_in_out_den
        torch.cuda.empty_cache()

    task["steps"][2]["status"] = "done"
    print(f"[FrameTest:{task_id}] 步骤3完成, 耗时 {time.time() - start_time:.1f}s")

    # ---- 4. 逐帧保存独立密度图 ----
    task["steps"][3]["status"] = "running"
    task["message"] = "生成密度图..."

    # 用于缓存上一 pair 的 Shared/IN（对齐 test.py 的 previous_gt_share_den 逻辑）
    prev_gt_share_next = None
    prev_pre_share_next = None
    prev_gt_in = None
    prev_pre_in = None

    for i, filename in enumerate(frame_files):
        frame_idx = int(os.path.splitext(filename)[0])
        frame_bgr = all_frames_bgr[i]
        orig_h, orig_w = frame_bgr.shape[:2]

        gt_data = labels.get(frame_idx, {"count": 0, "persons": []})
        gt_count = gt_data["count"]
        persons = gt_data["persons"]

        # STEERER 全局密度（用于获取 den_h, den_w）
        steerer_den = steerer_global[i]
        den_h, den_w = steerer_den.shape

        density_maps = []

        # 原图（缩放到密度图尺寸）
        orig_small = cv2.resize(frame_bgr, (den_w, den_h))
        orig_fname = f"frame_{frame_idx:06d}_original.jpg"
        cv2.imwrite(os.path.join(result_dir, orig_fname), orig_small,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        density_maps.append({
            "type": "original", "label": "原图", "count": 0, "filename": orig_fname,
        })

        # GT Global 密度图
        gt_global_np = _build_gt_density_map(persons, den_h, den_w, orig_w, orig_h)
        fname, cnt = _save_single_density_map(gt_global_np, "GT", "Global",
                                              float(gt_global_np.sum()), result_dir, frame_idx)
        density_maps.append({"type": "gt_global", "label": "GT Global", "count": cnt, "filename": fname})

        # 判断当前帧是否有 GD3A 输出
        is_matched = (i % test_interval == 0) or (i == total - 1)

        if is_matched and i in gd3a_outputs:
            out = gd3a_outputs[i]
            pred_count = float(out["pre_global"].sum())

            # Pre Global
            fname, cnt = _save_single_density_map(out["pre_global"], "Pre", "Global",
                                                  float(out["pre_global"].sum()), result_dir, frame_idx)
            density_maps.append({"type": "pre_global", "label": "Pre Global", "count": cnt, "filename": fname})

            # Shared(Prev) — 使用上一 pair 的 Shared(Next) 缓存
            if prev_gt_share_next is not None:
                fname, cnt = _save_single_density_map(prev_gt_share_next, "GT", "Shared(Prev)",
                                                      float(prev_gt_share_next.sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_prev", "label": "GT Shared(Prev)", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(prev_pre_share_next, "Pre", "Shared(Prev)",
                                                      float(prev_pre_share_next.sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_prev", "label": "Pre Shared(Prev)", "count": cnt, "filename": fname})
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "Shared(Prev)", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_prev", "label": "GT Shared(Prev)", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "Shared(Prev)", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_prev", "label": "Pre Shared(Prev)", "count": 0, "filename": fname})

            # IN（上一 pair 的流入）
            if prev_gt_in is not None:
                fname, cnt = _save_single_density_map(prev_gt_in, "GT", "IN",
                                                      float(prev_gt_in.sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_in", "label": "GT IN", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(prev_pre_in, "Pre", "IN",
                                                      float(prev_pre_in.sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_in", "label": "Pre IN", "count": cnt, "filename": fname})
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "IN", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_in", "label": "GT IN", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "IN", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_in", "label": "Pre IN", "count": 0, "filename": fname})

            # Shared(Next) & OUT — 当前 pair 的
            if "gt_share" in out:
                fname, cnt = _save_single_density_map(out["gt_share"], "GT", "Shared(Next)",
                                                      float(out["gt_share"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_next", "label": "GT Shared(Next)", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(out["pre_share"], "Pre", "Shared(Next)",
                                                      float(out["pre_share"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_next", "label": "Pre Shared(Next)", "count": cnt, "filename": fname})
                prev_gt_share_next = out["gt_share"]
                prev_pre_share_next = out["pre_share"]
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "Shared(Next)", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_next", "label": "GT Shared(Next)", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "Shared(Next)", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_next", "label": "Pre Shared(Next)", "count": 0, "filename": fname})
                prev_gt_share_next = zero
                prev_pre_share_next = zero

            if "gt_out" in out:
                fname, cnt = _save_single_density_map(out["gt_out"], "GT", "OUT",
                                                      float(out["gt_out"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_out", "label": "GT OUT", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(out["pre_out"], "Pre", "OUT",
                                                      float(out["pre_out"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_out", "label": "Pre OUT", "count": cnt, "filename": fname})
                prev_gt_in = out["gt_out"]  # 下一 pair 的 IN = 当前 OUT
                prev_pre_in = out["pre_out"]
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "OUT", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_out", "label": "GT OUT", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "OUT", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_out", "label": "Pre OUT", "count": 0, "filename": fname})
                prev_gt_in = zero
                prev_pre_in = zero

        else:
            # 非匹配帧：只用 STEERER 结果
            pred_count = float(steerer_den.sum())

            # Pre Global（STEERER）
            fname, cnt = _save_single_density_map(steerer_den, "Pre", "Global",
                                                  float(steerer_den.sum()), result_dir, frame_idx)
            density_maps.append({"type": "pre_global", "label": "Pre Global", "count": cnt, "filename": fname})

            # 其余填零
            zero = np.zeros((den_h, den_w), dtype=np.float32)
            for pair in [
                ("gt_shared_prev", "GT Shared(Prev)"), ("pre_shared_prev", "Pre Shared(Prev)"),
                ("gt_in", "GT IN"), ("pre_in", "Pre IN"),
                ("gt_shared_next", "GT Shared(Next)"), ("pre_shared_next", "Pre Shared(Next)"),
                ("gt_out", "GT OUT"), ("pre_out", "Pre OUT"),
            ]:
                prefix = "GT" if pair[0].startswith("gt_") else "Pre"
                label = pair[1].split(" ", 1)[1] if " " in pair[1] else pair[1]
                fname, _ = _save_single_density_map(zero, prefix, label, 0, result_dir, frame_idx)
                density_maps.append({"type": pair[0], "label": pair[1], "count": 0, "filename": fname})

        # 记录结果
        frame_result = {
            "frame": frame_idx,
            "filename": filename,
            "gt_count": gt_count,
            "pred_count": int(round(pred_count)),
            "error": abs(gt_count - int(round(pred_count))),
            "density_maps": density_maps,
        }
        all_results.append(frame_result)
        gt_total += gt_count
        pred_total += int(round(pred_count))
        abs_errors.append(abs(gt_count - int(round(pred_count))))

        task["progress"] = 40 + int((i + 1) / total * 60)
        task["message"] = f"生成密度图 {i + 1}/{total}: 帧{frame_idx} (GT={gt_count}, Pred={int(round(pred_count))})"
        task["elapsed"] = round(time.time() - start_time, 1)

        # GIL 释放
        if (i + 1) % 5 == 0:
            time.sleep(0)

    task["steps"][3]["status"] = "done"
    elapsed = time.time() - start_time

    mae = round(np.mean(abs_errors), 2) if abs_errors else 0
    mse = round(np.sqrt(np.mean([e ** 2 for e in abs_errors])), 2) if abs_errors else 0
    accuracy = round(pred_total / gt_total * 100, 1) if gt_total > 0 else 0

    # ---- 保存结果 JSON ----
    result = {
        "task_id": task_id,
        "model_mode": model_mode,
        "total_frames": total,
        "total_gt": gt_total,
        "total_pred": pred_total,
        "overall_mae": mae,
        "overall_mse": mse,
        "overall_accuracy": accuracy,
        "elapsed": round(elapsed, 2),
        "frames": all_results,
    }

    json_path = os.path.join(result_dir, "result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    task["status"] = "done"
    task["progress"] = 100
    task["message"] = f"完成! {total} 帧, MAE={mae}, 耗时 {elapsed:.1f}s"
    task["elapsed"] = round(elapsed, 2)
    for s in task.get("steps", []):
        if s["status"] == "running":
            s["status"] = "done"

    _frame_test_result_cache[task_id] = result

    # 释放显存
    gd3a_model.cpu()
    torch.cuda.empty_cache()

    return result


def run_frame_test_async(task_id: str, task_dir: str, model_mode: str = "GD3A"):
    """异步启动帧测试"""
    t = threading.Thread(
        target=run_frame_test,
        args=(task_id, task_dir, model_mode),
        daemon=True,
    )
    t.start()
    return task_id


# ============================================================
#  Scene 直接测试（不走上传，直接用数据集 scene 路径）
# ============================================================
DATASET_PATH = '/workspace/MovingDroneCrowd++'

_scene_test_task_cache: Dict[str, dict] = {}
_scene_test_result_cache: Dict[str, dict] = {}


def create_scene_test_task(scene_name: str) -> str:
    task_id = f"st_{uuid.uuid4().hex[:8]}"
    _scene_test_task_cache[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": f"等待启动 scene={scene_name}",
        "scene_name": scene_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_frames": 0,
        "steps": [
            {"name": "加载模型", "status": "pending"},
            {"name": "STEERER 全局密度估计", "status": "pending"},
            {"name": "GD3A 时序推理", "status": "pending"},
            {"name": "生成密度图", "status": "pending"},
        ],
    }
    return task_id


def get_scene_test_status(task_id: str):
    return _scene_test_task_cache.get(task_id)


def get_scene_test_result(task_id: str):
    return _scene_test_result_cache.get(task_id)


def run_scene_test(task_id: str, scene_name: str, test_interval: int = 4):
    """
    直接用数据集 scene 路径跑 GD3A 推理（不经过上传流程）。
    scene_name 如 "scene_1/1"
    """
    import torch
    import torch.nn.functional as F
    import pandas as pd

    task = _scene_test_task_cache.get(task_id)
    if not task:
        return None

    task["status"] = "running"
    task["progress"] = 0
    task["message"] = "加载 GD3A 模型..."

    # 数据路径
    frames_dir = os.path.join(DATASET_PATH, "frames", scene_name)
    csv_path = os.path.join(DATASET_PATH, "annotations", f"{scene_name}.csv")
    result_dir = os.path.join(FRAME_TEST_RESULT_DIR, task_id)
    os.makedirs(result_dir, exist_ok=True)

    # 读取帧列表
    frame_files = sorted(
        [f for f in os.listdir(frames_dir) if f.endswith('.jpg')],
        key=lambda x: int(x.split('.')[0])
    )
    total = len(frame_files)
    task["total_frames"] = total
    task["frame_files"] = frame_files
    task["message"] = f"共 {total} 帧, 开始加载模型..."

    # 解析 GT 标注
    labels: Dict[int, dict] = {}
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, header=None)
        # CSV 列: frame_id(0-based), person_id, x, y, w, h, ...
        for _, row in df.iterrows():
            try:
                frame_idx = int(row[0]) + 1  # CSV 0-based → 1-based
                pid = int(row[1])
                x, y = float(row[2]), float(row[3])
                w = float(row[4]) if len(row) > 4 else 10
                h = float(row[5]) if len(row) > 5 else 10
                if frame_idx not in labels:
                    labels[frame_idx] = {"count": 0, "persons": []}
                labels[frame_idx]["persons"].append({
                    "person_id": pid, "x": x, "y": y, "w": w, "h": h,
                })
                labels[frame_idx]["count"] = len(labels[frame_idx]["persons"])
            except Exception:
                continue

    all_results = []
    abs_errors = []
    gt_total = 0
    pred_total = 0
    start_time = time.time()

    # ---- 1. 加载模型 ----
    task["steps"][0]["status"] = "running"
    gd3a_model, gd3a_counter, cfg_data = _load_gd3a_model()
    gd3a_model = gd3a_model.cuda()
    gd3a_counter = gd3a_counter.cuda()
    device = next(gd3a_counter.parameters()).device
    task["steps"][0]["status"] = "done"
    task["elapsed"] = round(time.time() - start_time, 1)
    task["message"] = "GD3A 模型就绪，开始 STEERER 全局密度估计..."

    # ---- 2. 预读所有帧 + STEERER 批量推理 ----
    task["steps"][1]["status"] = "running"
    print(f"[SceneTest:{task_id}] 步骤2: STEERER 全局密度估计开始 ({total} 帧)")

    all_frames_bgr = []
    for filename in frame_files:
        img = cv2.imread(os.path.join(frames_dir, filename))
        all_frames_bgr.append(img)

    preprocessed = []
    for fb in all_frames_bgr:
        t, (w, h) = _preprocess_frame(fb)
        preprocessed.append((t, w, h))

    max_h = max(p[0].shape[2] for p in preprocessed)
    max_w = max(p[0].shape[3] for p in preprocessed)
    pad_h = (32 - max_h % 32) % 32
    pad_w = (32 - max_w % 32) % 32
    max_h_p, max_w_p = max_h + pad_h, max_w + pad_w

    steerer_global = []
    batch_size = 4
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_tensors = []
        for i in range(start, end):
            t = preprocessed[i][0]
            batch_tensors.append(F.pad(t, (0, max_w_p - t.shape[3], 0, max_h_p - t.shape[2]), "constant"))
        batch = torch.cat(batch_tensors, dim=0).to(device)
        with torch.no_grad():
            den = gd3a_counter(batch)
        for j in range(den.shape[0]):
            oh, ow = preprocessed[start + j][0].shape[2], preprocessed[start + j][0].shape[3]
            steerer_global.append(den[j, 0, :oh, :ow].cpu().numpy())
        task["progress"] = int(end / total * 20)
        task["message"] = f"STEERER 密度估计 {end}/{total}"
        task["elapsed"] = round(time.time() - start_time, 1)

    task["steps"][1]["status"] = "done"
    print(f"[SceneTest:{task_id}] 步骤2完成, 耗时 {time.time() - start_time:.1f}s")

    # ---- 3. GD3A 时序推理 ----
    task["steps"][2]["status"] = "running"
    task["message"] = "GD3A 时序推理中..."
    print(f"[SceneTest:{task_id}] 步骤3: GD3A 时序推理开始 (interval={test_interval})")

    def _make_target(persons_a, persons_b):
        """构建两帧的 target，计算 share/outflow/inflow mask"""
        def _single_target(persons, share_mask, outflow_mask, is_target1=True):
            if not persons:
                return {"points": torch.zeros((0, 2), dtype=torch.float32).cuda(),
                        "person_id": torch.zeros(0, dtype=torch.int64).cuda(),
                        "share_mask0": torch.zeros(0, dtype=torch.bool).cuda(),
                        "share_mask1": torch.zeros(0, dtype=torch.bool).cuda(),
                        "outflow_mask": torch.zeros(0, dtype=torch.bool).cuda(),
                        "inflow_mask": torch.zeros(0, dtype=torch.bool).cuda()}
            pts = torch.tensor([[p["x"], p["y"]] for p in persons], dtype=torch.float32)
            ids = torch.tensor([p.get("person_id", i) for i, p in enumerate(persons)], dtype=torch.int64)
            if is_target1:
                return {"points": pts.cuda(), "person_id": ids.cuda(),
                        "share_mask0": share_mask.cuda(),
                        "outflow_mask": outflow_mask.cuda()}
            else:
                return {"points": pts.cuda(), "person_id": ids.cuda(),
                        "share_mask1": share_mask.cuda(),
                        "inflow_mask": outflow_mask.cuda()}

        if not persons_a and not persons_b:
            return [_single_target([], None, None, True), _single_target([], None, None, False)]

        ids_a = torch.tensor([p.get("person_id", i) for i, p in enumerate(persons_a)], dtype=torch.int64) if persons_a else torch.tensor([], dtype=torch.int64)
        ids_b = torch.tensor([p.get("person_id", i) for i, p in enumerate(persons_b)], dtype=torch.int64) if persons_b else torch.tensor([], dtype=torch.int64)

        if len(ids_a) > 0 and len(ids_b) > 0:
            share_mask_a = torch.isin(ids_a, ids_b)
            share_mask_b = torch.isin(ids_b, ids_a)
        else:
            share_mask_a = torch.zeros(len(ids_a), dtype=torch.bool)
            share_mask_b = torch.zeros(len(ids_b), dtype=torch.bool)

        outflow_mask_a = torch.logical_not(share_mask_a)
        inflow_mask_b = torch.logical_not(share_mask_b)

        return [_single_target(persons_a, share_mask_a, outflow_mask_a, True),
                _single_target(persons_b, share_mask_b, inflow_mask_b, False)]

    gd3a_outputs = {}

    for pair_start in range(0, total - 1, test_interval):
        pair_end = min(pair_start + test_interval, total - 1)

        t1, w1, h1 = preprocessed[pair_start]
        t2, w2, h2 = preprocessed[pair_end]

        max_h_pair = max(t1.shape[2], t2.shape[2])
        max_w_pair = max(t1.shape[3], t2.shape[3])
        ph = (32 - max_h_pair % 32) % 32
        pw = (32 - max_w_pair % 32) % 32
        max_h_pp, max_w_pp = max_h_pair + ph, max_w_pair + pw

        t1_p = F.pad(t1, (0, max_w_pp - t1.shape[3], 0, max_h_pp - t1.shape[2]), "constant")
        t2_p = F.pad(t2, (0, max_w_pp - t2.shape[3], 0, max_h_pp - t2.shape[2]), "constant")

        frame_idx_1 = int(os.path.splitext(frame_files[pair_start])[0])
        frame_idx_2 = int(os.path.splitext(frame_files[pair_end])[0])
        gt1 = labels.get(frame_idx_1, {"persons": []})
        gt2 = labels.get(frame_idx_2, {"persons": []})

        img_pair = torch.stack([t1_p[0], t2_p[0]], dim=0).cuda()
        label_list = _make_target(gt1["persons"], gt2["persons"])

        with torch.no_grad():
            pre_map, gt_den, pre_share_map, gt_share_den, pre_in_out_map, gt_in_out_den, *_ = \
                gd3a_model(img_pair, label_list, gd3a_counter)

        oh1, ow1 = t1.shape[2], t1.shape[3]
        oh2, ow2 = t2.shape[2], t2.shape[3]

        gt_global_a = gt_den[0, 0, :oh1, :ow1].cpu().numpy()
        pre_global_a = pre_map[0, 0, :oh1, :ow1].cpu().numpy()
        gt_share_a = gt_share_den[0, 0, :oh1, :ow1].cpu().numpy()
        pre_share_a = pre_share_map[0, 0, :oh1, :ow1].cpu().numpy()
        gt_out_a = gt_in_out_den[0, 0, :oh1, :ow1].cpu().numpy()
        pre_out_a = pre_in_out_map[0, 0, :oh1, :ow1].cpu().numpy()

        gt_global_b = gt_den[1, 0, :oh2, :ow2].cpu().numpy()
        pre_global_b = pre_map[1, 0, :oh2, :ow2].cpu().numpy()
        gt_share_b = gt_share_den[1, 0, :oh2, :ow2].cpu().numpy()
        pre_share_b = pre_share_map[1, 0, :oh2, :ow2].cpu().numpy()
        gt_in_b = gt_in_out_den[1, 0, :oh2, :ow2].cpu().numpy()
        pre_in_b = pre_in_out_map[1, 0, :oh2, :ow2].cpu().numpy()

        if pair_start not in gd3a_outputs:
            gd3a_outputs[pair_start] = {}
        gd3a_outputs[pair_start].update({
            "pre_global": pre_global_a, "gt_global": gt_global_a,
            "pre_share": pre_share_a, "gt_share": gt_share_a,
            "pre_out": pre_out_a, "gt_out": gt_out_a,
        })

        if pair_end not in gd3a_outputs:
            gd3a_outputs[pair_end] = {}
        gd3a_outputs[pair_end].update({
            "pre_global": pre_global_b, "gt_global": gt_global_b,
            "pre_share": pre_share_b, "gt_share": gt_share_b,
            "pre_in": pre_in_b, "gt_in": gt_in_b,
        })

        task["progress"] = 20 + int((pair_start / (total - 1)) * 20)
        task["message"] = f"GD3A 推理 {pair_start + 1}-{pair_end}/{total}"
        task["elapsed"] = round(time.time() - start_time, 1)
        print(f"[SceneTest:{task_id}] GD3A pair {pair_start + 1}-{pair_end}/{total} 完成")

        del img_pair, pre_map, gt_den, pre_share_map, gt_share_den, pre_in_out_map, gt_in_out_den
        torch.cuda.empty_cache()

    task["steps"][2]["status"] = "done"
    print(f"[SceneTest:{task_id}] 步骤3完成, 耗时 {time.time() - start_time:.1f}s")

    # ---- 4. 逐帧保存独立密度图 ----
    task["steps"][3]["status"] = "running"
    task["message"] = "生成密度图..."

    prev_gt_share_next = None
    prev_pre_share_next = None
    prev_gt_in = None
    prev_pre_in = None

    for i, filename in enumerate(frame_files):
        frame_idx = int(os.path.splitext(filename)[0])
        frame_bgr = all_frames_bgr[i]
        orig_h, orig_w = frame_bgr.shape[:2]

        gt_data = labels.get(frame_idx, {"count": 0, "persons": []})
        gt_count = gt_data["count"]
        persons = gt_data["persons"]

        steerer_den = steerer_global[i]
        den_h, den_w = steerer_den.shape

        density_maps = []

        # 原图
        orig_small = cv2.resize(frame_bgr, (den_w, den_h))
        orig_fname = f"frame_{frame_idx:06d}_original.jpg"
        cv2.imwrite(os.path.join(result_dir, orig_fname), orig_small,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        density_maps.append({
            "type": "original", "label": "原图", "count": 0, "filename": orig_fname,
        })

        # GT Global
        gt_global_np = _build_gt_density_map(persons, den_h, den_w, orig_w, orig_h)
        fname, cnt = _save_single_density_map(gt_global_np, "GT", "Global",
                                              float(gt_global_np.sum()), result_dir, frame_idx)
        density_maps.append({"type": "gt_global", "label": "GT Global", "count": cnt, "filename": fname})

        is_matched = (i % test_interval == 0) or (i == total - 1)

        if is_matched and i in gd3a_outputs:
            out = gd3a_outputs[i]
            pred_count = float(out["pre_global"].sum())

            fname, cnt = _save_single_density_map(out["pre_global"], "Pre", "Global",
                                                  float(out["pre_global"].sum()), result_dir, frame_idx)
            density_maps.append({"type": "pre_global", "label": "Pre Global", "count": cnt, "filename": fname})

            if prev_gt_share_next is not None:
                fname, cnt = _save_single_density_map(prev_gt_share_next, "GT", "Shared(Prev)",
                                                      float(prev_gt_share_next.sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_prev", "label": "GT Shared(Prev)", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(prev_pre_share_next, "Pre", "Shared(Prev)",
                                                      float(prev_pre_share_next.sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_prev", "label": "Pre Shared(Prev)", "count": cnt, "filename": fname})
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "Shared(Prev)", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_prev", "label": "GT Shared(Prev)", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "Shared(Prev)", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_prev", "label": "Pre Shared(Prev)", "count": 0, "filename": fname})

            if prev_gt_in is not None:
                fname, cnt = _save_single_density_map(prev_gt_in, "GT", "IN",
                                                      float(prev_gt_in.sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_in", "label": "GT IN", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(prev_pre_in, "Pre", "IN",
                                                      float(prev_pre_in.sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_in", "label": "Pre IN", "count": cnt, "filename": fname})
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "IN", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_in", "label": "GT IN", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "IN", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_in", "label": "Pre IN", "count": 0, "filename": fname})

            if "gt_share" in out:
                fname, cnt = _save_single_density_map(out["gt_share"], "GT", "Shared(Next)",
                                                      float(out["gt_share"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_next", "label": "GT Shared(Next)", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(out["pre_share"], "Pre", "Shared(Next)",
                                                      float(out["pre_share"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_next", "label": "Pre Shared(Next)", "count": cnt, "filename": fname})
                prev_gt_share_next = out["gt_share"]
                prev_pre_share_next = out["pre_share"]
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "Shared(Next)", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_shared_next", "label": "GT Shared(Next)", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "Shared(Next)", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_shared_next", "label": "Pre Shared(Next)", "count": 0, "filename": fname})
                prev_gt_share_next = zero
                prev_pre_share_next = zero

            if "gt_out" in out:
                fname, cnt = _save_single_density_map(out["gt_out"], "GT", "OUT",
                                                      float(out["gt_out"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "gt_out", "label": "GT OUT", "count": cnt, "filename": fname})
                fname, cnt = _save_single_density_map(out["pre_out"], "Pre", "OUT",
                                                      float(out["pre_out"].sum()), result_dir, frame_idx)
                density_maps.append({"type": "pre_out", "label": "Pre OUT", "count": cnt, "filename": fname})
                prev_gt_in = out["gt_out"]
                prev_pre_in = out["pre_out"]
            else:
                zero = np.zeros((den_h, den_w), dtype=np.float32)
                fname, _ = _save_single_density_map(zero, "GT", "OUT", 0, result_dir, frame_idx)
                density_maps.append({"type": "gt_out", "label": "GT OUT", "count": 0, "filename": fname})
                fname, _ = _save_single_density_map(zero, "Pre", "OUT", 0, result_dir, frame_idx)
                density_maps.append({"type": "pre_out", "label": "Pre OUT", "count": 0, "filename": fname})
                prev_gt_in = zero
                prev_pre_in = zero

        else:
            pred_count = float(steerer_den.sum())

            fname, cnt = _save_single_density_map(steerer_den, "Pre", "Global",
                                                  float(steerer_den.sum()), result_dir, frame_idx)
            density_maps.append({"type": "pre_global", "label": "Pre Global", "count": cnt, "filename": fname})

            zero = np.zeros((den_h, den_w), dtype=np.float32)
            for pair in [
                ("gt_shared_prev", "GT Shared(Prev)"), ("pre_shared_prev", "Pre Shared(Prev)"),
                ("gt_in", "GT IN"), ("pre_in", "Pre IN"),
                ("gt_shared_next", "GT Shared(Next)"), ("pre_shared_next", "Pre Shared(Next)"),
                ("gt_out", "GT OUT"), ("pre_out", "Pre OUT"),
            ]:
                prefix = "GT" if pair[0].startswith("gt_") else "Pre"
                label = pair[1].split(" ", 1)[1] if " " in pair[1] else pair[1]
                fname, _ = _save_single_density_map(zero, prefix, label, 0, result_dir, frame_idx)
                density_maps.append({"type": pair[0], "label": pair[1], "count": 0, "filename": fname})

        frame_result = {
            "frame": frame_idx,
            "filename": filename,
            "gt_count": gt_count,
            "pred_count": int(round(pred_count)),
            "error": abs(gt_count - int(round(pred_count))),
            "density_maps": density_maps,
        }
        all_results.append(frame_result)
        gt_total += gt_count
        pred_total += int(round(pred_count))
        abs_errors.append(abs(gt_count - int(round(pred_count))))

        task["progress"] = 40 + int((i + 1) / total * 60)
        task["message"] = f"生成密度图 {i + 1}/{total}: 帧{frame_idx} (GT={gt_count}, Pred={int(round(pred_count))})"
        task["elapsed"] = round(time.time() - start_time, 1)

        if (i + 1) % 5 == 0:
            time.sleep(0)

    task["steps"][3]["status"] = "done"
    elapsed = time.time() - start_time

    mae = round(np.mean(abs_errors), 2) if abs_errors else 0
    mse = round(np.sqrt(np.mean([e ** 2 for e in abs_errors])), 2) if abs_errors else 0
    accuracy = round(pred_total / gt_total * 100, 1) if gt_total > 0 else 0

    result = {
        "task_id": task_id,
        "scene_name": scene_name,
        "model_mode": "GD3A",
        "total_frames": total,
        "total_gt": gt_total,
        "total_pred": pred_total,
        "overall_mae": mae,
        "overall_mse": mse,
        "overall_accuracy": accuracy,
        "elapsed": round(elapsed, 2),
        "frames": all_results,
    }

    json_path = os.path.join(result_dir, "result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    task["status"] = "done"
    task["progress"] = 100
    task["message"] = f"完成! {total} 帧, MAE={mae}, 耗时 {elapsed:.1f}s"
    task["elapsed"] = round(elapsed, 2)
    for s in task.get("steps", []):
        if s["status"] == "running":
            s["status"] = "done"

    _scene_test_result_cache[task_id] = result

    gd3a_model.cpu()
    torch.cuda.empty_cache()

    return result


def run_scene_test_async(task_id: str, scene_name: str, test_interval: int = 4):
    """异步启动 scene 测试"""
    t = threading.Thread(
        target=run_scene_test,
        args=(task_id, scene_name, test_interval),
        daemon=True,
    )
    t.start()
    return task_id
