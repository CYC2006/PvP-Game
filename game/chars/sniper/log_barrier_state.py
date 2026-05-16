import math
from game.state import LogBarrier

HP     = 60
RADIUS = 18.0
DIST   = 80.0


def activate_log_barriers(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    # 移除此玩家舊有的木頭障礙物
    for lid in [k for k, lb in state.log_barriers.items() if lb.owner_id == owner_id]:
        state.log_barriers.pop(lid)
    ux, uy = aim_x / length, aim_y / length
    for angle_offset in (0.0, math.radians(-45), math.radians(45)):
        ca, sa = math.cos(angle_offset), math.sin(angle_offset)
        dx = ux * ca - uy * sa
        dy = ux * sa + uy * ca
        lid = state._next_log_id
        state._next_log_id = (state._next_log_id + 1) % 256
        state.log_barriers[lid] = LogBarrier(
            id=lid, owner_id=owner_id,
            x=player.x + dx * DIST,
            y=player.y + dy * DIST,
            hp=HP,
            radius=RADIUS,
        )
