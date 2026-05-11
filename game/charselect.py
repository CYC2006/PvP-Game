"""
Character selection screen — horizontal carousel.
Scroll wheel (or ←/→ arrows) to move; centre card is the selected character.
Click or press Enter/Space to confirm.
"""
import os
import math
import time
import pygame

LOGICAL_W = 1280
LOGICAL_H = 720

# ── 9 個角色（依資料夾名稱 / 前綴自動命名）────────────────────────────────
CHARACTERS = [
    {"char_key": "hitman1",    "folder": "Hitman 1",    "name": "Hitman 1"},
    {"char_key": "manBlue",    "folder": "Man Blue",    "name": "Man Blue"},
    {"char_key": "manBrown",   "folder": "Man Brown",   "name": "Man Brown"},
    {"char_key": "manOld",     "folder": "Man Old",     "name": "Man Old"},
    {"char_key": "robot1",     "folder": "Robot 1",     "name": "Robot 1"},
    {"char_key": "soldier1",   "folder": "Soldier 1",   "name": "Soldier 1"},
    {"char_key": "survivor1",  "folder": "Survivor 1",  "name": "Survivor 1"},
    {"char_key": "womanGreen", "folder": "Woman Green", "name": "Woman Green"},
    {"char_key": "zoimbie1",   "folder": "Zombie 1",    "name": "Zombie 1"},
]
N = len(CHARACTERS)

# ── 版面 ──────────────────────────────────────────────────────────────────
CARD_W       = 190
CARD_H       = 280
CARD_SPACING = 230        # 卡片中心間距
CENTER_X     = LOGICAL_W // 2
CARD_Y       = LOGICAL_H // 2 - 40

# ── 顏色 ──────────────────────────────────────────────────────────────────
COL_BG          = (20,  24,  32)
COL_CARD        = (38,  46,  62)
COL_CARD_CENTER = (30,  70,  50)
COL_BORDER      = (60,  75, 100)
COL_BORDER_CTR  = (80, 220, 130)
COL_TEXT        = (220, 220, 220)
COL_TITLE       = (255, 230, 100)
COL_NAME_CTR    = (255, 255, 255)
COL_NAME        = (160, 160, 170)
COL_HINT        = (140, 200, 255)
COL_READY       = ( 80, 220, 130)
COL_WAIT        = (140, 200, 255)
COL_ARROW       = (180, 190, 210)
COL_ARROW_HOV   = (255, 230, 100)

# ── Carousel 狀態（模組全域）────────────────────────────────────────────
_target_idx:  int   = 0
_anim_offset: float = 0.0

# ── Sprite 快取 ───────────────────────────────────────────────────────────
_sprite_cache: dict = {}
_SPRITE_H = 160


def _load_sprite(char: dict) -> pygame.Surface:
    key = char["char_key"]
    if key not in _sprite_cache:
        path = os.path.join("assets", "Player", char["folder"],
                            f"{char['char_key']}_stand.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            ratio = _SPRITE_H / img.get_height()
            new_w = max(1, int(img.get_width() * ratio))
            raw   = pygame.transform.scale(img, (new_w, _SPRITE_H))
            # hitman1 等角色預設朝右；旋轉 90° 讓他朝上
            _sprite_cache[key] = pygame.transform.rotate(raw, 90)
        except Exception:
            surf = pygame.Surface((80, _SPRITE_H), pygame.SRCALPHA)
            pygame.draw.circle(surf, (160, 160, 160, 200),
                               (40, _SPRITE_H // 2), 40)
            _sprite_cache[key] = surf
    return _sprite_cache[key]


# ── 公開 API ──────────────────────────────────────────────────────────────

def reset() -> None:
    """重設 carousel 狀態（每次進入選角畫面時呼叫）。"""
    global _target_idx, _anim_offset
    _target_idx  = 0
    _anim_offset = 0.0


def handle_event(event: pygame.event.Event) -> bool:
    """
    處理輸入事件。
    回傳 True 表示玩家按下確認（Enter / Space / 點擊畫面）。
    """
    global _target_idx
    if event.type == pygame.MOUSEWHEEL:
        _target_idx = max(0, min(N - 1, _target_idx + event.y * -1))
    elif event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_LEFT, pygame.K_a):
            _target_idx = max(0, _target_idx - 1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            _target_idx = min(N - 1, _target_idx + 1)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            return True
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        return True
    return False


def selected_char() -> dict:
    """回傳目前中央角色的資訊 dict。"""
    return CHARACTERS[_target_idx]


def selected_idx() -> int:
    return _target_idx


def update(dt: float) -> None:
    """每幀呼叫，平滑插值 carousel 位置。"""
    global _anim_offset
    _anim_offset += (_target_idx - _anim_offset) * min(1.0, 14.0 * dt)


def draw_char_select(screen: pygame.Surface,
                     font_lg: pygame.font.Font,
                     font_sm: pygame.font.Font,
                     my_ready: bool,
                     opponent_ready: bool) -> None:
    """繪製整個選角畫面（不含事件處理）。"""
    screen.fill(COL_BG)

    # ── 標題 ──────────────────────────────────────────────────────
    title = font_lg.render("SELECT YOUR CHARACTER", True, COL_TITLE)
    screen.blit(title, (CENTER_X - title.get_width() // 2, 40))

    # ── Carousel 卡片 ──────────────────────────────────────────────
    for i, char in enumerate(CHARACTERS):
        d   = i - _anim_offset          # 距中央的偏移（帶正負號）
        abs_d = abs(d)
        if abs_d > 3.2:
            continue                    # 太遠，不渲染

        # 位置 & 縮放
        scale   = max(0.45, 1.0 - abs_d * 0.22)
        cx      = int(CENTER_X + d * CARD_SPACING)
        w, h    = int(CARD_W * scale), int(CARD_H * scale)
        rect    = pygame.Rect(cx - w // 2, CARD_Y - h // 2, w, h)

        # Alpha（距離越遠越透明）
        alpha = max(60, int(255 - abs_d * 90))

        card_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        is_center = abs_d < 0.4
        bg_col    = COL_CARD_CENTER if is_center else COL_CARD
        bd_col    = COL_BORDER_CTR  if is_center else COL_BORDER
        bd_w      = 3 if is_center else 2

        pygame.draw.rect(card_surf, (*bg_col, alpha), (0, 0, w, h), border_radius=14)
        pygame.draw.rect(card_surf, (*bd_col, alpha), (0, 0, w, h), bd_w, border_radius=14)

        # Sprite
        raw_sprite = _load_sprite(char)
        sp_scale   = scale * 0.95
        sp_w = max(1, int(raw_sprite.get_width()  * sp_scale))
        sp_h = max(1, int(raw_sprite.get_height() * sp_scale))
        sprite = pygame.transform.scale(raw_sprite, (sp_w, sp_h))
        sprite.set_alpha(alpha)
        sp_x = w // 2 - sp_w // 2
        sp_y = int(h * 0.10)
        card_surf.blit(sprite, (sp_x, sp_y))

        # 角色名稱
        name_col  = COL_NAME_CTR if is_center else COL_NAME
        name_surf = font_sm.render(char["name"], True, (*name_col, alpha))
        card_surf.blit(name_surf, (w // 2 - name_surf.get_width() // 2,
                                   h - int(h * 0.18)))

        screen.blit(card_surf, rect.topleft)

    # ── 導航箭頭 ──────────────────────────────────────────────────
    mx, my = pygame.mouse.get_pos()
    arrow_y = CARD_Y

    left_pts = [(CENTER_X - CARD_SPACING * 1.7,       arrow_y),
                (CENTER_X - CARD_SPACING * 1.7 + 28,  arrow_y - 18),
                (CENTER_X - CARD_SPACING * 1.7 + 28,  arrow_y + 18)]
    right_pts= [(CENTER_X + CARD_SPACING * 1.7,       arrow_y),
                (CENTER_X + CARD_SPACING * 1.7 - 28,  arrow_y - 18),
                (CENTER_X + CARD_SPACING * 1.7 - 28,  arrow_y + 18)]

    def arrow_col(pts):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        r = pygame.Rect(min(xs)-4, min(ys)-4, max(xs)-min(xs)+8, max(ys)-min(ys)+8)
        return COL_ARROW_HOV if r.collidepoint(mx, my) else COL_ARROW

    if _target_idx > 0:
        pygame.draw.polygon(screen, arrow_col(left_pts),  left_pts)
    if _target_idx < N - 1:
        pygame.draw.polygon(screen, arrow_col(right_pts), right_pts)

    # ── 提示文字 ──────────────────────────────────────────────────
    hint_y = CARD_Y + CARD_H // 2 + 30
    if not my_ready:
        hint = font_sm.render("Scroll / ← → to browse   •   Click or Enter to confirm",
                              True, COL_HINT)
        screen.blit(hint, (CENTER_X - hint.get_width() // 2, hint_y))

    # ── 狀態列 ────────────────────────────────────────────────────
    status_y = hint_y + 36
    me_text  = "YOU:       READY ✓" if my_ready else f"YOU:       {CHARACTERS[_target_idx]['name']}"
    me_col   = COL_READY if my_ready else COL_TEXT
    screen.blit(font_sm.render(me_text, True, me_col),
                (CENTER_X - 180, status_y))

    op_text  = "OPPONENT:  READY ✓" if opponent_ready else "OPPONENT:  waiting..."
    op_col   = COL_READY if opponent_ready else COL_TEXT
    screen.blit(font_sm.render(op_text, True, op_col),
                (CENTER_X - 180, status_y + 26))

    if my_ready and not opponent_ready:
        dots = "." * (int(time.perf_counter() * 2) % 4)
        w_surf = font_lg.render(f"Waiting for opponent{dots}", True, COL_WAIT)
        screen.blit(w_surf, (CENTER_X - w_surf.get_width() // 2, status_y + 62))
