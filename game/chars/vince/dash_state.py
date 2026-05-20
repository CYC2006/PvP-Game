import math
from game.state import GameState, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS

DASH_TICKS = 60       # 360 px / 6 px/tick  (~1 second)
DASH_SPEED = 6.0
STUN_TICKS = 60       # 1 second @ 60 fps


def activate_dash(state: GameState, owner_id: int,
                  aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if player is None or player.vince_dash_tick >= 0:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    player.vince_dash_dx   = aim_x / length
    player.vince_dash_dy   = aim_y / length
    player.vince_dash_tick = state.tick


def step_vince_dash(state: GameState, obstacles: dict = None) -> None:
    for pid, player in state.players.items():
        if player.vince_dash_tick < 0:
            continue
        age = state.tick - player.vince_dash_tick
        if age > DASH_TICKS:
            player.vince_dash_tick = -1
            continue

        new_x = max(PLAYER_RADIUS,
                    min(MAP_WIDTH  - PLAYER_RADIUS,
                        player.x + player.vince_dash_dx * DASH_SPEED))
        new_y = max(PLAYER_RADIUS,
                    min(MAP_HEIGHT - PLAYER_RADIUS,
                        player.y + player.vince_dash_dy * DASH_SPEED))

        # Stop on intact solid obstacle (skip destroyed and non-solid/trees)
        if obstacles:
            for oid, obs in obstacles.items():
                if not obs.solid:
                    continue
                if oid in state.destroyed_obstacles:
                    continue
                if obs.collides_circle(new_x, new_y, PLAYER_RADIUS):
                    player.vince_dash_tick = -1
                    break

        if player.vince_dash_tick < 0:
            continue

        player.x = new_x
        player.y = new_y

        # Stop on enemy contact and stun them
        for other_id, other in state.players.items():
            if other_id == pid:
                continue
            if math.hypot(player.x - other.x, player.y - other.y) <= PLAYER_RADIUS * 2:
                other.stun_until = state.tick + STUN_TICKS
                player.vince_dash_tick = -1
                break
