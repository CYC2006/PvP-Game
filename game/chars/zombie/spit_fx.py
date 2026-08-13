"""Zombie RMB — 腐蝕吐息視覺效果

球體本身即是暈眩判定區域（由 server 權威判定），這裡純粹依 state.zombie_orbs
目前存在的內容繪製「粗糙結晶」（不規則多邊形，取代單純圓形），紫色核心 +
薰衣草紫外暈，雙方皆可見，無需額外追蹤生命週期。

每顆球的多邊形頂點由 orb.id 當種子決定，同一顆球每幀重繪都會得到完全相同的
形狀（不會抖動），不同球之間形狀彼此不同。外暈與核心共用同一組角度/抖動，
只是半徑倍率不同，讓兩層看起來像同一顆結晶的層次，而不是兩坨互不相關的形狀。
"""

import math
import random
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H

CORE_COLOR = (165, 115, 205)
CORE_ALPHA = 175
CORE_SCALE = 0.82

HALO_COLOR = (195, 165, 225)
HALO_ALPHA = 95
HALO_SCALE = 1.2


def _facet_offsets(seed: int) -> list:
    """回傳 [(角度 rad, 半徑倍率)]，同一 seed 永遠得到同一組結果。"""
    rng   = random.Random(seed)
    n     = rng.randint(6, 8)
    start = rng.uniform(0, 360)
    step  = 360.0 / n
    return [
        (math.radians(start + i * step + rng.uniform(-10, 10)),
         rng.uniform(0.62, 1.0))
        for i in range(n)
    ]


def _crystal_points(cx: float, cy: float, radius: float, offsets: list) -> list:
    return [
        (cx + radius * factor * math.cos(ang),
         cy + radius * factor * math.sin(ang))
        for ang, factor in offsets
    ]


def draw(screen, state, cx: float, cy: float) -> None:
    for orb in state.zombie_orbs.values():
        fade = max(0, min(255, orb.fade)) / 255.0
        if fade <= 0.0:
            continue

        r  = orb.radius
        hs = int(r * HALO_SCALE) + 4
        sx, sy = ws(orb.x, orb.y, cx, cy)
        if sx < -hs or sx > SCREEN_W + hs or sy < -hs or sy > SCREEN_H + hs:
            continue

        offsets  = _facet_offsets(orb.id)
        halo_pts = _crystal_points(hs, hs, r * HALO_SCALE, offsets)
        core_pts = _crystal_points(hs, hs, r * CORE_SCALE, offsets)

        surf = pygame.Surface((hs * 2, hs * 2), pygame.SRCALPHA)
        pygame.draw.polygon(surf, (*HALO_COLOR, int(HALO_ALPHA * fade)), halo_pts)
        pygame.draw.polygon(surf, (*CORE_COLOR, int(CORE_ALPHA * fade)), core_pts)
        screen.blit(surf, (sx - hs, sy - hs))
