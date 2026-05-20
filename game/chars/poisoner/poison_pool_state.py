import math
import random
from game.state import Bullet, PoisonPool, PLAYER_RADIUS

POOL_RADIUS         = 150.0
POOL_TICKS          = 300    # 5s
DOT_INTERVAL        = 30     # 每 0.5s
DOT_MIN             = 3
DOT_MAX             = 5
POOL_BULLET_SPEED   = 10.0   # px/tick（600 px/s）
POOL_BULLET_RANGE   = 1200.0


def spawn_pool_bullet(state, owner_id: int, aim_x: float, aim_y: float) -> None:
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
    bid = state._next_bullet_id
    state._next_bullet_id = (state._next_bullet_id + 1) % 256
    state.bullets[bid] = Bullet(
        id=bid, owner_id=owner_id,
        x=spawn_x, y=spawn_y,
        dx=ux * POOL_BULLET_SPEED,
        dy=uy * POOL_BULLET_SPEED,
        aim_angle=math.degrees(math.atan2(uy, ux)),
        max_range=POOL_BULLET_RANGE,
        bullet_type=8,
    )


def create_poison_pool(state, x: float, y: float, owner_id: int) -> None:
    ppid = state._next_pool_id
    state._next_pool_id = (state._next_pool_id + 1) % 256
    state.poison_pools[ppid] = PoisonPool(
        id=ppid, owner_id=owner_id,
        x=x, y=y,
        spawn_tick=state.tick,
    )


def step_poison_pools(state) -> None:
    # 每 tick 開始先重置所有玩家的速度懲罰（由本模組負責管理）
    for player in state.players.values():
        player.speed_penalty = 1.0

    to_remove = []
    for ppid, pool in state.poison_pools.items():
        age = state.tick - pool.spawn_tick
        if age >= POOL_TICKS:
            to_remove.append(ppid)
            continue

        opponent_id = 3 - pool.owner_id
        opp = state.players.get(opponent_id)
        if opp:
            dist = math.hypot(opp.x - pool.x, opp.y - pool.y)
            if dist <= POOL_RADIUS:
                opp.speed_penalty = 0.8   # 毒液慢速 20%
                if age > 0 and age % DOT_INTERVAL == 0:
                    dmg = random.randint(DOT_MIN, DOT_MAX)
                    if opp.giant_tick >= 0:
                        dmg = int(dmg * 0.8)
                    state.apply_damage(opponent_id, dmg)

    for ppid in to_remove:
        state.poison_pools.pop(ppid, None)
