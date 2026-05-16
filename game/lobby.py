"""
Main menu / lobby screen — primary controller.

Returns:
  ("host", None)        – user chose to host
  ("join", "x.x.x.x")  – user entered an IP to join
  (None,  None)         – user closed the window
"""
import socket
import threading
import pygame

from game.pages.layout import (
    LOGICAL_W, LOGICAL_H,
    _TB, _SW,
    COL_BG, COL_SEP, COL_HINT, COL_TITLE,
    COL_BTN, COL_BTN_HOV, COL_BTN_BD, COL_BTN_TXT,
    COL_HOST, COL_HOST_HOV, COL_HOST_BD, COL_HOST_TXT,
    COL_JOIN, COL_JOIN_HOV, COL_JOIN_BD, COL_JOIN_TXT,
    COL_PL_BG, COL_PL_BD, COL_PL_NAME, COL_LEVEL,
    COL_IP_VAL, COL_IP_DIM, COL_INPUT_BG, COL_INPUT_BD,
    IC_USER, IC_COG, IC_VOLUME, IC_BOLT, IC_SERVER, IC_SIGNIN, IC_GAMEPAD,
    IC_CART, IC_TASKS, IC_GAMEPAD as _IC_GAME,
    btn, cx,
)
from game.pages import game_page, characters_page, map_page, shop_page, missions_page


# ── Sidebar tab definitions ───────────────────────────────────────────────────
_TAB_W    = _SW - 20
_TAB_H    = 50
_TAB_X    = 10
_TAB_Y0   = _TB + 18
_TAB_STEP = _TAB_H + 8

IC_MAP = ''   # nf-fa-map (Nerd Fonts)

SIDEBAR_TABS = [
    ("game",       IC_GAMEPAD, "GAME"),
    ("shop",       IC_CART,    "SHOP"),
    ("characters", IC_USER,    "CHARACTERS"),
    ("map",        IC_MAP,     "MAP"),
    ("missions",   IC_TASKS,   "MISSIONS"),
]

TAB_RS = [
    pygame.Rect(_TAB_X, _TAB_Y0 + i * _TAB_STEP, _TAB_W, _TAB_H)
    for i in range(len(SIDEBAR_TABS))
]

# ── Helpers ───────────────────────────────────────────────────────────────────

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
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=4) as r:
            result[0] = r.read().decode().strip()
    except Exception:
        result[0] = "unavailable"


# ── Persistent chrome ─────────────────────────────────────────────────────────

def _draw_topbar(screen, font_lg, font_sm, sfx_r, set_r, mx, my):
    pygame.draw.line(screen, COL_SEP, (0, _TB), (LOGICAL_W, _TB), 1)

    pl_r = pygame.Rect(18, 10, 235, 48)
    pygame.draw.rect(screen, COL_PL_BG, pl_r, border_radius=8)
    pygame.draw.rect(screen, COL_PL_BD, pl_r, 2, border_radius=8)
    screen.blit(font_lg.render(f"{IC_USER}  PLAYER_001", True, COL_PL_NAME),
                (pl_r.x + 12, pl_r.y + 5))
    screen.blit(font_sm.render(f"{IC_BOLT}  Lv. 1", True, COL_LEVEL),
                (pl_r.x + 12, pl_r.y + 27))

    for r, icon in ((sfx_r, IC_VOLUME), (set_r, IC_COG)):
        bg = COL_BTN_HOV if r.collidepoint(mx, my) else COL_BTN
        btn(screen, r, bg, COL_BTN_BD, font_lg, icon, COL_BTN_TXT, radius=8)


def _draw_sidebar(screen, font_lg, font_sm, page, mx, my):
    pygame.draw.line(screen, COL_SEP, (_SW, _TB), (_SW, LOGICAL_H), 1)

    COL_TAB_ACT    = (28,  38,  58)
    COL_TAB_ACT_BD = (60, 140, 230)
    COL_TAB_TXT_A  = (180, 215, 255)

    for (pg, icon, lbl), r in zip(SIDEBAR_TABS, TAB_RS):
        active   = (pg == page)
        hovering = (not active) and r.collidepoint(mx, my)

        if active:
            bg, bd, tc = COL_TAB_ACT, COL_TAB_ACT_BD, COL_TAB_TXT_A
        elif hovering:
            bg, bd, tc = COL_BTN_HOV, COL_BTN_BD, COL_BTN_TXT
        else:
            bg, bd, tc = COL_BTN,     COL_BTN_BD, COL_BTN_TXT

        pygame.draw.rect(screen, bg, r, border_radius=8)
        pygame.draw.rect(screen, bd, r, 2, border_radius=8)

        if active:
            pygame.draw.rect(screen, COL_TAB_ACT_BD,
                             (r.x, r.y + 6, 3, r.h - 12), border_radius=2)

        ic_s = font_sm.render(icon, True, tc)
        nm_s = font_sm.render(lbl,  True, tc)
        total_w = ic_s.get_width() + 8 + nm_s.get_width()
        bx = r.centerx - total_w // 2
        screen.blit(ic_s, (bx, r.centery - ic_s.get_height() // 2))
        screen.blit(nm_s, (bx + ic_s.get_width() + 8,
                            r.centery - nm_s.get_height() // 2))


# ── Host sub-screen ───────────────────────────────────────────────────────────

def _draw_host(screen, font_lg, font_sm, local_ip, pub_ip, back_r, start_r, mx, my):
    CX = LOGICAL_W // 2

    panel = pygame.Rect(CX - 370, 85, 740, 500)
    pygame.draw.rect(screen, (18, 22, 32), panel, border_radius=16)
    pygame.draw.rect(screen, (45, 58, 88), panel, 2, border_radius=16)

    cx(screen, font_lg, f"{IC_SERVER}  HOST  YOUR  GAME", CX, 118, COL_TITLE)
    pygame.draw.line(screen, (45, 58, 88), (CX - 280, 155), (CX + 280, 155), 1)
    cx(screen, font_sm, "Share one of these IPs with the other player:", CX, 172, COL_HINT)

    pub_col = COL_IP_VAL if pub_ip not in ("fetching...", "unavailable") else COL_IP_DIM
    cx(screen, font_lg, f"Public IP :  {pub_ip}",    CX, 210, pub_col)
    cx(screen, font_sm, f"Local  IP :  {local_ip}  (same Wi-Fi only)", CX, 252, (92, 128, 158))
    cx(screen, font_sm,
       "Port: 5000   —   public IP requires UDP 5000 port forwarding",
       CX, 280, (62, 82, 108))
    pygame.draw.line(screen, (38, 50, 75), (CX - 280, 320), (CX + 280, 320), 1)

    hov = start_r.collidepoint(mx, my)
    btn(screen, start_r,
        COL_HOST_HOV if hov else COL_HOST, COL_HOST_BD,
        font_lg, f"{IC_BOLT}  START WAITING", COL_HOST_TXT, radius=10)
    cx(screen, font_sm, "or press  Enter", CX, start_r.bottom + 10, (68, 85, 110))

    hov_b = back_r.collidepoint(mx, my)
    btn(screen, back_r,
        COL_BTN_HOV if hov_b else COL_BTN, COL_BTN_BD,
        font_sm, "< BACK", COL_BTN_TXT)
    cx(screen, font_sm, "ESC to go back", CX, LOGICAL_H - 26, (52, 65, 90))


# ── Join sub-screen ───────────────────────────────────────────────────────────

def _draw_join(screen, font_lg, font_sm, ip_text, cursor_on, back_r, conn_r, mx, my):
    CX = LOGICAL_W // 2

    panel = pygame.Rect(CX - 340, 100, 680, 440)
    pygame.draw.rect(screen, (18, 22, 32), panel, border_radius=16)
    pygame.draw.rect(screen, (40, 54, 84), panel, 2, border_radius=16)

    cx(screen, font_lg, f"{IC_SIGNIN}  JOIN  A  GAME", CX, 132, COL_TITLE)
    pygame.draw.line(screen, (40, 54, 84), (CX - 260, 168), (CX + 260, 168), 1)
    cx(screen, font_sm, "Enter the host's IP address:", CX, 185, COL_HINT)

    box = pygame.Rect(CX - 220, 215, 440, 52)
    pygame.draw.rect(screen, COL_INPUT_BG, box, border_radius=10)
    pygame.draw.rect(screen, COL_INPUT_BD, box, 2, border_radius=10)
    display = ip_text + ("|" if cursor_on else " ")
    ts = font_lg.render(display, True, (220, 220, 220))
    screen.blit(ts, (box.x + 16, box.centery - ts.get_height() // 2))

    cx(screen, font_sm, "Press  Enter  or  click  CONNECT", CX, 280, (68, 85, 110))

    ip_valid = bool(ip_text.strip())
    hov = conn_r.collidepoint(mx, my) and ip_valid
    bg  = (COL_JOIN_HOV if hov else COL_JOIN)   if ip_valid else (22, 27, 40)
    bd  = COL_JOIN_BD                            if ip_valid else (38, 46, 68)
    tc  = COL_JOIN_TXT                           if ip_valid else (58, 68, 88)
    btn(screen, conn_r, bg, bd, font_lg, f"{IC_SIGNIN}  CONNECT", tc, radius=10)

    hov_b = back_r.collidepoint(mx, my)
    btn(screen, back_r,
        COL_BTN_HOV if hov_b else COL_BTN, COL_BTN_BD,
        font_sm, "< BACK", COL_BTN_TXT)
    cx(screen, font_sm, "ESC to go back", CX, LOGICAL_H - 26, (52, 65, 90))


# ── Main entry point ──────────────────────────────────────────────────────────

def lobby_screen(screen: pygame.Surface,
                 font_lg: pygame.font.Font,
                 font_sm: pygame.font.Font,
                 clock: pygame.time.Clock) -> tuple:

    FPS           = 60
    state         = "main"   # "main" | "host" | "join"
    page          = "game"   # "game" | "shop" | "characters" | "map" | "missions"
    sel_mode      = 0
    char_page_idx = 0
    map_page_idx  = 0
    ip_text       = ""
    cursor_on     = True
    ctime         = 0.0

    local_ip = _get_local_ip()
    pub_ip   = ["fetching..."]
    threading.Thread(target=_fetch_public_ip, args=(pub_ip,), daemon=True).start()

    # Top-right icon buttons
    SFX_R  = pygame.Rect(LOGICAL_W - 26 - 46 - 10 - 46, 11, 46, 46)
    SET_R  = pygame.Rect(LOGICAL_W - 26 - 46,            11, 46, 46)

    # Sub-screen buttons
    CX      = LOGICAL_W // 2
    BACK_R  = pygame.Rect(24, LOGICAL_H - 22 - 40, 120, 40)
    START_R = pygame.Rect(CX - 148, 490, 296, 66)
    CONN_R  = pygame.Rect(CX - 148, 448, 296, 66)

    while True:
        dt = clock.tick(FPS) / 1000.0
        ctime += dt
        if ctime >= 0.5:
            ctime = 0.0
            cursor_on = not cursor_on

        mx, my = pygame.mouse.get_pos()

        # ── Events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None

            if event.type == pygame.KEYDOWN:
                k = event.key
                if k == pygame.K_ESCAPE:
                    if state != "main":
                        state = "main"; ip_text = ""
                    else:
                        return None, None

                elif state == "join":
                    if k == pygame.K_RETURN:
                        ip = ip_text.strip()
                        if ip:
                            return "join", ip
                    elif k == pygame.K_BACKSPACE:
                        ip_text = ip_text[:-1]
                    else:
                        ch = event.unicode
                        if ch and (ch.isdigit() or ch == ".") and len(ip_text) < 15:
                            ip_text += ch

                elif state == "host":
                    if k == pygame.K_RETURN:
                        return "host", None

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "main":
                    # Sidebar tab switching
                    for (pg, _, _lbl), r in zip(SIDEBAR_TABS, TAB_RS):
                        if r.collidepoint(mx, my):
                            page = pg

                    if page == "game":
                        for i, r in enumerate(game_page.MODE_RS):
                            if r.collidepoint(mx, my):
                                sel_mode = i
                        if game_page.HOST_R.collidepoint(mx, my):
                            state = "host"
                        elif game_page.JOIN_R.collidepoint(mx, my):
                            state = "join"

                    elif page == "characters":
                        for i, r in enumerate(characters_page.CHAR_THUMB_RS):
                            if r.collidepoint(mx, my):
                                char_page_idx = i

                    elif page == "map":
                        for i, r in enumerate(map_page.MAP_RS):
                            if r.collidepoint(mx, my):
                                map_page_idx = i

                elif state == "host":
                    if BACK_R.collidepoint(mx, my):
                        state = "main"
                    elif START_R.collidepoint(mx, my):
                        return "host", None

                elif state == "join":
                    if BACK_R.collidepoint(mx, my):
                        state = "main"; ip_text = ""
                    elif CONN_R.collidepoint(mx, my):
                        ip = ip_text.strip()
                        if ip:
                            return "join", ip

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(COL_BG)

        if state == "main":
            _draw_topbar(screen, font_lg, font_sm, SFX_R, SET_R, mx, my)
            _draw_sidebar(screen, font_lg, font_sm, page, mx, my)

            if page == "game":
                game_page.draw(screen, font_lg, font_sm, mx, my, sel_mode)
            elif page == "characters":
                characters_page.draw(screen, font_lg, font_sm, char_page_idx)
            elif page == "map":
                map_page.draw(screen, font_lg, font_sm, map_page_idx)
            elif page == "shop":
                shop_page.draw(screen, font_lg, font_sm)
            elif page == "missions":
                missions_page.draw(screen, font_lg, font_sm)

        elif state == "host":
            _draw_host(screen, font_lg, font_sm,
                       local_ip, pub_ip[0], BACK_R, START_R, mx, my)
        elif state == "join":
            _draw_join(screen, font_lg, font_sm,
                       ip_text, cursor_on, BACK_R, CONN_R, mx, my)

        pygame.display.flip()
