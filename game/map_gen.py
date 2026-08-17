"""
Runtime map-obstacle generator.
Called at game start to produce a random {id: Obstacle} dict from a seed.
The same seed always produces the same layout, so both server and client
generate identical obstacles without transmitting the full obstacle list.
"""
import math
import random
from game.obstacle import Obstacle, OBSTACLE_CONFIG, HITBOX_RATIO

_SPAWN_CLEAR_R = 40    # extra buffer beyond obstacle radius around each spawn point
_MAX_TRIES     = 200   # placement attempts per obstacle before giving up


# ── Helpers ─────────────────────────────────────────────────────────────────

def _spawn_zones(map_w: int, map_h: int) -> list:
    return [(map_w // 4, map_h // 2), (map_w * 3 // 4, map_h // 2)]


def _overlaps_spawn(x: float, y: float, r: float, zones: list) -> bool:
    for sx, sy in zones:
        if math.hypot(x - sx, y - sy) < _SPAWN_CLEAR_R + r:
            return True
    return False


def _overlaps_list(x: float, y: float, kind: str, scale: float,
                   avoid: list) -> bool:
    """True if bounding box of (x, y, kind, scale) overlaps any obstacle in avoid."""
    cfg = OBSTACLE_CONFIG[kind]
    hw  = cfg["width"]  * scale / 2 + 4
    hh  = cfg["height"] * scale / 2 + 4
    for obs in avoid:
        ehw = obs.width  / 2 + 4
        ehh = obs.height / 2 + 4
        if abs(x - obs.x) < hw + ehw and abs(y - obs.y) < hh + ehh:
            return True
    return False


def _try_place(rng, kind: str, scale: float,
               map_w: int, map_h: int, edge: int,
               avoid: list, zones: list):
    """Try up to _MAX_TRIES positions; return (x, y) or None."""
    cfg  = OBSTACLE_CONFIG[kind]
    hw   = cfg["width"]  * scale / 2
    hh   = cfg["height"] * scale / 2
    r    = max(hw, hh)
    x_lo, x_hi = edge + hw, map_w - edge - hw
    y_lo, y_hi = edge + hh, map_h - edge - hh
    if x_lo >= x_hi or y_lo >= y_hi:
        return None
    for _ in range(_MAX_TRIES):
        x = rng.uniform(x_lo, x_hi)
        y = rng.uniform(y_lo, y_hi)
        if not _overlaps_spawn(x, y, r, zones) and \
           not _overlaps_list(x, y, kind, scale, avoid):
            return x, y
    return None


def _make(oid: int, kind: str, x: float, y: float,
          scale: float = 1.0, angle_rad: float = 0.0) -> Obstacle:
    cfg = OBSTACLE_CONFIG[kind]
    return Obstacle(
        id=oid, x=x, y=y, kind=kind,
        width=float(cfg["width"]  * scale),
        height=float(cfg["height"] * scale),
        hp=cfg["hp"],
        angle=angle_rad,
        shape=cfg.get("shape", "obb"),
        destructible=cfg.get("destructible", True),
        radius_ratio=cfg.get("radius_ratio", HITBOX_RATIO),
        solid=cfg.get("solid", True),
    )


# ── Per-map generators ───────────────────────────────────────────────────────

# Storage (1680×1680)
_S_GRID  = 5
_S_STEP  = 1680 // (_S_GRID + 1)   # 280
_S_X_GR  = [_S_STEP * (i + 1) for i in range(_S_GRID)]
_S_Y_GR  = [_S_STEP * (i + 1) for i in range(_S_GRID)]
_S_OFF   = [(-32, -32), (32, -32), (-32, 32), (32, 32)]
_S_CTR   = (2, 2)
_S_PLACE = 20
_S_GOLDP = 0.25


def _gen_storage(seed: int, map_w: int = 1680, map_h: int = 1680) -> dict:
    rng     = random.Random(seed)
    others  = [(r, c) for r in range(_S_GRID) for c in range(_S_GRID)
               if (r, c) != _S_CTR]
    occupied = set(rng.sample(others, _S_PLACE))
    occupied.add(_S_CTR)

    obs = {}
    oid = 1
    for r, c in sorted(occupied):
        cx, cy = _S_X_GR[c], _S_Y_GR[r]
        for dx, dy in _S_OFF:
            kind = "box_special" if (r, c) == _S_CTR or rng.random() < _S_GOLDP \
                   else "box_normal"
            obs[oid] = _make(oid, kind, float(cx + dx), float(cy + dy))
            oid += 1
    return obs


def _gen_grassland(seed: int, map_w: int = 1920, map_h: int = 1080) -> dict:
    rng    = random.Random(seed)
    obs    = {}
    oid    = 1
    trees  = []   # placed tree obstacles
    solids = []   # placed rock + box obstacles
    zones  = _spawn_zones(map_w, map_h)
    edge   = 60

    n_trees = rng.randint(4, 6)
    n_rocks = rng.randint(10, 20)
    n_boxes = rng.randint(30, 40)

    # Trees first — avoid other trees + spawn zones
    for _ in range(n_trees):
        scale = rng.uniform(0.83, 1.25)
        pos = _try_place(rng, "tree_1", scale, map_w, map_h, edge, trees, zones)
        if pos:
            o = _make(oid, "tree_1", pos[0], pos[1], scale)
            obs[oid] = o; trees.append(o); oid += 1

    # Rocks — avoid other rocks + spawn zones; CAN be under trees
    for _ in range(n_rocks):
        kind = rng.choice(["rock_1", "rock_2"])
        pos = _try_place(rng, kind, 1.0, map_w, map_h, edge, solids, zones)
        if pos:
            o = _make(oid, kind, pos[0], pos[1])
            obs[oid] = o; solids.append(o); oid += 1

    # Boxes — avoid all solid obstacles + trees + spawn zones
    # Each box has a random scale (0.72-1.48) and angle (±45°), matching original map style
    all_avoid = solids + trees
    for _ in range(n_boxes):
        kind  = "box_special" if rng.random() < 0.10 else "box_normal"
        scale = rng.uniform(0.72, 1.48)
        pos   = _try_place(rng, kind, scale, map_w, map_h, edge, all_avoid, zones)
        if pos:
            angle = math.radians(rng.uniform(-45, 45))
            o = _make(oid, kind, pos[0], pos[1], scale, angle)
            obs[oid] = o; solids.append(o); all_avoid.append(o); oid += 1

    return obs


def _gen_treepath(seed: int, map_w: int = 2560, map_h: int = 720) -> dict:
    rng    = random.Random(seed)
    obs    = {}
    oid    = 1
    trees  = []
    rocks  = []
    zones  = _spawn_zones(map_w, map_h)
    edge   = 60

    n_trees = rng.randint(10, 12)
    n_rocks = rng.randint(50, 60)

    # Trees — avoid other trees + spawn zones
    for _ in range(n_trees):
        scale = rng.uniform(0.83, 1.25)
        pos = _try_place(rng, "tree_1", scale, map_w, map_h, edge, trees, zones)
        if pos:
            o = _make(oid, "tree_1", pos[0], pos[1], scale)
            obs[oid] = o; trees.append(o); oid += 1

    # Rocks — avoid other rocks + spawn zones; CAN be placed under trees
    for _ in range(n_rocks):
        kind = rng.choice(["rock_1", "rock_2"])
        pos = _try_place(rng, kind, 1.0, map_w, map_h, edge, rocks, zones)
        if pos:
            o = _make(oid, kind, pos[0], pos[1])
            obs[oid] = o; rocks.append(o); oid += 1

    return obs


# ── Public API ───────────────────────────────────────────────────────────────

_DISPATCH = {
    "grassland": _gen_grassland,
    "treepath":  _gen_treepath,
    "storage":   _gen_storage,
}


def generate(map_name: str, seed: int, map_w: int, map_h: int) -> dict:
    """Generate obstacles for a dynamic map. Returns {id: Obstacle} dict."""
    fn = _DISPATCH.get(map_name)
    return fn(seed, map_w, map_h) if fn else {}
