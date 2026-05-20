"""Zombie Space — 跳躍衝擊（200 px）

以瞄準方向飛躍 200 px，落地時在落點釋放衝擊波
（60→250 px，0.4 秒），對範圍內敵人施加擊退 + 0.4 秒暈眩。
"""
import math
from game.state import GameState, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS

JUMP_TICKS    = 40        # 200 px / 5 px/tick  (~0.67 s)
JUMP_DISTANCE = 200.0
_JUMP_SPEED   = JUMP_DISTANCE / JUMP_TICKS   # 5.0 px/tick

# 落地衝擊波參數（傳給 shield_state._start_shockwave）
_SW_START_R   = 60
_SW_END_R     = 250
_SW_DUR_TICKS = 24    # 0.4 s × 60 fps
_SW_STUN      = 24    # 0.4 s
_SW_KB        = 12.0  # px/tick


def activate_zombie_jump(state: GameState, owner_id: int,
                         aim_x: float, aim_y: float) -> None:
    """按下 Space：設定跳躍方向並記錄起跳 tick。"""
    player = state.players.get(owner_id)
    if player is None or player.zombie_jump_tick >= 0:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    player.zombie_jump_dx   = aim_x / length
    player.zombie_jump_dy   = aim_y / length
    player.zombie_jump_tick = state.tick


def step_zombie_jumps(state: GameState) -> None:
    """每 tick 推進 Zombie 跳躍，落地時觸發衝擊波。"""
    for player in state.players.values():
        if player.zombie_jump_tick < 0:
            continue
        age = state.tick - player.zombie_jump_tick
        if age <= JUMP_TICKS:
            player.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS,
                           player.x + player.zombie_jump_dx * _JUMP_SPEED))
            player.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS,
                           player.y + player.zombie_jump_dy * _JUMP_SPEED))
        else:
            # 落地：記錄落點座標，然後清除跳躍狀態，再觸發衝擊波
            lx, ly = player.x, player.y
            player.zombie_jump_tick = -1
            from game.chars.soldier.shield_state import _start_shockwave
            _start_shockwave(state, player.id,
                             start_r=_SW_START_R,
                             end_r=_SW_END_R,
                             duration_ticks=_SW_DUR_TICKS,
                             stun_ticks=_SW_STUN,
                             kb_force=_SW_KB,
                             cx=lx, cy=ly)
