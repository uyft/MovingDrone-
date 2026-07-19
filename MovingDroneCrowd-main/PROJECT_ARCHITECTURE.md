# MovingDroneCrowd 项目总体架构文档

## 一、项目概述

本工作区包含两个核心项目，共同构成 **"无人机视角动态密集人群计数与跟踪"** 完整系统：

| 项目 | 角色 | 技术栈 |
|------|------|--------|
| **MovingDroneCrowd-main** | 算法核心：深度学习模型训练、测试、视频推理 | PyTorch + FastAPI + Vue 3 |
| **mdc-visual-platform** | 数据集可视化平台：浏览/探索 MovingDroneCrowd++ 数据集 | Spring Boot 3.2 + Thymeleaf + H2 |

其中 `MovingDroneCrowd-main` 内部又分为三层：
- **算法层** (`model/`, `cusdatasets/`, `misc/`, `TrackEval/`)：模型训练与评估
- **推理后端** (`platform_backend/`)：FastAPI REST API，提供模型推理服务
- **推理前端** (`platform_frontend/`)：Vue 3 单页应用，可视化展示推理结果

---

## 二、整体系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                       MovingDroneCrowd 系统                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────── 推理服务平台 ──────────────────────────┐   │
│  │                                                                │   │
│  │   用户浏览器 (Vue 3 SPA)                                       │   │
│  │   ┌───────────┬───────────┬───────────┬───────────┐          │   │
│  │   │ Dashboard │ 逐帧分析  │ 热力图    │ 轨迹追踪  │          │   │
│  │   ├───────────┼───────────┼───────────┼───────────┤          │   │
│  │   │ 空间分析  │ 时序分析  │ 对比分析  │           │          │   │
│  │   └───────────┴───────────┴───────────┴───────────┘          │   │
│  │       │  HTTP/REST + WebSocket                                  │   │
│  │       ▼                                                        │   │
│  │   FastAPI 后端 (port 8000)                                     │   │
│  │   ┌──────────────────────────────────────────────────┐        │   │
│  │   │  路由层: main.py (挂载 API、静态文件、SPA回退)    │        │   │
│  │   │  API 层: api/video.py (上传、推理、进度推送)     │        │   │
│  │   │  服务层: inference_service.py (模型加载与推理)   │        │   │
│  │   │  数据层: db.py (SQLite 任务/结果持久化)          │        │   │
│  │   └──────────────────────────────────────────────────┘        │   │
│  │       │                                                        │   │
│  │       ▼ 加载模型                                                │   │
│  │   ┌──────────────────────────────────────────────────┐        │   │
│  │   │  模型层                                            │        │   │
│  │   │  ├─ STEERER (全局人群计数)                        │        │   │
│  │   │  ├─ GD3A (个体定位与跨帧匹配)                     │        │   │
│  │   │  └─ pretrained/*.pth (预训练权重)                 │        │   │
│  │   └──────────────────────────────────────────────────┘        │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────── 算法训练/测试 ───────────────────────────┐   │
│  │                                                                │   │
│  │   train.py ──────────► Video_Counter (VIC.py)                  │   │
│  │       │                    ├─ 编码器: gvt.py (PCViT/VGG/ResNet)│   │
│  │       │                    ├─ 匹配层: optimal_transport_layer  │   │
│  │       │                    ├─ 解码器: decoder.py               │   │
│  │       │                    └─ Dustbin: dustbin_score_predictor │   │
│  │       │                                                        │   │
│  │       ▼                                                        │   │
│  │   test.py ───────────► 评估指标: MAE/MSE/WRAE/MIAE/MOAE       │   │
│  │                                                                │   │
│  │   DVTracker.py ──────► 密集人群跟踪                            │   │
│  │       │                    ├─ 投票机制 (基于 GD3A 匹配结果)     │   │
│  │       │                    └─ 匈牙利算法 (最优 ID 传递)        │   │
│  │       ▼                                                        │   │
│  │   DVTack_evaluation.py ► TrackEval → HOTA/CLEAR/Identity      │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌────────────── 数据集可视化平台 (独立) ──────────────────────┐   │
│  │                                                                │   │
│  │   Spring Boot (port 8080)                                      │   │
│  │   ├─ PageController (Thymeleaf 页面路由)                       │   │
│  │   ├─ ApiController (REST JSON API)                             │   │
│  │   ├─ VisualService (业务逻辑)                                   │   │
│  │   ├─ DataLoaderService (CSV → H2 自动加载)                     │   │
│  │   └─ H2 内嵌数据库 (data/mdc_db.mv.db)                        │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、目录结构详解

### 3.1 MovingDroneCrowd-main 顶层目录

```
MovingDroneCrowd-main/
├── config.py                    # 全局实验配置（模型类型、数据集路径、GPU、学习率等）
├── train.py                     # 训练入口（支持 SDNet / GD3A 两种模型）
├── test.py                      # 测试入口（VIC 评估：MAE/MSE/MIAE/MOAE 等）
├── DVTracker.py                 # DVTrack 密集人群跟踪器（基于 GD3A 匹配结果）
├── DVTack_evaluation.py         # 跟踪评估脚本（调用 TrackEval 计算 HOTA/CLEAR/Identity）
├── requirements.txt             # Python 依赖（PyTorch, mmcv, timm, opencv 等）
├── setup.sh                     # 一键部署脚本（安装依赖 + 启动后端/前端）
├── run_commands.txt             # 完整的运行命令参考手册
│
├── model/                       # 【核心模型目录】见 3.2 节
├── cusdatasets/                 # 【数据集加载】见 3.3 节
├── misc/                        # 【工具函数】见 3.4 节
├── TrackEval/                   # 【跟踪评估库】见 3.5 节
│
├── pretrained/                  # 预训练模型权重（.pth 文件）
├── exp/                         # 实验输出（训练日志、checkpoint）
├── figures/                     # 论文图片（SDNet.jpg, GD3A.png）
├── dataset/                     # 测试用样例图片
│
├── platform_backend/            # 【推理后端 API】见 3.6 节
└── platform_frontend/           # 【推理前端 UI】见 3.7 节
```

### 3.2 model/ — 深度学习模型

```
model/
├── VIC.py                       # Video_Counter 主模型
│   # 实现 VIC (Video Individual Counting) 算法核心流程：
│   #   1. 编码器提取帧特征
│   #   2. 最优传输匹配层建立像素级对应
│   #   3. 解码器输出共享/流入/流出密度图
│   # 支持 SDNet 和 GD3A 两种架构切换
│
├── optimal_transport_layer.py   # 最优传输匹配层
│   # 实现 Sinkhorn 算法进行帧间描述符软匹配
│   # 包含自适应 dustbin 机制过滤背景噪声
│
├── gvt.py                       # Group Vision Transformer
│   # PCViT 骨干网络：结合卷积和 Transformer
│   # 作为 VIC 模型的编码器，提取多尺度特征
│
├── decoder.py                   # 解码器模块
│   # ShareDecoder:  共享解码器（预测共享密度图）
│   # InOutDecoder:  流入/流出解码器（预测帧间变化）
│   # GlobalDecoder: 全局解码器（预测全局计数）
│
├── dustbin_score_predictor.py   # 自适应 Dustbin 分数预测器
│   # 动态学习匹配阈值，区分前景行人 vs 背景
│
├── points_from_den.py           # 密度图 → 关键点提取
│   # 从密度图中检测局部峰值，输出行人位置坐标
│
├── density_estimator/           # 密度估计器
│   ├── MyCounter.py             # 自定义密度估计器（实验性）
│   ├── CSRNet.py                # CSRNet 实现（经典人群计数模型）
│   └── STEERER/                 # STEERER 全局计数器
│       # HRNet + ViT 混合骨干
│       # 用于推理服务平台的全局计数
│
├── VGG/VGG16_FPN.py             # VGG16 + FPN 特征提取器（Stride 8/16）
├── ResNet/ResNet50_FPN.py       # ResNet50 + FPN 特征提取器
├── ViT/                         # Cross-Attention 模块（SDNet 用）
├── MatchTool/                   # 匹配工具（计算匹配指标）
├── PreciseRoIPooling/           # 精确 RoI Pooling（PyTorch + TensorFlow）
└── necks/fpn.py                 # FPN 颈部模块
```

### 3.3 cusdatasets/ — 数据集加载

```
cusdatasets/
├── __init__.py                  # 数据增强流水线 + DataLoader 构建
├── dataset.py                   # 数据集基类（帧对加载、标注解析）
├── samplers.py                  # 分布式采样器（DistributedSampler）
└── setting/
    └── MovingDroneCrowd.py      # MovingDroneCrowd++ 数据集配置
        # 数据集路径、图片尺寸、Batch Size、帧间隔等
        # 支持 train/val/test 划分
```

### 3.4 misc/ — 工具函数

```
misc/
├── utils.py                     # 核心工具
│   # 学习率调度、日志记录、指标计算（MAE/MSE/WRAE/MIAE/MOAE）
│   # 模型保存/加载、可视化工具
├── tools.py                     # 分布式初始化、随机种子设置
├── transforms.py                # 数据变换（随机裁剪、翻转、缩放、归一化）
├── layer.py                     # 自定义网络层（GaussianLayer 等）
├── pos_embed.py                 # 位置编码
├── post_process.py              # 后处理（密度图 → 计数/定位）
├── nms.py                       # 非极大值抑制
├── get_bbox.py                  # 密度图 → 边界框提取
├── KPI_pool.py                  # KPI Pooling 实现
└── evaluation_code.py           # 评估代码辅助
```

### 3.5 TrackEval/ — 跟踪评估库

```
TrackEval/
├── trackeval/
│   ├── eval.py                  # 评估器主入口
│   ├── metrics/                 # 评估指标
│   │   ├── hota.py              # HOTA (Higher Order Tracking Accuracy)
│   │   ├── clear.py             # CLEAR (MOTA/MOTP)
│   │   └── identity.py          # Identity (IDF1/IDP/IDR)
│   ├── datasets/                # 数据集适配器（MOT Challenge 格式等）
│   └── utils.py                 # 评估工具
└── scripts/                     # 各数据集评估脚本
```

### 3.6 platform_backend/ — 推理后端 API

```
platform_backend/
├── run.py                       # 启动入口：uvicorn app.main:app
├── requirements.txt             # FastAPI, uvicorn, python-multipart 等
├── app/
│   ├── main.py                  # FastAPI 应用初始化
│   │   # 挂载 API 路由、静态文件服务
│   │   # SPA 回退：非 API 请求返回前端 index.html
│   ├── config.py                # 配置
│   │   # 模型路径、GPU 设备、上传文件大小限制
│   ├── db.py                    # SQLite 数据库
│   │   # 任务表（task_id, status, progress, params）
│   │   # 结果表（frame_id, count, bboxes 等）
│   ├── api/
│   │   └── video.py             # API 路由
│   │       # POST /api/upload        — 上传视频/图片
│   │       # POST /api/infer         — 启动推理任务
│   │       # GET  /api/tasks/{id}    — 查询任务状态
│   │       # GET  /api/results/{id}  — 获取推理结果
│   │       # WS   /ws/progress/{id}  — WebSocket 实时进度
│   ├── services/
│   │   └── inference_service.py # 推理引擎
│   │       # 单例模式加载 STEERER + GD3A 模型
│   │       # 逐帧推理：密度图 → 峰值检测 → 标注框
│   │       # 通过 WebSocket 推送实时进度
│   └── schemas/
│       └── models.py            # Pydantic 数据模型
├── uploads/                     # 上传文件存储
└── results/                     # 推理结果存储（JSON + 标注图片）
```

### 3.7 platform_frontend/ — 推理前端 UI

```
platform_frontend/
├── vite.config.js               # Vite 配置
│   # 开发代理：/api, /uploads, /results → localhost:8000
│   # 生产端口：8080
├── package.json                 # 依赖：Vue 3, axios, echarts, vue-router
├── index.html                   # HTML 入口
└── src/
    ├── main.js                  # Vue 应用入口
    ├── App.vue                  # 主布局（导航栏、主题切换、全局状态）
    ├── router.js                # 前端路由（7 个页面）
    ├── style.css                # 全局样式（暗色主题）
    ├── echartsTheme.js          # ECharts 自定义主题
    └── pages/
        ├── Dashboard.vue        # 仪表盘
        │   # 视频/图片上传、推理参数设置
        │   # 实时推理进度条（WebSocket）
        │   # 结果概览统计卡片
        ├── FrameAnalysis.vue    # 逐帧分析
        │   # 帧列表浏览、标注框叠加显示
        │   # 单帧人数统计、帧间对比
        ├── HeatmapView.vue      # 密度热力图
        │   # 密度图叠加在原始帧上
        │   # 可调节透明度、颜色映射
        ├── TrajectoryView.vue   # 轨迹追踪
        │   # 行人轨迹在 2D 平面上的投影
        │   # 单行人速度/方向分析
        ├── SpatialAnalysis.vue  # 空间分析
        │   # 人群空间分布热力图
        │   # 密度区域划分、热点检测
        ├── TemporalAnalysis.vue # 时序分析
        │   # 人数随时间变化曲线
        │   # 流入/流出率分析
        │   # 人数分布直方图
        └── ComparisonView.vue   # 对比分析
            # 多模型/多参数结果对比
            # 并排展示、指标对比表
```

---

## 四、核心算法详解

### 4.1 三种模型

| 模型 | 任务 | 核心思想 | 骨干网络 |
|------|------|---------|---------|
| **SDNet** | 视频个体计数 (VIC) | 跨帧注意力 + 共享/流入/流出密度图分解 | VGG16 + FPN |
| **GD3A** | 视频个体计数 (VIC) | 最优传输匹配 + 分组描述符关联 + 自适应 Dustbin | VGG16 / ResNet50 + FPN |
| **DVTrack** | 密集人群跟踪 | 基于 GD3A 匹配结果，投票机制 + 匈牙利算法 | 复用 GD3A |

### 4.2 GD3A 工作流程

```
帧 t 图片 ──► 编码器 ──► 描述符 D_t ──┐
                                       ├──► Sinkhorn 最优传输 ──► 匹配矩阵 M
帧 t+1 图片 ─► 编码器 ──► 描述符 D_{t+1} ┘        │
                                                    ▼
                    ┌─────────────────────────────────────┐
                    │  自适应 Dustbin Score               │
                    │  过滤背景噪声，保留前景匹配          │
                    └─────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────────────────────┐
                    │  分组投票 (Group Voting)             │
                    │  将描述符按空间归属分配给行人中心    │
                    │  构建投票矩阵                        │
                    └─────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────────────────────┐
                    │  解码器                              │
                    │  ├─ 共享密度图 (Shared Density)      │
                    │  ├─ 流入密度图 (Inflow Density)      │
                    │  └─ 流出密度图 (Outflow Density)     │
                    └─────────────────────────────────────┘
```

### 4.3 DVTrack 跟踪流程

```
GD3A 匹配结果
      │
      ▼
┌──────────────────────┐
│  描述符空间归属分配   │  ← 将匹配的描述符分配给最近的行人中心
└──────────────────────┘
      │
      ▼
┌──────────────────────┐
│  投票矩阵构建         │  ← 每个描述符对候选 ID 投票
└──────────────────────┘
      │
      ▼
┌──────────────────────┐
│  匈牙利算法           │  ← 求解最优 ID 传递（最小代价二分匹配）
└──────────────────────┘
      │
      ▼
┌──────────────────────┐
│  跟踪轨迹输出         │  ← MOT 格式：frame_id, track_id, x, y, w, h
└──────────────────────┘
```

---

## 五、数据集说明

### 5.1 MovingDroneCrowd++ 数据集

- **来源**：无人机航拍视频
- **标注格式**：MOT 风格 CSV（`frame_id, person_id, x, y, w, h`）
- **帧索引**：从 0 开始，图片从 `1.jpg` 开始命名
- **场景属性**：密度等级、光照条件、拍摄位置等

### 5.2 评估指标

| 类别 | 指标 | 含义 |
|------|------|------|
| VIC 计数 | MAE | 平均绝对误差 |
| VIC 计数 | MSE | 均方误差 |
| VIC 计数 | WRAE | 加权相对绝对误差 |
| VIC 计数 | MIAE | 平均流入绝对误差 |
| VIC 计数 | MOAE | 平均流出绝对误差 |
| 跟踪 | HOTA | 高阶跟踪准确度 |
| 跟踪 | MOTA | 多目标跟踪准确度 |
| 跟踪 | MOTP | 多目标跟踪精确度 |
| 跟踪 | IDF1 | ID F1 分数 |

---

## 六、系统运行方式

### 6.1 环境准备（首次运行必须）

#### 6.1.1 安装 Python 依赖

```bash
# 进入项目根目录
cd /workspace/MovingDroneCrowd-main

# 安装 mmcv（注意使用 --no-build-isolation 避免编译问题）
pip install --no-build-isolation mmcv==1.7.1

# 安装 numpy（版本兼容性）
pip install numpy==1.26.4

# 安装 timm（PyTorch >= 2.4 需要升级版本）
pip install timm==1.0.27

# 安装 pycocotools
pip install Cython
pip install pycocotools==2.0 --no-build-isolation

# 安装主依赖
pip install -r requirements.txt

# 安装后端 API 依赖
cd platform_backend
pip install -r requirements.txt
```

#### 6.1.2 下载 VGG16 骨干网络权重（可选，避免自动下载超时）

```bash
mkdir -p ~/.cache/torch/hub/checkpoints/
wget -c "https://download.pytorch.org/models/vgg16_bn-6c64b313.pth" \
    -O ~/.cache/torch/hub/checkpoints/vgg16_bn-6c64b313.pth
```

#### 6.1.3 下载数据集（如需训练/测试）

```bash
# 从 HuggingFace 镜像下载
wget -c "https://hf-mirror.com/datasets/fyw1999/MovingDroneCrowd/resolve/main/MovingDroneCrowd%2B%2B.zip?download=true" \
    -O MovingDroneCrowd++.zip
unzip -o MovingDroneCrowd++.zip

# 修改数据集路径配置
# 编辑 cusdatasets/setting/MovingDroneCrowd.py
# 将 __C_MDC.DATA_PATH 改为你的数据集实际路径
```

#### 6.1.4 下载预训练模型权重

```bash
# 从 HuggingFace 下载后放入 pretrained/ 目录：
#   - GD3A_MDC++_best_model_VGG16.pth
#   - GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth
#   - GD3A_MDC++_best_model_ResNet50.pth (可选)

# ⚠️ 注意：文件名中的 + 号下载后可能被 URL 编码为 %2B，需要重命名：
# cd pretrained
# mv 'GD3A_MDC%2B%2B_best_model_VGG16.pth' 'GD3A_MDC++_best_model_VGG16.pth'
# mv 'GD3A_pre_trained_global_counter_STEERER_MDC%2B%2B_ep_201_mae_13.5_mse_19.1.pth' \
#     'GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth'
```

---

### 6.2 推理服务平台（推荐用户使用）

> **端口规划**：后端 8000，前端开发模式 8080（自动代理到 8000）
>
> **生产模式**：仅需后端 8000 端口（自动 serve 前端静态文件）

#### 6.2.1 启动后端

```bash
cd /workspace/MovingDroneCrowd-main/platform_backend

# 默认启动（端口 8000）
python run.py

# 开发模式（热重载，代码改动自动重启）
python run.py --reload

# 指定端口
python run.py --port 9000

# 启动后可访问：
#   API 文档:  http://localhost:8000/docs
#   后端服务:  http://localhost:8000
```

#### 6.2.2 启动前端（开发模式）

```bash
cd /workspace/MovingDroneCrowd-main/platform_frontend

# 安装依赖（首次）
npm install

# 启动开发服务器
npm run dev
# Vite 运行在 http://localhost:8080
# 自动代理 /api, /uploads, /results 请求到后端 localhost:8000
```

#### 6.2.3 一键部署脚本（生产模式）

```bash
cd /workspace/MovingDroneCrowd-main
bash setup.sh

# 脚本自动完成：
#   1. 安装后端 Python 依赖
#   2. 安装前端 npm 依赖
#   3. 构建前端 npm run build
#   4. 提示启动命令

# 部署后访问 http://localhost:8000 即可（后端自动 serve 前端 dist/）
```

#### 6.2.4 手动生产部署

```bash
# 步骤 1：构建前端
cd /workspace/MovingDroneCrowd-main/platform_frontend
npm install
npm run build
# 产物输出到 dist/ 目录

# 步骤 2：启动后端（自动 serve 前端 dist/）
cd /workspace/MovingDroneCrowd-main/platform_backend
python run.py

# 访问 http://localhost:8000 即可使用完整系统
```

#### 6.2.5 使用流程

```
1. 浏览器访问 http://localhost:8000（或前端开发模式 http://localhost:8080）
2. 进入 Dashboard 页面上传无人机航拍视频/图片
3. 设置推理参数（帧间隔、阈值等）
4. 点击"开始推理"，WebSocket 实时显示进度
5. 推理完成后自动跳转结果页：
   ├─ 逐帧分析 (FrameAnalysis)     — 查看每帧标注结果
   ├─ 密度热力图 (HeatmapView)     — 密度分布可视化
   ├─ 轨迹追踪 (TrajectoryView)    — 行人运动轨迹
   ├─ 空间分析 (SpatialAnalysis)   — 空间分布分析
   ├─ 时序分析 (TemporalAnalysis)  — 人数随时间变化
   └─ 对比分析 (ComparisonView)    — 多结果对比
```

---

### 6.3 算法训练（研究人员使用）

#### 6.3.1 配置文件说明

```bash
# 编辑 config.py 修改以下关键参数：
#   __C.MODEL          — 模型选择：GD3A / SDNet
#   __C.DATASET        — 数据集：MovingDroneCrowd
#   __C.encoder        — 骨干网络：VGG16_FPN / ResNet50_FPN
#   __C.GPU_ID         — GPU 编号，如 '0' 或 '0,1,2,3'
#   __C.LR_Base        — 学习率，默认 5e-5
#   __C.MAX_EPOCH      — 最大训练轮数，默认 20
#   __C.global_counter — 全局计数器：STEERER
```

#### 6.3.2 训练 GD3A 模型

```bash
cd /workspace/MovingDroneCrowd-main

# 使用 VGG16 骨干网络（默认配置）
python train.py

# 训练输出：
#   日志:     exp/MovingDroneCrowd/{EXP_NAME}/log.txt
#   Checkpoint: exp/MovingDroneCrowd/{EXP_NAME}/ckpt/
#   TensorBoard: tensorboard --logdir exp/
```

#### 6.3.3 断点续训

```bash
# 在 config.py 中设置：
#   __C.RESUME = True
#   __C.RESUME_PATH = 'exp/MovingDroneCrowd/xxx/ckpt/xxx.pth'
python train.py
```

---

### 6.4 模型测试与评估（研究人员使用）

#### 6.4.1 GD3A 计数测试

```bash
cd /workspace/MovingDroneCrowd-main

# VGG16 backbone 测试
python3 test.py \
    --MODEL GD3A \
    --DATASET MovingDroneCrowd \
    --model_path ./pretrained/GD3A_MDC++_best_model_VGG16.pth \
    --counter STEERER \
    --pre_trained_counter_path "./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth" \
    --output_dir test_results \
    --test_name gd3a_vgg16 \
    --GPU_ID 0

# 预期输出（VGG16）：
#   MAE: 45.75  MSE: 73.77  WRAE: 22.97
#   Single Image MAE: 16.70  MSE: 29.26
```

#### 6.4.2 带可视化的测试（保存密度图）

```bash
# 需要先安装 imagecodecs
pip install imagecodecs

python3 test.py \
    --MODEL GD3A \
    --DATASET MovingDroneCrowd \
    --model_path ./pretrained/GD3A_MDC++_best_model_VGG16.pth \
    --counter STEERER \
    --pre_trained_counter_path "./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth" \
    --output_dir test_results \
    --test_name gd3a_vgg16_visual \
    --GPU_ID 0 \
    --test_visual True
```

#### 6.4.3 生成标注可视化（框 + ID）

```bash
# 基于 Ground Truth 生成带框和 ID 的标注可视化
python3 vis_boxes.py \
    --split MovingDroneCrowd++/test.txt \
    --max_scenes 50 \
    --max_frames 30

# 输出目录：vis_boxes/
#   *_vis.jpg   — 带框 + ID 的标注图
#   *_zoom.jpg  — 局部放大图
```

#### 6.4.4 离线视频处理

```bash
# 直接对无人机视频进行推理，输出带标注的视频
python3 video_demo.py \
    --video /path/to/your/drone_video.mp4 \
    --output output_annotated.mp4 \
    --model_path ./pretrained/GD3A_MDC++_best_model_VGG16.pth \
    --counter_path ./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth \
    --interval 4 \
    --GPU_ID 0

# 参数说明：
#   --video      输入视频路径
#   --output     输出视频路径
#   --interval   每隔多少帧做一次推理（默认4，越小越密但越慢）
#   --zoom       是否生成局部放大效果（默认开启）
#   --zoom_scale 放大倍数（默认 2.5）
```

---

### 6.5 跟踪与评估（研究人员使用）

#### 6.5.1 运行 DVTrack 跟踪

```bash
cd /workspace/MovingDroneCrowd-main

# 生成跟踪结果（基于 GD3A 匹配结果 + 匈牙利算法）
python DVTracker.py

# 输出：MOT 格式的跟踪文件（frame_id, track_id, x, y, w, h）
```

#### 6.5.2 跟踪性能评估

```bash
# 使用 TrackEval 评估 HOTA / CLEAR / Identity 指标
python DVTack_evaluation.py

# 评估指标：
#   HOTA     — 高阶跟踪准确度（综合检测 + 关联）
#   MOTA     — 多目标跟踪准确度
#   MOTP     — 多目标跟踪精确度
#   IDF1     — ID 保持 F1 分数
```

---

### 6.6 数据集可视化平台（独立运行）

#### 6.6.1 环境要求

- **JDK 17+**
- **Maven 3.6+**

#### 6.6.2 启动方式

```bash
cd /workspace/mdc-visual-platform

# 方式一：Maven 运行（开发模式，支持热重载）
mvn spring-boot:run

# 方式二：打包运行（生产模式）
mvn clean package -DskipTests
java -jar target/mdc-visual-platform-1.0.0.jar

# 启动后访问 http://localhost:8080

# ⚠️ 注意：需要确保 application.properties 中配置的数据集路径存在：
#   mdc.data.path=/workspace/MovingDroneCrowd++
#   启动时会自动将 CSV 标注文件加载到 H2 数据库
```

#### 6.6.3 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 数据集概览统计、ECharts 图表 |
| 场景浏览 | `/scenes` | 筛选场景（密度/光照/位置）、卡片列表 |
| 帧查看器 | `/viewer` | Canvas 标注框叠加 + 逐帧播放 |
| 密度热力图 | `/heatmap` | Canvas 热力图叠加在原图上 |
| 轨迹追踪 | `/trajectory` | 2D 轨迹投影 + 速度曲线 |
| 统计分析 | `/stats` | 散点图、饼图、柱状图分析 |

#### 6.6.4 调试工具

```bash
# H2 数据库控制台
# 访问 http://localhost:8080/h2-console
# JDBC URL: jdbc:h2:file:./data/mdc_db
# 用户名: sa，密码: (空)
```

---

### 6.7 完整运行命令速查表

```bash
# ==================== 推理服务平台 ====================

# 启动后端 API
cd /workspace/MovingDroneCrowd-main/platform_backend && python run.py

# 启动前端（开发）
cd /workspace/MovingDroneCrowd-main/platform_frontend && npm run dev

# 一键部署
cd /workspace/MovingDroneCrowd-main && bash setup.sh

# ==================== 算法训练与测试 ====================

# 训练
cd /workspace/MovingDroneCrowd-main && python train.py

# 测试（GD3A + VGG16）
python3 test.py --MODEL GD3A --DATASET MovingDroneCrowd \
    --model_path ./pretrained/GD3A_MDC++_best_model_VGG16.pth \
    --counter STEERER \
    --pre_trained_counter_path "./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth" \
    --output_dir test_results --test_name gd3a_vgg16 --GPU_ID 0

# 测试（带可视化）
python3 test.py --MODEL GD3A --DATASET MovingDroneCrowd \
    --model_path ./pretrained/GD3A_MDC++_best_model_VGG16.pth \
    --counter STEERER \
    --pre_trained_counter_path "./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth" \
    --output_dir test_results --test_name gd3a_vgg16_visual \
    --GPU_ID 0 --test_visual True

# 标注可视化
python3 vis_boxes.py --split MovingDroneCrowd++/test.txt \
    --max_scenes 50 --max_frames 30

# 离线视频处理
python3 video_demo.py --video /path/to/video.mp4 \
    --output output.mp4 \
    --model_path ./pretrained/GD3A_MDC++_best_model_VGG16.pth \
    --counter_path ./pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth \
    --interval 4 --GPU_ID 0

# 跟踪
cd /workspace/MovingDroneCrowd-main && python DVTracker.py

# 跟踪评估
cd /workspace/MovingDroneCrowd-main && python DVTack_evaluation.py

# ==================== 数据集可视化 ====================

cd /workspace/mdc-visual-platform && mvn spring-boot:run

# ==================== 环境安装 ====================

pip install --no-build-isolation mmcv==1.7.1
pip install numpy==1.26.4 timm==1.0.27
pip install Cython && pip install pycocotools==2.0 --no-build-isolation
pip install -r /workspace/MovingDroneCrowd-main/requirements.txt
pip install -r /workspace/MovingDroneCrowd-main/platform_backend/requirements.txt
cd /workspace/MovingDroneCrowd-main/platform_frontend && npm install
```

---

## 七、技术栈总览

| 层次 | 技术 | 版本 |
|------|------|------|
| 深度学习框架 | PyTorch | 2.4.1 |
| 计算机视觉库 | mmcv, opencv | - |
| Vision Transformer | timm | - |
| 后端 API | FastAPI + uvicorn | - |
| 实时通信 | WebSocket | - |
| 数据库 | SQLite (推理平台) | - |
| 前端框架 | Vue 3 + Vite | - |
| 图表可视化 | ECharts 5 | - |
| 路由 | vue-router 4 | - |
| Java 框架 | Spring Boot | 3.2.0 |
| Java 模板引擎 | Thymeleaf | - |
| Java 数据库 | H2 (内嵌) | - |
| Java 构建工具 | Maven | - |
| Java 版本 | JDK 17 | - |

---

## 八、依赖关系图

```
                    ┌──────────────────┐
                    │   pretrained/     │
                    │   (.pth 权重)     │
                    └────────┬─────────┘
                             │ 被加载
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       model/                                 │
│  ┌──────────┬──────────────┬───────────┬─────────────────┐  │
│  │ VIC.py   │ decoder.py   │ gvt.py    │ density_est/    │  │
│  │ (主模型) │ (解码器)     │ (编码器)  │ (密度估计器)    │  │
│  └────┬─────┴──────┬───────┴─────┬─────┴────────┬────────┘  │
│       │            │             │              │            │
│       ▼            ▼             ▼              ▼            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ optimal_transport_layer.py + dustbin_score_predictor │   │
│  │ (最优传输匹配层)                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                     │
         ▼                     ▼
┌──────────────┐    ┌──────────────────────┐
│ train.py     │    │ platform_backend/     │
│ test.py      │    │ (推理 API 服务)       │
│ DVTracker.py │    │         │             │
└──────┬───────┘    │         ▼             │
       │            │ platform_frontend/    │
       ▼            │ (Vue 3 前端)          │
┌──────────────┐    └──────────────────────┘
│ TrackEval/   │
│ (评估指标)   │
└──────────────┘

┌──────────────────────┐        ┌──────────────────────┐
│ mdc-visual-platform/ │        │ cusdatasets/          │
│ (数据集浏览, 独立)   │        │ (数据加载与增强)      │
└──────────────────────┘        └──────────────────────┘
```

---

## 九、快速参考

| 你想做什么 | 去哪里 |
|-----------|--------|
| 修改模型架构 | `model/VIC.py`, `model/gvt.py`, `model/decoder.py` |
| 调整训练参数 | `config.py` |
| 添加新数据集 | `cusdatasets/setting/` |
| 修改推理 API | `platform_backend/app/api/video.py` |
| 修改推理逻辑 | `platform_backend/app/services/inference_service.py` |
| 修改前端页面 | `platform_frontend/src/pages/` |
| 修改前端路由 | `platform_frontend/src/router.js` |
| 浏览数据集标注 | 启动 `mdc-visual-platform` |
| 评估跟踪结果 | `TrackEval/` + `DVTack_evaluation.py` |
| 查看预训练权重 | `pretrained/` |
| 部署到生产 | `setup.sh` 或按 6.1 节步骤 |
