"""
Character data — single source of truth for all character stats.

Current format:  each stat is a scalar value.
Future upgrade system: replace any scalar with a list indexed by level.
  e.g.  "hp": 100            (level 0 only)
        "hp": [100, 115, 130] (level 0 / 1 / 2)

Use get_stat(char_key, stat, level=0) everywhere so callers never need
to know whether a value is scalar or a list.
"""

# ── 角色靜態資料 ───────────────────────────────────────────────────────────
# 欄位說明：
#   name         顯示名稱
#   folder       assets/Player/ 下的資料夾名稱
#   hp           最大血量
#   gun          槍種名稱（顯示用）
#   damage       傷害描述字串；純特殊效果填 "" （面板顯示 —）
#   mag          彈夾容量字串；無彈夾概念填 ""（面板顯示 —）
#   fire_rate    射速（發/秒）；0 表示特殊/不適用
#   reload_time  換彈時間（秒）；0 表示無需換彈

CHAR_STATS: dict = {
    "hitman1": {
        "name":        "Agent",
        "folder":      "Hitman 1",
        "hp":          100,
        "gun":         "Pistol",
        "damage":      "25~30",
        "mag":         "12",
        "fire_rate":   3,
        "reload_time": 2,
    },
    "manBlue": {
        "name":        "Rambo",
        "folder":      "Man Blue",
        "hp":          200,
        "gun":         "Shotgun",
        "damage":      "",          # 越靠近越痛（特殊）
        "mag":         "6",
        "fire_rate":   2,
        "reload_time": 4,
    },
    "manBrown": {
        "name":        "Bear",
        "folder":      "Man Brown",
        "hp":          150,
        "gun":         "Machine",
        "damage":      "15~20",
        "mag":         "50",
        "fire_rate":   5,
        "reload_time": 4,
    },
    "manOld": {
        "name":        "Sniper",
        "folder":      "Man Old",
        "hp":          70,
        "gun":         "Sniper",
        "damage":      "75~80",
        "mag":         "5",
        "fire_rate":   0.5,
        "reload_time": 5,
    },
    "robot1": {
        "name":        "Robot",
        "folder":      "Robot 1",
        "hp":          120,
        "gun":         "Laser",
        "damage":      "",          # 特殊
        "mag":         "",          # 無彈夾
        "fire_rate":   0,
        "reload_time": 0,
    },
    "soldier1": {
        "name":        "Soldier",
        "folder":      "Soldier 1",
        "hp":          180,
        "gun":         "Rifle",
        "damage":      "10~15",
        "mag":         "40",
        "fire_rate":   8,
        "reload_time": 3,
    },
    "survivor1": {
        "name":        "Assassin",
        "folder":      "Survivor 1",
        "hp":          100,
        "gun":         "Shuriken",
        "damage":      "35~40",
        "mag":         "",          # 無彈夾
        "fire_rate":   4,
        "reload_time": 0,
    },
    "womanGreen": {
        "name":        "Dancer",
        "folder":      "Woman Green",
        "hp":          140,
        "gun":         "Poison",
        "damage":      "",          # 持續傷害（特殊）
        "mag":         "",          # 無彈夾
        "fire_rate":   0,
        "reload_time": 0,
    },
    "zoimbie1": {
        "name":        "Zombie",
        "folder":      "Zombie 1",
        "hp":          300,
        "gun":         "Hand",
        "damage":      "",          # 特殊
        "mag":         "",          # 無彈夾
        "fire_rate":   2,
        "reload_time": 0,
    },
}

# 固定的角色順序（選角頁面 / char_id 索引用）
CHAR_ORDER: list = [
    "hitman1", "manBlue", "manBrown", "manOld", "robot1",
    "soldier1", "survivor1", "womanGreen", "zoimbie1",
]


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
