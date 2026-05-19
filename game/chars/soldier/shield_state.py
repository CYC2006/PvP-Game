"""Soldier E — 防護罩 Force Shield

以玩家為圓心建立 80px 防護罩，持續 5 秒（300 tick）。
- HP：120；各類傷害優先扣防護罩，超過護盾血量不溢傷到玩家
- 防護罩消失時（破壞或到期）釋放衝擊波
"""

SHIELD_HP       = 120
SHIELD_DURATION = 300    # 5 s × 60 fps
SHIELD_RADIUS   = 80     # px
SHIELD_LINGER   = 8      # 破壞後繼續留在 state 的 tick 數（供 client FX 偵測）


def activate_shield(state, owner_id: int) -> None:
    """建立（或更新）防護罩；舊的直接替換。"""
    from game.state import Shield
    state.shields[owner_id] = Shield(
        owner_id=owner_id,
        hp=SHIELD_HP,
        max_hp=SHIELD_HP,
        spawn_tick=state.tick,
    )


def step_shields(state) -> None:
    """每 tick 更新：超時自動破壞，並清除已 linger 完的殘留。"""
    to_remove = []
    for oid, shield in list(state.shields.items()):
        if shield.broken_tick >= 0:
            # 已破壞：等 linger 結束後移除
            if state.tick - shield.broken_tick >= SHIELD_LINGER:
                to_remove.append(oid)
        else:
            # 存活中：檢查是否超時
            age = state.tick - shield.spawn_tick
            if age >= SHIELD_DURATION:
                shield.broken_tick = state.tick
    for oid in to_remove:
        state.shields.pop(oid, None)
