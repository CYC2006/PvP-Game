def activate_speed_boost(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if player:
        player.speed_boost_ticks = 180   # 3s × 60 fps
        player.speed_boost_mult  = 1.5
