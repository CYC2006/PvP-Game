"""
Character data — single source of truth for all character stats.

Current format:  each stat is a scalar value.
Future upgrade system: replace any scalar with a list indexed by level.
  e.g.  "hp": 100            (level 0 only)
        "hp": [100, 115, 130] (level 0 / 1 / 2)

Use get_stat(char_key, stat, level=0) everywhere so callers never need
to know whether a value is scalar or a list.
"""

# ── 欄位說明 ────────────────────────────────────────────────────────────────
#   name         顯示名稱
#   folder       assets/Player/ 下的資料夾名稱
#   hp           最大血量
#   gun          槍種名稱（顯示用）
#   damage       傷害描述字串（顯示用）；特殊效果填 ""
#   damage_min   最小傷害（server 計算用）
#   damage_max   最大傷害（server 計算用）
#   mag          彈夾容量字串（顯示用）；無彈夾概念填 ""
#   speed        移動速度（像素/tick）；基準值 = 3.0
#   fire_rate    射速（發/秒）；0 表示特殊/不適用
#   reload_time  換彈時間（秒）；0 表示無需換彈
#   bullet_speed 子彈移動速度（像素/tick）；基準值 = 8.0（≈ 1×）
#   spread       子彈最大偏角（±度）；0 = 完全精準

CHAR_STATS: dict = {

    # ── 已實作角色 ─────────────────────────────────────────────────────────
    "hitman1": {
        "name":         "Agent",
        "folder":       "Hitman 1",
        "hp":           100,
        "speed":        3.0,
        "gun":          "Pistol",
        "damage":       "25~30",
        "damage_min":   25,
        "damage_max":   30,
        "mag":          "12",
        "fire_rate":    3,
        "reload_time":  2,
        "bullet_speed": 10,   # 1.25×
        "spread":       3,
    },
    "manBrown": {
        "name":         "Bear",
        "folder":       "Man Brown",
        "hp":           150,
        "speed":        2.5,
        "gun":          "Machine",
        "damage":       "15~20",
        "damage_min":   15,
        "damage_max":   20,
        "mag":          "50",
        "fire_rate":    5,
        "reload_time":  4,
        "bullet_speed": 8,    # 1× baseline
        "spread":       7,
    },
    "manOld": {
        "name":         "Sniper",
        "folder":       "Man Old",
        "hp":           70,
        "speed":        3.5,
        "gun":          "Sniper",
        "damage":       "75~80",
        "damage_min":   75,
        "damage_max":   80,
        "mag":          "5",
        "fire_rate":    0.5,
        "reload_time":  5,
        "bullet_speed": 20,   # 2.5× 超快
        "spread":       1,
    },
    "soldier1": {
        "name":         "Soldier",
        "folder":       "Soldier 1",
        "hp":           180,
        "speed":        3.5,
        "gun":          "Rifle",
        "damage":       "10~15",
        "damage_min":   10,
        "damage_max":   15,
        "mag":          "40",
        "fire_rate":    8,
        "reload_time":  3,
        "bullet_speed": 12,   # 1.5×
        "spread":       4,
    },
    "survivor1": {
        "name":         "Assassin",
        "folder":       "Survivor 1",
        "hp":           100,
        "speed":        6.0,
        "gun":          "Shuriken",
        "damage":       "35~40",
        "damage_min":   35,
        "damage_max":   40,
        "mag":          "",          # 無彈夾（無限）
        "fire_rate":    4,
        "reload_time":  0,
        "bullet_speed": 14,   # 1.75× 手裡劍飛快
        "spread":       2,
    },

    # ── 未實作角色（damage_min/max 為預留值）──────────────────────────────
    "manBlue": {
        "name":         "Rambo",
        "folder":       "Man Blue",
        "hp":           200,
        "speed":        2.0,
        "gun":          "Shotgun",
        "damage":       "",          # 越靠近越痛（待實作）
        "damage_min":   20,
        "damage_max":   40,
        "mag":          "6",
        "fire_rate":    2,
        "reload_time":  4,
        "bullet_speed": 7,    # 0.875× 散彈較慢
        "spread":       15,
    },
    "robot1": {
        "name":         "Robot",
        "folder":       "Robot 1",
        "hp":           120,
        "speed":        4.0,
        "gun":          "Laser",
        "damage":       "",          # 特殊（待實作）
        "damage_min":   15,
        "damage_max":   25,
        "mag":          "",
        "fire_rate":    0,
        "reload_time":  0,
        "bullet_speed": 20,   # 2.5× 雷射
        "spread":       0,
    },
    "womanGreen": {
        "name":         "Dancer",
        "folder":       "Woman Green",
        "hp":           140,
        "speed":        4.0,
        "gun":          "Poison",
        "damage":       "",          # 持續傷害（待實作）
        "damage_min":   5,
        "damage_max":   10,
        "mag":          "",
        "fire_rate":    0,
        "reload_time":  0,
        "bullet_speed": 5,    # 0.625× 毒霧緩慢
        "spread":       12,
    },
    "zoimbie1": {
        "name":         "Zombie",
        "folder":       "Zombie 1",
        "hp":           300,
        "speed":        4.5,
        "gun":          "Hand",
        "damage":       "",          # 特殊（待實作）
        "damage_min":   20,
        "damage_max":   30,
        "mag":          "",
        "fire_rate":    2,
        "reload_time":  0,
        "bullet_speed": 4,    # 0.5× 很慢
        "spread":       20,
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
