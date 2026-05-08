from dataclasses import dataclass, field
import math

MAP_WIDTH  = 1920   # 縮小以方便測試（原 3840）
MAP_HEIGHT = 1080   # 縮小以方便測試（原 2160）

PLAYER_SPEED     = 3.0
PLAYER_RADIUS    = 16
BULLET_SPEED     = 8.0
BULLET_RADIUS    = 5
MAX_HP           = 5
BULLET_MAX_RANGE = 900


@dataclass
class Player:
    id: int
    x: float
    y: float
    speed: float = PLAYER_SPEED
    hp: int = MAX_HP

    def move(self, dx: float, dy: float, crouching: bool = False) -> None:
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length > 0:
            dx, dy = dx / length, dy / length
        speed = self.speed * (0.5 if crouching else 1.0)
        self.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS, self.x + dx * speed))
        self.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS, self.y + dy * speed))

    def respawn(self) -> None:
        self.hp = MAX_HP
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
    destroyed_obstacles: set = field(default_factory=set)  # 已被摧毀的障礙物 ID
    tick: int                = 0
    _next_bullet_id: int     = 0

    def add_player(self, player_id: int) -> Player:
        spawn_x = MAP_WIDTH  // 4 if player_id == 1 else MAP_WIDTH  * 3 // 4
        spawn_y = MAP_HEIGHT // 2
        self.players[player_id] = Player(id=player_id, x=float(spawn_x), y=float(spawn_y))
        return self.players[player_id]

    def apply_command(self, player_id: int, dx: float, dy: float,
                      shooting: bool, aim_x: float, aim_y: float,
                      crouching: bool = False) -> None:
        if player_id not in self.players:
            return
        self.players[player_id].move(dx, dy, crouching)
        if shooting:
            self._spawn_bullet(player_id, aim_x, aim_y)

    def _spawn_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        player = self.players[owner_id]
        length = math.hypot(aim_x, aim_y)
        if length == 0:
            return
        ux  = aim_x / length          # 瞄準方向單位向量
        uy  = aim_y / length
        ndx = ux * BULLET_SPEED
        ndy = uy * BULLET_SPEED
        # 槍口位置 = 中心 + 前方偏移 + 右肩偏移
        # 右肩方向（逆時針 90°）：(-uy, ux)
        barrel_fwd   = PLAYER_RADIUS + 10   # 前方距離（px）
        barrel_right = 8                    # 右肩距離（px）
        rx = -uy   # 角色右方單位向量 x
        ry =  ux   # 角色右方單位向量 y
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
        """
        移動所有子彈，解析碰撞。
        obstacles   : {id: Obstacle}，伺服器傳入
        obstacle_hp : {id: int}，伺服器端 HP 追蹤
        """
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
                    player.hp -= 1
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
                    if obstacle_hp is not None:
                        obstacle_hp[oid] -= 1
                        if obstacle_hp[oid] <= 0:
                            self.destroyed_obstacles.add(oid)
                    expired.append(bid)
                    break

        for bid in expired:
            self.bullets.pop(bid, None)

    def resolve_player_collisions(self, obstacles: dict = None) -> None:
        """將所有玩家從非破壞的障礙物中推出"""
        if not obstacles:
            return
        for player in self.players.values():
            for oid, obs in obstacles.items():
                if oid in self.destroyed_obstacles:
                    continue
                new_x, new_y = obs.push_out_circle(player.x, player.y, PLAYER_RADIUS)
                player.x = new_x
                player.y = new_y
