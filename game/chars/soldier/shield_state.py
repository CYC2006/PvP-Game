"""Soldier E — 防護罩 Force Shield

以玩家為圓心建立 60px 防護罩，持續 5 秒（300 tick）。
- HP：120；各類傷害優先扣防護罩，超過護盾血量不溢傷到玩家
- 防護罩消失時（破壞或到期）：
    - 釋放衝擊波（FX，半徑 0→200px）
    - 對範圍內對手造成 10~15 傷害 + 擊退 + 短暈眩
"""
import math
import random

SHIELD_HP            = 120
SHIELD_DURATION      = 300    # 5 s × 60 fps
SHIELD_RADIUS        = 60     # px
SHIELD_LINGER        = 8      # 破壞後繼續留在 state 的 tick 數（供 client FX 偵測）

SHOCKWAVE_DMG_MIN    = 10
SHOCKWAVE_DMG_MAX    = 15
SHOCKWAVE_RADIUS     = 200    # 與 shield_fx.py 的 SHOCKWAVE_MAX_R 一致
SHOCKWAVE_KB_FORCE   = 10.0   # px/tick（robot 為 18，縮短距離）
SHOCKWAVE_STUN_TICKS = 30     # 0.5 s 暈眩（robot 為 60 = 1 s）


def _apply_shockwave_effects(state, owner_id: int) -> None:
    """護盾破壞/到期時立即對附近對手施加傷害、擊退、暈眩。"""
    player = state.players.get(owner_id)
    if player is None:
        return
    opponent_id = 3 - owner_id
    opp = state.players.get(opponent_id)
    if opp is None:
        return

    dist = math.hypot(opp.x - player.x, opp.y - player.y)
    if dist > SHOCKWAVE_RADIUS or dist == 0:
        return

    # 傷害（透過 apply_damage，也可被對手的護盾吸收）
    damage = random.randint(SHOCKWAVE_DMG_MIN, SHOCKWAVE_DMG_MAX)
    state.apply_damage(opponent_id, damage)

    # 擊退方向：由護盾中心向外推
    ux = (opp.x - player.x) / dist
    uy = (opp.y - player.y) / dist
    opp.kb_vx = ux * SHOCKWAVE_KB_FORCE
    opp.kb_vy = uy * SHOCKWAVE_KB_FORCE

    # 短暫暈眩
    opp.stun_until = max(
        opp.stun_until if opp.stun_until > state.tick else state.tick,
        state.tick + SHOCKWAVE_STUN_TICKS,
    )


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
                _apply_shockwave_effects(state, oid)   # 到期衝擊波
    for oid in to_remove:
        state.shields.pop(oid, None)
