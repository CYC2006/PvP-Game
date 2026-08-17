"""Hunter RMB — 空氣炮視覺效果

以白色半透明填色圓形表現高速飛行的空氣炮彈。
每幀直接從 state.air_cannons 讀取當前位置，無需額外狀態追蹤。
"""
import pygame
from game import audio
from game.render_utils import ws, SCREEN_W, SCREEN_H

_CANNON_RADIUS = 25    # 視覺半徑 px（與碰撞半徑對應）
_FILL_ALPHA    = 120   # 填色透明度（0–255）
_RING_ALPHA    = 200   # 外環透明度
_RING_WIDTH    = 3     # 外環線寬 px

_known_ids: set = set()   # 上一幀已知的 air_cannon id，偵測新出現的拋射物


def detect_cannon_sfx(state, my_id: int) -> None:
    current_ids = set(state.air_cannons)
    for cid in current_ids - _known_ids:
        cannon = state.air_cannons[cid]
        volume = audio.VOLUME_SELF if cannon.owner_id == my_id else audio.VOLUME_OTHER
        audio.play('others/hunter_air_cannon.wav', volume)
    _known_ids.clear()
    _known_ids.update(current_ids)


def draw(screen: pygame.Surface, state, cx: float, cy: float) -> None:
    """繪製所有空氣炮拋射物。cx/cy 為鏡頭世界座標中心。"""
    if not state.air_cannons:
        return

    for cannon in state.air_cannons.values():
        sx, sy = ws(cannon.x, cannon.y, cx, cy)
        # 快速裁剪：超出螢幕範圍的不繪製
        r = _CANNON_RADIUS
        if sx + r < 0 or sx - r > SCREEN_W or sy + r < 0 or sy - r > SCREEN_H:
            continue

        # 填色：白色半透明圓形
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 255, _FILL_ALPHA), (r, r), r)
        # 外環：稍深輪廓
        pygame.draw.circle(surf, (220, 240, 255, _RING_ALPHA), (r, r), r, _RING_WIDTH)
        screen.blit(surf, (int(sx) - r, int(sy) - r))
