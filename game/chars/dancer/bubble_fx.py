import pygame

from game.state import BULLET_RADIUS

_BUBBLE_INIT_R = BULLET_RADIUS * 2
_BUBBLE_LIFE   = 2.0   # 秒

_spawn_time: dict = {}   # bid → spawn time (perf_counter)
_max_radius: dict = {}   # bid → max radius px


def cleanup(current_bids: set) -> None:
    for bid in list(_spawn_time.keys()):
        if bid not in current_bids:
            _spawn_time.pop(bid, None)
            _max_radius.pop(bid, None)


def draw_bullet(screen, bullet, sx: int, sy: int, color, now: float) -> None:
    """繪製毒氣泡：隨時間膨脹的半透明圓。"""
    if bullet.id not in _spawn_time:
        _spawn_time[bullet.id] = now
        rmax = getattr(bullet, "bubble_radius_max", 0.0)
        _max_radius[bullet.id] = rmax if rmax > 0 else BULLET_RADIUS * 6
    age = now - _spawn_time[bullet.id]
    t   = min(1.0, age / _BUBBLE_LIFE)
    r   = max(1, int(_BUBBLE_INIT_R + (_max_radius[bullet.id] - _BUBBLE_INIT_R) * t))
    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (*color, 120), (r, r), r)
    screen.blit(surf, (sx - r, sy - r))
