import math
import random
from game.state import Bullet, BULLET_MAX_RANGE

MINI_RADIUS  = 60.0
MINI_DMG_MIN = 5
MINI_DMG_MAX = 25   # 5 + 20 × (1 − 0/120)²

_DROP_RADIUS = 40.0
_LINGER_MIN  = 15
_LINGER_MAX  = 25
_COUNT       = 6


def spawn_mini_grenades(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    sector = math.tau / _COUNT
    for i in range(_COUNT):
        a = sector * i + random.uniform(0, sector)
        r = random.uniform(_DROP_RADIUS * 0.3, _DROP_RADIUS)
        bid = state._next_bullet_id
        state._next_bullet_id = (state._next_bullet_id + 1) % 256
        state.bullets[bid] = Bullet(
            id=bid, owner_id=owner_id,
            x=player.x + math.cos(a) * r,
            y=player.y + math.sin(a) * r,
            dx=0.0, dy=0.0,
            aim_angle=0.0,
            max_range=BULLET_MAX_RANGE * 999,
            decel=0.2,
            linger_ticks=random.randint(_LINGER_MIN, _LINGER_MAX),
            bullet_type=5,
        )


def trigger_mini_grenade_explosion(state, x: float, y: float, owner_id: int) -> None:
    for pid, player in state.players.items():
        if pid == owner_id:
            continue
        dist = math.hypot(player.x - x, player.y - y)
        if dist <= MINI_RADIUS:
            damage = int(MINI_DMG_MIN + 20 * (1 - dist / 120) ** 2)
            if player.giant_tick >= 0:
                damage = int(damage * 0.8)
            player.hp -= damage
            if player.hp <= 0:
                player.respawn()
