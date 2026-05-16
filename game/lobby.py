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
from game.charselect import LOGICAL_W, LOGICAL_H, CHARACTERS as _CHAR_LIST, _load_sprite as _cs_load_sprite

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
_TB   = 68    # top-bar height
_SW   = 170   # sidebar width

# 2×2 game-mode tile grid
_GX   = 220   # grid left edge (50 px right of sidebar)
_GY   = 112   # grid top edge
_GRGT = 40    # right margin from screen edge
_GTW  = (LOGICAL_W - _GX - _GRGT - 10) // 2   # = 505
_GTH  = 240   # tile height
_GGAP = 10    # gap between tiles (both axes)

# HOST / JOIN — side by side below the 2v2 TEAM tile (right column)
_HJBW = (_GTW - _GGAP) // 2   # two buttons together = one tile width
_HJBH = 64
_HJBY = _GY + 2 * _GTH + _GGAP + 14   # below bottom row

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

# ─── Characters page data ─────────────────────────────────────────────────────
IC_STAR  = ''   # fa-star  (filled)
IC_STAR0 = ''   # fa-star-o (empty)

# (ATK, AGI, DEF, UTL) out of 5
_RATINGS: dict = {
    'hitman1':    (3, 3, 2, 4),
    'manBlue':    (4, 1, 5, 3),
    'manBrown':   (4, 2, 3, 2),
    'manOld':     (5, 3, 1, 3),
    'robot1':     (3, 2, 3, 2),
    'soldier1':   (3, 4, 4, 2),
    'survivor1':  (3, 5, 1, 4),
    'womanGreen': (2, 3, 2, 5),
    'zoimbie1':   (3, 3, 4, 1),
}

# Four skill slots per character: RMB / SPACE / E / R  (in that fixed order)
# (skill_name, key_label, cooldown_secs, description)
_SKILLS: dict = {
    'hitman1': [
        ("BURST FIRE",    "RMB",   5,
         "Fires three rounds in rapid succession toward the cursor. Ideal for punishing an exposed or retreating enemy at close to mid range."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("FLASH GRENADE", "E",     6,
         "Lobs a stun grenade that detonates on landing. Any enemy inside the blast radius is briefly blinded and disoriented."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'manBlue': [
        ("AIRSTRIKE",     "RMB",   8,
         "Calls a sequence of bombs along the aimed trajectory. Impacts land in a line with a short delay, covering a wide zone."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("FRAG GRENADE",  "E",     7,
         "Hurls a fragmentation grenade that explodes on impact, dealing heavy damage to all enemies within the blast radius."),
        ("GIANT FORM",    "R",     20,
         "Transforms into a massive giant for a limited time. Greatly increases body size, armor thickness, and raw damage output."),
    ],
    'manBrown': [
        ("IMPACT ROUND",  "RMB",   4,
         "Fires an explosive bullet that detonates on contact. Deals burst damage to everything in a small radius around the point of impact."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("PROXIMITY MINE","E",     10,
         "Places a hidden mine at the current position. Triggers automatically when an enemy steps within detection range and detonates."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'manOld': [
        ("—",             "RMB",   0,
         "Skill under development."),
        ("MINI GRENADES", "SPACE", 4,
         "Scatters a cluster of small grenades in an arc. Each grenade lands independently and detonates with its own small explosion."),
        ("LOG BARRIER",   "E",     10,
         "Erects wooden barriers in the aimed direction. Blocks movement and line of sight, forcing enemies to reposition or break through."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'robot1': [
        ("—",             "RMB",   0,
         "Skill under development."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("—",             "E",     0,
         "Skill under development."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'soldier1': [
        ("STUN ROUND",    "RMB",   6,
         "Fires a specialized round that stuns the target on impact. Briefly halts enemy movement, leaving them exposed to follow-up fire."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("—",             "E",     0,
         "Skill under development."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'survivor1': [
        ("BLADE STRIKE",  "RMB",   5,
         "Hurls a powered shuriken in the aimed direction. Deals concentrated damage and cuts through any enemy in its path."),
        ("SPEED SURGE",   "SPACE", 10,
         "Activates a short burst of enhanced movement speed. Use it to close the gap on an enemy or escape a dangerous situation."),
        ("SMOKE SCREEN",  "E",     8,
         "Deploys a smoke grenade creating a persistent cloud. Both sides lose visibility in the area, ideal for breaking line of sight."),
        ("SHADOW RUSH",   "R",     7,
         "Dashes swiftly toward the cursor, releasing a spinning blade arc upon arrival that strikes any enemy caught in the sweep."),
    ],
    'womanGreen': [
        ("—",             "RMB",   0,
         "Skill under development."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("—",             "E",     0,
         "Skill under development."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'zoimbie1': [
        ("—",             "RMB",   0,
         "Skill under development."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("—",             "E",     0,
         "Skill under development."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
}

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
    state          = "main"   # "main" | "host" | "join"
    page           = "game"   # "game" | "shop" | "characters" | "missions"
    sel_mode       = 0
    char_page_idx  = 0        # selected char on characters page
    ip_text        = ""
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

    # Sidebar nav tabs: GAME / SHOP / CHARACTERS / MISSIONS
    _TAB_W = _SW - 20
    _TAB_H = 50
    _TAB_X = 10
    _TAB_Y0 = _TB + 18
    _TAB_STEP = _TAB_H + 8
    SIDEBAR_TABS = [
        ("game",       IC_GAMEPAD, "GAME"),
        ("shop",       IC_CART,    "SHOP"),
        ("characters", IC_USER,    "CHARACTERS"),
        ("missions",   IC_TASKS,   "MISSIONS"),
    ]
    TAB_RS = [
        pygame.Rect(_TAB_X, _TAB_Y0 + i * _TAB_STEP, _TAB_W, _TAB_H)
        for i in range(len(SIDEBAR_TABS))
    ]

    # Game-mode tiles (2×2 grid)
    MODE_RS = [
        pygame.Rect(
            _GX + (i % 2) * (_GTW + _GGAP),
            _GY + (i // 2) * (_GTH + _GGAP),
            _GTW, _GTH
        )
        for i in range(len(_MODES))
    ]

    # HOST / JOIN — side by side below the 2v2 TEAM tile (right column)
    _hj_x  = _GX + _GTW + _GGAP
    HOST_R = pygame.Rect(_hj_x,                   _HJBY, _HJBW, _HJBH)
    JOIN_R = pygame.Rect(_hj_x + _HJBW + _GGAP,   _HJBY, _HJBW, _HJBH)

    # Characters page thumbnail strip rects (mirrors _draw_characters_page layout)
    _CP_IX   = _SW + 14
    _CP_IW   = LOGICAL_W - _CP_IX - 10
    _CP_SY   = LOGICAL_H - 90
    _CP_N    = len(_CHAR_LIST)
    _CP_TGAP = 8
    _CP_TW   = (_CP_IW - _CP_TGAP * (_CP_N - 1)) // _CP_N
    _CP_TH   = 90 - 18
    CHAR_THUMB_RS = [
        pygame.Rect(_CP_IX + i * (_CP_TW + _CP_TGAP), _CP_SY + 8, _CP_TW, _CP_TH)
        for i in range(_CP_N)
    ]

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
                    # Sidebar tab switching
                    for (pg, _, _lbl), r in zip(SIDEBAR_TABS, TAB_RS):
                        if r.collidepoint(mx, my):
                            page = pg

                    if page == "game":
                        for i, r in enumerate(MODE_RS):
                            if r.collidepoint(mx, my):
                                sel_mode = i
                        if HOST_R.collidepoint(mx, my):
                            state = "host"
                        elif JOIN_R.collidepoint(mx, my):
                            state = "join"

                    elif page == "characters":
                        for i, r in enumerate(CHAR_THUMB_RS):
                            if r.collidepoint(mx, my):
                                char_page_idx = i

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
            _draw_topbar(screen, font_lg, font_sm, SFX_R, SET_R, mx, my)
            _draw_sidebar(screen, font_lg, font_sm, page, SIDEBAR_TABS, TAB_RS, mx, my)
            if page == "game":
                _draw_game_page(screen, font_lg, font_sm, mx, my,
                                sel_mode, MODE_RS, HOST_R, JOIN_R)
            elif page == "characters":
                _draw_characters_page(screen, font_lg, font_sm, char_page_idx)
            else:
                _draw_placeholder(screen, font_lg, page)
        elif state == "host":
            _draw_host(screen, font_lg, font_sm,
                       local_ip, pub_ip[0], BACK_R, START_R, mx, my)
        elif state == "join":
            _draw_join(screen, font_lg, font_sm,
                       ip_text, cursor_on, BACK_R, CONN_R, mx, my)

        pygame.display.flip()


# ─── Persistent chrome ────────────────────────────────────────────────────────

def _draw_topbar(screen, font_lg, font_sm, sfx_r, set_r, mx, my):
    W = LOGICAL_W
    pygame.draw.line(screen, COL_SEP, (0, _TB), (W, _TB), 1)

    pl_r = pygame.Rect(18, 10, 235, 48)
    pygame.draw.rect(screen, COL_PL_BG, pl_r, border_radius=8)
    pygame.draw.rect(screen, COL_PL_BD, pl_r, 2, border_radius=8)
    ns = font_lg.render(f"{IC_USER}  PLAYER_001", True, COL_PL_NAME)
    screen.blit(ns, (pl_r.x + 12, pl_r.y + 5))
    ls = font_sm.render(f"{IC_BOLT}  Lv. 1", True, COL_LEVEL)
    screen.blit(ls, (pl_r.x + 12, pl_r.y + 27))

    for r, icon in ((sfx_r, IC_VOLUME), (set_r, IC_COG)):
        bg = COL_BTN_HOV if r.collidepoint(mx, my) else COL_BTN
        _btn(screen, r, bg, COL_BTN_BD, font_lg, icon, COL_BTN_TXT, radius=8)


def _draw_sidebar(screen, font_lg, font_sm, page, tabs, tab_rs, mx, my):
    H = LOGICAL_H
    pygame.draw.line(screen, COL_SEP, (_SW, _TB), (_SW, H), 1)

    COL_TAB_ACT    = (28,  38,  58)
    COL_TAB_ACT_BD = ( 60, 140, 230)
    COL_TAB_TXT_A  = (180, 215, 255)

    for (pg, icon, lbl), r in zip(tabs, tab_rs):
        active   = (pg == page)
        hovering = (not active) and r.collidepoint(mx, my)

        if active:
            bg, bd, tc = COL_TAB_ACT, COL_TAB_ACT_BD, COL_TAB_TXT_A
        elif hovering:
            bg, bd, tc = COL_BTN_HOV, COL_BTN_BD,     COL_BTN_TXT
        else:
            bg, bd, tc = COL_BTN,     COL_BTN_BD,      COL_BTN_TXT

        pygame.draw.rect(screen, bg, r, border_radius=8)
        pygame.draw.rect(screen, bd, r, 2, border_radius=8)

        # Active left accent bar
        if active:
            pygame.draw.rect(screen, COL_TAB_ACT_BD,
                             (r.x, r.y + 6, 3, r.h - 12), border_radius=2)

        ic_s = font_sm.render(icon, True, tc)
        nm_s = font_sm.render(lbl,  True, tc)
        total_w = ic_s.get_width() + 8 + nm_s.get_width()
        bx = r.centerx - total_w // 2
        by = r.centery - nm_s.get_height() // 2
        screen.blit(ic_s, (bx, r.centery - ic_s.get_height() // 2))
        screen.blit(nm_s, (bx + ic_s.get_width() + 8, by))


# ─── Page: GAME ───────────────────────────────────────────────────────────────

def _draw_game_page(screen, font_lg, font_sm, mx, my,
                    sel_mode, mode_rs, host_r, join_r):
    # Section label
    sec_lbl = font_lg.render(f"{IC_GAMEPAD}  GAME  MODE", True, (68, 105, 158))
    screen.blit(sec_lbl, (_GX, _GY - sec_lbl.get_height() - 8))

    # 2×2 tile grid
    for i, (r, (icon, name, desc)) in enumerate(zip(mode_rs, _MODES)):
        selected = (i == sel_mode)
        hovering = (not selected) and r.collidepoint(mx, my)

        if selected:
            bg, bd, tc = COL_M_SEL,  COL_M_SEL_BD, COL_M_SEL_TXT
        elif hovering:
            bg, bd, tc = COL_M_HOV,  COL_M_UN_BD,  COL_M_HOV_TXT
        else:
            bg, bd, tc = COL_M_UN,   COL_M_UN_BD,  COL_M_UN_TXT

        pygame.draw.rect(screen, bg, r, border_radius=10)
        pygame.draw.rect(screen, bd, r, 2, border_radius=10)

        ic_surf = font_sm.render(icon, True, tc)
        nm_surf = font_lg.render(name, True, tc)
        ty = r.y + 16
        screen.blit(ic_surf, (r.x + 16,
                               ty + (nm_surf.get_height() - ic_surf.get_height()) // 2))
        screen.blit(nm_surf, (r.x + 16 + ic_surf.get_width() + 10, ty))

    # HOST / JOIN
    hh = host_r.collidepoint(mx, my)
    _btn(screen, host_r,
         COL_HOST_HOV if hh else COL_HOST, COL_HOST_BD,
         font_lg, f"{IC_SERVER}  HOST", COL_HOST_TXT, radius=10)

    jh = join_r.collidepoint(mx, my)
    _btn(screen, join_r,
         COL_JOIN_HOV if jh else COL_JOIN, COL_JOIN_BD,
         font_lg, f"{IC_SIGNIN}  JOIN", COL_JOIN_TXT, radius=10)


# ─── Page: placeholder ────────────────────────────────────────────────────────

def _draw_placeholder(screen, font_lg, page: str):
    CX = (_SW + LOGICAL_W) // 2
    CY = (_TB + LOGICAL_H) // 2
    label = font_lg.render(page.upper(), True, (40, 52, 78))
    screen.blit(label, (CX - label.get_width() // 2, CY - label.get_height() // 2))



# ─── Page: CHARACTERS ────────────────────────────────────────────────────────

def _draw_wrapped(screen, font, text: str, x, y, max_w, max_h, color):
    """Word-wrap `text` and draw within the given bounding box."""
    words = text.split()
    lines = []
    line: list = []
    for word in words:
        test = ' '.join(line + [word])
        if font.size(test)[0] <= max_w:
            line.append(word)
        else:
            if line:
                lines.append(' '.join(line))
            line = [word]
    if line:
        lines.append(' '.join(line))
    lh = font.get_height() + 3
    for i, ln in enumerate(lines):
        if i * lh >= max_h:
            break
        screen.blit(font.render(ln, True, color), (x, y + i * lh))


def _draw_characters_page(screen, font_lg, font_sm, char_idx: int):
    # ── Layout constants ──────────────────────────────────────────────────
    PAD_L, PAD_R = 14, 10
    IX  = _SW + PAD_L                        # content inner x  (184)
    IW  = LOGICAL_W - IX - PAD_R            # content inner width (1086)

    STRIP_H = 90
    STRIP_Y = LOGICAL_H - STRIP_H           # thumbnail strip top  (630)

    DET_Y = _TB + 12                         # detail area top      (80)
    DET_H = STRIP_Y - DET_Y - 8             # detail area height   (542)

    LW  = 268                                # left column width
    RX  = IX + LW + 12                      # right section x      (464)
    RW  = (IX + IW) - RX                    # right section width  (806)

    char     = _CHAR_LIST[char_idx]
    char_key = char["char_key"]

    # ── Character thumbnail strip ─────────────────────────────────────────
    N_CHARS = len(_CHAR_LIST)
    T_GAP   = 8
    TW      = (IW - T_GAP * (N_CHARS - 1)) // N_CHARS
    TH      = STRIP_H - 18

    pygame.draw.line(screen, COL_SEP,
                     (IX, STRIP_Y - 5), (IX + IW, STRIP_Y - 5), 1)

    for i, c in enumerate(_CHAR_LIST):
        tx  = IX + i * (TW + T_GAP)
        ty  = STRIP_Y + 8
        r   = pygame.Rect(tx, ty, TW, TH)
        sel = (i == char_idx)

        pygame.draw.rect(screen, (28, 48, 72) if sel else (20, 26, 40),
                         r, border_radius=6)
        pygame.draw.rect(screen, (72, 150, 238) if sel else (38, 48, 70),
                         r, 2, border_radius=6)

        sp = _cs_load_sprite(c)
        if sp.get_width() > 0 and sp.get_height() > 0:
            max_th = TH - font_sm.get_height() - 6
            sc = min((TW - 8) / sp.get_width(), max_th / sp.get_height())
            sw2 = max(1, int(sp.get_width() * sc))
            sh2 = max(1, int(sp.get_height() * sc))
            mini = pygame.transform.scale(sp, (sw2, sh2))
            screen.blit(mini, (r.centerx - sw2 // 2, ty + 2))

        nc = (180, 215, 255) if sel else (80, 100, 135)
        ns = font_sm.render(c["name"], True, nc)
        screen.blit(ns, (r.centerx - ns.get_width() // 2,
                          ty + TH - ns.get_height() - 2))

    # ── Left column ───────────────────────────────────────────────────────
    # Sprite display box
    SP_H    = 210
    sp_rect = pygame.Rect(IX, DET_Y, LW, SP_H)
    pygame.draw.rect(screen, (20, 26, 40), sp_rect, border_radius=10)
    pygame.draw.rect(screen, (38, 50, 75), sp_rect, 2, border_radius=10)

    sp = _cs_load_sprite(char)
    if sp.get_width() > 0 and sp.get_height() > 0:
        sc  = min((LW - 16) / sp.get_width(), (SP_H - 16) / sp.get_height())
        sw2 = max(1, int(sp.get_width() * sc))
        sh2 = max(1, int(sp.get_height() * sc))
        big = pygame.transform.scale(sp, (sw2, sh2))
        screen.blit(big, (IX + LW // 2 - sw2 // 2, DET_Y + SP_H // 2 - sh2 // 2))

    # Character name
    nm_s = font_lg.render(char["name"], True, (220, 232, 250))
    nm_y = DET_Y + SP_H + 6
    screen.blit(nm_s, (IX + LW // 2 - nm_s.get_width() // 2, nm_y))

    # Stats + ratings panel
    PANEL_Y = nm_y + nm_s.get_height() + 6
    PANEL_H = DET_Y + DET_H - PANEL_Y
    pan_r   = pygame.Rect(IX, PANEL_Y, LW, PANEL_H)
    pygame.draw.rect(screen, (20, 26, 40), pan_r, border_radius=10)
    pygame.draw.rect(screen, (38, 50, 75), pan_r, 2, border_radius=10)

    LBL_X = IX + 10
    VAL_X = IX + LW - 8
    sy    = PANEL_Y + 10

    spd = char["speed"]
    rt  = char["reload_time"]
    fi  = char["fire_interval"]
    stats_rows = [
        ("HP",       str(char["hp"])        if char["hp"]    else "—"),
        ("SPEED",    f"{spd} px/s"          if spd           else "—"),
        ("GUN",      char["gun"]            if char["gun"]   else "—"),
        ("DAMAGE",   char["damage"]         if char["damage"] else "—"),
        ("AMMO",     str(char["ammo"])      if char["ammo"]  else "—"),
        ("RELOAD",   f"{rt}s"              if rt            else "—"),
        ("INTERVAL", f"{fi}s"              if fi            else "—"),
    ]
    for lbl, val in stats_rows:
        ls = font_sm.render(lbl, True, (90, 112, 155))
        vs = font_sm.render(val, True, (195, 210, 232))
        screen.blit(ls, (LBL_X, sy))
        screen.blit(vs, (VAL_X - vs.get_width(), sy))
        sy += font_sm.get_height() + 3

    # Divider
    sy += 4
    pygame.draw.line(screen, (38, 50, 75), (IX + 8, sy), (IX + LW - 8, sy), 1)
    sy += 8

    # Star ratings
    atk, agi, dfs, utl = _RATINGS.get(char_key, (3, 3, 3, 3))
    rating_rows = [
        ("ATTACK",  atk, (255, 198,  52)),
        ("AGILITY", agi, ( 72, 218, 158)),
        ("DEFENSE", dfs, (102, 172, 248)),
        ("UTILITY", utl, (218, 142, 255)),
    ]
    star_w     = font_sm.size(IC_STAR)[0]
    star_gap   = 3
    stars_span = 5 * star_w + 4 * star_gap
    for rname, rval, rcol in rating_rows:
        screen.blit(font_sm.render(rname, True, (90, 112, 155)), (LBL_X, sy))
        sx0 = IX + LW - stars_span - 10
        for si in range(5):
            ic  = IC_STAR if si < rval else IC_STAR0
            col = rcol    if si < rval else (45, 55, 80)
            screen.blit(font_sm.render(ic, True, col),
                        (sx0 + si * (star_w + star_gap), sy))
        sy += font_sm.get_height() + 5

    # ── Right: 4 skill boxes in 2 × 2 grid ───────────────────────────────
    SK_GAP = 10
    SK_W   = (RW - SK_GAP) // 2
    SK_H   = (DET_H - SK_GAP) // 2

    skills = _SKILLS.get(char_key, [("—", "", 0, "Skill under development.")] * 4)

    BADGE_W = 54

    for si, (sname, skey, scd, sdesc) in enumerate(skills):
        col = si % 2
        row = si // 2
        skx = RX + col * (SK_W + SK_GAP)
        sky = DET_Y + row * (SK_H + SK_GAP)
        sr  = pygame.Rect(skx, sky, SK_W, SK_H)

        pygame.draw.rect(screen, (20, 26, 40), sr, border_radius=10)
        pygame.draw.rect(screen, (38, 50, 75), sr, 2, border_radius=10)

        HDR_Y = sky + 12

        # Key badge
        badge_r = pygame.Rect(skx + 10, HDR_Y - 3, BADGE_W, 24)
        pygame.draw.rect(screen, (30, 42, 66), badge_r, border_radius=5)
        pygame.draw.rect(screen, (55, 75, 115), badge_r, 1, border_radius=5)
        bk = font_sm.render(skey, True, (110, 148, 205))
        screen.blit(bk, (badge_r.centerx - bk.get_width() // 2,
                          badge_r.centery - bk.get_height() // 2))

        # Skill name
        sn_c = (185, 210, 248) if sname != "—" else (55, 68, 95)
        sn_s = font_lg.render(sname, True, sn_c)
        screen.blit(sn_s, (skx + 10 + BADGE_W + 8, HDR_Y - 1))

        # Cooldown (right-aligned)
        if scd > 0:
            cd_s = font_sm.render(f"CD  {scd}s", True, (95, 140, 195))
            screen.blit(cd_s, (skx + SK_W - cd_s.get_width() - 10, HDR_Y + 4))

        # Separator below header
        SEP_Y = HDR_Y + font_lg.get_height() + 6
        pygame.draw.line(screen, (38, 50, 75),
                         (skx + 10, SEP_Y), (skx + SK_W - 10, SEP_Y), 1)

        # Description
        DESC_Y = SEP_Y + 8
        DESC_H = sky + SK_H - DESC_Y - 8
        dc = (135, 160, 198) if sname != "—" else (55, 68, 95)
        _draw_wrapped(screen, font_sm, sdesc,
                      skx + 12, DESC_Y, SK_W - 24, DESC_H, dc)


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
