"""
Character selection screen — horizontal carousel.
Scroll wheel / ← → to browse; centre card is the selected character.
Click or Enter/Space to confirm.

All character stats are imported from game.char_data (single source of truth).
"""
import os
import time
import pygame
from game.char_data import CHAR_STATS, CHAR_ORDER, get_stat

LOGICAL_W = 1280
LOGICAL_H = 720

# ── 角色清單（從 char_data 自動建構，不在此處維護數值）─────────────────────
CHARACTERS = [
    {
        "char_key":    key,
        "folder":      CHAR_STATS[key]["folder"],
        "name":        get_stat(key, "name"),
        "hp":          get_stat(key, "hp"),
        "gun":         get_stat(key, "gun"),
        "damage":      get_stat(key, "damage"),
        "ammo":        get_stat(key, "mag"),
        "reload_time": get_stat(key, "reload_time"),
        "fire_rate":   get_stat(key, "fire_rate"),
    }
    for key in CHAR_ORDER
]
N = len(CHARACTERS)

# ── 版面 ──────────────────────────────────────────────────────────────────
CARD_W       = 190
CARD_H       = 265
CARD_SPACING = 225
CENTER_X     = LOGICAL_W // 2
CARD_Y       = 300          # 卡片中心 y（稍微往上移以騰出下方空間）

# ── 顏色 ──────────────────────────────────────────────────────────────────
COL_BG          = (20,  24,  32)
COL_CARD        = (38,  46,  62)
COL_CARD_CENTER = (28,  68,  48)
COL_BORDER      = (60,  75, 100)
COL_BORDER_CTR  = (80, 220, 130)
COL_TEXT        = (220, 220, 220)
COL_TITLE       = (255, 230, 100)
COL_NAME_CTR    = (255, 255, 255)
COL_NAME        = (150, 155, 168)
COL_ARROW       = (170, 180, 200)
COL_ARROW_HOV   = (255, 230, 100)
COL_READY       = ( 80, 220, 130)
COL_WAIT        = (140, 200, 255)
COL_STATUS      = (190, 195, 210)
COL_HINT        = (110, 130, 160)

# Stats panel
COL_PANEL_BG    = (30,  36,  50)
COL_PANEL_BD    = (55,  68,  95)
COL_STAT_LABEL  = (110, 130, 160)
COL_STAT_VAL    = (230, 235, 245)
COL_STAT_EMPTY  = (70,  78, 100)

# ── Carousel 狀態（模組全域）────────────────────────────────────────────
_target_idx:  int   = 0
_anim_offset: float = 0.0

# ── Sprite 快取 ───────────────────────────────────────────────────────────
_sprite_cache: dict = {}
_SPRITE_H = 148


def _load_sprite(char: dict) -> pygame.Surface:
    key = char["char_key"]
    if key not in _sprite_cache:
        path = os.path.join("assets", "Player", char["folder"],
                            f"{char['char_key']}_stand.png")
        try:
            img   = pygame.image.load(path).convert_alpha()
            ratio = _SPRITE_H / img.get_height()
            new_w = max(1, int(img.get_width() * ratio))
            raw   = pygame.transform.scale(img, (new_w, _SPRITE_H))
            _sprite_cache[key] = pygame.transform.rotate(raw, 90)
        except Exception:
            surf = pygame.Surface((80, _SPRITE_H), pygame.SRCALPHA)
            pygame.draw.circle(surf, (160, 160, 160, 200),
                               (40, _SPRITE_H // 2), 40)
            _sprite_cache[key] = surf
    return _sprite_cache[key]


# ── 公開 API ──────────────────────────────────────────────────────────────

def reset() -> None:
    global _target_idx, _anim_offset
    _target_idx  = 0
    _anim_offset = 0.0


def handle_event(event: pygame.event.Event) -> bool:
    """回傳 True 表示玩家確認選擇。"""
    global _target_idx
    if event.type == pygame.MOUSEWHEEL:
        _target_idx = max(0, min(N - 1, _target_idx - event.y))
    elif event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_LEFT,  pygame.K_a):
            _target_idx = max(0, _target_idx - 1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            _target_idx = min(N - 1, _target_idx + 1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            return True
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        return True
    return False


def selected_char() -> dict:
    return CHARACTERS[_target_idx]


def selected_idx() -> int:
    return _target_idx


def update(dt: float) -> None:
    global _anim_offset
    _anim_offset += (_target_idx - _anim_offset) * min(1.0, 14.0 * dt)


# ── 繪圖 ──────────────────────────────────────────────────────────────────

def draw_char_select(screen: pygame.Surface,
                     font_lg: pygame.font.Font,
                     font_sm: pygame.font.Font,
                     my_ready: bool,
                     opponent_ready: bool) -> None:
    screen.fill(COL_BG)

    # ── 標題 ──────────────────────────────────────────────────────
    title = font_lg.render("SELECT YOUR CHARACTER", True, COL_TITLE)
    screen.blit(title, (CENTER_X - title.get_width() // 2, 28))

    # ── Carousel 卡片 ──────────────────────────────────────────────
    for i, char in enumerate(CHARACTERS):
        d     = i - _anim_offset
        abs_d = abs(d)
        if abs_d > 3.2:
            continue

        scale   = max(0.44, 1.0 - abs_d * 0.22)
        cx      = int(CENTER_X + d * CARD_SPACING)
        w, h    = int(CARD_W * scale), int(CARD_H * scale)
        rect    = pygame.Rect(cx - w // 2, CARD_Y - h // 2, w, h)
        alpha   = max(55, int(255 - abs_d * 95))

        card_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        is_center = abs_d < 0.4
        bg_col    = COL_CARD_CENTER if is_center else COL_CARD
        bd_col    = COL_BORDER_CTR  if is_center else COL_BORDER
        bd_w      = 3 if is_center else 2

        pygame.draw.rect(card_surf, (*bg_col, alpha), (0, 0, w, h), border_radius=14)
        pygame.draw.rect(card_surf, (*bd_col, alpha), (0, 0, w, h), bd_w, border_radius=14)

        # Sprite
        raw_sprite = _load_sprite(char)
        sp_scale   = scale * 0.92
        sp_w = max(1, int(raw_sprite.get_width()  * sp_scale))
        sp_h = max(1, int(raw_sprite.get_height() * sp_scale))
        sprite = pygame.transform.scale(raw_sprite, (sp_w, sp_h))
        sprite.set_alpha(alpha)
        card_surf.blit(sprite, (w // 2 - sp_w // 2, int(h * 0.08)))

        # 名稱（放大字體）
        name_col  = COL_NAME_CTR if is_center else COL_NAME
        name_surf = font_lg.render(char["name"], True, (*name_col, alpha))
        card_surf.blit(name_surf,
                       (w // 2 - name_surf.get_width() // 2, h - int(h * 0.18)))

        screen.blit(card_surf, rect.topleft)

    # ── 導航箭頭 ──────────────────────────────────────────────────
    mx, my_pos = pygame.mouse.get_pos()
    arrow_y    = CARD_Y

    left_pts  = [(CENTER_X - CARD_SPACING * 1.7,      arrow_y),
                 (CENTER_X - CARD_SPACING * 1.7 + 26, arrow_y - 16),
                 (CENTER_X - CARD_SPACING * 1.7 + 26, arrow_y + 16)]
    right_pts = [(CENTER_X + CARD_SPACING * 1.7,      arrow_y),
                 (CENTER_X + CARD_SPACING * 1.7 - 26, arrow_y - 16),
                 (CENTER_X + CARD_SPACING * 1.7 - 26, arrow_y + 16)]

    def _arrow_col(pts):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        r = pygame.Rect(min(xs)-6, min(ys)-6,
                        max(xs)-min(xs)+12, max(ys)-min(ys)+12)
        return COL_ARROW_HOV if r.collidepoint(mx, my_pos) else COL_ARROW

    if _target_idx > 0:
        pygame.draw.polygon(screen, _arrow_col(left_pts),  left_pts)
    if _target_idx < N - 1:
        pygame.draw.polygon(screen, _arrow_col(right_pts), right_pts)

    # ── 合併狀態列（一行）─────────────────────────────────────────
    status_y = CARD_Y + CARD_H // 2 + 22

    char_name = CHARACTERS[_target_idx]["name"]
    if my_ready:
        you_part = f"YOU: {char_name} ✓"
        you_col  = COL_READY
    else:
        you_part = f"YOU: {char_name}"
        you_col  = COL_STATUS

    if opponent_ready:
        op_part = "OPPONENT: READY ✓"
        op_col  = COL_READY
    else:
        op_part = "OPPONENT: waiting..."
        op_col  = COL_STATUS

    hint_part = "" if my_ready else "  •  ← → scroll / Click or Enter to confirm"

    # 分段渲染，讓各段有自己的顏色
    you_surf  = font_sm.render(you_part, True, you_col)
    sep_surf  = font_sm.render("   |   ", True, COL_HINT)
    op_surf   = font_sm.render(op_part,  True, op_col)
    hint_surf = font_sm.render(hint_part, True, COL_HINT)

    total_w = (you_surf.get_width() + sep_surf.get_width() +
               op_surf.get_width() + hint_surf.get_width())
    x = CENTER_X - total_w // 2
    for surf in (you_surf, sep_surf, op_surf, hint_surf):
        screen.blit(surf, (x, status_y))
        x += surf.get_width()

    # ── 數值面板 ──────────────────────────────────────────────────
    _draw_stats_panel(screen, font_lg, font_sm, status_y + 34)


def _draw_stats_panel(screen, font_lg, font_sm, top_y: int) -> None:
    """顯示中央角色的數值：HP | GUN | DAMAGE | AMMO | RELOAD | RATE。"""
    char = CHARACTERS[_target_idx]

    reload = char["reload_time"]
    reload_str = f"{reload}s" if reload else ""

    rate = char["fire_rate"]
    if rate and rate > 0:
        rate_str = f"{int(rate) if rate == int(rate) else rate}/s"
    else:
        rate_str = ""

    fields = [
        ("HP",     str(char["hp"])),
        ("GUN",    char["gun"]),
        ("DAMAGE", char["damage"]),
        ("AMMO",   char["ammo"]),
        ("RELOAD", reload_str),
        ("RATE",   rate_str),
    ]

    panel_w  = 660
    panel_h  = 72
    panel_x  = CENTER_X - panel_w // 2
    panel_y  = top_y

    # 背景
    pygame.draw.rect(screen, COL_PANEL_BG,
                     (panel_x, panel_y, panel_w, panel_h), border_radius=10)
    pygame.draw.rect(screen, COL_PANEL_BD,
                     (panel_x, panel_y, panel_w, panel_h), 2, border_radius=10)

    col_w = panel_w // len(fields)   # 欄寬隨欄數自動計算
    for i, (label, value) in enumerate(fields):
        cx = panel_x + col_w * i + col_w // 2

        # 分隔線
        if i > 0:
            line_x = panel_x + col_w * i
            pygame.draw.line(screen, COL_PANEL_BD,
                             (line_x, panel_y + 8), (line_x, panel_y + panel_h - 8))

        # Label
        lbl = font_sm.render(label, True, COL_STAT_LABEL)
        screen.blit(lbl, (cx - lbl.get_width() // 2, panel_y + 10))

        # Value
        if value:
            val_surf = font_lg.render(value, True, COL_STAT_VAL)
        else:
            val_surf = font_sm.render("—", True, COL_STAT_EMPTY)
        screen.blit(val_surf, (cx - val_surf.get_width() // 2, panel_y + 32))

    # "Waiting for opponent" 文字（已確認後顯示）
    if _is_waiting():
        dots   = "." * (int(time.perf_counter() * 2) % 4)
        w_surf = font_lg.render(f"Waiting for opponent{dots}", True, COL_WAIT)
        screen.blit(w_surf,
                    (CENTER_X - w_surf.get_width() // 2,
                     panel_y + panel_h + 16))


# 模組內部用來判斷是否正在等待對手的旗標
_waiting: bool = False

def _is_waiting() -> bool:
    return _waiting

def set_waiting(v: bool) -> None:
    global _waiting
    _waiting = v
