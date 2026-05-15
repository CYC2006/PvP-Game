import math
import time
import random

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws, COL_BULLET

_WAIT_TICKS     = 60
_BOMB_TICKS     = 120
_TOTAL_TICKS    = 180
_RADIUS         = 100
_PREVIEW_R      = 80
_MAX_RANGE      = 300
_DMG_INTERVAL   = 6

_particles:      list = []   # [wx, wy, vx, vy, spawn_t, max_life, color, size]
_last_expl_tick: dict = {}   # aid → last state.tick when explosion was spawned


def update(state) -> None:
    """bombing 期間每 2 tick 生成一次爆炸粒子（由 renderer 每幀呼叫）。"""
    active_ids = set(state.air_strikes)
    for aid in list(_last_expl_tick):
        if aid not in active_ids:
            _last_expl_tick.pop(aid)
    for aid, strike in state.air_strikes.items():
        age = state.tick - strike.spawn_tick
        if age < _WAIT_TICKS or age > _TOTAL_TICKS:
            continue
        if state.tick - _last_expl_tick.get(aid, -999) >= 2:
            _last_expl_tick[aid] = state.tick
            _spawn_explosion(strike.cx, strike.cy, strike.owner_id)


def _spawn_explosion(cx: float, cy: float, owner_id: int) -> None:
    now      = time.perf_counter()
    r        = random.uniform(0, _RADIUS)
    a        = random.uniform(0, math.tau)
    ex, ey   = cx + math.cos(a) * r, cy + math.sin(a) * r
    base_col = COL_BULLET.get(owner_id, (255, 200, 100))
    for _ in range(random.randint(5, 10)):
        pa    = random.uniform(0, math.tau)
        speed = random.uniform(20, 110)
        life  = random.uniform(0.15, 0.45)
        size  = random.uniform(2.0, 6.0)
        col   = tuple(max(0, min(255, c + random.randint(-40, 40))) for c in base_col)
        _particles.append([ex, ey,
                           math.cos(pa) * speed, math.sin(pa) * speed,
                           now, life, col, size])


def draw(screen, state, cx: float, cy: float) -> None:
    """繪製施放後的空襲圓 + 爆炸粒子（雙方皆可見）。"""
    now = time.perf_counter()

    for strike in state.air_strikes.values():
        age = state.tick - strike.spawn_tick
        if age < 0 or age > _TOTAL_TICKS:
            continue
        sx, sy = ws(strike.cx, strike.cy, cx, cy)
        color  = COL_BULLET.get(strike.owner_id, (255, 200, 100))
        r_px   = _RADIUS
        pad    = 4
        surf   = pygame.Surface((r_px * 2 + pad, r_px * 2 + pad), pygame.SRCALPHA)
        center = (r_px + pad // 2, r_px + pad // 2)
        if age >= _WAIT_TICKS:
            pygame.draw.circle(surf, (*color, 35), center, r_px)
        pygame.draw.circle(surf, (*color, 210), center, r_px, 3)
        screen.blit(surf, (sx - r_px - pad // 2, sy - r_px - pad // 2))

    alive = []
    for p in _particles:
        wx, wy, vx, vy, spawn_t, max_life, col, size = p
        elapsed = now - spawn_t
        if elapsed >= max_life:
            continue
        alive.append(p)
        alpha_f = 1.0 - elapsed / max_life
        spx, spy = ws(wx + vx * elapsed, wy + vy * elapsed, cx, cy)
        r_draw   = max(1, int(size * alpha_f))
        dc       = (int(col[0] * alpha_f), int(col[1] * alpha_f), int(col[2] * alpha_f))
        if -10 <= spx <= SCREEN_W + 10 and -10 <= spy <= SCREEN_H + 10:
            pygame.draw.circle(screen, dc, (spx, spy), r_draw)
    _particles[:] = alive


def draw_preview(screen, cx: float, cy: float, me_x: float, me_y: float, my_id: int) -> None:
    """R 按住時顯示 300px 灰色虛線範圍圈 + 80px 玩家色瞄準圈（僅本地可見）。"""
    import game.input as _inp
    if not _inp._r_holding:
        return

    aim_dx = _inp._last_aim_x
    aim_dy = _inp._last_aim_y
    dist   = math.hypot(aim_dx, aim_dy)
    if dist > _MAX_RANGE and dist > 0:
        scale   = _MAX_RANGE / dist
        aim_dx *= scale
        aim_dy *= scale

    target_wx = me_x + aim_dx
    target_wy = me_y + aim_dy
    color     = COL_BULLET.get(my_id, (255, 200, 100))

    me_sx, me_sy = ws(me_x, me_y, cx, cy)
    tx, ty       = ws(target_wx, target_wy, cx, cy)

    surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

    # 300px 虛線灰圓（每隔一點畫一個點）
    n = 72
    for i in range(0, n, 2):
        a  = math.tau * i / n
        px = int(me_sx + math.cos(a) * _MAX_RANGE)
        py = int(me_sy + math.sin(a) * _MAX_RANGE)
        if -4 <= px <= SCREEN_W + 4 and -4 <= py <= SCREEN_H + 4:
            pygame.draw.circle(surf, (190, 190, 190, 130), (px, py), 3)

    # 80px 玩家色瞄準圈（半透明填充 + 實邊框）
    r = _PREVIEW_R
    pygame.draw.circle(surf, (*color, 45), (tx, ty), r)
    pygame.draw.circle(surf, (*color, 210), (tx, ty), r, 3)

    screen.blit(surf, (0, 0))
