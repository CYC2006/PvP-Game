import math
import pygame
from game.command import PlayerCommand

# 預設值（連線前 / 未選角時的 fallback）
SHOOT_COOLDOWN_MS = 333
MAGAZINE_SIZE     = 12
RELOAD_TIME_MS    = 2000

_last_shot_time:  int  = 0
_ammo:            int  = MAGAZINE_SIZE
_reloading:       bool = False
_reload_start_ms: int  = 0

# ── 角色速度 (px/tick) ────────────────────────────────────────────
_player_speed: float = 3.0


_skill_cds_ms:  dict = {'space': -1, 'e': -1, 'r': -1, 'rmb': -1}
_skill_last_ms: dict = {'space':  0, 'e':  0, 'r':  0, 'rmb':  0}
_char_key:            str   = ""
_rmb_prev:            bool  = False
_r_prev:              bool  = False
_speed_boost_end_ms:  int   = 0     # 速度提升到期時間（ms），供 renderer 粒子使用
_r_skill_start_ms:    int   = 0     # R 大招啟動時間（ms），供 renderer 旋轉使用
_r_skill_start_angle: float = 0.0   # R 大招啟動時的瞄準角度（度）
_r_holding:           bool  = False  # manBlue R 按住中（未施放）
_last_aim_x:          float = 0.0   # 上幀瞄準偏移（world 座標，供 airstrike_fx 使用）
_last_aim_y:          float = 0.0

# ── 衝刺常數 ──────────────────────────────────────────────────────
# 9 ticks：15 + 14.1 + … + 7.8 ≈ 102 px，接近 100 px
_DASH_V0        = 15.0   # 初速 (px/tick)
_DASH_DECEL     = 0.9    # 每 tick 減速 (px/tick²)
_DASH_MIN_SPEED = 7.5    # 低於此速度停止衝刺

# ── 衝刺狀態 ──────────────────────────────────────────────────────
_dash_active: bool  = False
_dash_dx:     float = 0.0
_dash_dy:     float = 0.0
_dash_speed:  float = 0.0

# ── 技能鍵上升緣偵測 ──────────────────────────────────────────────
_space_prev: bool = False
_e_prev:     bool = False


def init_char(char_key: str) -> None:
    """
    遊戲開始後呼叫，依選擇角色設定射速 / 彈夾 / 換彈時間，並重置所有狀態。
    """
    global SHOOT_COOLDOWN_MS, MAGAZINE_SIZE, RELOAD_TIME_MS
    global _ammo, _reloading, _reload_start_ms, _last_shot_time
    global _player_speed, _skill_cds_ms, _skill_last_ms
    global _dash_active, _dash_speed, _space_prev
    global _char_key, _rmb_prev, _r_prev, _speed_boost_end_ms, _r_skill_start_ms, _r_skill_start_angle
    global _r_holding, _last_aim_x, _last_aim_y

    from game.char_data import get_stat, CHAR_STATS

    interval = get_stat(char_key, "fire_interval")
    SHOOT_COOLDOWN_MS = int(interval * 1000) if interval and interval > 0 else 9999

    mag_str = get_stat(char_key, "mag")
    MAGAZINE_SIZE = int(mag_str) if mag_str and str(mag_str).strip().isdigit() else 9999

    reload_s = get_stat(char_key, "reload_time")
    RELOAD_TIME_MS = int(reload_s * 1000) if reload_s and reload_s > 0 else 99999

    _player_speed = float(CHAR_STATS.get(char_key, {}).get('speed', 3.0))

    cfg = CHAR_STATS.get(char_key, {})
    def _cd(key: str) -> int:
        v = float(cfg.get(key, 0))
        return int(v * 1000) if v > 0 else -1
    _skill_cds_ms = {
        'rmb':   _cd('cd_rmb'),
        'space': _cd('cd_space'),
        'e':     _cd('cd_e'),
        'r':     _cd('cd_r'),
    }
    _skill_last_ms = {'space': 0, 'e': 0, 'r': 0, 'rmb': 0}

    _char_key             = char_key
    _speed_boost_end_ms   = 0
    _r_skill_start_ms     = 0
    _r_skill_start_angle  = 0.0
    _ammo                 = MAGAZINE_SIZE
    _reloading       = False
    _reload_start_ms = 0
    _last_shot_time  = 0
    _dash_active     = False
    _dash_speed      = 0.0
    _space_prev      = False
    _e_prev          = False
    _rmb_prev        = False
    _r_prev          = False
    _r_holding       = False
    _last_aim_x      = 0.0
    _last_aim_y      = 0.0


def read_input(player_id: int, keys_held: set,
               logical_mouse: tuple,
               shift_held: bool) -> tuple:
    """
    回傳 (PlayerCommand, effective_stance, ammo, is_reloading, skill_cooldowns)

    skill_cooldowns : {'space':(remaining_ms, max_ms), 'e':..., 'r':..., 'rmb':...}
                      remaining_ms == -1  → 技能尚未實作
    """
    global _last_shot_time, _ammo, _reloading, _reload_start_ms
    global _space_prev, _e_prev, _rmb_prev, _r_prev
    global _dash_active, _dash_dx, _dash_dy, _dash_speed
    global _skill_last_ms, _speed_boost_end_ms, _r_skill_start_ms, _r_skill_start_angle
    global _r_holding, _last_aim_x, _last_aim_y

    now = pygame.time.get_ticks()

    # ── 換彈完成判斷 ──────────────────────────────────────────────
    if _reloading and (now - _reload_start_ms) >= RELOAD_TIME_MS:
        _reloading = False
        _ammo      = MAGAZINE_SIZE

    effective_stance = "reload" if _reloading else "machine"

    from game.render_utils import LOGICAL_W, LOGICAL_H
    lx, ly = logical_mouse
    aim_x = float(lx - LOGICAL_W // 2)
    aim_y = float(ly - LOGICAL_H // 2)
    _last_aim_x = aim_x
    _last_aim_y = aim_y

    # ── 技能鍵上升緣 ──────────────────────────────────────────────
    space_held         = pygame.K_SPACE in keys_held
    space_just_pressed = space_held and not _space_prev
    _space_prev        = space_held

    e_held             = pygame.K_e in keys_held
    e_just_pressed     = e_held and not _e_prev
    _e_prev            = e_held

    rmb_held           = pygame.mouse.get_pressed()[2]
    rmb_just_pressed   = rmb_held and not _rmb_prev
    rmb_just_released  = not rmb_held and _rmb_prev
    _rmb_prev          = rmb_held

    r_held             = pygame.K_r in keys_held
    r_just_pressed     = r_held and not _r_prev
    r_just_released    = not r_held and _r_prev
    _r_prev            = r_held

    # ── R 技能啟動狀態（在所有技能判斷之前計算，確保完全隔離）────
    _r_skill_active = (now - _r_skill_start_ms) < 500 and _r_skill_start_ms > 0

    # ── 位移 / WASD ───────────────────────────────────────────────
    dx, dy          = 0.0, 0.0
    speed_mult      = 1.0
    use_skill_space = False

    if _dash_active:
        if _dash_speed < _DASH_MIN_SPEED:
            _dash_active = False          # 速度低於閾值，衝刺結束
        else:
            speed_mult  = _dash_speed / max(_player_speed, 0.001)
            dx, dy      = _dash_dx, _dash_dy
            _dash_speed -= _DASH_DECEL

    if not _dash_active:
        if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
        if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
        if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
        if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

        # ── 觸發衝刺（非 survivor1）或速度技能（survivor1）──────
        if (not _r_skill_active
                and space_just_pressed
                and _skill_cds_ms.get('space', -1) >= 0):
            cd_remaining = _skill_cds_ms['space'] - (now - _skill_last_ms['space'])
            if cd_remaining <= 0:
                if _char_key == 'survivor1':
                    pass   # 冷卻由下方 use_skill_space 區塊統一記錄
                elif _char_key == 'manOld':
                    aim_len = math.hypot(aim_x, aim_y)
                    if aim_len > 0:
                        _dash_active     = True
                        _dash_dx         = -aim_x / aim_len
                        _dash_dy         = -aim_y / aim_len
                        speed_mult       = 18.0 / max(_player_speed, 0.001)
                        dx, dy           = _dash_dx, _dash_dy
                        _dash_speed      = 18.0 - _DASH_DECEL
                        _skill_last_ms['space'] = now
                        use_skill_space  = True
                else:
                    length = math.hypot(dx, dy)
                    if length > 0:
                        _dash_active     = True
                        _dash_dx         = dx / length
                        _dash_dy         = dy / length
                        speed_mult       = _DASH_V0 / max(_player_speed, 0.001)
                        dx, dy           = _dash_dx, _dash_dy
                        _dash_speed      = _DASH_V0 - _DASH_DECEL
                        _skill_last_ms['space'] = now

    running = shift_held and not _dash_active

    # ── E 技能（閃光彈等）────────────────────────────────────────
    use_skill_e = False
    if (not _r_skill_active and e_just_pressed and _skill_cds_ms.get('e', -1) >= 0):
        cd_remaining = _skill_cds_ms['e'] - (now - _skill_last_ms['e'])
        if cd_remaining <= 0:
            use_skill_e = True
            _skill_last_ms['e'] = now

    # ── RMB 技能（manBlue：按住蓄力放開施放；其他角色：按下即發）──
    use_skill_rmb = False
    if not _r_skill_active and _skill_cds_ms.get('rmb', -1) >= 0:
        rmb_cd_ms = _skill_cds_ms['rmb']
        if _char_key == 'manBlue':
            cd_ok = (rmb_cd_ms - (now - _skill_last_ms['rmb'])) <= 0
            if rmb_just_pressed and cd_ok:
                _r_holding = True
            if rmb_just_released and _r_holding:
                use_skill_rmb = True
                _skill_last_ms['rmb'] = now
            if rmb_just_released:
                _r_holding = False
        else:
            if rmb_just_pressed and (rmb_cd_ms - (now - _skill_last_ms['rmb'])) <= 0:
                use_skill_rmb = True
                _skill_last_ms['rmb'] = now

    # ── Space 技能（survivor1：速度提升）─────────────────────────
    if (not _r_skill_active
            and _char_key == 'survivor1'
            and space_just_pressed
            and _skill_cds_ms.get('space', -1) >= 0):
        cd_elapsed = now - _skill_last_ms['space']
        if cd_elapsed >= _skill_cds_ms['space']:
            use_skill_space = True
            _skill_last_ms['space'] = now
            _speed_boost_end_ms = now + 2000   # 2 秒提升

    # ── R 技能（按下即發）────────────────────────────────────────
    use_skill_r = False
    if not _r_skill_active and _skill_cds_ms.get('r', -1) >= 0:
        if r_just_pressed and (_skill_cds_ms['r'] - (now - _skill_last_ms['r'])) <= 0:
            use_skill_r = True
            _skill_last_ms['r']  = now
            _r_skill_start_ms    = now
            _r_skill_start_angle = math.degrees(math.atan2(aim_x, -aim_y))

    # ── 射擊（換彈中禁止 / R 技能期間禁止）──────────────────────
    shooting = False
    if (not _reloading and not _r_skill_active
            and pygame.mouse.get_pressed()[0]
            and (now - _last_shot_time) >= SHOOT_COOLDOWN_MS):
        shooting        = True
        _last_shot_time = now
        if MAGAZINE_SIZE < 9999:
            _ammo -= 1
            if _ammo <= 0:
                _ammo            = 0
                _reloading       = True
                _reload_start_ms = now

    # ── 技能冷卻資訊（給 HUD）────────────────────────────────────
    skill_cooldowns: dict = {}
    for slot in ('space', 'e', 'r', 'rmb'):
        max_cd = _skill_cds_ms.get(slot, -1)
        if max_cd < 0:
            skill_cooldowns[slot] = (-1, -1)
        else:
            remaining = max_cd - (now - _skill_last_ms[slot])
            skill_cooldowns[slot] = (max(0, remaining), max_cd)

    cmd = PlayerCommand(
        player_id=player_id,
        move_x=dx, move_y=dy,
        shooting=shooting,
        aim_x=aim_x, aim_y=aim_y,
        running=running,
        stance=effective_stance,
        speed_mult=speed_mult,
        use_skill_e=use_skill_e,
        use_skill_rmb=use_skill_rmb,
        use_skill_space=use_skill_space,
        use_skill_r=use_skill_r,
    )
    return cmd, effective_stance, _ammo, _reloading, skill_cooldowns
