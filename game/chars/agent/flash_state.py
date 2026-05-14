import math
from game.state import Bullet, PLAYER_RADIUS, BULLET_MAX_RANGE

FLASH_RADIUS = 120.0
FLASH_TICKS  = 180   # 1s 全白 + 2s 恢復 × 60 fps


def spawn_flash_grenade(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    SPEED  = 8.8
    DECEL  = 0.2
    LINGER = 12
    bid = state._next_bullet_id
    state._next_bullet_id = (state._next_bullet_id + 1) % 256
    state.bullets[bid] = Bullet(
        id=bid, owner_id=owner_id,
        x=player.x + ux * (PLAYER_RADIUS + 12),
        y=player.y + uy * (PLAYER_RADIUS + 12),
        dx=ux * SPEED, dy=uy * SPEED,
        aim_angle=math.degrees(math.atan2(uy * SPEED, ux * SPEED)),
        max_range=BULLET_MAX_RANGE * 999,
        decel=DECEL,
        linger_ticks=LINGER,
        bullet_type=1,
    )


def trigger_flash_explosion(state, x: float, y: float, owner_id: int) -> None:
    for pid, player in state.players.items():
        if pid == owner_id:
            continue
        if math.hypot(player.x - x, player.y - y) <= FLASH_RADIUS:
            player.flash_ticks = FLASH_TICKS
