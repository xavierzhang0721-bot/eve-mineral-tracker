#!/bin/bash
# 启动本地预览服务器
# 用法: bash serve.sh
# 然后在浏览器打开 http://localhost:8080

cd "$(dirname "$0")"
echo "🦞 EVE 矿物价格追踪"
echo "📍 http://localhost:8080"
echo "按 Ctrl+C 停止"
echo ""
python3 -m http.server 8080
