"""
Character data — 從專案根目錄 chars.csv 讀取。

chars.csv 速度欄位說明：
  speed_pxs        移動速度（px/s）；÷60 → px/tick 存入 CHAR_STATS['speed']
  bspeed_pxs       子彈速度（px/s）；÷480 → 乘數 存入 CHAR_STATS['bullet_speed']
  bspeed_min_pxs   子彈初速下限（px/s）；同上換算

對外介面與原來完全相同：
  CHAR_STATS   dict[char_key → stat dict]
  CHAR_ORDER   list[char_key]（依 CSV 行序）
  get_stat(char_key, stat, level=0)
"""

import csv
import os

_CSV_PATH   = os.path.join(os.path.dirname(__file__), '..', 'chars.csv')
_TICK_RATE  = 60       # fps
_BULLET_BASE = 8.0     # BULLET_SPEED (px/tick) in state.py
_BSPEED_DENOM = _BULLET_BASE * _TICK_RATE   # 480：px/s → 乘數 換算基底


def _load() -> tuple[dict, list]:
    stats: dict = {}
    order: list = []

    with open(_CSV_PATH, encoding='utf-8', newline='') as f:
        # 跳過以 # 開頭的注釋行
        lines = [l for l in f if not l.startswith('#')]

    for row in csv.DictReader(lines):
        key = row['char_key'].strip()
        order.append(key)

        def f(col: str, default: float = 0.0) -> float:
            v = row.get(col, '').strip()
            return float(v) if v else default

        def i(col: str, default: int = 0) -> int:
            v = row.get(col, '').strip()
            return int(v) if v else default

        def s(col: str) -> str:
            return row.get(col, '').strip()

        d: dict = {
            'name':         s('name'),
            'folder':       s('folder'),
            'hp':           i('hp'),
            'speed':        f('speed_pxs') / _TICK_RATE,        # px/s → px/tick
            'gun':           s('gun'),
            'damage_min':    i('dmg_min'),
            'damage_max':    i('dmg_max'),
            'mag':           s('mag'),
            'fire_interval': f('fire_interval'),    # 每次射擊間隔（秒）
            'reload_time':   f('reload_time'),
            'bullet_speed':  f('bspeed_pxs') / _BSPEED_DENOM,   # px/s → 乘數
            'spread':        f('spread'),
        }

        # 特殊武器欄位（空白 → 略過；apply_char_stats 會用預設值）
        _opt = [
            ('bspeed_min_pxs',        'bullet_speed_min', lambda v: float(v) / _BSPEED_DENOM),
            ('pellet_count',          'pellet_count',      lambda v: int(float(v))),
            ('pellet_interval(tick)', 'pellet_interval',   lambda v: float(v)),
            ('shoot_slow',           'shoot_slow',         lambda v: float(v)),
            ('shoot_slow_dur(tick)', 'shoot_slow_dur',     lambda v: int(float(v))),
            ('brange_px',             'bullet_range',      lambda v: float(v)),
            ('brange_min_px',         'bullet_range_min',  lambda v: float(v)),
            ('lifetime',              'bullet_lifetime',   lambda v: float(v)),
            ('linger',                'bullet_linger',     lambda v: float(v)),
            ('dot_interval',          'dot_interval',      lambda v: int(float(v))),
        ]
        for csv_col, stat_key, conv in _opt:
            v = row.get(csv_col, '').strip()
            if v:
                d[stat_key] = conv(v)

        # damage 顯示字串：由 dmg_min/dmg_max/pellet_count 自動生成
        dmin, dmax = d['damage_min'], d['damage_max']
        pellets    = d.get('pellet_count', 1)
        if dmin == 0 and dmax == 0:
            d['damage'] = ""
        elif dmin == dmax:
            d['damage'] = str(dmin)
        elif pellets > 1:
            d['damage'] = f"{dmin}~{dmax} ×{pellets}"   # ×
        else:
            d['damage'] = f"{dmin}~{dmax}"

        stats[key] = d

    return stats, order


CHAR_STATS, CHAR_ORDER = _load()


def reload() -> None:
    """重新從 CSV 載入所有角色數值（每局開始前呼叫，改完 CSV 不用重啟程式）。"""
    global CHAR_STATS, CHAR_ORDER
    CHAR_STATS, CHAR_ORDER = _load()


def get_stat(char_key: str, stat: str, level: int = 0):
    """
    取得角色在指定等級的數值。

    - 若數值為 scalar，直接回傳（忽略 level）。
    - 若數值為 list，回傳 list[min(level, len-1)]（超出上限取最後一級）。
    - 未來升級系統只需把 scalar 換成 list，呼叫端無需修改。
    """
    val = CHAR_STATS[char_key][stat]
    if isinstance(val, list):
        return val[min(level, len(val) - 1)]
    return val
