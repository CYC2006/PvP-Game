import math
import time
import random

import pygame

from game.render_utils import ws

STUN_RADIUS = 60.0
_DURATION   = 0.5   # seconds

_tracked:    dict = {}   # bid → (x, y)
_explosions: list = []   # [(x, y, start_t), ...]


def track(bullet) -> None:
    _tracked[bullet.id] = (bullet.x, bullet.y)


def detect_disappeared(state, now: float) -> None:
    current = set(state.bullets)
    for bid in list(_tracked):
        if bid not in current:
            x, y = _tracked.pop(bid)
            _explosions.append((x, y, now))


def draw_explosions(screen, cx: float, cy: float) -> None:
    now   = time.perf_counter()
    alive = []
    for entry in _explosions:
        x, y, start_t = entry
        t = (now - start_t) / _DURATION
        if t >= 1.0:
            continue
        alive.append(entry)
        sx, sy = ws(x, y, cx, cy)
        r      = max(1, int(STUN_RADIUS * t))
        alpha  = int(220 * (1.0 - t))

        # 擴散黃色圓環
        surf   = pygame.Surface((int(STUN_RADIUS) * 2 + 6,
                                  int(STUN_RADIUS) * 2 + 6), pygame.SRCALPHA)
        sc     = (int(STUN_RADIUS) + 3, int(STUN_RADIUS) + 3)
        pygame.draw.circle(surf, (255, 230,  40, alpha),       sc, r, 3)
        pygame.draw.circle(surf, (255, 255, 120, alpha // 2),  sc, max(1, r - 5), 2)
        screen.blit(surf, (sx - int(STUN_RADIUS) - 3,
                            sy - int(STUN_RADIUS) - 3))

        # 閃電射線（前半段持續出現）
        if t < 0.55:
            _draw_lightning(screen, sx, sy, r, start_t)

    _explosions[:] = alive


def _draw_lightning(screen, cx: int, cy: int, radius: int, seed_base: float) -> None:
    rng   = random.Random(int(seed_base * 30) & 0xFFFF)
    count = 5
    for _ in range(count):
        angle  = rng.uniform(0, math.tau)
        steps  = 5
        x0, y0 = cx, cy
        for i in range(1, steps + 1):
            t  = i / steps
            x1 = cx + math.cos(angle) * radius * t + rng.uniform(-10, 10)
            y1 = cy + math.sin(angle) * radius * t + rng.uniform(-10, 10)
            bright = (255, 255, int(80 + 175 * (1 - t)))
            pygame.draw.line(screen, bright,
                             (int(x0), int(y0)), (int(x1), int(y1)), 2)
            x0, y0 = x1, y1
