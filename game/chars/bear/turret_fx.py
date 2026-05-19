"""Bear E — 機槍台視覺效果

機槍台外觀：
  - 底座：深灰圓盤
  - 砲塔：橄欖色方形機體
  - 砲管：深色長方形，朝向敵人（或 aim_angle = 0 時朝右）
  - 血量條（機槍台下方）
  - 偵測圈（只有擁有者才看得到）
"""

import math
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H
from game.chars.bear.turret_state import TURRET_RANGE, TURRET_MAX_HP

# 顏色
_COL_BASE       = (70,  70,  70)     # 底座
_COL_BODY       = (80,  100, 60)     # 砲塔機體（橄欖色）
_COL_BODY_ENEMY = (100, 70,  60)     # 對手視角（不顯示擁有者顏色）
_COL_BARREL     = (40,  40,  40)     # 砲管
_COL_RANGE      = (255, 220, 60)     # 偵測圈（owner 才看到）
_COL_HP_BG      = (60,  20,  20)
_COL_HP_FILL    = (220, 100, 60)
_COL_BORDER     = (180, 180, 180)

_BASE_R  = 16    # 底座半徑 px（邏輯）
_BODY_W  = 22    # 砲塔方形邊長
_BARREL_LEN = 20
_BARREL_W   = 6
_HP_BAR_W   = 30
_HP_BAR_H   = 5
_HP_BAR_OY  = 24   # HP 條在機槍台中心下方偏移量


def draw(screen: pygame.Surface, state, my_id: int, cx: float, cy: float) -> None:
    """每幀繪製所有機槍台。"""
    if not state.turrets:
        return

    for turret in state.turrets.values():
        sx = ws(turret.x - cx + SCREEN_W / 2)
        sy = ws(turret.y - cy + SCREEN_H / 2)

        # ── 偵測圈（owner 才看得到）─────────────────────────────────────
        if turret.owner_id == my_id:
            r_scr = ws(TURRET_RANGE)
            surf = pygame.Surface((r_scr * 2 + 2, r_scr * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*_COL_RANGE, 30), (r_scr + 1, r_scr + 1), r_scr)
            pygame.draw.circle(surf, (*_COL_RANGE, 80), (r_scr + 1, r_scr + 1), r_scr, max(1, ws(1.5)))
            screen.blit(surf, (sx - r_scr - 1, sy - r_scr - 1))

        # ── 底座 ─────────────────────────────────────────────────────────
        base_r = max(2, ws(_BASE_R))
        pygame.draw.circle(screen, _COL_BASE, (int(sx), int(sy)), base_r)
        pygame.draw.circle(screen, _COL_BORDER, (int(sx), int(sy)), base_r, 1)

        # ── 砲塔機體（旋轉方形）─────────────────────────────────────────
        body_col = _COL_BODY if turret.owner_id == my_id else _COL_BODY_ENEMY
        bw = max(4, ws(_BODY_W))
        body_rect = pygame.Rect(int(sx) - bw // 2, int(sy) - bw // 2, bw, bw)
        pygame.draw.rect(screen, body_col, body_rect)
        pygame.draw.rect(screen, _COL_BORDER, body_rect, 1)

        # ── 砲管（朝向對手：由 server tick 狀態推算最新角度）────────────
        # 用 hp 隨機 seed 估算方向不可行；改用「朝最近敵人」即時計算
        enemy_id = 3 - turret.owner_id
        enemy = state.players.get(enemy_id)
        if enemy:
            dx = enemy.x - turret.x
            dy = enemy.y - turret.y
            angle_rad = math.atan2(dy, dx)
        else:
            angle_rad = 0.0

        blen = max(4, ws(_BARREL_LEN))
        bw2  = max(2, ws(_BARREL_W))
        # 砲管從中心沿方向延伸
        ux = math.cos(angle_rad)
        uy = math.sin(angle_rad)
        rx, ry = -uy, ux   # 右方向（垂直）
        p1x = int(sx + rx * bw2 / 2)
        p1y = int(sy + ry * bw2 / 2)
        p2x = int(sx - rx * bw2 / 2)
        p2y = int(sy - ry * bw2 / 2)
        p3x = int(sx + ux * blen - rx * bw2 / 2)
        p3y = int(sy + uy * blen - ry * bw2 / 2)
        p4x = int(sx + ux * blen + rx * bw2 / 2)
        p4y = int(sy + uy * blen + ry * bw2 / 2)
        pygame.draw.polygon(screen, _COL_BARREL, [(p1x, p1y), (p2x, p2y),
                                                   (p3x, p3y), (p4x, p4y)])

        # ── 血量條 ──────────────────────────────────────────────────────
        hp_frac = max(0.0, turret.hp / TURRET_MAX_HP)
        bar_w   = max(4, ws(_HP_BAR_W))
        bar_h   = max(2, ws(_HP_BAR_H))
        bar_x   = int(sx) - bar_w // 2
        bar_y   = int(sy) + max(4, ws(_HP_BAR_OY))
        pygame.draw.rect(screen, _COL_HP_BG,   (bar_x,     bar_y, bar_w,              bar_h))
        pygame.draw.rect(screen, _COL_HP_FILL,  (bar_x,     bar_y, int(bar_w * hp_frac), bar_h))
        pygame.draw.rect(screen, _COL_BORDER,   (bar_x,     bar_y, bar_w,              bar_h), 1)
