import math
import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws, COL_BULLET


def _build_crescent_pts():
    n = 14
    outer_r, inner_r, offset = 13, 10, 8
    pts = []
    for i in range(n + 1):
        a = math.pi / 2 - math.pi * i / n
        pts.append((outer_r * math.cos(a), outer_r * math.sin(a)))
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((offset + inner_r * math.cos(a), inner_r * math.sin(a)))
    return pts


_crescent_pts = _build_crescent_pts()


def draw(screen, state, cx: float, cy: float) -> None:
    """繪製 Zombie 主攻的月牙形刀弧。"""
    now = time.perf_counter()
    for blade in state.blade_arcs.values():
        owner = state.players.get(blade.owner_id)
        sx, sy = ws(blade.x, blade.y, cx, cy)
        if sx < -40 or sx > SCREEN_W + 40 or sy < -40 or sy > SCREEN_H + 40:
            continue
        color = COL_BULLET.get(blade.owner_id, (255, 255, 200))

        orbit_angle = (math.atan2(blade.y - owner.y, blade.x - owner.x)
                       if owner else 0.0)
        travel_dir  = orbit_angle + blade.direction * math.pi / 2
        spin_offset = (blade.id * 1.0472) % (math.pi * 2)
        spin = travel_dir + now * 4.0 + spin_offset

        age   = blade.age
        alpha = min(1.0, min(age / 5.0, (30 - age) / 5.0))
        if alpha <= 0:
            continue

        cos_s, sin_s = math.cos(spin), math.sin(spin)
        pts = [(sx + x * cos_s - y * sin_s, sy + x * sin_s + y * cos_s)
               for x, y in _crescent_pts]

        r, g, b = color
        pygame.draw.polygon(screen, (int(r * alpha), int(g * alpha), int(b * alpha)), pts)
