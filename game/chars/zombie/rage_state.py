"""Zombie E — 嗜血 Bloodlust

按下 E 立即進入 4 秒嗜血狀態，不僵直、可正常移動/射擊/使用其他技能。
期間效果分開獨立同步生效：
- 減傷：所受一切傷害（apply_damage 內套用）無條件捨去減半。
- 吸血：普攻（血刃 blade arc）造成的傷害有一半無條件捨去回復自身血量，
  滿血時 min(max_hp, ...) 封頂自然不生效，技能傷害不觸發。
"""

DURATION_TICKS = 240   # 4s × 60fps


def activate_rage(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player or player.zombie_rage_tick >= 0:
        return
    player.zombie_rage_tick = state.tick


def step_rage(state) -> None:
    for player in state.players.values():
        if player.zombie_rage_tick < 0:
            continue
        if state.tick - player.zombie_rage_tick >= DURATION_TICKS:
            player.zombie_rage_tick = -1
