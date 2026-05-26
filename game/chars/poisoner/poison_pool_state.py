import math
import random
from game.state import Bullet, BType, PoisonPool, PLAYER_RADIUS

POOL_RADIUS    = 150.0   # RMB 大毒液池碰撞半徑
POOL_TICKS     = 300     # 5s（RMB 與 Space 小池共用）
DOT_INTERVAL   = 30      # RMB 池：每 0.5s 傷害一次
DOT_MIN        = 3
DOT_MAX        = 3
POOL_BULLET_SPEED = 10.0    # px/tick
POOL_BULLET_RANGE = 1200.0

SPACE_DOT_INTERVAL = 30  # Space 小池：每 0.5s 嘗試疊層一次（無傷害）


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
        bullet_type=BType.POISON_BALL,
    )


def create_poison_pool(state, x: float, y: float, owner_id: int) -> None:
    """建立 RMB 大毒液池（radius=150, pool_source='rmb'）。"""
    ppid = state._next_pool_id
    state._next_pool_id = (state._next_pool_id + 1) % 256
    state.poison_pools[ppid] = PoisonPool(
        id=ppid, owner_id=owner_id,
        x=x, y=y,
        spawn_tick=state.tick,
        radius=POOL_RADIUS,
        pool_source='rmb',
    )


def create_small_poison_pool(state, x: float, y: float,
                              owner_id: int, radius: float) -> None:
    """建立 Space 小毒液池（radius=20~30, pool_source='space'）。"""
    ppid = state._next_pool_id
    state._next_pool_id = (state._next_pool_id + 1) % 256
    state.poison_pools[ppid] = PoisonPool(
        id=ppid, owner_id=owner_id,
        x=x, y=y,
        spawn_tick=state.tick,
        radius=radius,
        pool_source='space',
    )


def step_poison_pools(state) -> None:
    from game.chars.poisoner.poison_stack_state import add_poison_stack

    # 每 tick 依毒素層數設定速度懲罰：1 - 0.1 × stacks（最低 0.5，即 5 層）
    for player in state.players.values():
        player.speed_penalty = max(0.5, 1.0 - 0.1 * player.poison_stacks)

    to_remove = []
    for ppid, pool in state.poison_pools.items():
        age = state.tick - pool.spawn_tick
        if age >= POOL_TICKS:
            to_remove.append(ppid)
            continue

        opponent_id = 3 - pool.owner_id
        opp = state.players.get(opponent_id)
        if not opp:
            continue

        dist = math.hypot(opp.x - pool.x, opp.y - pool.y)
        if dist > pool.radius:
            continue

        if pool.pool_source == 'rmb':
            if age > 0 and age % DOT_INTERVAL == 0:
                dmg = random.randint(DOT_MIN, DOT_MAX)
                if opp.giant_tick >= 0:
                    dmg = int(dmg * 0.8)
                state.apply_damage(opponent_id, dmg)
                add_poison_stack(state, opponent_id, 'rmb')
        elif pool.pool_source == 'space':
            if age > 0 and age % SPACE_DOT_INTERVAL == 0:
                add_poison_stack(state, opponent_id, 'space_pool')

    for ppid in to_remove:
        state.poison_pools.pop(ppid, None)
