#!/bin/bash
# deploy.sh — 一鍵同步 server 檔案到 Oracle VM
# 用法：bash deploy.sh
# 只傳 server 需要的檔案，跳過 client 專用的部分（renderer、assets 等）

KEY="$(dirname "$0")/network/pvp-game-server.key"
REMOTE="opc@161.33.6.210"
LOCAL="$(dirname "$0")/"

echo "[Deploy] Syncing files..."

rsync -avz --progress \
  -e "ssh -i \"$KEY\"" \
  --exclude="venv/" \
  --exclude="__pycache__/" \
  --exclude="*.pyc" \
  --exclude=".git/" \
  --exclude=".claude/" \
  --exclude="assets/" \
  --exclude="network/*.key" \
  --exclude="network/*.pub" \
  --exclude="network/cloud_config.py" \
  --exclude="client.py" \
  --exclude="game/renderer.py" \
  --exclude="game/render_utils.py" \
  --exclude="game/input.py" \
  --exclude="game/charselect.py" \
  --exclude="game/lobby.py" \
  --exclude="game/pages/" \
  --exclude="*_fx.py" \
  --exclude="RESTORE.md" \
  --exclude="CLAUDE.md" \
  --exclude="README.md" \
  --exclude="SKILLS.md" \
  --exclude="memory/" \
  --exclude="deploy.sh" \
  "$LOCAL" \
  "$REMOTE:~/"

echo "[Deploy] Done. Restarting server..."

ssh -i "$KEY" "$REMOTE" \
  "pkill -f server.py; sleep 1; nohup python3 server.py > server.log 2>&1 &"

echo "[Deploy] Server restarted."
