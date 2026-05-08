import math
import json
from dataclasses import dataclass

# 每種障礙物的尺寸與初始血量
OBSTACLE_CONFIG: dict = {
    "box_1": {"width": 64, "height": 64, "hp": 3},
    "box_2": {"width": 64, "height": 64, "hp": 3},
}


@dataclass
class Obstacle:
    id: int
    x: float        # 中心 x
    y: float        # 中心 y
    kind: str
    width: float
    height: float
    hp: int         # 初始血量（0 = 不可破壞）

    # ── AABB 邊界屬性 ────────────────────────────────────────────
    @property
    def left(self):   return self.x - self.width  / 2
    @property
    def right(self):  return self.x + self.width  / 2
    @property
    def top(self):    return self.y - self.height / 2
    @property
    def bottom(self): return self.y + self.height / 2

    # ── 碰撞偵測 ─────────────────────────────────────────────────
    def collides_circle(self, cx: float, cy: float, radius: float) -> bool:
        """圓形是否與此矩形碰撞"""
        closest_x = max(self.left, min(cx, self.right))
        closest_y = max(self.top,  min(cy, self.bottom))
        dx = cx - closest_x
        dy = cy - closest_y
        return dx * dx + dy * dy < radius * radius

    def push_out_circle(self, cx: float, cy: float, radius: float):
        """將圓形推出矩形，回傳 (new_cx, new_cy)"""
        closest_x = max(self.left, min(cx, self.right))
        closest_y = max(self.top,  min(cy, self.bottom))
        dx = cx - closest_x
        dy = cy - closest_y
        dist_sq = dx * dx + dy * dy

        if dist_sq >= radius * radius:
            return cx, cy   # 無重疊

        dist = math.sqrt(dist_sq)

        if dist < 1e-6:
            # 圓心在矩形內部，沿最近邊緣推出
            options = [
                (cx - self.left   + radius, self.left   - radius, cy),
                (self.right - cx  + radius, self.right  + radius, cy),
                (cy - self.top    + radius, cx, self.top    - radius),
                (self.bottom - cy + radius, cx, self.bottom + radius),
            ]
            _, new_x, new_y = min(options, key=lambda e: e[0])
            return new_x, new_y

        # 沿碰撞法線推出
        overlap = radius - dist
        return cx + (dx / dist) * overlap, cy + (dy / dist) * overlap


def load_map(path: str) -> dict:
    """從 JSON 讀取障礙物清單，回傳 {id: Obstacle}"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    obstacles = {}
    for entry in data["obstacles"]:
        kind = entry["kind"]
        cfg  = OBSTACLE_CONFIG[kind]
        obs  = Obstacle(
            id=entry["id"],
            x=float(entry["x"]),
            y=float(entry["y"]),
            kind=kind,
            width=float(cfg["width"]),
            height=float(cfg["height"]),
            hp=cfg["hp"],
        )
        obstacles[obs.id] = obs
    return obstacles
