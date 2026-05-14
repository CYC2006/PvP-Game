"""
共用渲染常數與工具函式。
renderer.py 與各 chars/*/skill_fx.py 均從此處 import，避免循環依賴。
"""

LOGICAL_W = 1280
LOGICAL_H = 720
SCREEN_W  = LOGICAL_W
SCREEN_H  = LOGICAL_H

COL_BULLET  = {1: (160, 220, 255), 2: (255, 180, 140)}
COL_PLAYERS = {1: (100, 180, 255), 2: (255, 120, 100)}


def ws(wx, wy, cx, cy) -> tuple:
    """世界座標 → 螢幕座標。"""
    return int(wx + cx), int(wy + cy)
