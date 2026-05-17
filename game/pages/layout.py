"""
Shared layout constants, colours, Nerd Font icons and tiny draw helpers.
All lobby page modules import from here.
"""
import pygame
from game.charselect import LOGICAL_W, LOGICAL_H

# ── Colours ───────────────────────────────────────────────────────────────────
COL_BG        = (15,  18,  26)
COL_SEP       = (36,  46,  66)
COL_TEXT      = (220, 220, 220)
COL_HINT      = ( 95, 112, 145)
COL_TITLE     = (255, 230, 100)

# Generic buttons (sidebar tabs, misc)
COL_BTN       = (26,  34,  50)
COL_BTN_HOV   = (36,  48,  72)
COL_BTN_BD    = (48,  62,  90)
COL_BTN_TXT   = (145, 162, 195)

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

# Player info (top bar)
COL_PL_BG     = (20,  26,  40)
COL_PL_BD     = (45,  58,  85)
COL_PL_NAME   = (205, 210, 228)
COL_LEVEL     = (255, 198,  52)

# IP / input (join screen)
COL_IP_VAL    = ( 72, 212, 128)
COL_IP_DIM    = ( 95, 152, 122)
COL_INPUT_BG  = (20,  26,  40)
COL_INPUT_BD  = ( 72, 132, 212)

# ── Layout ────────────────────────────────────────────────────────────────────
_TB = 68    # top-bar height
_SW = 170   # sidebar width

# ── Nerd Fonts icons (Font Awesome via MapleMono-NF) ─────────────────────────
# Using explicit Unicode escapes so the codepoints survive any encoding round-trip.
IC_USER       = ''   # nf-fa-user
IC_COG        = ''   # nf-fa-cog
IC_CART       = ''   # nf-fa-shopping-cart
IC_TASKS      = ''   # nf-fa-tasks
IC_USERS      = ''   # nf-fa-users
IC_GAMEPAD    = ''   # nf-fa-gamepad
IC_FLAG       = ''   # nf-fa-flag
IC_CROSSHAIRS = ''   # nf-fa-crosshairs
IC_BULLSEYE   = ''   # nf-fa-bullseye
IC_SERVER     = ''   # nf-fa-server
IC_SIGNIN     = ''   # nf-fa-sign-in
IC_VOLUME     = ''   # nf-fa-volume-up
IC_BOLT       = ''   # nf-fa-bolt
IC_HOME       = ''   # nf-fa-home

# ── Tiny draw helpers ─────────────────────────────────────────────────────────

def btn(surf: pygame.Surface, rect: pygame.Rect,
        bg, bd, font: pygame.font.Font, label: str, col, radius: int = 9) -> None:
    """Draw a filled rounded-rect button with centred label."""
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    pygame.draw.rect(surf, bd, rect, 2, border_radius=radius)
    s = font.render(label, True, col)
    surf.blit(s, (rect.centerx - s.get_width()  // 2,
                  rect.centery - s.get_height() // 2))


def cx(surf: pygame.Surface, font: pygame.font.Font,
       text: str, centre_x: int, y: int, color) -> None:
    """Draw horizontally-centred text."""
    s = font.render(text, True, color)
    surf.blit(s, (centre_x - s.get_width() // 2, y))
