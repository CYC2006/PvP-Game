import math
import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H
from game.state import BULLET_RADIUS

SHURIKEN_GROW_RATE = 0.3   # 與 shuriken_state 保持一致

_first_tick: dict = {}   # bid → 第一次出現時的 state.tick


def cleanup(current_bids: set) -> None:
    for bid in list(_first_tick.keys()):
        if bid not in current_bids:
            _first_tick.pop(bid, None)


def draw_bullet(screen, bullet, sx: int, sy: int, color, state) -> None:
    """繪製 RMB 手裡劍（等速旋轉，隨時間成長）。"""
    if bullet.id not in _first_tick:
        _first_tick[bullet.id] = state.tick
    age  = state.tick - _first_tick[bullet.id]
    grow = age * SHURIKEN_GROW_RATE
    r_outer = max(BULLET_RADIUS, BULLET_RADIUS + grow)
    r_inner = r_outer * 0.45
    spin = time.perf_counter() * 6.0
    pts = []
    for i in range(8):
        r = r_outer if i % 2 == 0 else r_inner
        ang = spin + i * math.pi / 4
        pts.append((sx + r * math.cos(ang), sy + r * math.sin(ang)))
    glow_r = int(r_outer + 3)
    glow_surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (*color, 60), (glow_r + 1, glow_r + 1), glow_r)
    screen.blit(glow_surf, (sx - glow_r - 1, sy - glow_r - 1))
    if len(pts) >= 3:
        pygame.draw.polygon(screen, color, pts)
