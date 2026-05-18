from dataclasses import dataclass, field
import math
import random

MAP_WIDTH  = 1920
MAP_HEIGHT = 1080

PLAYER_SPEED     = 3.0
PLAYER_RADIUS    = 16
BULLET_SPEED     = 8.0
BULLET_RADIUS    = 5
DEFAULT_MAX_HP   = 100      # 預設血量（未設定角色時使用）
BULLET_MAX_RANGE = 900


@dataclass
class Player:
    id: int
    x: float
    y: float
    speed: float        = PLAYER_SPEED
    hp: int             = DEFAULT_MAX_HP
    max_hp: int         = DEFAULT_MAX_HP   # 依角色設定，respawn 恢復到此值
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
    speed_boost_ticks: int  = 0     # >0：速度提升中，倒數至 0（survivor1 space）
    speed_boost_mult: float = 1.0   # 速度提升倍率
    char_key: str           = ""    # 角色 key，由 apply_char_stats 設定，不同步至 client
    # ── manBlue R 技能狀態（巨大化）─────────────────────────────────
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
    # ── survivor1 R 技能狀態 ──────────────────────────────────────
    r_skill_phase: int        = 0    # 0=inactive 1=phase1 2=phase2
    r_skill_tick: int         = 0    # 當前階段已過 ticks
    r_skill_dx: float         = 0.0  # 第一段滑動方向 x（單位向量）
    r_skill_dy: float         = 0.0  # 第一段滑動方向 y
    r_skill_start_angle: float = 0.0 # 技能啟動時的 aim_angle
    r_skill_dmg_done: int     = 0    # bitmask: 1=phase1 已傷害, 2=phase2 已傷害

    def move(self, dx: float, dy: float, speed_mult: float = 1.0) -> None:
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length > 0:
            dx, dy = dx / length, dy / length
        speed = self.speed * speed_mult
        self.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS, self.x + dx * speed))
        self.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS, self.y + dy * speed))

    def respawn(self) -> None:
        self.hp = self.max_hp
        self.x  = float(MAP_WIDTH  // 4 if self.id == 1 else MAP_WIDTH  * 3 // 4)
        self.y  = float(MAP_HEIGHT // 2)


GOLD_RADIUS = 10   # 玩家撿取金錠的碰撞半徑


@dataclass
class GoldIngot:
    id: int
    x: float
    y: float
    kind: str = "gold"   # "gold" | "health"


@dataclass
class SmokePatch:
    id: int
    x: float
    y: float
    radius: float
    spawn_tick: int


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
    id:         int
    owner_id:   int
    x:          float
    y:          float
    spawn_tick: int
    radius:     float = 300.0


@dataclass
class RobotMark:
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
class LogBarrier:
    id:       int
    owner_id: int
    x:        float
    y:        float
    hp:       int
    radius:   float = 12.0


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


@dataclass
class GameState:
    players: dict            = field(default_factory=dict)
    bullets: dict            = field(default_factory=dict)
    destroyed_obstacles: set = field(default_factory=set)
    gold_ingots: dict        = field(default_factory=dict)   # gid → GoldIngot
    gold_counts: dict        = field(default_factory=dict)   # pid → int
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
    poison_pools: dict       = field(default_factory=dict)   # ppid → PoisonPool
    _next_pool_id: int       = 0
    push_zones: dict         = field(default_factory=dict)   # pzid → PushZone
    _next_push_zone_id: int  = 0
    robot_marks: dict        = field(default_factory=dict)   # owner_id → RobotMark（每個 robot1 最多一筆）

    def add_player(self, player_id: int) -> "Player":
        spawn_x = MAP_WIDTH  // 4 if player_id == 1 else MAP_WIDTH  * 3 // 4
        spawn_y = MAP_HEIGHT // 2
        self.players[player_id] = Player(id=player_id,
                                         x=float(spawn_x), y=float(spawn_y))
        return self.players[player_id]

    def apply_char_stats(self, player_id: int, char_key: str) -> None:
        """遊戲開始後由 server 呼叫，將角色數值套用到 Player。"""
        from game.char_data import get_stat, CHAR_STATS
        if player_id not in self.players:
            return
        p = self.players[player_id]
        p.char_key     = char_key
        p.max_hp       = get_stat(char_key, "hp")
        p.hp           = p.max_hp
        p.speed        = float(get_stat(char_key, "speed"))
        p.damage_min   = get_stat(char_key, "damage_min")
        p.damage_max   = get_stat(char_key, "damage_max")
        p.bullet_speed = float(get_stat(char_key, "bullet_speed")) * BULLET_SPEED
        p.spread       = float(get_stat(char_key, "spread"))
        # 特殊武器專屬欄位（其他角色無此欄位時取預設值）
        char_cfg           = CHAR_STATS.get(char_key, {})
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

    def apply_command(self, player_id: int, dx: float, dy: float,
                      shooting: bool, aim_x: float, aim_y: float,
                      running: bool = False, stance: str = "machine",
                      speed_mult: float = 1.0) -> None:
        if player_id not in self.players:
            return
        player = self.players[player_id]
        # 暈眩中：忽略所有輸入
        if self.tick < player.stun_until:
            return
        # 巨大化進行中
        if player.giant_tick >= 0:
            from game.chars.rambo.giant_state import GROW_TICKS, ACTIVE_TICKS
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
        # 射擊觸發計時器；計時器倒數中套用移動懲罰（shoot_slow 優先於 run）
        if shooting:
            player._shoot_slow_timer = player._shoot_slow_ticks
        elif player._shoot_slow_timer > 0:
            player._shoot_slow_timer -= 1
        if speed_mult != 1.0:
            mult = speed_mult          # 技能位移（衝刺等）：最高優先，不疊加 boost
        elif player._shoot_slow_timer > 0:
            mult = player.shoot_slow   # 射擊僵直：速度下降
        elif running:
            mult = 1.2                 # 跑步：速度 ×1.2
        else:
            mult = 1.0
        # 速度提升技能（survivor1 space）：與 shoot_slow 疊加
        if player.speed_boost_ticks > 0 and speed_mult == 1.0:
            mult *= player.speed_boost_mult
        # 巨大化主動階段：移速 ×1.5
        if player.giant_tick >= 0 and speed_mult == 1.0:
            from game.chars.rambo.giant_state import GROW_TICKS, ACTIVE_TICKS
            _ga = self.tick - player.giant_tick
            if GROW_TICKS <= _ga < GROW_TICKS + ACTIVE_TICKS:
                mult *= 1.5
        # 通用速度懲罰（由技能模組設定，如毒液區域 0.8）
        mult *= player.speed_penalty
        player.move(dx, dy, speed_mult=mult)
        player.stance = stance
        # 連射期間：禁止普攻（避免與連射子彈重疊）
        if player.burst_next_tick >= 0:
            shooting = False
        if math.hypot(aim_x, aim_y) > 0:
            player.aim_angle = math.degrees(math.atan2(aim_x, -aim_y))
        if shooting:
            if player.char_key == 'zombie1':
                self._activate_blade_arc(player_id, aim_x, aim_y)
            else:
                self._spawn_bullet(player_id, aim_x, aim_y)
                # Soldier1 R：分身同步射擊（只在普攻觸發，不在技能路徑）
                if player.clone_until > self.tick:
                    self._spawn_clone_bullets(player_id, aim_x, aim_y)

    def _spawn_bullet(self, owner_id: int, aim_x: float, aim_y: float,
                      bullet_scale_override: float = 0.0,
                      spread_override: float = -1.0) -> None:
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
                from game.chars.rambo.giant_state import GROW_TICKS, ACTIVE_TICKS
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
            bid = self._next_bullet_id
            self._next_bullet_id = (self._next_bullet_id + 1) % 256
            _btype = 9 if player.char_key == 'robot1' else 0
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
                self._spawn_item(obs.x, obs.y, "gold")
            elif r < 0.20:
                self._spawn_item(obs.x, obs.y, "health")

    def step_bullets(self, obstacles: dict = None,
                     obstacle_hp: dict = None) -> None:
        from game.chars.assassin.shuriken_state import (
            SHURIKEN_GROW_RATE as _SHURIKEN_GROW_RATE,
            SHURIKEN_BASE_DMG  as _SHURIKEN_BASE_DMG,
            SHURIKEN_DMG_SCALE as _SHURIKEN_DMG_SCALE,
        )
        if obstacles is None:
            obstacles = {}

        expired = []
        for bid, bullet in self.bullets.items():
            bullet.step()
            if bullet.is_expired():
                expired.append(bid)
                continue

            hit = False
            shooter = self.players.get(bullet.owner_id)
            does_damage = not (shooter and shooter.damage_min == 0 and shooter.damage_max == 0)
            if bullet.bullet_type in (1, 2, 5, 6, 7, 8):
                does_damage = False   # 閃光彈/手榴彈/迷你手雷/暈眩彈/爆炸彈/毒液彈不造成接觸傷害

            # 手裡劍：碰撞半徑隨時間線性成長
            if bullet.bullet_type == 3:
                age    = self.tick - bullet.spawn_tick
                coll_r = BULLET_RADIUS + age * _SHURIKEN_GROW_RATE
            # DoT 子彈的動態碰撞半徑（隨泡泡成長）
            elif bullet.dot_interval > 0 and bullet.bubble_radius_max > 0:
                _BUBBLE_LIFE_TICKS = 120  # 2.0s × 60 fps
                age    = self.tick - bullet.spawn_tick
                t_grow = min(1.0, age / _BUBBLE_LIFE_TICKS)
                coll_r = (BULLET_RADIUS * 2
                          + (bullet.bubble_radius_max - BULLET_RADIUS * 2) * t_grow)
            else:
                coll_r = float(BULLET_RADIUS) * bullet.bullet_scale

            # ── 子彈 vs 玩家 ────────────────────────────────────────────
            if bullet.dot_interval > 0:
                # DoT 子彈（毒氣泡）：穿透玩家，以動態半徑每 dot_interval tick 傷害一次
                for pid, player in self.players.items():
                    if pid == bullet.owner_id:
                        continue
                    if math.hypot(bullet.x - player.x,
                                  bullet.y - player.y) < PLAYER_RADIUS + coll_r:
                        key = (bid, pid)
                        if self.tick >= self._dot_cooldown.get(key, 0):
                            damage = self._roll_damage(shooter)
                            if bullet.bullet_scale != 1.0:
                                damage = int(damage * bullet.bullet_scale)
                            if player.giant_tick >= 0:
                                damage = int(damage * 0.8)
                            player.hp -= damage
                            if player.hp <= 0:
                                player.respawn()
                            self._dot_cooldown[key] = self.tick + bullet.dot_interval
                            self._dot_keys_by_bid.setdefault(bid, set()).add(key)
            elif does_damage:
                # 一般子彈：碰到玩家即消失
                for pid, player in self.players.items():
                    if pid == bullet.owner_id:
                        continue
                    if math.hypot(bullet.x - player.x,
                                  bullet.y - player.y) < PLAYER_RADIUS + coll_r:
                        if bullet.bullet_type == 3:
                            # 手裡劍：傷害隨碰撞半徑線性成長
                            damage = int(_SHURIKEN_BASE_DMG
                                         + _SHURIKEN_DMG_SCALE
                                         * (coll_r - BULLET_RADIUS))
                        else:
                            damage = self._roll_damage(shooter)
                        if bullet.bullet_scale != 1.0:
                            damage = int(damage * bullet.bullet_scale)
                        if player.giant_tick >= 0:
                            damage = int(damage * 0.8)
                        player.hp -= damage
                        if player.hp <= 0:
                            player.respawn()
                        expired.append(bid)
                        hit = True
                        break

            # ── 暈眩彈(6)/爆炸彈(7)/毒液彈(8) vs 玩家：碰觸即加入 expired ──
            if not hit and bullet.bullet_type in (6, 7, 8):
                for pid, player in self.players.items():
                    if pid == bullet.owner_id:
                        continue
                    if math.hypot(bullet.x - player.x,
                                  bullet.y - player.y) < PLAYER_RADIUS + coll_r:
                        expired.append(bid)
                        hit = True
                        break

            if hit:
                continue

            # ── 子彈 vs 障礙物 ──────────────────────────────────────────
            for oid, obs in obstacles.items():
                if oid in self.destroyed_obstacles:
                    continue
                if not obs.solid:          # 非實體（樹/草叢）→ 子彈穿透
                    continue
                if obs.collides_circle(bullet.x, bullet.y, coll_r):
                    if bullet.bullet_type in (1, 2, 3, 4, 5):
                        continue   # 投擲物 / 手裡劍 / 迷你手雷無視障礙物
                    if bullet.dot_interval > 0:
                        # DoT 子彈（毒氣泡）：撞牆時停住，不消失，持續傷害障礙物
                        if bullet.dx != 0.0 or bullet.dy != 0.0:
                            bullet.dx = 0.0
                            bullet.dy = 0.0   # 停在障礙物旁，觸發 linger 倒數
                        if obstacle_hp is not None and obs.destructible and does_damage:
                            key = (bid, -oid)  # 負 oid 與玩家 id 區分
                            if self.tick >= self._dot_cooldown.get(key, 0):
                                obstacle_hp[oid] -= self._roll_damage(shooter)
                                if obstacle_hp[oid] <= 0:
                                    self.destroyed_obstacles.add(oid)
                                    self._handle_obstacle_drop(obs)
                                self._dot_cooldown[key] = self.tick + bullet.dot_interval
                                self._dot_keys_by_bid.setdefault(bid, set()).add(key)
                        break   # 只對第一個相交的障礙物作用
                    else:
                        # 一般子彈：碰到障礙物即消失，可能破壞
                        if obstacle_hp is not None and obs.destructible and does_damage:
                            obstacle_hp[oid] -= self._roll_damage(shooter)
                            if obstacle_hp[oid] <= 0:
                                self.destroyed_obstacles.add(oid)
                                self._handle_obstacle_drop(obs)
                        expired.append(bid)
                        break

            # ── 子彈 vs 木頭障礙物 ──────────────────────────────────────
            if not hit:
                for lid in list(self.log_barriers):
                    lb = self.log_barriers.get(lid)
                    if lb is None:
                        continue
                    if math.hypot(bullet.x - lb.x, bullet.y - lb.y) < lb.radius + coll_r:
                        if bullet.bullet_type in (1, 2, 3, 4, 5):
                            continue   # 投擲物/手裡劍/迷你手雷穿透
                        if does_damage and shooter:
                            lb.hp -= self._roll_damage(shooter)
                            if lb.hp <= 0:
                                self.log_barriers.pop(lid, None)
                        expired.append(bid)
                        break

        for bid in expired:
            b = self.bullets.get(bid)
            # 投擲物 linger 結束時爆炸
            if b and b.decel > 0 and b.dx == 0.0 and b.dy == 0.0:
                if b.bullet_type == 1:
                    self._trigger_flash_explosion(b.x, b.y, b.owner_id)
                elif b.bullet_type == 2:
                    self._trigger_grenade_explosion(b.x, b.y, b.owner_id)
                elif b.bullet_type == 4:
                    self._trigger_smoke_explosion(b.x, b.y)
                elif b.bullet_type == 5:
                    self._trigger_mini_grenade_explosion(b.x, b.y, b.owner_id)
            # 暈眩彈：任何原因消失都爆炸（包含射程耗盡、碰到玩家/障礙物）
            if b and b.bullet_type == 6:
                from game.chars.soldier.stun_bullet_state import trigger_stun_explosion
                trigger_stun_explosion(self, b.x, b.y, b.owner_id)
            # 爆炸彈：任何原因消失都爆炸
            if b and b.bullet_type == 7:
                self._trigger_explosion_bullet(b.x, b.y, b.owner_id)
            # 毒液彈：命中物體（射程未耗盡）才生成毒液池
            if b and b.bullet_type == 8 and b.distance_travelled < b.max_range:
                self._create_poison_pool(b.x, b.y, b.owner_id)
            self.bullets.pop(bid, None)
            for k in self._dot_keys_by_bid.pop(bid, ()):
                self._dot_cooldown.pop(k, None)

    def _spawn_item(self, x: float, y: float, kind: str) -> None:
        """掉落 1 個道具（金錠或血包），位置稍微隨機偏移。"""
        angle = random.uniform(0, math.tau)
        dist  = random.uniform(10, 30)
        gid   = self._next_gold_id
        self._next_gold_id = (self._next_gold_id + 1) % 256
        self.gold_ingots[gid] = GoldIngot(
            id=gid,
            x=x + math.cos(angle) * dist,
            y=y + math.sin(angle) * dist,
            kind=kind,
        )

    def _spawn_gold(self, x: float, y: float) -> None:
        """在 box_special 破壞位置周圍散落 2~5 顆金錠。"""
        for _ in range(random.randint(2, 5)):
            angle = random.uniform(0, math.tau)
            dist  = random.uniform(20, 70)
            gid   = self._next_gold_id
            self._next_gold_id = (self._next_gold_id + 1) % 256
            self.gold_ingots[gid] = GoldIngot(
                id=gid,
                x=x + math.cos(angle) * dist,
                y=y + math.sin(angle) * dist,
            )

    # ── 技能相關（實作移至 game/chars/*/）────────────────────────────────────────

    def _spawn_flash_grenade(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.agent.flash_state import spawn_flash_grenade
        spawn_flash_grenade(self, owner_id, aim_x, aim_y)

    def _trigger_flash_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.agent.flash_state import trigger_flash_explosion
        trigger_flash_explosion(self, x, y, owner_id)

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

    def _trigger_smoke_explosion(self, x: float, y: float) -> None:
        from game.chars.assassin.smoke_state import trigger_smoke_explosion
        trigger_smoke_explosion(self, x, y)

    def step_smoke_patches(self) -> None:
        from game.chars.assassin.smoke_state import step_smoke_patches
        step_smoke_patches(self)

    def _activate_airstrike(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.rambo.airstrike_state import activate_airstrike
        activate_airstrike(self, owner_id, aim_x, aim_y)

    def _spawn_mini_grenades(self, owner_id: int) -> None:
        from game.chars.sniper.mini_grenade_state import spawn_mini_grenades
        spawn_mini_grenades(self, owner_id)

    def _trigger_mini_grenade_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.sniper.mini_grenade_state import trigger_mini_grenade_explosion
        trigger_mini_grenade_explosion(self, x, y, owner_id)

    def _activate_log_barriers(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.sniper.log_barrier_state import activate_log_barriers
        activate_log_barriers(self, owner_id, aim_x, aim_y)

    def _activate_giant(self, owner_id: int) -> None:
        from game.chars.rambo.giant_state import activate_giant
        activate_giant(self, owner_id)

    def step_giant(self) -> None:
        from game.chars.rambo.giant_state import step_giant
        step_giant(self)

    def step_air_strikes(self) -> None:
        from game.chars.rambo.airstrike_state import step_air_strikes
        step_air_strikes(self)

    def _activate_blade_arc(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.zombie.blade_state import activate_blade_arc
        activate_blade_arc(self, owner_id, aim_x, aim_y)

    def step_blade_arcs(self) -> None:
        from game.chars.zombie.blade_state import step_blade_arcs
        step_blade_arcs(self)

    def _activate_burst(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.agent.burst_state import activate_burst
        activate_burst(self, owner_id, aim_x, aim_y)

    def step_burst(self) -> None:
        from game.chars.agent.burst_state import step_burst
        step_burst(self)

    def _spawn_pool_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.dancer.poison_pool_state import spawn_pool_bullet
        spawn_pool_bullet(self, owner_id, aim_x, aim_y)

    def _create_poison_pool(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.dancer.poison_pool_state import create_poison_pool
        create_poison_pool(self, x, y, owner_id)

    def step_poison_pools(self) -> None:
        from game.chars.dancer.poison_pool_state import step_poison_pools
        step_poison_pools(self)

    def _place_mine(self, owner_id: int) -> None:
        from game.chars.bear.mine_state import place_mine
        place_mine(self, owner_id)

    def step_mines(self) -> None:
        from game.chars.bear.mine_state import step_mines
        step_mines(self)

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
            player.kb_vx *= 0.78
            player.kb_vy *= 0.78
            if abs(player.kb_vx) < 0.3:
                player.kb_vx = 0.0
            if abs(player.kb_vy) < 0.3:
                player.kb_vy = 0.0

    def _activate_clones(self, owner_id: int) -> None:
        from game.chars.soldier.clone_state import activate_clones
        activate_clones(self, owner_id)

    def _spawn_clone_bullets(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.soldier.clone_state import spawn_clone_bullets
        spawn_clone_bullets(self, owner_id, aim_x, aim_y)

    def _activate_robot_space(self, owner_id: int) -> None:
        from game.chars.robot.mark_state import activate_robot_space
        activate_robot_space(self, owner_id)

    def step_robot_marks(self) -> None:
        from game.chars.robot.mark_state import step_robot_marks
        step_robot_marks(self)

    def _activate_push_zone(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.robot.push_state import activate_push
        activate_push(self, owner_id, aim_x, aim_y)

    def step_push_zones(self) -> None:
        from game.chars.robot.push_state import step_push_zones
        step_push_zones(self)

    def _spawn_stun_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.soldier.stun_bullet_state import spawn_stun_bullet
        spawn_stun_bullet(self, owner_id, aim_x, aim_y)

    def _spawn_explosion_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.bear.explosion_bullet_state import spawn_explosion_bullet
        spawn_explosion_bullet(self, owner_id, aim_x, aim_y)

    def _trigger_explosion_bullet(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.bear.explosion_bullet_state import trigger_explosion
        trigger_explosion(self, x, y, owner_id)

    def _spawn_grenade(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        from game.chars.rambo.grenade_state import spawn_grenade
        spawn_grenade(self, owner_id, aim_x, aim_y)

    def _trigger_grenade_explosion(self, x: float, y: float, owner_id: int) -> None:
        from game.chars.rambo.grenade_state import trigger_grenade_explosion
        trigger_grenade_explosion(self, x, y, owner_id)

    def step_status_effects(self) -> None:
        for player in self.players.values():
            if player.flash_ticks > 0:
                player.flash_ticks -= 1
            if player.speed_boost_ticks > 0:
                player.speed_boost_ticks -= 1

    def step_gold_collection(self) -> None:
        """任一玩家碰到金錠/血包就撿起。金錠累計計數；血包回復最大血量 30%（不超過滿血）。"""
        collected = []
        for gid, ingot in self.gold_ingots.items():
            for pid, player in self.players.items():
                if math.hypot(player.x - ingot.x, player.y - ingot.y) < PLAYER_RADIUS + GOLD_RADIUS:
                    if ingot.kind == "health":
                        heal = int(player.max_hp * 0.30)
                        player.hp = min(player.max_hp, player.hp + heal)
                    else:
                        self.gold_counts[pid] = self.gold_counts.get(pid, 0) + 1
                    collected.append(gid)
                    break
        for gid in collected:
            self.gold_ingots.pop(gid, None)

    def resolve_player_collisions(self, obstacles: dict = None) -> None:
        if not obstacles:
            return
        for player in self.players.values():
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
