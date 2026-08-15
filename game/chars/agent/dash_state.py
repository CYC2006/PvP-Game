DASH_TICKS = 8   # matches client-side decay duration in game/input.py (_DASH_V0/_DASH_DECEL/_DASH_MIN_SPEED)


def activate_agent_dash(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if player is None or player.agent_dash_tick >= 0:
        return
    player.agent_dash_tick = state.tick


def step_agent_dash(state) -> None:
    for player in state.players.values():
        if player.agent_dash_tick < 0:
            continue
        if state.tick - player.agent_dash_tick > DASH_TICKS:
            player.agent_dash_tick = -1
