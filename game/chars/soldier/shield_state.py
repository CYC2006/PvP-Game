"""Soldier E — 防護罩 Force Shield

以玩家為圓心建立 60px 防護罩，持續 5 秒（300 tick）。
- HP：120；各類傷害優先扣防護罩，超過護盾血量不溢傷到玩家
- 防護罩消失時（破壞或到期）：
    - 釋放衝擊波 FX（60→250px，0.5 秒）
    - 衝擊波圓環「掃過」對手時才觸發：10~15 傷害 + 擊退 + 短暈眩
"""
import math
import random

SHIELD_HP               = 80
SHIELD_DURATION         = 300    # 5 s × 60 fps
SHIELD_RADIUS           = 60     # px
SHIELD_LINGER           = 8      # 破壞後繼續留在 state 的 tick 數（供 client FX 偵測）

SHOCKWAVE_RADIUS        = 250    # 衝擊波最大半徑（與 shield_fx 同步）
SHOCKWAVE_DURATION_TICKS = 30   # 0.5 s × 60 fps
SHOCKWAVE_DMG_MIN       = 10
SHOCKWAVE_DMG_MAX       = 15
SHOCKWAVE_KB_FORCE      = 10.0   # px/tick（robot 為 18）
SHOCKWAVE_STUN_TICKS    = 30     # 0.5 s（robot 為 60 = 1 s）


def _start_shockwave(state, owner_id: int) -> None:
    """記錄衝擊波起始資訊，由 step_shockwaves 每 tick 追蹤圓環位置。"""
    player = state.players.get(owner_id)
    if player is None:
        return
    state._pending_shockwaves.append({
        'owner_id':   owner_id,
        'cx':         player.x,
        'cy':         player.y,
        'start_tick': state.tick,
        'hit_done':   False,
    })


def step_shockwaves(state) -> None:
    """每 tick 推進圓環半徑，圓環首次覆蓋到對手時觸發效果。"""
    still_active = []
    for sw in state._pending_shockwaves:
        t = state.tick - sw['start_tick']
        if t > SHOCKWAVE_DURATION_TICKS:
            continue   # 衝擊波已結束，丟棄
        still_active.append(sw)

        if sw['hit_done']:
            continue

        # 當前圓環半徑（線性擴張）
        frac   = t / SHOCKWAVE_DURATION_TICKS
        ring_r = SHIELD_RADIUS + (SHOCKWAVE_RADIUS - SHIELD_RADIUS) * frac

        owner_id    = sw['owner_id']
        opponent_id = 3 - owner_id
        opp         = state.players.get(opponent_id)
        if opp is None:
            continue

        dist = math.hypot(opp.x - sw['cx'], opp.y - sw['cy'])
        if dist > ring_r:
            continue   # 圓環還沒掃到對手

        # 圓環掃到對手 → 施加效果
        damage = random.randint(SHOCKWAVE_DMG_MIN, SHOCKWAVE_DMG_MAX)
        state.apply_damage(opponent_id, damage)

        if dist > 0:
            ux = (opp.x - sw['cx']) / dist
            uy = (opp.y - sw['cy']) / dist
        else:
            ux, uy = 1.0, 0.0
        opp.kb_vx = ux * SHOCKWAVE_KB_FORCE
        opp.kb_vy = uy * SHOCKWAVE_KB_FORCE

        opp.stun_until = max(
            opp.stun_until if opp.stun_until > state.tick else state.tick,
            state.tick + SHOCKWAVE_STUN_TICKS,
        )
        sw['hit_done'] = True

    state._pending_shockwaves = still_active


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
            if state.tick - shield.broken_tick >= SHIELD_LINGER:
                to_remove.append(oid)
        else:
            age = state.tick - shield.spawn_tick
            if age >= SHIELD_DURATION:
                shield.broken_tick = state.tick
                _start_shockwave(state, oid)   # 到期也啟動衝擊波環
    for oid in to_remove:
        state.shields.pop(oid, None)
