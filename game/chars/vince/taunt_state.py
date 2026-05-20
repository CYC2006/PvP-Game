"""Vince Space — 嘲諷 (Taunt)

按下 Space 後釋放 60→500 px 衝擊波（0.8 秒）：
- 擊中對手：暈眩 0.5 秒 + 被 120 px/s 等速吸引向 Vince
- 衝擊波視覺：薰衣草色（由 taunt_fx 處理）
"""
from game.state import GameState

_SW_START_R   = 60
_SW_END_R     = 500
_SW_DUR_TICKS = 48    # 0.8 s × 60 fps
_SW_STUN      = 30    # 0.5 s × 60 fps
_PULL_SPEED   = 2.0   # 120 px/s ÷ 60 fps = 2.0 px/tick


def activate_vince_taunt(state: GameState, owner_id: int) -> None:
    """按下 Space：標記嘲諷開始並觸發衝擊波。"""
    player = state.players.get(owner_id)
    if player is None or player.vince_taunt_tick >= 0:
        return
    player.vince_taunt_tick = state.tick
    from game.chars.pioneer.shield_state import _start_shockwave
    _start_shockwave(state, owner_id,
                     start_r=_SW_START_R,
                     end_r=_SW_END_R,
                     duration_ticks=_SW_DUR_TICKS,
                     stun_ticks=_SW_STUN,
                     kb_force=0.0,
                     pull_source_id=owner_id,
                     pull_speed=_PULL_SPEED)


def step_vince_taunt(state: GameState) -> None:
    """清除已過期的嘓諷狀態，供客戶端 FX 偵測結束。"""
    for player in state.players.values():
        if player.vince_taunt_tick < 0:
            continue
        if state.tick - player.vince_taunt_tick > _SW_DUR_TICKS:
            player.vince_taunt_tick = -1
