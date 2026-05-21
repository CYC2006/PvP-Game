"""Poisoner Space — 毒素疾走（server-only）

- 持續 3 秒（180 tick），移速 +20%，殘影效果（client 透過 speed_boost_end_ms 呈現）
- 每 20 tick 在腳下生成一個小毒液池（半徑 20~30），最多 9 個
- 小池存活 5 秒（300 tick），冷卻 8 秒（由 chars.csv cd_space=8）
"""
import random
from game.chars.poisoner.poison_pool_state import create_small_poison_pool

SPACE_TICKS    = 180   # 3s × 60 fps
POOL_INTERVAL  = 20    # ticks between small pool spawns
MAX_POOLS      = 9


def activate_poisoner_space(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    player.speed_boost_ticks          = SPACE_TICKS
    player.speed_boost_mult           = 1.2
    player.poisoner_space_until       = state.tick + SPACE_TICKS
    player.poisoner_space_last_pool_tick = state.tick - POOL_INTERVAL  # 第一個小池立即生成
    player.poisoner_space_pool_count  = 0


def step_poisoner_space(state) -> None:
    for pid, player in state.players.items():
        if player.char_name != 'Poisoner':
            continue
        if player.poisoner_space_until < 0:
            continue
        if state.tick > player.poisoner_space_until:
            player.poisoner_space_until = -1
            continue
        if player.poisoner_space_pool_count >= MAX_POOLS:
            continue
        if state.tick - player.poisoner_space_last_pool_tick >= POOL_INTERVAL:
            radius = random.uniform(20.0, 30.0)
            create_small_poison_pool(state, player.x, player.y, pid, radius)
            player.poisoner_space_last_pool_tick = state.tick
            player.poisoner_space_pool_count    += 1
