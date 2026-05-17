import math
from game.state import PLAYER_RADIUS, MAP_WIDTH, MAP_HEIGHT

PUSH_WIND_UP  = 6      # ticks: 按下到觸發（約 0.1s）
PUSH_ACTIVE   = 15     # ticks: 觸發後矩形視覺持續時間
PUSH_WIDTH    = 100.0  # px，垂直方向（左右各 50）
PUSH_HEIGHT   = 160.0  # px，朝滑鼠方向
STUN_TICKS    = 60     # 1 秒暈眩
KB_FORCE      = 18.0   # 初速 px/tick；中間（80 px）約 12 tick 飛出矩形外
KB_DECAY      = 0.78   # 每 tick 速度乘數


def _in_rect(px: float, py: float,
             ox: float, oy: float,
             fwd_x: float, fwd_y: float,
             right_x: float, right_y: float) -> bool:
    """判斷點 (px, py) 是否在推力矩形內。
    矩形：從 (ox, oy) 沿 fwd 延伸 PUSH_HEIGHT，沿 ±right 各延伸 PUSH_WIDTH/2。
    """
    dx = px - ox
    dy = py - oy
    along = dx * fwd_x + dy * fwd_y
    perp  = dx * right_x + dy * right_y
    return (0.0 <= along <= PUSH_HEIGHT and
            -PUSH_WIDTH / 2 <= perp <= PUSH_WIDTH / 2)


def activate_push(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    from game.state import PushZone
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    angle = math.degrees(math.atan2(aim_y, aim_x))
    pzid = state._next_push_zone_id
    state._next_push_zone_id = (state._next_push_zone_id + 1) % 256
    state.push_zones[pzid] = PushZone(
        id=pzid, owner_id=owner_id,
        x=player.x, y=player.y,
        angle=angle,
        spawn_tick=state.tick,
    )


def step_push_zones(state) -> None:
    to_remove = []
    for pzid, zone in state.push_zones.items():
        age = state.tick - zone.spawn_tick
        if age == PUSH_WIND_UP:
            _apply_push_effect(state, zone)
        if age >= PUSH_WIND_UP + PUSH_ACTIVE:
            to_remove.append(pzid)
    for pzid in to_remove:
        state.push_zones.pop(pzid, None)


def _apply_push_effect(state, zone) -> None:
    angle_rad = math.radians(zone.angle)
    fwd_x  =  math.cos(angle_rad)
    fwd_y  =  math.sin(angle_rad)
    right_x = -fwd_y
    right_y =  fwd_x

    opponent_id = 3 - zone.owner_id
    opp = state.players.get(opponent_id)
    if not opp:
        return
    if _in_rect(opp.x, opp.y, zone.x, zone.y, fwd_x, fwd_y, right_x, right_y):
        opp.kb_vx = fwd_x * KB_FORCE
        opp.kb_vy = fwd_y * KB_FORCE
        opp.stun_until = state.tick + STUN_TICKS
