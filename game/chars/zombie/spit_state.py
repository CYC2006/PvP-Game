"""Zombie RMB — 腐蝕吐息 Corrosive Spew

按下 RMB 時鎖定當前瞄準方向，角色進入 1 秒完全僵直（比照巨人化 grow/shrink：
不能移動、不能射擊、不能使用任何技能）。從第 6 個 tick 起每 6 tick 一波，沿鎖定
方向朝前吐出，共 10 波、每波 3 顆，總計 30 顆。前進距離與橫向偏移範圍皆隨 tick
數線性增加（第 N 波：前進 10N px，橫向偏移 ±N px），球體半徑各自獨立隨機
30~40px。每顆球生成後作為地面上的暈眩區域存在 60~72 tick（各自獨立隨機），
暈眩判定區間結束後不會立刻消失，而是再花 FADE_TICKS（0.3 秒）淡出至完全
透明才真正移除，純視覺、不再判定碰撞。

碰撞判定分兩種，互相獨立：
- 傷害：每顆球只要碰到敵人就造成一次 6~8 傷害（orb.hit_enemy 旗標，單顆球
  只會命中一次），多顆球同時疊在同一位置就會疊加成多倍傷害。
- 暈眩：整次施放只會暈眩對手一次（zombie_spit_hit_enemy 旗標），避免對手
  中招暈眩結束的瞬間又站在另一顆（或同一顆）尚存活的球體範圍內被連續暈眩
  鎖死；即使暈眩已用掉，其餘球體仍會正常造成傷害。
"""

import math
import random
from game.state import ZombieOrb, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS

WAVE_COUNT       = 10
WAVE_INTERVAL    = 6                                  # ticks between waves
BALLS_PER_WAVE   = 3
TOTAL_TICKS      = WAVE_COUNT * WAVE_INTERVAL         # 60 ticks（完全僵直總時長）
FORWARD_PER_TICK = 10.0                               # px：前進距離 = 波次 tick 數 × 此值
ORB_RADIUS_MIN   = 30.0
ORB_RADIUS_MAX   = 40.0
ORB_LIFETIME_MIN = 60                                 # tick（1.0s）：暈眩判定區間
ORB_LIFETIME_MAX = 72                                 # tick（1.2s）：暈眩判定區間
FADE_TICKS       = 18                                 # tick（0.3s）：判定區間結束後的淡出時長
STUN_TICKS       = 60                                 # 1 秒
DAMAGE_MIN       = 6
DAMAGE_MAX       = 8


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
    player.zombie_spit_hit_enemy  = False


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
        hazard_age  = state.tick - orb.spawn_tick
        hazard_life = orb.expire_tick - orb.spawn_tick
        if hazard_age >= hazard_life:
            # 暈眩判定區間已結束：只淡出、不再判定碰撞
            fade_age = hazard_age - hazard_life
            orb.fade = max(0, 255 - int(255 * fade_age / FADE_TICKS))
            if state.tick >= orb.expire_tick + FADE_TICKS:
                expired.append(oid)
            continue

        if orb.hit_enemy:
            continue   # 這顆球已經命中過，不會重複造成傷害
        enemy_id = 3 - orb.owner_id
        enemy    = state.players.get(enemy_id)
        if not enemy:
            continue
        dist = math.hypot(enemy.x - orb.x, enemy.y - orb.y)
        if dist > orb.radius + PLAYER_RADIUS:
            continue

        orb.hit_enemy = True
        damage = random.randint(DAMAGE_MIN, DAMAGE_MAX)
        if enemy.giant_tick >= 0:
            damage = int(damage * 0.8)
        state.apply_damage(enemy_id, damage)

        owner = state.players.get(orb.owner_id)
        if owner and not owner.zombie_spit_hit_enemy:
            state.apply_stun(enemy_id, STUN_TICKS)
            owner.zombie_spit_hit_enemy = True

    for oid in expired:
        state.zombie_orbs.pop(oid, None)
