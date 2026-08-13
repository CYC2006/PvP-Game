"""Zombie RMB — 腐蝕吐息視覺效果

球體本身即是暈眩判定區域（由 server 權威判定），這裡純粹依 state.zombie_orbs
目前存在的內容繪製淺灰色半透明圓，雙方皆可見，無需額外追蹤生命週期。

顏色刻意選淺灰／中灰：場地底色 COL_MAP_BG=(45,55,45) 偏暗綠，原本的深黑灰
(55,55,62) 亮度太接近底色，幾乎看不見；改用較亮的中性灰以確保對比度。
"""

import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H

ORB_COLOR = (185, 185, 190)
ORB_ALPHA = 150


def draw(screen, state, cx: float, cy: float) -> None:
    for orb in state.zombie_orbs.values():
        r = max(1, int(orb.radius))
        sx, sy = ws(orb.x, orb.y, cx, cy)
        if sx < -r or sx > SCREEN_W + r or sy < -r or sy > SCREEN_H + r:
            continue
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*ORB_COLOR, ORB_ALPHA), (r, r), r)
        screen.blit(surf, (sx - r, sy - r))
