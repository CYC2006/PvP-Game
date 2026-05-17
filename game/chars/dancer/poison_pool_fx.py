import math
import time
import random
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H

POOL_RADIUS    = 300.0
POOL_TICKS     = 600
BUBBLE_INTERVAL = 0.08   # 秒，生成新泡泡的最短間隔

# pool_id → {'last_bubble_t': float, 'bubbles': list[(lx, ly, r, birth_t, lifetime, speed_y)]}
_pool_state: dict = {}


def update(state) -> None:
    """每幀呼叫，為所有池子生成新泡泡並清理已消失的池。"""
    now = time.perf_counter()
    current_ids = set(state.poison_pools)

    # 清理已消失的池
    for pid in list(_pool_state):
        if pid not in current_ids:
            del _pool_state[pid]

    for ppid, pool in state.poison_pools.items():
        ps = _pool_state.setdefault(ppid, {'last_bubble_t': 0.0, 'bubbles': []})

        # 生成新泡泡
        if now - ps['last_bubble_t'] >= BUBBLE_INTERVAL:
            ps['last_bubble_t'] = now
            # 在池內隨機位置生成
            angle  = random.uniform(0, math.tau)
            dist_r = random.uniform(0, POOL_RADIUS * 0.9)
            lx     = math.cos(angle) * dist_r
            ly     = math.sin(angle) * dist_r
            r      = random.uniform(6, 22)
            life   = random.uniform(0.8, 2.0)
            spd    = random.uniform(20, 55)   # px/s 向上
            ps['bubbles'].append([lx, ly, r, now, life, spd])

        # 清理過期泡泡
        ps['bubbles'] = [b for b in ps['bubbles']
                         if now - b[3] < b[4]]


def draw(screen, state, cx: float, cy: float) -> None:
    """繪製所有毒液池及其內部泡泡特效。"""
    now = time.perf_counter()
    for ppid, pool in state.poison_pools.items():
        age   = state.tick - pool.spawn_tick
        # 最後 60 tick 開始淡出
        fade  = max(0.0, min(1.0, (POOL_TICKS - age) / 60))
        sx, sy = ws(pool.x, pool.y, cx, cy)

        r = int(POOL_RADIUS)
        if -r <= sx <= SCREEN_W + r and -r <= sy <= SCREEN_H + r:
            # ── 主圓（填充 + 邊框）──
            surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            sc   = (r + 2, r + 2)
            pygame.draw.circle(surf, (60, 200, 60, int(50 * fade)),  sc, r)       # 半透明填充
            pygame.draw.circle(surf, (30, 160, 30, int(200 * fade)), sc, r, 3)    # 深綠邊框
            screen.blit(surf, (sx - r - 2, sy - r - 2))

            # ── 泡泡 ──
            ps = _pool_state.get(ppid)
            if ps:
                for lx, ly, br, birth_t, lifetime, spd in ps['bubbles']:
                    elapsed = now - birth_t
                    t       = elapsed / lifetime
                    # 向上移動
                    bx = sx + int(lx)
                    by = sy + int(ly - spd * elapsed)
                    alpha = int(160 * fade * (1.0 - t))
                    br_int = max(1, int(br * (1.0 - t * 0.3)))
                    if -br_int <= bx - sx <= r + br_int:
                        bsurf = pygame.Surface((br_int * 2 + 2, br_int * 2 + 2), pygame.SRCALPHA)
                        pygame.draw.circle(bsurf, (100, 230, 100, alpha),
                                           (br_int + 1, br_int + 1), br_int, 2)
                        screen.blit(bsurf, (bx - br_int - 1, by - br_int - 1))
