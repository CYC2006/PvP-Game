import math
import time
import random
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H

POOL_TICKS = 300

# pool_id → {'last_bubble_t': float, 'bubbles': list}
_pool_state: dict = {}


def update(state) -> None:
    now = time.perf_counter()
    current_ids = set(state.poison_pools)

    for pid in list(_pool_state):
        if pid not in current_ids:
            del _pool_state[pid]

    for ppid, pool in state.poison_pools.items():
        ps = _pool_state.setdefault(ppid, {'last_bubble_t': 0.0, 'bubbles': []})
        r  = pool.radius

        interval = 0.08 if pool.pool_source == 'rmb' else 0.15
        if now - ps['last_bubble_t'] >= interval:
            ps['last_bubble_t'] = now
            angle  = random.uniform(0, math.tau)
            dist_r = random.uniform(0, r * 0.9)
            lx     = math.cos(angle) * dist_r
            ly     = math.sin(angle) * dist_r
            br     = random.uniform(3, 10) if pool.pool_source == 'space' else random.uniform(6, 22)
            life   = random.uniform(0.5, 1.2) if pool.pool_source == 'space' else random.uniform(0.8, 2.0)
            spd    = random.uniform(15, 35) if pool.pool_source == 'space' else random.uniform(20, 55)
            ps['bubbles'].append([lx, ly, br, now, life, spd])

        ps['bubbles'] = [b for b in ps['bubbles'] if now - b[3] < b[4]]


def draw(screen, state, cx: float, cy: float) -> None:
    now = time.perf_counter()
    for ppid, pool in state.poison_pools.items():
        age  = state.tick - pool.spawn_tick
        fade = max(0.0, min(1.0, (POOL_TICKS - age) / 60))
        r    = int(pool.radius)
        sx, sy = ws(pool.x, pool.y, cx, cy)

        if -r > sx or sx > SCREEN_W + r or -r > sy or sy > SCREEN_H + r:
            continue

        if pool.pool_source == 'space':
            _draw_small_pool(screen, sx, sy, r, fade)
        else:
            _draw_large_pool(screen, sx, sy, r, fade)

        ps = _pool_state.get(ppid)
        if ps:
            for lx, ly, br, birth_t, lifetime, spd in ps['bubbles']:
                elapsed = now - birth_t
                t       = elapsed / lifetime
                bx = sx + int(lx)
                by = sy + int(ly - spd * elapsed)
                alpha   = int(160 * fade * (1.0 - t))
                br_int  = max(1, int(br * (1.0 - t * 0.3)))
                if abs(bx - sx) <= r + br_int and abs(by - sy) <= r + br_int:
                    bsurf = pygame.Surface((br_int * 2 + 2, br_int * 2 + 2), pygame.SRCALPHA)
                    pygame.draw.circle(bsurf, (100, 230, 100, alpha),
                                       (br_int + 1, br_int + 1), br_int, 2)
                    screen.blit(bsurf, (bx - br_int - 1, by - br_int - 1))


def _draw_large_pool(screen, sx: int, sy: int, r: int, fade: float) -> None:
    surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    sc   = (r + 2, r + 2)
    pygame.draw.circle(surf, (60, 200, 60, int(50 * fade)),  sc, r)
    pygame.draw.circle(surf, (30, 160, 30, int(200 * fade)), sc, r, 3)
    screen.blit(surf, (sx - r - 2, sy - r - 2))


def _draw_small_pool(screen, sx: int, sy: int, r: int, fade: float) -> None:
    surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    sc   = (r + 2, r + 2)
    pygame.draw.circle(surf, (80, 230, 80, int(80 * fade)),  sc, r)
    pygame.draw.circle(surf, (40, 190, 40, int(220 * fade)), sc, r, 2)
    screen.blit(surf, (sx - r - 2, sy - r - 2))
