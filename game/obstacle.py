import math
import json
from dataclasses import dataclass

OBSTACLE_CONFIG: dict = {
    "box_1":       {"width": 64, "height": 64, "hp": 50,  "shape": "obb", "destructible": True},
    "box_special": {"width": 64, "height": 64, "hp": 100, "shape": "obb", "destructible": True},
    # radius_ratio：石頭在 PNG 裡只佔部分面積，用量測到的視覺半徑比例取代 HITBOX_RATIO
    "rock_1": {"width": 80, "height": 80, "hp": 200, "shape": "circle", "destructible": True, "radius_ratio": 0.70},
    "rock_2": {"width": 80, "height": 80, "hp": 200, "shape": "circle", "destructible": True, "radius_ratio": 0.52},
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
    angle:        float = 0.0         # 旋轉角度（弧度）
    shape:        str   = "obb"       # "obb" | "circle"
    destructible: bool  = True        # False → 子彈會彈開但不扣血、不摧毀
    radius_ratio: float = HITBOX_RATIO  # circle shape 用：碰撞半徑 = (width/2)*ratio

    # ── circle shape 用的碰撞半徑 ────────────────────────────────
    @property
    def _collision_radius(self) -> float:
        return (self.width / 2) * self.radius_ratio

    # ── OBB 半邊長 ───────────────────────────────────────────────
    @property
    def _hw(self) -> float:
        return self.width  * HITBOX_RATIO / 2

    @property
    def _hh(self) -> float:
        return self.height * HITBOX_RATIO / 2

    # ── 世界座標 → OBB 本地座標 ───────────────────────────────────
    def _to_local(self, cx: float, cy: float):
        dx = cx - self.x
        dy = cy - self.y
        c  = math.cos(-self.angle)
        s  = math.sin(-self.angle)
        return dx * c - dy * s, dx * s + dy * c

    # ── 碰撞偵測 ─────────────────────────────────────────────────
    def collides_circle(self, cx: float, cy: float, radius: float) -> bool:
        if self.shape == "circle":
            return math.hypot(cx - self.x, cy - self.y) < self._collision_radius + radius
        # OBB
        lx, ly = self._to_local(cx, cy)
        nx = max(-self._hw, min(lx, self._hw))
        ny = max(-self._hh, min(ly, self._hh))
        return (lx - nx) ** 2 + (ly - ny) ** 2 < radius * radius

    # ── 推出圓形 ─────────────────────────────────────────────────
    def push_out_circle(self, cx: float, cy: float, radius: float):
        if self.shape == "circle":
            dx   = cx - self.x
            dy   = cy - self.y
            dist = math.hypot(dx, dy)
            min_dist = self._collision_radius + radius
            if dist >= min_dist:
                return cx, cy
            if dist < 1e-6:
                return cx, cy - min_dist      # 圓心重合時向上推
            scale = min_dist / dist
            return self.x + dx * scale, self.y + dy * scale

        # OBB（原始邏輯不變）
        lx, ly = self._to_local(cx, cy)
        hw, hh = self._hw, self._hh

        closest_x = max(-hw, min(lx, hw))
        closest_y = max(-hh, min(ly, hh))
        diff_x    = lx - closest_x
        diff_y    = ly - closest_y
        dist_sq   = diff_x ** 2 + diff_y ** 2

        if dist_sq >= radius * radius:
            return cx, cy

        dist = math.sqrt(dist_sq)

        if dist < 1e-6:
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

        c = math.cos(self.angle)
        s = math.sin(self.angle)
        return (
            cx + push_lx * c - push_ly * s,
            cy + push_lx * s + push_ly * c,
        )


def load_map(path: str) -> dict:
    """從 JSON 讀取障礙物清單，回傳 {id: Obstacle}。
    支援 JSON 欄位：id, kind, x, y, angle_deg, scale（可選，預設 1.0）
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    obstacles = {}
    for entry in data["obstacles"]:
        kind  = entry["kind"]
        cfg   = OBSTACLE_CONFIG[kind]
        scale = float(entry.get("scale", 1.0))
        obs   = Obstacle(
            id=entry["id"],
            x=float(entry["x"]),
            y=float(entry["y"]),
            kind=kind,
            width=float(cfg["width"])  * scale,
            height=float(cfg["height"]) * scale,
            hp=cfg["hp"],
            angle=math.radians(entry.get("angle_deg", 0)),
            shape=cfg.get("shape", "obb"),
            destructible=cfg.get("destructible", True),
            radius_ratio=cfg.get("radius_ratio", HITBOX_RATIO),
        )
        obstacles[obs.id] = obs
    return obstacles
