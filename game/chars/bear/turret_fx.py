"""Bear E — 機槍台視覺效果

機槍台外觀：
  - 底座：深灰圓盤
  - 砲塔：橄欖色方形機體
  - 砲管：深色長方形，朝向敵人（無敵人時朝右）
  - 血量條（機槍台下方）
  - 偵測圈（只有擁有者才看得到）
"""

import math
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H
from game.chars.bear.turret_state import TURRET_RANGE, TURRET_MAX_HP

# 顏色
_COL_BASE       = (70,  70,  70)     # 底座
_COL_BODY       = (80,  100, 60)     # 砲塔機體（橄欖色，己方）
_COL_BODY_ENEMY = (100, 70,  60)     # 對手視角
_COL_BARREL     = (40,  40,  40)     # 砲管
_COL_RANGE      = (255, 220, 60)     # 偵測圈（owner 才看到）
_COL_HP_BG      = (60,  20,  20)
_COL_HP_FILL    = (220, 100, 60)
_COL_BORDER     = (180, 180, 180)

_BASE_R     = 16     # 底座半徑 px（邏輯）
_BODY_W     = 22     # 砲塔方形邊長
_BARREL_LEN = 20
_BARREL_W   = 6
_HP_BAR_W   = 30
_HP_BAR_H   = 5
_HP_BAR_OY  = 24    # HP 條在機槍台中心下方偏移量


def draw(screen: pygame.Surface, state, my_id: int, cx: float, cy: float) -> None:
    """每幀繪製所有機槍台。cx/cy 為 ws() 所需的世界→螢幕偏移量。"""
    if not state.turrets:
        return

    for turret in state.turrets.values():
        sx, sy = ws(turret.x, turret.y, cx, cy)

        # ── 偵測圈（owner 才看得到）─────────────────────────────────────
        if turret.owner_id == my_id:
            r = int(TURRET_RANGE)
            surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*_COL_RANGE, 25),  (r + 1, r + 1), r)
            pygame.draw.circle(surf, (*_COL_RANGE, 90),  (r + 1, r + 1), r, 2)
            screen.blit(surf, (sx - r - 1, sy - r - 1))

        # ── 底座 ─────────────────────────────────────────────────────────
        pygame.draw.circle(screen, _COL_BASE,   (sx, sy), _BASE_R)
        pygame.draw.circle(screen, _COL_BORDER, (sx, sy), _BASE_R, 1)

        # ── 砲塔機體（方形）─────────────────────────────────────────────
        body_col = _COL_BODY if turret.owner_id == my_id else _COL_BODY_ENEMY
        bw = _BODY_W
        body_rect = pygame.Rect(sx - bw // 2, sy - bw // 2, bw, bw)
        pygame.draw.rect(screen, body_col,   body_rect)
        pygame.draw.rect(screen, _COL_BORDER, body_rect, 1)

        # ── 砲管（朝向最近敵人）─────────────────────────────────────────
        enemy_id = 3 - turret.owner_id
        enemy = state.players.get(enemy_id)
        if enemy:
            angle_rad = math.atan2(enemy.y - turret.y, enemy.x - turret.x)
        else:
            angle_rad = 0.0

        ux = math.cos(angle_rad)
        uy = math.sin(angle_rad)
        rx, ry = -uy, ux   # 右方向（垂直於砲管）
        hw = _BARREL_W / 2
        p1 = (int(sx + rx * hw), int(sy + ry * hw))
        p2 = (int(sx - rx * hw), int(sy - ry * hw))
        p3 = (int(sx + ux * _BARREL_LEN - rx * hw), int(sy + uy * _BARREL_LEN - ry * hw))
        p4 = (int(sx + ux * _BARREL_LEN + rx * hw), int(sy + uy * _BARREL_LEN + ry * hw))
        pygame.draw.polygon(screen, _COL_BARREL, [p1, p2, p3, p4])

        # ── 血量條 ──────────────────────────────────────────────────────
        hp_frac = max(0.0, turret.hp / TURRET_MAX_HP)
        bar_w   = _HP_BAR_W
        bar_h   = _HP_BAR_H
        bar_x   = sx - bar_w // 2
        bar_y   = sy + _HP_BAR_OY
        pygame.draw.rect(screen, _COL_HP_BG,   (bar_x, bar_y, bar_w,                bar_h))
        pygame.draw.rect(screen, _COL_HP_FILL,  (bar_x, bar_y, int(bar_w * hp_frac), bar_h))
        pygame.draw.rect(screen, _COL_BORDER,   (bar_x, bar_y, bar_w,                bar_h), 1)
