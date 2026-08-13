"""Zombie RMB — 腐蝕吐息 Corrosive Spew

按下 RMB 時鎖定當前瞄準方向，角色進入 1 秒完全僵直（比照巨人化 grow/shrink：
不能移動、不能射擊、不能使用任何技能）。從第 6 個 tick 起每 6 tick 一波，沿鎖定
方向朝前吐出，共 10 波、每波 3 顆，總計 30 顆。前進距離與橫向偏移範圍皆隨 tick
數線性增加（第 N 波：前進 10N px，橫向偏移 ±N px），球體半徑各自獨立隨機
20~30px。每顆球生成後停留 60~72 tick（各自獨立隨機）作為地面上的暈眩區域，
碰到敵人造成 1 秒暈眩、無傷害。
"""

import math
import random
from game.state import ZombieOrb, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS

WAVE_COUNT       = 10
WAVE_INTERVAL    = 6                                  # ticks between waves
BALLS_PER_WAVE   = 3
TOTAL_TICKS      = WAVE_COUNT * WAVE_INTERVAL         # 60 ticks（完全僵直總時長）
FORWARD_PER_TICK = 10.0                               # px：前進距離 = 波次 tick 數 × 此值
ORB_RADIUS_MIN   = 20.0
ORB_RADIUS_MAX   = 30.0
ORB_LIFETIME_MIN = 60                                 # tick（1.0s）
ORB_LIFETIME_MAX = 72                                 # tick（1.2s）
STUN_TICKS       = 60                                 # 1 秒


def activate_spit(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player or player.zombie_spit_tick >= 0:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    player.zombie_spit_aim_x      = aim_x / length
    player.zombie_spit_aim_y      = aim_y / length
    player.zombie_spit_tick       = state.tick
    player.zombie_spit_wave_fired = 0


def _fire_wave(state, player, wave_idx: int) -> None:
    """wave_idx：第幾波（1-based，1~WAVE_COUNT）。"""
    ux, uy = player.zombie_spit_aim_x, player.zombie_spit_aim_y
    rx, ry = -uy, ux   # 垂直於前進方向的右手向量，供橫向偏移使用

    t       = wave_idx * WAVE_INTERVAL   # 施放到第幾個 tick（6,12,...,60）
    forward = t * FORWARD_PER_TICK

    for _ in range(BALLS_PER_WAVE):
        lateral = random.uniform(-t, t)
        x = player.x + ux * forward + rx * lateral
        y = player.y + uy * forward + ry * lateral
        x = max(20.0, min(float(MAP_WIDTH  - 20), x))
        y = max(20.0, min(float(MAP_HEIGHT - 20), y))

        radius   = random.uniform(ORB_RADIUS_MIN, ORB_RADIUS_MAX)
        lifetime = random.randint(ORB_LIFETIME_MIN, ORB_LIFETIME_MAX)

        oid = state._next_zombie_orb_id
        state._next_zombie_orb_id = (state._next_zombie_orb_id + 1) % 65536
        state.zombie_orbs[oid] = ZombieOrb(
            id=oid, owner_id=player.id, x=x, y=y, radius=radius,
            spawn_tick=state.tick, expire_tick=state.tick + lifetime,
        )

    player.zombie_spit_wave_fired += 1


def step_spit(state) -> None:
    """每 tick：推進僵直中角色的吐息波次；處理已生成球體的暈眩判定與過期。"""
    for player in state.players.values():
        if player.zombie_spit_tick < 0:
            continue
        # 施放中被暈眩打斷（比照 Mercury Barrage）
        if state.tick < player.stun_until:
            player.zombie_spit_tick       = -1
            player.zombie_spit_wave_fired = 0
            continue

        age       = state.tick - player.zombie_spit_tick
        waves_due = age // WAVE_INTERVAL
        while (player.zombie_spit_wave_fired < waves_due
               and player.zombie_spit_wave_fired < WAVE_COUNT):
            _fire_wave(state, player, player.zombie_spit_wave_fired + 1)

        if age >= TOTAL_TICKS and player.zombie_spit_wave_fired >= WAVE_COUNT:
            player.zombie_spit_tick = -1

    expired = []
    for oid, orb in state.zombie_orbs.items():
        if state.tick >= orb.expire_tick:
            expired.append(oid)
            continue
        enemy_id = 3 - orb.owner_id
        enemy    = state.players.get(enemy_id)
        if enemy and state.tick >= enemy.stun_until:
            dist = math.hypot(enemy.x - orb.x, enemy.y - orb.y)
            if dist <= orb.radius + PLAYER_RADIUS:
                state.apply_stun(enemy_id, STUN_TICKS)

    for oid in expired:
        state.zombie_orbs.pop(oid, None)
