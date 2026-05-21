"""Poisoner E — 毒素共鳴（server-only）

- 持續 3 秒（180 tick）
- 每 30 tick 釋放一次綠色衝擊波（不再需要站在毒液池上）
- 衝擊波：半徑 60→400，歷時 0.6 秒（36 tick），命中對手 3 點傷害 + 毒素層數 +1
- 衝擊波命中對手時：自己回復 3 × 對手當前毒素層數 HP
- 最多 6 次，冷卻 10 秒（由 chars.csv cd_e=10）
"""
from game.chars.pioneer.shield_state import _start_shockwave
from game.chars.poisoner.poison_stack_state import add_poison_stack

E_TICKS          = 180   # 3s × 60 fps
CHECK_INTERVAL   = 30    # ticks between pool-standing checks
MAX_CHECKS       = 6

SW_START_R       = 60
SW_END_R         = 400
SW_DURATION      = 36    # ticks (0.6s)
SW_DAMAGE        = 3
HEAL_PER_STACK   = 3


def activate_poisoner_e(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    player.poisoner_e_until          = state.tick + E_TICKS
    player.poisoner_e_last_check_tick = state.tick - CHECK_INTERVAL  # 啟動後立即首次檢查
    player.poisoner_e_check_count    = 0


def step_poisoner_e(state) -> None:
    for pid, player in state.players.items():
        if player.char_name != 'Poisoner':
            continue
        if player.poisoner_e_until < 0:
            continue
        if state.tick > player.poisoner_e_until:
            player.poisoner_e_until = -1
            continue
        if player.poisoner_e_check_count >= MAX_CHECKS:
            continue
        if state.tick - player.poisoner_e_last_check_tick < CHECK_INTERVAL:
            continue

        player.poisoner_e_last_check_tick = state.tick
        player.poisoner_e_check_count    += 1

        # 釋放衝擊波（無暈眩、無擊退；命中時造成傷害、疊毒、回血）
        _start_shockwave(
            state, pid,
            start_r=SW_START_R,
            end_r=SW_END_R,
            duration_ticks=SW_DURATION,
            stun_ticks=0,
            kb_force=0.0,
            damage=SW_DAMAGE,
            poison_src='e',
            heal_per_stack=HEAL_PER_STACK,
            cx=player.x,
            cy=player.y,
        )

        # 遞增 seq 讓 client FX 偵測
        player.poisoner_e_shockwave_seq = (player.poisoner_e_shockwave_seq + 1) % 256
