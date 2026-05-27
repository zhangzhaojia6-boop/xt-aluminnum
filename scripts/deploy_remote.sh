#!/bin/bash
# 云端自动部署脚本
# 在云端服务器执行: bash <(curl -s https://raw.githubusercontent.com/zhangzhaojia6-boop/xt-aluminnum/main/scripts/deploy_remote.sh)

set -e

echo "=== 鑫泰铝业数据中枢 - 自动部署 ==="
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

cd /srv/aluminum-bypass

echo "1. 拉取最新代码..."
git pull origin main

echo ""
echo "2. 重启后端服务..."
systemctl --user restart aluminum-bypass

echo ""
echo "3. 等待服务启动..."
sleep 3

echo ""
echo "4. 检查服务状态..."
systemctl --user status aluminum-bypass --no-pager | head -20

echo ""
echo "=== 部署完成 ==="
echo "完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
