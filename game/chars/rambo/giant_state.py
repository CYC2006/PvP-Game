GROW_TICKS   = 48    # 4 stages × 12 ticks  (100→125→150→175→200%)
ACTIVE_TICKS = 300   # 5 seconds
SHRINK_TICKS = 48
TOTAL_TICKS  = 396   # entire skill duration

_STAGE_TICKS = 12
_STAGES      = ((1.0, 1.25), (1.25, 1.50), (1.50, 1.75), (1.75, 2.0))


def activate_giant(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player or player.giant_tick >= 0:
        return
    player.giant_tick = state.tick


def step_giant(state) -> None:
    for player in state.players.values():
        if player.giant_tick < 0:
            continue
        if state.tick - player.giant_tick >= TOTAL_TICKS:
            player.giant_tick = -1


def get_scale(giant_age: int) -> float:
    """Return visual scale given ticks since skill activation (0 = just started)."""
    if giant_age < 0 or giant_age >= TOTAL_TICKS:
        return 1.0
    if giant_age < GROW_TICKS:
        stage = giant_age // _STAGE_TICKS
        t     = (giant_age % _STAGE_TICKS) / _STAGE_TICKS
        s0, s1 = _STAGES[stage]
        return s0 + (s1 - s0) * t
    if giant_age < GROW_TICKS + ACTIVE_TICKS:
        return 2.0
    shrink_t = (giant_age - GROW_TICKS - ACTIVE_TICKS) / SHRINK_TICKS
    return 2.0 - shrink_t * 1.0
