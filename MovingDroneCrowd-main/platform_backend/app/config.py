"""
全局配置
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件（若存在）
_ENV_FILE = os.path.join(BASE_DIR, ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# 算法根目录（现有代码位置）
ALGORITHM_PATH = os.path.join(BASE_DIR, "..")

# 上传 & 结果存储
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
RESULT_DIR = os.path.join(BASE_DIR, "results")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# GPU 配置
GPU_ID = "0"

# 模型路径（相对 ALGORITHM_PATH）
COUNTER_WEIGHT = "pretrained/GD3A_pre_trained_global_counter_STEERER_MDC++_ep_201_mae_13.5_mse_19.1.pth"
GD3A_WEIGHT = "pretrained/GD3A_MDC++_best_model_VGG16.pth"
GD3A_WEIGHT_RESNET50 = "pretrained/GD3A_MDC++_best_model_ResNet50.pth"

# YOLO11 检测模型路径
YOLO11_WEIGHT = "/workspace/HybridSORT-master/yolo11_visdrone/runs/yolo11m_visdrone_person-2/weights/best.pt"

# 推理参数
MAX_LONG = 1920
MAX_SHORT = 1080
MIN_DISTANCE = 10
THRESHOLD_REL = 0.15

# 允许上传的视频格式
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_VIDEO_SIZE_MB = 500

# ============================================================
#  AI Agent 配置 (DeepSeek V4 Pro)
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")  # DeepSeek V4 Pro
AGENT_ENABLED = bool(DEEPSEEK_API_KEY)
