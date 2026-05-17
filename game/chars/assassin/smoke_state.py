import math
import random
from game.state import Bullet, SmokePatch, PLAYER_RADIUS, BULLET_MAX_RANGE

SMOKE_DURATION = 360   # 6s × 60 fps
SMOKE_FADE     = 60    # 1s 淡出


def spawn_smoke_grenade(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    DECEL  = 0.2
    LINGER = 12
    DELAYS = (0, 4, 8, 12, 16)
    SPD_MIN, SPD_MAX, N = 6.0, 12.0, 5
    bucket_w = (SPD_MAX - SPD_MIN) / N
    buckets  = random.sample(range(N), N)
    spawn_x = player.x + ux * (PLAYER_RADIUS + 12)
    spawn_y = player.y + uy * (PLAYER_RADIUS + 12)
    for delay, bucket in zip(DELAYS, buckets):
        lo  = SPD_MIN + bucket * bucket_w
        spd = random.uniform(lo, lo + bucket_w)
        dev = math.radians(random.uniform(-30.0, 30.0))
        cos_d, sin_d = math.cos(dev), math.sin(dev)
        gux = ux * cos_d - uy * sin_d
        guy = ux * sin_d + uy * cos_d
        bid = state._next_bullet_id
        state._next_bullet_id = (state._next_bullet_id + 1) % 256
        b = Bullet(
            id=bid, owner_id=owner_id,
            x=spawn_x, y=spawn_y,
            dx=gux * spd, dy=guy * spd,
            aim_angle=math.degrees(math.atan2(guy, gux)),
            max_range=BULLET_MAX_RANGE * 999,
            decel=DECEL,
            linger_ticks=LINGER,
            bullet_type=4,
            spawn_tick=state.tick,
        )
        if delay == 0:
            state.bullets[bid] = b
        else:
            import bisect
            bisect.insort(state._pending_pellets, (state.tick + delay, state._pending_seq, b))
            state._pending_seq += 1


def trigger_smoke_explosion(state, x: float, y: float) -> None:
    radius = 130 * random.uniform(0.8, 1.2)
    sid = state._next_smoke_id
    state._next_smoke_id = (state._next_smoke_id + 1) % 256
    state.smoke_patches[sid] = SmokePatch(
        id=sid, x=x, y=y, radius=radius, spawn_tick=state.tick)


def step_smoke_patches(state) -> None:
    expired = [sid for sid, s in state.smoke_patches.items()
               if state.tick - s.spawn_tick >= SMOKE_DURATION + SMOKE_FADE]
    for sid in expired:
        del state.smoke_patches[sid]
