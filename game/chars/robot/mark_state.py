import math

MARK_TICKS = 180   # 3 秒（60 tick/s）


def activate_robot_space(state, owner_id: int) -> None:
    """第一次 Space：在當前位置建立印記。
    第二次 Space（印記有效時）：傳送回印記位置並清除印記。
    """
    from game.state import RobotMark
    player = state.players.get(owner_id)
    if not player:
        return

    mark = state.robot_marks.get(owner_id)
    if mark is not None and state.tick - mark.spawn_tick < MARK_TICKS:
        # ── 回傳傳送 ──────────────────────────────────
        player.x = mark.x
        player.y = mark.y
        del state.robot_marks[owner_id]
    else:
        # ── 建立印記 ──────────────────────────────────
        state.robot_marks[owner_id] = RobotMark(
            owner_id=owner_id,
            x=player.x,
            y=player.y,
            spawn_tick=state.tick,
        )


def step_robot_marks(state) -> None:
    """每 tick 清除已過期的印記。"""
    expired = [
        oid for oid, m in state.robot_marks.items()
        if state.tick - m.spawn_tick >= MARK_TICKS
    ]
    for oid in expired:
        del state.robot_marks[oid]
