import math
from game.state import GameState, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS

JUMP_TICKS    = 30       # 0.5 s @ 60 fps
JUMP_DISTANCE = 150.0
_JUMP_SPEED   = JUMP_DISTANCE / JUMP_TICKS   # 5.0 px / tick


def activate_jump(state: GameState, owner_id: int,
                  aim_x: float, aim_y: float) -> None:
    """按下 Space：設定跳躍方向並記錄起跳 tick。"""
    player = state.players.get(owner_id)
    if player is None or player.jump_tick >= 0:
        return          # 已在跳躍中，忽略
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return          # 沒有瞄準方向，忽略
    player.jump_dx   = aim_x / length
    player.jump_dy   = aim_y / length
    player.jump_tick = state.tick


def step_jumps(state: GameState) -> None:
    """每 tick 推進所有玩家的跳躍狀態。
    落地 tick 清除 jump_tick（下一步 resolve_player_collisions 會推出障礙物）。
    """
    for player in state.players.values():
        if player.jump_tick < 0:
            continue
        age = state.tick - player.jump_tick
        if age <= JUMP_TICKS:
            # 在空中：以固定速度朝跳躍方向移動（含第 JUMP_TICKS tick 以補足一幀的偏移）
            player.x = max(PLAYER_RADIUS,
                           min(MAP_WIDTH  - PLAYER_RADIUS,
                               player.x + player.jump_dx * _JUMP_SPEED))
            player.y = max(PLAYER_RADIUS,
                           min(MAP_HEIGHT - PLAYER_RADIUS,
                               player.y + player.jump_dy * _JUMP_SPEED))
        else:
            # 落地：解除跳躍，下一步 resolve_player_collisions 推出障礙物
            player.jump_tick = -1
