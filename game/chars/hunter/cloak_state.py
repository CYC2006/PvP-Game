"""Sniper R — Phantom Cloak（幻影隱身）

持續 3 秒（180 tick）。
每個週期 30 tick = 24 tick 隱身 + 6 tick 現形。
共 6 個週期，形成「出現→消失→出現→消失」迷蹤效果。

phase_of(remaining) -> 'hidden' | 'revealed'
  remaining = cloak_until - current_tick（剩餘 tick 數）
"""

CLOAK_TICKS  = 180   # 3 秒
CLOAK_CYCLE  = 30    # 一個週期長度
CLOAK_HIDDEN = 24    # 每週期中隱身的 tick 數
CLOAK_SHOW   = 6     # 每週期中現形的 tick 數


def activate_cloak(state, owner_id: int) -> None:
    """按下 R：啟動隱身。若已在隱身中則忽略。"""
    player = state.players.get(owner_id)
    if player is None:
        return
    if player.cloak_until > state.tick:
        return   # 隱身進行中，不重疊
    # +1 使 cloak_until > tick 恰好覆蓋完整 CLOAK_TICKS 個遊戲 tick
    player.cloak_until = state.tick + CLOAK_TICKS + 1


def phase_of(cloak_until: int, tick: int) -> str:
    """回傳當前隱身階段。
    'inactive' : 隱身未啟動或已結束
    'hidden'   : 隱身中（對手看不見）
    'revealed' : 閃現中（對手半透明可見）
    """
    if cloak_until <= tick:
        return 'inactive'
    remaining   = cloak_until - tick           # 1 ~ CLOAK_TICKS
    elapsed     = CLOAK_TICKS - remaining      # 已過 tick
    cycle_pos   = elapsed % CLOAK_CYCLE        # 0 ~ CLOAK_CYCLE-1
    if cycle_pos < CLOAK_HIDDEN:
        return 'hidden'
    return 'revealed'
