import math
import random
from game.state import AirStrike

WAIT_TICKS   = 60
BOMB_TICKS   = 120
TOTAL_TICKS  = 180
RADIUS       = 100.0
MAX_RANGE    = 300.0
DMG_MIN      = 10
DMG_MAX      = 15
DMG_INTERVAL = 6


def activate_airstrike(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    dist = math.hypot(aim_x, aim_y)
    if dist > MAX_RANGE and dist > 0:
        scale  = MAX_RANGE / dist
        aim_x *= scale
        aim_y *= scale
    aid = state._next_airstrike_id
    state._next_airstrike_id = (state._next_airstrike_id + 1) % 256
    state.air_strikes[aid] = AirStrike(
        id=aid, owner_id=owner_id,
        cx=player.x + aim_x, cy=player.y + aim_y,
        spawn_tick=state.tick,
    )


def step_air_strikes(state) -> None:
    to_remove = []
    for aid, strike in state.air_strikes.items():
        age = state.tick - strike.spawn_tick
        if age > TOTAL_TICKS:
            to_remove.append(aid)
            continue
        if age >= WAIT_TICKS:
            bomb_age = age - WAIT_TICKS
            if bomb_age % DMG_INTERVAL == 0:
                opponent_id = 3 - strike.owner_id
                opponent    = state.players.get(opponent_id)
                if opponent:
                    dist = math.hypot(opponent.x - strike.cx, opponent.y - strike.cy)
                    if dist < RADIUS:
                        dmg = random.randint(DMG_MIN, DMG_MAX)
                        if opponent.giant_tick >= 0:
                            dmg = int(dmg * 0.8)
                        state.apply_damage(opponent_id, dmg)
    for aid in to_remove:
        state.air_strikes.pop(aid, None)
