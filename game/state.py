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
    pellet_count: int   = 1               # 散彈槍：一次發射的子彈數量
    bullet_range: float = BULLET_MAX_RANGE  # 子彈最大射程（px）
    bullet_range_min: float = 0           # >0 時每顆散彈隨機射程 [min, range]
    aim_angle: float   = 0.0             # 瞄準角度（度），0=上, 90=右；同步給對手
    stance: str        = "stand"         # "stand" | "machine" | "hold" | "reload"

    def move(self, dx: float, dy: float, crouching: bool = False) -> None:
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length > 0:
            dx, dy = dx / length, dy / length
        speed = self.speed * (0.5 if crouching else 1.0)
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


@dataclass
class Bullet:
    id: int
    owner_id: int
    x: float
    y: float
    dx: float
    dy: float
    distance_travelled: float = 0.0
    aim_angle: float = 0.0            # 飛行方向（度）atan2(dy,dx)，供 client 繪圖用
    max_range: float = BULLET_MAX_RANGE  # 最大射程（px）；散彈槍可設極短

    def step(self) -> None:
        self.x += self.dx
        self.y += self.dy
        self.distance_travelled += math.hypot(self.dx, self.dy)

    def is_expired(self) -> bool:
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
        p.max_hp       = get_stat(char_key, "hp")
        p.hp           = p.max_hp
        p.speed        = float(get_stat(char_key, "speed"))
        p.damage_min   = get_stat(char_key, "damage_min")
        p.damage_max   = get_stat(char_key, "damage_max")
        p.bullet_speed = float(get_stat(char_key, "bullet_speed")) * BULLET_SPEED
        p.spread       = float(get_stat(char_key, "spread"))
        # 散彈槍專屬欄位（其他角色無此欄位時取預設值）
        char_cfg          = CHAR_STATS.get(char_key, {})
        p.pellet_count    = int(char_cfg.get("pellet_count", 1))
        p.bullet_range    = float(char_cfg.get("bullet_range", BULLET_MAX_RANGE))
        p.bullet_range_min = float(char_cfg.get("bullet_range_min", 0))

    def apply_command(self, player_id: int, dx: float, dy: float,
                      shooting: bool, aim_x: float, aim_y: float,
                      crouching: bool = False, stance: str = "stand") -> None:
        if player_id not in self.players:
            return
        player = self.players[player_id]
        player.move(dx, dy, crouching)
        player.stance = stance
        if math.hypot(aim_x, aim_y) > 0:
            player.aim_angle = math.degrees(math.atan2(aim_x, -aim_y))
        if shooting:
            self._spawn_bullet(player_id, aim_x, aim_y)

    def _spawn_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        player = self.players[owner_id]
        length = math.hypot(aim_x, aim_y)
        if length == 0:
            return
        ux = aim_x / length
        uy = aim_y / length

        # 槍口偏移（固定用主瞄準方向計算，所有散彈共用同一出口）
        barrel_fwd   = PLAYER_RADIUS + 10
        barrel_right = 14
        rx, ry = -uy, ux
        spawn_x = player.x + ux * barrel_fwd + rx * barrel_right
        spawn_y = player.y + uy * barrel_fwd + ry * barrel_right

        for _ in range(player.pellet_count):
            # 每顆散彈獨立隨機偏角
            pux, puy = ux, uy
            if player.spread > 0:
                dev = math.radians(random.uniform(-player.spread, player.spread))
                cos_s, sin_s = math.cos(dev), math.sin(dev)
                pux = ux * cos_s - uy * sin_s
                puy = ux * sin_s + uy * cos_s

            ndx = pux * player.bullet_speed
            ndy = puy * player.bullet_speed
            # 每顆散彈各自隨機射程（min>0 時），製造遠近不一的散射效果
            if player.bullet_range_min > 0:
                pellet_range = random.uniform(player.bullet_range_min, player.bullet_range)
            else:
                pellet_range = player.bullet_range
            bid = self._next_bullet_id
            self._next_bullet_id = (self._next_bullet_id + 1) % 256
            self.bullets[bid] = Bullet(
                id=bid, owner_id=owner_id,
                x=spawn_x, y=spawn_y,
                dx=ndx, dy=ndy,
                aim_angle=math.degrees(math.atan2(ndy, ndx)),
                max_range=pellet_range,
            )

    def step_bullets(self, obstacles: dict = None,
                     obstacle_hp: dict = None) -> None:
        if obstacles is None:
            obstacles = {}

        expired = []
        for bid, bullet in self.bullets.items():
            bullet.step()
            if bullet.is_expired():
                expired.append(bid)
                continue

            hit = False

            # 子彈 vs 玩家
            for pid, player in self.players.items():
                if pid == bullet.owner_id:
                    continue
                if math.hypot(bullet.x - player.x, bullet.y - player.y) < PLAYER_RADIUS + BULLET_RADIUS:
                    # 依射手角色計算傷害
                    shooter = self.players.get(bullet.owner_id)
                    if shooter and shooter.damage_min < shooter.damage_max:
                        damage = random.randint(shooter.damage_min, shooter.damage_max)
                    elif shooter:
                        damage = shooter.damage_min
                    else:
                        damage = 1
                    player.hp -= damage
                    if player.hp <= 0:
                        player.respawn()
                    expired.append(bid)
                    hit = True
                    break

            if hit:
                continue

            # 子彈 vs 障礙物
            for oid, obs in obstacles.items():
                if oid in self.destroyed_obstacles:
                    continue
                if not obs.solid:          # 非實體（樹/草叢）→ 子彈穿透
                    continue
                if obs.collides_circle(bullet.x, bullet.y, BULLET_RADIUS):
                    if obstacle_hp is not None and obs.destructible:
                        shooter = self.players.get(bullet.owner_id)
                        if shooter and shooter.damage_min < shooter.damage_max:
                            obs_dmg = random.randint(shooter.damage_min, shooter.damage_max)
                        elif shooter:
                            obs_dmg = shooter.damage_min
                        else:
                            obs_dmg = 1
                        obstacle_hp[oid] -= obs_dmg
                        if obstacle_hp[oid] <= 0:
                            self.destroyed_obstacles.add(oid)
                            if obs.kind == "box_special":
                                self._spawn_gold(obs.x, obs.y)
                            elif obs.kind == "box_normal" and random.random() < 0.20:
                                self._spawn_gold_single(obs.x, obs.y)
                    expired.append(bid)
                    break

        for bid in expired:
            self.bullets.pop(bid, None)

    def _spawn_gold_single(self, x: float, y: float) -> None:
        """box_normal 破壞時 20% 機率掉 1 顆金錠，位置稍微隨機偏移。"""
        angle = random.uniform(0, math.tau)
        dist  = random.uniform(10, 30)
        gid   = self._next_gold_id
        self._next_gold_id = (self._next_gold_id + 1) % 256
        self.gold_ingots[gid] = GoldIngot(
            id=gid,
            x=x + math.cos(angle) * dist,
            y=y + math.sin(angle) * dist,
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

    def step_gold_collection(self) -> None:
        """任一玩家碰到金錠就撿起，累計計數。"""
        collected = []
        for gid, ingot in self.gold_ingots.items():
            for pid, player in self.players.items():
                if math.hypot(player.x - ingot.x, player.y - ingot.y) < PLAYER_RADIUS + GOLD_RADIUS:
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
