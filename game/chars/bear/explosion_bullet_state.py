import math
from game.state import Bullet, PLAYER_RADIUS

EXPL_RADIUS  = 120.0
EXPL_DMG_MAX = 50
EXPL_DMG_MIN = 10


def spawn_explosion_bullet(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    rx, ry = -uy, ux
    spawn_x = player.x + ux * (PLAYER_RADIUS + 10) + rx * 14
    spawn_y = player.y + uy * (PLAYER_RADIUS + 10) + ry * 14
    spd = player.bullet_speed
    bid = state._next_bullet_id
    state._next_bullet_id = (state._next_bullet_id + 1) % 256
    state.bullets[bid] = Bullet(
        id=bid, owner_id=owner_id,
        x=spawn_x, y=spawn_y,
        dx=ux * spd, dy=uy * spd,
        aim_angle=math.degrees(math.atan2(uy, ux)),
        max_range=player.bullet_range,
        bullet_type=7,
    )


def trigger_explosion(state, x: float, y: float, owner_id: int) -> None:
    for pid, player in state.players.items():
        if pid == owner_id:
            continue
        dist = math.hypot(player.x - x, player.y - y)
        if dist <= EXPL_RADIUS:
            t      = dist / EXPL_RADIUS
            damage = int(EXPL_DMG_MIN + (EXPL_DMG_MAX - EXPL_DMG_MIN) * (1 - t) * (1 - t))
            if player.giant_tick >= 0:
                damage = int(damage * 0.8)
            state.apply_damage(pid, damage)
