"""
启动脚本
用法:
  python run.py              → 启动 FastAPI 服务
  python run.py --reload     → 开发模式（热重载）
  python run.py --port 8080  → 指定端口
"""
import argparse
import os
import sys

# 确保能找到 app 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--workers", type=int, default=1, help="worker 数量 (默认 1，GPU 模型避免重复加载)")
    args = parser.parse_args()

    import uvicorn

    print("=" * 60)
    print("  无人机视角动态密集人群计数与时空分布分析系统")
    print(f"  后端服务启动: http://{args.host}:{args.port}")
    print(f"  API 文档:     http://{args.host}:{args.port}/docs")
    print(f"  Workers:      {args.workers}")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )
