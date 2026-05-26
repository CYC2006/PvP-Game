# 還原 Host / Join 模式說明

這份文件記錄了從「雙人雲端版」還原回「Host / Join 模式」所需的所有步驟。
Host / Join 的邏輯程式碼完整保留在原本的檔案裡，只是沒有被 UI 呼叫到。

---

## 目前狀態（雲端版）

主畫面只有一個 **ONLINE** 按鈕，玩家按下後自動連到 `cloud_config.py` 裡的雲端 IP。

## 還原目標（Host / Join 版）

主畫面顯示 **HOST** 和 **JOIN** 兩個按鈕：
- HOST：在本機啟動 server，自己當房主
- JOIN：輸入對方 IP 加入

---

## 需要修改的檔案

### 1. `game/pages/game_page.py`

**現況**：`draw()` 函式渲染 ONLINE 按鈕，HOST_R / JOIN_R 定義保留但未渲染。  
**還原**：把 `draw()` 函式底部改回渲染 HOST 和 JOIN 按鈕。

把這段（ONLINE 按鈕）：
```python
    # ONLINE
    btn(screen, ONLINE_R,
        COL_ONLINE_HOV if ONLINE_R.collidepoint(mx, my) else COL_ONLINE,
        COL_ONLINE_BD, font_lg, f"{IC_SERVER}  ONLINE", COL_ONLINE_TXT, radius=10)
```

換回這段（HOST / JOIN 按鈕）：
```python
    # HOST / JOIN
    btn(screen, HOST_R,
        COL_HOST_HOV if HOST_R.collidepoint(mx, my) else COL_HOST,
        COL_HOST_BD, font_lg, f"{IC_SERVER}  HOST", COL_HOST_TXT, radius=10)

    btn(screen, JOIN_R,
        COL_JOIN_HOV if JOIN_R.collidepoint(mx, my) else COL_JOIN,
        COL_JOIN_BD, font_lg, f"{IC_SIGNIN}  JOIN", COL_JOIN_TXT, radius=10)
```

---

### 2. `game/lobby.py`

**現況**：event handler 裡，`page == "game"` 時點擊 ONLINE_R → `return ("online", None)`。  
**還原**：改回點擊 HOST_R → `state = "host"`，點擊 JOIN_R → `state = "join"`。

把這段（ONLINE）：
```python
                    if game_page.ONLINE_R.collidepoint(mx, my):
                        return "online", None
```

換回這段（HOST / JOIN）：
```python
                        if game_page.HOST_R.collidepoint(mx, my):
                            state = "host"
                        elif game_page.JOIN_R.collidepoint(mx, my):
                            state = "join"
```

---

### 3. `client.py`

**現況**：`mode == "online"` 的分支讀取 `cloud_config.CLOUD_SERVER_IP`。  
**還原**：這段不需要刪除，host / join 分支本來就在，三個模式可以並存。  
只需要確保 lobby 不會再回傳 `"online"`，client.py 不需要改動。

---

## 注意事項

- `_draw_host()` 和 `_draw_join()` 函式在 `lobby.py` 裡完整保留，隨時可用。
- `network/cloud_config.py` 可以保留，不影響 Host / Join 模式運作。
- `RESTORE.md`（本文件）可以保留，不影響任何功能。
