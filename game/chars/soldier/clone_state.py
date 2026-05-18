import math
import random
from game.state import Bullet, PLAYER_RADIUS, BULLET_MAX_RANGE

CLONE_TICKS          = 480    # 8 秒
CLONE_OFFSET_SIDE    = 30.0   # 左右各 30 px
CLONE_OFFSET_FORWARD = 10.0   # 前方 10 px

# 槍口偏移量（與 _spawn_bullet 的 barrel_fwd / barrel_right 相同）
_BARREL_FWD   = PLAYER_RADIUS + 10   # 26 px
_BARREL_RIGHT = 14                   # px


def activate_clones(state, owner_id: int) -> None:
    player = state.players.get(owner_id)
    if not player:
        return
    # 已有分身時不重疊啟動
    if player.clone_until > state.tick:
        return
    player.clone_until = state.tick + CLONE_TICKS


def spawn_clone_bullets(state, owner_id: int, aim_x: float, aim_y: float) -> None:
    """在左右分身位置各射出一顆子彈，方向與玩家本體相同。
    只在普攻觸發（apply_command 的 shooting 路徑），不消耗額外彈藥。
    """
    player = state.players.get(owner_id)
    if not player or player.clone_until <= state.tick:
        return

    length = math.hypot(aim_x, aim_y)
    if length == 0:
        return
    ux, uy = aim_x / length, aim_y / length
    rx, ry = -uy, ux   # 右方向（與 _spawn_bullet 相同慣例）

    for sign in (-1.0, 1.0):   # -1 = 左分身, +1 = 右分身
        # 分身中心
        clone_x = player.x + rx * sign * CLONE_OFFSET_SIDE + ux * CLONE_OFFSET_FORWARD
        clone_y = player.y + ry * sign * CLONE_OFFSET_SIDE + uy * CLONE_OFFSET_FORWARD
        # 槍口位置（從分身中心再偏移，與本體一致）
        spawn_x = clone_x + ux * _BARREL_FWD + rx * _BARREL_RIGHT
        spawn_y = clone_y + uy * _BARREL_FWD + ry * _BARREL_RIGHT

        # 獨立 spread 偏角
        pux, puy = ux, uy
        if player.spread > 0:
            dev     = math.radians(random.uniform(-player.spread, player.spread))
            cos_s   = math.cos(dev)
            sin_s   = math.sin(dev)
            pux     = ux * cos_s - uy * sin_s
            puy     = ux * sin_s + uy * cos_s

        spd = player.bullet_speed
        ndx = pux * spd
        ndy = puy * spd

        # 射程（仿 _spawn_bullet，不處理 decel / linger 以保持簡單）
        import math as _m
        if _m.isinf(player.bullet_range):
            pellet_range = player.bullet_range
        elif player.bullet_range_min > 0:
            pellet_range = random.uniform(player.bullet_range_min, player.bullet_range)
        else:
            pellet_range = player.bullet_range

        bid = state._next_bullet_id
        state._next_bullet_id = (state._next_bullet_id + 1) % 256
        # 分身子彈：char_key 仍是 soldier1 → bullet_type = 0（在 _spawn_bullet 的 _btype 邏輯之外）
        state.bullets[bid] = Bullet(
            id=bid, owner_id=owner_id,
            x=spawn_x, y=spawn_y,
            dx=ndx, dy=ndy,
            aim_angle=math.degrees(math.atan2(ndy, ndx)),
            max_range=pellet_range,
            spawn_tick=state.tick,
            bullet_scale=1.0,
            bullet_type=0,
        )
