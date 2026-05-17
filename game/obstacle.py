import math
import json
from dataclasses import dataclass, field

OBSTACLE_CONFIG: dict = {
    "box_normal":  {"width": 64, "height": 64, "hp": 60,  "shape": "obb", "destructible": True},
    "box_special": {"width": 64, "height": 64, "hp": 120, "shape": "obb", "destructible": True},
    # radius_ratio：石頭在 PNG 裡只佔部分面積，用量測到的視覺半徑比例取代 HITBOX_RATIO
    "rock_1": {"width": 80, "height": 80, "hp": 240, "shape": "circle", "destructible": True, "radius_ratio": 0.70},
    "rock_2": {"width": 80, "height": 80, "hp": 240, "shape": "circle", "destructible": True, "radius_ratio": 0.52},
    # solid=False：玩家與子彈可直接穿過；最頂層繪製；本地玩家在樹下時半透明
    # base 240；map 裡用 scale 0.83~1.25 讓實際尺寸落在 200~300px
    "tree_1": {"width": 240, "height": 240, "hp": 9999, "shape": "circle",
               "destructible": False, "solid": False, "radius_ratio": 0.65},
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
    solid:        bool  = True        # False → 玩家/子彈穿透，繪製於最頂層（樹/草叢）

    # 預計算不變量（angle/width/height 在 load 後不再改變）
    _collision_radius: float = field(init=False, repr=False)
    _hw: float               = field(init=False, repr=False)
    _hh: float               = field(init=False, repr=False)
    _cos_neg: float          = field(init=False, repr=False)  # cos(-angle)
    _sin_neg: float          = field(init=False, repr=False)  # sin(-angle)
    _cos_pos: float          = field(init=False, repr=False)  # cos(angle)
    _sin_pos: float          = field(init=False, repr=False)  # sin(angle)

    def __post_init__(self) -> None:
        self._collision_radius = (self.width / 2) * self.radius_ratio
        self._hw      = self.width  * HITBOX_RATIO / 2
        self._hh      = self.height * HITBOX_RATIO / 2
        self._cos_neg = math.cos(-self.angle)
        self._sin_neg = math.sin(-self.angle)
        self._cos_pos = math.cos(self.angle)
        self._sin_pos = math.sin(self.angle)

    # ── 世界座標 → OBB 本地座標 ───────────────────────────────────
    def _to_local(self, cx: float, cy: float):
        dx = cx - self.x
        dy = cy - self.y
        return dx * self._cos_neg - dy * self._sin_neg, dx * self._sin_neg + dy * self._cos_neg

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

        return (
            cx + push_lx * self._cos_pos - push_ly * self._sin_pos,
            cy + push_lx * self._sin_pos + push_ly * self._cos_pos,
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
            solid=cfg.get("solid", True),
        )
        obstacles[obs.id] = obs
    return obstacles
