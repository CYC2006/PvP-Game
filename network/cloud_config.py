# ── 伺服器設定 ────────────────────────────────────────────────────────────────
# 同機測試（兩個終端機）：  CLOUD_SERVER_IP = "127.0.0.1"
#   → client 自動在背景啟動本機 server，兩個視窗都點 ONLINE 即可撮合。
#
# 跨網路（Oracle VM）：     CLOUD_SERVER_IP = "161.33.6.210"
#   → 先執行 bash deploy.sh 部署 server，兩台電腦點 ONLINE 即可撮合。

#CLOUD_SERVER_IP   = "129.225.195.211"  # Oracle VM — auto-detection handles localhost fallback
CLOUD_SERVER_IP   = "127.0.0.1"
CLOUD_SERVER_PORT = 5000
