import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws, COL_BULLET

_positions:  dict = {}   # bid → (wx, wy, owner_id)
_explosions: list = []   # [(wx, wy, spawn_t, owner_id)]


def detect_disappeared(state, now: float) -> None:
    current = {bid for bid, b in state.bullets.items()
               if getattr(b, 'bullet_type', 0) == 5}
    for bid in set(_positions) - current:
        if bid in _positions:
            bx, by, bowner = _positions[bid]
            _explosions.append((bx, by, now, bowner))
        _positions.pop(bid, None)


def track(bullet) -> None:
    _positions[bullet.id] = (bullet.x, bullet.y, bullet.owner_id)


def draw_explosions(screen, cx: float, cy: float) -> None:
    now = time.perf_counter()
    alive = []
    DURATION, MAX_R = 0.4, 65
    for wx, wy, t, owner in _explosions:
        elapsed = now - t
        if elapsed >= DURATION:
            continue
        alive.append((wx, wy, t, owner))
        progress = elapsed / DURATION
        r     = max(1, int(MAX_R * progress))
        alpha = int(200 * (1.0 - progress))
        col   = COL_BULLET.get(owner, (255, 200, 100))
        sx, sy = ws(wx, wy, cx, cy)
        if -MAX_R <= sx <= SCREEN_W + MAX_R and -MAX_R <= sy <= SCREEN_H + MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _explosions[:] = alive
