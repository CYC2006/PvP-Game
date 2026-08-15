from dataclasses import dataclass, field
from enum import IntEnum
import bisect
import math
import random

MAP_WIDTH  = 1920
MAP_HEIGHT = 1080

# Portal teleport constants (used only on Portal map)
PORTAL_Y_MIN = 240
PORTAL_Y_MAX = 480
PORTAL_COOLDOWN_TICKS = 90   # 1.5 s at 60 Hz — prevents instant re-entry


def configure_map(width: int, height: int) -> None:
    """Update global map dimensions when loading a different map."""
    global MAP_WIDTH, MAP_HEIGHT
    MAP_WIDTH  = width
    MAP_HEIGHT = height

KB_FORCE   = 10.0   # standard knockback initial speed (px/tick); ~45 px total displacement
KB_DECAY   = 0.78   # per-tick multiplier (shared with step_knockback)
KB_STOP    = 0.3    # stop threshold

PLAYER_SPEED     = 3.0
PLAYER_RADIUS    = 16
BULLET_SPEED     = 8.0
BULLET_RADIUS    = 5
DEFAULT_MAX_HP   = 100      # 預設血量（未設定角色時使用）
BULLET_MAX_RANGE = 900


class BType(IntEnum):
    """子彈類型常數（取代散落各處的魔術數字）。"""
    NORMAL       = 0
    FLASH        = 1   # 閃光彈（Agent E）
    GRENADE      = 2   # 手榴彈（Vince E）
    SHURIKEN     = 3   # 手裡劍（Assassin RMB）
    SMOKE        = 4   # 煙霧彈（Assassin E）
    MINI_GRENADE = 5   # 迷你手雷（Hunter Space）
    STUN         = 6   # 暈眩彈（Pioneer RMB）
    EXPLOSION    = 7   # 爆炸彈（Marksman RMB）
    POISON_BALL  = 8   # 毒液彈（Poisoner RMB）
    ROBOT_LASER  = 9   # Robot 普攻視覺樣式（黃色雷射矩形，行為與一般子彈相同）


# 穿透牆壁/屏障的子彈類型集合（投擲物、手裡劍、毒氣泡）
_THROWABLE: frozenset = frozenset({
    BType.FLASH, BType.GRENADE, BType.SHURIKEN,
    BType.SMOKE, BType.MINI_GRENADE,
})

# 不造成接觸傷害的子彈類型集合（傷害由爆炸/觸發效果處理）
_NON_CONTACT: frozenset = frozenset({
    BType.FLASH, BType.GRENADE, BType.MINI_GRENADE,
    BType.STUN, BType.EXPLOSION, BType.POISON_BALL,
})

# 碰觸玩家即觸發的特殊彈（傷害/效果在 expiry 時處理）
_TRIGGER_ON_TOUCH: frozenset = frozenset({
    BType.STUN, BType.EXPLOSION, BType.POISON_BALL,
})


@dataclass
class Player:
    id: int
    x: float
    y: float
    speed: float        = PLAYER_SPEED
    hp: int             = DEFAULT_MAX_HP
    max_hp: int         = DEFAULT_MAX_HP   # 依角色設定，respawn 恢復到此值
    spawn_x: float      = 0.0             # 記錄初始出生 x，respawn 回此處
    damage_min: int     = 1                # 子彈最小傷害（由 server 依角色設定）
    damage_max: int     = 1                # 子彈最大傷害
    bullet_speed: float = BULLET_SPEED    # 子彈速度（像素/tick），依角色設定
    spread: float       = 5.0             # 子彈最大偏角（±度），依角色設定
    pellet_count: int    = 1               # 散彈槍：一次發射的子彈數量
    pellet_interval: float = 0.0          # >0：各散彈之間的發射間隔（tick，支援 0.5 = 2發/tick）
    bullet_range: float = BULLET_MAX_RANGE  # 子彈最大射程（px）
    bullet_range_min: float = 0           # >0 時每顆散彈隨機射程 [min, range]
    bullet_decel: float  = 0.0            # 毒氣泡等：每 tick 減速量（px/tick²）
    bullet_linger: int   = 0             # 停止後存活 tick 數（0 = 停止即消失）
    bullet_speed_min: float = 0.0        # >0 時每顆子彈初速在 [min, speed] 間隨機
    dot_interval: int   = 0             # >0：穿透玩家，每 N tick 傷害一次（DoT 子彈）
    shoot_slow: float       = 1.0   # 射擊時的移動速度倍率（0~1，1=無懲罰）
    _shoot_slow_ticks: int  = 0     # 每次射擊後減速持續 tick 數（= fire_interval × 60）
    _shoot_slow_timer: int  = 0     # 當前剩餘減速 tick（>0 表示正在減速中）
    aim_angle: float        = 0.0   # 瞄準角度（度），0=上, 90=右；同步給對手
    stance: str             = "stand"  # "stand" | "machine" | "hold" | "reload"
    flash_ticks: int        = 0     # >0：被閃光彈影響，倒數至 0
    speed_boost_ticks: int  = 0     # >0：速度提升中，倒數至 0（Assassin space）
    speed_boost_mult: float = 1.0   # 速度提升倍率
    char_name: str          = ""    # 角色名稱，由 apply_char_stats 設定，不同步至 client
    # ── 魔紋狀態 ──────────────────────────────────────────────────
    rune_id: int              = 0   # 0=一般恢復 1=強化恢復 2=血量上限
    rune_cd_until: int        = -1  # server tick when rune CD expires（-1=無 CD）
    rune_recovery_ticks: int  = 0   # 一般恢復剩餘 tick（>0 生效, ≤0 非啟動）
    base_max_hp: int          = 0   # 原始血量上限（血量上限魔紋boost 前）
    # ── Vince R 技能狀態（巨大化）────────────────────────────────────
    stun_until: int            = -1   # tick when stun ends (-1 = not stunned)
    burst_next_tick: int       = -1   # tick to fire next burst shot (-1 = inactive)
    burst_shots_fired: int     = 0    # shots fired so far in current burst
    burst_aim_x: float         = 0.0  # locked aim direction for burst
    burst_aim_y: float         = 0.0
    giant_tick: int            = -1   # tick when giant mode started (-1 = inactive)
    speed_penalty: float       = 1.0  # 通用速度懲罰倍率（由角色技能模組每 tick 設定，預設 1.0 = 無懲罰）
    kb_vx: float               = 0.0  # 擊退速度 x（px/tick，每 tick 衰減）
    kb_vy: float               = 0.0  # 擊退速度 y
    clone_until: int           = -1   # tick when soldier clones expire (-1 = inactive)
    cloak_until: int           = -1   # tick when sniper cloak expires (-1 = inactive)
    jump_tick: int             = -1   # tick when soldier jump started (-1 = not jumping)
    jump_dx: float             = 0.0  # normalized jump direction x
    jump_dy: float             = 0.0  # normalized jump direction y
    # ── Marksman Space 技能狀態（前衝）──────────────────────────────
    vince_dash_tick: int      = -1   # tick when dash started (-1 = inactive)
    vince_dash_dx: float      = 0.0  # normalized dash direction x
    vince_dash_dy: float      = 0.0  # normalized dash direction y
    # ── Vince Space 技能狀態（嘲諷）─────────────────────────────────
    vince_taunt_tick: int     = -1   # tick when taunt started (-1 = inactive)
    # ── 被嘲諷吸引狀態（任意角色可持有）──────────────────────────────
    pull_source_id: int       = -1   # player id pulling this player (-1 = none)
    pull_speed: float         = 0.0  # px/tick
    # ── Zombie Space 技能狀態（跳躍衝擊）────────────────────────────
    zombie_jump_tick: int   = -1   # tick when zombie jump started (-1 = inactive)
    zombie_jump_dx: float   = 0.0  # normalized jump direction x
    zombie_jump_dy: float   = 0.0  # normalized jump direction y
    # ── Zombie RMB 技能狀態（腐蝕吐息，完全僵直）─────────────────────
    zombie_spit_tick: int       = -1   # tick when spit started (-1 = inactive)
    zombie_spit_aim_x: float    = 0.0  # locked aim direction x（施放當下鎖定）
    zombie_spit_aim_y: float    = 0.0
    zombie_spit_wave_fired: int = 0    # waves fired so far (0~WAVE_COUNT)
    zombie_spit_hit_enemy: bool = False  # 本次施放是否已暈眩過對手（一次施放只暈眩一次）
    # ── Zombie E 技能狀態（嗜血 Bloodlust，無僵直）────────────────────
    zombie_rage_tick: int       = -1   # tick when bloodlust started (-1 = inactive)
    # ── Zombie 普攻（血刃 blade arc）：6 片刀片視為同一次攻擊 ───────────
    zombie_blade_hit_player:   bool = False  # 本次普攻是否已對玩家造成過傷害
    zombie_blade_hit_obstacle: bool = False  # 本次普攻是否已對障礙物造成過傷害
    # ── Zombie RMB 體力衝刺 ─────────────────────────────────────────
    zombie_energy:      float = 300.0  # 0~300，按住 RMB 消耗、放開回復
    zombie_base_speed:  float = 0.0    # 由 apply_char_stats 記錄，供放開 RMB 時還原
    # ── Assassin R 技能狀態 ───────────────────────────────────────
    r_skill_phase: int        = 0    # 0=inactive 1=phase1 2=phase2
    r_skill_tick: int         = 0    # 當前階段已過 ticks
    r_skill_dx: float         = 0.0  # 第一段滑動方向 x（單位向量）
    r_skill_dy: float         = 0.0  # 第一段滑動方向 y
    r_skill_start_angle: float = 0.0 # 技能啟動時的 aim_angle
    r_skill_dmg_done: int     = 0    # bitmask: 1=phase1 已傷害, 2=phase2 已傷害
    # ── Assassin E：煙霧彈施放（欄位僅供雙方端音效同步用）────────────────
    assassin_smoke_tick: int  = -1   # tick when smoke grenade E was cast (-1 = inactive)
    # ── Poisoner 毒素層數系統 ──────────────────────────────────────────
    poison_stacks: int        = 0    # 當前毒素層數（0~5）
    _poison_last_tick: int    = -1   # 上次受到毒素傷害的 tick（-1=從未）
    _poison_stk_dmg_timer: int = 0  # 每秒傷害計時器（60 tick → 造成一次）
    _poison_src_normal: int   = 0   # 普攻已貢獻層數（上限 1）
    _poison_src_rmb: int      = 0   # RMB 毒液池已貢獻層數（上限 2）
    _poison_src_space_pool: int = 0 # Space 小毒液池已貢獻層數（上限 2）
    _poison_src_e: int        = 0   # E 衝擊波已貢獻層數（上限 2）
    # ── Poisoner Space 技能狀態 ────────────────────────────────────────
    poisoner_space_until: int           = -1  # 技能結束 tick（-1=未啟動）
    poisoner_space_last_pool_tick: int  = -1  # 上次生成小池的 tick
    poisoner_space_pool_count: int      = 0   # 本次已生成小池數
    # ── Poisoner E 技能狀態 ────────────────────────────────────────────
    poisoner_e_until: int               = -1  # 技能結束 tick（-1=未啟動）
    poisoner_e_last_check_tick: int     = -1  # 上次 30-tick 檢查的 tick
    poisoner_e_check_count: int         = 0   # 本次已檢查次數
    poisoner_e_shockwave_seq: int       = 0   # 每次釋放衝擊波時遞增（供 client FX 偵測）
    # ── Agent 大招：水銀彈幕 ───────────────────────────────────────────────────
    mercury_start_tick: int   = -1   # -1=inactive; tick when barrage started
    mercury_aim_x: float      = 0.0  # locked aim direction (unit vector)
    mercury_aim_y: float      = 0.0
    mercury_volley_fired: int = 0    # volleys fired so far (0–7)
    # ── Agent Space：衝刺（純位移，欄位僅供對手端音效同步用）──────────────────
    agent_dash_tick: int      = -1   # tick when dash started (-1 = inactive)
    # ── Hunter RMB 空氣炮命中序號 ─────────────────────────────────────────────
    air_cannon_hit_seq: int   = 0    # increments each time owner's air cannon hits; client resets RMB CD
    # ── Server-side 射速限制 ──────────────────────────────────────────────────
    last_shot_tick: int       = -9999  # tick of last successful shot spawn
    fire_interval_ticks: int  = 0      # min ticks between shots（由 apply_char_stats 設定）

    def move(self, dx: float, dy: float, speed_mult: float = 1.0) -> None:
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length > 0:
            dx, dy = dx / length, dy / length
        speed = self.speed * speed_mult
        self.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS, self.x + dx * speed))
        self.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS, self.y + dy * speed))

    def respawn(self) -> None:
        self.hp = self.max_hp
        self.x  = self.spawn_x if self.spawn_x else float(MAP_WIDTH // 4 if self.id == 1 else MAP_WIDTH * 3 // 4)
        self.y  = float(MAP_HEIGHT // 2)
        self.poison_stacks         = 0
        self._poison_last_tick     = -1
        self._poison_stk_dmg_timer = 0
        self._poison_src_normal    = 0
        self._poison_src_rmb       = 0
        self._poison_src_space_pool = 0
        self._poison_src_e         = 0
        from game.chars.zombie.sprint_state import ENERGY_MAX
        self.zombie_energy = ENERGY_MAX


GOLD_RADIUS = 10   # 玩家撿取金錠的碰撞半徑


@dataclass
class GoldIngot:
    id: int
    x: float
    y: float
    kind: str = "gem"   # "gem" | "health"


@dataclass
class SmokePatch:
    id: int
    x: float
    y: float
    radius: float
    spawn_tick: int
    owner_id: int = 0


@dataclass
class BladeArc:
    id: int
    owner_id: int
    x: float           # current world position (updated each tick by server)
    y: float
    orbit_radius: float
    orbit_angle: float  # current orbit angle (radians)
    direction: int      # +1 = CW on screen (angle++), -1 = CCW
    damage: int         # pre-rolled 10~15
    age: int = 0
    hit: bool = False


@dataclass
class AirStrike:
    id: int
    owner_id: int
    cx: float
    cy: float
    spawn_tick: int


@dataclass
class PoisonPool:
    id:          int
    owner_id:    int
    x:           float
    y:           float
    spawn_tick:  int
    radius:      float = 150.0   # RMB 大池=150, Space 小池=20~30
    pool_source: str   = "rmb"  # "rmb" | "space"


@dataclass
class RobotMark:
    owner_id:   int
    x:          float
    y:          float
    spawn_tick: int


@dataclass
class RobotEMark:
    owner_id:    int
    center_x:    float
    center_y:    float
    start_angle: int     # degrees: 0, 90, 180, or 270
    spawn_tick:  int


@dataclass
class RobotERing:
    owner_id:   int
    x:          float
    y:          float
    spawn_tick: int


@dataclass
class PushZone:
    id:         int
    owner_id:   int
    x:          float
    y:          float
    angle:      float   # 朝滑鼠方向的角度（degrees，math 座標系）
    spawn_tick: int


@dataclass
class Mine:
    id:             int
    owner_id:       int
    x:              float
    y:              float
    triggered_tick: int = -1   # -1 = 等待中；>= 0 = 引爆倒數開始的 tick


@dataclass
class Turret:
    id:             int
    owner_id:       int
    x:              float
    y:              float
    hp:             int   = 180
    _passive_timer: int   = 0    # 被動扣血計時
    _fire_timer:    int   = 0    # 射擊冷卻計時（初始為 0 → 第一次偵測立即射擊）


@dataclass
class Shield:
    owner_id:    int
    hp:          int   = 120
    max_hp:      int   = 120
    spawn_tick:  int   = 0
    broken_tick: int   = -1   # -1 = 活躍中；>= 0 = 破壞/到期的 tick


@dataclass
class BarrageStrike:
    id:         int
    owner_id:   int
    x:          float
    y:          float
    spawn_tick: int   # tick when the shrink ring starts


@dataclass
class ZombieOrb:
    id:          int
    owner_id:    int
    x:           float
    y:           float
    radius:      float
    spawn_tick:  int
    expire_tick: int = -1   # tick when the orb disappears (server-only; unknown on client)
    fade:        int = 255  # 0-255 alpha multiplier；由 step_spit 逐 tick 更新，client 直接讀取
    hit_enemy:   bool = False  # 這顆球是否已命中過敵人（server-only；每顆球只造成一次傷害）


@dataclass
class LogBarrier:
    id:       int
    owner_id: int
    x:        float
    y:        float
    hp:       int
    radius:   float = 12.0


@dataclass
class AirCannon:
    id:           int
    owner_id:     int
    x:            float
    y:            float
    dx:           float        # velocity x (px/tick)
    dy:           float        # velocity y (px/tick)
    spawn_tick:   int
    dist_traveled: float = 0.0
    max_range:    float  = 400.0


@dataclass
class Bullet:
    id: int
    owner_id: int
    x: float
    y: float
    dx: float
    dy: float
    distance_travelled: float = 0.0
    aim_angle: float  = 0.0            # 飛行方向（度）atan2(dy,dx)，供 client 繪圖用
    max_range: float  = BULLET_MAX_RANGE  # 最大射程（px）
    decel: float      = 0.0            # 每 tick 減少的速度量（px/tick²）；0 = 等速
    linger_ticks: int = 0              # 停止後再存活的 tick 數（倒數至 0 才消失）
    dot_interval: int = 0              # >0：穿透玩家，每 N tick 傷害一次
    spawn_tick: int   = 0              # 建立時的 tick（DoT 半徑成長計算用）
    bubble_radius_max: float = 0.0     # DoT 泡泡最大碰撞半徑 px（由 server 亂數，client 同步）
    bullet_scale: float = 1.0          # 巨大化子彈：3.0（碰撞半徑與視覺同比放大）
    bullet_type: int  = 0              # 0=一般子彈  1=閃光彈
    has_knockback: bool = False        # True 僅限 Agent RMB 放大彈；Vince 大招子彈不觸發擊退

    def step(self) -> None:
        self.x += self.dx
        self.y += self.dy
        self.distance_travelled += math.hypot(self.dx, self.dy)
        if self.decel > 0:
            speed = math.hypot(self.dx, self.dy)
            if speed <= self.decel:
                self.dx = 0.0
                self.dy = 0.0
            else:
                factor = (speed - self.decel) / speed
                self.dx *= factor
                self.dy *= factor
        # 停止後 linger 倒數
        if self.decel > 0 and self.dx == 0.0 and self.dy == 0.0 and self.linger_ticks > 0:
            self.linger_ticks -= 1

    def is_expired(self) -> bool:
        if self.decel > 0 and self.dx == 0.0 and self.dy == 0.0:
            return self.linger_ticks == 0   # linger 倒數完才消失
        return (
            self.distance_travelled >= self.max_range
            or self.x < 0 or self.x > MAP_WIDTH
            or self.y < 0 or self.y > MAP_HEIGHT
        )


# ── 射擊行為 dispatch 表（char name → callable(state, pid, aim_x, aim_y)）──────
# 不在表中的角色使用預設普攻（_spawn_bullet）。
_SHOOT_HANDLERS: dict = {
    'Zombie': lambda s, pid, ax, ay: s._activate_blade_arc(pid, ax, ay),
}

# Robot 普攻沿用雷射視覺樣式（純外觀，碰撞/傷害規則與 NORMAL 相同），其餘角色用 NORMAL
_BULLET_TYPE_BY_CHAR: dict = {
    'Robot': BType.ROBOT_LASER,
}


@dataclass
class GameState:
    players: dict            = field(default_factory=dict)
    bullets: dict            = field(default_factory=dict)
    destroyed_obstacles: set = field(default_factory=set)
    gold_ingots: dict        = field(default_factory=dict)   # gid → GoldIngot
    gold_counts: dict        = field(default_factory=dict)   # pid → gem 撿取數（用於 client 觸發冷卻縮減）
    kill_counts: dict        = field(default_factory=dict)   # pid → 擊殺數
    lives: dict              = field(default_factory=dict)   # pid → 剩餘生命（deathmatch）
    game_mode: str           = "endless"                      # "endless" | "deathmatch"
    side_flip: bool          = False                          # True = pid1 在右側
    game_start_tick: int     = 0
    tick: int                = 0
    _next_bullet_id: int     = 0
    _next_gold_id: int       = 0
    _next_smoke_id: int      = 0
    _next_blade_id: int      = 0
    _dot_cooldown: dict      = field(default_factory=dict)   # {(bid, pid): next_hit_tick}
    _dot_keys_by_bid: dict   = field(default_factory=dict)   # bid → set of (bid,*) keys in _dot_cooldown
    _pending_pellets: list   = field(default_factory=list)   # sorted [(fire_tick, seq, Bullet)], earliest first
    _pending_seq: int        = 0                             # monotonic counter breaks fire_tick ties
    smoke_patches: dict      = field(default_factory=dict)   # sid → SmokePatch
    blade_arcs: dict         = field(default_factory=dict)   # bid → BladeArc
    _blade_spawn_queue: list = field(default_factory=list)   # [(spawn_tick, owner_id, x, y, radius, orbit_angle, direction, damage)]
    air_strikes: dict        = field(default_factory=dict)   # aid → AirStrike
    _next_airstrike_id: int  = 0
    log_barriers: dict       = field(default_factory=dict)   # lid → LogBarrier
    _next_log_id: int        = 0
    mines: dict              = field(default_factory=dict)   # mid → Mine
    _next_mine_id: int       = 0
    turrets: dict            = field(default_factory=dict)   # tid → Turret
    _next_turret_id: int     = 0
    barrage_strikes: dict    = field(default_factory=dict)   # sid → BarrageStrike
    _next_barrage_id: int    = 0
    _pending_barrage: list   = field(default_factory=list)   # server-only queue
    shields: dict            = field(default_factory=dict)   # owner_id → Shield
    _pending_shockwaves: list = field(default_factory=list)  # server-only expanding ring list
    poison_pools: dict       = field(default_factory=dict)   # ppid → PoisonPool
    _next_pool_id: int       = 0
    push_zones: dict         = field(default_factory=dict)   # pzid → PushZone
    _next_push_zone_id: int  = 0
    robot_marks: dict        = field(default_factory=dict)   # owner_id → RobotMark（每個 Robot 最多一筆）
    robot_e_marks: dict      = field(default_factory=dict)   # owner_id → RobotEMark
    robot_e_rings: dict      = field(default_factory=dict)   # owner_id → RobotERing
    air_cannons: dict        = field(default_factory=dict)   # cid → AirCannon
    _next_air_cannon_id: int = 0
    zombie_orbs: dict        = field(default_factory=dict)   # oid → ZombieOrb
    _next_zombie_orb_id: int = 0

    def add_player(self, player_id: int) -> "Player":
        left_x  = MAP_WIDTH  // 4
        right_x = MAP_WIDTH  * 3 // 4
        if self.side_flip:
            spawn_x = right_x if player_id == 1 else left_x
        else:
            spawn_x = left_x  if player_id == 1 else right_x
        spawn_y = MAP_HEIGHT // 2
        p = Player(id=player_id, x=float(spawn_x), y=float(spawn_y), spawn_x=float(spawn_x))
        self.players[player_id] = p
        return p

    def apply_char_stats(self, player_id: int, char_name: str,
                         rune_id: int = 0) -> None:
        """遊戲開始後由 server 呼叫，將角色數值及魔紋設定套用到 Player。"""
        from game.char_data import get_stat, CHAR_STATS
        if player_id not in self.players:
            return
        p = self.players[player_id]
        p.char_name    = char_name
        p.rune_id      = rune_id
        p.max_hp       = get_stat(char_name, "hp")
        p.base_max_hp  = p.max_hp   # 記錄原始血量上限（供魔紋回復計算）
        p.hp           = p.max_hp
        p.speed        = float(get_stat(char_name, "speed"))
        p.zombie_base_speed = p.speed
        p.damage_min   = get_stat(char_name, "damage_min")
        p.damage_max   = get_stat(char_name, "damage_max")
        p.bullet_speed = float(get_stat(char_name, "bullet_speed")) * BULLET_SPEED
        p.spread       = float(get_stat(char_name, "spread"))
        # 特殊武器專屬欄位（其他角色無此欄位時取預設值）
        char_cfg           = CHAR_STATS.get(char_name, {})
        p.pellet_count     = int(char_cfg.get("pellet_count", 1))
        p.bullet_range     = float(char_cfg.get("bullet_range", BULLET_MAX_RANGE))
        p.bullet_range_min = float(char_cfg.get("bullet_range_min", 0))
        # bullet_lifetime > 0：子彈線性減速，lifetime 秒後速度歸零消失
        lifetime = float(char_cfg.get("bullet_lifetime", 0))
        if lifetime > 0:
            tick_rate = 60
            p.bullet_decel = p.bullet_speed / (lifetime * tick_rate)
        else:
            p.bullet_decel = 0.0
        p.bullet_linger    = int(char_cfg.get("bullet_linger", 0) * 60)  # 秒→tick
        p.bullet_speed_min = float(char_cfg.get("bullet_speed_min", 0)) * BULLET_SPEED
        p.dot_interval       = int(char_cfg.get("dot_interval", 0))
        p.shoot_slow         = float(char_cfg.get("shoot_slow", 1.0))
        p._shoot_slow_ticks  = int(char_cfg.get("shoot_slow_dur", 0))
        p._shoot_slow_timer  = 0
        p.pellet_interval    = float(char_cfg.get("pellet_interval", 0.0))
        # server-side 最短射擊間隔（tick），防止重複封包造成連發
        fi = get_stat(char_name, "fire_interval")
        p.fire_interval_ticks = max(1, int(fi * 60)) if fi and fi > 0 else 1

        # 血量上限魔紋（rune_id=2）：遊戲開始即 +30% max_hp
        if rune_id == 2:
            p.max_hp = int(p.base_max_hp * 1.3)
        p.hp = p.max_hp   # 以最終 max_hp 滿血開始

    def apply_command(self, player_id: int, dx: float, dy: float,
                      shooting: bool, aim_x: float, aim_y: float,
                      running: bool = False, stance: str = "machine",
                      speed_mult: float = 1.0, rmb_held: bool = False) -> None:
        if player_id not in self.players:
            return
        player = self.players[player_id]
        # 暈眩中：忽略所有輸入
        if self.tick < player.stun_until:
            return
        # 巨大化進行中
        if player.giant_tick >= 0:
            from game.chars.vince.giant_state import GROW_TICKS, ACTIVE_TICKS
            _giant_age = self.tick - player.giant_tick
            if _giant_age < GROW_TICKS or _giant_age >= GROW_TICKS + ACTIVE_TICKS:
                # 放大 / 縮小階段：原地不動，不接受任何輸入
                if player._shoot_slow_timer > 0:
                    player._shoot_slow_timer -= 1
                return
        # R 技能進行中：禁止所有輸入，由 step_r_skill 驅動
        if player.r_skill_phase > 0:
            if player._shoot_slow_timer > 0:
                player._shoot_slow_timer -= 1
            return
        # Zombie F 鍵施放中（腐蝕吐息）：完全僵直，比照巨大化放大/縮小階段
        if player.zombie_spit_tick >= 0:
            if player._shoot_slow_timer > 0:
                player._shoot_slow_timer -= 1
            return
        # 隱身中（Sniper R）：移動速度 ×2，其他行為照常（可射擊、可用技能）
        if player.cloak_until > self.tick:
            # 強制覆蓋 speed_mult 為 2 倍（忽略 run / shoot_slow）
            if speed_mult == 1.0:   # 非技能位移時才覆蓋
                speed_mult = 2.0
        # 射擊觸發計時器；計時器倒數中套用移動懲罰（shoot_slow 優先於 run）
        if shooting:
            player._shoot_slow_timer = player._shoot_slow_ticks
        elif player._shoot_slow_timer > 0:
            player._shoot_slow_timer -= 1
        # Zombie RMB：體力衝刺（更新 player.speed，供下方 move() 使用）
        if player.char_name == 'Zombie':
            from game.chars.zombie.sprint_state import step_zombie_sprint
            step_zombie_sprint(player, rmb_held)
        if speed_mult != 1.0:
            mult = speed_mult          # 技能位移（衝刺等）：最高優先，不疊加 boost
        elif player._shoot_slow_timer > 0:
            mult = player.shoot_slow   # 射擊僵直：速度下降
        elif running:
            mult = 1.2                 # 跑步：速度 ×1.2
        else:
            mult = 1.0
        # 速度提升技能（Assassin space）：與 shoot_slow 疊加
        if player.speed_boost_ticks > 0 and speed_mult == 1.0:
            mult *= player.speed_boost_mult
        # 巨大化主動階段：移速 ×1.5
        if player.giant_tick >= 0 and speed_mult == 1.0:
            from game.chars.vince.giant_state import GROW_TICKS, ACTIVE_TICKS
            _ga = self.tick - player.giant_tick
            if GROW_TICKS <= _ga < GROW_TICKS + ACTIVE_TICKS:
                mult *= 1.5
        # 通用速度懲罰（由技能模組設定，如毒液區域 0.8）
        mult *= player.speed_penalty
        # 跳躍 / Vince 衝刺 / Zombie 跳躍中：由各自 step 控制位置，忽略普通移動輸入
        if player.jump_tick < 0 and player.vince_dash_tick < 0 and player.zombie_jump_tick < 0:
            player.move(dx, dy, speed_mult=mult)
        player.stance = stance
        # Mercury Barrage active: aim locked, LMB blocked
        if player.mercury_start_tick >= 0:
            return
        # 連射期間：禁止普攻（避免與連射子彈重疊）
        if player.burst_next_tick >= 0:
            shooting = False
        if math.hypot(aim_x, aim_y) > 0:
            player.aim_angle = math.degrees(math.atan2(aim_x, -aim_y))
        if shooting:
            # Server-side rate limiting：防止重複封包或客戶端異常造成連發
            if self.tick - player.last_shot_tick < player.fire_interval_ticks:
                shooting = False   # 本幀忽略，不產生子彈
        if shooting:
            player.last_shot_tick = self.tick
            fn = _SHOOT_HANDLERS.get(player.char_name)
            if fn:
                fn(self, player_id, aim_x, aim_y)
            else:
                self._spawn_bullet(player_id, aim_x, aim_y)
                # Pioneer R：分身同步射擊（只在普攻觸發，不在技能路徑）
                if player.clone_until > self.tick:
                    self._spawn_clone_bullets(player_id, aim_x, aim_y)

    def _spawn_bullet(self, owner_id: int, aim_x: float, aim_y: float,
                      bullet_scale_override: float = 0.0,
                      spread_override: float = -1.0,
                      has_knockback: bool = False) -> None:
        player = self.players[owner_id]
        length = math.hypot(aim_x, aim_y)
        if length == 0:
            return
        ux = aim_x / length
        uy = aim_y / length

        # 巨大化主動階段：子彈與射程放大 2 倍；可被 override 蓋過
        _barrel_scale = 1.0   # 槍口偏移只跟玩家視覺大小有關（巨人化才放大）
        if bullet_scale_override > 0:
            _bscale = bullet_scale_override
        else:
            _bscale = 1.0
            if player.giant_tick >= 0:
                from game.chars.vince.giant_state import GROW_TICKS, ACTIVE_TICKS
                _ga = self.tick - player.giant_tick
                if GROW_TICKS <= _ga < GROW_TICKS + ACTIVE_TICKS:
                    _bscale = 2.0
                    _barrel_scale = 2.0

        # 槍口偏移（巨人化時依縮放推遠，所有散彈共用同一出口）
        barrel_fwd   = (PLAYER_RADIUS + 10) * _barrel_scale
        barrel_right = 14 * _barrel_scale
        rx, ry = -uy, ux
        spawn_x = player.x + ux * barrel_fwd + rx * barrel_right
        spawn_y = player.y + uy * barrel_fwd + ry * barrel_right

        effective_spread = spread_override if spread_override >= 0 else player.spread
        for pellet_i in range(player.pellet_count):
            # 每顆散彈獨立隨機偏角
            pux, puy = ux, uy
            if effective_spread > 0:
                dev = math.radians(random.uniform(-effective_spread, effective_spread))
                cos_s, sin_s = math.cos(dev), math.sin(dev)
                pux = ux * cos_s - uy * sin_s
                puy = ux * sin_s + uy * cos_s

            # 初速隨機（bullet_speed_min > 0）；decel 固定，速度慢的飛得近
            if player.bullet_speed_min > 0:
                spd = random.uniform(player.bullet_speed_min, player.bullet_speed)
            else:
                spd = player.bullet_speed
            ndx = pux * spd
            ndy = puy * spd
            # 射程：減速子彈靠速度歸零消失，無需限制距離
            if player.bullet_decel > 0:
                pellet_range = BULLET_MAX_RANGE * 999
            elif math.isinf(player.bullet_range):
                pellet_range = player.bullet_range   # inf：子彈永遠不因距離消失
            elif player.bullet_range_min > 0:
                pellet_range = random.uniform(player.bullet_range_min, player.bullet_range) * _bscale
            else:
                pellet_range = player.bullet_range * _bscale
            while self._next_bullet_id in self.bullets:
                self._next_bullet_id = (self._next_bullet_id + 1) % 256
            bid = self._next_bullet_id
            self._next_bullet_id = (self._next_bullet_id + 1) % 256
            _btype = _BULLET_TYPE_BY_CHAR.get(player.char_name, BType.NORMAL)
            bullet = Bullet(
                id=bid, owner_id=owner_id,
                x=spawn_x, y=spawn_y,
                dx=ndx, dy=ndy,
                aim_angle=math.degrees(math.atan2(ndy, ndx)),
                max_range=pellet_range,
                decel=player.bullet_decel,
                linger_ticks=player.bullet_linger,
                dot_interval=player.dot_interval,
                spawn_tick=self.tick,
                bubble_radius_max=(
                    random.uniform(BULLET_RADIUS * 5, BULLET_RADIUS * 7)
                    if player.dot_interval > 0 else 0.0
                ),
                bullet_scale=_bscale,
                bullet_type=_btype,
                has_knockback=has_knockback,
            )
            # pellet_interval > 0：第一顆立即發射，其餘依 fire_tick 升序插入佇列
            if player.pellet_interval > 0 and pellet_i > 0:
                fire_tick = self.tick + pellet_i * player.pellet_interval
                import bisect
                bisect.insort(self._pending_pellets, (fire_tick, self._pending_seq, bullet))
                self._pending_seq += 1
            else:
                self.bullets[bid] = bullet

    def step_pending_pellets(self) -> None:
        """將佇列中到達發射時間的散彈加入戰場。
        _pending_pellets 保持依 fire_tick 升序排列，break 提前結束。
        """
        while self._pending_pellets and self._pending_pellets[0][0] <= self.tick:
            _, _seq, bullet = self._pending_pellets.pop(0)
            self.bullets[bullet.id] = bullet

    @staticmethod
    def _roll_damage(shooter) -> int:
        """Roll damage from shooter stats; returns 1 if shooter is None."""
        if shooter and shooter.damage_min < shooter.damage_max:
            return random.randint(shooter.damage_min, shooter.damage_max)
        return shooter.damage_min if shooter else 1

    def _handle_obstacle_drop(self, obs) -> None:
        """Spawn loot when an obstacle is destroyed."""
        if obs.kind == "box_special":
            self._spawn_gold(obs.x, obs.y)
        elif obs.kind == "box_normal":
            r = random.random()
            if r < 0.10:
                self._spawn_item(obs.x, obs.y, "gem")
            elif r < 0.20:
                self._spawn_item(obs.x, obs.y, "health")
            elif r < 0.25:
                self._spawn_item(obs.x, obs.y, "gem")
                self._spawn_item(obs.x, obs.y, "gem")
            elif r < 0.30:
                self._spawn_item(obs.x, obs.y, "health")
                self._spawn_item(obs.x, obs.y, "health")

    # ── step_bullets 輔助方法 ────────────────────────────────────────────────

    def _calc_coll_radius(self, bullet: "Bullet") -> float:
        """計算本 tick 的碰撞半徑（依子彈類型與成長狀態動態變化）。"""
        from game.chars.assassin.shuriken_state import SHURIKEN_GROW_RATE
        if bullet.bullet_type == BType.SHURIKEN:   # 手裡劍：半徑隨時間線性成長
            age = self.tick - bullet.spawn_tick
            return BULLET_RADIUS + age * SHURIKEN_GROW_RATE
        if bullet.dot_interval > 0 and bullet.bubble_radius_max > 0:   # 毒氣泡
            _BUBBLE_LIFE_TICKS = 120   # 2.0 s × 60 fps
            age    = self.tick - bullet.spawn_tick
            t_grow = min(1.0, age / _BUBBLE_LIFE_TICKS)
            return (BULLET_RADIUS * 2
                    + (bullet.bubble_radius_max - BULLET_RADIUS * 2) * t_grow)
        return float(BULLET_RADIUS) * bullet.bullet_scale   # 一般子彈

    def _bullet_vs_players(self, bullet: "Bullet", bid: int, coll_r: float,
                            does_damage: bool, shooter,
                            expired: list) -> bool:
        """子彈 vs 玩家碰撞。回傳 True 表示命中（子彈應停止繼續檢查障礙物）。"""
        from game.chars.assassin.shuriken_state import SHURIKEN_BASE_DMG, SHURIKEN_DMG_SCALE

        def _invincible(p: "Player") -> bool:
            return p.jump_tick >= 0 or p.zombie_jump_tick >= 0 or p.r_skill_phase > 0

        if bullet.dot_interval > 0:
            # DoT 子彈（毒氣泡）：穿透玩家，以動態半徑每 dot_interval tick 傷害一次
            for pid, player in self.players.items():
                if pid == bullet.owner_id or _invincible(player):
                    continue
                if math.hypot(bullet.x - player.x, bullet.y - player.y) < PLAYER_RADIUS + coll_r:
                    key = (bid, pid)
                    if self.tick >= self._dot_cooldown.get(key, 0):
                        damage = self._roll_damage(shooter)
                        if bullet.bullet_scale != 1.0:
                            damage = int(damage * bullet.bullet_scale)
                        if player.giant_tick >= 0:
                            damage = int(damage * 0.8)
                        self.apply_damage(pid, damage)
                        if shooter and shooter.char_name == 'Poisoner':
                            from game.chars.poisoner.poison_stack_state import add_poison_stack
                            add_poison_stack(self, pid, 'normal')
                        self._dot_cooldown[key] = self.tick + bullet.dot_interval
                        self._dot_keys_by_bid.setdefault(bid, set()).add(key)
            return False   # DoT 子彈不因碰到玩家而停止

        if does_damage:
            # 一般子彈：碰到玩家即消失
            for pid, player in self.players.items():
                if pid == bullet.owner_id or _invincible(player):
                    continue
                if math.hypot(bullet.x - player.x, bullet.y - player.y) < PLAYER_RADIUS + coll_r:
                    if bullet.bullet_type == BType.SHURIKEN:   # 手裡劍：傷害隨半徑線性成長
                        damage = int(SHURIKEN_BASE_DMG
                                     + SHURIKEN_DMG_SCALE * (coll_r - BULLET_RADIUS))
                    else:
                        damage = self._roll_damage(shooter)
                    if bullet.bullet_scale != 1.0:
                        damage = int(damage * bullet.bullet_scale)
                    if player.giant_tick >= 0:
                        damage = int(damage * 0.8)
                    self.apply_damage(pid, damage)
                    if bullet.has_knockback:
                        self.apply_knockback(pid, bullet.dx, bullet.dy)
                    expired.append(bid)
                    return True

        # 暈眩彈/爆炸彈/毒液彈：碰觸玩家即觸發（傷害由爆炸效果處理）
        if bullet.bullet_type in _TRIGGER_ON_TOUCH:
            for pid, player in self.players.items():
                if pid == bullet.owner_id or _invincible(player):
                    continue
                if math.hypot(bullet.x - player.x, bullet.y - player.y) < PLAYER_RADIUS + coll_r:
                    expired.append(bid)
                    return True

        return False

    def _bullet_vs_obstacles(self, bullet: "Bullet", bid: int, coll_r: float,
                              does_damage: bool, shooter,
                              obstacles: dict, obstacle_hp,
                              expired: list) -> None:
        """子彈 vs 地圖障礙物碰撞（可破壞障礙物）。"""
        for oid, obs in obstacles.items():
            if oid in self.destroyed_obstacles or not obs.solid:
                continue
            if obs.collides_circle(bullet.x, bullet.y, coll_r):
                if bullet.bullet_type in _THROWABLE or bullet.dot_interval > 0:
                    continue   # 投擲物 / 手裡劍 / 迷你手雷 / 毒氣泡穿透
                if obstacle_hp is not None and obs.destructible and does_damage \
                        and bullet.bullet_type != BType.POISON_BALL:   # 毒液彈不破壞障礙物
                    obstacle_hp[oid] -= self._roll_damage(shooter)
                    if obstacle_hp[oid] <= 0:
                        self.destroyed_obstacles.add(oid)
                        self._handle_obstacle_drop(obs)
                expired.append(bid)
                break

    def _bullet_vs_barriers(self, bullet: "Bullet", bid: int, coll_r: float,
                             does_damage: bool, shooter,
                             expired: list) -> None:
        """子彈 vs 木頭屏障碰撞（Hunter E 技能）。"""
        for lid in list(self.log_barriers):
            lb = self.log_barriers.get(lid)
            if lb is None:
                continue
            if math.hypot(bullet.x - lb.x, bullet.y - lb.y) < lb.radius + coll_r:
                if bullet.bullet_type in _THROWABLE or bullet.dot_interval > 0:
                    continue   # 投擲物 / 手裡劍 / 迷你手雷 / 毒氣泡穿透
                if does_damage and shooter:
                    lb.hp -= self._roll_damage(shooter)
                    if lb.hp <= 0:
                        self.log_barriers.pop(lid, None)
                expired.append(bid)
                break

    def _bullet_vs_turrets(self, bullet: "Bullet", bid: int, coll_r: float,
                            does_damage: bool, shooter,
                            expired: list) -> None:
        """子彈 vs 機槍台碰撞（敵方子彈才傷害）。"""
        from game.chars.marksman.turret_state import TURRET_HITBOX_R
        for tid in list(self.turrets):
            turret = self.turrets.get(tid)
            if turret is None or bullet.owner_id == turret.owner_id:
                continue
            if bullet.bullet_type in (1, 2, 3, 4, 5) or bullet.dot_interval > 0:
                continue   # 投擲物 / 手裡劍 / 迷你手雷 / 毒氣泡穿透
            if math.hypot(bullet.x - turret.x, bullet.y - turret.y) < TURRET_HITBOX_R + coll_r:
                if does_damage and shooter:
                    turret.hp -= self._roll_damage(shooter)
                    if turret.hp <= 0:
                        self.turrets.pop(tid, None)
                expired.append(bid)
                break

    def _trigger_bullet_expiry(self, b: "Bullet") -> None:
        """子彈消失時的副作用（爆炸、毒液池等）。"""
        # 停在地上 linger 結束後才引爆的投擲物
        if b.decel > 0 and b.dx == 0.0 and b.dy == 0.0:
            if b.bullet_type == BType.FLASH:
                self._trigger_flash_explosion(b.x, b.y, b.owner_id)
            elif b.bullet_type == BType.GRENADE:
                self._trigger_grenade_explosion(b.x, b.y, b.owner_id)
            elif b.bullet_type == BType.SMOKE:
                self._trigger_smoke_explosion(b.x, b.y, b.owner_id)
            elif b.bullet_type == BType.MINI_GRENADE:
                self._trigger_mini_grenade_explosion(b.x, b.y, b.owner_id)
        # 以下無論何種原因消失都觸發
        if b.bullet_type == BType.STUN:
            from game.chars.pioneer.stun_bullet_state import trigger_stun_explosion
            trigger_stun_explosion(self, b.x, b.y, b.owner_id)
        if b.bullet_type == BType.EXPLOSION:
            self._trigger_explosion_bullet(b.x, b.y, b.owner_id)
        if b.bullet_type == BType.POISON_BALL and b.distance_travelled < b.max_range:
            self._create_poison_pool(b.x, b.y, b.owner_id)

    # ── 主要更新方法 ─────────────────────────────────────────────────────────

    def step_bullets(self, obstacles: dict = None,
                     obstacle_hp: dict = None) -> None:
        if obstacles is None:
            obstacles = {}

        expired: list = []
        for bid, bullet in self.bullets.items():
            bullet.step()
            if bullet.is_expired():
                expired.append(bid)
                continue

            shooter     = self.players.get(bullet.owner_id)
            does_damage = not (shooter and shooter.damage_min == 0
                               and shooter.damage_max == 0)
            if bullet.bullet_type in _NON_CONTACT:
                does_damage = False   # 投擲物 / 特殊彈不造成接觸傷害
            coll_r = self._calc_coll_radius(bullet)

            hit = self._bullet_vs_players(bullet, bid, coll_r, does_damage, shooter, expired)
            if not hit:
                self._bullet_vs_obstacles(bullet, bid, coll_r, does_damage, shooter,
                                          obstacles, obstacle_hp, expired)
                self._bullet_vs_barriers(bullet, bid, coll_r, does_damage, shooter, expired)
                self._bullet_vs_turrets(bullet, bid, coll_r, does_damage, shooter, expired)

        for bid in expired:
            b = self.bullets.get(bid)
            if b:
                self._trigger_bullet_expiry(b)
            self.bullets.pop(bid, None)
            for k in self._dot_keys_by_bid.pop(bid, ()):
                self._dot_cooldown.pop(k, None)

    def _spawn_item(self, x: float, y: float, kind: str) -> None:
        """掉落 1 個道具（寶石或血包），位置稍微隨機偏移。"""
        angle = random.uniform(0, math.tau)
        dist  = random.uniform(20, 60)
        while self._next_gold_id in self.gold_ingots:
            self._next_gold_id = (self._next_gold_id + 1) % 256
        gid   = self._next_gold_id
        self._next_gold_id = (self._next_gold_id + 1) % 256
        self.gold_ingots[gid] = GoldIngot(
            id=gid,
            x=x + math.cos(angle) * dist,
            y=y + math.sin(angle) * dist,
            kind=kind,
        )

    def _spawn_gold(self, x: float, y: float) -> None:
        """在 box_special 破壞位置周圍散落同種寶石（冷縮或回血各 50%）。
        數量：40% 2個、30% 3個、20% 4個、10% 5個。
        """
        r = random.random()
        count = 2 if r < 0.40 else 3 if r < 0.70 else 4 if r < 0.90 else 5
        kind  = random.choice(("gem", "health"))
        for _ in range(count):
            self._spawn_item(x, y, kind)

    # ── 技能相關（實作移至 game/chars/*/）────────────────────────────────────────

    def _spawn_flash_grenade(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.agent.flash_state import spawn_flash_grenade
        spawn_flash_grenade(self, owner_id, aim_x, aim_y)

    def _trigger_flash_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.agent.flash_state import trigger_flash_explosion
        trigger_flash_explosion(self, x, y, owner_id)

    def _activate_mercury_barrage(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.agent.mercury_state import activate_mercury
        activate_mercury(self, owner_id, aim_x, aim_y)

    def step_mercury_barrage(self) -> None:
        from game.chars.agent.mercury_state import step_mercury
        step_mercury(self)

    def _spawn_shuriken(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.assassin.shuriken_state import spawn_shuriken
        spawn_shuriken(self, owner_id, aim_x, aim_y)

    def _activate_speed_boost(self, owner_id: int) -> None:
        from game.chars.assassin.speed_state import activate_speed_boost
        activate_speed_boost(self, owner_id)

    def _activate_r_skill(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.assassin.r_dash_state import activate_r_skill
        activate_r_skill(self, owner_id, aim_x, aim_y)

    def step_r_skill(self) -> None:
        from game.chars.assassin.r_dash_state import step_r_skill
        step_r_skill(self)

    def _spawn_smoke_grenade(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.assassin.smoke_state import spawn_smoke_grenade
        spawn_smoke_grenade(self, owner_id, aim_x, aim_y)

    def _trigger_smoke_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.assassin.smoke_state import trigger_smoke_explosion
        trigger_smoke_explosion(self, x, y, owner_id)

    def step_smoke_patches(self) -> None:
        from game.chars.assassin.smoke_state import step_smoke_patches
        step_smoke_patches(self)

    def _activate_airstrike(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.vince.airstrike_state import activate_airstrike
        activate_airstrike(self, owner_id, aim_x, aim_y)

    def _spawn_mini_grenades(self, owner_id: int) -> None:
        from game.chars.hunter.mini_grenade_state import spawn_mini_grenades
        spawn_mini_grenades(self, owner_id)

    def _trigger_mini_grenade_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.hunter.mini_grenade_state import trigger_mini_grenade_explosion
        trigger_mini_grenade_explosion(self, x, y, owner_id)

    def _activate_log_barriers(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.hunter.log_barrier_state import activate_log_barriers
        activate_log_barriers(self, owner_id, aim_x, aim_y)

    def _activate_giant(self, owner_id: int) -> None:
        from game.chars.vince.giant_state import activate_giant
        activate_giant(self, owner_id)

    def step_giant(self) -> None:
        from game.chars.vince.giant_state import step_giant
        step_giant(self)

    def step_air_strikes(self) -> None:
        from game.chars.vince.airstrike_state import step_air_strikes
        step_air_strikes(self)

    def _activate_blade_arc(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.zombie.blade_state import activate_blade_arc
        activate_blade_arc(self, owner_id, aim_x, aim_y)

    def step_blade_arcs(self, obstacles: dict = None, obstacle_hp: dict = None) -> None:
        from game.chars.zombie.blade_state import step_blade_arcs
        step_blade_arcs(self, obstacles, obstacle_hp)

    def _activate_zombie_spit(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.zombie.spit_state import activate_spit
        activate_spit(self, owner_id, aim_x, aim_y)

    def step_zombie_spit(self) -> None:
        from game.chars.zombie.spit_state import step_spit
        step_spit(self)

    def _activate_zombie_rage(self, owner_id: int) -> None:
        from game.chars.zombie.rage_state import activate_rage
        activate_rage(self, owner_id)

    def step_zombie_rage(self) -> None:
        from game.chars.zombie.rage_state import step_rage
        step_rage(self)

    def _activate_burst(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.agent.burst_state import activate_burst
        activate_burst(self, owner_id, aim_x, aim_y)

    def step_burst(self) -> None:
        from game.chars.agent.burst_state import step_burst
        step_burst(self)

    def _spawn_pool_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.poisoner.poison_pool_state import spawn_pool_bullet
        spawn_pool_bullet(self, owner_id, aim_x, aim_y)

    def _create_poison_pool(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.poisoner.poison_pool_state import create_poison_pool
        create_poison_pool(self, x, y, owner_id)

    def step_poison_pools(self) -> None:
        from game.chars.poisoner.poison_pool_state import step_poison_pools
        step_poison_pools(self)

    def _activate_poisoner_space(self, owner_id: int) -> None:
        from game.chars.poisoner.space_skill_state import activate_poisoner_space
        activate_poisoner_space(self, owner_id)

    def step_poisoner_space(self) -> None:
        from game.chars.poisoner.space_skill_state import step_poisoner_space
        step_poisoner_space(self)

    def _activate_poisoner_e(self, owner_id: int) -> None:
        from game.chars.poisoner.e_skill_state import activate_poisoner_e
        activate_poisoner_e(self, owner_id)

    def step_poisoner_e(self) -> None:
        from game.chars.poisoner.e_skill_state import step_poisoner_e
        step_poisoner_e(self)

    def step_poison_stacks(self) -> None:
        from game.chars.poisoner.poison_stack_state import step_poison_stacks
        step_poison_stacks(self)

    def _place_mine(self, owner_id: int) -> None:
        from game.chars.marksman.mine_state import place_mine
        place_mine(self, owner_id)

    def step_mines(self) -> None:
        from game.chars.marksman.mine_state import step_mines
        step_mines(self)

    def _place_turret(self, owner_id: int) -> None:
        from game.chars.marksman.turret_state import place_turret
        place_turret(self, owner_id)

    def step_turrets(self, obstacles: dict = None, obstacle_hp: dict = None) -> None:
        from game.chars.marksman.turret_state import step_turrets
        step_turrets(self, obstacles, obstacle_hp)

    def _activate_barrage(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.marksman.barrage_state import activate_barrage
        activate_barrage(self, owner_id, aim_x, aim_y)

    def step_barrage(self) -> None:
        from game.chars.marksman.barrage_state import step_barrage
        step_barrage(self)

    # ── Soldier E：防護罩 ──────────────────────────────────────────────────────
    def _activate_shield(self, owner_id: int) -> None:
        from game.chars.pioneer.shield_state import activate_shield
        activate_shield(self, owner_id)

    def step_shields(self) -> None:
        from game.chars.pioneer.shield_state import step_shields
        step_shields(self)

    def step_shockwaves(self) -> None:
        from game.chars.pioneer.shield_state import step_shockwaves
        step_shockwaves(self)

    def apply_stun(self, player_id: int, ticks: int) -> None:
        """Apply stun to a player. Extends duration if already stunned."""
        player = self.players.get(player_id)
        if player is None:
            return
        player.stun_until = max(
            player.stun_until if player.stun_until > self.tick else self.tick,
            self.tick + ticks,
        )

    def apply_damage(self, player_id: int, damage: int) -> None:
        """所有對玩家的傷害應透過此方法，使防護罩優先吸收。
        防護罩規則：傷害先扣護盾；護盾 HP 歸零即破壞；不溢傷到玩家血量。
        """
        player = self.players.get(player_id)
        if player is None:
            return
        # Assassin R 衝刺中：完全無敵
        if player.r_skill_phase > 0:
            return
        # 一般恢復魔紋：任何傷害（含護盾吸收前）即打斷回復
        if damage > 0 and player.rune_recovery_ticks > 0:
            player.rune_recovery_ticks = 0

        # Zombie E 嗜血：所受傷害無條件捨去減半
        if player.zombie_rage_tick >= 0:
            damage = damage // 2

        shield = self.shields.get(player_id)
        if shield is not None and shield.broken_tick < 0:
            if damage >= shield.hp:
                # 護盾破壞，傷害不溢出；啟動衝擊波環
                shield.broken_tick = self.tick
                from game.chars.pioneer.shield_state import _start_shockwave
                _start_shockwave(self, player_id)
            else:
                shield.hp -= damage
            return   # 無論如何，玩家本體不受傷
        # 無護盾：直接扣血
        player.hp -= damage
        if player.hp <= 0:
            killer_id = next((pid for pid in self.players if pid != player_id), None)
            if killer_id is not None:
                self.kill_counts[killer_id] = self.kill_counts.get(killer_id, 0) + 1
            if self.game_mode == "deathmatch":
                self.lives[player_id] = max(0, self.lives.get(player_id, 3) - 1)
            player.respawn()

    def apply_knockback(self, player_id: int, dir_x: float, dir_y: float) -> None:
        """施加標準擊退。dir_x/dir_y 為擊退方向（自動正規化），力道使用全域 KB_FORCE。"""
        player = self.players.get(player_id)
        if player is None:
            return
        dist = math.hypot(dir_x, dir_y)
        if dist == 0:
            return
        player.kb_vx = (dir_x / dist) * KB_FORCE
        player.kb_vy = (dir_y / dist) * KB_FORCE

    def step_knockback(self) -> None:
        """每 tick 執行：套用並衰減所有玩家的擊退速度（kb_vx / kb_vy）。
        暈眩期間玩家無法自主移動，但擊退位移照常執行。
        邊界碰撞由 MAP 邊框 clamp 處理，障礙物碰撞由 resolve_player_collisions 處理。
        """
        for player in self.players.values():
            if player.kb_vx == 0.0 and player.kb_vy == 0.0:
                continue
            player.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS,
                                              player.x + player.kb_vx))
            player.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS,
                                              player.y + player.kb_vy))
            player.kb_vx *= KB_DECAY
            player.kb_vy *= KB_DECAY
            if abs(player.kb_vx) < KB_STOP:
                player.kb_vx = 0.0
            if abs(player.kb_vy) < KB_STOP:
                player.kb_vy = 0.0

    def _activate_clones(self, owner_id: int) -> None:
        from game.chars.pioneer.clone_state import activate_clones
        activate_clones(self, owner_id)

    def _spawn_clone_bullets(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.pioneer.clone_state import spawn_clone_bullets
        spawn_clone_bullets(self, owner_id, aim_x, aim_y)

    def _activate_robot_overload(self, owner_id: int) -> None:
        from game.chars.robot.overload_state import activate_overload
        activate_overload(self, owner_id)

    def _activate_robot_space(self, owner_id: int) -> None:
        from game.chars.robot.mark_state import activate_robot_space
        activate_robot_space(self, owner_id)

    def step_robot_marks(self) -> None:
        from game.chars.robot.mark_state import step_robot_marks
        step_robot_marks(self)

    def _activate_robot_e(self, owner_id: int) -> None:
        from game.chars.robot.e_state import activate_robot_e
        activate_robot_e(self, owner_id)

    def step_robot_e(self) -> None:
        from game.chars.robot.e_state import step_robot_e
        step_robot_e(self)

    def _activate_push_zone(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.robot.push_state import activate_push
        activate_push(self, owner_id, aim_x, aim_y)

    def step_push_zones(self) -> None:
        from game.chars.robot.push_state import step_push_zones
        step_push_zones(self)

    # ── 魔紋 ─────────────────────────────────────────────────────────────────

    _RUNE_CD_TICKS = 30 * 60   # 30 秒 × 60 tick/s = 1800 ticks

    def _activate_rune(self, player_id: int) -> None:
        """Q 鍵啟動魔紋（血量上限 rune_id=2 為被動，server 不會收到 use_rune）。"""
        p = self.players.get(player_id)
        if p is None:
            return
        if p.rune_cd_until > self.tick:
            return   # 冷卻中
        if p.hp >= p.max_hp:
            return   # 滿血時不啟動、不進入冷卻
        p.rune_cd_until = self.tick + self._RUNE_CD_TICKS

        if p.rune_id == 0:   # 一般恢復：每秒 5% 持續 6 秒，首 tick 立即恢復
            p.rune_recovery_ticks = 360
        elif p.rune_id == 1:   # 強化恢復：瞬間 20%
            heal = int(p.base_max_hp * 0.20)
            p.hp  = min(p.max_hp, p.hp + heal)

    def step_rune_recovery(self) -> None:
        """每 tick 呼叫：驅動一般恢復的逐秒治療倒計時。"""
        for p in self.players.values():
            if p.rune_recovery_ticks <= 0:
                continue
            # 在 360, 300, 240, 180, 120, 60 tick 各回復 5%（共 6 次）
            if p.rune_recovery_ticks % 60 == 0:
                heal = int(p.base_max_hp * 0.05)
                p.hp = min(p.max_hp, p.hp + heal)
            p.rune_recovery_ticks -= 1

    def _spawn_stun_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.pioneer.stun_bullet_state import spawn_stun_bullet
        spawn_stun_bullet(self, owner_id, aim_x, aim_y)

    def _spawn_explosion_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.marksman.explosion_bullet_state import spawn_explosion_bullet
        spawn_explosion_bullet(self, owner_id, aim_x, aim_y)

    def _trigger_explosion_bullet(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.marksman.explosion_bullet_state import trigger_explosion
        trigger_explosion(self, x, y, owner_id)

    def _spawn_grenade(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.vince.grenade_state import spawn_grenade
        spawn_grenade(self, owner_id, aim_x, aim_y)

    def _trigger_grenade_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.vince.grenade_state import trigger_grenade_explosion
        trigger_grenade_explosion(self, x, y, owner_id)

    def step_status_effects(self) -> None:
        for player in self.players.values():
            if player.flash_ticks > 0:
                player.flash_ticks -= 1
            if player.speed_boost_ticks > 0:
                player.speed_boost_ticks -= 1

    def step_gold_collection(self) -> None:
        """任一玩家碰到寶石/血包就撿起。寶石累計計數（client 偵測後縮短冷卻）；血包回復最大血量 30%（不超過滿血）。"""
        collected = []
        for gid, ingot in self.gold_ingots.items():
            for pid, player in self.players.items():
                if math.hypot(player.x - ingot.x, player.y - ingot.y) < PLAYER_RADIUS + GOLD_RADIUS:
                    if ingot.kind == "health":
                        heal = int(player.max_hp * 0.10)
                        player.hp = min(player.max_hp, player.hp + heal)
                    else:  # "gem"
                        self.gold_counts[pid] = self.gold_counts.get(pid, 0) + 1
                    collected.append(gid)
                    break
        for gid in collected:
            self.gold_ingots.pop(gid, None)

    def resolve_player_collisions(self, obstacles: dict = None) -> None:
        if not obstacles:
            return
        for player in self.players.values():
            if player.jump_tick >= 0 or player.zombie_jump_tick >= 0:
                continue  # 跳躍中：穿越障礙物
            for oid, obs in obstacles.items():
                if oid in self.destroyed_obstacles:
                    continue
                if not obs.solid:          # 非實體（樹/草叢）→ 玩家穿透
                    continue
                new_x, new_y = obs.push_out_circle(player.x, player.y, PLAYER_RADIUS)
                player.x = new_x
                player.y = new_y
            for lb in list(self.log_barriers.values()):
                min_dist = PLAYER_RADIUS + lb.radius
                ddx = player.x - lb.x
                ddy = player.y - lb.y
                dist = math.hypot(ddx, ddy)
                if dist < min_dist:
                    scale = min_dist / dist if dist > 0 else 1.0
                    player.x = lb.x + ddx * scale if dist > 0 else lb.x + min_dist
                    player.y = lb.y + ddy * scale if dist > 0 else lb.y

    # ── Sniper R：幻影隱身 ───────────────────────────────────────────────────
    def _activate_cloak(self, owner_id: int) -> None:
        from game.chars.hunter.cloak_state import activate_cloak
        activate_cloak(self, owner_id)

    # ── Soldier Space：跳躍 ──────────────────────────────────────────────────
    def _activate_jump(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.pioneer.jump_state import activate_jump
        activate_jump(self, owner_id, aim_x, aim_y)

    def step_jumps(self) -> None:
        from game.chars.pioneer.jump_state import step_jumps
        step_jumps(self)

    def _activate_vince_dash(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.vince.dash_state import activate_dash
        activate_dash(self, owner_id, aim_x, aim_y)

    def step_vince_dash(self, obstacles: dict = None) -> None:
        from game.chars.vince.dash_state import step_vince_dash
        step_vince_dash(self, obstacles)

    # ── Agent Space：衝刺 ────────────────────────────────────────────────────
    def _activate_agent_dash(self, owner_id: int) -> None:
        from game.chars.agent.dash_state import activate_agent_dash
        activate_agent_dash(self, owner_id)

    def step_agent_dash(self) -> None:
        from game.chars.agent.dash_state import step_agent_dash
        step_agent_dash(self)

    # ── Zombie Space：跳躍衝擊 ───────────────────────────────────────────────
    def _activate_zombie_jump(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.zombie.jump_state import activate_zombie_jump
        activate_zombie_jump(self, owner_id, aim_x, aim_y)

    def step_zombie_jumps(self) -> None:
        from game.chars.zombie.jump_state import step_zombie_jumps
        step_zombie_jumps(self)

    # ── Vince Space：嘲諷 ────────────────────────────────────────────────────
    def _activate_vince_taunt(self, owner_id: int) -> None:
        from game.chars.vince.taunt_state import activate_vince_taunt
        activate_vince_taunt(self, owner_id)

    def step_vince_taunt(self) -> None:
        from game.chars.vince.taunt_state import step_vince_taunt
        step_vince_taunt(self)

    def step_pull(self) -> None:
        """每 tick：被嘲諷吸引的玩家向吸引源等速移動。"""
        for player in self.players.values():
            if player.pull_source_id < 0:
                continue
            if player.stun_until <= self.tick:
                player.pull_source_id = -1
                player.pull_speed     = 0.0
                continue
            source = self.players.get(player.pull_source_id)
            if source is None:
                player.pull_source_id = -1
                continue
            dx   = source.x - player.x
            dy   = source.y - player.y
            dist = math.hypot(dx, dy)
            if dist <= PLAYER_RADIUS * 2:
                continue   # 已抵達，停止
            player.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS,
                           player.x + (dx / dist) * player.pull_speed))
            player.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS,
                           player.y + (dy / dist) * player.pull_speed))

    # ── Hunter RMB：空氣炮 ───────────────────────────────────────────────────

    _AIR_CANNON_SPEED = 800.0 / 60.0   # px/tick
    _AIR_CANNON_RADIUS = 25.0          # 碰撞半徑 px

    def _spawn_air_cannon(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        player = self.players.get(owner_id)
        if player is None:
            return
        dist = math.hypot(aim_x, aim_y)
        if dist == 0:
            return
        spd = self._AIR_CANNON_SPEED
        ux, uy = aim_x / dist, aim_y / dist
        cid = self._next_air_cannon_id
        self._next_air_cannon_id = (self._next_air_cannon_id + 1) % 256
        self.air_cannons[cid] = AirCannon(
            id=cid, owner_id=owner_id,
            x=player.x, y=player.y,
            dx=ux * spd, dy=uy * spd,
            spawn_tick=self.tick,
        )

    def step_air_cannons(self) -> None:
        to_remove = []
        for cid, cannon in self.air_cannons.items():
            cannon.x += cannon.dx
            cannon.y += cannon.dy
            cannon.dist_traveled += self._AIR_CANNON_SPEED

            opponent_id = 3 - cannon.owner_id
            opp = self.players.get(opponent_id)
            if opp:
                hit_r = PLAYER_RADIUS + self._AIR_CANNON_RADIUS
                if math.hypot(opp.x - cannon.x, opp.y - cannon.y) < hit_r:
                    self.apply_knockback(opponent_id, cannon.dx, cannon.dy)
                    owner = self.players.get(cannon.owner_id)
                    if owner:
                        owner.air_cannon_hit_seq = (owner.air_cannon_hit_seq + 1) % 256
                    to_remove.append(cid)
                    continue

            if (cannon.dist_traveled >= cannon.max_range or
                    cannon.x < 0 or cannon.x > MAP_WIDTH or
                    cannon.y < 0 or cannon.y > MAP_HEIGHT):
                to_remove.append(cid)

        for cid in to_remove:
            self.air_cannons.pop(cid, None)
