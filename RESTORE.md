# RESTORE.md — 連線模式切換說明

本文件記錄各種連線模式的切換方法，以及目前各模式相關程式碼的保留狀態。

---

## 目前狀態（Host / Join 模式）

主畫面顯示 **HOST** 和 **JOIN** 兩個按鈕：
- **HOST**：在本機啟動 server，等待對方加入
- **JOIN**：輸入對方 IP 連線

適用情境：同一網路（LAN）的兩台電腦對打。

---

## 模式 A：還原 Oracle 雲端自動撮合

這個模式下，主畫面只有 ONLINE 按鈕，client 自動探測 Oracle VM 是否在線：
- Oracle VM 有回應 → 連 Oracle VM（異地對打）
- Oracle VM 無回應 → 自動 fallback 到本機 server（同電腦開發測試）

### 目前哪些程式碼還保留

| 檔案 | 內容 | 狀態 |
|------|------|------|
| `network/cloud_config.py` | Oracle IP `161.33.6.210` | ✅ 保留 |
| `network/protocol.py` | `PKT_PING = 0x0A`, `PKT_PONG = 0x0B`, `pack_ping()` | ✅ 保留 |
| `server.py` | PKT_PING handler（收到後直接回 PKT_PONG） | ✅ 保留 |
| `deploy.sh` | rsync + SSH 部署腳本 | ✅ 保留 |
| `client.py` | Oracle probe 邏輯 | ❌ 已移除（見 git history） |
| `game/pages/game_page.py` | ONLINE_R rect 定義 + COL_ONLINE 顏色 | ✅ 保留 |

### 需要修改的檔案

#### 1. `client.py` — 加回 Oracle probe 邏輯

**完整實作在 git commit `872d3df`**（2026-06-09）。

概略步驟：

a. 加回 import：
```python
from network.protocol import (
    ..., PKT_PING, PKT_PONG,
    ..., pack_ping,
)
```

b. `matchmaking_screen` 改為接受 `oracle_addr`，加回 Phase 1 probe：
```python
_PROBE_TIMEOUT  = 2.0   # 秒：等待 Oracle VM 回應的上限
_PROBE_INTERVAL = 0.5   # 秒：每次重送 PKT_PING 的間隔

def matchmaking_screen(sock, oracle_addr, screen, font_lg, font_sm, clock):
    # Phase 1: 探測 Oracle VM（送 PKT_PING，等 PKT_PONG）
    #   - 有回應 → server_addr = oracle_addr
    #   - 超時   → server_addr = ("127.0.0.1", port)（本機 fallback）
    # Phase 2: 送 PKT_JOIN，等 PKT_JOINED + PKT_ALL_JOINED
    # Returns (player_id, server_addr) or (None, None)
```

c. `run()` 改為：
```python
oracle_addr = (CLOUD_SERVER_IP, CLOUD_SERVER_PORT)
# 在 matchmaking_screen 裡預先啟動本機 server（fallback 用）
player_id, server_addr = matchmaking_screen(sock, oracle_addr, ...)
```

#### 2. `game/pages/game_page.py` — 換回 ONLINE 按鈕

把 HOST / JOIN 按鈕換回單一 ONLINE 按鈕（`draw()` 底部）：
```python
btn(screen, ONLINE_R,
    COL_ONLINE_HOV if ONLINE_R.collidepoint(mx, my) else COL_ONLINE,
    COL_ONLINE_BD, font_lg, f"{IC_SERVER}  ONLINE", COL_ONLINE_TXT, radius=10)
```

#### 3. `game/lobby.py` — event handler 改回回傳 `"online"`

```python
if game_page.ONLINE_R.collidepoint(mx, my):
    return "online", None
```

移除 `_draw_join()` 子畫面和 `join_mode` 狀態機。

#### 4. 部署 Oracle VM

```bash
# 確認 Oracle VM 上 iptables 已開放 UDP 5000
ssh -i network/pvp-game-server.key opc@161.33.6.210 \
  "sudo iptables -I INPUT -p udp --dport 5000 -j ACCEPT"

# 部署 server.py
bash deploy.sh
```

---

## 模式 B：目前使用中的 Host / Join 模式

不需要任何修改，目前 codebase 就是這個模式。

---

## 注意事項

- `network/*.key` 和 `network/*.pub` 已加入 `.gitignore`，不會被 commit。
- `network/cloud_config.py` 在 `deploy.sh` 的 rsync exclude list 裡，不會被傳到 Oracle VM。
- 完整的 Oracle 自動撮合實作可以在 git log 裡找到：`git show 872d3df`
