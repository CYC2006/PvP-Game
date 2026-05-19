"""Bear R — 滾動空襲視覺效果

每枚空襲分兩階段：
  1. X 標誌（BARRAGE_FUSE tick）：地板上出現 × 記號，雙方皆可見
  2. 爆炸擴散圓（time-based）：半徑從 0 擴散至 EXPL_MAX_R
"""

import time
import pygame
from game.render_utils import ws, SCREEN_W, COL_BULLET
from game.chars.bear.barrage_state import BARRAGE_FUSE

EXPL_MAX_R    = 110
EXPL_DURATION = 0.5   # 秒
_X_SIZE       = 14    # X 標誌的半臂長（px）
_X_WIDTH      = 3     # X 線寬（px）

_known:      dict = {}   # sid → (wx, wy, owner_id, explode_t_or_None)
_explosions: list = []   # [(wx, wy, owner_id, start_t)]


def update(state) -> None:
    """每幀呼叫：追蹤 strike、偵測爆炸時機。"""
    current_ids = set(state.barrage_strikes)
    now = time.perf_counter()

    for sid, strike in state.barrage_strikes.items():
        age  = state.tick - strike.spawn_tick
        prev = _known.get(sid)
        if prev is None:
            explode_t = now if age >= BARRAGE_FUSE else None
            _known[sid] = (strike.x, strike.y, strike.owner_id, explode_t)
            if explode_t is not None:
                _explosions.append((strike.x, strike.y, strike.owner_id, explode_t))
        else:
            wx, wy, oid, explode_t = prev
            if explode_t is None and age >= BARRAGE_FUSE:
                explode_t = now
                _known[sid] = (wx, wy, oid, explode_t)
                _explosions.append((wx, wy, oid, explode_t))

    for sid in list(_known):
        if sid not in current_ids:
            _known.pop(sid)


def draw(screen, state, cx: float, cy: float) -> None:
    """繪製 X 標誌（age < BARRAGE_FUSE 期間）。"""
    for sid, strike in state.barrage_strikes.items():
        age = state.tick - strike.spawn_tick
        if age < 0 or age >= BARRAGE_FUSE:
            continue

        sx, sy = ws(strike.x, strike.y, cx, cy)
        if sx < -_X_SIZE * 2 or sx > SCREEN_W + _X_SIZE * 2:
            continue

        # 後半段閃爍提示即將爆炸
        if age >= BARRAGE_FUSE * 0.6 and (age // 3) % 2 == 0:
            continue

        color = COL_BULLET.get(strike.owner_id, (255, 200, 100))
        d = _X_SIZE
        pygame.draw.line(screen, color, (sx - d, sy - d), (sx + d, sy + d), _X_WIDTH)
        pygame.draw.line(screen, color, (sx + d, sy - d), (sx - d, sy + d), _X_WIDTH)


def draw_explosions(screen, cx: float, cy: float) -> None:
    """繪製爆炸擴散圓（半徑從 0 開始放大）。"""
    now   = time.perf_counter()
    alive = []
    for wx, wy, owner, t0 in _explosions:
        elapsed = now - t0
        if elapsed >= EXPL_DURATION:
            continue
        alive.append((wx, wy, owner, t0))
        frac  = elapsed / EXPL_DURATION
        r     = max(1, int(EXPL_MAX_R * frac))
        alpha = int(210 * (1.0 - frac))
        color = COL_BULLET.get(owner, (255, 200, 100))
        sx, sy = ws(wx, wy, cx, cy)
        if sx < -EXPL_MAX_R or sx > SCREEN_W + EXPL_MAX_R:
            continue
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*color, alpha), (r, r), r)
        screen.blit(surf, (sx - r, sy - r))
    _explosions[:] = alive
