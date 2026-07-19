#!/bin/bash
# DroneCrowd 平台一键启动脚本
# 用法: bash restart.sh

echo "=============================="
echo "  DroneCrowd 平台启动中..."
echo "=============================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. 启动后端 (FastAPI, 端口 8000)
echo ""
echo "[1/2] 启动后端 (FastAPI :8000)..."
cd "$SCRIPT_DIR/platform_backend"
pkill -f "run.py --port 8000" 2>/dev/null
sleep 1
nohup python run.py --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"

# 2. 等待后端就绪
sleep 2
if ss -tlnp | grep -q ":8000"; then
    echo "  后端启动成功 ✓"
else
    echo "  后端启动失败，请查看 /tmp/backend.log"
fi

# 3. 启动前端 (Vite, 端口 8080)
echo ""
echo "[2/2] 启动前端 (Vite :8080)..."
cd "$SCRIPT_DIR/platform_frontend"
pkill -f "vite --host 0.0.0.0 --port 8080" 2>/dev/null
sleep 1
nohup npx vite --host 0.0.0.0 --port 8080 > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  前端 PID: $FRONTEND_PID"

# 4. 等待前端就绪
sleep 4
if ss -tlnp | grep -q ":8080"; then
    echo "  前端启动成功 ✓"
else
    echo "  前端启动失败，请查看 /tmp/frontend.log"
fi

echo ""
echo "=============================="
echo "  启动完成!"
echo "  前端: http://localhost:8080"
echo "  后端: http://localhost:8000"
echo "=============================="
