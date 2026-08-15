import math
import random
from game.state import BladeArc, PLAYER_RADIUS, MAP_WIDTH, MAP_HEIGHT

BLADE_LIFESPAN   = 30   # 0.5s × 60 fps
BLADE_HIT_RADIUS = 12   # px，刀片碰撞半徑


def activate_blade_arc(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    theta = math.atan2(aim_y, aim_x)

    # 6 片刀片視為同一次普攻：對玩家、對障礙物各自只算一次命中
    player.zombie_blade_hit_player   = False
    player.zombie_blade_hit_obstacle = False

    left_base  = theta - math.pi / 4
    right_base = theta + math.pi / 4
    left_blades, right_blades = [], []
    for i in range(3):
        offset = math.radians((i - 1) * 4.0)
        for blades, base, direction in (
                (left_blades,  left_base,  +1),
                (right_blades, right_base, -1)):
            start  = base + offset
            radius = random.uniform(40.0, 60.0)
            blades.append((player.x + math.cos(start) * radius,
                           player.y + math.sin(start) * radius,
                           radius, start, direction))

    for i in range(3):
        for j, (side_list, _) in enumerate(((left_blades, +1), (right_blades, -1))):
            x, y, radius, orbit_angle, direction = side_list[i]
            state._blade_spawn_queue.append((
                state.tick + (i * 2 + j) * 2,
                owner_id, x, y, radius, orbit_angle, direction,
            ))


def step_blade_arcs(state, obstacles: dict = None, obstacle_hp: dict = None) -> None:
    remaining = []
    for entry in state._blade_spawn_queue:
        spawn_tick, owner_id, x, y, radius, orbit_angle, direction = entry
        if state.tick >= spawn_tick:
            bid = state._next_blade_id
            state._next_blade_id = (state._next_blade_id + 1) % 256
            state.blade_arcs[bid] = BladeArc(
                id=bid, owner_id=owner_id,
                x=x, y=y,
                orbit_radius=radius,
                orbit_angle=orbit_angle,
                direction=direction,
                damage=0,   # 不再逐片預骰，命中當下才骰一次（見下方）
            )
        else:
            remaining.append(entry)
    state._blade_spawn_queue[:] = remaining

    to_remove = []
    for blade in state.blade_arcs.values():
        player = state.players.get(blade.owner_id)
        if player is None:
            to_remove.append(blade.id)
            continue
        blade.age += 1
        progress = blade.age / BLADE_LIFESPAN
        ease = 1.0 - (1.0 - progress) ** 2
        current_angle = blade.orbit_angle + blade.direction * (math.pi / 2) * ease
        blade.x = player.x + math.cos(current_angle) * blade.orbit_radius
        blade.y = player.y + math.sin(current_angle) * blade.orbit_radius

        if not blade.hit:
            hit_something = False

            if not player.zombie_blade_hit_player:
                opponent_id = 3 - blade.owner_id
                opponent    = state.players.get(opponent_id)
                if opponent:
                    dist = math.hypot(blade.x - opponent.x, blade.y - opponent.y)
                    if dist < PLAYER_RADIUS + BLADE_HIT_RADIUS:
                        dmg = state._roll_damage(player)
                        if opponent.giant_tick >= 0:
                            dmg = int(dmg * 0.8)
                        state.apply_damage(opponent_id, dmg)
                        if player.zombie_rage_tick >= 0:   # 嗜血：普攻傷害的一半回復自身血量
                            player.hp = min(player.max_hp, player.hp + dmg // 2)
                        player.zombie_blade_hit_player = True
                        hit_something = True

            if (not hit_something and obstacles
                    and not player.zombie_blade_hit_obstacle):
                for oid, obs in obstacles.items():
                    if oid in state.destroyed_obstacles or not obs.solid:
                        continue
                    if obs.collides_circle(blade.x, blade.y, BLADE_HIT_RADIUS):
                        if obstacle_hp is not None and obs.destructible:
                            dmg = state._roll_damage(player)
                            obstacle_hp[oid] -= dmg
                            if obstacle_hp[oid] <= 0:
                                state.destroyed_obstacles.add(oid)
                                state._handle_obstacle_drop(obs)
                        player.zombie_blade_hit_obstacle = True
                        hit_something = True
                        break

            if hit_something:
                blade.hit = True

        if blade.age >= BLADE_LIFESPAN:
            to_remove.append(blade.id)
    for bid in to_remove:
        state.blade_arcs.pop(bid, None)
