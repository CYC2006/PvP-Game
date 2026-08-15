"""Zombie RMB — 體力衝刺 Energy Sprint（server-only）

- 基礎移速 100 px/s（極慢），按住 RMB 才會加速，放開回到基礎速度
- 能量滿值 300：按住 RMB 每 tick -1；放開每 tick +0.5（即每 2 tick +1）
- 加速時的速度依當前能量分級（見 _tier_speed_pxs），能量歸零仍卡在最低檔
  （120 px/s），只是不會再往下扣；放開才開始回能量
- 能量紀錄本身維持 0~300；client 顯示時才 ÷5 無條件捨去（見 renderer.py），
  純粹讓數字/血條看起來不要每 tick 跳動太快，不影響這裡的判定門檻

注意：Player.speed 存的是 px/tick（chars.csv 的 speed_pxs 在 apply_char_stats
時已經 ÷60 換算過），所以這裡的分級數值（px/s，對應設計時給的規格）在指派
給 player.speed 前都要 ÷ _TICK_RATE。
"""

_TICK_RATE = 60

ENERGY_MAX     = 300.0
DRAIN_PER_TICK = 1.0
REGEN_PER_TICK = 0.5   # 每 2 tick 回 1


def _tier_speed_pxs(energy: float) -> float:
    if energy > 240:
        return 300.0
    if energy > 180:
        return 270.0
    if energy > 120:
        return 230.0
    if energy > 60:
        return 180.0
    return 120.0


def step_zombie_sprint(player, rmb_held: bool) -> None:
    if rmb_held:
        player.zombie_energy = max(0.0, player.zombie_energy - DRAIN_PER_TICK)
        player.speed          = _tier_speed_pxs(player.zombie_energy) / _TICK_RATE
    else:
        player.zombie_energy = min(ENERGY_MAX, player.zombie_energy + REGEN_PER_TICK)
        player.speed          = player.zombie_base_speed
