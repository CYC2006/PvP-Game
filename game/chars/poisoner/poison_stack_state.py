"""Poisoner — 毒素層數系統（server-only）

規則：
- 最大 5 層；各來源獨立上限（normal=1, rmb=2, space_pool=2, e=2）
- 每秒造成 3×層數 傷害（60 tick 一次）
- 3 秒無毒素傷害 → 層數歸 0、計時器重置
- 任何毒素傷害命中 → 計時器刷新（即使未增加層數）
"""

STACK_MAX         = 5
STACK_DECAY_TICKS = 180   # 3s × 60 fps

_SRC_CAPS = {
    'normal':     1,
    'rmb':        2,
    'space_pool': 2,
    'e':          2,
}
_SRC_ATTRS = {
    'normal':     '_poison_src_normal',
    'rmb':        '_poison_src_rmb',
    'space_pool': '_poison_src_space_pool',
    'e':          '_poison_src_e',
}


def add_poison_stack(state, victim_id: int, source: str) -> None:
    """嘗試從指定來源新增一層毒素，並刷新計時器。"""
    victim = state.players.get(victim_id)
    if victim is None:
        return
    victim._poison_last_tick = state.tick   # 總是刷新計時器

    cap  = _SRC_CAPS.get(source, 0)
    attr = _SRC_ATTRS.get(source)
    if not cap or attr is None:
        return
    if getattr(victim, attr, 0) >= cap:
        return   # 此來源已達上限
    if victim.poison_stacks >= STACK_MAX:
        return   # 全域上限
    setattr(victim, attr, getattr(victim, attr, 0) + 1)
    victim.poison_stacks += 1


def _reset_stacks(player) -> None:
    player.poison_stacks          = 0
    player._poison_last_tick      = -1
    player._poison_stk_dmg_timer  = 0
    player._poison_src_normal     = 0
    player._poison_src_rmb        = 0
    player._poison_src_space_pool = 0
    player._poison_src_e          = 0


def step_poison_stacks(state) -> None:
    """每 tick 執行：衰退檢查 + 每秒被動傷害。"""
    for pid, player in state.players.items():
        if player.poison_stacks <= 0:
            continue
        if (player._poison_last_tick >= 0
                and state.tick - player._poison_last_tick >= STACK_DECAY_TICKS):
            _reset_stacks(player)
            continue
        player._poison_stk_dmg_timer += 1
        if player._poison_stk_dmg_timer >= 60:
            player._poison_stk_dmg_timer = 0
            state.apply_damage(pid, 3 * player.poison_stacks)
