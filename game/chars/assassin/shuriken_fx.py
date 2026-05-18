import math
import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws
from game.state import BULLET_RADIUS

SHURIKEN_GROW_RATE = 0.3   # 與 shuriken_state 保持一致

_first_tick: dict = {}   # bid → 第一次出現時的 state.tick

# ── 殘影追蹤 ─────────────────────────────────────────────────────────────────
_TRAIL_MAX = 8      # 最多保留幾個殘影點
_TRAIL_GAP = 0.014  # 兩殘影點之間最短時間間隔（秒）
_trails: dict = {}  # bid → [(world_x, world_y, spin_angle, r_outer, timestamp), ...]


def cleanup(current_bids: set) -> None:
    for bid in list(_first_tick.keys()):
        if bid not in current_bids:
            _first_tick.pop(bid, None)
    for bid in list(_trails.keys()):
        if bid not in current_bids:
            del _trails[bid]


def draw_bullet(screen, bullet, sx: int, sy: int, color, state,
                cx: float = 0.0, cy: float = 0.0) -> None:
    """繪製 RMB 手裡劍（等速旋轉，隨時間成長）及尾部殘影。
    cx / cy 為本幀相機偏移，供殘影換算螢幕座標使用。
    """
    if bullet.id not in _first_tick:
        _first_tick[bullet.id] = state.tick
    age  = state.tick - _first_tick[bullet.id]
    grow = age * SHURIKEN_GROW_RATE
    r_outer = max(BULLET_RADIUS, BULLET_RADIUS + grow)
    r_inner = r_outer * 0.45
    spin = time.perf_counter() * 6.0

    # ── 記錄殘影點（世界座標 + 當前旋轉角 + 半徑）────────────────────────────
    now   = time.perf_counter()
    trail = _trails.setdefault(bullet.id, [])
    if not trail or now - trail[-1][4] >= _TRAIL_GAP:
        trail.append((bullet.x, bullet.y, spin, r_outer, now))
        if len(trail) > _TRAIL_MAX:
            trail.pop(0)

    # ── 繪製殘影（由老到新，越新越不透明、越大）──────────────────────────────
    n = len(trail)
    for idx, (wx, wy, t_spin, t_r, _ts) in enumerate(trail):
        frac   = (idx + 1) / n          # 0 = 最老, 1 = 最新
        alpha  = int(90 * frac)         # 10 → 90
        t_rout = max(3.0, t_r * (0.35 + 0.55 * frac))   # 較小的殘影星
        t_rin  = t_rout * 0.45
        ghost_color = (*color, alpha)
        tx, ty = ws(wx, wy, cx, cy)
        # 每個殘影旋轉角與記錄時一致（不再繼續旋轉，呈現「拖尾」感）
        ghost_pts = []
        for i in range(8):
            r = t_rout if i % 2 == 0 else t_rin
            ang = t_spin + i * math.pi / 4
            ghost_pts.append((tx + r * math.cos(ang),
                               ty + r * math.sin(ang)))
        surf_r = int(t_rout) + 2
        surf = pygame.Surface((surf_r * 2 + 2, surf_r * 2 + 2), pygame.SRCALPHA)
        shifted = [(p[0] - tx + surf_r + 1, p[1] - ty + surf_r + 1)
                   for p in ghost_pts]
        if len(shifted) >= 3:
            pygame.draw.polygon(surf, ghost_color, shifted)
        screen.blit(surf, (int(tx) - surf_r - 1, int(ty) - surf_r - 1))

    # ── 本體光暈 ──────────────────────────────────────────────────────────────
    glow_r = int(r_outer + 3)
    glow_surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (*color, 60), (glow_r + 1, glow_r + 1), glow_r)
    screen.blit(glow_surf, (sx - glow_r - 1, sy - glow_r - 1))

    # ── 本體手裡劍 ────────────────────────────────────────────────────────────
    pts = []
    for i in range(8):
        r = r_outer if i % 2 == 0 else r_inner
        ang = spin + i * math.pi / 4
        pts.append((sx + r * math.cos(ang), sy + r * math.sin(ang)))
    if len(pts) >= 3:
        pygame.draw.polygon(screen, color, pts)
