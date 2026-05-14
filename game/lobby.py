"""
Lobby 畫面：Host（開房）或 Join（加入）選擇，以及 IP 輸入框。

回傳值：
  ("host", None)        → 使用者選擇開房
  ("join", "x.x.x.x")  → 使用者輸入 IP 後確認
  (None,  None)         → 使用者關閉視窗
"""
import socket
import threading
import pygame

from game.charselect import LOGICAL_W, LOGICAL_H

# ── 顏色 ──────────────────────────────────────────────────────────────────
COL_BG       = (20,  24,  32)
COL_TITLE    = (255, 230, 100)
COL_TEXT     = (220, 220, 220)
COL_HINT     = (110, 130, 160)
COL_BTN      = (38,  46,  62)
COL_BTN_HOV  = (55,  75, 110)
COL_BTN_BD   = (80, 110, 160)
COL_INPUT_BG = (28,  34,  48)
COL_INPUT_BD = (80, 130, 200)
COL_IP       = (80,  220, 130)
COL_IP_DIM   = (110, 160, 130)


def _get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "unknown"
    finally:
        s.close()


def _fetch_public_ip(result: list) -> None:
    """背景執行緒取得公網 IP，結果寫入 result[0]。"""
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=4) as r:
            result[0] = r.read().decode().strip()
    except Exception:
        result[0] = "無法取得"


def lobby_screen(screen: pygame.Surface,
                 font_lg: pygame.font.Font,
                 font_sm: pygame.font.Font,
                 clock: pygame.time.Clock) -> tuple:
    """主進入點，回傳 (mode, ip_or_None)。"""

    FPS        = 60
    CX         = LOGICAL_W // 2
    mode       = None        # None | "host" | "join"
    ip_text    = ""
    cursor_on  = True
    cur_timer  = 0.0

    local_ip   = _get_local_ip()
    public_ip  = ["fetching..."]
    threading.Thread(target=_fetch_public_ip, args=(public_ip,), daemon=True).start()

    HOST_RECT = pygame.Rect(CX - 230, 310, 210, 72)
    JOIN_RECT = pygame.Rect(CX +  20, 310, 210, 72)

    while True:
        dt = clock.tick(FPS) / 1000.0
        cur_timer += dt
        if cur_timer >= 0.5:
            cur_timer = 0.0
            cursor_on = not cursor_on

        # ── 事件 ────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if mode is not None:
                        mode = None
                        ip_text = ""
                    else:
                        return None, None

                elif mode == "join":
                    if event.key == pygame.K_RETURN:
                        ip = ip_text.strip()
                        if ip:
                            return "join", ip
                    elif event.key == pygame.K_BACKSPACE:
                        ip_text = ip_text[:-1]
                    else:
                        ch = event.unicode
                        if ch and (ch.isdigit() or ch == ".") and len(ip_text) < 15:
                            ip_text += ch

                elif mode == "host":
                    if event.key == pygame.K_RETURN:
                        return "host", None

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = pygame.mouse.get_pos()
                if mode is None:
                    if HOST_RECT.collidepoint(mx, my):
                        mode = "host"
                    elif JOIN_RECT.collidepoint(mx, my):
                        mode = "join"

        # ── 繪製 ────────────────────────────────────────────────────
        screen.fill(COL_BG)

        # 標題
        title = font_lg.render("PvP  GAME", True, COL_TITLE)
        screen.blit(title, (CX - title.get_width() // 2, 130))

        # ── 選擇畫面 ────────────────────────────────────────────────
        if mode is None:
            mx, my = pygame.mouse.get_pos()
            for rect, label in ((HOST_RECT, "HOST"), (JOIN_RECT, "JOIN")):
                col = COL_BTN_HOV if rect.collidepoint(mx, my) else COL_BTN
                pygame.draw.rect(screen, col, rect, border_radius=12)
                pygame.draw.rect(screen, COL_BTN_BD, rect, 2, border_radius=12)
                ls = font_lg.render(label, True, COL_TEXT)
                screen.blit(ls, (rect.centerx - ls.get_width()  // 2,
                                 rect.centery - ls.get_height() // 2))

            hint = font_sm.render(
                "HOST = Start a server          JOIN = Connect to a server",
                True, COL_HINT)
            screen.blit(hint, (CX - hint.get_width() // 2, 410))

        # ── Host 畫面 ────────────────────────────────────────────────
        elif mode == "host":
            _draw_text(screen, font_lg, "Share your IP with the other player", CX, 250, COL_TEXT)

            pub_col = COL_IP if public_ip[0] not in ("fetching...", "unavailable") else COL_IP_DIM
            _draw_text(screen, font_lg, f"Public IP : {public_ip[0]}", CX, 310, pub_col)
            _draw_text(screen, font_sm,
                       f"Local  IP : {local_ip}   (same WiFi only)",
                       CX, 355, COL_HINT)
            _draw_text(screen, font_sm,
                       "Port : 5000  -  requires UDP 5000 port forwarding for public IP",
                       CX, 385, COL_HINT)

            _draw_text(screen, font_lg, "Press Enter to start waiting",
                       CX, 460, COL_TITLE)
            _draw_text(screen, font_sm, "ESC to go back", CX, 510, COL_HINT)

        # ── Join 畫面 ────────────────────────────────────────────────
        elif mode == "join":
            _draw_text(screen, font_lg, "Enter the server IP address", CX, 250, COL_TEXT)

            box_w, box_h = 420, 54
            box = pygame.Rect(CX - box_w // 2, 310, box_w, box_h)
            pygame.draw.rect(screen, COL_INPUT_BG, box, border_radius=10)
            pygame.draw.rect(screen, COL_INPUT_BD, box, 2,  border_radius=10)

            display = ip_text + ("|" if cursor_on else " ")
            ts = font_lg.render(display, True, COL_TEXT)
            screen.blit(ts, (box.x + 14, box.centery - ts.get_height() // 2))

            _draw_text(screen, font_sm, "Press Enter to connect", CX, 385, COL_HINT)
            _draw_text(screen, font_sm, "ESC to go back",         CX, 420, COL_HINT)

        pygame.display.flip()


def _draw_text(surface, font, text, cx, y, color):
    s = font.render(text, True, color)
    surface.blit(s, (cx - s.get_width() // 2, y))
