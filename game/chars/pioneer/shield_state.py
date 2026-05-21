"""Soldier E — 防護罩 Force Shield

以玩家為圓心建立 60px 防護罩，持續 5 秒（300 tick）。
- HP：120；各類傷害優先扣防護罩，超過護盾血量不溢傷到玩家
- 防護罩消失時（破壞或到期）：
    - 釋放衝擊波 FX（60→250px，0.5 秒）
    - 衝擊波圓環「掃過」對手時才觸發：10~15 傷害 + 擊退 + 短暈眩
"""
import math

SHIELD_HP               = 80
SHIELD_DURATION         = 300    # 5 s × 60 fps
SHIELD_RADIUS           = 60     # px
SHIELD_LINGER           = 8      # 破壞後繼續留在 state 的 tick 數（供 client FX 偵測）

SHOCKWAVE_RADIUS        = 350    # 衝擊波最大半徑（與 shield_fx 同步）
SHOCKWAVE_DURATION_TICKS = 30   # 0.5 s × 60 fps
SHOCKWAVE_KB_FORCE      = 10.0   # px/tick（robot 為 18）
SHOCKWAVE_STUN_TICKS    = 30     # 0.5 s（robot 為 60 = 1 s）


def _start_shockwave(state, owner_id: int, *,
                     start_r: float = SHIELD_RADIUS,
                     end_r: float = SHOCKWAVE_RADIUS,
                     duration_ticks: int = SHOCKWAVE_DURATION_TICKS,
                     stun_ticks: int = SHOCKWAVE_STUN_TICKS,
                     kb_force: float = SHOCKWAVE_KB_FORCE,
                     pull_source_id: int = -1,
                     pull_speed: float = 0.0,
                     damage: int = 0,
                     poison_src: str = '',
                     heal_per_stack: int = 0,
                     cx: float = None, cy: float = None) -> None:
    """記錄衝擊波起始資訊，由 step_shockwaves 每 tick 追蹤圓環位置。
    cx/cy 可選覆寫起始座標（預設取 owner 當前位置）。
    damage/poison_src：支援純傷害型衝擊波（無暈眩/擊退）。
    """
    if cx is None or cy is None:
        player = state.players.get(owner_id)
        if player is None:
            return
        cx = player.x
        cy = player.y
    state._pending_shockwaves.append({
        'owner_id':       owner_id,
        'cx':             cx,
        'cy':             cy,
        'start_tick':     state.tick,
        'hit_done':       False,
        'start_r':        start_r,
        'end_r':          end_r,
        'duration_ticks': duration_ticks,
        'stun_ticks':     stun_ticks,
        'kb_force':       kb_force,
        'pull_source_id': pull_source_id,
        'pull_speed':     pull_speed,
        'damage':         damage,
        'poison_src':     poison_src,
        'heal_per_stack': heal_per_stack,
    })


def step_shockwaves(state) -> None:
    """每 tick 推進圓環半徑，圓環首次覆蓋到對手時觸發效果。
    每個衝擊波 dict 可攜帶自訂參數，預設退回護盾衝擊波常數。
    """
    still_active = []
    for sw in state._pending_shockwaves:
        dur = sw.get('duration_ticks', SHOCKWAVE_DURATION_TICKS)
        t   = state.tick - sw['start_tick']
        if t > dur:
            continue   # 衝擊波已結束，丟棄
        still_active.append(sw)

        if sw['hit_done']:
            continue

        # 讀取此衝擊波的自訂參數
        s_r        = sw.get('start_r',    SHIELD_RADIUS)
        e_r        = sw.get('end_r',      SHOCKWAVE_RADIUS)
        stun_ticks = sw.get('stun_ticks', SHOCKWAVE_STUN_TICKS)
        kb_force   = sw.get('kb_force',   SHOCKWAVE_KB_FORCE)

        # 當前圓環半徑（線性擴張）
        frac   = t / dur
        ring_r = s_r + (e_r - s_r) * frac

        owner_id    = sw['owner_id']
        opponent_id = 3 - owner_id
        opp         = state.players.get(opponent_id)
        if opp is None:
            continue

        dist = math.hypot(opp.x - sw['cx'], opp.y - sw['cy'])
        if dist > ring_r:
            continue   # 圓環還沒掃到對手

        # 圓環掃到對手 → 施加效果
        pull_sid = sw.get('pull_source_id', -1)
        pull_spd = sw.get('pull_speed', 0.0)
        dmg      = sw.get('damage', 0)
        psrc     = sw.get('poison_src', '')

        if pull_sid >= 0 and pull_spd > 0:
            opp.pull_source_id = pull_sid
            opp.pull_speed     = pull_spd
        else:
            if kb_force > 0:
                if dist > 0:
                    ux = (opp.x - sw['cx']) / dist
                    uy = (opp.y - sw['cy']) / dist
                else:
                    ux, uy = 1.0, 0.0
                opp.kb_vx = ux * kb_force
                opp.kb_vy = uy * kb_force

        if stun_ticks > 0:
            state.apply_stun(opponent_id, stun_ticks)
        if dmg > 0:
            state.apply_damage(opponent_id, dmg)
        if psrc:
            from game.chars.poisoner.poison_stack_state import add_poison_stack
            add_poison_stack(state, opponent_id, psrc)
        heal_ps = sw.get('heal_per_stack', 0)
        if heal_ps > 0 and opp.poison_stacks > 0:
            owner_p = state.players.get(owner_id)
            if owner_p:
                owner_p.hp = min(owner_p.max_hp, owner_p.hp + heal_ps * opp.poison_stacks)
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
