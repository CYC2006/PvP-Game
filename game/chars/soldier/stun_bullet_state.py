import math
from game.state import Bullet, PLAYER_RADIUS, BULLET_MAX_RANGE

STUN_RADIUS = 100.0
STUN_DMG    = 10
STUN_TICKS  = 30   # 0.5s × 60 fps


def spawn_stun_bullet(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    rx, ry = -uy, ux  # right vector perpendicular to aim
    barrel_fwd   = PLAYER_RADIUS + 10
    barrel_right = 14
    spawn_x = player.x + ux * barrel_fwd + rx * barrel_right
    spawn_y = player.y + uy * barrel_fwd + ry * barrel_right
    spd = player.bullet_speed
    bid = state._next_bullet_id
    state._next_bullet_id = (state._next_bullet_id + 1) % 256
    state.bullets[bid] = Bullet(
        id=bid, owner_id=owner_id,
        x=spawn_x,
        y=spawn_y,
        dx=ux * spd, dy=uy * spd,
        aim_angle=math.degrees(math.atan2(uy, ux)),
        max_range=player.bullet_range,
        bullet_type=6,
    )


def trigger_stun_explosion(state, x: float, y: float, owner_id: int) -> None:
    for pid, player in state.players.items():
        if pid == owner_id:
            continue
        dist = math.hypot(player.x - x, player.y - y)
        if dist <= STUN_RADIUS:
            dmg = int(STUN_DMG * 0.8) if player.giant_tick >= 0 else STUN_DMG
            player.hp -= dmg
            player.stun_until = max(
                player.stun_until if player.stun_until > state.tick else state.tick,
                state.tick + STUN_TICKS,
            )
            if player.hp <= 0:
                player.respawn()
