# 无人机视角动态密集人群计数与时空分布分析系统

## 项目介绍文档

---

## 一、项目概述

本项目是一个完整的**无人机视角人群计数、定位与跟踪系统**，集成了四种先进的深度学习模型，并提供了一个可视化 Web 推理平台。系统支持对无人机航拍视频进行实时人群密度估计、个体计数、目标检测与跨帧跟踪，适用于城市安防、大型活动监控、灾害应急响应等场景。

### 核心特性

- **四种模型可选**：STEERER 密度估计、GD³A 个体计数与跟踪、STNNet 目标跟踪与定位、YOLO11 行人检测
- **完整 Web 平台**：FastAPI 后端 + Vue 3 前端，支持视频上传、实时推理、结果可视化
- **数据集标准化评测**：支持 MovingDroneCrowd++ 数据集批量测试与自定义帧测试
- **丰富可视化**：密度热力图、轨迹追踪、空间分布分析、时序变化曲线、ROI 放大对比

---

## 二、系统架构

本项目采用**双后端 + 双前端**的微服务架构，包含 Python 推理后端和 Java 数据可视化后端两个独立的子系统。

```
┌─────────────────────────────────────────────────────────────────┐
│                     Python 推理子系统                              │
│                                                                   │
│  ┌─────────────────────┐     ┌─────────────────────────────────┐ │
│  │   前端 (Vue 3)       │     │       后端 (FastAPI)             │ │
│  │   Dashboard          │◄───►│  /api/v1/video/*  视频处理      │ │
│  │   热力图/轨迹/空间    │     │  /api/v1/dataset/* 数据集测试   │ │
│  │   时序/对比分析       │     │  WebSocket 实时进度推送         │ │
│  │   端口: 8080          │     │  端口: 8000                     │ │
│  └─────────────────────┘     └──────────────┬──────────────────┘ │
│                                              │                    │
│                              ┌───────────────┴───────────────┐   │
│                              │          推理引擎               │   │
│                              │  STEERER │ GD³A │ STNNet │ YOLO │   │
│                              └───────────────┬───────────────┘   │
│                                              │                    │
│                              ┌───────────────┴───────────────┐   │
│                              │      SQLite 数据存储            │   │
│                              │   tasks 表 │ results 表         │   │
│                              └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Java 数据可视化子系统                           │
│                                                                   │
│  ┌─────────────────────┐     ┌─────────────────────────────────┐ │
│  │   前端 (Thymeleaf)   │     │    后端 (Spring Boot)            │ │
│  │   场景浏览            │◄───►│  REST API: 场景/帧/标注/轨迹    │ │
│  │   帧标注查看          │     │  Service: 数据加载/可视化       │ │
│  │   热力图/轨迹/统计    │     │  端口: 8080 (独立部署)          │ │
│  └─────────────────────┘     └──────────────┬──────────────────┘ │
│                                              │                    │
│                              ┌───────────────┴───────────────┐   │
│                              │      H2 内嵌文件数据库           │   │
│                              │   Scene │ Annotation 实体       │   │
│                              └───────────────────────────────┘   │
│                                              │                    │
│                              ┌───────────────┴───────────────┐   │
│                              │   MovingDroneCrowd++ 数据集     │   │
│                              │   frames/ + annotations/        │   │
│                              └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | Python 推理子系统 | Java 可视化子系统 |
|------|-------------------|-------------------|
| 深度学习框架 | PyTorch | — |
| 后端框架 | **FastAPI + Uvicorn** (Python) | **Spring Boot 3.2.0** (Java 17) |
| 前端框架 | **Vue 3 + Vite 5** | **Thymeleaf** 模板引擎 |
| 数据可视化 | ECharts 5 + ECharts-GL | 原生 HTML/CSS/JS + 图表库 |
| 数据库 | SQLite | **H2** 内嵌文件数据库 |
| 实时通信 | WebSocket | REST API |
| 目标检测 | Ultralytics YOLO11 | — |
| 构建工具 | — | **Maven** |
| 编译产物 | Python 脚本 | JAR 包 (45.66 MB) |

---

## 三、模型详细介绍

### 3.1 STEERER — 全局密度估计器

#### 概述

STEERER 是一个基于 HRNet-48 骨干网络的**图像级人群密度图估计器**，由 Microsoft 研究院开发（MIT License）。在本系统中，STEERER 作为 GD³A 模型的"全局计数器"组件，负责从单帧无人机航拍图像中估计人群密度图，从而进行人群计数和个体定位。

#### 架构设计

```
输入图像 (RGB)
    │
    ▼
HRNet-48 骨干网络 (高分辨率特征保持)
    │
    ├── 4 级多分辨率特征 (x4, x8, x16, x32)
    │
    ▼
MOE (混合专家) 模块
    ├── 每个分辨率级别独立计数头 (CountingHead)
    ├── Patch 级路由网络 (4 路 softmax)
    └── 自底向上多分辨率特征融合
    │
    ▼
密度图 (下采样 8x, 密度因子 100)
    │
    ▼
峰值检测 → 个体位置坐标
```

#### 关键技术

- **MOE (Mixture of Experts)**：4 个分辨率级别的计数头，通过 patch 级路由自适应选择最佳分辨率进行密度估计
- **HRNet-48 骨干**：保持高分辨率特征表示，适合密集人群场景
- **CountingHead**：多通道融合解码器，逐级上采样输出密度图

#### 模型参数

| 参数 | 值 |
|------|------|
| 骨干网络 | HRNet-48 |
| 下采样倍率 | 8x |
| 密度因子 | 100 |
| 分辨率级别数 | 4 |
| 输入路由尺寸 | 256×256 |

#### 预训练权重

| 文件 | 大小 | 性能 |
|------|------|------|
| `GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth` | 247.66 MB | MAE=13.5, MSE=19.1 (MDC++) |

#### 论文引用

STEERER 是 GD³A 论文的组成部分：
- Fan, Y. et al. "Video Individual Counting and Tracking from Moving Drones: A Benchmark and Methods", arXiv:2601.12500, 2026.

---

### 3.2 GD³A — 群体描述符密度分解关联模型

#### 概述

GD³A（**G**roup-wise **D**escriptor **D**ensity **D**ecomposition **A**ssociation）是 ICCV 2025 Highlight 论文的核心方法。它通过**最优传输（Optimal Transport）**建立帧间像素级描述符匹配，再用**分组关联**将全局密度图分解为共享、流入和流出密度图，实现视频级别的个体计数。

GD³A 是 SDNet（会议版方法）的改进版本，主要优势在于：可解释性更强、训练速度更快、GPU 内存占用更低。

#### 架构设计

```
输入: 连续两帧图像
    │
    ▼
┌─────────────────────────────────────┐
│  1. 特征提取 (VGG16-FPN / ResNet50-FPN) │
│     输出: 256 维特征图 (stride=8)        │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  2. 全局密度估计 (STEERER, 冻结)       │
│     输出: 全局密度图 → 背景过滤         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  3. 最优传输匹配层                     │
│     ├── KeypointEncoder (位置编码 MLP) │
│     ├── AttentionalGNN (18层注意力GNN) │
│     ├── DustbinScorePredictor (自适应阈值) │
│     └── Sinkhorn 算法 (最优传输求解)   │
│     输出: 像素级软匹配矩阵              │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  4. 双向 top-K 互检验                 │
│     确保匹配的相互一致性               │
└─────────────────────────────────────┘
    │
    ├── 匹配成功的点 → 共享密度图 (Shared Density)
    └── 匹配失败的点 → 流入/流出密度图 (In/Out Flow)
```

#### 核心技术

- **最优传输匹配**：将帧间个体匹配建模为最优传输问题，使用 Sinkhorn 算法求解，输出软匹配矩阵
- **AttentionalGNN**：18 层图神经网络（9 层 self-attention + 9 层 cross-attention），增强像素级描述符的判别能力
- **DustbinScorePredictor**：Transformer 编码器 + MLP，自适应预测 Sinkhorn 算法的"垃圾箱"分数，控制匹配严格程度
- **分组密度分解**：根据匹配结果将全局密度图分解为共享/流入/流出三部分，实现视频级计数

#### 模型变体

| 模型 | 骨干网络 | 权重文件 | 大小 | 性能 (MAE/RMSE) |
|------|----------|----------|------|-------------------|
| GD³A-VGG16 | VGG16 + FPN | `GD3A_MDC++_best_model_VGG16.pth` | 131.62 MB | 45.23 / 73.27 |
| GD³A-ResNet50 | ResNet50 + FPN | `GD3A_MDC++_best_model_ResNet50.pth` | 168.43 MB | 40.11 / 71.61 |

#### DVTrack 跟踪器

DVTrack 是基于 GD³A 匹配结果的**无额外训练**的密集人群跟踪器：
1. 从密度图提取峰值 → 行人位置
2. GD³A 描述符匹配结果 → 描述符归属关联
3. 构建行人级投票矩阵 → 匈牙利算法求解最优 ID 传递
4. 新出现的人分配新 ID

#### 论文引用

```bibtex
@article{MDC++_GD3A,
  title={Video Individual Counting and Tracking from Moving Drones: A Benchmark and Methods},
  author={Fan, Yaowu and Wan, Jia and Han, Tao and Ma, Andy J. and Ouyang, Wanli and Chan, Antoni B.},
  journal={arXiv preprint arXiv:2601.12500},
  year={2026}
}

@inproceedings{fan2025video,
  title={Video Individual Counting for Moving Drones},
  author={Fan, Yaowu and Wan, Jia and Han, Tao and Chan, Antoni B. and Ma, Andy J.},
  booktitle={Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)},
  month={October},
  year={2025},
  pages={12284--12293}
}
```

---

### 3.3 STNNet — 时空邻居感知网络

#### 概述

STNNet（**S**pace-**T**ime **N**eighbor-Aware **Net**work）源自 CVPR 2021 论文 *"Detection, Tracking, and Counting Meets Drones in Crowds: A Benchmark"*。它是一个**多任务、多尺度**的网络，同时支持人群计数（Counting）、定位（Localization）和跟踪（Tracking）三项任务。

#### 架构设计

```
输入: 连续两帧 RGB 图像
    │
    ▼
┌─────────────────────────────────────┐
│  VGG-16 骨干网络 (前 3 个 stage)        │
│  ├── f1: 128ch, 1/2 分辨率 (x2)        │
│  ├── f2: 256ch, 1/4 分辨率 (x4)        │
│  └── f3: 512ch, 1/8 分辨率 (x8)        │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  多尺度特征融合 (自顶向下 + 空间注意力)    │
│  ├── f3 → deconv → g2 (256ch, x4)     │
│  └── g2 → deconv → g1 (128ch, x2)     │
│  每级: SpatialWeightLayer 空间加权     │
└─────────────────────────────────────┘
    │
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│密度头   │  │  定位头    │  │  跟踪头    │  │ 关联头    │
│3 尺度   │  │  3 尺度     │  │  空间相关   │  │  GCN      │
│密度图   │  │ 定位+偏移   │  │  PointConv  │  │  图卷积    │
└────────┘  └──────────┘  └──────────┘  └──────────┘
```

#### 三个输出子网络

**A. 密度头 (Density Head)** — 始终启用
- 3 个尺度输出密度图（x2/x4/x8 分辨率）
- 加权融合：x2 权重 2.0、x4 权重 0.5、x8 权重 0.05

**B. 定位头 (Localization Head)** — `--loc` 启用
- 3 个尺度定位分类图（2 通道 softmax：前景/背景）
- 3 个尺度回归偏移图（2 通道：dx/dy 精修）
- 多尺度融合到 x2 分辨率

**C. 跟踪头 (Tracking Head)** — `--trk` 启用
- **空间相关性计算**：相邻帧特征的空间相关性（kernel=11）
- **PointConv GCN**：3 层密度感知图卷积，处理 top-128 高置信度点
  - nsample=8，bandwidth 0.1→0.2→0.4
  - 密度估计 + DensityNet + WeightNet

#### 多阶段训练策略

| 阶段 | 组件 | 说明 |
|------|------|------|
| 1. 密度预训练 | 仅密度头 | ImageNet 预训练 VGG-16 |
| 2. 定位训练 | 密度头 + 定位头 | 基于密度预训练权重 |
| 3. 时序训练 | + 跟踪头 (仅时序损失) | 冻结密度/定位参数 |
| 4. 无循环训练 | + 跟踪头 (无 cycle loss) | |
| 5. 完整训练 | + 完整跟踪 (cycle loss) | 循环一致性损失 |

#### 损失函数

- **密度损失**：MSE（3 个尺度加权）
- **定位损失**：分类交叉熵 + 偏移回归 MSE
- **跟踪损失**：时序预测损失 + 循环一致性损失 + 邻居关系约束

#### 评估指标

- **计数指标**：MAE、MSE（预测人数 vs GT 人数）
- **定位指标**：Precision、Recall（距离阈值 ≤ 10px）
- **分组评估**：按尺度、天气、密度分组统计

#### 模型权重

| 文件 | 大小 | 描述 |
|------|------|------|
| `den_model_best.pth.tar` | 114.63 MB | 仅密度头 |
| `loc_model_best.pth.tar` | 115.03 MB | 密度 + 定位 |
| `cyc_model_best.pth.tar` | 48.64 MB | 完整 STNNet（含 cycle loss） |

#### 论文引用

```bibtex
@inproceedings{dronecrowd_cvpr2021,
  author    = {Longyin Wen and Dawei Du and Pengfei Zhu and Qinghua Hu and
               Qilong Wang and Liefeng Bo and Siwei Lyu},
  title     = {Detection, Tracking, and Counting Meets Drones in Crowds: A Benchmark},
  booktitle = {CVPR},
  year      = {2021}
}
```

---

### 3.4 YOLO11 — 行人检测模型

#### 概述

YOLO11 是 Ultralytics 推出的最新一代单阶段目标检测模型，本系统集成了 **YOLO11m**（中等规模版本），并在 **VisDrone** 无人机航拍数据集上针对行人（person 类）进行了微调训练。YOLO11 通过检测框（bounding box）的方式定位每个行人，提供基于检测的人群计数方案，与密度估计路线形成互补。

#### 架构设计

```
输入: 单帧 RGB 图像
    │
    ▼
CSPDarknet 骨干网络 + C3k2 模块
    │
    ▼
SPPF (空间金字塔池化) + C2PSA (跨阶段部分自注意力)
    │
    ▼
多尺度特征金字塔 (FPN + PAN)
    │
    ▼
解耦检测头 (Decoupled Head)
    ├── 分类分支 → 类别置信度 (person 类, cls=0)
    └── 回归分支 → 边界框坐标 (x1, y1, x2, y2)
    │
    ▼
NMS 后处理 (IoU 阈值过滤)
    │
    ▼
输出: 检测框列表 [(x1, y1, x2, y2, confidence), ...]
    │
    ▼
人数统计: 检测框数量 = 人数
```

#### 核心技术

- **C3k2 模块**：改进的跨阶段特征提取模块，支持不同核大小的可配置性，在效率和精度之间取得平衡
- **C2PSA 自注意力**：跨阶段部分自注意力机制，增强全局上下文建模能力
- **解耦检测头**：分类和回归分支分离，避免任务冲突，提升检测精度
- **VisDrone 微调**：在无人机视角的 VisDrone 数据集上仅训练 person 类，专注行人检测场景

#### 模型参数

| 参数 | 值 |
|------|------|
| 模型规模 | YOLO11m (medium) |
| 训练数据 | VisDrone 无人机数据集 (仅 person 类) |
| 置信度阈值 | 0.25 |
| 输入尺寸 | 原始分辨率（无需缩放到固定尺寸） |
| 输出格式 | 边界框 (x1, y1, x2, y2, conf) |
| 计数方式 | 检测框数量 = 人数 |
| 权重文件 | `yolo11m_visdrone_person-2/weights/best.pt` |

#### 技术特点

- **端到端检测**：无需密度图中间表示，直接输出行人检测框
- **推理速度快**：单阶段检测架构，适合实时场景
- **检测框可视化**：绿色矩形框标注每个行人，直观展示检测结果
- **互补方案**：与密度估计模型（STEERER/GD³A/STNNet）形成互补，检测框方式更易于理解和审计
- **可扩展性**：YOLO 架构可轻松扩展至多类别检测场景

---

## 四、四模型对比总结

| 特性 | STEERER | GD³A | STNNet | YOLO11 |
|------|---------|------|--------|--------|
| **任务类型** | 单帧密度估计 | 视频个体计数 | 计数+定位+跟踪 | 行人检测+计数 |
| **核心机制** | HRNet + MOE | 最优传输 + 描述符匹配 | 多尺度 + 时空邻居感知 | CSPDarknet + 解耦检测头 |
| **骨干网络** | HRNet-48 | VGG16-FPN / ResNet50-FPN | VGG-16 | CSPDarknet (C3k2 + C2PSA) |
| **输入** | 单帧图像 | 连续帧对 | 连续两帧 | 单帧图像 |
| **输出** | 密度图 + 人数 | 密度图 + 个体ID + 人数 | 密度图 + 定位点 + 跟踪ID | 检测框 + 人数 |
| **计数方式** | 密度图积分 | 密度图峰值计数 | 密度图峰值计数 | 检测框数量 |
| **需要身份标注** | 否 | 是 | 是（训练时） | 否（仅需检测框标注） |
| **下采样倍率** | 8x | 8x | 2x/4x/8x 多尺度 | 无固定（自适应） |
| **计数精度 (MAE)** | 13.5 (单帧) | 40-45 (视频) | 取决于数据集 | 取决于数据集 |
| **可解释性** | 中 | 高（显式匹配） | 中 | 高（检测框直接可视化） |
| **训练复杂度** | 低 | 中 | 高（5 阶段训练） | 低（端到端单阶段） |
| **推理速度** | 中 | 中 | 较慢（多任务） | 快（单阶段） |
| **发表会议/年份** | ICCV 2025 (组件) | ICCV 2025 Highlight | CVPR 2021 | Ultralytics 2024 |
| **许可证** | MIT | 学术用途 | 学术用途 | AGPL-3.0 |

---

## 五、Java 数据可视化子系统 (Spring Boot)

### 5.1 概述

`mdc-visual-platform` 是一个独立的 **Spring Boot 3.2.0** 项目（Java 17），专门用于 **MovingDroneCrowd++ 数据集的可视化浏览与分析**。它与 Python 推理子系统完全独立部署，通过 Maven 构建管理，使用 Thymeleaf 模板引擎渲染前端页面，H2 内嵌文件数据库存储数据集元信息。

### 5.2 项目结构

```
mdc-visual-platform/
├── pom.xml                        # Maven 构建配置
├── src/main/java/com/mdc/visual/
│   ├── MdcVisualApplication.java  # Spring Boot 启动入口
│   ├── config/
│   │   └── WebConfig.java         # Web 配置（CORS、静态资源）
│   ├── controller/
│   │   ├── ApiController.java     # REST API 控制器
│   │   └── PageController.java    # 页面路由控制器
│   ├── model/
│   │   ├── Scene.java             # 场景 JPA 实体
│   │   ├── SceneRepository.java   # 场景数据仓库
│   │   ├── Annotation.java        # 标注 JPA 实体
│   │   └── AnnotationRepository.java # 标注数据仓库
│   └── service/
│       ├── DataLoaderService.java # 数据集加载服务
│       └── VisualService.java     # 可视化业务逻辑
├── src/main/resources/
│   ├── application.properties     # Spring Boot 配置
│   └── templates/                 # Thymeleaf 模板页面
└── target/
    └── mdc-visual-platform-1.0.0.jar  # 编译产物 (45.66 MB)
```

### 5.3 核心功能

| 功能模块 | 说明 |
|----------|------|
| **场景浏览** | 列出所有数据集场景，按密度等级、光照条件、场景类型分类 |
| **帧标注查看** | 逐帧查看图片和 GT 标注框（行人边界框 + 身份 ID） |
| **热力图可视化** | 展示人群密度热力图和空间分布 |
| **轨迹追踪** | 可视化个体行人跨帧运动轨迹 |
| **统计分析** | 场景级别的统计信息（总人数、密度分布等） |
| **图片服务** | 提供数据集帧图片的 HTTP 访问服务 |

### 5.4 技术特点

- **Spring Boot 3.2.0 + Java 17**：最新稳定版本，利用虚拟线程等新特性
- **JPA + H2 数据库**：Spring Data JPA 持久化，H2 内嵌文件数据库零配置启动
- **Thymeleaf 模板引擎**：服务端渲染，无需额外前端构建
- **Maven 构建管理**：标准化 Java 项目构建流程
- **独立部署**：单一 JAR 包即可运行，无需外部数据库

### 5.5 数据流向

```
MovingDroneCrowd++ 数据集
  (frames/ + annotations/)
        │
        ▼
DataLoaderService
  解析 CSV 标注 → JPA 实体
        │
        ▼
H2 数据库 (./data/mdc_db)
  Scene 表 + Annotation 表
        │
        ▼
VisualService / ApiController
  查询 + 聚合 + 处理
        │
        ▼
Thymeleaf 模板 → HTML 页面
  场景浏览 / 帧查看 / 热力图 / 轨迹 / 统计
```

---

## 六、平台功能详解

### 6.1 Python 推理子系统 — 视频推理

支持上传无人机航拍视频（.mp4/.avi/.mov/.mkv，最大 500MB），选择模型和推理模式（counting/tracking）进行分析。

**推理模式**：
- **counting（人群计数）**：输出每帧的总人数和密度图
- **tracking（个体跟踪）**：输出每帧的个体位置、ID 和轨迹

**可选模型**：
- STEERER — 全局密度估计
- GD³A + VGG16 — 个体计数与匹配
- GD³A + ResNet50 — 个体计数与匹配（更高精度）
- YOLO11 — 行人检测计数
- STNNet — 目标跟踪与定位（数据集测试）

### 6.2 数据集测试

支持 MovingDroneCrowd++ 标准化数据集测试：

- **场景测试**：直接使用数据集场景进行推理，自动对比 GT 标注
- **帧测试**：用户上传自定义帧图片 + CSV 标签进行评测
- **STNNet 测试**：使用 STNNet 模型对数据集场景或上传帧进行推理

### 6.3 可视化分析

- **密度热力图**：6 种配色方案（jet/hot/plasma/inferno/viridis/cool），叠加检测点和等高线
- **轨迹追踪**：可视化个体跨帧运动轨迹
- **空间分布分析**：人群在画面中的空间分布热力图
- **时序分析**：人数随时间变化的曲线图
- **ROI 放大对比**：自定义/自动感兴趣区域放大对比原图与预测
- **热力图视频**：批量生成密度热力图并合成视频

### 6.4 评估指标

| 指标 | 说明 |
|------|------|
| MAE | 平均绝对误差（预测人数 vs GT 人数） |
| MSE | 均方误差 |
| Accuracy | 准确率 |
| Precision | 精确率（定位点检测） |
| Recall | 召回率（定位点检测） |
| F1 Score | F1 分数 |

---

## 七、数据集

### MovingDroneCrowd++

本项目使用的主要数据集，包含无人机拍摄的密集人群视频，标注格式为 MOT-style。

**数据结构**：
```
MovingDroneCrowd++/
├── frames/
│   └── scene_X/
│       └── Y/
│           └── 1.jpg, 2.jpg, ...
├── annotations/
│   └── scene_X/
│       └── Y.csv          (MOT 格式标注)
├── train.txt              (训练集场景列表)
├── val.txt                (验证集场景列表)
├── test.txt               (测试集场景列表)
└── scene_labels.txt       (场景属性标签)
```

**标注格式** (CSV)：
```
frame_id, person_id, x, y, w, h, -1, -1, -1, -1
```

**场景属性**：
- 密度等级：0（稀疏）~ 3（密集）
- 光照条件：Daytime、Nighttime、Cloudy、Sunny
- 场景类型：Urban、Plaza、Walking Area 等

---

## 八、部署与运行

### 环境要求

**Python 推理子系统**：
- Python 3.8+
- PyTorch 1.9+
- Node.js 18+ (前端构建)
- CUDA 支持（推荐）

**Java 可视化子系统**：
- Java 17+
- Maven 3.6+

### 快速启动

#### Python 推理子系统

```bash
# 1. 安装依赖
cd /workspace/MovingDroneCrowd-main
pip install -r requirements.txt
cd platform_backend && pip install -r requirements.txt
cd ../platform_frontend && npm install

# 2. 启动 Python 后端 (端口 8000)
cd ../platform_backend
python run.py

# 3. 启动 Vue 前端 (端口 8080)
cd ../platform_frontend
npm run dev
```

#### Java 可视化子系统

```bash
# 1. 编译打包
cd /workspace/mdc-visual-platform
mvn clean package -DskipTests

# 2. 启动 Spring Boot 应用 (端口 8080，注意与 Vue 前端错开)
java -jar target/mdc-visual-platform-1.0.0.jar

# 3. 或在开发模式直接运行
mvn spring-boot:run
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| Python 推理 API | `http://localhost:8000/docs` | FastAPI Swagger 文档 |
| Vue 推理前端 | `http://localhost:8080` | 推理平台用户界面 |
| Java 可视化平台 | `http://localhost:8080` | 数据集浏览（与 Vue 前端端口一致，需分别部署） |

---

## 九、总结

本项目包含**两个独立的子系统**：

### Python 推理子系统
整合了四种先进的无人机人群分析模型（STEERER、GD³A、STNNet、YOLO11），通过 FastAPI 后端 + Vue 3 前端提供完整的 Web 推理平台。支持从单帧密度估计到视频级个体跟踪的完整分析流水线，具备丰富的可视化和评估功能。

### Java 可视化子系统
基于 Spring Boot 3.2.0 构建的数据集可视化平台，使用 Thymeleaf + H2 数据库，专门用于 MovingDroneCrowd++ 数据集的场景浏览、帧标注查看、热力图展示和轨迹追踪。

### 核心贡献

1. **多模型集成**：统一平台支持密度估计、个体计数、目标跟踪、目标检测四种技术路线
2. **双后端架构**：Python (FastAPI) + Java (Spring Boot) 微服务架构，各司其职
3. **完整可视化**：密度热力图、轨迹追踪、空间分布、时序分析等多维度可视化
4. **标准化评测**：支持数据集批量测试和自定义数据上传评测
5. **学术前沿**：基于 ICCV 2025 Highlight 和 CVPR 2021 论文的最新方法，结合工业级 YOLO11 检测模型
