import math
import random
from game.state import Bullet, PLAYER_RADIUS, BULLET_MAX_RANGE

GRENADE_RADIUS  = 120.0
GRENADE_DMG_MAX = 50
GRENADE_DMG_MIN = 10


def spawn_grenade(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    DECEL   = 0.2
    LINGER  = 12
    DELAYS  = (0, 4, 8)
    spawn_x = player.x + ux * (PLAYER_RADIUS + 12)
    spawn_y = player.y + uy * (PLAYER_RADIUS + 12)
    for delay in DELAYS:
        spd = round(random.uniform(8.0, 11.0), 1)
        dev = math.radians(random.uniform(-12.0, 12.0))
        cos_d, sin_d = math.cos(dev), math.sin(dev)
        gux = ux * cos_d - uy * sin_d
        guy = ux * sin_d + uy * cos_d
        bid = state._next_bullet_id
        state._next_bullet_id = (state._next_bullet_id + 1) % 256
        b = Bullet(
            id=bid, owner_id=owner_id,
            x=spawn_x, y=spawn_y,
            dx=gux * spd, dy=guy * spd,
            aim_angle=math.degrees(math.atan2(guy * spd, gux * spd)),
            max_range=BULLET_MAX_RANGE * 999,
            decel=DECEL,
            linger_ticks=LINGER,
            bullet_type=2,
        )
        if delay == 0:
            state.bullets[bid] = b
        else:
            state._pending_pellets.append((state.tick + delay, b))


def trigger_grenade_explosion(state, x: float, y: float, owner_id: int) -> None:
    for pid, player in state.players.items():
        if pid == owner_id:
            continue
        dist = math.hypot(player.x - x, player.y - y)
        if dist <= GRENADE_RADIUS:
            t      = dist / GRENADE_RADIUS
            damage = int(GRENADE_DMG_MIN
                         + (GRENADE_DMG_MAX - GRENADE_DMG_MIN) * (1 - t) * (1 - t))
            if player.giant_tick >= 0:
                damage = int(damage * 0.8)
            player.hp -= damage
            if player.hp <= 0:
                player.respawn()
