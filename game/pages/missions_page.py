"""
Lobby MISSIONS page.

Layout
------
  Left half  — Daily Missions   (scrollable card list)
  Right half — Career Missions  (scrollable card list)

Each card
---------
  [ Mission name ]
  [ Description / condition        ]
  [ ████░░░░░░  progress bar  n/N  ]   [ CLAIM ]
"""
import pygame
from game.pages.layout import LOGICAL_W, LOGICAL_H, _TB, _SW

# ── Mission data ──────────────────────────────────────────────────────────────
# (name, description, current, goal)
_DAILY: list[tuple] = [
    ("FIRST BLOOD",     "Deal the killing blow first in a match",         1,  1),
    ("TRIGGER HAPPY",   "Fire 200 bullets in a single session",           137, 200),
    ("DESTROYER",       "Break 5 destructible obstacles",                  5,  5),
    ("MEDIC",           "Collect 3 health packs dropped on the map",       1,  3),
    ("SURVIVOR",        "Win a match with less than 20 % HP remaining",    0,  1),
    ("GOLD RUSH",       "Pick up 10 gold ingots",                          7, 10),
]

_CAREER: list[tuple] = [
    ("VETERAN",         "Play a total of 50 matches",                     23, 50),
    ("KILLING SPREE",   "Accumulate 100 total kills",                     61, 100),
    ("DEMOLISHER",      "Destroy 200 obstacles across all games",        154, 200),
    ("TREASURER",       "Collect 500 gold ingots in total",              312, 500),
    ("MASTER OF ARMS",  "Use every character at least once",               6,   9),
    ("UNTOUCHABLE",     "Win 10 matches without taking damage",            2,  10),
]

# ── Layout ────────────────────────────────────────────────────────────────────
_PAD_L, _PAD_R = 14, 10
_IX  = _SW + _PAD_L                        # content area left edge
_IW  = LOGICAL_W - _IX - _PAD_R           # content area width

_HALF_GAP = 10                             # gap between the two columns
_COL_W    = (_IW - _HALF_GAP) // 2        # width of one column

_COL_L_X  = _IX                           # left column x
_COL_R_X  = _IX + _COL_W + _HALF_GAP     # right column x

_CARD_H   = 88
_CARD_GAP = 8
_TOP_Y    = _TB + 46                       # first card top (below section header)
_BOT_PAD  = 12

# ── Scroll state ──────────────────────────────────────────────────────────────
_scroll_l: int = 0   # left column scroll offset (px, positive = scrolled down)
_scroll_r: int = 0   # right column scroll offset

_SCROLL_SPEED = 28


def _max_scroll(n_cards: int, col_h: int) -> int:
    """Maximum scroll in pixels for a column with n_cards."""
    total = n_cards * (_CARD_H + _CARD_GAP) - _CARD_GAP
    return max(0, total - col_h)


def handle_scroll(event: pygame.event.Event) -> None:
    """Call from lobby.py on MOUSEWHEEL events while missions page is active."""
    global _scroll_l, _scroll_r
    col_h    = LOGICAL_H - _TOP_Y - _BOT_PAD
    if event.x < _COL_R_X:          # mouse in left column
        _scroll_l = max(0, min(_scroll_l - event.y * _SCROLL_SPEED,
                               _max_scroll(len(_DAILY), col_h)))
    else:                            # mouse in right column
        _scroll_r = max(0, min(_scroll_r - event.y * _SCROLL_SPEED,
                               _max_scroll(len(_CAREER), col_h)))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_card(screen: pygame.Surface,
               font_lg: pygame.font.Font,
               font_sm: pygame.font.Font,
               x: int, y: int, w: int,
               name: str, desc: str,
               cur: int, goal: int,
               mx: int, mouse_y: int,
               claimed: bool = False) -> None:
    """Draw one mission card. `claimed` is True when already collected."""
    done      = (cur >= goal)
    r         = pygame.Rect(x, y, w, _CARD_H)

    # Card background
    pygame.draw.rect(screen, (20, 26, 40), r, border_radius=10)
    pygame.draw.rect(screen, (40, 52, 78) if done else (32, 42, 62),
                     r, 2, border_radius=10)

    # Left accent bar (green when done)
    accent = (55, 185, 100) if done else (45, 58, 85)
    pygame.draw.rect(screen, accent, (x, y + 8, 3, _CARD_H - 16), border_radius=2)

    # ── CLAIM button ────────────────────────────────────────────────
    _PAD  = 12
    BTN_W = 68
    BTN_H = _CARD_H - _PAD * 2          # 與 container 上下邊緣同 padding
    BTN_X = x + w - BTN_W - _PAD
    BTN_Y = y + _PAD
    btn_r = pygame.Rect(BTN_X, BTN_Y, BTN_W, BTN_H)

    if claimed:
        btn_bg = (28, 60, 38)
        btn_bd = (45, 105, 62)
        btn_tc = (75, 148, 95)
        btn_lbl = "DONE"
    elif done:
        hov     = btn_r.collidepoint(mx, mouse_y)
        btn_bg  = (48, 168, 88) if hov else (38, 138, 70)
        btn_bd  = (85, 220, 130) if hov else (62, 190, 100)
        btn_tc  = (210, 255, 225)
        btn_lbl = "CLAIM"
    else:
        btn_bg  = (24, 28, 40)
        btn_bd  = (38, 46, 68)
        btn_tc  = (52, 62, 90)
        btn_lbl = "CLAIM"

    pygame.draw.rect(screen, btn_bg, btn_r, border_radius=6)
    pygame.draw.rect(screen, btn_bd, btn_r, 1, border_radius=6)
    bs = font_sm.render(btn_lbl, True, btn_tc)
    screen.blit(bs, (btn_r.centerx - bs.get_width()  // 2,
                     btn_r.centery - bs.get_height() // 2))

    # ── Text area (left of CLAIM button) ──────────────────────────
    TEXT_X  = x + 14
    TEXT_W  = BTN_X - TEXT_X - 8
    TEXT_Y  = y + 10

    nc = (205, 225, 252) if done else (160, 182, 218)
    ns = font_lg.render(name, True, nc)
    screen.blit(ns, (TEXT_X, TEXT_Y))

    ds = font_sm.render(desc, True, (88, 108, 148))
    screen.blit(ds, (TEXT_X, TEXT_Y + ns.get_height() + 3))

    # ── Progress bar ───────────────────────────────────────────────
    BAR_Y  = y + _CARD_H - 20
    BAR_H  = 7
    BAR_W  = TEXT_W
    ratio  = min(1.0, cur / goal) if goal > 0 else 1.0
    fill_w = int(BAR_W * ratio)

    pygame.draw.rect(screen, (28, 35, 54),  (TEXT_X, BAR_Y, BAR_W, BAR_H), border_radius=3)
    if fill_w > 0:
        fill_col = (55, 190, 100) if done else (58, 128, 210)
        pygame.draw.rect(screen, fill_col, (TEXT_X, BAR_Y, fill_w, BAR_H), border_radius=3)
    pygame.draw.rect(screen, (40, 52, 78), (TEXT_X, BAR_Y, BAR_W, BAR_H), 1, border_radius=3)

    # Progress label  "n / N"
    prog_s = font_sm.render(f"{cur} / {goal}", True,
                             (82, 200, 120) if done else (72, 120, 185))
    screen.blit(prog_s, (TEXT_X + BAR_W - prog_s.get_width(),
                         BAR_Y - prog_s.get_height() - 2))


# ── Main draw entry point ─────────────────────────────────────────────────────

def draw(screen: pygame.Surface,
         font_lg: pygame.font.Font,
         font_sm: pygame.font.Font,
         mx: int = 0, my: int = 0) -> None:

    col_h = LOGICAL_H - _TOP_Y - _BOT_PAD   # visible column height

    # ── Section headers ───────────────────────────────────────────────────
    HDR_Y = _TB + 14
    for col_x, label in ((_COL_L_X, "DAILY MISSIONS"), (_COL_R_X, "CAREER MISSIONS")):
        hs = font_lg.render(label, True, (145, 168, 210))
        screen.blit(hs, (col_x, HDR_Y))
        pygame.draw.line(screen, (38, 50, 78),
                         (col_x, HDR_Y + hs.get_height() + 4),
                         (col_x + _COL_W, HDR_Y + hs.get_height() + 4), 1)

    # Centre divider
    div_x = _COL_R_X - _HALF_GAP // 2
    pygame.draw.line(screen, (36, 46, 66),
                     (div_x, _TB + 8), (div_x, LOGICAL_H - 8), 1)

    # ── Clip drawing to content area to hide cards outside scroll window ──
    clip_rect = pygame.Rect(_IX, _TOP_Y, _IW, col_h)
    prev_clip = screen.get_clip()
    screen.set_clip(clip_rect)

    # ── Left column: Daily ───────────────────────────────────────────────
    for i, (name, desc, cur, goal) in enumerate(_DAILY):
        cy = _TOP_Y + i * (_CARD_H + _CARD_GAP) - _scroll_l
        if cy + _CARD_H < _TOP_Y or cy > _TOP_Y + col_h:
            continue   # outside visible area
        _draw_card(screen, font_lg, font_sm,
                   _COL_L_X, cy, _COL_W,
                   name, desc, cur, goal, mx, my)

    # ── Right column: Career ─────────────────────────────────────────────
    for i, (name, desc, cur, goal) in enumerate(_CAREER):
        cy = _TOP_Y + i * (_CARD_H + _CARD_GAP) - _scroll_r
        if cy + _CARD_H < _TOP_Y or cy > _TOP_Y + col_h:
            continue
        _draw_card(screen, font_lg, font_sm,
                   _COL_R_X, cy, _COL_W,
                   name, desc, cur, goal, mx, my)

    screen.set_clip(prev_clip)
