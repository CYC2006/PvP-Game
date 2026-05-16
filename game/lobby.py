"""
Main menu / lobby screen.

Returns:
  ("host", None)        – user chose to host
  ("join", "x.x.x.x")  – user entered an IP to join
  (None,  None)         – user closed the window
"""
import socket
import threading
import pygame
from game.charselect import LOGICAL_W, LOGICAL_H

# ─── Colors ───────────────────────────────────────────────────────────────────
COL_BG        = (15,  18,  26)
COL_TOPBAR    = (18,  22,  32)
COL_SIDEBAR   = (18,  22,  32)
COL_SEP       = (36,  46,  66)
COL_TEXT      = (220, 220, 220)
COL_HINT      = ( 95, 112, 145)
COL_TITLE     = (255, 230, 100)

# Generic (sidebar / icon buttons)
COL_BTN       = (26,  34,  50)
COL_BTN_HOV   = (36,  48,  72)
COL_BTN_BD    = (48,  62,  90)
COL_BTN_TXT   = (145, 162, 195)

# Mode selector
COL_M_SEL     = (22,  54,  92)
COL_M_SEL_BD  = (68, 150, 238)
COL_M_SEL_TXT = (170, 210, 255)
COL_M_UN      = (22,  28,  42)
COL_M_UN_BD   = (38,  48,  70)
COL_M_UN_TXT  = (100, 118, 150)
COL_M_HOV     = (28,  38,  58)
COL_M_HOV_TXT = (148, 172, 212)

# HOST button
COL_HOST      = ( 36, 112,  68)
COL_HOST_HOV  = ( 48, 145,  88)
COL_HOST_BD   = ( 72, 205, 118)
COL_HOST_TXT  = (175, 238, 200)

# JOIN button
COL_JOIN      = ( 32,  70, 142)
COL_JOIN_HOV  = ( 44,  94, 178)
COL_JOIN_BD   = ( 72, 140, 235)
COL_JOIN_TXT  = (165, 200, 248)

# Player info
COL_PL_BG     = (20,  26,  40)
COL_PL_BD     = (45,  58,  85)
COL_PL_NAME   = (205, 210, 228)
COL_LEVEL     = (255, 198,  52)

# IP / input
COL_IP_VAL    = ( 72, 212, 128)
COL_IP_DIM    = ( 95, 152, 122)
COL_INPUT_BG  = (20,  26,  40)
COL_INPUT_BD  = ( 72, 132, 212)

# ─── Layout constants ─────────────────────────────────────────────────────────
_TB  = 68          # top-bar height
_SW  = 170         # sidebar width
_MCX = (_SW + LOGICAL_W) // 2   # main-area center-x = 725

# Game-mode section (left half of main area)
_MX   = 205        # left edge of mode buttons
_MW   = 345        # mode-button width
_MH   = 52         # mode-button height
_MGAP = 11         # gap between mode buttons
_MY0  = 310        # y of first mode button

# Divider between mode section and play section
_DVX  = 728

# HOST / JOIN (bottom-right)
_BW   = 255
_BH   = 72
_BX   = LOGICAL_W - 26 - _BW   # = 999
_HY   = 498        # HOST button y
_JY   = _HY + _BH + 15         # JOIN button y = 585

# ─── Nerd Fonts icons (MapleMono-NF has these built in) ──────────────────────
IC_USER       = ''   #
IC_COG        = ''   #
IC_CART       = ''   #
IC_TASKS      = ''   #
IC_USERS      = ''   #
IC_GAMEPAD    = ''   #
IC_FLAG       = ''   #
IC_CROSSHAIRS = ''   #
IC_BULLSEYE   = ''   #
IC_SERVER     = ''   #
IC_SIGNIN     = ''   #
IC_VOLUME     = ''   #
IC_BOLT       = ''   #
IC_HOME       = ''   #

# ─── Game modes ───────────────────────────────────────────────────────────────
_MODES = [
    (IC_CROSSHAIRS, "DEATHMATCH",       "Eliminate the enemy player"),
    (IC_FLAG,       "CAPTURE THE FLAG", "Capture and return the flag"),
    (IC_BULLSEYE,   "CAPTURE POINT",    "Hold key positions longer"),
    (IC_USERS,      "2v2  TEAM",        "Two versus two squad battle"),
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _btn(surf, rect, bg, bd, font, label, col, radius=9):
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    pygame.draw.rect(surf, bd, rect, 2, border_radius=radius)
    s = font.render(label, True, col)
    surf.blit(s, (rect.centerx - s.get_width()  // 2,
                  rect.centery - s.get_height() // 2))


def _cx(surf, font, text, cx, y, color):
    s = font.render(text, True, color)
    surf.blit(s, (cx - s.get_width() // 2, y))


# ─── Main entry point ─────────────────────────────────────────────────────────

def lobby_screen(screen: pygame.Surface,
                 font_lg: pygame.font.Font,
                 font_sm: pygame.font.Font,
                 clock: pygame.time.Clock) -> tuple:

    FPS       = 60
    state     = "main"   # "main" | "host" | "join"
    sel_mode  = 0
    ip_text   = ""
    cursor_on = True
    ctime     = 0.0

    local_ip = _get_local_ip()
    pub_ip   = ["fetching..."]
    threading.Thread(target=_fetch_public_ip, args=(pub_ip,),
                     daemon=True).start()

    # ── Static rects ──────────────────────────────────────────────────────────
    # Top-right icon buttons
    SFX_R  = pygame.Rect(LOGICAL_W - 26 - 46 - 10 - 46, 11, 46, 46)
    SET_R  = pygame.Rect(LOGICAL_W - 26 - 46,            11, 46, 46)

    # Sidebar buttons
    SHOP_R  = pygame.Rect(15, _TB + 24,             _SW - 30, 48)
    CHARS_R = pygame.Rect(15, _TB + 86,             _SW - 30, 48)
    MISS_R  = pygame.Rect(15, LOGICAL_H - 24 - 44,  _SW - 30, 44)

    # Game-mode buttons
    MODE_RS = [
        pygame.Rect(_MX, _MY0 + i * (_MH + _MGAP), _MW, _MH)
        for i in range(len(_MODES))
    ]

    # HOST / JOIN
    HOST_R = pygame.Rect(_BX, _HY, _BW, _BH)
    JOIN_R = pygame.Rect(_BX, _JY, _BW, _BH)

    # Sub-screen buttons (centered on full screen)
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
                    for i, r in enumerate(MODE_RS):
                        if r.collidepoint(mx, my):
                            sel_mode = i
                    if HOST_R.collidepoint(mx, my):
                        state = "host"
                    elif JOIN_R.collidepoint(mx, my):
                        state = "join"
                    # Sidebar & top-right buttons: no action (not implemented)

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

        # ── Render ────────────────────────────────────────────────────────────
        screen.fill(COL_BG)

        if state == "main":
            _draw_main(screen, font_lg, font_sm, mx, my,
                       sel_mode, MODE_RS, HOST_R, JOIN_R,
                       SHOP_R, CHARS_R, MISS_R, SFX_R, SET_R)
        elif state == "host":
            _draw_host(screen, font_lg, font_sm,
                       local_ip, pub_ip[0], BACK_R, START_R, mx, my)
        elif state == "join":
            _draw_join(screen, font_lg, font_sm,
                       ip_text, cursor_on, BACK_R, CONN_R, mx, my)

        pygame.display.flip()


# ─── Main screen ──────────────────────────────────────────────────────────────

def _draw_main(screen, font_lg, font_sm, mx, my,
               sel_mode, mode_rs, host_r, join_r,
               shop_r, chars_r, miss_r, sfx_r, set_r):
    W, H = LOGICAL_W, LOGICAL_H

    # ── Top bar ───────────────────────────────────────────────────────────────
    pygame.draw.line(screen, COL_SEP, (0, _TB), (W, _TB), 1)

    # Player info panel (top-left)
    pl_r = pygame.Rect(18, 10, 235, 48)
    pygame.draw.rect(screen, COL_PL_BG, pl_r, border_radius=8)
    pygame.draw.rect(screen, COL_PL_BD, pl_r, 2, border_radius=8)
    ns = font_lg.render(f"{IC_USER}  PLAYER_001", True, COL_PL_NAME)
    screen.blit(ns, (pl_r.x + 12, pl_r.y + 5))
    ls = font_sm.render(f"{IC_BOLT}  Lv. 1", True, COL_LEVEL)
    screen.blit(ls, (pl_r.x + 12, pl_r.y + 27))

    # Top-right: SFX + SET — icon only, no text
    for r, icon in ((sfx_r, IC_VOLUME), (set_r, IC_COG)):
        bg = COL_BTN_HOV if r.collidepoint(mx, my) else COL_BTN
        _btn(screen, r, bg, COL_BTN_BD, font_lg, icon, COL_BTN_TXT, radius=8)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    pygame.draw.line(screen, COL_SEP, (_SW, _TB), (_SW, H), 1)

    for r, icon, lbl in ((shop_r,  IC_CART,  "SHOP"),
                         (chars_r, IC_USER,  "CHARACTERS"),
                         (miss_r,  IC_TASKS, "MISSIONS")):
        bg = COL_BTN_HOV if r.collidepoint(mx, my) else COL_BTN
        _btn(screen, r, bg, COL_BTN_BD, font_sm, f"{icon}  {lbl}", COL_BTN_TXT)

    # ── Game mode section ─────────────────────────────────────────────────────
    sec_lbl = font_sm.render(f"{IC_GAMEPAD}  GAME  MODE", True, (68, 105, 158))
    screen.blit(sec_lbl, (_MX, _MY0 - 36))

    for i, (r, (icon, name, desc)) in enumerate(zip(mode_rs, _MODES)):
        selected = (i == sel_mode)
        hovering = (not selected) and r.collidepoint(mx, my)

        if selected:
            bg, bd, tc = COL_M_SEL,  COL_M_SEL_BD, COL_M_SEL_TXT
        elif hovering:
            bg, bd, tc = COL_M_HOV,  COL_M_UN_BD,  COL_M_HOV_TXT
        else:
            bg, bd, tc = COL_M_UN,   COL_M_UN_BD,  COL_M_UN_TXT

        pygame.draw.rect(screen, bg, r, border_radius=8)
        pygame.draw.rect(screen, bd, r, 2, border_radius=8)

        # Icon at fixed x; name at fixed offset so all 4 names align vertically
        ic_surf = font_lg.render(icon, True, tc)
        nm_surf = font_lg.render(name, True, tc)
        ty2 = r.centery - ic_surf.get_height() // 2
        screen.blit(ic_surf, (r.x + 14, ty2))
        screen.blit(nm_surf, (r.x + 46, ty2))   # fixed 46px indent for all rows

        # Radio indicator (right side)
        ix, iy = r.right - 20, r.centery
        if selected:
            pygame.draw.circle(screen, COL_M_SEL_BD, (ix, iy), 7)
            pygame.draw.circle(screen, (210, 230, 255), (ix, iy), 3)
        else:
            pygame.draw.circle(screen, bd, (ix, iy), 6, 2)

    # Description of currently selected mode
    _, _, sel_desc = _MODES[sel_mode]
    ds = font_sm.render(sel_desc, True, (82, 122, 172))
    screen.blit(ds, (_MX, _MY0 + len(_MODES) * (_MH + _MGAP) - _MGAP + 8))

    # ── Play section (right of divider) ───────────────────────────────────────
    # Section label left-aligned with the HOST/JOIN buttons
    play_lbl = font_sm.render(f"{IC_BOLT}  START  GAME", True, (68, 105, 158))
    screen.blit(play_lbl, (_BX, _HY - 36))

    # HOST button
    hh = host_r.collidepoint(mx, my)
    _btn(screen, host_r,
         COL_HOST_HOV if hh else COL_HOST, COL_HOST_BD,
         font_lg, f"{IC_SERVER}  HOST", COL_HOST_TXT, radius=10)

    # JOIN button
    jh = join_r.collidepoint(mx, my)
    _btn(screen, join_r,
         COL_JOIN_HOV if jh else COL_JOIN, COL_JOIN_BD,
         font_lg, f"{IC_SIGNIN}  JOIN", COL_JOIN_TXT, radius=10)



# ─── Host sub-screen ──────────────────────────────────────────────────────────

def _draw_host(screen, font_lg, font_sm,
               local_ip, pub_ip, back_r, start_r, mx, my):
    W, H = LOGICAL_W, LOGICAL_H
    CX   = W // 2

    # Centre panel
    panel = pygame.Rect(CX - 370, 85, 740, 500)
    pygame.draw.rect(screen, COL_TOPBAR,  panel, border_radius=16)
    pygame.draw.rect(screen, (45, 58, 88), panel, 2, border_radius=16)

    _cx(screen, font_lg, f"{IC_SERVER}  HOST  YOUR  GAME", CX, 118, COL_TITLE)

    pygame.draw.line(screen, (45, 58, 88), (CX - 280, 155), (CX + 280, 155), 1)

    _cx(screen, font_sm,
        "Share one of these IPs with the other player:", CX, 172, COL_HINT)

    pub_col = COL_IP_VAL if pub_ip not in ("fetching...", "unavailable") \
              else COL_IP_DIM
    _cx(screen, font_lg, f"Public IP :  {pub_ip}",    CX, 210, pub_col)
    _cx(screen, font_sm, f"Local  IP :  {local_ip}  (same Wi-Fi only)", CX, 252, (92, 128, 158))
    _cx(screen, font_sm,
        "Port: 5000   —   public IP requires UDP 5000 port forwarding",
        CX, 280, (62, 82, 108))

    pygame.draw.line(screen, (38, 50, 75), (CX - 280, 320), (CX + 280, 320), 1)

    # START WAITING button
    hov = start_r.collidepoint(mx, my)
    _btn(screen, start_r,
         COL_HOST_HOV if hov else COL_HOST, COL_HOST_BD,
         font_lg, f"{IC_BOLT}  START WAITING", COL_HOST_TXT, radius=10)
    _cx(screen, font_sm, "or press  Enter", CX, start_r.bottom + 10, (68, 85, 110))

    # BACK button
    hov_b = back_r.collidepoint(mx, my)
    _btn(screen, back_r,
         COL_BTN_HOV if hov_b else COL_BTN, COL_BTN_BD,
         font_sm, "< BACK", COL_BTN_TXT)
    _cx(screen, font_sm, "ESC to go back", CX, H - 26, (52, 65, 90))


# ─── Join sub-screen ──────────────────────────────────────────────────────────

def _draw_join(screen, font_lg, font_sm,
               ip_text, cursor_on, back_r, conn_r, mx, my):
    W, H = LOGICAL_W, LOGICAL_H
    CX   = W // 2

    # Centre panel
    panel = pygame.Rect(CX - 340, 100, 680, 440)
    pygame.draw.rect(screen, COL_TOPBAR,  panel, border_radius=16)
    pygame.draw.rect(screen, (40, 54, 84), panel, 2, border_radius=16)

    _cx(screen, font_lg, f"{IC_SIGNIN}  JOIN  A  GAME", CX, 132, COL_TITLE)

    pygame.draw.line(screen, (40, 54, 84), (CX - 260, 168), (CX + 260, 168), 1)

    _cx(screen, font_sm, "Enter the host's IP address:", CX, 185, COL_HINT)

    # IP input box
    box = pygame.Rect(CX - 220, 215, 440, 52)
    pygame.draw.rect(screen, COL_INPUT_BG, box, border_radius=10)
    pygame.draw.rect(screen, COL_INPUT_BD, box, 2, border_radius=10)
    display = ip_text + ("|" if cursor_on else " ")
    ts = font_lg.render(display, True, COL_TEXT)
    screen.blit(ts, (box.x + 16, box.centery - ts.get_height() // 2))

    _cx(screen, font_sm, "Press  Enter  or  click  CONNECT", CX, 280, (68, 85, 110))

    # CONNECT button (dims if no IP entered)
    ip_valid = bool(ip_text.strip())
    hov      = conn_r.collidepoint(mx, my) and ip_valid
    bg  = (COL_JOIN_HOV if hov else COL_JOIN)   if ip_valid else (22, 27, 40)
    bd  = COL_JOIN_BD                            if ip_valid else (38, 46, 68)
    tc  = COL_JOIN_TXT                           if ip_valid else (58, 68, 88)
    _btn(screen, conn_r, bg, bd, font_lg, f"{IC_SIGNIN}  CONNECT", tc, radius=10)

    # BACK button
    hov_b = back_r.collidepoint(mx, my)
    _btn(screen, back_r,
         COL_BTN_HOV if hov_b else COL_BTN, COL_BTN_BD,
         font_sm, "< BACK", COL_BTN_TXT)
    _cx(screen, font_sm, "ESC to go back", CX, H - 26, (52, 65, 90))
