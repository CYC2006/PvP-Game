"""
Character selection screen.
All three slots currently use hitman1; ready for future expansion.
"""
import os
import math
import time
import pygame

LOGICAL_W = 1280
LOGICAL_H = 720

# 三個角色定義（目前都導向 hitman1）
CHARACTERS = [
    {"name": "SOLDIER", "char_key": "hitman1"},
    {"name": "SCOUT",   "char_key": "hitman1"},
    {"name": "HEAVY",   "char_key": "hitman1"},
]

# 版面
BOX_W      = 200
BOX_H      = 300
BOX_GAP    = 50
BOXES_TOP  = 180
SPRITE_H   = 160   # 角色 sprite 區塊高度

# 顏色
COL_BG          = (20,  24,  32)
COL_BOX_IDLE    = (40,  48,  60)
COL_BOX_HOVER   = (55,  68,  88)
COL_BOX_SELECTED= (30,  80,  50)
COL_BORDER_IDLE = (70,  85, 110)
COL_BORDER_SEL  = (80, 220, 120)
COL_BORDER_HOV  = (120, 155, 200)
COL_TEXT        = (220, 220, 220)
COL_TITLE       = (255, 230, 100)
COL_WAIT        = (140, 200, 255)
COL_READY       = (80,  220, 120)
COL_NAME        = (255, 255, 255)

# sprite 快取
_sprite_cache: dict = {}


def _box_rects() -> list:
    """回傳三個角色框的 pygame.Rect。"""
    total_w = BOX_W * 3 + BOX_GAP * 2
    start_x = (LOGICAL_W - total_w) // 2
    return [
        pygame.Rect(start_x + i * (BOX_W + BOX_GAP), BOXES_TOP, BOX_W, BOX_H)
        for i in range(3)
    ]


def _load_sprite(char_key: str) -> pygame.Surface:
    if char_key not in _sprite_cache:
        folder_map = {"hitman1": ("Hitman 1", "hitman1")}
        folder, prefix = folder_map.get(char_key, ("Hitman 1", "hitman1"))
        path = os.path.join("assets", "Player", folder, f"{prefix}_stand.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            # 等比例縮放到 SPRITE_H 高
            ratio = SPRITE_H / img.get_height()
            new_w = max(1, int(img.get_width() * ratio))
            _sprite_cache[char_key] = pygame.transform.scale(img, (new_w, SPRITE_H))
        except Exception:
            surf = pygame.Surface((80, SPRITE_H), pygame.SRCALPHA)
            pygame.draw.circle(surf, (160, 160, 160, 200),
                               (40, SPRITE_H // 2), 40)
            _sprite_cache[char_key] = surf
    return _sprite_cache[char_key]


def draw_char_select(screen: pygame.Surface,
                     font_lg: pygame.font.Font,
                     font_sm: pygame.font.Font,
                     selected_idx: int,   # -1 = 未選
                     my_ready: bool,
                     opponent_ready: bool) -> None:
    """繪製選角畫面（不處理事件，只負責渲染）。"""
    screen.fill(COL_BG)

    # ── 標題 ──────────────────────────────────────────────────────
    title = font_lg.render("SELECT YOUR CHARACTER", True, COL_TITLE)
    screen.blit(title, (LOGICAL_W // 2 - title.get_width() // 2, 60))

    # ── 三個角色框 ────────────────────────────────────────────────
    mx, my = pygame.mouse.get_pos()
    rects  = _box_rects()

    for i, (rect, char) in enumerate(zip(rects, CHARACTERS)):
        hovered  = rect.collidepoint(mx, my) and not my_ready
        selected = (i == selected_idx)

        # 背景
        bg_col  = COL_BOX_SELECTED if selected else (COL_BOX_HOVER if hovered else COL_BOX_IDLE)
        bd_col  = COL_BORDER_SEL   if selected else (COL_BORDER_HOV if hovered else COL_BORDER_IDLE)
        pygame.draw.rect(screen, bg_col,  rect, border_radius=12)
        pygame.draw.rect(screen, bd_col,  rect, 3, border_radius=12)

        # sprite（旋轉 90° 讓 hitman1 朝上）
        sprite  = _load_sprite(char["char_key"])
        rotated = pygame.transform.rotate(sprite, 90)
        sp_x = rect.centerx - rotated.get_width()  // 2
        sp_y = rect.y + 20
        screen.blit(rotated, (sp_x, sp_y))

        # 角色名稱
        name_surf = font_lg.render(char["name"], True, COL_NAME)
        screen.blit(name_surf,
                    (rect.centerx - name_surf.get_width() // 2,
                     rect.bottom - 60))

        # 底部提示
        if selected:
            hint = font_sm.render("✓ SELECTED", True, COL_BORDER_SEL)
        elif hovered:
            hint = font_sm.render("CLICK TO SELECT", True, COL_BORDER_HOV)
        else:
            hint = font_sm.render("", True, COL_TEXT)
        screen.blit(hint, (rect.centerx - hint.get_width() // 2,
                            rect.bottom - 30))

    # ── 狀態列 ────────────────────────────────────────────────────
    status_y = BOXES_TOP + BOX_H + 40

    # 我的狀態
    if my_ready:
        me_text = "YOU:       READY ✓"
        me_col  = COL_READY
    elif selected_idx >= 0:
        me_text = "YOU:       SELECTED — CLICK TO CONFIRM"
        me_col  = COL_WAIT
    else:
        me_text = "YOU:       selecting..."
        me_col  = COL_TEXT
    screen.blit(font_sm.render(me_text, True, me_col),
                (LOGICAL_W // 2 - 200, status_y))

    # 對手狀態
    op_text = "OPPONENT:  READY ✓" if opponent_ready else "OPPONENT:  waiting..."
    op_col  = COL_READY if opponent_ready else COL_TEXT
    screen.blit(font_sm.render(op_text, True, op_col),
                (LOGICAL_W // 2 - 200, status_y + 28))

    # 等待中的跳動點（視覺反饋）
    if my_ready and not opponent_ready:
        dots = "." * (int(time.perf_counter() * 2) % 4)
        wait_surf = font_lg.render(f"Waiting for opponent{dots}", True, COL_WAIT)
        screen.blit(wait_surf,
                    (LOGICAL_W // 2 - wait_surf.get_width() // 2, status_y + 70))


def handle_click(pos: tuple, selected_idx: int, my_ready: bool) -> int:
    """
    點擊事件處理。
    回傳新的 selected_idx（未變化則回傳原值）。
    my_ready 後不再允許更換。
    """
    if my_ready:
        return selected_idx
    rects = _box_rects()
    for i, rect in enumerate(rects):
        if rect.collidepoint(pos):
            return i
    return selected_idx
