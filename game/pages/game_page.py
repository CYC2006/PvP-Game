"""
Lobby GAME page — mode selector (2×2 grid) + HOST / JOIN buttons.
"""
import pygame
from game.pages.layout import (
    LOGICAL_W, _TB, _SW,
    COL_BTN_BD, COL_HOST, COL_HOST_HOV, COL_HOST_BD, COL_HOST_TXT,
    COL_JOIN,  COL_JOIN_HOV,  COL_JOIN_BD,  COL_JOIN_TXT,
    IC_GAMEPAD, IC_FLAG, IC_CROSSHAIRS, IC_BULLSEYE, IC_USERS,
    IC_SERVER, IC_SIGNIN,
    btn,
)

# ── Mode colours ──────────────────────────────────────────────────────────────
COL_M_SEL     = (22,  54,  92)
COL_M_SEL_BD  = (68, 150, 238)
COL_M_SEL_TXT = (170, 210, 255)
COL_M_UN      = (22,  28,  42)
COL_M_UN_BD   = (38,  48,  70)
COL_M_UN_TXT  = (100, 118, 150)
COL_M_HOV     = (28,  38,  58)
COL_M_HOV_TXT = (148, 172, 212)

# ── Game-mode grid geometry ───────────────────────────────────────────────────
_GX   = 220          # grid left edge
_GY   = 112          # grid top edge
_GRGT = 40           # right margin
_GTW  = (LOGICAL_W - _GX - _GRGT - 10) // 2   # tile width  ≈ 505
_GTH  = 240          # tile height
_GGAP = 10           # gap between tiles

# HOST / JOIN below the 2v2 tile (right column)
_HJBW = (_GTW - _GGAP) // 2
_HJBH = 64
_HJBY = _GY + 2 * _GTH + _GGAP + 14

_hj_x = _GX + _GTW + _GGAP

# ── Static rects (module-level — shared with lobby.py event handler) ──────────
MODES = [
    (IC_CROSSHAIRS, "DEATHMATCH",       "Eliminate the enemy player"),
    (IC_FLAG,       "CAPTURE THE FLAG", "Capture and return the flag"),
    (IC_BULLSEYE,   "CAPTURE POINT",    "Hold key positions longer"),
    (IC_USERS,      "2v2  TEAM",        "Two versus two squad battle"),
]

MODE_RS: list[pygame.Rect] = [
    pygame.Rect(
        _GX + (i % 2) * (_GTW + _GGAP),
        _GY + (i // 2) * (_GTH + _GGAP),
        _GTW, _GTH,
    )
    for i in range(len(MODES))
]

HOST_R = pygame.Rect(_hj_x,                  _HJBY, _HJBW, _HJBH)
JOIN_R = pygame.Rect(_hj_x + _HJBW + _GGAP, _HJBY, _HJBW, _HJBH)


# ── Draw ──────────────────────────────────────────────────────────────────────

def draw(screen: pygame.Surface,
         font_lg: pygame.font.Font,
         font_sm: pygame.font.Font,
         mx: int, my: int,
         sel_mode: int) -> None:

    # Section label
    lbl = font_lg.render(f"{IC_GAMEPAD}  GAME  MODE", True, (68, 105, 158))
    screen.blit(lbl, (_GX, _GY - lbl.get_height() - 8))

    # 2×2 tile grid
    for i, (r, (icon, name, _desc)) in enumerate(zip(MODE_RS, MODES)):
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

        ic_s = font_sm.render(icon, True, tc)
        nm_s = font_lg.render(name, True, tc)
        ty   = r.y + 16
        screen.blit(ic_s, (r.x + 16,
                            ty + (nm_s.get_height() - ic_s.get_height()) // 2))
        screen.blit(nm_s, (r.x + 16 + ic_s.get_width() + 10, ty))

    # HOST / JOIN
    btn(screen, HOST_R,
        COL_HOST_HOV if HOST_R.collidepoint(mx, my) else COL_HOST,
        COL_HOST_BD, font_lg, f"{IC_SERVER}  HOST", COL_HOST_TXT, radius=10)

    btn(screen, JOIN_R,
        COL_JOIN_HOV if JOIN_R.collidepoint(mx, my) else COL_JOIN,
        COL_JOIN_BD, font_lg, f"{IC_SIGNIN}  JOIN", COL_JOIN_TXT, radius=10)
