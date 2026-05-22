import math
import pygame

from game.render_utils import ws, SCREEN_W, SCREEN_H
from game.chars.robot.e_state import RING_TICKS, E_MARK_TICKS, E_RING_R

_MARK_RADIUS = 12


def draw(screen, state, my_player_id: int, cx: float, cy: float) -> None:
    # ── Fading ring (visible to both players) ────────────────────────
    for ring in state.robot_e_rings.values():
        age = state.tick - ring.spawn_tick
        if age >= RING_TICKS:
            continue
        t          = age / RING_TICKS
        alpha_rim  = int(200 * (1.0 - t))
        alpha_fill = int(55  * (1.0 - t))

        sx, sy = ws(ring.x, ring.y, cx, cy)
        r = E_RING_R
        if (sx + r < 0 or sx - r > SCREEN_W or sy + r < 0 or sy - r > SCREEN_H):
            continue

        diam = r * 2 + 4
        surf = pygame.Surface((diam, diam), pygame.SRCALPHA)
        c    = (r + 2, r + 2)
        pygame.draw.circle(surf, (255, 220, 40, alpha_fill), c, r)
        pygame.draw.circle(surf, (255, 220, 40, alpha_rim),  c, r, 2)
        screen.blit(surf, (int(sx) - r - 2, int(sy) - r - 2))

    # ── Rotating mark (owner only) ────────────────────────────────────
    for owner_id, e_mark in state.robot_e_marks.items():
        if owner_id != my_player_id:
            continue
        age = state.tick - e_mark.spawn_tick
        if age >= E_MARK_TICKS:
            continue

        angle_rad = (math.radians(e_mark.start_angle)
                     + 2 * math.pi * (age / E_MARK_TICKS))
        wx = e_mark.center_x + E_RING_R * math.cos(angle_rad)
        wy = e_mark.center_y + E_RING_R * math.sin(angle_rad)
        sx, sy = ws(wx, wy, cx, cy)

        r = _MARK_RADIUS
        if (-r <= sx <= SCREEN_W + r and -r <= sy <= SCREEN_H + r):
            surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            c    = (r + 2, r + 2)
            pygame.draw.circle(surf, (255, 220, 40, 220),      c, r, 2)
            pygame.draw.circle(surf, (255, 220, 40, 220 // 3), c, r - 4)
            pygame.draw.line(surf, (255, 220, 40, 220), (c[0]-6, c[1]), (c[0]+6, c[1]), 1)
            pygame.draw.line(surf, (255, 220, 40, 220), (c[0], c[1]-6), (c[0], c[1]+6), 1)
            screen.blit(surf, (int(sx) - r - 2, int(sy) - r - 2))
