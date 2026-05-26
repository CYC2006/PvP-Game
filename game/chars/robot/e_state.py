import math
import random

from game.state import PLAYER_RADIUS, MAP_WIDTH, MAP_HEIGHT

RING_TICKS   = 60    # 1 second fade
E_MARK_TICKS = 240   # 4 seconds rotation
E_RING_R     = 200   # pixels
STUN_TICKS   = 60    # 1 second

_CARDINAL_ANGLES = [0, 90, 180, 270]


def activate_robot_e(state, owner_id: int) -> None:
    from game.state import RobotEMark, RobotERing

    player = state.players.get(owner_id)
    if not player:
        return

    # ── Second press: teleport to rotating mark ──────────────────────
    e_mark = state.robot_e_marks.get(owner_id)
    if e_mark is not None and state.tick - e_mark.spawn_tick < E_MARK_TICKS:
        elapsed   = state.tick - e_mark.spawn_tick
        angle_rad = math.radians(e_mark.start_angle) + 2 * math.pi * (elapsed / E_MARK_TICKS)
        player.x  = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS,
                                           e_mark.center_x + E_RING_R * math.cos(angle_rad)))
        player.y  = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS,
                                           e_mark.center_y + E_RING_R * math.sin(angle_rad)))
        del state.robot_e_marks[owner_id]
        return

    # ── First press: ring + stun + maybe create rotating mark ────────
    state.robot_e_rings[owner_id] = RobotERing(
        owner_id=owner_id, x=player.x, y=player.y, spawn_tick=state.tick)

    # ── 消除範圍內的普攻子彈（Zombie 普攻除外）────────────────────────
    _clear_normal_bullets(state, player.x, player.y, E_RING_R)

    opponent_id = 3 - owner_id
    opp = state.players.get(opponent_id)
    if opp and math.hypot(opp.x - player.x, opp.y - player.y) < E_RING_R:
        state.apply_stun(opponent_id, STUN_TICKS)

    # Block if Space mark is active
    from game.chars.robot.mark_state import MARK_TICKS
    space_mark = state.robot_marks.get(owner_id)
    if space_mark is not None and state.tick - space_mark.spawn_tick < MARK_TICKS:
        return

    state.robot_e_marks[owner_id] = RobotEMark(
        owner_id=owner_id,
        center_x=player.x,
        center_y=player.y,
        start_angle=random.choice(_CARDINAL_ANGLES),
        spawn_tick=state.tick,
    )


def _clear_normal_bullets(state, cx: float, cy: float, radius: float) -> None:
    """刪除以 (cx, cy) 為圓心、radius 範圍內的普攻子彈。
    bullet_type == 0：一般普攻（所有角色，除 Zombie 外）
    bullet_type == 9：Robot 雷射普攻（不在消除範圍內，由 Robot 自己放出）
    Zombie 的普攻（char_name == 'Zombie'）刻意保留，不被消除。
    """
    to_del = []
    for bid, b in state.bullets.items():
        if b.bullet_type != 0:          # 只處理一般普攻（type 0）
            continue
        owner = state.players.get(b.owner_id)
        if owner and owner.char_name == 'Zombie':
            continue                    # Zombie 普攻不消除
        if math.hypot(b.x - cx, b.y - cy) < radius:
            to_del.append(bid)
    for bid in to_del:
        state.bullets.pop(bid, None)


def step_robot_e(state) -> None:
    for oid in [k for k, m in state.robot_e_marks.items()
                if state.tick - m.spawn_tick >= E_MARK_TICKS]:
        del state.robot_e_marks[oid]
    for oid in [k for k, r in state.robot_e_rings.items()
                if state.tick - r.spawn_tick >= RING_TICKS]:
        del state.robot_e_rings[oid]
