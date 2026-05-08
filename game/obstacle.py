import math
import json
from dataclasses import dataclass, field

OBSTACLE_CONFIG: dict = {
    "box_1": {"width": 64, "height": 64, "hp": 3},
    "box_2": {"width": 64, "height": 64, "hp": 3},
}

# hitbox 比視覺小一圈，讓「擦邊而過」體驗更舒適
HITBOX_RATIO = 0.82


@dataclass
class Obstacle:
    id: int
    x: float        # 中心 x（世界座標）
    y: float        # 中心 y（世界座標）
    kind: str
    width: float
    height: float
    hp: int
    angle: float = 0.0   # 旋轉角度（弧度），用於 OBB 與繪圖

    # ── OBB hitbox 半邊長 ────────────────────────────────────────
    @property
    def _hw(self) -> float:
        return self.width  * HITBOX_RATIO / 2

    @property
    def _hh(self) -> float:
        return self.height * HITBOX_RATIO / 2

    # ── 世界座標 → 本地座標（旋轉 -angle） ───────────────────────
    def _to_local(self, cx: float, cy: float):
        dx = cx - self.x
        dy = cy - self.y
        c = math.cos(-self.angle)
        s = math.sin(-self.angle)
        return dx * c - dy * s, dx * s + dy * c

    # ── OBB 碰撞偵測 ──────────────────────────────────────────────
    def collides_circle(self, cx: float, cy: float, radius: float) -> bool:
        lx, ly = self._to_local(cx, cy)
        nx = max(-self._hw, min(lx, self._hw))
        ny = max(-self._hh, min(ly, self._hh))
        return (lx - nx) ** 2 + (ly - ny) ** 2 < radius * radius

    # ── OBB 推出圓形 ──────────────────────────────────────────────
    def push_out_circle(self, cx: float, cy: float, radius: float):
        """
        將圓形從 OBB 中推出，回傳 (new_cx, new_cy)。
        1. 轉換到木箱本地座標
        2. 做 AABB-circle 推出
        3. 把推出向量轉回世界座標
        """
        lx, ly = self._to_local(cx, cy)
        hw, hh = self._hw, self._hh

        closest_x = max(-hw, min(lx, hw))
        closest_y = max(-hh, min(ly, hh))
        diff_x    = lx - closest_x
        diff_y    = ly - closest_y
        dist_sq   = diff_x ** 2 + diff_y ** 2

        if dist_sq >= radius * radius:
            return cx, cy   # 沒有重疊

        dist = math.sqrt(dist_sq)

        if dist < 1e-6:
            # 圓心在矩形內部，沿最短路徑推出
            options = [
                (lx + hw + radius, -(lx + hw + radius), 0.0),
                (hw - lx + radius,   hw - lx + radius,  0.0),
                (ly + hh + radius, 0.0, -(ly + hh + radius)),
                (hh - ly + radius, 0.0,   hh - ly + radius),
            ]
            _, push_lx, push_ly = min(options, key=lambda e: e[0])
        else:
            overlap  = radius - dist
            push_lx  = (diff_x / dist) * overlap
            push_ly  = (diff_y / dist) * overlap

        # 推出向量轉回世界座標
        c = math.cos(self.angle)
        s = math.sin(self.angle)
        return (
            cx + push_lx * c - push_ly * s,
            cy + push_lx * s + push_ly * c,
        )


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
            angle=math.radians(entry.get("angle_deg", 0)),
        )
        obstacles[obs.id] = obs
    return obstacles
