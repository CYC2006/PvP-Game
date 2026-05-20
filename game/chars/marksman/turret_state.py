"""Bear E — 機槍台 Turret

放置於玩家當前位置。
- 偵測半徑 150 px；對手進入後開始射擊
- 子彈屬性與 Bear 普攻完全相同（傷害、速度、散佈）
- HP 消耗：每發子彈 -1；每 30 tick 被動 -1；被敵方普攻擊中扣對應傷害
- HP 歸零時消失（最長壽命：180 × 30 tick = 5400 tick ≈ 90 秒）
"""

import math
import random
from game.state import Bullet

TURRET_RANGE          = 200.0    # 偵測半徑（px）
TURRET_MAX_HP         = 180
TURRET_HITBOX_R       = 14.0     # 機槍台碰撞半徑（px）
TURRET_PASSIVE_DRAIN  = 30       # 被動扣血間隔（tick）
TURRET_FIRE_INTERVAL  = 9        # 射擊間隔（tick，= bear fire_interval 0.15s）

_BULLET_SPEED  = 900.0 / 60      # 15 px/tick
_BULLET_RANGE  = 1000.0
_BULLET_SPREAD = 8.0             # 度（與 bear 普攻相同）


def place_turret(state, owner_id: int) -> None:
    """在玩家當前位置放置機槍台；若同一玩家已有機槍台則先移除舊的。"""
    from game.state import Turret
    player = state.players.get(owner_id)
    if not player:
        return
    # 移除同一擁有者的舊機槍台
    for tid in [t for t, turr in state.turrets.items() if turr.owner_id == owner_id]:
        state.turrets.pop(tid, None)
    tid = state._next_turret_id
    state._next_turret_id = (state._next_turret_id + 1) % 256
    state.turrets[tid] = Turret(id=tid, owner_id=owner_id,
                                 x=player.x, y=player.y)


def step_turrets(state, obstacles: dict = None,
                 obstacle_hp: dict = None) -> None:
    """每 tick 更新所有機槍台。"""
    if obstacles is None:
        obstacles = {}
    to_remove = []

    for tid, turret in list(state.turrets.items()):
        # ── 被動扣血 ────────────────────────────────────────────────────────
        turret._passive_timer += 1
        if turret._passive_timer >= TURRET_PASSIVE_DRAIN:
            turret.hp -= 1
            turret._passive_timer = 0

        if turret.hp <= 0:
            to_remove.append(tid)
            continue

        # ── 偵測對手 ─────────────────────────────────────────────────────────
        enemy_id = 3 - turret.owner_id
        enemy    = state.players.get(enemy_id)
        if enemy is None:
            continue

        dist = math.hypot(enemy.x - turret.x, enemy.y - turret.y)
        if dist > TURRET_RANGE:
            continue

        # ── 射擊計時 ─────────────────────────────────────────────────────────
        turret._fire_timer -= 1
        if turret._fire_timer > 0:
            continue
        turret._fire_timer = TURRET_FIRE_INTERVAL

        # ── 計算瞄準方向 ──────────────────────────────────────────────────────
        dx, dy = enemy.x - turret.x, enemy.y - turret.y
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        ux, uy = dx / length, dy / length

        # 加入隨機散佈
        if _BULLET_SPREAD > 0:
            dev     = math.radians(random.uniform(-_BULLET_SPREAD, _BULLET_SPREAD))
            cos_d   = math.cos(dev)
            sin_d   = math.sin(dev)
            ux, uy  = ux * cos_d - uy * sin_d, ux * sin_d + uy * cos_d

        # ── 生成子彈 ─────────────────────────────────────────────────────────
        bid = state._next_bullet_id
        state._next_bullet_id = (state._next_bullet_id + 1) % 256
        state.bullets[bid] = Bullet(
            id=bid, owner_id=turret.owner_id,
            x=turret.x + ux * 20,
            y=turret.y + uy * 20,
            dx=ux * _BULLET_SPEED,
            dy=uy * _BULLET_SPEED,
            aim_angle=math.degrees(math.atan2(uy, ux)),
            max_range=_BULLET_RANGE,
            spawn_tick=state.tick,
            bullet_type=0,
        )

        # 每射一發扣機槍台血
        turret.hp -= 1
        if turret.hp <= 0:
            to_remove.append(tid)

    for tid in to_remove:
        state.turrets.pop(tid, None)
