GROW_TICKS   = 48    # 4 stages × 12 ticks
ACTIVE_TICKS = 300   # 5 seconds
SHRINK_TICKS = 48
TOTAL_TICKS  = 396   # entire skill duration

_STAGE_TICKS = 12
_STAGES      = ((1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0))


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
        return 3.0
    shrink_t = (giant_age - GROW_TICKS - ACTIVE_TICKS) / SHRINK_TICKS
    return 3.0 - shrink_t * 2.0
