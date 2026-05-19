"""
Character selection screen — horizontal carousel.
Scroll wheel / ← → to browse; centre card is the selected character.
Click arrows or press ← → to navigate.
Click CONFIRM button or press Enter to confirm / unconfirm.
When confirmed: navigation (arrows, scroll, keys) is locked.
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
        "speed":       round(get_stat(key, "speed") * 60),  # px/tick → px/s
        "gun":         get_stat(key, "gun"),
        "damage":      get_stat(key, "damage"),
        "ammo":        get_stat(key, "mag"),
        "reload_time":   get_stat(key, "reload_time"),
        "fire_interval": get_stat(key, "fire_interval"),
    }
    for key in CHAR_ORDER
]
N = len(CHARACTERS)

# ── 版面 ──────────────────────────────────────────────────────────────────
CARD_W       = 190
CARD_H       = 265
CARD_SPACING = 225
CENTER_X     = LOGICAL_W // 2
CARD_Y       = 300          # 卡片中心 y

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
COL_ARROW_DIS   = (60,  66,  85)   # disabled (confirmed)
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

# Confirm button
COL_BTN_ACTIVE  = (42, 130, 80)
COL_BTN_HOV     = (55, 165, 100)
COL_BTN_BD      = (80, 220, 130)
COL_BTN_DIM     = (45,  50,  68)
COL_BTN_DIM_BD  = (70,  78, 105)
COL_BTN_TXT     = (220, 235, 220)
COL_BTN_TXT_DIM = (90,  98, 120)

# ── Carousel 狀態（模組全域）────────────────────────────────────────────
_target_idx:  int   = 0
_anim_offset: float = 0.0
_confirmed:   bool  = False

# ── 點擊區域（每幀在 draw 裡更新）────────────────────────────────────────
_left_arr_rect:    pygame.Rect = pygame.Rect(0, 0, 0, 0)
_right_arr_rect:   pygame.Rect = pygame.Rect(0, 0, 0, 0)
_confirm_btn_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

# ── Sprite 快取 ───────────────────────────────────────────────────────────
_sprite_cache: dict = {}
_SPRITE_H = 148


def _load_sprite(char: dict) -> pygame.Surface:
    key = char["char_key"]
    if key not in _sprite_cache:
        path = os.path.join("assets", "Player", char["folder"],
                            f"{char['folder']}_stand.png")
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
    global _target_idx, _anim_offset, _confirmed
    _target_idx  = 0
    _anim_offset = 0.0
    _confirmed   = False


def is_confirmed() -> bool:
    return _confirmed


def handle_event(event: pygame.event.Event) -> bool:
    """
    回傳 True 表示玩家剛剛確認選擇（confirmed 變為 True）。
    確認狀態中：← → 與滾輪失效；再次點擊按鈕或 Enter 可取消確認。
    """
    global _target_idx, _confirmed

    if event.type == pygame.MOUSEWHEEL:
        if not _confirmed:
            _target_idx = max(0, min(N - 1, _target_idx - event.y))

    elif event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_LEFT, pygame.K_a):
            if not _confirmed:
                _target_idx = max(0, _target_idx - 1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            if not _confirmed:
                _target_idx = min(N - 1, _target_idx + 1)
        elif event.key == pygame.K_RETURN:
            _confirmed = not _confirmed
            return _confirmed   # True = 剛確認；False = 剛取消確認

    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mx, my = event.pos
        # 左右箭頭（僅未確認時有效）
        if not _confirmed:
            if _left_arr_rect.collidepoint(mx, my) and _target_idx > 0:
                _target_idx -= 1
            elif _right_arr_rect.collidepoint(mx, my) and _target_idx < N - 1:
                _target_idx += 1
        # 確認按鈕（永遠可點）
        if _confirm_btn_rect.collidepoint(mx, my):
            _confirmed = not _confirmed
            return _confirmed

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
    global _left_arr_rect, _right_arr_rect

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

        # 名稱
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

    def _make_rect(pts):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return pygame.Rect(min(xs) - 8, min(ys) - 8,
                           max(xs) - min(xs) + 16, max(ys) - min(ys) + 16)

    # 更新全域點擊矩形
    _left_arr_rect  = _make_rect(left_pts)
    _right_arr_rect = _make_rect(right_pts)

    def _arrow_col(pts, arr_rect, visible):
        if not visible:
            return None
        if _confirmed:
            return COL_ARROW_DIS
        return COL_ARROW_HOV if arr_rect.collidepoint(mx, my_pos) else COL_ARROW

    left_col  = _arrow_col(left_pts,  _left_arr_rect,  _target_idx > 0)
    right_col = _arrow_col(right_pts, _right_arr_rect, _target_idx < N - 1)

    if left_col:
        pygame.draw.polygon(screen, left_col,  left_pts)
    if right_col:
        pygame.draw.polygon(screen, right_col, right_pts)

    # ── 提示文字（未確認時）──────────────────────────────────────
    hint_y = CARD_Y + CARD_H // 2 + 22
    if not my_ready:
        hint_surf = font_sm.render(
            "← → / click arrows to browse   |   Enter or CONFIRM to lock in",
            True, COL_HINT)
        screen.blit(hint_surf, (CENTER_X - hint_surf.get_width() // 2, hint_y))

    # ── 數值面板 + 確認按鈕 ────────────────────────────────────────
    _draw_stats_panel(screen, font_lg, font_sm, hint_y + 34, my_ready)


def _draw_stats_panel(screen, font_lg, font_sm, top_y: int,
                      my_ready: bool = False) -> None:
    global _confirm_btn_rect

    char = CHARACTERS[_target_idx]

    reload = char["reload_time"]
    reload_str = f"{reload}s" if reload else ""

    interval = char["fire_interval"]
    if interval and interval > 0:
        interval_str = f"{int(interval) if interval == int(interval) else interval}s"
    else:
        interval_str = ""

    spd = char["speed"]
    spd_str = f"{spd} px/s"

    fields = [
        ("HP",       str(char["hp"])),
        ("SPEED",    spd_str),
        ("GUN",      char["gun"]),
        ("DAMAGE",   char["damage"]),
        ("AMMO",     char["ammo"]),
        ("RELOAD",   reload_str),
        ("INTERVAL", interval_str),
    ]

    panel_w = 1100
    panel_h = 72
    panel_x = CENTER_X - panel_w // 2
    panel_y = top_y

    # 背景
    pygame.draw.rect(screen, COL_PANEL_BG,
                     (panel_x, panel_y, panel_w, panel_h), border_radius=10)
    pygame.draw.rect(screen, COL_PANEL_BD,
                     (panel_x, panel_y, panel_w, panel_h), 2, border_radius=10)

    col_w = panel_w // len(fields)
    for i, (label, value) in enumerate(fields):
        cx = panel_x + col_w * i + col_w // 2

        if i > 0:
            line_x = panel_x + col_w * i
            pygame.draw.line(screen, COL_PANEL_BD,
                             (line_x, panel_y + 8), (line_x, panel_y + panel_h - 8))

        lbl = font_sm.render(label, True, COL_STAT_LABEL)
        screen.blit(lbl, (cx - lbl.get_width() // 2, panel_y + 10))

        if value:
            val_surf = font_lg.render(value, True, COL_STAT_VAL)
        else:
            val_surf = font_sm.render("—", True, COL_STAT_EMPTY)
        screen.blit(val_surf, (cx - val_surf.get_width() // 2, panel_y + 32))

    # ── 確認按鈕（panel 下方靠右）────────────────────────────────
    btn_w, btn_h = 164, 38
    btn_x = panel_x + panel_w - btn_w          # 與 panel 右緣對齊
    btn_y = panel_y + panel_h + 10

    _confirm_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

    mx, my_pos = pygame.mouse.get_pos()
    hovering   = _confirm_btn_rect.collidepoint(mx, my_pos)

    if _confirmed:
        bg_col  = COL_BTN_DIM
        bd_col  = COL_BTN_DIM_BD
        txt_col = COL_BTN_TXT_DIM
        label   = "CONFIRMED"
    else:
        bg_col  = COL_BTN_HOV if hovering else COL_BTN_ACTIVE
        bd_col  = COL_BTN_BD
        txt_col = COL_BTN_TXT
        label   = "CONFIRM"

    pygame.draw.rect(screen, bg_col, _confirm_btn_rect, border_radius=8)
    pygame.draw.rect(screen, bd_col, _confirm_btn_rect, 2, border_radius=8)

    btn_surf = font_lg.render(label, True, txt_col)
    screen.blit(btn_surf, (btn_x + btn_w // 2 - btn_surf.get_width() // 2,
                            btn_y + btn_h // 2 - btn_surf.get_height() // 2))

    # ── Waiting for opponent（已確認時，與按鈕同一行，靠左對齊 panel）
    if my_ready:
        dots   = "." * (int(time.perf_counter() * 2) % 4)
        w_surf = font_lg.render(f"Waiting for opponent{dots}", True, COL_WAIT)
        screen.blit(w_surf, (panel_x,
                             btn_y + btn_h // 2 - w_surf.get_height() // 2))
