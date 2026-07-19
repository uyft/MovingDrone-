#!/bin/bash
# ==========================================
#  无人机人群计数平台 — 一键部署脚本
#  适用于: Cloud Studio / 云端 GPU 服务器
# ==========================================

set -e
echo "============================================="
echo "  无人机人群计数平台 — 部署脚本"
echo "============================================="

BASE_DIR="/workspace/MovingDroneCrowd-main"
BACKEND_DIR="$BASE_DIR/platform_backend"
FRONTEND_DIR="$BASE_DIR/platform_frontend"

# ---- 1. 后端依赖 ----
echo ""
echo "[1/4] 安装后端依赖..."
cd "$BASE_DIR"
pip install -r requirements.txt 2>/dev/null || echo "  主依赖已安装"
cd "$BACKEND_DIR"
pip install -r requirements.txt

# ---- 2. 前端依赖 ----
echo ""
echo "[2/4] 安装前端依赖..."
cd "$FRONTEND_DIR"
npm install

# ---- 3. 构建前端 ----
echo ""
echo "[3/4] 构建前端..."
npm run build

# ---- 4. 启动 ----
echo ""
echo "[4/4] 启动服务..."
echo ""
echo "  后端 API:  http://localhost:8000/docs"
echo "  前端页面(开发):  http://localhost:5173"
echo ""
echo "  启动后端: cd $BACKEND_DIR && python run.py"
echo "  启动前端: cd $FRONTEND_DIR && npm run dev"
echo ""
echo "============================================="
