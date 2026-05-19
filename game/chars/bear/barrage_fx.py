"""Bear R — 滾動空襲視覺效果

每枚空襲分兩階段：
  1. 縮小瞄準圓（BARRAGE_FUSE tick）：圓圈從 BARRAGE_EXPL_R 縮至 0
  2. 爆炸擴散圓（time-based，同地雷爆炸風格）：圓從 0 擴散至 EXPL_MAX_R
"""

import time
import pygame
from game.render_utils import ws, SCREEN_W, COL_BULLET
from game.chars.bear.barrage_state import BARRAGE_FUSE, BARRAGE_EXPL_R

EXPL_MAX_R    = 110
EXPL_DURATION = 0.5   # 秒

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
            # 新出現的 strike
            explode_t = now if age >= BARRAGE_FUSE else None
            _known[sid] = (strike.x, strike.y, strike.owner_id, explode_t)
            if explode_t is not None:
                _explosions.append((strike.x, strike.y, strike.owner_id, explode_t))
        else:
            wx, wy, oid, explode_t = prev
            if explode_t is None and age >= BARRAGE_FUSE:
                # 剛越過引爆時刻 → 觸發爆炸
                explode_t = now
                _known[sid] = (wx, wy, oid, explode_t)
                _explosions.append((wx, wy, oid, explode_t))

    # 清理已從 state 移除的 strike
    for sid in list(_known):
        if sid not in current_ids:
            _known.pop(sid)


def draw(screen, state, cx: float, cy: float) -> None:
    """繪製縮小瞄準圓（雙方皆可見）。"""
    for sid, strike in state.barrage_strikes.items():
        age = state.tick - strike.spawn_tick
        if age < 0 or age >= BARRAGE_FUSE:
            continue   # 還未出現 or 已進入爆炸階段

        sx, sy = ws(strike.x, strike.y, cx, cy)
        if sx < -BARRAGE_EXPL_R or sx > SCREEN_W + BARRAGE_EXPL_R:
            continue

        frac  = age / BARRAGE_FUSE          # 0.0 → 1.0
        r     = max(2, int(BARRAGE_EXPL_R * (1.0 - frac)))
        alpha = int(230 * (1.0 - frac * 0.4))
        lw    = max(2, int(5 * (1.0 - frac * 0.6)))
        color = COL_BULLET.get(strike.owner_id, (255, 200, 100))

        surf = pygame.Surface((BARRAGE_EXPL_R * 2 + 4, BARRAGE_EXPL_R * 2 + 4),
                              pygame.SRCALPHA)
        c = BARRAGE_EXPL_R + 2
        pygame.draw.circle(surf, (*color, alpha), (c, c), r, lw)
        # 中心十字準星
        cs = max(1, int(6 * (1.0 - frac)))
        pygame.draw.line(surf, (*color, alpha), (c - cs, c), (c + cs, c), max(1, lw - 1))
        pygame.draw.line(surf, (*color, alpha), (c, c - cs), (c, c + cs), max(1, lw - 1))
        screen.blit(surf, (sx - c, sy - c))


def draw_explosions(screen, cx: float, cy: float) -> None:
    """繪製爆炸擴散圓（同地雷 FX 風格）。"""
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
