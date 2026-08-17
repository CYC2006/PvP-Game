import random
from game.obstacle import Obstacle, OBSTACLE_CONFIG, HITBOX_RATIO

_MAP_SIZE = 1680
_GRID_N   = 5
_STEP     = _MAP_SIZE // (_GRID_N + 1)          # 280
_X_GRID   = [_STEP * (i + 1) for i in range(_GRID_N)]  # [280,560,840,1120,1400]
_Y_GRID   = [_STEP * (i + 1) for i in range(_GRID_N)]
_OFFSETS  = [(-32, -32), (32, -32), (-32, 32), (32, 32)]
_CENTER   = (2, 2)
_PLACED   = 20    # non-centre clusters to place (out of 24)
_GOLD_P   = 0.25  # probability each non-centre box is gold


def generate(seed: int) -> dict:
    """Return {id: Obstacle} for a Storage map layout generated from seed.

    Centre cluster (row=2, col=2) is always 4 gold boxes.
    20 of the remaining 24 positions are randomly occupied.
    """
    rng     = random.Random(seed)
    others  = [(r, c) for r in range(_GRID_N)
               for c in range(_GRID_N) if (r, c) != _CENTER]
    occupied = set(rng.sample(others, _PLACED))
    occupied.add(_CENTER)

    obs = {}
    oid = 1
    for r, c in sorted(occupied):
        cx, cy = _X_GRID[c], _Y_GRID[r]
        for dx, dy in _OFFSETS:
            if (r, c) == _CENTER:
                kind = "box_special"
            else:
                kind = "box_special" if rng.random() < _GOLD_P else "box_normal"
            cfg = OBSTACLE_CONFIG[kind]
            obs[oid] = Obstacle(
                id=oid,
                x=float(cx + dx),
                y=float(cy + dy),
                kind=kind,
                width=float(cfg["width"]),
                height=float(cfg["height"]),
                hp=cfg["hp"],
                angle=0.0,
                shape=cfg.get("shape", "obb"),
                destructible=cfg.get("destructible", True),
                radius_ratio=cfg.get("radius_ratio", HITBOX_RATIO),
                solid=cfg.get("solid", True),
            )
            oid += 1
    return obs
