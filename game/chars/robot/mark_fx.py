import math
import time
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H
from game.chars.robot.mark_state import MARK_TICKS

_MARK_RADIUS  = 12   # 印記圓半徑 px
_BAR_W        = 44   # 倒計時 bar 寬度（與 HP bar 相同）
_BAR_H        = 5
_BAR_Y_OFFSET = 52   # 從玩家中心往上的偏移量 px（大約在頭頂上方）


def draw(screen, state, my_player_id: int, cx: float, cy: float) -> None:
    """繪製 robot 的機器印記（地面指示）與頭頂倒計時 bar。
    兩者都只對 owner 本人顯示（owner_id == my_player_id）。
    """
    for owner_id, mark in state.robot_marks.items():
        age = state.tick - mark.spawn_tick
        remaining = MARK_TICKS - age
        if remaining <= 0 or owner_id != my_player_id:
            continue

        # ── 地面印記 ─────────────────────────────────────────────
        sx, sy = ws(mark.x, mark.y, cx, cy)
        r = _MARK_RADIUS
        if (-r <= sx <= SCREEN_W + r and -r <= sy <= SCREEN_H + r):
            pulse = 0.65 + 0.35 * math.sin(time.perf_counter() * 7.0)
            alpha = int(220 * pulse)

            surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            c = (r + 2, r + 2)
            pygame.draw.circle(surf, (255, 220, 40, alpha),       c, r, 2)    # 外圓
            pygame.draw.circle(surf, (255, 220, 40, alpha // 3),  c, r - 4)   # 填充
            # 十字刻線
            pygame.draw.line(surf, (255, 220, 40, alpha), (c[0]-6, c[1]), (c[0]+6, c[1]), 1)
            pygame.draw.line(surf, (255, 220, 40, alpha), (c[0], c[1]-6), (c[0], c[1]+6), 1)
            screen.blit(surf, (sx - r - 2, sy - r - 2))

        # ── 玩家頭頂倒計時 bar ────────────────────────────────────
        player = state.players.get(owner_id)
        if player:
            px, py = ws(player.x, player.y, cx, cy)
            ratio  = remaining / MARK_TICKS
            bx     = px - _BAR_W // 2
            by     = py - _BAR_Y_OFFSET
            fill_w = max(0, int(_BAR_W * ratio))

            pygame.draw.rect(screen, (50, 40,  0),        (bx, by, _BAR_W,  _BAR_H), border_radius=2)
            if fill_w > 0:
                pygame.draw.rect(screen, (255, 220, 40),  (bx, by, fill_w,  _BAR_H), border_radius=2)
            pygame.draw.rect(screen, (180, 160, 30),      (bx, by, _BAR_W,  _BAR_H), 1, border_radius=2)
