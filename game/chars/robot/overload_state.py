"""Robot RMB — 超載（server-only）

- 移速 ×2，持續 3 秒（180 tick）
- 純粹的速度增益，無其他附加效果
- 冷卻 10 秒（由 chars.csv cd_rmb=10）
"""

OVERLOAD_TICKS = 180   # 3s × 60 fps
OVERLOAD_MULT  = 2.0


def activate_overload(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if player is None:
        return
    player.speed_boost_ticks = OVERLOAD_TICKS
    player.speed_boost_mult  = OVERLOAD_MULT
