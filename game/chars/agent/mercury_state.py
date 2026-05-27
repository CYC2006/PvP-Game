import math

VOLLEY_COUNT    = 7
VOLLEY_INTERVAL = 6                                # ticks between volleys
ULT_DURATION    = VOLLEY_INTERVAL * (VOLLEY_COUNT - 1)   # 72 ticks
_ANGLES_DEG     = (-6.0, -3.0, 0.0, 3.0, 6.0)


def activate_mercury(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player or player.mercury_start_tick >= 0:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux = aim_x / length
    uy = aim_y / length
    player.mercury_aim_x       = ux
    player.mercury_aim_y       = uy
    player.mercury_start_tick  = state.tick
    player.mercury_volley_fired = 0
    player.aim_angle = math.degrees(math.atan2(ux, -uy))
    _fire_volley(state, player)


def _fire_volley(state, player) -> None:
    ux, uy = player.mercury_aim_x, player.mercury_aim_y
    for deg in _ANGLES_DEG:
        rad   = math.radians(deg)
        cos_d = math.cos(rad)
        sin_d = math.sin(rad)
        rx = ux * cos_d - uy * sin_d
        ry = ux * sin_d + uy * cos_d
        state._spawn_bullet(player.id, rx, ry, spread_override=0.0)
    player.mercury_volley_fired += 1


def step_mercury(state) -> None:
    for player in state.players.values():
        if player.mercury_start_tick < 0:
            continue
        if state.tick < player.stun_until:
            player.mercury_start_tick   = -1
            player.mercury_volley_fired = 0
            continue
        elapsed     = state.tick - player.mercury_start_tick
        volleys_due = elapsed // VOLLEY_INTERVAL + 1
        while (player.mercury_volley_fired < volleys_due
               and player.mercury_volley_fired < VOLLEY_COUNT):
            _fire_volley(state, player)
        if elapsed >= ULT_DURATION and player.mercury_volley_fired >= VOLLEY_COUNT:
            player.mercury_start_tick    = -1
            player.mercury_volley_fired  = 0
