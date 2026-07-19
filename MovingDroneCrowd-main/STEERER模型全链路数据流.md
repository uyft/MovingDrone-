# STEERER 模型全链路数据流详解

## 目录

1. [全链路总览](#全链路总览)
2. [第一阶段：视频上传](#第一阶段视频上传)
3. [第二阶段：发起推理任务](#第二阶段发起推理任务)
4. [第三阶段：模型推理核心流程](#第三阶段模型推理核心流程)
5. [第四阶段：单帧预处理详解](#第四阶段单帧预处理详解)
6. [第五阶段：STEERER 模型结构](#第五阶段-steerer-模型结构)
7. [第六阶段：峰值检测详解](#第六阶段峰值检测详解)
8. [第七阶段：绘制标注与视频输出](#第七阶段绘制标注与视频输出)
9. [第八阶段：数据持久化](#第八阶段数据持久化)
10. [第九阶段：进度推送 WebSocket](#第九阶段进度推送-websocket)
11. [第十阶段：前端加载与可视化](#第十阶段前端加载与可视化)
12. [第十一阶段：下载与导出](#第十一阶段下载与导出)
13. [第十二阶段：DOCX 报告生成](#第十二阶段-docx-报告生成)
14. [总结：完整数据链路图](#总结完整数据链路图)
15. [关键文件索引](#关键文件索引)

---

## 全链路总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  浏览器 ──①上传──► FastAPI ──②保存──► uploads/                         │
│  浏览器 ──③发起分析──► FastAPI ──④创建任务──► SQLite                    │
│                    └──⑤后台线程启动──► STEERER推理                     │
│  浏览器 ◄──⑥WebSocket推送进度──── 推理线程                             │
│  浏览器 ──⑦查询结果──► FastAPI ◄──⑧读取── results/ + SQLite           │
│  浏览器 ──⑨下载──► FastAPI ──► 返回文件                               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 第一阶段：视频上传

### 前端代码

文件：`platform_frontend/src/pages/Dashboard.vue`

```javascript
// 点击上传区 → 触发 <input type="file"> → handleFile()
function triggerUpload() {
  fileInput.value?.click()
}

async function doUpload(file) {
  uploading.value = true
  uploadProgress.value = 0

  const form = new FormData()
  form.append('file', file)

  const res = await axios.post('/api/v1/video/upload', form, {
    onUploadProgress: (e) => {
      uploadProgress.value = Math.round((e.loaded / e.total) * 100)
    }
  })

  uploadedFile.value = res.data.filename      // "scene_14.mp4"
  uploadedSize.value = res.data.size_mb        // 24.78
}
```

### 后端代码

文件：`platform_backend/app/api/video.py`（第 20-40 行）

```python
@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    # 1. 格式校验
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:  # ['.mp4', '.avi', '.mov', '.mkv']
        return {"error": f"不支持格式 {ext}"}

    # 2. 安全化文件名
    safe_name = file.filename.replace(" ", "_")
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    # → /workspace/MovingDroneCrowd-main/platform_backend/uploads/scene_14.mp4

    # 3. 异步写入磁盘
    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    # 4. 返回文件信息
    size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
    return VideoUploadResponse(
        filename=safe_name,
        filepath=filepath,
        size_mb=size_mb,
    )
```

---

## 第二阶段：发起推理任务

### 前端代码

文件：`platform_frontend/src/pages/Dashboard.vue`（第 772-784 行）

```javascript
async function startAnalyze() {
  analyzing.value = true
  const res = await axios.post('/api/v1/video/analyze', null, {
    params: {
      filename: uploadedFile.value,   // "scene_14.mp4"
      mode: 'counting',               // 人群计数
      model: 'STEERER',               // STEERER 模型
    }
  })
  currentTaskId.value = res.data.task_id   // 如 "e184b3a5"
  await globalLoadTasks()
  startPolling()   // 开始轮询状态
}
```

### 后端代码

文件：`platform_backend/app/api/video.py`（第 46-88 行）

```python
@router.post("/analyze", response_model=TaskSubmitResponse)
async def analyze_video(filename, mode, model):
    # 1. 检查文件是否存在
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return TaskSubmitResponse(status="error", message=f"文件不存在: {filename}")

    # 2. 创建任务记录
    task_id = create_task(mode, filename=filename, size_mb=24.78)
    # → 写入 SQLite tasks 表 + 内存缓存 _task_cache

    # 3. 启动后台推理线程（不阻塞 HTTP 响应）
    run_counting_async(task_id, filepath, model)
    # → threading.Thread(target=run_counting, args=(task_id, video_path, model), daemon=True).start()

    return TaskSubmitResponse(task_id=task_id, status="submitted", message="推理任务已提交")
```

---

## 第三阶段：模型推理核心流程

文件：`platform_backend/app/services/inference_service.py`（第 682-823 行）

### 3.1 模型加载（线程安全单例）

```python
# 全局变量，整个进程生命周期只加载一次
_counter = None
_model_lock = threading.Lock()

def load_counter():
    global _counter
    if _counter is not None:
        return _counter      # 已加载，直接返回

    with _model_lock:         # 双重检查锁，防止多线程重复加载
        if _counter is not None:
            return _counter

        print("[InferenceService] 加载 STEERER 计数器...")

        # 从 Python 路径导入 STEERER 类
        from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
        from mmcv import Config

        # 读取模型配置文件
        counter_config = Config.fromfile(
            "model/density_estimator/STEERER/configs/MDC.py")

        # 实例化模型
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _counter = STEERER(
            counter_config.network,
            counter_config.dataset.den_factor,
            counter_config.train.route_size
        ).to(device)

        # 加载预训练权重
        sd = torch.load(COUNTER_WEIGHT, map_location="cpu")
        # COUNTER_WEIGHT = "pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth"

        # 去除多GPU训练的 "module." 前缀
        clean = {}
        for k, v in sd.items():
            while k.startswith("module."):
                k = k[7:]
            clean[k] = v
        _counter.load_state_dict(clean, strict=True)
        _counter.eval()     # 切换到评估模式（禁用 Dropout/BatchNorm 统计）

        print(f"[InferenceService] STEERER 加载完成")
        return _counter
```

### 3.2 主推理循环

```python
def run_counting(task_id, video_path, model_name="STEERER"):
    # ===== 更新任务状态 =====
    t = _task_cache[task_id]
    t["status"] = "running"
    t["progress"] = 0
    t["message"] = f"加载模型 {model_name}..."
    db_update_task(task_id, status="running", progress=0, message=t["message"])
    _emit_progress(task_id)  # → WebSocket 推送

    # ===== 加载模型 =====
    counter = load_counter()
    device = _get_device()

    # ===== 打开视频文件 =====
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # ===== 初始化输出 =====
    output_video = os.path.join(RESULT_DIR, f"{task_id}_result.mp4")
    output_json  = os.path.join(RESULT_DIR, f"{task_id}_result.json")

    out_writer = None    # cv2.VideoWriter，首帧初始化
    frame_idx = 0
    all_frame_counts = []
    start_time = time.time()

    # ===== 逐帧处理 =====
    while True:
        ret, frame = cap.read()     # OpenCV 读取一帧 → BGR numpy数组
        if not ret: break
        frame_idx += 1

        # ── 步骤1：预处理 ──
        tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)

        # ── 步骤2：模型推理 ──
        with torch.no_grad():
            density_map = counter(tensor.to(device))

        # ── 步骤3：峰值检测 → 每个人坐标 ──
        peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
        count = len(peaks_xy)

        # ── 步骤4：在帧上绘制标注 ──
        vis = draw_result(frame, peaks_xy, frame_idx, count)

        # ── 步骤5：写入输出视频 ──
        if out_writer is None:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            vh, vw = vis.shape[:2]
            out_writer = cv2.VideoWriter(output_video, fourcc, fps, (vw, vh))
        out_writer.write(vis)

        # ── 步骤6：收集数据 ──
        all_frame_counts.append({
            "frame": frame_idx,
            "count": count,
            "peaks": peaks_xy.tolist() if len(peaks_xy) > 0 else []
        })

        # ── 步骤7：进度更新（每10帧）──
        if frame_idx % 10 == 0:
            progress = int(frame_idx / total_frames * 100)
            t["progress"] = progress
            t["message"] = f"处理中 {frame_idx}/{total_frames}, 当前 {count} 人"
            db_update_task(task_id, progress=progress, message=t["message"])
            _emit_progress(task_id)

    # ===== 收尾处理 =====
    cap.release()
    if out_writer:
        out_writer.release()

    # ===== ffmpeg 转码（mp4v → H.264，确保浏览器兼容）=====
    h264_video = output_video.replace("_result.mp4", "_result_h264.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", output_video,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", h264_video
    ], check=True, capture_output=True)
    os.replace(h264_video, output_video)

    elapsed = time.time() - start_time

    # ===== 更新任务为完成 =====
    t["status"] = "done"
    t["progress"] = 100
    t["message"] = f"完成! 共 {frame_idx} 帧, 耗时 {elapsed:.1f}s"
    db_update_task(task_id, status="done", progress=100, message=t["message"])
    _emit_progress(task_id)

    # ===== 保存 JSON 结果 =====
    result = {
        "task_id": task_id,
        "video_path": video_path,
        "output_video": output_video,
        "fps": fps,
        "total_frames": frame_idx,
        "width": width,
        "height": height,
        "total_time": round(elapsed, 1),
        "frames": all_frame_counts,
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ===== 写入 SQLite =====
    db_save_result(task_id, result)
    _result_cache[task_id] = result

    return result
```

---

## 第四阶段：单帧预处理详解

文件：`platform_backend/app/services/inference_service.py`（第 267-293 行）

```python
MAX_LONG = 1920    # 最长边上限
MAX_SHORT = 1080   # 最短边上限

def preprocess_frame(frame_bgr, max_long=MAX_LONG, max_short=MAX_SHORT):
    """
    输入: BGR numpy数组 (H, W, 3)
    输出: 归一化Tensor [1, 3, H_pad, W_pad]
    """
    # 1. 色彩空间转换: BGR → RGB
    img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    # 2. NumPy → PIL Image
    img_pil = Image.fromarray(img_rgb)
    w, h = img_pil.size

    # 3. 等比缩放（保持宽高比，限制最大尺寸）
    scale = 1.0
    scale_long = max_long / max(w, h) if max(w, h) > 0 else 1
    scale_short = max_short / min(w, h) if min(w, h) > 0 else 1
    if scale_long < 1 or scale_short < 1:
        scale = min(scale_long, scale_short)
        new_w, new_h = int(w * scale), int(h * scale)
        img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)

    # 4. 转换为 Tensor 并归一化
    # _img_transform = Compose([ToTensor(), Normalize(mean, std)])
    tensor = _img_transform(img_pil).unsqueeze(0)  # [1, 3, H, W]

    # 5. Pad 到 32 的倍数（HRNet 网络要求）
    _, _, th, tw = tensor.shape
    pad_h = (32 - th % 32) % 32
    pad_w = (32 - tw % 32) % 32
    if pad_h > 0 or pad_w > 0:
        tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "constant")

    return tensor, (th, tw), (pad_h, pad_w), scale
```

### 预处理流程图

```
原始帧 BGR (3840×2160×3)
    │ cv2.cvtColor
    ▼
RGB (3840×2160×3)
    │ Image.fromarray
    ▼
PIL Image (3840×2160)
    │ resize(LANCZOS)
    │ 3840 > 1920 → scale = 1920/3840 = 0.5
    ▼
PIL Image (1920×1080)
    │ ToTensor() → [0,1] + Normalize(mean, std)
    ▼
Tensor [1, 3, 1080, 1920]
    │ F.pad → pad到32的倍数
    │ pad_h = (32 - 1080%32) % 32 = 8
    │ pad_w = (32 - 1920%32) % 32 = 0
    ▼
Tensor [1, 3, 1088, 1920]  ← 送入模型
```

---

## 第五阶段：STEERER 模型结构

文件：`model/density_estimator/STEERER/build_counter.py`

### 模型架构

```
输入 Tensor [1, 3, H, W]
    │
    ▼
HRNet-48 骨干网络（高分辨率特征保持）
    │  多分辨率并行分支，保持高分辨率特征不丢失
    │  输出多尺度特征图
    ▼
ViT (Vision Transformer) 混合模块
    │  在特征图上做自注意力，增强全局上下文感知
    ▼
密度图解码器
    │  1×1 卷积 → 上采样 → 输出单通道密度图
    ▼
密度图 [1, 1, H/den_factor, W/den_factor]
    │  den_factor 通常是 4 或 8
    │
    ▼ （后处理阶段）
上采样 → 峰值检测 → 每个人坐标
```

### 关键代码路径

| 组件 | 文件路径 |
|------|---------|
| HRNet骨干网络 | `model/density_estimator/STEERER/hrnet.py` |
| ViT模块 | `model/density_estimator/STEERER/vit.py` |
| 密度解码器 | `model/density_estimator/STEERER/decoder.py` |
| 配置文件 | `model/density_estimator/STEERER/configs/MDC.py` |
| 预训练权重 | `pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth` |

---

## 第六阶段：峰值检测详解

文件：`platform_backend/app/services/inference_service.py`（第 296-317 行）

```python
MIN_DISTANCE = 10       # 两个峰值最小间隔（像素）
THRESHOLD_REL = 0.15    # 相对阈值（密度最大值的15%）

def extract_peaks(density_map, original_hw, pad_hw, scale):
    """
    输入:
        density_map: Tensor [1, 1, H_d, W_d]  模型输出的密度图
        original_hw: (H, W)  预处理前的真实尺寸
        pad_hw: (pad_h, pad_w)  padding 量
        scale: 缩放比例

    输出:
        peaks_xy: numpy数组 [[x1,y1], [x2,y2], ...]  每个人的像素坐标
        den_np: 密度图的numpy数组（用于后续热力图）
    """
    th, tw = original_hw
    pad_h, pad_w = pad_hw

    # 1. 双线性上采样到原始尺寸
    den = F.interpolate(
        density_map,
        size=(th + pad_h, tw + pad_w),
        mode='bilinear',
        align_corners=False
    )[0, 0]   # 取 batch[0], channel[0]

    # 2. 去掉 padding 区域
    if pad_h > 0 or pad_w > 0:
        den = den[:th, :tw]

    den_np = den.cpu().numpy()

    # 3. 局部峰值检测
    threshold_abs = den_np.max() * THRESHOLD_REL
    # 例如密度最大值 = 0.008, 阈值 = 0.008 × 0.15 = 0.0012

    peaks = peak_local_max(
        den_np,
        min_distance=MIN_DISTANCE,       # 两个峰值至少相隔10个像素
        threshold_abs=threshold_abs,     # 低于此阈值的忽略
    )
    # peaks 格式: [[row1, col1], [row2, col2], ...]

    # 4. (row, col) → (x, y)，还原到原始图像坐标
    peaks_xy = peaks[:, ::-1].astype(np.float32)

    if scale != 1.0:
        peaks_xy = peaks_xy / scale      # 缩放还原

    return peaks_xy, den_np
```

### 峰值检测原理

```
密度图（灰度热力）              峰值检测结果
┌─────────────────────┐       peaks = [
│  ░░░░░░░░░░░░░░░░░  │         [513, 163],
│  ░░░░████░░░░░░░░░  │         [626, 360],
│  ░░░░████░░░░░░░░░  │         [561, 255],
│  ░░░░░░░░██░░░░░░░  │         [648, 545],
│  ░░░░░░░░░░░░░░░░░  │         ...
│  ░░░░██░░░░░░░░░░░  │       ]
│  ░░░░██░░░░░░░░░░░  │
└─────────────────────┘
       ↓
每个局部最大值 = 一个人
peaks.length = 该帧检测到的人数
```

---

## 第七阶段：绘制标注与视频输出

### 绘制函数

文件：`platform_backend/app/services/inference_service.py`（第 320-340 行）

```python
def draw_result(frame_bgr, peaks_xy, frame_idx, count):
    """在帧上绘制检测框 + 人数统计"""
    vis = frame_bgr.copy()    # 不修改原始帧
    fh, fw = vis.shape[:2]
    box_size = 16             # 检测框半径

    for i, (x, y) in enumerate(peaks_xy):
        x, y = int(x), int(y)

        # 黄色检测框 (BGR: 0, 255, 255)
        cv2.rectangle(vis,
            (max(0, x - box_size // 2), max(0, y - box_size // 2)),
            (min(fw, x + box_size // 2), min(fh, y + box_size // 2)),
            (0, 255, 255), 2)

        # 黄色编号
        cv2.putText(vis, str(i + 1), (x - 8, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # 左上角帧号 + 人数
    cv2.putText(vis, f"Frame {frame_idx} | Count: {count}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)

    return vis
```

### 视频编码流程

```
标注后的帧 (numpy数组)
    │ cv2.VideoWriter (mp4v编码)
    ▼
临时视频 (mp4v, 兼容性差)
    │ subprocess ffmpeg
    │ -c:v libx264 -preset fast -crf 23
    │ -pix_fmt yuv420p -movflags +faststart
    ▼
results/{task_id}_result.mp4 (H.264, 浏览器可直接播放)
```

**为什么需要 ffmpeg 转码？**
- `cv2.VideoWriter` 的 mp4v 编码器在浏览器中兼容性差
- H.264 + yuv420p 是浏览器 `<video>` 标签通用格式
- `-movflags +faststart` 将 moov atom 移到文件头部，支持流式播放

---

## 第八阶段：数据持久化

### 存储位置

```
platform_backend/
├── data.db                           ← SQLite 数据库
├── uploads/
│   └── scene_14.mp4                  ← 用户上传的原始视频
└── results/
    ├── {task_id}_result.mp4          ← 标注后的视频
    └── {task_id}_result.json         ← 完整推理结果
```

### SQLite 表结构

**tasks 表**（任务记录）：

```sql
CREATE TABLE tasks (
    task_id   TEXT PRIMARY KEY,      -- 如 "e184b3a5"
    status    TEXT DEFAULT 'pending', -- pending/running/done/failed
    progress  REAL DEFAULT 0,        -- 0~100
    message   TEXT,                  -- 当前状态描述
    mode      TEXT DEFAULT 'counting',
    model     TEXT,                  -- STEERER/GD3A_VGG16/YOLO11/STNNet
    filename  TEXT,                  -- 上传的文件名
    size_mb   REAL,
    created_at TEXT
);
```

**results 表**（推理结果）：

```sql
CREATE TABLE results (
    task_id      TEXT PRIMARY KEY,
    video_path   TEXT,    -- 原始视频路径
    output_video TEXT,    -- 标注视频路径
    fps          REAL,
    total_frames INTEGER,
    width        INTEGER, -- 视频宽度
    height       INTEGER, -- 视频高度
    total_time   REAL,    -- 推理耗时(秒)
    frames_json  TEXT     -- 每帧数据的JSON
);
```

### JSON 结果格式

```json
{
  "task_id": "e184b3a5",
  "video_path": "/workspace/.../uploads/scene_14.mp4",
  "output_video": "/workspace/.../results/e184b3a5_result.mp4",
  "fps": 30.0,
  "total_frames": 222,
  "width": 2160,
  "height": 3840,
  "total_time": 160.4,
  "frames": [
    {
      "frame": 1,
      "count": 32,
      "peaks": [[958, 2110], [1092, 1996], [1044, 2064], ...]
    },
    {
      "frame": 2,
      "count": 30,
      "peaks": [[1092, 1998], [956, 2112], [1044, 2066], ...]
    }
  ]
}
```

### 双写缓存策略

```python
# 内存缓存（加速频繁读取）
_task_cache: dict = {}      # task_id → task信息
_result_cache: dict = {}    # task_id → 推理结果

def get_task_status(task_id):
    # 优先读缓存
    if task_id in _task_cache:
        return _task_cache[task_id]
    # 缓存未命中，从数据库加载
    t = db_get_task(task_id)
    if t:
        _task_cache[task_id] = t
    return t
```

---

## 第九阶段：进度推送 WebSocket

文件：`platform_backend/app/api/video.py`（第 504-536 行）

### 后端 WebSocket

```python
@router.websocket("/ws/{task_id}")
async def websocket_progress(ws: WebSocket, task_id: str):
    await ws.accept()

    queue = asyncio.Queue()

    def on_progress(data):
        # 推理线程 → asyncio 事件循环（跨线程安全）
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)

    register_progress_callback(task_id, on_progress)

    try:
        while True:
            try:
                # 每5秒超时，发 ping 保持连接
                data = await asyncio.wait_for(queue.get(), timeout=5.0)
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        unregister_progress_callback(task_id)
```

### 前端状态轮询

文件：`platform_frontend/src/pages/Dashboard.vue`（第 786-810 行）

```javascript
function startPolling() {
  pollingTimer = setInterval(async () => {
    await globalLoadTasks()          // 每2秒刷新所有任务列表
    if (currentTaskId.value) {
      await loadCurrentTaskDetail()  // 刷新当前任务详情
    }
  }, 2000)
}

async function loadCurrentTaskDetail() {
  const tid = currentTaskId.value
  await globalLoadTaskDetail(tid)

  // 任务完成 → 加载标注视频 + 更新统计
  if (currentTask.value?.status === 'done') {
    videoSrc.value = `/api/v1/video/download/${tid}`
    if (currentResult.value) {
      updateStatsFromResult(currentResult.value)
    }
  }
}
```

---

## 第十阶段：前端加载与可视化

### 10.1 仪表盘统计

```javascript
function updateStatsFromResult(result) {
  const frames = result.frames || []
  const counts = frames.map(f => f.count)
  const avg = Math.round(counts.reduce((a, b) => a + b, 0) / counts.length)

  currentStats.avgCount = avg              // 平均人数 → 右侧卡片
  currentStats.peakCount = Math.max(...counts)  // 峰值人数
  currentStats.minCount = Math.min(...counts)  // 最低人数
  currentStats.totalFrames = frames.length     // 总帧数
  currentStats.elapsed = result.total_time + 's'  // 耗时
}
```

### 10.2 人群数量变化曲线（ECharts）

```javascript
function updateCountChart(frames) {
  countChartInst.setOption({
    xAxis: {
      type: 'category',
      data: frames.map(f => f.frame),          // 帧号 → 横轴
    },
    yAxis: {
      type: 'value',                           // 人数 → 纵轴
    },
    series: [{
      data: frames.map(f => f.count),          // 每帧人数 → 数据
      type: 'line',
      smooth: true,
      areaStyle: {...}                          // 渐变填充
    }]
  })
}
```

### 10.3 密度分布饼图（ECharts）

```javascript
function updateDensityChart(frames) {
  const counts = frames.map(f => f.count).sort((a, b) => a - b)
  const n = counts.length
  const t1 = counts[Math.floor(n / 3)]
  const t2 = counts[Math.floor(n * 2 / 3)]
  const low  = counts.filter(c => c <= t1).length
  const mid  = counts.filter(c => c > t1 && c <= t2).length
  const high = counts.filter(c => c > t2).length

  densityChartInst.setOption({
    series: [{
      type: 'pie',
      radius: ['40%', '72%'],
      data: [
        { value: low,  name: '低密度' },
        { value: mid,  name: '中密度' },
        { value: high, name: '高密度' },
      ]
    }]
  })
}
```

### 10.4 密度热力图

```python
# 后端生成热力图
def generate_density_image(task_id, video_path, frame_idx, cmap="jet", peaks=True, contour=False, alpha=0.6):
    # 1. 读取帧 + 模型推理 → 密度图
    # 2. matplotlib 叠加：
    #    - imshow(原图)
    #    - imshow(密度图, cmap=cmap, alpha=alpha)  ← 热力图蒙层
    #    - scatter(peaks)                           ← 检测点
    #    - contour(密度图)                          ← 等高线
    # 3. 保存为 JPEG
    # 4. 前端通过 GET /api/v1/video/density/{task_id}/{frame_idx} 获取
```

---

## 第十一阶段：下载与导出

### API 端点一览

| 方法 | 路径 | 功能 | 后端实现 |
|------|------|------|---------|
| `GET` | `/api/v1/video/download/{id}` | 下载标注视频 | `FileResponse(video_path)` |
| `GET` | `/api/v1/video/export/csv/{id}` | CSV 人数统计 | 查 SQLite → 生成 `frame,count,peak_count` |
| `GET` | `/api/v1/video/export/peaks/{id}` | CSV 坐标数据 | 生成 `frame,x,y` |
| `GET` | `/api/v1/video/export/json/{id}` | 完整 JSON 下载 | 返回 `results/{id}_result.json` |
| `GET` | `/api/v1/video/export/pdf/{id}` | DOCX 报告 | 见下节 |
| `POST` | `/api/v1/video/export/zip/{id}` | ZIP 打包 | 后台线程打包 JSON+视频+CSV+采样帧 |
| `GET` | `/api/v1/video/export/zip/{id}/download` | 下载 ZIP | 返回生成好的 ZIP 文件 |

### CSV 导出示例

```python
@router.get("/export/csv/{task_id}")
async def export_csv(task_id: str):
    result = db_get_result(task_id)  # 从 SQLite 读取
    frames = result["frames"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["frame", "count", "peak_count"])
    for f in frames:
        writer.writerow([f["frame"], f["count"], len(f["peaks"])])

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{task_id}_counts.csv"'}
    )
```

生成的 CSV：

```csv
frame,count,peak_count
1,32,32
2,30,30
3,31,31
...
222,28,28
```

---

## 第十二阶段：DOCX 报告生成

文件：`platform_backend/app/services/docx_report.py`

```python
from docx import Document
from docx.shared import Inches

def build_task_report(task_id):
    # 1. 从数据库获取结果
    result = db_get_result(task_id)
    if not result:
        return None

    frames = result["frames"]
    counts = [f["count"] for f in frames]
    avg_count = round(sum(counts) / len(counts))
    peak_count = max(counts)
    min_count = min(counts)

    # 2. 创建 Word 文档
    doc = Document()
    doc.add_heading('DroneCrowd 人群分析报告', level=1)

    # 3. 基本信息
    doc.add_heading('基本信息', level=2)
    doc.add_paragraph(f"任务ID: {task_id}")
    doc.add_paragraph(f"视频分辨率: {result['width']}×{result['height']}")
    doc.add_paragraph(f"总帧数: {result['total_frames']}")
    doc.add_paragraph(f"推理耗时: {result['total_time']}秒")

    # 4. 统计摘要表格
    doc.add_heading('统计摘要', level=2)
    table = doc.add_table(rows=2, cols=5)
    headers = ['总帧数', '平均人数', '峰值人数', '最低人数', '峰值帧']
    values = [result['total_frames'], avg_count, peak_count, min_count, f"第{counts.index(peak_count)+1}帧"]
    for i, h in enumerate(headers):
        table.cell(0, i).text = h
        table.cell(1, i).text = str(values[i])

    # 5. 逐帧数据表
    doc.add_heading('逐帧统计', level=2)
    table2 = doc.add_table(rows=1, cols=3)
    for i, h in enumerate(['帧号', '人数', '检测点数']):
        table2.cell(0, i).text = h
    for f in frames[:50]:  # 最多50帧
        row = table2.add_row()
        row.cells[0].text = str(f['frame'])
        row.cells[1].text = str(f['count'])
        row.cells[2].text = str(len(f.get('peaks', [])))

    # 6. 嵌入标注帧截图
    frame_path = os.path.join(RESULT_DIR, f"{task_id}_frame_000001.jpg")
    if os.path.exists(frame_path):
        doc.add_heading('标注结果示例', level=2)
        doc.add_picture(frame_path, width=Inches(5))

    # 7. 保存
    docx_path = os.path.join(RESULT_DIR, f"{task_id}_report.docx")
    doc.save(docx_path)
    return docx_path
```

---

## 总结：完整数据链路图

```
                        ① 前端上传
    浏览器 ──────────────────────────────────────┐
      │                                          │
      │  FormData { file: scene_14.mp4 }         │
      │                                          ▼
      │                              FastAPI POST /api/v1/video/upload
      │                                          │
      │                                    ② 写入磁盘
      │                                          ▼
      │                              uploads/scene_14.mp4 (25MB)
      │
      │                        ③ 发起推理
      │  axios.post('/analyze', {filename, mode, model})
      │                                          │
      │                                    ④ 创建任务
      │                              task_id = "e184b3a5"
      │                              SQLite INSERT INTO tasks
      │                                          │
      │                                    ⑤ 后台线程
      │                              threading.Thread(run_counting)
      │                                          │
      │                              ┌───────────┴──────────┐
      │                              │  逐帧处理循环          │
      │                              │                      │
      │                              │  ⑥ cv2.read() → BGR │
      │                              │  ⑦ preprocess_frame  │
      │                              │     BGR→RGB→PIL→     │
      │                              │     resize→ToTensor→ │
      │                              │     Normalize→Pad    │
      │                              │  ⑧ STEERER 推理      │
      │                              │     Tensor → 密度图  │
      │                              │  ⑨ extract_peaks    │
      │                              │     密度图 → [x,y]   │
      │                              │  ⑩ draw_result      │
      │                              │     画框+编号+文字   │
      │                              │  ⑩ cv2.VideoWriter   │
      │                              │     写入标注视频     │
      │                              │  ⑩ 收集帧数据        │
      │                              │     {frame,count,    │
      │                              │      peaks}          │
      │                              │                      │
      │                              │  每10帧:             │
      │                              │  → db_update_task    │
      │                              │  → _emit_progress ───┤
      │                              └──────────────────────┘
      │                                                   │
      │                        ⑥ WebSocket 推送进度 ──────┘
      │  ◄── ws.send({progress: 50%, message: "处理中..."})
      │
      │                        ⑦ 收尾
      │                              ffmpeg H.264 转码
      │                              JSON 写入 results/
      │                              SQLite INSERT results
      │                              task.status = "done"
      │
      │                        ⑧ 查询结果
      │  ◄── GET /api/v1/video/result/{task_id}
      │      { frames: [{frame, count, peaks}, ...] }
      │
      │                        ⑨ 前端可视化
      │  ├─ <video src="/download/{task_id}"> 标注视频
      │  ├─ ECharts 折线图: 人数变化曲线
      │  ├─ ECharts 饼图: 密度分布
      │  ├─ 热力图: GET /density/{task_id}/{frame}
      │  └─ 统计卡片: 平均/峰值/最低/耗时
      │
      │                        ⑩ 下载
      │  ◄── GET /export/csv/{task_id}    → CSV
      │  ◄── GET /export/json/{task_id}   → JSON
      │  ◄── GET /export/pdf/{task_id}    → DOCX 报告
      │  ◄── GET /export/zip/{task_id}    → ZIP 打包
```

---

## 关键文件索引

| 功能 | 文件路径 |
|------|---------|
| 前端仪表盘 | `platform_frontend/src/pages/Dashboard.vue` |
| 前端热力图 | `platform_frontend/src/pages/HeatmapView.vue` |
| 前端空间分析 | `platform_frontend/src/pages/SpatialAnalysis.vue` |
| 前端时序分析 | `platform_frontend/src/pages/TemporalAnalysis.vue` |
| 前端轨迹追踪 | `platform_frontend/src/pages/TrajectoryView.vue` |
| 前端路由 | `platform_frontend/src/router.js` |
| 前端全局框架 | `platform_frontend/src/App.vue` |
| 后端入口 | `platform_backend/run.py` |
| FastAPI 应用 | `platform_backend/app/main.py` |
| API 路由（视频） | `platform_backend/app/api/video.py` |
| API 路由（数据集） | `platform_backend/app/api/dataset.py` |
| 推理引擎 | `platform_backend/app/services/inference_service.py` |
| 数据库 | `platform_backend/app/db.py` |
| DOCX 报告 | `platform_backend/app/services/docx_report.py` |
| STEERER 模型 | `model/density_estimator/STEERER/build_counter.py` |
| 预训练权重 | `pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth` |
