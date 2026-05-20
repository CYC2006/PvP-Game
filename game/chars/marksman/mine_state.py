import math
from game.state import Mine

TRIGGER_RADIUS = 60.0
FUSE_TICKS     = 30    # 0.5s × 60 fps
EXPL_RADIUS    = 120.0
EXPL_DMG_MIN   = 10
EXPL_DMG_MAX   = 50


def place_mine(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    mid = state._next_mine_id
    state._next_mine_id = (state._next_mine_id + 1) % 256
    state.mines[mid] = Mine(id=mid, owner_id=owner_id, x=player.x, y=player.y)


def step_mines(state) -> None:
    to_remove = []
    for mid, mine in state.mines.items():
        opponent_id = 3 - mine.owner_id
        opp = state.players.get(opponent_id)

        if mine.triggered_tick >= 0:
            age = state.tick - mine.triggered_tick
            if age >= FUSE_TICKS:
                if opp:
                    dist = math.hypot(opp.x - mine.x, opp.y - mine.y)
                    if dist <= EXPL_RADIUS:
                        t      = dist / EXPL_RADIUS
                        damage = int(EXPL_DMG_MIN
                                     + (EXPL_DMG_MAX - EXPL_DMG_MIN) * (1 - t) * (1 - t))
                        if opp.giant_tick >= 0:
                            damage = int(damage * 0.8)
                        state.apply_damage(opponent_id, damage)
                to_remove.append(mid)
        else:
            if opp:
                dist = math.hypot(opp.x - mine.x, opp.y - mine.y)
                if dist <= TRIGGER_RADIUS:
                    mine.triggered_tick = state.tick

    for mid in to_remove:
        state.mines.pop(mid, None)
