from dataclasses import dataclass, field
import math

MAP_WIDTH  = 3840
MAP_HEIGHT = 2160

PLAYER_SPEED  = 3.0
PLAYER_RADIUS = 16
BULLET_SPEED  = 8.0
BULLET_RADIUS = 5
MAX_HP        = 5
BULLET_MAX_RANGE = 900   # pixels before bullet disappears


@dataclass
class Player:
    id: int
    x: float
    y: float
    speed: float = PLAYER_SPEED
    hp: int = MAX_HP

    def move(self, dx: float, dy: float) -> None:
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length > 0:
            dx, dy = dx / length, dy / length
        self.x = max(PLAYER_RADIUS, min(MAP_WIDTH  - PLAYER_RADIUS, self.x + dx * self.speed))
        self.y = max(PLAYER_RADIUS, min(MAP_HEIGHT - PLAYER_RADIUS, self.y + dy * self.speed))

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
    dx: float       # normalised direction × speed
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
    players: dict = field(default_factory=dict)
    bullets: dict = field(default_factory=dict)   # bullet_id → Bullet
    tick: int = 0
    _next_bullet_id: int = 0

    def add_player(self, player_id: int) -> Player:
        spawn_x = MAP_WIDTH  // 4 if player_id == 1 else MAP_WIDTH  * 3 // 4
        spawn_y = MAP_HEIGHT // 2
        self.players[player_id] = Player(id=player_id, x=float(spawn_x), y=float(spawn_y))
        return self.players[player_id]

    def apply_command(self, player_id: int, dx: float, dy: float,
                      shooting: bool, aim_x: float, aim_y: float) -> None:
        if player_id not in self.players:
            return
        self.players[player_id].move(dx, dy)
        if shooting:
            self._spawn_bullet(player_id, aim_x, aim_y)

    def _spawn_bullet(self, owner_id: int, aim_x: float, aim_y: float) -> None:
        player = self.players[owner_id]
        length = math.hypot(aim_x, aim_y)
        if length == 0:
            return
        ndx = aim_x / length * BULLET_SPEED
        ndy = aim_y / length * BULLET_SPEED
        bid = self._next_bullet_id
        self._next_bullet_id = (self._next_bullet_id + 1) % 256
        self.bullets[bid] = Bullet(
            id=bid, owner_id=owner_id,
            x=player.x, y=player.y,
            dx=ndx, dy=ndy,
        )

    def step_bullets(self) -> None:
        """Move all bullets and resolve hits. Called once per server tick."""
        expired = []
        for bid, bullet in self.bullets.items():
            bullet.step()
            if bullet.is_expired():
                expired.append(bid)
                continue
            # collision with players
            for pid, player in self.players.items():
                if pid == bullet.owner_id:
                    continue
                if math.hypot(bullet.x - player.x, bullet.y - player.y) < PLAYER_RADIUS + BULLET_RADIUS:
                    player.hp -= 1
                    expired.append(bid)
                    if player.hp <= 0:
                        player.respawn()
                    break
        for bid in expired:
            self.bullets.pop(bid, None)
