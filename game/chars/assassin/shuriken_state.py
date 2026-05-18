import math
from game.state import Bullet, PLAYER_RADIUS, BULLET_MAX_RANGE

SHURIKEN_GROW_RATE = 0.3    # px/tick，碰撞半徑每 tick 增加量
SHURIKEN_BASE_DMG  = 15     # 初始傷害
SHURIKEN_DMG_SCALE = 1.5    # 每 px 碰撞半徑增加的傷害


def spawn_shuriken(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    rx, ry = -uy, ux   # 右側垂直方向（與 _spawn_bullet 相同）
    _BARREL_FWD   = PLAYER_RADIUS + 10   # 26 px
    _BARREL_RIGHT = 14
    SPEED = 800 / 60
    bid = state._next_bullet_id
    state._next_bullet_id = (state._next_bullet_id + 1) % 256
    state.bullets[bid] = Bullet(
        id=bid, owner_id=owner_id,
        x=player.x + ux * _BARREL_FWD + rx * _BARREL_RIGHT,
        y=player.y + uy * _BARREL_FWD + ry * _BARREL_RIGHT,
        dx=ux * SPEED, dy=uy * SPEED,
        aim_angle=math.degrees(math.atan2(uy, ux)),
        max_range=float('inf'),
        spawn_tick=state.tick,
        bullet_type=3,
    )
