import math

BURST_COUNT    = 1
BURST_INTERVAL = 3   # ticks between shots (unused for single shot)


def activate_burst(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player or player.burst_next_tick >= 0:
        return
    if math.hypot(aim_x, aim_y) == 0:
        return
    player.burst_shots_fired = 0
    player.burst_aim_x       = aim_x
    player.burst_aim_y       = aim_y
    player.burst_next_tick   = state.tick


def step_burst(state) -> None:
    for player in state.players.values():
        if player.burst_next_tick < 0:
            continue
        if state.tick >= player.burst_next_tick:
            state._spawn_bullet(player.id,
                                player.burst_aim_x, player.burst_aim_y,
                                bullet_scale_override=2.0, spread_override=0.0)
            player.burst_shots_fired += 1
            if player.burst_shots_fired >= BURST_COUNT:
                player.burst_next_tick   = -1
                player.burst_shots_fired = 0
            else:
                player.burst_next_tick = state.tick + BURST_INTERVAL
