"""
共用渲染常數與工具函式。
renderer.py 與各 chars/*/skill_fx.py 均從此處 import，避免循環依賴。
"""
import math
import random

LOGICAL_W = 1280
LOGICAL_H = 720
SCREEN_W  = LOGICAL_W
SCREEN_H  = LOGICAL_H

COL_BULLET  = {1: (160, 220, 255), 2: (255, 180, 140)}
COL_PLAYERS = {1: (100, 180, 255), 2: (255, 120, 100)}


def ws(wx, wy, cx, cy) -> tuple:
    """世界座標 → 螢幕座標。"""
    return int(wx + cx), int(wy + cy)


def facet_offsets(seed: int) -> list:
    """回傳 [(角度 rad, 半徑倍率)]，同一 seed 永遠得到同一組結果（粗糙結晶多邊形用）。
    origin: game/chars/zombie/spit_fx.py 的結晶生成技法。
    """
    rng   = random.Random(seed)
    n     = rng.randint(6, 8)
    start = rng.uniform(0, 360)
    step  = 360.0 / n
    return [
        (math.radians(start + i * step + rng.uniform(-10, 10)),
         rng.uniform(0.62, 1.0))
        for i in range(n)
    ]


def crystal_points(cx: float, cy: float, radius: float, offsets: list) -> list:
    return [
        (cx + radius * factor * math.cos(ang),
         cy + radius * factor * math.sin(ang))
        for ang, factor in offsets
    ]
