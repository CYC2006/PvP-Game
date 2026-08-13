"""Robot 普攻 — 自動鎖定雷射（server-only）

- 以 Robot 為圓心，半徑 300 px 的偵測範圍；左鍵對 Robot 無效，普攻完全自動。
- 範圍內有敵人時，每 fire_interval（沿用 chars.csv 的 Robot fire_interval）自動
  發射一發雷射朝該敵人；子彈的追蹤邏輯在 GameState._home_robot_laser 處理。
"""
import math

ATTACK_RADIUS = 300.0   # px


def step_robot_auto_attack(state) -> None:
    for pid, player in state.players.items():
        if player.char_name != 'Robot':
            continue
        if state.tick - player.robot_auto_last_tick < player.fire_interval_ticks:
            continue
        opponent_id = 3 - pid
        opp = state.players.get(opponent_id)
        if opp is None:
            continue
        dx = opp.x - player.x
        dy = opp.y - player.y
        if math.hypot(dx, dy) > ATTACK_RADIUS:
            continue
        player.robot_auto_last_tick = state.tick
        state._spawn_bullet(pid, dx, dy, spread_override=0.0)
