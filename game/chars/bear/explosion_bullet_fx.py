import math
import time
import pygame
from game.render_utils import ws

EXPL_RADIUS = 120.0
_DURATION   = 0.45   # seconds

_tracked:    dict = {}
_explosions: list = []


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
        r      = max(1, int(EXPL_RADIUS * t))
        alpha  = int(240 * (1.0 - t))
        size   = int(EXPL_RADIUS) * 2 + 6
        surf   = pygame.Surface((size, size), pygame.SRCALPHA)
        sc     = (int(EXPL_RADIUS) + 3, int(EXPL_RADIUS) + 3)

        # 橙色主環
        pygame.draw.circle(surf, (255, 140, 20, alpha),       sc, r, 4)
        # 內環（亮黃）
        pygame.draw.circle(surf, (255, 220, 80, alpha // 2),  sc, max(1, r - 8), 2)
        # 爆炸核心閃光（前 30%）
        if t < 0.3:
            core_r = max(1, int(EXPL_RADIUS * 0.25 * (1 - t / 0.3)))
            pygame.draw.circle(surf, (255, 255, 200, int(alpha * 0.8)), sc, core_r)

        screen.blit(surf, (sx - int(EXPL_RADIUS) - 3,
                            sy - int(EXPL_RADIUS) - 3))

        # 輻射射線
        if t < 0.5:
            _draw_rays(screen, sx, sy, r, start_t)

    _explosions[:] = alive


def _draw_rays(screen, cx: int, cy: int, radius: int, seed_base: float) -> None:
    import random
    rng   = random.Random(int(seed_base * 30) & 0xFFFF)
    count = 6
    for _ in range(count):
        angle = rng.uniform(0, math.tau)
        length = radius * rng.uniform(0.6, 1.0)
        x1 = int(cx + math.cos(angle) * length)
        y1 = int(cy + math.sin(angle) * length)
        pygame.draw.line(screen, (255, 180, 50), (cx, cy), (x1, y1), 2)
