import math
import random
import pygame
from dataclasses import dataclass, field
from game import audio
from game.command import PlayerCommand
from game.chars.vince.giant_state import GROW_TICKS, ACTIVE_TICKS, SHRINK_TICKS, TOTAL_TICKS
from game.chars.agent.mercury_state import ULT_DURATION as _MERCURY_ULT_TICKS
from game.chars.zombie.spit_state import TOTAL_TICKS as _ZOMBIE_SPIT_TICKS

# ── 模組級常數（renderer 以 from game.input import 取得；init_char 後同步更新）──
SHOOT_COOLDOWN_MS = 333
MAGAZINE_SIZE     = 12
RELOAD_TIME_MS    = 2000

# ── 衝刺常數（不因角色或局別改變）────────────────────────────────────────────
_DASH_V0          = 15.0   # 初速 (px/tick)
_DASH_DECEL       = 0.9    # 每 tick 減速 (px/tick²)
_DASH_MIN_SPEED   = 7.5    # 低於此速度停止衝刺
_RAMBO_DASH_SPEED = 8.33   # 等速衝刺速度 (px/tick，保留供未來角色使用)

# ── 角色普攻音效 ──────────────────────────────────────────────────────────────
_AGENT_PISTOL_SFX  = ('weapon/agent_pistol_1.wav', 'weapon/agent_pistol_2.wav')
_PIONEER_RIFLE_SFX = ('weapon/pioneer_rifle_1.wav', 'weapon/pioneer_rifle_2.wav',
                      'weapon/pioneer_rifle_3.wav', 'weapon/pioneer_rifle_4.wav')
_MARKSMAN_MACHINE_SFX = ('weapon/marksman_machine_1.wav', 'weapon/marksman_machine_2.wav',
                         'weapon/marksman_machine_3.wav', 'weapon/marksman_machine_4.wav')
_HUNTER_SNIPER_SFX = 'weapon/hunter_sniper.wav'
_ASSASSIN_SHURIKEN_SFX = ('weapon/assassin_shuriken_1.wav', 'weapon/assassin_shuriken_2.wav')
_ASSASSIN_PELLET_COUNT = 5
_ASSASSIN_PELLET_INTERVAL_MS = 50   # pellet_interval=3 tick × (1000/60)
_VINCE_SHOTGUN_SFX = ('weapon/vince_shotgun_1.wav', 'weapon/vince_shotgun_2.wav')
_ZOMBIE_MOAN_SFX = ('weapon/zombie_moan_1.wav', 'weapon/zombie_moan_2.wav',
                    'weapon/zombie_moan_3.wav', 'weapon/zombie_moan_4.wav')
_RELOAD_SFX: dict = {
    'Agent':    'reload/agent_reload.wav',
    'Pioneer':  'reload/pioneer_reload.wav',
    'Marksman': 'reload/marksman_reload.wav',
    'Hunter':   'reload/sniper_reload.wav',
}


# ─────────────────────────────────────────────────────────────────────────────
# InputState：所有 client 端輸入狀態集中管理
# 每局開始時由 init_char() 重建；新增狀態欄位只需在此加 field，不會遺漏重置。
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InputState:
    # ── 角色設定（init_char 設定）──────────────────────────────────────────
    char_name:           str   = ""
    shoot_cooldown_ms:   int   = 333
    magazine_size:       int   = 12
    reload_time_ms:      int   = 2000
    current_reload_ms:   int   = 2000   # 本次換彈所需 ms（散彈/狙擊依發數計算）
    player_speed:        float = 3.0
    skill_cds_ms:        dict  = field(default_factory=lambda: {
                                     'space': -1, 'e': -1, 'r': -1, 'rmb': -1, 'q': -1})
    skill_last_ms:       dict  = field(default_factory=lambda: {
                                     'space': 0, 'e': 0, 'r': 0, 'rmb': 0, 'q': 0})
    # ── 射擊 / 彈夾 ─────────────────────────────────────────────────────────
    last_shot_time:      int   = 0
    ammo:                int   = 12
    reloading:           bool  = False
    reload_start_ms:     int   = 0
    pending_sfx:         list  = field(default_factory=list)   # [(due_ms, relpath)]，供錯開發射的音效排程用
    # ── 按鍵緣偵測 ───────────────────────────────────────────────────────────
    space_prev:          bool  = False
    e_prev:              bool  = False
    rmb_prev:            bool  = False
    r_prev:              bool  = False
    f_prev:              bool  = False
    q_prev:              bool  = False
    r_holding:           bool  = False   # Vince RMB 蓄力中
    # ── 技能輔助 ─────────────────────────────────────────────────────────────
    speed_boost_end_ms:  int   = 0
    r_skill_start_ms:    int   = 0
    r_skill_start_angle: float = 0.0
    robot_mark_until_ms:   int   = 0
    robot_e_mark_until_ms: int   = 0
    mercury_end_ms:      int   = 0   # ms when Agent barrage ends (0=inactive)
    mercury_aim_angle:   float = 0.0  # aim_angle_deg locked at barrage activation
    zombie_spit_end_ms:  int   = 0   # ms when Zombie spit channel ends (0=inactive)
    rune_id:             int   = 0
    # ── 每幀由 client.py 推入（伺服器狀態鏡像）─────────────────────────────
    giant_age:              int   = -1
    burst_shots_left:       int   = 0
    cloak_ticks_left:       int   = 0
    air_cannon_hit_seq:     int   = -1   # -1 = 尚未初始化；偵測變化以刷新 RMB 冷卻
    last_aim_x:          float = 0.0
    last_aim_y:          float = 0.0
    # ── 衝刺狀態 ─────────────────────────────────────────────────────────────
    dash_active:         bool  = False
    dash_dx:             float = 0.0
    dash_dy:             float = 0.0
    dash_speed:          float = 0.0
    dash_dist_remaining: float = 0.0
    # ── 衝刺碰撞上下文（每幀由 client.py 更新）──────────────────────────────
    dash_player_x:       float = 0.0
    dash_player_y:       float = 0.0
    dash_obstacles:      dict  = field(default_factory=dict)
    dash_destroyed:      set   = field(default_factory=set)


_state = InputState()


# ─────────────────────────────────────────────────────────────────────────────
# client.py 每幀推入的 setters（不需要 global 宣告）
# ─────────────────────────────────────────────────────────────────────────────

def set_giant_age(age: int) -> None:
    _state.giant_age = age


def set_burst_shots_left(n: int) -> None:
    _state.burst_shots_left = n


def set_cloak_ticks(n: int) -> None:
    _state.cloak_ticks_left = n


def cancel_mercury_barrage() -> None:
    """由 client.py 呼叫：server 廣播大招已結束（被暈眩中斷）時清除本地鎖定狀態。"""
    _state.mercury_end_ms = 0


def cancel_zombie_spit() -> None:
    """由 client.py 呼叫：本地玩家被暈眩打斷施放中的吐息時清除本地僵直預測。"""
    _state.zombie_spit_end_ms = 0


def notify_air_cannon_hit(seq: int) -> None:
    """由 client.py 呼叫：偵測到本玩家的空氣炮命中序號變化時，立即刷新 RMB 冷卻。"""
    if _state.air_cannon_hit_seq == -1:
        # 首次初始化，不觸發刷新
        _state.air_cannon_hit_seq = seq
        return
    if seq != _state.air_cannon_hit_seq:
        _state.air_cannon_hit_seq = seq
        # 將上次施放時間設為超早，使冷卻立即到期
        _state.skill_last_ms['rmb'] = 0


def apply_gem_cd_reduction() -> None:
    """撿到冷縮寶石時呼叫：所有在冷卻中的技能減少 1 秒冷卻時間。"""
    now = pygame.time.get_ticks()
    for slot, max_cd in _state.skill_cds_ms.items():
        if max_cd <= 0:
            continue
        remaining = max_cd - (now - _state.skill_last_ms[slot])
        if remaining > 0:
            # 提早 1000ms 計為已使用，等效縮短 1 秒冷卻
            _state.skill_last_ms[slot] = max(
                _state.skill_last_ms[slot] - 1000,
                now - max_cd,
            )


def get_mercury_aim_angle():
    """Return locked aim_angle_deg while Agent's Mercury Barrage is active, else None."""
    now = pygame.time.get_ticks()
    if _state.char_name == 'Agent' and now < _state.mercury_end_ms:
        return _state.mercury_aim_angle
    return None


def set_dash_context(player_x: float, player_y: float,
                     obstacles: dict, destroyed: set) -> None:
    _state.dash_player_x  = player_x
    _state.dash_player_y  = player_y
    _state.dash_obstacles = obstacles
    _state.dash_destroyed = destroyed


# ─────────────────────────────────────────────────────────────────────────────
# Space 技能 per-character handlers
#
# 簽名：(st, dx, dy, aim_x, aim_y, now) → (use_skill_space, dx, dy, speed_mult)
# Handler 負責：寫入 st 的持久狀態、記錄 skill_last_ms['space']、回傳本幀覆蓋值
# ─────────────────────────────────────────────────────────────────────────────

def _space_vince(st: InputState, dx: float, dy: float,
                 aim_x: float, aim_y: float, now: int) -> tuple:
    st.skill_last_ms['space'] = now
    return True, dx, dy, 1.0


def _space_marksman(st: InputState, dx: float, dy: float,
                    aim_x: float, aim_y: float, now: int) -> tuple:
    st.skill_last_ms['space'] = now
    return True, dx, dy, 1.0


def _space_hunter(st: InputState, dx: float, dy: float,
                  aim_x: float, aim_y: float, now: int) -> tuple:
    """向瞄準反方向翻滾衝刺。"""
    aim_len = math.hypot(aim_x, aim_y)
    if aim_len == 0:
        return False, dx, dy, 1.0
    ndx = -aim_x / aim_len
    ndy = -aim_y / aim_len
    st.dash_active            = True
    st.dash_dx                = ndx
    st.dash_dy                = ndy
    st.dash_speed             = 18.0 - _DASH_DECEL
    st.skill_last_ms['space'] = now
    speed_mult = 18.0 / max(st.player_speed, 0.001)
    return True, ndx, ndy, speed_mult


def _space_pioneer_zombie(st: InputState, dx: float, dy: float,
                          aim_x: float, aim_y: float, now: int) -> tuple:
    """跳躍：通知 server 起跳，本地立即補滿彈夾並取消換彈。"""
    st.skill_last_ms['space'] = now
    st.ammo                   = st.magazine_size
    st.reloading               = False
    st.reload_start_ms         = 0
    return True, dx, dy, 1.0


def _space_robot(st: InputState, dx: float, dy: float,
                 aim_x: float, aim_y: float, now: int) -> tuple:
    """衝刺並在落點設置印記。"""
    length = math.hypot(dx, dy)
    if length == 0:
        return False, dx, dy, 1.0
    ndx = dx / length
    ndy = dy / length
    st.dash_active            = True
    st.dash_dx                = ndx
    st.dash_dy                = ndy
    st.dash_speed             = _DASH_V0 - _DASH_DECEL
    st.skill_last_ms['space'] = now
    st.robot_mark_until_ms    = now + 4000
    speed_mult = _DASH_V0 / max(st.player_speed, 0.001)
    return True, ndx, ndy, speed_mult


def _space_assassin_noop(st: InputState, dx: float, dy: float,
                         aim_x: float, aim_y: float, now: int) -> tuple:
    """Assassin space 邏輯在 read_input 的獨立區塊處理
    （因可在衝刺中觸發，不受 not dash_active guard 限制），此處為 no-op 佔位。"""
    return False, dx, dy, 1.0


def _space_poisoner(st: InputState, dx: float, dy: float,
                    aim_x: float, aim_y: float, now: int) -> tuple:
    """Poisoner Space：移速 +20%（server 處理）+ 殘影（client 透過 speed_boost_end_ms）。"""
    st.speed_boost_end_ms     = now + 3000
    st.skill_last_ms['space'] = now
    return True, dx, dy, 1.0


def _space_agent(st: InputState, dx: float, dy: float,
                 aim_x: float, aim_y: float, now: int) -> tuple:
    """衝刺：client 端位移預測同 _default_space_dash，另通知 server 供對手端音效同步。"""
    length = math.hypot(dx, dy)
    if length == 0:
        return False, dx, dy, 1.0
    ndx = dx / length
    ndy = dy / length
    st.dash_active            = True
    st.dash_dx                = ndx
    st.dash_dy                = ndy
    st.dash_speed             = _DASH_V0 - _DASH_DECEL
    st.skill_last_ms['space'] = now
    speed_mult = _DASH_V0 / max(st.player_speed, 0.001)
    return True, ndx, ndy, speed_mult


def _default_space_dash(st: InputState, dx: float, dy: float,
                        aim_x: float, aim_y: float, now: int) -> tuple:
    """預設：純 client 端衝刺，不通知 server（use_skill_space=False）。"""
    length = math.hypot(dx, dy)
    if length == 0:
        return False, dx, dy, 1.0
    ndx = dx / length
    ndy = dy / length
    st.dash_active            = True
    st.dash_dx                = ndx
    st.dash_dy                = ndy
    st.dash_speed             = _DASH_V0 - _DASH_DECEL
    st.skill_last_ms['space'] = now
    speed_mult = _DASH_V0 / max(st.player_speed, 0.001)
    return False, ndx, ndy, speed_mult


# Pioneer 與 Zombie 共用 handler：兩者技能概念完全相同（跳躍起跳 + 補滿彈夾）。
# Vince 與 Marksman 各自獨立：目前程式碼相同，但設計意圖不同（嘲諷 vs 衝刺）。
# Assassin：no-op 佔位，避免 fallthrough 到 _default_space_dash。
_SPACE_HANDLERS: dict = {
    'Agent':    _space_agent,
    'Vince':    _space_vince,
    'Marksman': _space_marksman,
    'Hunter':   _space_hunter,
    'Pioneer':  _space_pioneer_zombie,
    'Zombie':   _space_pioneer_zombie,
    'Robot':    _space_robot,
    'Assassin': _space_assassin_noop,
    'Poisoner': _space_poisoner,
}


# ─────────────────────────────────────────────────────────────────────────────
# init_char / init_rune
# ─────────────────────────────────────────────────────────────────────────────

def init_char(char_name: str) -> None:
    """遊戲開始後呼叫，依選擇角色完整重置並設定所有 client 端狀態。"""
    global _state, SHOOT_COOLDOWN_MS, MAGAZINE_SIZE, RELOAD_TIME_MS

    from game.char_data import get_stat, CHAR_STATS

    interval  = get_stat(char_name, "fire_interval")
    shoot_cd  = int(interval * 1000) if interval and interval > 0 else 9999

    mag_str = get_stat(char_name, "mag")
    mag     = int(mag_str) if mag_str and str(mag_str).strip().isdigit() else 9999

    reload_s  = get_stat(char_name, "reload_time")
    reload_ms = int(reload_s * 1000) if reload_s and reload_s > 0 else 99999

    player_speed = float(CHAR_STATS.get(char_name, {}).get('speed', 3.0))

    cfg = CHAR_STATS.get(char_name, {})
    def _cd(key: str) -> int:
        v = float(cfg.get(key, 0))
        return int(v * 1000) if v > 0 else -1

    skill_cds = {
        'rmb':   _cd('cd_rmb'),
        'space': _cd('cd_space'),
        'e':     _cd('cd_e'),
        'r':     _cd('cd_r'),
        'q':     -1,   # 由 init_rune 設定
    }
    now_ms = pygame.time.get_ticks()
    skill_last = {
        slot: (now_ms - cd - 1) if cd >= 0 else 0
        for slot, cd in skill_cds.items()
    }

    # 一行重建 InputState → 所有欄位自動回到預設值，只需覆蓋角色相關設定
    _state = InputState(
        char_name         = char_name,
        shoot_cooldown_ms = shoot_cd,
        magazine_size     = mag,
        reload_time_ms    = reload_ms,
        current_reload_ms = reload_ms,
        player_speed      = player_speed,
        skill_cds_ms      = skill_cds,
        skill_last_ms     = skill_last,
        ammo              = mag,
    )

    # 同步 module-level 常數，維持 renderer.py 的 from-import 向後相容
    SHOOT_COOLDOWN_MS = shoot_cd
    MAGAZINE_SIZE     = mag
    RELOAD_TIME_MS    = reload_ms


def init_rune(rune_id: int) -> None:
    """選角確認後呼叫（在 init_char 之後）。
    rune_id: 0=一般恢復, 1=強化恢復, 2=血量上限（被動，Q 鍵無效）。
    """
    _state.rune_id = rune_id
    _state.q_prev  = False
    if rune_id == 2:   # 血量上限：被動，Q 無動作
        _state.skill_cds_ms['q']  = -1
        _state.skill_last_ms['q'] = 0
    else:              # 一般恢復 / 強化恢復：20s CD，遊戲開始即可用
        _state.skill_cds_ms['q']  = 20_000
        _state.skill_last_ms['q'] = pygame.time.get_ticks() - 20_001


# ─────────────────────────────────────────────────────────────────────────────
# read_input
# ─────────────────────────────────────────────────────────────────────────────

def read_input(player_id: int, keys_held: set,
               logical_mouse: tuple,
               shift_held: bool,
               suppress_lmb: bool = False,
               is_stunned: bool = False) -> tuple:
    """
    回傳 (PlayerCommand, effective_stance, ammo, is_reloading, skill_cooldowns)

    skill_cooldowns : {'space':(remaining_ms, max_ms), 'e':..., 'r':..., 'rmb':..., 'q':...}
                      remaining_ms == -1  → 技能尚未實作
    """
    from game.render_utils import LOGICAL_W, LOGICAL_H
    now = pygame.time.get_ticks()

    # ── 排程音效（例如錯開發射的連續彈丸）────────────────────────────────
    if _state.pending_sfx:
        still_pending = []
        for due_ms, relpath in _state.pending_sfx:
            if now >= due_ms:
                audio.play(relpath, audio.VOLUME_SELF)
            else:
                still_pending.append((due_ms, relpath))
        _state.pending_sfx = still_pending

    # ── 換彈完成判斷 ──────────────────────────────────────────────────────
    if _state.reloading and (now - _state.reload_start_ms) >= _state.current_reload_ms:
        _state.reloading = False
        _state.ammo      = _state.magazine_size

    from game.char_data import CHAR_STATS as _cs
    _default_sprite  = _cs.get(_state.char_name, {}).get('sprite', 'machine')
    effective_stance = "reload" if _state.reloading else _default_sprite

    lx, ly            = logical_mouse
    aim_x             = float(lx - LOGICAL_W // 2)
    aim_y             = float(ly - LOGICAL_H // 2)
    _state.last_aim_x = aim_x
    _state.last_aim_y = aim_y

    # ── 按鍵上升緣偵測 ────────────────────────────────────────────────────
    space_held         = pygame.K_SPACE in keys_held
    space_just_pressed = space_held and not _state.space_prev
    _state.space_prev  = space_held

    e_held             = pygame.K_e in keys_held
    e_just_pressed     = e_held and not _state.e_prev
    _state.e_prev      = e_held

    rmb_held           = pygame.mouse.get_pressed()[2]
    rmb_just_pressed   = rmb_held and not _state.rmb_prev
    rmb_just_released  = not rmb_held and _state.rmb_prev
    _state.rmb_prev    = rmb_held

    r_held             = pygame.K_r in keys_held
    r_just_pressed     = r_held and not _state.r_prev
    _state.r_prev      = r_held

    f_held             = pygame.K_f in keys_held
    f_just_pressed     = f_held and not _state.f_prev
    _state.f_prev      = f_held

    q_held             = pygame.K_q in keys_held
    q_just_pressed     = q_held and not _state.q_prev
    _state.q_prev      = q_held

    # ── 衍生狀態（每幀計算，不持久化）────────────────────────────────────
    r_skill_active      = (_state.r_skill_start_ms > 0
                           and (now - _state.r_skill_start_ms) < 500)
    giant_frozen        = (_state.giant_age >= 0
                           and not (GROW_TICKS <= _state.giant_age < GROW_TICKS + ACTIVE_TICKS))
    _mercury_ult_active = _state.char_name == 'Agent' and now < _state.mercury_end_ms
    _zombie_spit_active = _state.char_name == 'Zombie' and now < _state.zombie_spit_end_ms

    # ── 位移 / speed_mult 初始化 ──────────────────────────────────────────
    dx, dy          = 0.0, 0.0
    speed_mult      = 1.0
    use_skill_space = False
    robot_recall    = False

    # ── Robot 印記回傳（可在衝刺中觸發，需先於主要位移處理）────────────
    if (_state.char_name == 'Robot'
            and space_just_pressed
            and _state.robot_mark_until_ms > now):
        use_skill_space            = True
        _state.robot_mark_until_ms = 0
        robot_recall               = True

    # ── 衝刺中：繼續推進衝刺位移 ─────────────────────────────────────────
    if _state.dash_active:
        if _state.dash_dist_remaining > 0:
            # 等速衝刺：障礙物碰撞時立即中止
            from game.state import PLAYER_RADIUS as _PR
            hit_obs = any(
                obs.collides_circle(_state.dash_player_x, _state.dash_player_y, _PR)
                for oid, obs in _state.dash_obstacles.items()
                if oid not in _state.dash_destroyed
            )
            if hit_obs:
                _state.dash_active         = False
                _state.dash_dist_remaining = 0.0
            else:
                speed_mult                  = _RAMBO_DASH_SPEED / max(_state.player_speed, 0.001)
                dx, dy                      = _state.dash_dx, _state.dash_dy
                _state.dash_dist_remaining -= _RAMBO_DASH_SPEED
                if _state.dash_dist_remaining <= 0:
                    _state.dash_active         = False
                    _state.dash_dist_remaining = 0.0
        elif _state.dash_speed < _DASH_MIN_SPEED:
            _state.dash_active = False
        else:
            speed_mult         = _state.dash_speed / max(_state.player_speed, 0.001)
            dx, dy             = _state.dash_dx, _state.dash_dy
            _state.dash_speed -= _DASH_DECEL

    # ── WASD 移動 + Space 技能（不在衝刺 / 巨人凍結 / 連射中 / 暈眩中 / Zombie 吐息僵直中）──
    if (not _state.dash_active and not giant_frozen and not _state.burst_shots_left
            and not _zombie_spit_active):
        if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
        if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
        if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
        if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

        if (not is_stunned
                and not r_skill_active
                and not _mercury_ult_active
                and space_just_pressed
                and not robot_recall
                and _state.skill_cds_ms.get('space', -1) >= 0):
            cd_remaining = (_state.skill_cds_ms['space']
                            - (now - _state.skill_last_ms['space']))
            if cd_remaining <= 0:
                handler = _SPACE_HANDLERS.get(_state.char_name)
                if handler:
                    use_skill_space, dx, dy, speed_mult = handler(
                        _state, dx, dy, aim_x, aim_y, now)
                else:
                    use_skill_space, dx, dy, speed_mult = _default_space_dash(
                        _state, dx, dy, aim_x, aim_y, now)

    running = shift_held and not _state.dash_active

    # ── Robot E 旋轉標誌回傳（繞過冷卻，需先於主要 E 區塊）─────────────
    use_skill_e    = False
    robot_e_recall = False
    if (_state.char_name == 'Robot'
            and e_just_pressed
            and _state.robot_e_mark_until_ms > now):
        use_skill_e                    = True
        _state.robot_e_mark_until_ms   = 0
        robot_e_recall                 = True

    # ── E 技能 ────────────────────────────────────────────────────────────
    if (not robot_e_recall
            and not is_stunned
            and not r_skill_active and not giant_frozen and not _state.burst_shots_left
            and not _mercury_ult_active and not _zombie_spit_active
            and e_just_pressed
            and _state.skill_cds_ms.get('e', -1) >= 0):
        cd_remaining = _state.skill_cds_ms['e'] - (now - _state.skill_last_ms['e'])
        if cd_remaining <= 0:
            use_skill_e = True
            _state.skill_last_ms['e'] = now
            if _state.char_name == 'Robot':
                _state.robot_e_mark_until_ms = now + 4000

    # ── RMB 技能（Vince：蓄力放開；其他：按下即發）───────────────────────
    use_skill_rmb = False
    if (not is_stunned
            and not r_skill_active and not giant_frozen and not _state.burst_shots_left
            and not _mercury_ult_active and not _zombie_spit_active
            and _state.skill_cds_ms.get('rmb', -1) >= 0):
        rmb_cd_ms = _state.skill_cds_ms['rmb']
        if _state.char_name == 'Vince':
            cd_ok = (rmb_cd_ms - (now - _state.skill_last_ms['rmb'])) <= 0
            if rmb_just_pressed and cd_ok:
                _state.r_holding = True
            if rmb_just_released and _state.r_holding:
                use_skill_rmb = True
                _state.skill_last_ms['rmb'] = now
            if rmb_just_released:
                _state.r_holding = False
        else:
            if rmb_just_pressed and (rmb_cd_ms - (now - _state.skill_last_ms['rmb'])) <= 0:
                use_skill_rmb = True
                _state.skill_last_ms['rmb'] = now
    elif is_stunned and rmb_just_released:
        # 暈眩中放開 RMB：清除 Vince 蓄力狀態，但不觸發技能
        _state.r_holding = False

    # ── Assassin Space：速度提升（可在衝刺中觸發，獨立於主要 Space 區塊）─
    if (not is_stunned
            and not r_skill_active and not giant_frozen
            and _state.char_name == 'Assassin'
            and space_just_pressed
            and _state.skill_cds_ms.get('space', -1) >= 0):
        if (now - _state.skill_last_ms['space']) >= _state.skill_cds_ms['space']:
            use_skill_space               = True
            _state.skill_last_ms['space'] = now
            _state.speed_boost_end_ms     = now + 2000

    # ── F 鍵：大招（按下即發）────────────────────────────────────────────
    use_skill_r = False
    if (not is_stunned
            and not r_skill_active and not giant_frozen and not _state.burst_shots_left
            and not _mercury_ult_active and not _zombie_spit_active
            and _state.skill_cds_ms.get('r', -1) >= 0):
        if f_just_pressed and (_state.skill_cds_ms['r'] - (now - _state.skill_last_ms['r'])) <= 0:
            use_skill_r = True
            _state.skill_last_ms['r'] = now
            if _state.char_name == 'Assassin':
                _state.r_skill_start_ms    = now
                _state.r_skill_start_angle = math.degrees(math.atan2(aim_x, -aim_y))
            if _state.char_name == 'Agent':
                _state.mercury_end_ms   = now + int(_MERCURY_ULT_TICKS * 1000 / 60) + 150  # duration + safety margin
                _state.mercury_aim_angle = math.degrees(math.atan2(aim_x, -aim_y))
            if _state.char_name == 'Zombie':
                _state.zombie_spit_end_ms = now + int(_ZOMBIE_SPIT_TICKS * 1000 / 60) + 150

    # ── R 鍵：手動換彈 ────────────────────────────────────────────────────
    _NO_RELOAD = {'Robot', 'Assassin', 'Zombie'}
    if (r_just_pressed
            and not _state.reloading
            and _state.char_name not in _NO_RELOAD
            and _state.ammo < _state.magazine_size):
        if _state.char_name == 'Vince':
            _state.current_reload_ms = (_state.magazine_size - _state.ammo) * 500
        elif _state.char_name == 'Hunter':
            _state.current_reload_ms = (_state.magazine_size - _state.ammo) * 1000
        else:
            _state.current_reload_ms = _state.reload_time_ms
        _state.reloading       = True
        _state.reload_start_ms = now
        reload_sfx = _RELOAD_SFX.get(_state.char_name)
        if reload_sfx:
            audio.play(reload_sfx, audio.VOLUME_SELF)

    # ── Q 鍵：啟動魔紋（血量上限為被動，cd=-1 不觸發）───────────────────
    use_rune = False
    if (q_just_pressed and _state.skill_cds_ms.get('q', -1) >= 0
            and not giant_frozen and not _state.burst_shots_left
            and not _zombie_spit_active):
        cd_remaining = _state.skill_cds_ms['q'] - (now - _state.skill_last_ms['q'])
        if cd_remaining <= 0:
            use_rune = True
            _state.skill_last_ms['q'] = now

    # ── 射擊（換彈中禁止 / R 技能期間禁止 / 連射中禁止 / 暈眩中禁止）────
    shooting = False
    if (not suppress_lmb
            and not _mercury_ult_active
            and not _zombie_spit_active
            and not _state.reloading
            and not r_skill_active
            and not _state.burst_shots_left
            and not is_stunned
            and pygame.mouse.get_pressed()[0]
            and (now - _state.last_shot_time) >= _state.shoot_cooldown_ms):
        shooting              = True
        _state.last_shot_time = now
        if _state.char_name == 'Agent':
            audio.play(random.choice(_AGENT_PISTOL_SFX), audio.VOLUME_SELF)
        elif _state.char_name == 'Pioneer':
            audio.play(random.choice(_PIONEER_RIFLE_SFX), audio.VOLUME_SELF)
        elif _state.char_name == 'Marksman':
            audio.play(random.choice(_MARKSMAN_MACHINE_SFX), audio.VOLUME_SELF)
        elif _state.char_name == 'Hunter':
            audio.play(_HUNTER_SNIPER_SFX, audio.VOLUME_SELF)
        elif _state.char_name == 'Assassin':
            for pellet_i in range(_ASSASSIN_PELLET_COUNT):
                due_ms = now + pellet_i * _ASSASSIN_PELLET_INTERVAL_MS
                _state.pending_sfx.append((due_ms, random.choice(_ASSASSIN_SHURIKEN_SFX)))
        elif _state.char_name == 'Vince':
            audio.play(random.choice(_VINCE_SHOTGUN_SFX), audio.VOLUME_SELF)
        elif _state.char_name == 'Zombie':
            audio.play(random.choice(_ZOMBIE_MOAN_SFX), audio.VOLUME_SELF)
        if _state.magazine_size < 9999:
            _state.ammo -= 1
            if _state.ammo <= 0:
                _state.ammo              = 0
                _state.reloading         = True
                _state.reload_start_ms   = now
                _state.current_reload_ms = _state.reload_time_ms
                reload_sfx = _RELOAD_SFX.get(_state.char_name)
                if reload_sfx:
                    audio.play(reload_sfx, audio.VOLUME_SELF)

    # ── 技能冷卻資訊（給 HUD）────────────────────────────────────────────
    skill_cooldowns: dict = {}
    for slot in ('space', 'e', 'r', 'rmb', 'q'):
        max_cd = _state.skill_cds_ms.get(slot, -1)
        if max_cd < 0:
            skill_cooldowns[slot] = (-1, -1)
        else:
            remaining = max_cd - (now - _state.skill_last_ms[slot])
            skill_cooldowns[slot] = (max(0, remaining), max_cd)

    cmd = PlayerCommand(
        player_id       = player_id,
        move_x          = dx,
        move_y          = dy,
        shooting        = shooting,
        aim_x           = aim_x,
        aim_y           = aim_y,
        running         = running,
        stance          = effective_stance,
        speed_mult      = speed_mult,
        use_skill_e     = use_skill_e,
        use_skill_rmb   = use_skill_rmb,
        use_skill_space = use_skill_space,
        use_skill_r     = use_skill_r,
        use_rune        = use_rune,
        rmb_held        = rmb_held,
    )
    return cmd, effective_stance, _state.ammo, _state.reloading, skill_cooldowns
