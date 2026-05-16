import time
import pygame
from game.render_utils import ws

_TRAIL_MAX  = 10     # 最多保留幾個殘影點
_TRAIL_GAP  = 0.010  # 兩個殘影點之間的最短時間間隔（秒）

_trails: dict = {}   # bid → [(world_x, world_y, timestamp), ...]


def track(bullet) -> None:
    """每幀呼叫，記錄 burst 子彈的位置歷史。"""
    bid = bullet.id
    now = time.perf_counter()
    trail = _trails.setdefault(bid, [])
    if not trail or now - trail[-1][2] >= _TRAIL_GAP:
        trail.append((bullet.x, bullet.y, now))
        if len(trail) > _TRAIL_MAX:
            trail.pop(0)


def draw_trail(screen, bullet, cx: float, cy: float, color: tuple) -> None:
    """在子彈主體之前呼叫，由舊到新繪製漸隱殘影圓。"""
    trail = _trails.get(bullet.id)
    if not trail:
        return
    r = max(1, int(5 * bullet.bullet_scale))   # BULLET_RADIUS=5
    n = len(trail)
    for i, (wx, wy, _t) in enumerate(trail):
        alpha = int(110 * (i + 1) / n)         # 越老越透明
        sx, sy = ws(wx, wy, cx, cy)
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*color, alpha), (r + 1, r + 1), r)
        screen.blit(surf, (sx - r - 1, sy - r - 1))


def cleanup(current_bids: set) -> None:
    """移除已消失子彈的殘影資料。"""
    for bid in list(_trails):
        if bid not in current_bids:
            del _trails[bid]
