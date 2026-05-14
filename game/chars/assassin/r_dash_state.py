import math
from game.state import PLAYER_RADIUS, MAP_WIDTH, MAP_HEIGHT

# 每段距離 400px / 0.25s；速度從 v0 等減速至 v0/2（不減到 0）
# 連續積分：distance = v0*T - (v0/2T)*T²/2 = 3*v0*T/4 = 400 → v0 = 1600/45
R_PHASE_TICKS = 15
R_V0          = 1600.0 / 45.0   # ≈ 35.56 px/tick
R_DAMAGE      = 30               # 每段碰撞傷害


def activate_r_skill(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    player = state.players.get(owner_id)
    if not player or player.r_skill_phase > 0:
        return
    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    player.r_skill_phase       = 1
    player.r_skill_tick        = 0
    player.r_skill_dx          = aim_x / length
    player.r_skill_dy          = aim_y / length
    player.r_skill_start_angle = player.aim_angle
    player.r_skill_dmg_done    = 0


def step_r_skill(state) -> None:
    for player in state.players.values():
        if player.r_skill_phase == 0:
            continue
        tick  = player.r_skill_tick
        phase = player.r_skill_phase

        progress  = tick / R_PHASE_TICKS
        speed     = R_V0 * (1.0 - 0.5 * progress)
        direction = 1.0 if phase == 1 else -1.0
        player.x  = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS,
                                           player.x + player.r_skill_dx * speed * direction))
        player.y  = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS,
                                           player.y + player.r_skill_dy * speed * direction))

        base_offset  = 180.0 if phase == 2 else 0.0
        player.aim_angle = player.r_skill_start_angle + base_offset + 180.0 * progress

        dmg_flag    = 1 if phase == 1 else 2
        opponent_id = 3 - player.id
        opponent    = state.players.get(opponent_id)
        if opponent and not (player.r_skill_dmg_done & dmg_flag):
            if math.hypot(player.x - opponent.x, player.y - opponent.y) < PLAYER_RADIUS * 2 + 4:
                opponent.hp -= R_DAMAGE
                player.r_skill_dmg_done |= dmg_flag
                if opponent.hp <= 0:
                    opponent.respawn()

        player.r_skill_tick += 1
        if player.r_skill_tick >= R_PHASE_TICKS:
            if phase == 1:
                player.r_skill_phase = 2
                player.r_skill_tick  = 0
            else:
                player.r_skill_phase = 0
                player.r_skill_tick  = 0
