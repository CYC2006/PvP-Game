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
    speed: float = PLAYER_SPEED
    hp: int      = DEFAULT_MAX_HP
    max_hp: int  = DEFAULT_MAX_HP   # 依角色設定，respawn 恢復到此值
    damage_min: int = 1             # 子彈最小傷害（由 server 依角色設定）
    damage_max: int = 1             # 子彈最大傷害
    aim_angle: float = 0.0          # 瞄準角度（度），0=上, 90=右；同步給對手
    stance: str = "stand"           # "stand" | "machine" | "hold" | "reload"

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


@dataclass
class Bullet:
    id: int
    owner_id: int
    x: float
    y: float
    dx: float
    dy: float
    distance_travelled: float = 0.0

    def step(self) -> None:
        self.x += self.dx
        self.y += self.dy
        self.distance_travelled += math.hypot(self.dx, self.dy)

    def is_expired(self) -> bool:
        return (
            self.distance_travelled >= BULLET_MAX_RANGE
            or self.x < 0 or self.x > MAP_WIDTH
            or self.y < 0 or self.y > MAP_HEIGHT
        )


@dataclass
class GameState:
    players: dict            = field(default_factory=dict)
    bullets: dict            = field(default_factory=dict)
    destroyed_obstacles: set = field(default_factory=set)
    tick: int                = 0
    _next_bullet_id: int     = 0

    def add_player(self, player_id: int) -> "Player":
        spawn_x = MAP_WIDTH  // 4 if player_id == 1 else MAP_WIDTH  * 3 // 4
        spawn_y = MAP_HEIGHT // 2
        self.players[player_id] = Player(id=player_id,
                                         x=float(spawn_x), y=float(spawn_y))
        return self.players[player_id]

    def apply_char_stats(self, player_id: int, char_key: str) -> None:
        """遊戲開始後由 server 呼叫，將角色數值套用到 Player。"""
        from game.char_data import get_stat
        if player_id not in self.players:
            return
        p = self.players[player_id]
        p.max_hp     = get_stat(char_key, "hp")
        p.hp         = p.max_hp
        p.damage_min = get_stat(char_key, "damage_min")
        p.damage_max = get_stat(char_key, "damage_max")

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
        ux  = aim_x / length
        uy  = aim_y / length
        # 後座力散佈：±5° 隨機偏角
        spread = math.radians(random.uniform(-5.0, 5.0))
        cos_s, sin_s = math.cos(spread), math.sin(spread)
        ux, uy = ux * cos_s - uy * sin_s, ux * sin_s + uy * cos_s

        ndx = ux * BULLET_SPEED
        ndy = uy * BULLET_SPEED
        barrel_fwd   = PLAYER_RADIUS + 10
        barrel_right = 14
        rx = -uy
        ry =  ux
        bid = self._next_bullet_id
        self._next_bullet_id = (self._next_bullet_id + 1) % 256
        self.bullets[bid] = Bullet(
            id=bid, owner_id=owner_id,
            x=player.x + ux * barrel_fwd + rx * barrel_right,
            y=player.y + uy * barrel_fwd + ry * barrel_right,
            dx=ndx, dy=ndy,
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
                if obs.collides_circle(bullet.x, bullet.y, BULLET_RADIUS):
                    if obstacle_hp is not None and obs.destructible:
                        obstacle_hp[oid] -= 1
                        if obstacle_hp[oid] <= 0:
                            self.destroyed_obstacles.add(oid)
                    expired.append(bid)
                    break

        for bid in expired:
            self.bullets.pop(bid, None)

    def resolve_player_collisions(self, obstacles: dict = None) -> None:
        if not obstacles:
            return
        for player in self.players.values():
            for oid, obs in obstacles.items():
                if oid in self.destroyed_obstacles:
                    continue
                new_x, new_y = obs.push_out_circle(player.x, player.y, PLAYER_RADIUS)
                player.x = new_x
                player.y = new_y
