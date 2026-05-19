"""Bear R — 滾動空襲 Rolling Barrage

朝鼠標方向依序召喚 18 枚空襲，每 10 tick 一枚，由近至遠依次落下。
每枚空襲：縮小圓圈（20 tick）→ 爆炸傷害。
"""

import math
import random
from game.state import BarrageStrike, MAP_WIDTH, MAP_HEIGHT

BARRAGE_COUNT    = 18     # 總空襲枚數
BARRAGE_INTERVAL = 10     # 每枚間隔 tick
BARRAGE_FUSE     = 20     # 縮小圓圈持續 tick，到期後爆炸
BARRAGE_LINGER   = 60     # 爆炸後 strike 繼續留在 state 的 tick（供 client FX）
BARRAGE_START_D  = 60     # 第一枚距玩家的前向距離（px）
BARRAGE_STEP_D   = 10     # 每枚遞增的前向距離（px）
BARRAGE_HALF_W   = 100    # 橫向隨機偏移範圍 ±px
BARRAGE_EXPL_R   = 80     # 爆炸傷害半徑（px）
BARRAGE_DMG_MIN  = 10     # 邊緣最低傷害
BARRAGE_DMG_MAX  = 35     # 中心最高傷害（公式算出）


def activate_barrage(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    """按下 R 後立即建立 18 枚待發空襲，存入 _pending_barrage。"""
    player = state.players.get(owner_id)
    if not player:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    rx, ry = -uy, ux   # 右方向向量（垂直於前進方向）

    for i in range(BARRAGE_COUNT):
        forward  = BARRAGE_START_D + i * BARRAGE_STEP_D
        lateral  = random.uniform(-BARRAGE_HALF_W, BARRAGE_HALF_W)
        x = player.x + ux * forward + rx * lateral
        y = player.y + uy * forward + ry * lateral
        # 限制在地圖邊界內
        x = max(20.0, min(float(MAP_WIDTH  - 20), x))
        y = max(20.0, min(float(MAP_HEIGHT - 20), y))

        sid = state._next_barrage_id
        state._next_barrage_id = (state._next_barrage_id + 1) % 256
        strike = BarrageStrike(
            id=sid, owner_id=owner_id, x=x, y=y,
            spawn_tick=state.tick + i * BARRAGE_INTERVAL,
        )
        state._pending_barrage.append(strike)


def step_barrage(state) -> None:
    """每 tick 執行：推送待發 strike → 觸發爆炸 → 清除過期 strike。"""
    # ── 將到達時刻的 strike 從待發佇列移入 barrage_strikes ──────────
    still_pending = []
    for strike in state._pending_barrage:
        if strike.spawn_tick <= state.tick:
            state.barrage_strikes[strike.id] = strike
        else:
            still_pending.append(strike)
    state._pending_barrage = still_pending

    # ── 處理已啟動的 strike ──────────────────────────────────────────
    to_remove = []
    for sid, strike in list(state.barrage_strikes.items()):
        age = state.tick - strike.spawn_tick

        # 爆炸傷害（剛好到達 FUSE 的那一 tick）
        if age == BARRAGE_FUSE:
            enemy_id = 3 - strike.owner_id
            enemy    = state.players.get(enemy_id)
            if enemy:
                dist = math.hypot(enemy.x - strike.x, enemy.y - strike.y)
                if dist < BARRAGE_EXPL_R:
                    ratio  = 1.0 - dist / BARRAGE_EXPL_R
                    damage = int(BARRAGE_DMG_MIN + (BARRAGE_DMG_MAX - BARRAGE_DMG_MIN) * ratio ** 2)
                    if enemy.giant_tick >= 0:
                        damage = int(damage * 0.8)
                    enemy.hp -= damage
                    if enemy.hp <= 0:
                        enemy.respawn()

        # 超過 LINGER 時間後移除
        if age >= BARRAGE_FUSE + BARRAGE_LINGER:
            to_remove.append(sid)

    for sid in to_remove:
        state.barrage_strikes.pop(sid, None)
