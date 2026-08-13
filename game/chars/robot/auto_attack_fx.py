import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H
from game.chars.robot.auto_attack_state import ATTACK_RADIUS

_FILL_COLOR = (255, 220, 40)
_FILL_ALPHA = 28
_RING_ALPHA = 90


def draw(screen, state, my_player_id: int, cx: float, cy: float, my_char: str) -> None:
    """Robot 普攻自動鎖定範圍的地面提示圈——只有 Robot 玩家自己看得到，對手不可見。

    char_name 不會經由 network/protocol.py 同步到 client 端的 Player 物件，
    角色判斷必須用 renderer.draw() 從 player_chars（大廳選角）解析出的
    my_char，不能用 state.players[my_player_id].char_name（永遠是預設值）。
    """
    if my_char != 'Robot':
        return
    me = state.players.get(my_player_id)
    if me is None:
        return

    r = int(ATTACK_RADIUS)
    sx, sy = ws(me.x, me.y, cx, cy)
    if not (-r <= sx <= SCREEN_W + r and -r <= sy <= SCREEN_H + r):
        return

    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    c = (r, r)
    pygame.draw.circle(surf, (*_FILL_COLOR, _FILL_ALPHA), c, r)
    pygame.draw.circle(surf, (*_FILL_COLOR, _RING_ALPHA), c, r, 2)
    screen.blit(surf, (sx - r, sy - r))
