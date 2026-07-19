# STEERER 模型平台全流程详解

> 从平台启动 → 视频上传 → STEERER 推理 → 结果保存 → 可视化展示 → 报告下载，完整链路深度解析。

---

## 目录

- [一、平台架构总览](#一平台架构总览)
- [二、前后端启动流程](#二前后端启动流程)
- [三、视频上传：从前端到磁盘](#三视频上传从前端到磁盘)
- [四、推理任务发起](#四推理任务发起)
- [五、STEERER 模型推理核心流程（深度详解）](#五steerer-模型推理核心流程深度详解)
- [六、结果数据持久化](#六结果数据持久化)
- [七、前端可视化：各模块如何消费结果数据](#七前端可视化各模块如何消费结果数据)
- [八、下载与报告生成](#八下载与报告生成)
- [九、完整数据链路图](#九完整数据链路图)
- [十、关键文件索引](#十关键文件索引)

---

## 一、平台架构总览

整个 MovingDroneCrowd 系统的架构分为三层：

```
┌──────────────────────────────────────────────────────────────────┐
│                    用户浏览器                                     │
│               http://localhost:8080                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│           Spring Boot 前端网关 (mdc-visual-platform, 端口 8080)    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Vue 3 SPA (platform_frontend 构建产物)                       │ │
│  │  ├─ SplashPage      首页（无人机灯光秀）                      │ │
│  │  ├─ Dashboard       仪表盘（上传 + 推理 + 统计）              │ │
│  │  ├─ HeatmapView     密度热力图                               │ │
│  │  ├─ SpatialAnalysis 空间分布分析                              │ │
│  │  ├─ TemporalAnalysis 时序分析                                │ │
│  │  ├─ TrajectoryView  轨迹追踪                                 │ │
│  │  ├─ ZoomView        ROI 放大对比                             │ │
│  │  └─ ComparisonView  多模型对比                               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Thymeleaf 模板页面（数据集浏览，服务端渲染）                   │ │
│  │  ├─ index.html      数据集概览首页                           │ │
│  │  ├─ viewer.html     帧查看器（Canvas 标注框 + 逐帧播放）     │ │
│  │  ├─ heatmap.html    密度热力图叠加                           │ │
│  │  ├─ trajectory.html 轨迹追踪 2D 投影                         │ │
│  │  ├─ scenes.html     场景浏览与筛选                           │ │
│  │  └─ stats.html      统计分析图表                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Java 后端服务                                               │ │
│  │  ├─ ApiController      REST API（场景/帧/标注/轨迹查询）     │ │
│  │  ├─ VisualService      业务逻辑层                            │ │
│  │  ├─ DataLoaderService  启动时自动加载 CSV → H2 数据库        │ │
│  │  ├─ H2 内嵌数据库       数据集标注存储                       │ │
│  │  └─ SpaController      SPA 路由回退（Vue Router History 模式）│ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  ProxyFilter  反向代理层（最关键！）                          │ │
│  │  /api/*           → http://localhost:8000/api/*              │ │
│  │  /uploads/*       → http://localhost:8000/uploads/*          │ │
│  │  /results/*       → http://localhost:8000/results/*          │ │
│  │  /dataset_frames/* → http://localhost:8000/dataset_frames/*  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP 反向代理
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│           FastAPI 推理后端 (platform_backend, 端口 8000)           │
│                                                                   │
│  ├─ app/main.py            FastAPI 应用入口                      │
│  ├─ app/api/video.py       API 路由层（上传/推理/导出）          │
│  ├─ app/services/inference_service.py   推理引擎（核心）          │
│  ├─ app/services/docx_report.py         DOCX 报告生成            │
│  ├─ app/db.py              SQLite 持久化                         │
│  └─ app/config.py          全局配置                              │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  STEERER 模型 (HRNet + ViT 混合骨干)                         │ │
│  │  ├─ model/density_estimator/STEERER/build_counter.py        │ │
│  │  ├─ model/density_estimator/STEERER/hrnet.py                │ │
│  │  ├─ model/density_estimator/STEERER/vit.py                  │ │
│  │  ├─ model/density_estimator/STEERER/decoder.py              │ │
│  │  └─ pretrained/*.pth  预训练权重                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**核心设计：Spring Boot 作为统一网关**

Spring Boot 是整个平台的唯一入口（端口 8080）。它同时承担三个角色：

| 角色 | 实现方式 |
|------|---------|
| **静态资源服务器** | 托管 Vue 3 SPA 构建产物（`static/index.html` + `assets/`） |
| **反向代理网关** | `ProxyFilter` 将 `/api/*`、`/uploads/*`、`/results/*` 转发到 FastAPI |
| **数据集可视化后端** | 内嵌 API + Thymeleaf 模板，独立完成数据集浏览功能 |

**关键：请求路由规则**

```
用户请求 URL                         Spring Boot 处理方式
─────────────────────────────────────────────────────────────
/                                    SpaController → forward:/index.html (Vue SPA)
/dashboard                           SpaController → forward:/index.html (Vue Router 接管)
/heatmap                             SpaController → forward:/index.html
/overview                            SpaController → forward:/index.html
/assets/index-Cy2lgwTg.js           静态资源，直接返回
/viewer                              Thymeleaf 模板 viewer.html
/scenes                              Thymeleaf 模板 scenes.html
/heatmap (Thymeleaf)                Thymeleaf 模板 heatmap.html
/api/v1/video/upload                 ProxyFilter → FastAPI :8000
/api/v1/video/analyze               ProxyFilter → FastAPI :8000
/api/v1/video/result/{id}           ProxyFilter → FastAPI :8000
/uploads/drone.mp4                   ProxyFilter → FastAPI :8000
/results/e184b3a5_result.mp4        ProxyFilter → FastAPI :8000
/api/scenes                          ApiController（Spring Boot 自身处理）
/api/images/...                      ApiController（Spring Boot 自身处理）
```

**技术栈速览：**

| 层次 | 技术 |
|------|------|
| 前端框架 | Vue 3 + Vite（构建为静态资源） |
| 前端图表 | ECharts 5 |
| 前端路由 | vue-router 4（History 模式） |
| 前端网关 | Spring Boot 3.2.0 |
| 服务端模板 | Thymeleaf |
| Java 数据库 | H2（内嵌，存储数据集标注） |
| Java 构建工具 | Maven |
| 推理后端 | FastAPI + uvicorn (Python) |
| 实时通信 | WebSocket |
| Python 数据库 | SQLite (WAL 模式) |
| 深度学习 | PyTorch 2.4.1 + torchvision |
| 图像处理 | OpenCV, PIL, scikit-image |
| 文档生成 | python-docx + matplotlib |

---

## 二、前后端启动流程

### 2.1 完整启动步骤

平台由两个进程组成，需要分别启动：

**第一步：启动 FastAPI 推理后端（端口 8000）**

```bash
cd /workspace/MovingDroneCrowd-main/platform_backend
nohup python run.py --port 8000 > /tmp/backend.log 2>&1 &
```

**第二步：启动 Spring Boot 前端网关（端口 8080）**

```bash
cd /workspace/mdc-visual-platform
mvn spring-boot:run
# 或者打包运行：
# mvn clean package -DskipTests
# java -jar target/mdc-visual-platform-1.0.0.jar
```

**一键启动脚本：** `restart.sh`（但当前脚本启动的是 Vite 开发服务器，非 Spring Boot）

### 2.2 Spring Boot 前端网关启动详解

**入口文件：** `mdc-visual-platform/src/main/java/com/mdc/visual/MdcVisualApplication.java`

```java
@SpringBootApplication
public class MdcVisualApplication {
    public static void main(String[] args) {
        SpringApplication.run(MdcVisualApplication.class, args);
    }
}
```

**启动时自动执行的操作：**

1. **DataLoaderService 数据加载** — 读取 `mdc.data.path` 指向的数据集 CSV 标注文件，批量写入 H2 数据库
2. **ProxyFilter 注册** — 注册反向代理过滤器，优先级最高（`Ordered.HIGHEST_PRECEDENCE`），拦截所有请求路径
3. **静态资源配置** — `classpath:/static/` 映射到根路径，使 Vue SPA 构建产物可被访问
4. **Thymeleaf 模板引擎初始化** — 加载 `templates/` 下的 HTML 模板
5. **H2 数据库初始化** — 文件模式，数据持久化到 `data/mdc_db.mv.db`

**配置文件：** `mdc-visual-platform/src/main/resources/application.properties`

```properties
server.port=8080
mdc.data.path=/workspace/MovingDroneCrowd++          # 数据集路径
spring.datasource.url=jdbc:h2:file:./data/mdc_db      # H2 文件数据库
spring.thymeleaf.cache=false                           # 开发模式不缓存模板
```

### 2.3 FastAPI 推理后端启动详解

**入口文件：** `platform_backend/run.py`

```python
# run.py 核心逻辑
uvicorn.run(
    "app.main:app",      # FastAPI 应用实例
    host="0.0.0.0",
    port=8000,
    reload=False,        # 生产模式不热重载
    workers=1,           # 单 worker（GPU 模型避免重复加载）
)
```

**FastAPI 应用初始化：** `platform_backend/app/main.py`

启动时执行的关键步骤：

1. **数据库初始化** — 创建 `tasks` 和 `results` 两张表（SQLite）
2. **缓存预热** — 从 SQLite 加载所有历史任务到内存缓存 `_task_cache`
3. **CORS 中间件** — 允许所有来源的跨域请求（Spring Boot 代理也需要）
4. **路由注册** — 挂载 `/api/v1` 前缀的 API 路由
5. **静态文件挂载** — `/uploads`、`/results`、`/dataset_frames`（供 Spring Boot 反向代理访问）
6. **SPA 回退** — 如果检测到 `platform_frontend/dist/` 存在，也提供 SPA 回退（兼容直接访问 8000 端口时）

```python
@app.on_event("startup")
async def startup():
    from app.db import init_db_sync, db_list_tasks, db_get_result
    init_db_sync()                     # 创建表结构

    # 预热缓存：加载所有历史任务
    tasks = db_list_tasks()
    for t in tasks:
        _task_cache[t["task_id"]] = t
    # 加载已完成任务的结果
    for t in tasks:
        r = db_get_result(t["task_id"])
        if r:
            _result_cache[t["task_id"]] = r
```

### 2.4 Spring Boot ProxyFilter：反向代理核心

这是整个架构中最重要的组件，所有推理相关的请求都通过它转发到 FastAPI。

**文件：** `mdc-visual-platform/src/main/java/com/mdc/visual/config/ProxyFilter.java`

```java
public class ProxyFilter implements Filter {

    private static final String TARGET_BASE = "http://localhost:8000";

    // 需要代理的路径前缀
    private static final List<String> PROXY_PREFIXES = Arrays.asList(
        "/api/", "/uploads/", "/results/", "/dataset_frames/"
    );

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        String path = request.getRequestURI();

        // 判断是否需要代理
        if (!shouldProxy(path)) {
            chain.doFilter(request, response);   // 不需要代理，交给 Spring Boot 自身处理
            return;
        }

        // 构建目标 URL → http://localhost:8000/api/v1/video/upload
        String targetUrl = TARGET_BASE + path + (query != null ? "?" + query : "");

        // 使用 HttpURLConnection 转发请求
        HttpURLConnection conn = (HttpURLConnection) new URL(targetUrl).openConnection();
        conn.setRequestMethod(request.getMethod());

        // 转发请求头（排除 hop-by-hop 头）
        copyRequestHeaders(request, conn);

        // 转发请求体（POST/PUT 的文件上传等）
        if (request.getContentLengthLong() > 0) {
            // 流式复制请求体到后端
            InputStream in = request.getInputStream();
            OutputStream out = conn.getOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
            }
        }

        // 读取后端响应并写回给浏览器
        int status = conn.getResponseCode();
        response.setStatus(status);
        copyResponseHeaders(conn, response);    // 转发响应头

        // 流式转发响应体（支持大文件和 SSE）
        InputStream in = conn.getInputStream();
        OutputStream out = response.getOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) != -1) {
            out.write(buf, 0, n);
            out.flush();
        }
    }
}
```

**请求流向示意：**

```
浏览器 POST http://localhost:8080/api/v1/video/upload
    │
    ▼
Spring Boot :8080
    │ ProxyFilter 匹配到 /api/ 前缀
    │ 构建目标 URL: http://localhost:8000/api/v1/video/upload
    │ HttpURLConnection 转发请求 + 请求体
    ▼
FastAPI :8000
    │ POST /api/v1/video/upload
    │ 处理上传，保存文件到 uploads/
    │ 返回 JSON { filename: "drone.mp4", size_mb: 24.78 }
    ▼
Spring Boot :8080
    │ 读取 FastAPI 响应
    │ 复制响应头 + 响应体 → 写回给浏览器
    ▼
浏览器收到 JSON 响应
```

### 2.5 前端路由机制

Spring Boot 通过 `SpaController` 支持 Vue Router 的 HTML5 History 模式：

```java
@Controller
public class SpaController {

    @GetMapping("/")
    public String index() {
        return "forward:/index.html";   // → static/index.html (Vue SPA 入口)
    }

    @GetMapping("/{path:[^\\.]+}")       // 单层路径，不含文件后缀
    public String forwardSingle(String path) {
        return "forward:/index.html";   // → Vue Router 接管路由
    }

    @GetMapping("/{path1:[^\\.]+}/{path2:[^\\.]+}")  // 两层路径
    public String forwardDouble(String path1, String path2) {
        return "forward:/index.html";
    }
}
```

> 例如 `/dashboard`、`/heatmap`、`/spatial` 等 Vue Router 路由都会被转发到 `static/index.html`，由 Vue Router 客户端接管。

---

## 三、视频上传：从前端到磁盘

### 3.1 完整请求链路

```
用户浏览器 (Vue 3 SPA)
    │
    │  axios.post('/api/v1/video/upload', FormData { file })
    │
    ▼
Spring Boot :8080  (ProxyFilter)
    │  匹配 /api/ 前缀
    │  HttpURLConnection → http://localhost:8000/api/v1/video/upload
    │  流式转发请求体（视频文件二进制数据）
    ▼
FastAPI :8000  (app/api/video.py)
    │  格式校验 → 安全化文件名 → aiofiles 异步写入磁盘
    ▼
uploads/drone_footage.mp4  (写入磁盘)
```

### 3.2 前端上传代码

**文件：** `platform_frontend/src/pages/Dashboard.vue`（构建后部署到 Spring Boot `static/` 中）

```javascript
// 用户点击上传区 → 触发文件选择
function triggerUpload() {
  fileInput.value?.click()
}

// 文件选择后通过 axios 上传
async function doUpload(file) {
  uploading.value = true

  const form = new FormData()
  form.append('file', file)

  // 这个请求被 Spring Boot ProxyFilter 转发到 FastAPI
  const res = await axios.post('/api/v1/video/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      uploadProgress.value = Math.round((e.loaded / e.total) * 100)
    }
  })

  uploadedFile.value = res.data.filename      // "drone_footage.mp4"
  uploadedSize.value = res.data.size_mb        // 24.78
}
```

### 3.3 FastAPI 后端接收与存储

**文件：** `platform_backend/app/api/video.py`

```python
@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    # 步骤 1：格式校验
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:  # {'.mp4', '.avi', '.mov', '.mkv'}
        return {"error": f"不支持格式 {ext}"}

    # 步骤 2：安全化文件名（替换空格，防止路径遍历攻击）
    safe_name = file.filename.replace(" ", "_")
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    # → /workspace/MovingDroneCrowd-main/platform_backend/uploads/drone_footage.mp4

    # 步骤 3：异步流式写入磁盘
    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()      # 读取全部字节
        await f.write(content)           # 写入磁盘

    # 步骤 4：计算文件大小并返回
    size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
    return VideoUploadResponse(
        filename=safe_name,
        filepath=filepath,
        size_mb=size_mb,
    )
```

**存储位置：**
```
platform_backend/uploads/
└── drone_footage.mp4    ← 用户上传的原始视频
```

---

## 四、推理任务发起

### 4.1 前端发起推理

用户在 Dashboard 上传视频后，点击"开始分析"按钮：

```javascript
async function startAnalyze() {
  analyzing.value = true

  // 这个请求同样被 Spring Boot ProxyFilter 转发到 FastAPI
  const res = await axios.post('/api/v1/video/analyze', null, {
    params: {
      filename: uploadedFile.value,   // "drone_footage.mp4"
      mode: 'counting',               // 人群计数模式
      model: 'STEERER',               // 使用 STEERER 模型
    }
  })

  currentTaskId.value = res.data.task_id   // 如 "e184b3a5"
  await globalLoadTasks()                   // 刷新任务列表
  startPolling()                            // 每 2 秒轮询任务状态
}
```

### 4.2 FastAPI 后端创建任务并启动推理

**文件：** `platform_backend/app/api/video.py`

```python
@router.post("/analyze", response_model=TaskSubmitResponse)
async def analyze_video(filename, mode, model):
    # 步骤 1：校验文件存在
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return TaskSubmitResponse(status="error", message=f"文件不存在: {filename}")

    # 步骤 2：创建任务记录（写入 SQLite + 内存缓存）
    task_id = create_task(mode, filename=filename, size_mb=...)

    # 步骤 3：启动后台推理线程（不阻塞 HTTP 响应，立即返回）
    run_counting_async(task_id, filepath, model)
    # → threading.Thread(target=run_counting, daemon=True).start()

    # 步骤 4：立即返回任务 ID
    return TaskSubmitResponse(task_id=task_id, status="submitted", message="推理任务已提交")
```

**关键设计：** 推理在后台线程中运行，HTTP 请求立即返回。前端通过轮询（每 2 秒 GET `/api/v1/video/task/{task_id}`）获取进度。

---

## 五、STEERER 模型推理核心流程（深度详解）

这是整个平台最核心的部分。推理引擎位于 `platform_backend/app/services/inference_service.py`。

### 5.1 推理入口：`run_counting()`

```python
def run_counting(task_id, video_path, model_name="STEERER"):
    """
    执行人群计数任务（在后台线程中运行）

    参数:
        task_id:    任务 ID，如 "e184b3a5"
        video_path: 原始视频绝对路径
        model_name: "STEERER" / "GD3A_VGG16" / "GD3A_ResNet50" / "YOLO11"
    """
```

整个推理流程分为以下步骤：

---

### 5.2 步骤 ①：模型加载（线程安全单例）

```python
_counter = None          # 全局模型实例，整个进程只加载一次
_model_lock = threading.Lock()

def load_counter():
    global _counter
    if _counter is not None:
        return _counter      # 已加载，直接返回（避免重复占用 GPU 显存）

    with _model_lock:         # 双重检查锁（DCL），防止多线程竞争
        if _counter is not None:
            return _counter

        # 1. 导入 STEERER 模型类
        from model.density_estimator.STEERER.build_counter import Baseline_Counter as STEERER
        from mmcv import Config

        # 2. 读取模型配置文件
        counter_config = Config.fromfile(
            "model/density_estimator/STEERER/configs/MDC.py")

        # 3. 实例化模型并移到 GPU
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _counter = STEERER(
            counter_config.network,              # 网络结构配置（HRNet48 + MoE）
            counter_config.dataset.den_factor,   # 密度图下采样因子（通常 4 或 8）
            counter_config.train.route_size      # 路由尺寸
        ).to(device)

        # 4. 加载预训练权重
        sd = torch.load(
            "pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth",
            map_location="cpu")

        # 5. 去除多 GPU 训练的 "module." 前缀
        clean = {}
        for k, v in sd.items():
            while k.startswith("module."):
                k = k[7:]       # 剥离 DataParallel 包装的前缀
            clean[k] = v

        # 6. 加载权重 + 切换到评估模式
        _counter.load_state_dict(clean, strict=True)
        _counter.eval()   # 禁用 Dropout、BatchNorm 统计更新

        return _counter
```

**设计要点：**
- 整个进程生命周期只加载一次模型（GPU 显存宝贵，避免重复加载）
- 双重检查锁（Double-Checked Locking）防止多线程重复加载
- `model.eval()` 确保推理时行为确定（关闭随机性）

---

### 5.3 步骤 ②：打开视频文件

```python
cap = cv2.VideoCapture(video_path)

# 读取视频元信息
fps = cap.get(cv2.CAP_PROP_FPS)                      # 帧率，如 30.0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) # 总帧数，如 222
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))       # 宽度，如 3840
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))      # 高度，如 2160

# 初始化输出路径
output_video = "results/{task_id}_result.mp4"
output_json  = "results/{task_id}_result.json"
```

---

### 5.4 步骤 ③：逐帧处理主循环

```python
frame_idx = 0
all_frame_counts = []
out_writer = None

while True:
    ret, frame = cap.read()       # OpenCV 读取一帧 → BGR numpy 数组 (H, W, 3)
    if not ret:
        break                      # 视频结束

    frame_idx += 1

    # ── 子步骤 3a：图像预处理 ──
    tensor, (th, tw), (pad_h, pad_w), scale = preprocess_frame(frame)

    # ── 子步骤 3b：STEERER 模型推理 ──
    with torch.no_grad():
        density_map = counter(tensor.to(device))

    # ── 子步骤 3c：峰值检测提取人头坐标 ──
    peaks_xy, _ = extract_peaks(density_map, (th, tw), (pad_h, pad_w), scale)
    count = len(peaks_xy)         # 该帧检测到的总人数

    # ── 子步骤 3d：绘制标注框 ──
    vis = draw_result(frame, peaks_xy, frame_idx, count)

    # ── 子步骤 3e：写入输出视频 ──
    if out_writer is None:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(output_video, fourcc, fps, (vw, vh))
    out_writer.write(vis)

    # ── 子步骤 3f：收集帧数据 ──
    all_frame_counts.append({
        "frame": frame_idx,
        "count": count,
        "peaks": peaks_xy.tolist() if len(peaks_xy) > 0 else []
    })

    # ── 子步骤 3g：进度更新（每 10 帧写 DB + 推送一次）──
    if frame_idx % 10 == 0:
        progress = int(frame_idx / total_frames * 100)
        t["progress"] = progress
        t["message"] = f"处理中 {frame_idx}/{total_frames}, 当前 {count} 人"
        db_update_task(task_id, progress=progress, message=t["message"])
        _emit_progress(task_id)    # → 触发 WebSocket 推送
```

---

### 5.5 子步骤 3a 详解：图像预处理 `preprocess_frame()`

这是数据进入模型前的关键变换管线：

```python
MAX_LONG = 1920    # 长边最大像素
MAX_SHORT = 1080   # 短边最大像素

def preprocess_frame(frame_bgr):
    """
    输入: BGR numpy 数组 (H, W, 3)  — 如 (2160, 3840, 3)  4K 无人机视频帧
    输出: 归一化 Tensor [1, 3, H_pad, W_pad]
    """
    # ① BGR → RGB 色彩空间转换
    img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    # ② NumPy → PIL Image
    img_pil = Image.fromarray(img_rgb)
    w, h = img_pil.size   # (3840, 2160)

    # ③ 等比缩放（保持宽高比，限制最大尺寸为 1920×1080）
    scale = 1.0
    scale_long  = MAX_LONG / max(w, h)    # 1920/3840 = 0.5
    scale_short = MAX_SHORT / min(w, h)   # 1080/2160 = 0.5
    if scale_long < 1 or scale_short < 1:
        scale = min(scale_long, scale_short)   # scale = 0.5
        new_w, new_h = int(w * scale), int(h * scale)  # (1920, 1080)
        img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)

    # ④ ToTensor + Normalize（使用数据集预计算的 mean/std）
    # _img_transform = Compose([ToTensor(), Normalize(mean, std)])
    tensor = _img_transform(img_pil).unsqueeze(0)   # → [1, 3, 1080, 1920]

    # ⑤ Pad 到 32 的倍数（HRNet 骨干网络要求输入尺寸能被 32 整除）
    _, _, th, tw = tensor.shape
    pad_h = (32 - th % 32) % 32    # (32 - 1080%32) % 32 = (32-24) % 32 = 8
    pad_w = (32 - tw % 32) % 32    # (32 - 1920%32) % 32 = 0
    if pad_h > 0 or pad_w > 0:
        tensor = F.pad(tensor, (0, pad_w, 0, pad_h), "constant")

    return tensor, (th, tw), (pad_h, pad_w), scale
    # tensor: [1, 3, 1088, 1920]   ← 送入模型
```

**预处理可视化流水线：**

```
原始帧 BGR (2160×3840×3)    ← OpenCV 读取的原始 4K 帧
    │ ① cv2.cvtColor(BGR→RGB)
    ▼
RGB (2160×3840×3)
    │ ② Image.fromarray
    ▼
PIL Image (3840×2160)
    │ ③ resize(LANCZOS), scale=0.5
    ▼
PIL Image (1920×1080)       ← 缩放到 HD 分辨率
    │ ④ ToTensor() → [0,1] + Normalize(mean, std)
    ▼
Tensor [1, 3, 1080, 1920]
    │ ⑤ F.pad → pad 到 32 的倍数 (pad_h=8, pad_w=0)
    ▼
Tensor [1, 3, 1088, 1920]   ← 送入 STEERER 模型
```

---

### 5.6 子步骤 3b 详解：STEERER 模型前向推理

**模型文件：** `model/density_estimator/STEERER/build_counter.py`

STEERER 是一个基于 **HRNet-48 + ViT 混合架构**的密度估计模型。它的核心思想是：输入一张航拍图像，输出一张密度图（density map），密度图上每个像素的值表示该位置有人头的概率密度。

```
输入 Tensor [1, 3, 1088, 1920]
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  HRNet-48 骨干网络 (High-Resolution Network)              │
│                                                          │
│  特点：全程保持高分辨率特征不丢失                          │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  阶段 1:  高分辨率分支 (1/4 尺度)                  │    │
│  │  阶段 2:  中分辨率分支 (1/8 尺度)                  │    │
│  │  阶段 3:  中低分辨率分支 (1/16 尺度)               │    │
│  │  阶段 4:  低分辨率分支 (1/32 尺度)                 │    │
│  │                                                   │    │
│  │  各分支之间通过多尺度融合模块交换信息                │    │
│  │  输出：多尺度特征图                                 │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
    │ 多尺度特征图
    ▼
┌─────────────────────────────────────────────────────────┐
│  ViT (Vision Transformer) 混合模块                        │
│                                                          │
│  特点：在特征图上做自注意力，增强全局上下文感知              │
│                                                          │
│  ├─ Patch Embedding: 将特征图切分为 patch                 │
│  ├─ Multi-Head Self-Attention: 建模长距离依赖             │
│  ├─ Feed-Forward Network: 非线性变换                     │
│  └─ Layer Normalization + Residual Connection            │
└─────────────────────────────────────────────────────────┘
    │ 增强后的特征图
    ▼
┌─────────────────────────────────────────────────────────┐
│  密度图解码器 (Counting Head)                              │
│                                                          │
│  ├─ 1×1 卷积 → 降维到单通道                              │
│  ├─ 上采样 → 恢复到 (输入尺寸 / den_factor)               │
│  └─ ReLU 激活 → 保证密度值非负                           │
└─────────────────────────────────────────────────────────┘
    │
    ▼
密度图 [1, 1, H/den_factor, W/den_factor]
    │ 如 [1, 1, 272, 480]（den_factor=4 时，1088/4=272, 1920/4=480）
    │ 
    │ 每个像素值 = 该位置有人头的概率密度
    │ 密度越高 → 该像素附近越可能有人
```

**关键代码路径：**

| 组件 | 文件路径 | 作用 |
|------|---------|------|
| 模型入口 | `model/density_estimator/STEERER/build_counter.py` | Baseline_Counter 类，组装 HRNet + ViT + Head |
| HRNet 骨干 | `model/density_estimator/STEERER/backbones/hrnet/` | 多分辨率特征提取，保持高分辨率 |
| ViT 模块 | `model/density_estimator/STEERER/backbones/modules/` | 全局自注意力 + FFN |
| 计数头 | `model/density_estimator/STEERER/heads/counting_head.py` | 密度图解码器 |
| 模型配置 | `model/density_estimator/STEERER/configs/MDC.py` | 网络参数 + 数据集配置 |
| 预训练权重 | `pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth` | 在 MovingDroneCrowd++ 上训练 |

**推理时的关键设置：**

```python
with torch.no_grad():          # 关闭梯度计算，节省显存 + 加速推理
    density_map = counter(tensor.to(device))
# density_map: Tensor [1, 1, H_d, W_d]，浮点值，每个像素表示密度
```

---

### 5.7 子步骤 3c 详解：峰值检测 `extract_peaks()`

从密度图中提取每个人的像素坐标。这是从"密度图"到"人数+位置"的关键转换步骤。

```python
MIN_DISTANCE = 10       # 两个峰值最小间隔（像素），防止同一人被检测多次
THRESHOLD_REL = 0.15    # 相对阈值：只有密度值 > 最大值×15% 的峰值才保留

def extract_peaks(density_map, original_hw, pad_hw, scale):
    """
    输入:
        density_map:  Tensor [1, 1, H_d, W_d] — 模型输出的低分辨率密度图
        original_hw:  (H, W) — 预处理前的原始尺寸（1080, 1920）
        pad_hw:       (pad_h, pad_w) — padding 量（8, 0）
        scale:        float — 缩放比例（0.5）

    输出:
        peaks_xy: numpy 数组 [[x1,y1], [x2,y2], ...] — 原始图像坐标系中每个人的像素坐标
        den_np:   密度图的 numpy 数组（用于后续热力图渲染）
    """
    th, tw = original_hw      # (1080, 1920)
    pad_h, pad_w = pad_hw     # (8, 0)

    # ① 双线性上采样到原始尺寸 + padding
    den = F.interpolate(
        density_map,                              # [1, 1, 272, 480]
        size=(th + pad_h, tw + pad_w),            # (1088, 1920)
        mode='bilinear',
        align_corners=False
    )[0, 0]   # 取 batch[0], channel[0] → shape: (1088, 1920)

    # ② 去掉 padding 区域 → (1080, 1920)
    if pad_h > 0 or pad_w > 0:
        den = den[:th, :tw]

    den_np = den.cpu().numpy()   # GPU Tensor → CPU NumPy

    # ③ 局部峰值检测（使用 scikit-image 的 peak_local_max）
    threshold_abs = den_np.max() * THRESHOLD_REL
    # 例如: 密度最大值 = 0.008, 阈值 = 0.008 × 0.15 = 0.0012

    peaks = peak_local_max(
        den_np,
        min_distance=MIN_DISTANCE,       # 两个峰值最少相隔 10 像素
        threshold_abs=threshold_abs,     # 低于 0.0012 的峰忽略（过滤噪声）
    )
    # peaks 格式: [[row1, col1], [row2, col2], ...]  — 注意是 (行, 列)

    # ④ (row, col) → (x, y)，并还原到原始图像坐标系
    peaks_xy = peaks[:, ::-1].astype(np.float32)   # 行列互换 → (x, y)

    if scale != 1.0:
        peaks_xy = peaks_xy / scale   # 缩放还原: 坐标 × (1/0.5) = 坐标 × 2
        # 因为预处理时将 4K 缩小到 1080p，检测到的坐标需要放大回 4K

    return peaks_xy, den_np
```

**峰值检测原理图示：**

```
密度图（灰度热力）                    峰值检测结果
┌─────────────────────┐            peaks = [
│  ░░░░░░░░░░░░░░░░░  │              [513, 163],   ← 人 1 (x=513, y=163)
│  ░░░░████░░░░░░░░░  │              [626, 360],   ← 人 2
│  ░░░░████░░░░░░░░░  │              [561, 255],   ← 人 3
│  ░░░░░░░░██░░░░░░░  │              [648, 545],   ← 人 4
│  ░░░░░░░░░░░░░░░░░  │              ...
│  ░░░░██░░░░░░░░░░░  │            ]
│  ░░░░██░░░░░░░░░░░  │
└─────────────────────┘
       ↓
   每个局部最大值 = 一个人头位置
   peaks.length = 该帧检测到的总人数
```

---

### 5.8 子步骤 3d 详解：绘制标注 `draw_result()`

```python
def draw_result(frame_bgr, peaks_xy, frame_idx, count):
    """在原始帧上绘制检测框 + 编号 + 帧信息"""
    vis = frame_bgr.copy()    # 不修改原始帧
    fh, fw = vis.shape[:2]
    box_size = 16             # 检测框半径（像素）

    for i, (x, y) in enumerate(peaks_xy):
        x, y = int(x), int(y)

        # 黄色检测框 (BGR: 0, 255, 255)
        cv2.rectangle(vis,
            (max(0, x - box_size // 2), max(0, y - box_size // 2)),
            (min(fw, x + box_size // 2), min(fh, y + box_size // 2)),
            (0, 255, 255), 2)

        # 黄色编号（从 1 开始）
        cv2.putText(vis, str(i + 1), (x - 8, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # 左上角帧号 + 人数（黄色大字）
    cv2.putText(vis, f"Frame {frame_idx} | Count: {count}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)

    return vis
```

### 5.9 步骤 ④：收尾处理

```python
# 1. 释放视频资源
cap.release()
out_writer.release()

# 2. ffmpeg 转码（mp4v → H.264，确保浏览器兼容）
h264_video = output_video.replace("_result.mp4", "_result_h264.mp4")
subprocess.run([
    "ffmpeg", "-y", "-i", output_video,
    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    "-an", h264_video
], check=True, capture_output=True)
os.replace(h264_video, output_video)   # 用 H.264 版本替换原 mp4v 文件

# 3. 更新任务状态为 "done"
elapsed = time.time() - start_time
t["status"] = "done"
t["progress"] = 100
t["message"] = f"完成! 共 {frame_idx} 帧, 耗时 {elapsed:.1f}s"
db_update_task(task_id, status="done", progress=100, message=t["message"])
_emit_progress(task_id)   # → WebSocket 推送给前端

# 4. 保存完整结果 JSON 文件
result = {
    "task_id": task_id,
    "video_path": video_path,
    "output_video": output_video,
    "fps": fps,
    "total_frames": frame_idx,
    "width": width,
    "height": height,
    "total_time": round(elapsed, 1),
    "frames": all_frame_counts,   # 每帧的 {frame, count, peaks}
}
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# 5. 写入 SQLite 数据库（持久化）
db_save_result(task_id, result)
_result_cache[task_id] = result     # 更新内存缓存
```

**为什么需要 ffmpeg 转码？**

| 编码格式 | 问题 |
|---------|------|
| OpenCV 的 mp4v (MPEG-4) | 许多浏览器不支持 `<video>` 直接播放 |
| H.264 (libx264) + yuv420p | 所有现代浏览器通用格式 |
| `-movflags +faststart` | 将 moov atom 移到文件头部，支持流式播放（边下载边播） |

---

### 5.10 进度推送机制

**FastAPI WebSocket：** `platform_backend/app/api/video.py`

```python
@router.websocket("/ws/{task_id}")
async def websocket_progress(ws: WebSocket, task_id: str):
    await ws.accept()
    queue = asyncio.Queue()

    def on_progress(data):
        # 推理线程 → asyncio 事件循环（跨线程安全）
        asyncio.run_coroutine_threadsafe(queue.put(data), asyncio.get_event_loop())

    register_progress_callback(task_id, on_progress)

    while True:
        try:
            data = await asyncio.wait_for(queue.get(), timeout=5.0)
            await ws.send_text(json.dumps(data, ensure_ascii=False))
        except asyncio.TimeoutError:
            await ws.send_text(json.dumps({"type": "ping"}))   # 心跳保活
```

**前端轮询（Vue 3）：**

```javascript
// 每 2 秒通过 HTTP 轮询任务状态（请求经过 Spring Boot ProxyFilter → FastAPI）
function startPolling() {
  pollingTimer = setInterval(async () => {
    await globalLoadTasks()          // GET /api/v1/video/list → 刷新所有任务
    if (currentTaskId.value) {
      await loadCurrentTaskDetail()  // GET /api/v1/video/task/{id} → 刷新当前任务
    }
  }, 2000)
}

// 任务完成 → 自动加载标注视频
async function loadCurrentTaskDetail() {
  await globalLoadTaskDetail(currentTaskId.value)
  if (currentTask.value?.status === 'done') {
    // 标注视频通过 Spring Boot ProxyFilter 从 FastAPI 获取
    videoSrc.value = `/api/v1/video/download/${currentTaskId.value}`
    updateStatsFromResult(currentResult.value)
  }
}
```

---

## 六、结果数据持久化

### 6.1 存储架构（三层双写策略）

```
┌─────────────────────────────────────────────────────────┐
│                   数据存储层次                            │
├─────────────────────────────────────────────────────────┤
│  内存缓存 (_task_cache / _result_cache)                   │
│  ├─ Python dict，进程内读写 O(1)                         │
│  ├─ 优先读取，加速高频访问                               │
│  └─ 服务重启后从 SQLite 恢复                             │
│                                                         │
│  SQLite 数据库 (platform_backend/data.db)                 │
│  ├─ tasks 表: 任务状态、进度、元信息                      │
│  ├─ results 表: 推理结果汇总（frames_json 列存完整帧数据） │
│  └─ WAL 模式，支持读写并发                                │
│                                                         │
│  文件系统                                                │
│  ├─ uploads/{filename}              原始视频             │
│  ├─ results/{task_id}_result.mp4    标注视频 (H.264)     │
│  └─ results/{task_id}_result.json   完整 JSON 结果       │
└─────────────────────────────────────────────────────────┘
```

### 6.2 SQLite 表结构

**tasks 表：**

```sql
CREATE TABLE tasks (
    task_id    TEXT PRIMARY KEY,       -- "e184b3a5"
    status     TEXT DEFAULT 'pending', -- pending → running → done / failed
    progress   REAL DEFAULT 0,         -- 0.0 ~ 100.0
    message    TEXT,                   -- "处理中 111/222, 当前 32 人"
    mode       TEXT DEFAULT 'counting',
    model      TEXT,                   -- "STEERER" / "YOLO11" / "GD3A_VGG16"
    filename   TEXT,                   -- "drone_footage.mp4"
    size_mb    REAL,                   -- 24.78
    created_at TEXT
);
```

**results 表：**

```sql
CREATE TABLE results (
    task_id      TEXT PRIMARY KEY,
    video_path   TEXT,     -- 原始视频路径
    output_video TEXT,     -- 标注视频路径
    fps          REAL,     -- 30.0
    total_frames INTEGER,  -- 222
    width        INTEGER,  -- 3840
    height       INTEGER,  -- 2160
    total_time   REAL,     -- 160.4 (秒)
    frames_json  TEXT      -- 每帧数据的 JSON 字符串（完整存储）
);
```

### 6.3 JSON 结果文件格式

```json
{
  "task_id": "e184b3a5",
  "video_path": "/workspace/.../uploads/drone_footage.mp4",
  "output_video": "/workspace/.../results/e184b3a5_result.mp4",
  "fps": 30.0,
  "total_frames": 222,
  "width": 3840,
  "height": 2160,
  "total_time": 160.4,
  "frames": [
    {
      "frame": 1,
      "count": 32,
      "peaks": [[958, 2110], [1092, 1996], [1044, 2064]]
    },
    {
      "frame": 2,
      "count": 30,
      "peaks": [[1092, 1998], [956, 2112], [1044, 2066]]
    }
  ]
}
```

### 6.4 文件系统存储布局

```
platform_backend/
├── data.db                              ← SQLite 数据库
├── uploads/
│   └── drone_footage.mp4                ← 用户上传的原始视频
└── results/
    ├── e184b3a5_result.mp4              ← 标注后的视频 (H.264, 浏览器可播放)
    ├── e184b3a5_result.json             ← 完整推理结果
    ├── e184b3a5_density_000001_jet_1_0_0.6.jpg  ← 密度热力图（按需生成）
    ├── e184b3a5_frame_000001.jpg        ← 单帧标注图（按需生成）
    ├── e184b3a5_zoom_000030_s2.5_r0.25.jpg      ← ROI 放大对比图
    └── e184b3a5_report.docx             ← DOCX 分析报告（按需生成）
```

---

## 七、前端可视化：各模块如何消费结果数据

### 7.1 数据获取路径

所有前端页面通过 **Spring Boot 代理** 访问 FastAPI 后端获取数据：

```
浏览器 → Spring Boot :8080 (ProxyFilter) → FastAPI :8000
```

关键 API（全部通过 ProxyFilter 转发）：

| API | 方法 | 返回内容 | 说明 |
|-----|------|---------|------|
| `/api/v1/video/result/{task_id}` | GET | 完整结果 JSON | 所有帧的 count + peaks |
| `/api/v1/video/download/{task_id}` | GET | 标注视频 MP4 | `<video>` 直接播放 |
| `/api/v1/video/frame/{task_id}/{frame_idx}` | GET | 单帧标注 JPEG | 按需生成 + 文件缓存 |
| `/api/v1/video/density/{task_id}/{frame_idx}` | GET | 密度热力图 JPEG | 按需生成 + 文件缓存 |
| `/api/v1/video/zoom/{task_id}/{frame_idx}` | GET | ROI 放大对比 JPEG | 自动计算 ROI 中心 |
| `/api/v1/video/list` | GET | 所有历史任务 | 含状态、进度 |

### 7.2 前端页面总览

| 页面 | 路由 | 渲染方式 | 功能 |
|------|------|---------|------|
| Dashboard | `/dashboard` | **Vue 3 SPA** | 上传 + 推理 + 统计卡片 + ECharts 图表 |
| 热力图 | `/heatmap` | **Vue 3 SPA** | 密度热力图叠加 + 参数调节 |
| 空间分析 | `/spatial` | **Vue 3 SPA** | 人群空间分布 + 热点检测 |
| 时序分析 | `/temporal` | **Vue 3 SPA** | 人数变化曲线 + 直方图 |
| 轨迹追踪 | `/trajectory` | **Vue 3 SPA** | 行人轨迹 2D 投影 |
| 放大对比 | `/zoom` | **Vue 3 SPA** | ROI 框选 + 自动放大 |
| 对比分析 | `/compare` | **Vue 3 SPA** | 多模型/多参数结果对比 |
| 数据集首页 | `/` (Thymeleaf) | **服务端渲染** | 数据集概览统计 + ECharts |
| 场景浏览 | `/scenes` | **服务端渲染** | 筛选场景 + 卡片列表 |
| 帧查看器 | `/viewer` | **服务端渲染** | Canvas 标注框 + 逐帧播放 |
| 热力图 | `/heatmap` (Thymeleaf) | **服务端渲染** | Canvas 热力图叠加 |
| 轨迹追踪 | `/trajectory` (Thymeleaf) | **服务端渲染** | 2D 轨迹投影 + 速度曲线 |
| 统计分析 | `/stats` | **服务端渲染** | 散点图、饼图、柱状图 |

> **注意：** `/heatmap` 和 `/trajectory` 路径存在歧义。当用户访问时，SpaController 的 `/` 路由优先匹配 → 返回 `index.html` (Vue SPA)。Thymeleaf 版本的独立页面通过导航栏链接直接访问（具体路径取决于 Thymeleaf 模板中的链接设置）。

### 7.3 Vue 3 SPA 模块的数据消费方式

#### Dashboard（仪表盘）

**路由：** `/dashboard`
**文件：** `platform_frontend/src/pages/Dashboard.vue`

Dashboard 是核心操作页面，直接从结果 JSON 计算所有统计：

```javascript
// 任务完成后，从 result JSON 计算统计卡片
function updateStatsFromResult(result) {
  const frames = result.frames || []
  const counts = frames.map(f => f.count)

  currentStats.avgCount    = Math.round(avg(counts))   // 平均人数
  currentStats.peakCount   = Math.max(...counts)        // 峰值人数
  currentStats.minCount    = Math.min(...counts)        // 最低人数
  currentStats.totalFrames = frames.length              // 总帧数
  currentStats.elapsed     = result.total_time + 's'    // 推理耗时
}

// 标注视频（浏览器 <video> 标签播放）
// <video :src="`/api/v1/video/download/${taskId}`" />

// ECharts 折线图：人群数量变化曲线
countChart.setOption({
  xAxis: { data: frames.map(f => f.frame) },         // 帧号 → X 轴
  yAxis: { type: 'value' },                           // 人数 → Y 轴
  series: [{
    data: frames.map(f => f.count),                   // 每帧人数
    type: 'line', smooth: true,
    areaStyle: { /* 渐变填充 */ }
  }]
})

// ECharts 饼图：密度分布（低/中/高密度帧比例）
const sorted = [...counts].sort((a,b) => a-b)
const t1 = sorted[Math.floor(n/3)]
const t2 = sorted[Math.floor(n*2/3)]
densityChart.setOption({
  series: [{
    type: 'pie',
    data: [
      { value: counts.filter(c => c <= t1).length, name: '低密度' },
      { value: counts.filter(c => c > t1 && c <= t2).length, name: '中密度' },
      { value: counts.filter(c => c > t2).length, name: '高密度' },
    ]
  }]
})
```

#### HeatmapView（密度热力图）

**路由：** `/heatmap`
**文件：** `platform_frontend/src/pages/HeatmapView.vue`

**工作方式：按需生成 + 缓存**

```
用户选择帧号 → 前端请求:
  GET /api/v1/video/density/{task_id}/{frame_idx}?cmap=jet&peaks=true&contour=false&alpha=0.6

↓ Spring Boot ProxyFilter 转发到 FastAPI

后端处理（inference_service.py, generate_density_image）:
  1. cv2.VideoCapture 读取指定帧
  2. preprocess_frame → STEERER 推理 → 得到密度图 + peaks
  3. matplotlib 渲染:
     ax.imshow(原图)
     ax.imshow(密度图, cmap=jet, alpha=0.6)    ← 热力图蒙层
     ax.scatter(peaks, c='white')               ← 白色检测点
     ax.contour(密度图)                          ← 可选等高线
  4. fig.savefig() → JPEG → FileResponse

↓ Spring Boot 反向代理响应

前端: <img :src="`/api/v1/video/density/${taskId}/${frame}?cmap=${cmap}`" />
```

**热力图支持的可调参数（前端控件）：**

| 参数 | 可选值 | 说明 |
|------|--------|------|
| cmap | jet / hot / plasma / inferno / viridis / cool | 配色方案 |
| peaks | true / false | 是否叠加白色检测点 |
| contour | true / false | 是否叠加青色等高线 |
| alpha | 0.1 ~ 1.0 | 热力图不透明度 |

#### SpatialAnalysis（空间分析）

**路由：** `/spatial`
**文件：** `platform_frontend/src/pages/SpatialAnalysis.vue`

从结果 JSON 的 `frames[].peaks` 坐标数组出发，进行空间维度分析：
- 聚合多帧 peaks → 2D 空间热力图（ECharts）
- 密度区域划分（高/中/低密度区域）
- 热点检测与标注

#### TemporalAnalysis（时序分析）

**路由：** `/temporal`
**文件：** `platform_frontend/src/pages/TemporalAnalysis.vue`

从结果 JSON 的 `frames[].count` 出发：
- 人数随时间变化曲线（ECharts 折线图 + 均值线）
- 人数分布直方图（ECharts 柱状图）
- 峰值时段高亮标注
- 流入/流出率变化趋势

#### ZoomView（ROI 放大对比）

**路由：** `/zoom`
**文件：** `platform_frontend/src/pages/ZoomView.vue`

调用后端 API 生成"原图 + 红虚线 ROI 框 + 右侧放大图"的拼接效果：

```
GET /api/v1/video/zoom/{task_id}/{frame_idx}?zoom_scale=2.5&roi_ratio=0.25

后端处理流程:
  1. 读取帧 → STEERER 推理 → 获取 peaks 坐标
  2. 计算所有检测点的几何中心 → 自动确定 ROI 区域
  3. 在原图上画红色虚线 ROI 框
  4. 裁剪 ROI 区域 → 放大 2.5× → 在放大图上重绘检测框
  5. np.hstack([原图 + ROI框, 放大图]) → 保存 JPEG → 返回
```

也支持用户在前端自定义 ROI 矩形（框选区域）：
```
POST /api/v1/video/zoom-custom/{task_id}/{frame_idx}?x1=...&y1=...&x2=...&y2=...
```

#### TrajectoryView（轨迹追踪）

**路由：** `/trajectory`
**文件：** `platform_frontend/src/pages/TrajectoryView.vue`

需要 GD3A + DVTrack 模式（帧间匹配 + 匈牙利算法），利用 `peaks` 帧间关联构建行人轨迹：
- 2D 平面轨迹投影（ECharts scatter + lines）
- 单行人速度/方向分析

#### ComparisonView（对比分析）

**路由：** `/compare`
**文件：** `platform_frontend/src/pages/ComparisonView.vue`

加载多个已完成任务的 `result JSON`，并排对比：
- 不同模型（STEERER vs YOLO11 vs GD3A）的检测差异
- 不同参数的计数结果对比
- 指标对比表（平均人数、峰值、耗时）

### 7.4 Thymeleaf 数据集可视化模块

#### 帧查看器（viewer.html）

**路由：** `/viewer`

Canvas 实现的帧查看器，逐帧播放并叠加 GT 标注框：

```javascript
// 通过 Spring Boot 自身 API 获取数据（不经过 ProxyFilter）
const scenes = await fetch('/api/scenes').then(r => r.json())
const annotations = await fetch(`/api/scenes/${sceneId}/${seqId}/frames/${frameId}`).then(r => r.json())
const imageUrl = `/api/images/${sceneId}/${seqId}/${frameId}`

// Canvas 绘制
ctx.drawImage(img, 0, 0)
annotations.forEach(a => {
  ctx.strokeRect(a.x, a.y, a.w, a.h)     // 标注框
  ctx.fillText(a.personId, a.x, a.y)     // ID 编号
})
```

#### 密度热力图（heatmap.html — Thymeleaf 版本）

**路由：** `/heatmap`（Thymeleaf 模板独立页面）

Canvas 叠加密度热力图到原始帧上，与 Vue 版本不同的实现方式。

---

## 八、下载与报告生成

### 8.1 下载 API 一览

所有下载请求通过 Spring Boot ProxyFilter 转发到 FastAPI：

| API 端点 | 方法 | 输出格式 | 说明 |
|---------|------|---------|------|
| `/api/v1/video/download/{id}` | GET | MP4 视频 | 标注视频文件 |
| `/api/v1/video/export/csv/{id}` | GET | CSV | 每帧人数统计：`frame,count,peak_count` |
| `/api/v1/video/export/peaks/{id}` | GET | CSV | 所有检测点坐标：`frame,x,y` |
| `/api/v1/video/export/json/{id}` | GET | JSON | 完整推理结果文件 |
| `/api/v1/video/export/pdf/{id}` | GET | DOCX | Word 格式分析报告 |
| `/api/v1/video/export/zip/{id}` | POST+GET | ZIP | 异步打包：JSON + 视频 + CSV + 采样帧 |

### 8.2 CSV 导出

**FastAPI 实现：** `platform_backend/app/api/video.py`

```python
@router.get("/export/csv/{task_id}")
async def export_csv(task_id: str):
    result = db_get_result(task_id)     # 从 SQLite 读取
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

生成的 CSV 示例：
```csv
frame,count,peak_count
1,32,32
2,30,30
3,31,31
...
222,28,28
```

### 8.3 DOCX 报告生成（深度详解）

**文件：** `platform_backend/app/services/docx_report.py`

报告生成基于 `python-docx` + `matplotlib`，生成结构化的 Word 文档。

#### 报告结构（6 个章节）

| 章节 | 内容 | 生成方式 |
|------|------|---------|
| **封面** | DroneCrowd 品牌、报告标题、任务 ID、文件名、模型、时间 | python-docx 排版 |
| **一、任务概览** | 视频文件、分辨率、FPS、总帧数、文件大小、处理耗时 | python-docx 表格 |
| **二、统计摘要** | 累计总人数、均值、峰值、最小值、标准差、四分位数、变异系数 | python-docx 表格 |
| **三、人群计数曲线** | 逐帧人数折线图（含均值线 + 峰值标注） + 人数分布直方图 | matplotlib → PNG → 嵌入 |
| **四、关键帧截图** | 首帧、1/3 处、2/3 处、末帧、峰值帧（共 5 张） | OpenCV 抽取 → 嵌入 |
| **五、帧统计附表** | 采样后的逐帧数据（最多 40 行，按间隔采样） | python-docx 表格 |
| **六、总结与分析** | 密度等级判定、变化趋势分析、核心发现、建议与展望 | LLM 风格的自动文本生成 |

#### 核心流程

```python
def build_task_report(task_id: str) -> str | None:
    # 1. 从数据库获取任务和结果
    task = db_get_task(task_id)
    result = db_get_result(task_id)

    frames = result["frames"]
    counts = [f["count"] for f in frames]

    # 2. 计算所有统计指标
    avg_count = sum(counts) / len(counts)
    max_count = max(counts)
    min_count = min(counts)
    std_count = float(np.std(counts))
    cv = (std_count / avg_count * 100)                     # 变异系数 (%)
    q25 = float(np.percentile(counts, 25))                 # 下四分位数
    q75 = float(np.percentile(counts, 75))                 # 上四分位数
    density_label = _density_level(avg_count)               # 密度等级
    trend = _trend_analysis(counts)                         # 前后半段趋势
    high_density_ratio = sum(1 for c in counts              # 高密度帧占比
        if c > avg_count + std_count) / len(counts) * 100

    # 3. 生成图表 → 临时 PNG 文件
    chart_path = _make_count_chart(counts, filename, tmpdir)    # matplotlib 折线图
    hist_path  = _make_density_histogram(counts, tmpdir)        # matplotlib 直方图
    frame_imgs = _extract_key_frames(video_path, ...)           # 关键帧截图

    # 4. 构建 DOCX 文档
    _build_docx(
        docx_path=os.path.join(RESULT_DIR, f"{task_id}_report.docx"),
        task, result, counts, avg_count, max_count, ...
        chart_path, hist_path, frame_imgs,
    )

    return docx_path
```

#### 智能分析能力

报告不仅展示数据，还自动生成分析结论：

**密度等级自动判定：**
```python
def _density_level(avg):
    if avg < 15:    return "低密度（稀疏）"
    elif avg < 50:  return "中低密度"
    elif avg < 100: return "中等密度"
    elif avg < 300: return "中高密度"
    else:           return "高密度（密集）"
```

**变化趋势自动分析（前后半段对比）：**
```python
def _trend_analysis(counts):
    half = len(counts) // 2
    first_avg  = np.mean(counts[:half])
    second_avg = np.mean(counts[half:])
    change_pct = (second_avg - first_avg) / first_avg * 100

    if change_pct > 15:      return "明显上升"
    elif change_pct > 5:     return "小幅上升"
    elif change_pct > -5:    return "基本平稳"
    elif change_pct > -15:   return "小幅下降"
    else:                    return "明显下降"
```

**自动生成建议：**
- 高密度场景 → "建议在峰值时段加强现场管控，设置分流通道"
- CV > 40% → "人群数量波动较大，建议关注波动原因"
- 峰值远超均值（>2.5×） → "建议设置预警阈值，实现自动化告警"
- 通用建议 → "建议定期重复分析，积累历史数据进行纵向对比"

### 8.4 ZIP 打包下载

异步生成，避免大文件打包阻塞 HTTP 响应：

```python
# 前端触发（POST）
POST /api/v1/video/export/zip/{task_id}  → 返回 { zip_task_id, status: "creating" }

# 后台线程打包
def _build_zip(task_id, zip_task_id):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write("results/{task_id}_result.json")       # 完整 JSON
        zf.write("results/{task_id}_result.mp4")        # 标注视频
        zf.writestr("{task_id}_counts.csv", csv_data)   # CSV 统计
        # 采样帧图片（每 30 帧一张）
        for fi in range(1, total, sample_rate):
            frame = cap.read()
            zf.writestr(f"frames/frame_{fi:06d}.jpg", img_bytes)

# 前端轮询状态
GET /api/v1/video/export/zip/{zip_task_id}/status  → { status: "done" }

# 下载
GET /api/v1/video/export/zip/{zip_task_id}/download → ZIP 文件
```

### 8.5 全局下载中心（Vue SPA）

**文件：** `platform_frontend/src/App.vue`

顶部导航栏的全局下载入口，列出所有已完成任务：

```html
<!-- 顶部导航栏下载按钮 -->
<button @click="showDownload = !showDownload">
  ↓ <span class="badge">{{ doneTasks.length }}</span>
</button>

<!-- 下拉菜单：每个任务 5 种下载选项 -->
<div v-if="showDownload">
  <div v-for="t in doneTasks">
    <span>{{ t.filename }}</span>
    <a :href="`/api/v1/video/download/${t.task_id}`">⬡ 视频</a>
    <a :href="`/api/v1/video/export/csv/${t.task_id}`">≡ CSV</a>
    <a :href="`/api/v1/video/export/peaks/${t.task_id}`">📍 坐标</a>
    <a :href="`/api/v1/video/export/json/${t.task_id}`">⊡ JSON</a>
    <a :href="`/api/v1/video/export/pdf/${t.task_id}`">📄 报告</a>
  </div>
</div>
```

所有下载链接都经过 Spring Boot ProxyFilter → FastAPI 后端处理。

---

## 九、完整数据链路图

```
                          ① 前端上传视频
      浏览器 (Vue 3 SPA) ─────────────────────────────────┐
        │  axios.post('/api/v1/video/upload', FormData)    │
        │                                                  │
        ▼                                                  │
      Spring Boot :8080 (ProxyFilter)                      │
        │  匹配 /api/ 前缀                                  │
        │  HttpURLConnection → localhost:8000               │
        │  流式转发请求体（视频二进制数据）                   │
        ▼                                                  │
      FastAPI :8000  POST /api/v1/video/upload             │
        │  格式校验(.mp4/.avi/.mov/.mkv)                   │
        │  安全化文件名 → aiofiles 异步写入                  │
        ▼                                                  │
      uploads/drone_footage.mp4 (写入磁盘)                  │
                                                           │
                          ② 发起推理                       │
      浏览器 ──────────────────────────────────────────────┤
        │  axios.post('/api/v1/video/analyze', {           │
        │    filename, mode:'counting', model:'STEERER'})  │
        ▼                                                  │
      Spring Boot ProxyFilter → FastAPI :8000              │
        │  POST /api/v1/video/analyze                      │
        │                                                  │
        │  ③ 创建任务                                      │
        │  task_id = "e184b3a5" (uuid[:8])                │
        │  SQLite: INSERT INTO tasks (...)                 │
        │  _task_cache["e184b3a5"] = {status:"pending"}   │
        │                                                  │
        │  ④ 启动后台推理线程（不阻塞 HTTP 响应）            │
        │  threading.Thread(run_counting, daemon=True)     │
        │  立即返回 { task_id, status: "submitted" }       │
        │                                                  │
        │  ┌─────────────────────────────────────────────┐ │
        │  │  后台线程: run_counting()                    │ │
        │  │                                             │ │
        │  │  ⑤ 加载 STEERER 模型（仅首次，线程安全单例） │ │
        │  │     HRNet48 + ViT + CountingHead            │ │
        │  │     加载 .pth 预训练权重                     │ │
        │  │     .eval() 切换到推理模式                   │ │
        │  │                                             │ │
        │  │  ⑥ 打开视频 cv2.VideoCapture()              │ │
        │  │     fps, total_frames, width, height        │ │
        │  │                                             │ │
        │  │  ┌── 逐帧循环 ──────────────────────────┐  │ │
        │  │  │                                        │  │ │
        │  │  │  ⑦ cv2.read() → BGR Frame             │  │ │
        │  │  │  ⑧ preprocess_frame()                 │  │ │
        │  │  │     BGR→RGB→PIL→resize(1920×1080)→   │  │ │
        │  │  │     ToTensor→Normalize→Pad(32倍数)    │  │ │
        │  │  │     [H,W,3] → [1,3,H_pad,W_pad]      │  │ │
        │  │  │                                        │  │ │
        │  │  │  ⑨ STEERER 前向推理 (torch.no_grad)   │  │ │
        │  │  │     Tensor → HRNet → ViT → Decoder    │  │ │
        │  │  │     → 密度图 [1,1,Hd,Wd]              │  │ │
        │  │  │                                        │  │ │
        │  │  │  ⑩ extract_peaks()                    │  │ │
        │  │  │     上采样 → 阈值过滤(15%) →          │  │ │
        │  │  │     peak_local_max(min_dist=10)       │  │ │
        │  │  │     → [[x1,y1], [x2,y2], ...]         │  │ │
        │  │  │     count = len(peaks)  ← 该帧人数     │  │ │
        │  │  │                                        │  │ │
        │  │  │  ⑪ draw_result()                      │  │ │
        │  │  │     黄色框 + 编号 + 帧号 + 人数        │  │ │
        │  │  │                                        │  │ │
        │  │  │  ⑫ cv2.VideoWriter.write()             │  │ │
        │  │  │     写入标注帧到输出视频               │  │ │
        │  │  │                                        │  │ │
        │  │  │  ⑬ 收集 {frame, count, peaks}         │  │ │
        │  │  │                                        │  │ │
        │  │  │  每10帧: db_update_task(progress)      │  │ │
        │  │  │          _emit_progress(task_id)       │  │ │
        │  │  └────────────────────────────────────┘  │  │ │
        │  │                                             │ │
        │  │  ⑭ 收尾:                                    │ │
        │  │     ffmpeg mp4v→H.264 转码                   │ │
        │  │     JSON 写入 results/                       │ │
        │  │     SQLite INSERT results                    │ │
        │  │     _result_cache 更新                       │ │
        │  │     task.status = "done"                     │ │
        │  └─────────────────────────────────────────────┘ │
        │                                                  │
        │  ⑮ WebSocket / 轮询 进度推送 ─────────────────── │
        │  ◄── {progress: 50%, message: "处理中..."}       │
        │                                                  │
      浏览器 ◄── Spring Boot ProxyFilter ◄── FastAPI ──────┘

                          ⑯ 前端可视化（Vue 3 SPA）
      浏览器 ──────────────────────────────────────────────
        │
        │  所有数据请求经 Spring Boot ProxyFilter → FastAPI
        │
        ├─ Dashboard:       GET /api/v1/video/result/{id}
        │                   → 统计卡片 + 折线图 + 饼图
        │
        ├─ HeatmapView:     GET /api/v1/video/density/{id}/{frame}
        │                   → matplotlib 热力图叠加
        │
        ├─ SpatialAnalysis: 基于 frames[].peaks → 空间聚合
        │
        ├─ TemporalAnalysis: 基于 frames[].count → 时序分析
        │
        ├─ ZoomView:        GET /api/v1/video/zoom/{id}/{frame}
        │                   → 原图+ROI框+放大图拼接
        │
        └─ ComparisonView:  GET 多个 result → 并排对比

                          ⑰ 下载与导出
      浏览器 ──────────────────────────────────────────────
        │  所有下载请求经 Spring Boot ProxyFilter → FastAPI
        │
        ├─ GET  /api/v1/video/download/{id}        → 标注视频 MP4
        ├─ GET  /api/v1/video/export/csv/{id}      → 人数统计 CSV
        ├─ GET  /api/v1/video/export/peaks/{id}    → 坐标 CSV
        ├─ GET  /api/v1/video/export/json/{id}     → 完整 JSON
        ├─ GET  /api/v1/video/export/pdf/{id}      → DOCX 分析报告
        └─ POST /api/v1/video/export/zip/{id}      → ZIP 异步打包

                          ⑱ 数据集可视化（Thymeleaf 独立功能）
      浏览器 ──────────────────────────────────────────────
        │  直接由 Spring Boot 自身处理（不经过 ProxyFilter）
        │
        ├─ /viewer      帧查看器 → Canvas 标注框 + 逐帧播放
        ├─ /scenes      场景浏览 → 筛选 + 卡片列表
        ├─ /heatmap     密度热力图 → Thymeleaf 版本
        ├─ /trajectory  轨迹追踪 → 2D 投影
        ├─ /stats       统计分析 → ECharts 图表
        │
        └─ /api/scenes, /api/images, /api/...
           → Spring Boot ApiController + H2 数据库
           → VisualService 业务逻辑
```

---

## 十、关键文件索引

### Spring Boot 前端网关 (mdc-visual-platform)

| 功能 | 文件路径 |
|------|---------|
| 应用入口 | `mdc-visual-platform/src/main/java/com/mdc/visual/MdcVisualApplication.java` |
| **反向代理过滤器（核心）** | **`mdc-visual-platform/src/main/java/com/mdc/visual/config/ProxyFilter.java`** |
| Web 配置 | `mdc-visual-platform/src/main/java/com/mdc/visual/config/WebConfig.java` |
| SPA 路由回退 | `mdc-visual-platform/src/main/java/com/mdc/visual/controller/SpaController.java` |
| REST API | `mdc-visual-platform/src/main/java/com/mdc/visual/controller/ApiController.java` |
| 业务逻辑 | `mdc-visual-platform/src/main/java/com/mdc/visual/service/VisualService.java` |
| 数据加载 | `mdc-visual-platform/src/main/java/com/mdc/visual/service/DataLoaderService.java` |
| 应用配置 | `mdc-visual-platform/src/main/resources/application.properties` |
| Vue SPA 入口 | `mdc-visual-platform/src/main/resources/static/index.html` |
| Thymeleaf 模板 | `mdc-visual-platform/src/main/resources/templates/*.html` |

### FastAPI 推理后端 (platform_backend)

| 功能 | 文件路径 |
|------|---------|
| 启动入口 | `platform_backend/run.py` |
| FastAPI 应用 | `platform_backend/app/main.py` |
| 后端配置 | `platform_backend/app/config.py` |
| API 路由（视频） | `platform_backend/app/api/video.py` |
| **推理引擎（核心）** | **`platform_backend/app/services/inference_service.py`** |
| DOCX 报告生成 | `platform_backend/app/services/docx_report.py` |
| SQLite 数据库 | `platform_backend/app/db.py` |
| Pydantic 数据模型 | `platform_backend/app/schemas/models.py` |

### Vue 3 前端源码 (platform_frontend) — 构建后部署到 Spring Boot

| 功能 | 文件路径 |
|------|---------|
| Vite 配置 | `platform_frontend/vite.config.js` |
| Vue 路由 | `platform_frontend/src/router.js` |
| 全局框架 | `platform_frontend/src/App.vue` |
| Dashboard | `platform_frontend/src/pages/Dashboard.vue` |
| 热力图 | `platform_frontend/src/pages/HeatmapView.vue` |
| 空间分析 | `platform_frontend/src/pages/SpatialAnalysis.vue` |
| 时序分析 | `platform_frontend/src/pages/TemporalAnalysis.vue` |
| 轨迹追踪 | `platform_frontend/src/pages/TrajectoryView.vue` |
| 放大对比 | `platform_frontend/src/pages/ZoomView.vue` |
| 对比分析 | `platform_frontend/src/pages/ComparisonView.vue` |

### STEERER 模型与算法

| 功能 | 文件路径 |
|------|---------|
| **STEERER 模型入口** | **`model/density_estimator/STEERER/build_counter.py`** |
| HRNet 骨干 | `model/density_estimator/STEERER/backbones/hrnet/` |
| ViT 模块 | `model/density_estimator/STEERER/backbones/modules/` |
| 计数头 | `model/density_estimator/STEERER/heads/counting_head.py` |
| 模型配置 | `model/density_estimator/STEERER/configs/MDC.py` |
| 预训练权重 | `pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth` |
| 全局训练配置 | `config.py` |
