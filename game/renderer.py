import os
import math
import time
import random
import pygame
from game.state import (GameState, PLAYER_RADIUS, BULLET_RADIUS)
import game.input as _inp
from game.input import MAGAZINE_SIZE
from game.render_utils import (LOGICAL_W, LOGICAL_H, SCREEN_W, SCREEN_H, ws as _ws,
                               COL_BULLET as _COL_BULLET_UTILS,
                               facet_offsets as _facet_offsets, crystal_points as _crystal_points)

from game.chars.agent    import flash_fx
from game.chars.agent    import burst_bullet_fx
from game.chars.agent    import dash_fx as agent_dash_fx
from game.chars.vince    import grenade_fx, airstrike_fx
from game.chars.vince    import taunt_fx as vince_taunt_fx
from game.chars.pioneer  import stun_bullet_fx
from game.chars.vince.giant_state import get_scale as _giant_get_scale, GROW_TICKS, ACTIVE_TICKS, TOTAL_TICKS
from game.chars.hunter   import mini_grenade_fx
from game.chars.hunter   import air_cannon_fx
from game.chars.zombie   import blade_fx
from game.chars.zombie   import jump_fx as zombie_jump_fx
from game.chars.zombie   import spit_fx as zombie_spit_fx
from game.chars.zombie   import rage_fx as zombie_rage_fx
from game.chars.assassin import smoke_fx, shuriken_fx, r_dash_fx
from game.chars.poisoner   import bubble_fx
from game.chars.poisoner   import poison_pool_fx
from game.chars.poisoner   import e_skill_fx as poisoner_e_fx
from game.chars.marksman     import explosion_bullet_fx
from game.chars.marksman     import mine_fx as marksman_mine_fx
from game.chars.marksman     import turret_fx as marksman_turret_fx
from game.chars.marksman     import barrage_fx as marksman_barrage_fx
from game.chars.pioneer  import shield_fx as pioneer_shield_fx
from game.chars.pioneer  import jump_fx as pioneer_jump_fx
from game.chars.robot    import push_fx as robot_push_fx
from game.chars.robot    import mark_fx as robot_mark_fx
from game.chars.robot    import e_fx as robot_e_fx

# colours
COL_BG         = (30,  30,  30)
COL_MAP_BG     = (45,  55,  45)
COL_GRID       = (55,  65,  55)
COL_MAP_BORDER = (80,  80,  80)
COL_TEXT       = (220, 220, 220)
COL_SELF_RIM   = (255, 255, 255)
COL_OTHER_RIM  = (200, 200, 200)
COL_PLAYERS    = {1: (100, 180, 255), 2: (255, 120, 100)}
COL_BULLET     = _COL_BULLET_UTILS   # 來自 render_utils，保持名稱相容
COL_HP_BG      = (60,  20,  20)
COL_HP_FILL    = (220, 60,  60)
COL_HP_BORDER  = (180, 180, 180)

GRID_SIZE            = 120
HP_BAR_X             = 20
HP_BAR_Y_FROM_BOTTOM = 62
HP_BAR_W             = 220
HP_BAR_H             = 26
HP_PIP_GAP           = 4
PLAYER_SPRITE_SCALE  = 1.5   # 原圖 33–54 × 43 px，放大後約 50–81 × 65 px

SKILL_CIRCLE_R   = 34   # 17 × 2
SKILL_CIRCLE_GAP = 10
SKILL_STEP       = SKILL_CIRCLE_R * 2 + SKILL_CIRCLE_GAP   # 78 px
_SKILL_SLOTS     = ('rmb', 'space', 'e', 'r', 'q')
_SKILL_LABELS    = ('MB', 'SP', 'E', 'F', 'Q')

COL_SKILL_READY_BORDER = (220, 220, 255)
COL_SKILL_CD_BORDER    = ( 80,  80,  80)
COL_SKILL_NONE_BORDER  = ( 50,  50,  50)
COL_SKILL_READY_TEXT   = (255, 255, 255)
COL_SKILL_CD_TEXT      = (180, 180, 180)
COL_SKILL_NONE_TEXT    = ( 70,  70,  70)
COL_SKILL_FILL         = ( 25,  25,  38)

# Q rune — 綠色系（回血主題）
COL_RUNE_READY_BORDER   = ( 80, 220, 130)
COL_RUNE_CD_BORDER      = ( 35,  90,  60)
COL_RUNE_PASSIVE_BORDER = ( 50, 130,  85)
COL_RUNE_READY_TEXT     = (170, 255, 205)
COL_RUNE_CD_TEXT        = ( 90, 165, 120)
COL_RUNE_PASSIVE_TEXT   = (100, 175, 135)

# 角色定義：char name → (資料夾名稱, 檔名前綴)
# folder 來自 chars.csv，不在此處維護
from game.char_data import CHAR_STATS as _CHAR_STATS
CHAR_DIR: dict = {name: (s['folder'], s['folder']) for name, s in _CHAR_STATS.items()}

# 障礙物圖片快取：(kind, w, h) → Surface（未旋轉原始縮放圖）
_sprite_cache: dict = {}
# 預旋轉障礙物快取：(kind, w, h, angle_deg_int) → Surface
_rotated_cache: dict = {}
# 角色圖片快取：(char_name, stance) → Surface（原尺寸 × PLAYER_SPRITE_SCALE）
_player_cache: dict = {}
# 靜態地圖底層（背景 + 網格），在 pygame 初始化後第一次 draw() 時建立
_map_surface: "pygame.Surface | None" = None
# Portal definitions for current map: list of {"x", "y_min", "y_max"}
_map_portals: list = []
# Portal teleport flash effect (additive tint fading over several frames)
_portal_flash_frames: int = 0
_PORTAL_FLASH_TOTAL:  int = 18
# Deathmatch zone: ember particles along the shrinking ring
_zone_embers: list = []
# skill HUD 圓形背景 Surface（固定大小，建立一次重複使用）
_skill_bg_surf: "pygame.Surface | None" = None
# skill HUD 冷卻扇形 Surface（固定大小，每幀 fill 清空後重繪，省掉 allocation）
_skill_pie_surf: "pygame.Surface | None" = None

# ── 設定選單 HUD ─────────────────────────────────────────────────────────────
_IC_COG_HUD      = chr(0xf013)   # fa-cog
_IC_SIGN_OUT_HUD = chr(0xf08b)   # fa-sign-out
_IC_VOLUME_HUD   = chr(0xf028)   # fa-volume-up

_SETTINGS_BTN = pygame.Rect(SCREEN_W - 52, 10, 42, 42)
_MENU_W       = 188
_MENU_ITEM_H  = 44
_MENU_GAP     = 5
_MENU_X       = SCREEN_W - _MENU_W - 4
_MENU_Y       = _SETTINGS_BTN.bottom + 6

_MENU_ITEMS = [
    ("sound", _IC_VOLUME_HUD,   "SOUND"),
    ("quit",  _IC_SIGN_OUT_HUD, "QUIT GAME"),
]
_MENU_RS = [
    pygame.Rect(_MENU_X, _MENU_Y + i * (_MENU_ITEM_H + _MENU_GAP), _MENU_W, _MENU_ITEM_H)
    for i in range(len(_MENU_ITEMS))
]

_settings_open: bool = False


def settings_blocks_click(mx: int, my: int) -> bool:
    """回傳 True 表示該位置屬於設定 UI，點擊應被消耗（不觸發遊戲輸入）。"""
    if _SETTINGS_BTN.collidepoint(mx, my):
        return True
    if _settings_open:
        for r in _MENU_RS:
            if r.collidepoint(mx, my):
                return True
    return False


def handle_settings_click(mx: int, my: int) -> "str | None":
    """
    MOUSEBUTTONDOWN 時由 client.py 呼叫。
    回傳 'quit' / 'toggle_sound' / None。
    """
    global _settings_open
    if _SETTINGS_BTN.collidepoint(mx, my):
        _settings_open = not _settings_open
        return None
    if _settings_open:
        for (key, _, _), r in zip(_MENU_ITEMS, _MENU_RS):
            if r.collidepoint(mx, my):
                _settings_open = False
                return "quit" if key == "quit" else "toggle_sound"
    _settings_open = False   # 點到選單外 → 收起
    return None


def _draw_settings_hud(screen: pygame.Surface, font: pygame.font.Font,
                       mx: int, my: int) -> None:
    """繪製右上角齒輪按鈕及（展開時的）下拉選單。"""
    # ── 齒輪按鈕 ──────────────────────────────────────────────────────
    hov = _SETTINGS_BTN.collidepoint(mx, my)
    active = hov or _settings_open
    bg  = (55, 65, 92) if active else (22, 28, 42)
    bd  = (105, 138, 215) if active else (48, 60, 90)
    pygame.draw.rect(screen, bg, _SETTINGS_BTN, border_radius=9)
    pygame.draw.rect(screen, bd, _SETTINGS_BTN, 2, border_radius=9)
    ic = font.render(_IC_COG_HUD, True, (195, 215, 252) if active else (95, 118, 165))
    screen.blit(ic, (_SETTINGS_BTN.centerx - ic.get_width()  // 2,
                     _SETTINGS_BTN.centery - ic.get_height() // 2))

    if not _settings_open:
        return

    # ── 下拉面板背景 ───────────────────────────────────────────────────
    panel_h = len(_MENU_ITEMS) * (_MENU_ITEM_H + _MENU_GAP) - _MENU_GAP + 14
    panel_r = pygame.Rect(_MENU_X - 4, _MENU_Y - 7, _MENU_W + 8, panel_h)
    pygame.draw.rect(screen, (18, 24, 38), panel_r, border_radius=11)
    pygame.draw.rect(screen, (55, 72, 112), panel_r, 1, border_radius=11)

    # ── 選單項目 ───────────────────────────────────────────────────────
    for (key, icon, lbl), r in zip(_MENU_ITEMS, _MENU_RS):
        hov_item = r.collidepoint(mx, my)
        if key == "quit":
            ibg = (72, 28, 28) if hov_item else (40, 18, 18)
            ibd = (210, 75, 75) if hov_item else (95, 42, 42)
            itc = (255, 158, 158) if hov_item else (185, 100, 100)
        else:
            ibg = (30, 48, 78) if hov_item else (22, 34, 54)
            ibd = (78, 120, 210) if hov_item else (42, 65, 110)
            itc = (185, 218, 255) if hov_item else (125, 162, 215)
        pygame.draw.rect(screen, ibg, r, border_radius=7)
        pygame.draw.rect(screen, ibd, r, 1, border_radius=7)
        ic_s  = font.render(icon, True, itc)
        lbl_s = font.render(lbl,  True, itc)
        PAD = 12
        screen.blit(ic_s,  (r.x + PAD,
                             r.centery - ic_s.get_height() // 2))
        screen.blit(lbl_s, (r.x + PAD + ic_s.get_width() + 8,
                             r.centery - lbl_s.get_height() // 2))


# ── 障礙物被擊中震動 ──────────────────────────────────────────────
# {oid: (expiry, duration)}  ← perf_counter 時間戳 + 本次持續秒數
_shake_timers: dict = {}
# 上一幀子彈位置 {bid: (x, y)}，用來偵測消失的子彈
_prev_bullet_pos: dict = {}


SHAKE_AMP  = 5    # 最大位移像素
SHAKE_FREQ = 40   # 振盪頻率 Hz

# ── 粒子效果 ──────────────────────────────────────────────────────────────────
# 每顆粒子：[spawn_x, spawn_y, vx, vy, spawn_t, max_life, (r,g,b), max_size]
_particles: list = []

# 上一幀已摧毀的障礙物 ID，用來偵測「本幀新摧毀」以補觸發粒子
_prev_destroyed: set = set()

# ── 地面殘骸（純視覺，永久留存）────────────────────────────────────────────
# 每筆：{'x','y','polys':[[(dx,dy),...],...],'color':(r,g,b),'outline':(r,g,b)}
_debris: list = []


def set_map_portals(portals: list) -> None:
    """Set portal definitions for the current map (called before each game)."""
    global _map_portals
    _map_portals = portals or []


def trigger_portal_flash() -> None:
    global _portal_flash_frames
    _portal_flash_frames = _PORTAL_FLASH_TOTAL


def reset_game_state() -> None:
    """每局遊戲開始前呼叫，清除跨局殘留的視覺狀態。"""
    global _map_surface, _skill_bg_surf, _skill_pie_surf
    _shake_timers.clear()
    _prev_bullet_pos.clear()
    _particles.clear()
    _prev_destroyed.clear()
    _debris.clear()
    # 強制重建地圖底層（下一幀重新繪製）
    _map_surface         = None
    _skill_bg_surf       = None
    _skill_pie_surf      = None
    _portal_flash_frames = 0
    _zone_embers.clear()


# 各障礙物種類的粒子顏色（同色系深淺變化）
PARTICLE_COLORS: dict = {
    "box_normal":       [(165, 108, 52), (195, 142, 68), (145, 88, 38),
                    (220, 168, 92), (130,  75, 30)],
    "box_special": [(255, 215,   0), (255, 180,  20), (255, 240, 80),
                    (220, 160,   0), (255, 255, 140)],
    "rock_1":      [(138, 132, 122), (112, 108, 100), (158, 152, 142),
                    ( 88,  84,  78), (175, 170, 160)],
    "rock_2":      [(118, 113, 105), (143, 138, 128), ( 93,  90,  84),
                    (168, 162, 153), (105, 100,  93)],
}


def _process_hits(state: GameState, obstacles: dict) -> None:
    """
    每幀做兩件事：
    1. 比較 destroyed_obstacles：本幀新摧毀的障礙物補觸發粒子（彌補最後一擊）
    2. 比較子彈集合：消失子彈靠近哪個障礙物 → 震動 + 粒子
    """
    now     = time.perf_counter()
    cur_ids = set(state.bullets)

    # ── 1. 新摧毀障礙物 ───────────────────────────────────────────
    newly_destroyed = state.destroyed_obstacles - _prev_destroyed
    for oid in newly_destroyed:
        if oid in obstacles:
            obs = obstacles[oid]
            if obs.kind == "box_special":
                _spawn_particles(obs.x, obs.y, obs.kind, count=55, destroy=True)
            else:
                _spawn_particles(obs.x, obs.y, obs.kind, count=30, destroy=True)
            _add_debris(obs.x, obs.y, obs.kind)
    _prev_destroyed.clear()
    _prev_destroyed.update(state.destroyed_obstacles)

    # ── 2. 消失子彈偵測 ───────────────────────────────────────────
    # newly_destroyed 的障礙物已在步驟 1 生成粒子，這裡跳過它們，
    # 避免子彈同幀摧毀障礙物時誤用旁邊 box_normal 的顏色。
    skip_oids = state.destroyed_obstacles   # 包含本幀新摧毀
    for bid, (bx, by) in _prev_bullet_pos.items():
        if bid not in cur_ids and obstacles:
            # 先看是否打中本幀才摧毀的障礙物（給它震動但不重複生成粒子）
            # 偵測半徑：子彈半徑 + 小緩衝（補償伺服器/渲染器之間的一幀延遲）
            # 不用 obs 尺寸比例，避免射程耗盡的散彈誤觸發鄰近障礙物震動
            HIT_CHECK_R = BULLET_RADIUS + 10

            hit_newly = False
            for oid in newly_destroyed:
                if oid in obstacles:
                    obs = obstacles[oid]
                    if obs.collides_circle(bx, by, HIT_CHECK_R):
                        hit_newly = True
                        break
            if hit_newly:
                continue  # 摧毀粒子已在步驟 1 生成，不再重複

            # 打中仍存活的障礙物 → 震動 + 命中粒子
            for oid, obs in obstacles.items():
                if oid in skip_oids:
                    continue
                if obs.collides_circle(bx, by, HIT_CHECK_R):
                    dur = random.uniform(0.2, 0.3)
                    _shake_timers[oid] = (now + dur, dur)
                    _spawn_particles(bx, by, obs.kind)
                    break

    _prev_bullet_pos.clear()
    for bid, b in state.bullets.items():
        if getattr(b, 'bullet_type', 0) == 0:   # 投擲物/手裡劍不參與震動偵測
            _prev_bullet_pos[bid] = (b.x, b.y)


def _shake_offset(oid: int) -> tuple:
    """回傳 (dx, dy) 震動偏移像素；振幅隨剩餘時間線性衰減。"""
    now = time.perf_counter()
    if oid not in _shake_timers:
        return 0, 0
    expiry, duration = _shake_timers[oid]
    remaining = expiry - now
    if remaining <= 0:
        del _shake_timers[oid]
        return 0, 0
    amp = SHAKE_AMP * (remaining / duration)
    t   = (duration - remaining) * SHAKE_FREQ * math.tau
    return int(amp * math.sin(t)), int(amp * math.sin(t * 1.3 + 1.0))


def _add_debris(x: float, y: float, kind: str) -> None:
    """障礙物被摧毀時在地面生成永久殘骸（純視覺）。"""
    if kind in ("box_normal", "box_special"):
        # 2~3 根木板交錯
        col  = (95, 62, 28) if kind == "box_normal" else (105, 78, 30)
        outl = (70, 45, 18) if kind == "box_normal" else (80,  58, 18)
        polys = []
        for _ in range(random.randint(2, 3)):
            ang  = random.uniform(0, math.pi)
            pw   = random.uniform(24, 40)   # 板長
            ph   = random.uniform(3,  6)    # 板寬
            ox   = random.uniform(-14, 14)
            oy   = random.uniform(-14, 14)
            ca, sa = math.cos(ang), math.sin(ang)
            hw, hh = pw / 2, ph / 2
            corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
            polys.append([(ox + dx*ca - dy*sa, oy + dx*sa + dy*ca)
                          for dx, dy in corners])
        _debris.append({'x': x, 'y': y, 'polys': polys,
                        'color': col, 'outline': outl})

    elif kind in ("rock_1", "rock_2"):
        # 3~5 顆小碎石
        col  = (88,  84,  78)
        outl = (65,  62,  58)
        polys = []
        for _ in range(random.randint(3, 5)):
            ox    = random.uniform(-28, 28)
            oy    = random.uniform(-28, 28)
            r     = random.uniform(4, 9)
            sides = random.randint(4, 6)
            base  = random.uniform(0, math.tau)
            polys.append([
                (ox + r * random.uniform(0.65, 1.0) * math.cos(base + i * math.tau / sides),
                 oy + r * random.uniform(0.65, 1.0) * math.sin(base + i * math.tau / sides))
                for i in range(sides)
            ])
        _debris.append({'x': x, 'y': y, 'polys': polys,
                        'color': col, 'outline': outl})


def _draw_debris(screen, cx, cy) -> None:
    """將地面殘骸繪製在障礙物圖層之上、粒子之下。"""
    for item in _debris:
        sx, sy = _ws(item['x'], item['y'], cx, cy)
        if -120 <= sx <= SCREEN_W + 120 and -120 <= sy <= SCREEN_H + 120:
            for poly in item['polys']:
                pts = [(int(sx + dx), int(sy + dy)) for dx, dy in poly]
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, item['color'],  pts)
                    pygame.draw.polygon(screen, item['outline'], pts, 1)


def _spawn_particles(bx: float, by: float, kind: str,
                     count: int = 12, destroy: bool = False) -> None:
    """在被擊中位置朝四周噴出同色系粒子。
    destroy=True 時使用更大的速度、尺寸與壽命（障礙物摧毀特效）。
    """
    now    = time.perf_counter()
    colors = PARTICLE_COLORS.get(kind, [(128, 128, 128)])
    if destroy and kind == "box_special":
        speed_range    = (80, 300)
        life_range     = (0.40, 0.75)
        size_range     = (10.0, 18.0)
    elif destroy:
        speed_range    = (60, 240)
        life_range     = (0.30, 0.60)
        size_range     = (6.0, 10.0)
    else:
        speed_range    = (40, 140)
        life_range     = (0.20, 0.45)
        size_range     = (2.0, 5.5)
    for _ in range(count):
        angle    = random.uniform(0, math.tau)
        speed    = random.uniform(*speed_range)
        max_life = random.uniform(*life_range)
        color    = random.choice(colors)
        max_size = random.uniform(*size_range)
        _particles.append([
            bx, by,
            math.cos(angle) * speed,
            math.sin(angle) * speed,
            now, max_life, color, max_size,
        ])


def _draw_particles(screen, cx: float, cy: float) -> None:
    """更新並繪製所有粒子，清除已過期的。"""
    now   = time.perf_counter()
    alive = []
    for p in _particles:
        bx, by, vx, vy, spawn_t, max_life, color, max_size = p
        elapsed   = now - spawn_t
        remaining = max_life - elapsed
        if remaining <= 0:
            continue
        alive.append(p)
        alpha    = remaining / max_life          # 1.0 → 0.0
        cur_size = max(1, int(max_size * alpha))
        sx, sy   = _ws(bx + vx * elapsed, by + vy * elapsed, cx, cy)
        if -10 <= sx <= SCREEN_W + 10 and -10 <= sy <= SCREEN_H + 10:
            r, g, b = color
            pygame.draw.circle(screen,
                               (int(r * alpha), int(g * alpha), int(b * alpha)),
                               (sx, sy), cur_size)
    _particles[:] = alive


def _get_player_sprite(char_name: str, stance: str) -> pygame.Surface:
    """載入並快取角色 sprite（按 PLAYER_SPRITE_SCALE 放大，保持原始比例）。"""
    key = (char_name, stance)
    if key not in _player_cache:
        folder, prefix = CHAR_DIR.get(char_name, ("agent", "agent"))
        path = os.path.join("assets", "Player", folder, f"{prefix}_{stance}.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            new_w = max(1, int(img.get_width()  * PLAYER_SPRITE_SCALE))
            new_h = max(1, int(img.get_height() * PLAYER_SPRITE_SCALE))
            _player_cache[key] = pygame.transform.scale(img, (new_w, new_h))
        except Exception:
            # 找不到圖片時用灰色圓形代替
            size = int(43 * PLAYER_SPRITE_SCALE)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, (160, 160, 160, 220), (size // 2, size // 2), size // 2)
            _player_cache[key] = surf
    return _player_cache[key]


def _get_obstacle_sprite(kind: str, w: int, h: int) -> pygame.Surface:
    key = (kind, w, h)
    if key not in _sprite_cache:
        path = os.path.join("assets", "Obstacles", f"{kind}.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            # 樹類：保持原始長寬比（以 config width 為基準，height 依比例計算）
            if kind.startswith("tree"):
                orig_w, orig_h = img.get_width(), img.get_height()
                scaled_h = max(1, int(w * orig_h / orig_w))
                _sprite_cache[key] = pygame.transform.scale(img, (w, scaled_h))
            else:
                _sprite_cache[key] = pygame.transform.scale(img, (w, h))
        except Exception:
            # 找不到圖片時用純色方塊代替
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill((139, 90, 43, 220))
            _sprite_cache[key] = surf
    return _sprite_cache[key]


def _get_rotated_obstacle_sprite(kind: str, w: int, h: int, angle_rad: float) -> pygame.Surface:
    """Return a pre-rotated obstacle sprite, cached by (kind, w, h, angle_deg_int)."""
    angle_deg = -math.degrees(angle_rad)
    rkey = (kind, w, h, int(round(angle_deg)))
    if rkey not in _rotated_cache:
        _rotated_cache[rkey] = pygame.transform.rotate(_get_obstacle_sprite(kind, w, h), angle_deg)
    return _rotated_cache[rkey]


def _camera(my_player) -> tuple:
    return SCREEN_W // 2 - my_player.x, SCREEN_H // 2 - my_player.y


# ── 主繪圖入口 ────────────────────────────────────────────────────────────────

def draw(screen: pygame.Surface, state: GameState, my_id: int,
         font: pygame.font.Font, obstacles: dict = None,
         my_stance: str = "stand", aim_angle_deg: float = 0.0,
         ammo: int = MAGAZINE_SIZE, is_reloading: bool = False,
         player_chars: dict = None,
         skill_cooldowns: dict = None,
         mx: int = 0, my: int = 0,
         font_hud: pygame.font.Font = None,
         game_mode: str = "endless",
         elapsed_ms: int = 0) -> None:
    # player_chars: {pid: char_name}，None 時全部用 Agent

    if my_id not in state.players:
        screen.fill(COL_BG)
        _draw_waiting(screen, font)
        return

    screen.fill(COL_BG)
    me = state.players[my_id]
    cx, cy = _camera(me)

    my_char = (player_chars or {}).get(my_id, "Agent")

    agent_dash_fx.detect(state, my_id, player_chars or {})
    smoke_fx.detect_smoke_sfx(state, my_id, player_chars or {})
    zombie_spit_fx.detect_spit_sfx(state, my_id, player_chars or {})
    pioneer_jump_fx.detect_jump_sfx(state, my_id, player_chars or {})
    r_dash_fx.detect_rush_sfx(state, my_id, player_chars or {})

    _draw_map(screen, cx, cy)
    if game_mode == "deathmatch":
        from game.state import MAP_WIDTH as _mw, MAP_HEIGHT as _mh
        _draw_zone(screen, cx, cy, state.tick, _mw, _mh)
    r_dash_fx.draw_r_trail(screen, cx, cy)
    airstrike_fx.draw_preview(screen, cx, cy, me.x, me.y, my_id)

    if obstacles:
        _process_hits(state, obstacles)
        _draw_obstacles(screen, obstacles, state.destroyed_obstacles, cx, cy)

    _draw_log_barriers(screen, state, cx, cy)
    _draw_debris(screen, cx, cy)
    _draw_particles(screen, cx, cy)
    _draw_gold_ingots(screen, state, cx, cy)
    _draw_bullets(screen, state, cx, cy, player_chars or {}, my_id)
    r_dash_fx.draw_afterimages(screen, cx, cy, state.tick)
    zombie_rage_fx.draw(screen, state, cx, cy)
    _draw_players(screen, state, my_id, cx, cy, font, my_stance, aim_angle_deg,
                  player_chars or {})
    blade_fx.draw(screen, state, cx, cy)

    # 樹/草叢繪製在玩家之上（最頂層），本地玩家在樹下時半透明
    if obstacles:
        _draw_trees(screen, obstacles, state.destroyed_obstacles,
                    cx, cy, me.x, me.y)

    pioneer_shield_fx.update(state)
    pioneer_shield_fx.draw(screen, state, cx, cy)
    smoke_fx.draw_patches(screen, state, cx, cy, my_id)
    flash_fx.draw_explosions(screen, cx, cy)
    grenade_fx.draw_explosions(screen, cx, cy)
    mini_grenade_fx.draw_explosions(screen, cx, cy)
    stun_bullet_fx.draw_explosions(screen, cx, cy)
    explosion_bullet_fx.draw_explosions(screen, cx, cy)
    pioneer_shield_fx.draw_shockwaves(screen, cx, cy)
    zombie_jump_fx.update(state)
    zombie_jump_fx.draw_landing_shockwaves(screen, cx, cy)
    zombie_spit_fx.draw(screen, state, cx, cy)
    vince_taunt_fx.update(state)
    vince_taunt_fx.draw_taunt_shockwaves(screen, cx, cy)
    marksman_mine_fx.update(state, my_id)
    marksman_mine_fx.draw(screen, state, cx, cy, my_id)
    marksman_mine_fx.draw_explosions(screen, cx, cy)
    marksman_turret_fx.draw(screen, state, my_id, cx, cy)
    marksman_barrage_fx.update(state)
    marksman_barrage_fx.draw(screen, state, cx, cy)
    marksman_barrage_fx.draw_explosions(screen, cx, cy)
    poison_pool_fx.update(state)
    poison_pool_fx.draw(screen, state, cx, cy)
    poisoner_e_fx.update(state)
    poisoner_e_fx.draw(screen, cx, cy)
    robot_push_fx.draw(screen, state, my_id, cx, cy)
    robot_mark_fx.draw(screen, state, my_id, cx, cy)
    robot_e_fx.draw(screen, state, my_id, cx, cy)
    air_cannon_fx.draw(screen, state, cx, cy)
    airstrike_fx.update(state)
    airstrike_fx.draw(screen, state, cx, cy)
    flash_fx.draw_screen_flash(screen, state, my_id)

    # Portal teleport flash — additive RGB tint, no extra Surface needed
    global _portal_flash_frames
    if _portal_flash_frames > 0:
        t = _portal_flash_frames / _PORTAL_FLASH_TOTAL
        screen.fill((int(70 * t), int(10 * t), int(110 * t)),
                    special_flags=pygame.BLEND_RGB_ADD)
        _portal_flash_frames -= 1

    # ── 邊框脈動：中毒綠框（非殘血時）或殘血紅框（優先級高）
    low_hp = me.max_hp > 0 and (me.hp / me.max_hp) <= 0.30
    if me.poison_stacks > 0 and not low_hp:
        _draw_poison_vignette(screen, me.poison_stacks)
    _draw_low_hp_vignette(screen, me.hp, me.max_hp)

    _draw_hud(screen, state, my_id, font, ammo, is_reloading, skill_cooldowns,
              font_hud=font_hud or font, my_char=my_char)
    _draw_mode_hud(screen, state, font_hud or font, game_mode, elapsed_ms)
    _draw_settings_hud(screen, font, mx, my)


# ── 地圖底層 ──────────────────────────────────────────────────────────────────

def _build_map_surface() -> "pygame.Surface":
    """預渲染整張地圖底層（背景色 + 網格線 + 邊框）到 MAP_WIDTH×MAP_HEIGHT Surface。
    建立一次，每幀只做一次 blit。
    """
    from game.state import MAP_WIDTH as MW, MAP_HEIGHT as MH
    surf = pygame.Surface((MW, MH))
    surf.fill(COL_MAP_BG)
    for x in range(0, MW + 1, GRID_SIZE):
        pygame.draw.line(surf, COL_GRID, (x, 0), (x, MH))
    for y in range(0, MH + 1, GRID_SIZE):
        pygame.draw.line(surf, COL_GRID, (0, y), (MW, y))
    pygame.draw.rect(surf, COL_MAP_BORDER, surf.get_rect(), 2)

    # Draw portals if this map has them
    for portal in _map_portals:
        px     = portal["x"]
        py_min = portal["y_min"]
        py_max = portal["y_max"]
        ph     = py_max - py_min
        pw     = 28   # portal visual width into the map

        # Determine rect: left portal anchors at x=0, right portal at map edge
        rect_x = 0 if px == 0 else MW - pw

        # Outer glow layers (darkest → brightest), each inset from the open (inner) side.
        # Left portal: anchored at x=0, shrinks rightward.
        # Right portal: anchored at x=MW, shrinks leftward.
        LAYERS = [
            ((60,  18,  90), 0),
            ((100,  30, 150), 3),
            ((150,  60, 220), 7),
            ((190, 100, 255), 12),
        ]
        for col, inset in LAYERS:
            if px == 0:
                r = pygame.Rect(0, py_min + inset, pw - inset, ph - inset * 2)
            else:
                r = pygame.Rect(MW - pw + inset, py_min + inset, pw - inset, ph - inset * 2)
            if r.width > 0 and r.height > 0:
                pygame.draw.rect(surf, col, r)

        # Lavender shimmer stripe down the centre of the portal slab
        cx_line = rect_x + pw // 2
        pygame.draw.line(surf, (230, 190, 255),
                         (cx_line, py_min + 6), (cx_line, py_max - 6), 2)
        # Small bright centre dot
        pygame.draw.circle(surf, (255, 230, 255),
                           (cx_line, (py_min + py_max) // 2), 4)

    return surf


def _draw_map(screen, cx, cy):
    global _map_surface
    if _map_surface is None:
        _map_surface = _build_map_surface()
    screen.blit(_map_surface, (int(cx), int(cy)))


def _draw_zone(screen: pygame.Surface, cx: float, cy: float,
               tick: int, map_w: int, map_h: int) -> None:
    """Render the deathmatch shrinking zone: danger-area tint, pulsing border, ember particles."""
    from game.state import get_zone_bounds
    bounds = get_zone_bounds(tick, map_w, map_h)
    if bounds is None:
        return
    left, top, right, bottom = bounds

    sx_l = int(left  + cx)
    sx_r = int(right + cx)
    sy_t = int(top   + cy)
    sy_b = int(bottom + cy)

    # ── Danger-area additive orange tint (4 strips outside safe zone) ───
    TINT = (40, 12, 0)
    for x, y, w, h in (
        (0,    0,    SCREEN_W,            max(0, sy_t)),
        (0,    sy_b, SCREEN_W,            max(0, SCREEN_H - sy_b)),
        (0,    sy_t, max(0, sx_l),        sy_b - sy_t),
        (sx_r, sy_t, max(0, SCREEN_W - sx_r), sy_b - sy_t),
    ):
        if w > 0 and h > 0:
            screen.fill(TINT, (x, y, w, h), special_flags=pygame.BLEND_RGB_ADD)

    # ── Pulsing orange border ────────────────────────────────────────────
    bw = max(2, int(4 + 3 * abs(math.sin(tick * 0.08))))
    zone_rect = pygame.Rect(sx_l, sy_t, sx_r - sx_l, sy_b - sy_t)
    pygame.draw.rect(screen, (210, 120, 15), zone_rect, bw)

    # ── Ember particles: spawn along border every other tick ─────────────
    if tick % 2 == 0:
        for _ in range(random.randint(1, 3)):
            side = random.randint(0, 3)
            if side == 0:
                wx, wy = random.uniform(left, right), float(top)
            elif side == 1:
                wx, wy = random.uniform(left, right), float(bottom)
            elif side == 2:
                wx, wy = float(left), random.uniform(top, bottom)
            else:
                wx, wy = float(right), random.uniform(top, bottom)
            bright = random.randint(0, 55)
            _zone_embers.append([
                wx, wy,
                random.uniform(-0.5, 0.5),
                random.uniform(-1.6, -0.5),
                random.randint(50, 90),
                0,
                200 + bright, 90 + bright,
                random.randint(2, 4),
            ])

    # ── Update and draw embers ────────────────────────────────────────────
    alive = []
    for e in _zone_embers:
        wx, wy, vx, vy, life, age, er, eg, erad = e
        age += 1
        if age >= life:
            continue
        wx += vx
        wy += vy
        e[0], e[1], e[5] = wx, wy, age
        alpha = 1.0 - age / life
        col = (int(er * alpha), int(eg * alpha), 0)
        ex, ey = int(wx + cx), int(wy + cy)
        if 0 <= ex < SCREEN_W and 0 <= ey < SCREEN_H:
            pygame.draw.circle(screen, col, (ex, ey), erad)
        alive.append(e)
    _zone_embers[:] = alive


# ── 障礙物 ────────────────────────────────────────────────────────────────────

def _draw_obstacles(screen, obstacles: dict, destroyed: set, cx, cy):
    """繪製實體障礙物（跳過 solid=False 的樹/草叢，它們在最頂層另外繪製）。"""
    for oid, obs in obstacles.items():
        if oid in destroyed:
            continue
        if not obs.solid:          # 樹/草叢留給 _draw_trees
            continue
        sx, sy = _ws(obs.x, obs.y, cx, cy)
        w, h = int(obs.width), int(obs.height)

        # 螢幕範圍外就跳過
        if sx < -w or sx > SCREEN_W + w or sy < -h or sy > SCREEN_H + h:
            continue

        rotated = _get_rotated_obstacle_sprite(obs.kind, w, h, obs.angle)
        ox, oy  = _shake_offset(oid)
        screen.blit(rotated, (sx - rotated.get_width()  // 2 + ox,
                               sy - rotated.get_height() // 2 + oy))


_LOG_OUTER_COLOR = (120, 72, 28)   # 外層：木頭色主體
_LOG_CORE_COLOR  = (70, 38, 10)    # 中心：較深的實心年輪
_LOG_CORE_SCALE  = 0.5


def _draw_log_barriers(screen, state, cx, cy) -> None:
    """粗糙結晶多邊形（技法同 Zombie RMB 的 spit_fx），純視覺，碰撞仍是 lb.radius 圓形。"""
    for lb in state.log_barriers.values():
        sx, sy = _ws(lb.x, lb.y, cx, cy)
        r = int(lb.radius)
        if sx < -r - 10 or sx > SCREEN_W + r + 10 or sy < -r - 10 or sy > SCREEN_H + r + 10:
            continue

        offsets   = _facet_offsets(lb.id)
        outer_pts = _crystal_points(r, r, r, offsets)
        core_pts  = _crystal_points(r, r, r * _LOG_CORE_SCALE, offsets)

        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.polygon(surf, _LOG_OUTER_COLOR, outer_pts)
        pygame.draw.polygon(surf, _LOG_CORE_COLOR, core_pts)
        screen.blit(surf, (sx - r, sy - r))


def _draw_trees(screen, obstacles: dict, destroyed: set,
                cx, cy, my_wx: float, my_wy: float) -> None:
    """將樹/草叢繪製在最頂層（玩家之上）。
    若本地玩家的圓心落在樹的視覺範圍內，該樹對本地玩家顯示為半透明（草叢躲藏效果）。
    對手的畫面不做任何透明處理，所以對手看不到躲在樹後的玩家。
    """
    for oid, obs in obstacles.items():
        if obs.solid:              # 只處理非實體障礙物
            continue
        if oid in destroyed:
            continue
        sx, sy = _ws(obs.x, obs.y, cx, cy)
        w, h   = int(obs.width), int(obs.height)
        if sx < -w or sx > SCREEN_W + w or sy < -h or sy > SCREEN_H + h:
            continue

        rotated = _get_rotated_obstacle_sprite(obs.kind, w, h, obs.angle)
        draw_x  = sx - rotated.get_width()  // 2
        draw_y  = sy - rotated.get_height() // 2

        # 判斷本地玩家是否在樹的視覺圓內 → 半透明顯示
        dist      = math.hypot(my_wx - obs.x, my_wy - obs.y)
        visual_r  = obs.width / 2   # 視覺半徑（完整圓形）
        if dist < visual_r + PLAYER_RADIUS:
            # 半透明：對本地玩家可見，對手看到的是完整不透明的樹
            semi = rotated.copy()
            # BLEND_RGBA_MULT 對每個像素的 alpha 乘上係數（110/255 ≈ 43% 不透明度）
            semi.fill((255, 255, 255, 110), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(semi, (draw_x, draw_y))
        else:
            screen.blit(rotated, (draw_x, draw_y))


# ── 子彈 ──────────────────────────────────────────────────────────────────────

def _draw_gold_ingots(screen, state, cx, cy) -> None:
    """在地圖上繪製散落的金錠與血包（旋轉菱形 + 光暈）。"""
    now = time.perf_counter()
    for ingot in state.gold_ingots.values():
        sx, sy = _ws(ingot.x, ingot.y, cx, cy)
        if -20 <= sx <= SCREEN_W + 20 and -20 <= sy <= SCREEN_H + 20:
            spin = now * 120 + ingot.id * 47
            a    = math.radians(spin % 360)
            r    = 10
            pts  = [(sx + r * math.cos(a + i * math.pi / 2),
                     sy + r * math.sin(a + i * math.pi / 2)) for i in range(4)]

            if ingot.kind == "health":
                col_main = (220,  80, 100)   # 紅偏粉
                col_ring = (240, 130, 145)
                col_glow = (255, 180, 190)
            else:  # "gem" 冷縮寶石：淺藍色
                col_main = ( 80, 200, 255)
                col_ring = (140, 220, 255)
                col_glow = (210, 245, 255)

            pygame.draw.polygon(screen, col_main, pts)
            pygame.draw.circle(screen, col_ring, (sx, sy), r + 3, 1)
            pygame.draw.circle(screen, col_glow, (int(sx - 2), int(sy - 2)), 3)


def _rot_pts(cx, cy, pts, angle_rad):
    """將一組相對座標點以 (cx,cy) 為原點旋轉後回傳螢幕座標。"""
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return [(cx + x * cos_a - y * sin_a,
             cy + x * sin_a + y * cos_a) for x, y in pts]


def _draw_bullet_shape(screen, char_name: str, color, sx, sy, angle_deg: float,
                       bullet_scale: float = 1.0):
    """依角色繪製不同形狀的子彈，color 為玩家顏色（藍/紅）。"""
    a = math.radians(angle_deg)   # 飛行方向（標準數學角，0=右，90=下）

    if char_name == "Marksman":         # 短矩形彈殼（10×4）
        pts = [(-5, -2), (5, -2), (5, 2), (-5, 2)]
        pygame.draw.polygon(screen, color, _rot_pts(sx, sy, pts, a))

    elif char_name == "Hunter":         # Sniper — 細長針形（24×2），前白後漸暗
        tip  = [(-12, 0), (12, -1), (12, 1)]          # 針尖三角
        body = [(-12, -1), (4, -1), (4, 1), (-12, 1)] # 針身矩形
        dim  = tuple(max(0, c - 60) for c in color)
        pygame.draw.polygon(screen, dim,   _rot_pts(sx, sy, body, a))
        pygame.draw.polygon(screen, color, _rot_pts(sx, sy, tip,  a))

    elif char_name == "Pioneer":        # 與 Machine Gun 相同的短矩形彈殼（10×4）
        pts = [(-5, -2), (5, -2), (5, 2), (-5, 2)]
        pygame.draw.polygon(screen, color, _rot_pts(sx, sy, pts, a))

    elif char_name == "Assassin":       # 旋轉手裡劍（4角星）
        spin = math.radians(time.perf_counter() * 540 % 360)  # 1.5轉/秒
        outer, inner = 8, 4
        pts = []
        for i in range(8):
            r = outer if i % 2 == 0 else inner
            ang = spin + i * math.pi / 4
            pts.append((r * math.cos(ang), r * math.sin(ang)))
        pygame.draw.polygon(screen, color, [(sx + x, sy + y) for x, y in pts])

    # Poisoner 改在 _draw_bullets 直接處理（需要 bid 與時間資訊）

    elif char_name == "Vince":          # 散彈圓點（巨人模式等比放大）
        pygame.draw.circle(screen, color, (sx, sy), max(1, int(4 * bullet_scale)))

    else:                               # Agent（Pistol）& 其他 — 標準圓形
        pygame.draw.circle(screen, color, (sx, sy), max(1, int(BULLET_RADIUS * bullet_scale)))


def _draw_bullets(screen, state, cx, cy, player_chars: dict, my_id: int = None):
    now = time.perf_counter()
    current_bids = set(state.bullets.keys())

    # 各 fx 模組清除已消失子彈的追蹤狀態
    shuriken_fx.cleanup(current_bids)
    bubble_fx.cleanup(current_bids)
    burst_bullet_fx.cleanup(current_bids)
    flash_fx.detect_disappeared(state, now)
    grenade_fx.detect_disappeared(state, now, my_id)
    mini_grenade_fx.detect_disappeared(state, now)
    stun_bullet_fx.detect_disappeared(state, now)
    explosion_bullet_fx.detect_disappeared(state, now)

    for bullet in state.bullets.values():
        sx, sy = _ws(bullet.x, bullet.y, cx, cy)
        btype  = getattr(bullet, 'bullet_type', 0)
        if -60 <= sx <= SCREEN_W + 60 and -60 <= sy <= SCREEN_H + 60:
            color    = COL_BULLET.get(bullet.owner_id, (255, 255, 200))
            char_name = player_chars.get(bullet.owner_id, "Agent")

            if btype == 9:   # Laser：黃色線狀矩形
                a = math.radians(bullet.aim_angle)
                hw, hl = 2, 10   # half-width / half-length（像素）
                pts = [(-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw)]
                rotated = [(sx + int(px * math.cos(a) - py * math.sin(a)),
                            sy + int(px * math.sin(a) + py * math.cos(a)))
                           for px, py in pts]
                pygame.draw.polygon(screen, (255, 240, 80), rotated)
            elif btype == 8:   # 毒液彈：紫色圓點
                pygame.draw.circle(screen, (150, 90, 195),  (sx, sy), 9)
                pygame.draw.circle(screen, (210, 180, 235), (sx, sy), 4)
            elif btype == 7:   # 爆炸彈：橙色圓點
                explosion_bullet_fx.track(bullet)
                pygame.draw.circle(screen, (255, 140, 20), (sx, sy), 7)
                pygame.draw.circle(screen, (255, 220, 80), (sx, sy), 3)
            elif btype == 6:   # 暈眩彈：固定黃色圓點
                stun_bullet_fx.track(bullet)
                pygame.draw.circle(screen, (255, 230, 40), (sx, sy), 6)
                pygame.draw.circle(screen, (255, 255, 160), (sx, sy), 3)
            elif btype == 5:   # 迷你手雷：玩家色小圓點
                mini_grenade_fx.track(bullet)
                pygame.draw.circle(screen, color, (sx, sy), 5)
            elif btype == 4:   # 煙霧彈：小灰綠色圓點
                pygame.draw.circle(screen, (90, 120, 70), (sx, sy), 6)
            elif btype == 3:
                shuriken_fx.draw_bullet(screen, bullet, sx, sy, color, state, cx, cy)
            elif btype == 1:
                flash_fx.draw_bullet(screen, bullet, sx, sy, color)
            elif btype == 2:
                grenade_fx.draw_bullet(screen, bullet, sx, sy, color)
            elif char_name == "Poisoner":
                bubble_fx.draw_bullet(screen, bullet, sx, sy, color, now)
            else:
                bscale = getattr(bullet, 'bullet_scale', 1.0)
                # Agent burst 子彈（scale > 1）加殘影
                if char_name == "Agent" and bscale > 1.0:
                    burst_bullet_fx.track(bullet)
                    burst_bullet_fx.draw_trail(screen, bullet, cx, cy, color)
                _draw_bullet_shape(screen, char_name, color, sx, sy, bullet.aim_angle, bscale)




# ── 玩家 ──────────────────────────────────────────────────────────────────────







def _draw_players(screen, state, my_id, cx, cy, font,
                  my_stance="stand", aim_angle_deg=0.0, player_chars=None):
    if player_chars is None:
        player_chars = {}
    for pid, player in state.players.items():
        sx, sy = _ws(player.x, player.y, cx, cy)
        cull = PLAYER_RADIUS * 6   # 旋轉後 sprite 最大半徑
        if not (-cull <= sx <= SCREEN_W + cull
                and -cull <= sy <= SCREEN_H + cull):
            continue

        # 煙霧遮蔽：對手在煙霧中且本地玩家不在同一煙霧 → 不渲染
        if pid != my_id:
            me = state.players.get(my_id)
            if me and smoke_fx.is_hidden_by_smoke(player, me, state):
                continue

        # ── 隱身（Sniper R）可見度 ───────────────────────────────────────────
        _cloak_alpha = None   # None = 正常不透明；int = 套用此 alpha
        if player.cloak_until > state.tick:
            from game.chars.hunter.cloak_state import phase_of
            _cloak_phase = phase_of(player.cloak_until, state.tick)
            if pid == my_id:
                # 自己視角：hidden = 半透明(80)，revealed = 全實體
                _cloak_alpha = None if _cloak_phase == 'revealed' else 80
            else:
                # 對手視角：hidden = 完全不可見，revealed = 半透明(110)
                if _cloak_phase == 'hidden':
                    continue
                _cloak_alpha = 110

        if pid == my_id:
            stance = my_stance
            angle  = r_dash_fx.r_skill_angle(aim_angle_deg)
            r_dash_fx.spawn_dash_dust(player.x, player.y, _particles)
            r_dash_fx.update_r_trail(player.x, player.y)
        else:
            stance = player.stance
            angle  = player.aim_angle

        char_name = player_chars.get(pid, "Agent")
        sprite    = _get_player_sprite(char_name, stance)
        rotated = pygame.transform.rotate(sprite, 90 - angle)

        # 巨人縮放
        giant_scale = 1.0
        if player.giant_tick >= 0:
            giant_age = state.tick - player.giant_tick
            if 0 <= giant_age < TOTAL_TICKS:
                giant_scale = _giant_get_scale(giant_age)
        if giant_scale != 1.0:
            new_w = max(1, int(rotated.get_width()  * giant_scale))
            new_h = max(1, int(rotated.get_height() * giant_scale))
            rotated = pygame.transform.scale(rotated, (new_w, new_h))

        # ── 跳躍：地面陰影 + 玩家放大（Soldier/Pioneer jump_tick）─────────
        if player.jump_tick >= 0:
            from game.chars.pioneer.jump_state import JUMP_TICKS as _JUMP_TICKS
            _j_age = state.tick - player.jump_tick
            _j_t   = max(0.0, min(1.0, _j_age / _JUMP_TICKS))
            # 地面陰影（原位置，半透明灰色橢圓）
            _sh_r = int(PLAYER_RADIUS * 0.9)
            _sh_surf = pygame.Surface((_sh_r * 4, _sh_r * 2), pygame.SRCALPHA)
            _sh_alpha = int(120 * math.sin(math.pi * _j_t))
            pygame.draw.ellipse(_sh_surf, (0, 0, 0, _sh_alpha),
                                _sh_surf.get_rect())
            screen.blit(_sh_surf,
                        (sx - _sh_r * 2, sy - _sh_r))
            # 跳躍時玩家放大（sin 弧線，最高 +25%）
            _j_scale = 1.0 + 0.25 * math.sin(math.pi * _j_t)
            new_w = max(1, int(rotated.get_width()  * _j_scale))
            new_h = max(1, int(rotated.get_height() * _j_scale))
            rotated = pygame.transform.scale(rotated, (new_w, new_h))

        # ── Zombie Space 跳躍：地面陰影 + 玩家放大 ───────────────────────
        if player.zombie_jump_tick >= 0:
            from game.chars.zombie.jump_state import JUMP_TICKS as _ZJ_TICKS
            _zj_age = state.tick - player.zombie_jump_tick
            _zj_t   = max(0.0, min(1.0, _zj_age / _ZJ_TICKS))
            _sh_r = int(PLAYER_RADIUS * 0.9)
            _sh_surf = pygame.Surface((_sh_r * 4, _sh_r * 2), pygame.SRCALPHA)
            _sh_alpha = int(120 * math.sin(math.pi * _zj_t))
            pygame.draw.ellipse(_sh_surf, (0, 0, 0, _sh_alpha),
                                _sh_surf.get_rect())
            screen.blit(_sh_surf, (sx - _sh_r * 2, sy - _sh_r))
            _zj_scale = 1.0 + 0.25 * math.sin(math.pi * _zj_t)
            new_w = max(1, int(rotated.get_width()  * _zj_scale))
            new_h = max(1, int(rotated.get_height() * _zj_scale))
            rotated = pygame.transform.scale(rotated, (new_w, new_h))

        # ── Soldier 分身（clone_until 有效時先畫，在本體之下）──────────────
        if player.clone_until > state.tick:
            _draw_soldier_clones(screen, player, rotated, angle, cx, cy)

        if _cloak_alpha is not None:
            _cloak_surf = rotated.copy()
            _cloak_surf.set_alpha(_cloak_alpha)
            screen.blit(_cloak_surf, (sx - rotated.get_width()  // 2,
                                      sy - rotated.get_height() // 2))
        else:
            screen.blit(rotated, (sx - rotated.get_width()  // 2,
                                   sy - rotated.get_height() // 2))

        if pid == my_id:
            r_dash_fx.maybe_spawn_afterimage(player.x, player.y, rotated, state.tick)

        # 頭頂血條（對手）——始終顯示
        head_y = sy - rotated.get_height() // 2 - 10
        if pid != my_id:
            _draw_opponent_hp_bar(screen, player.hp, player.max_hp, sx, head_y)

        # 頭頂毒素層數（中毒時才顯示，自己 + 對方）
        if player.poison_stacks > 0:
            _draw_poison_stack_label(screen, font,
                                     player.poison_stacks, sx, head_y)

        # 暈眩指示：三顆黃色小球繞頭頂旋轉
        if player.stun_until > state.tick:
            _draw_stun_indicator(screen, sx, head_y + 2)



def _draw_soldier_clones(screen, player, rotated_sprite, angle: float,
                         cx: float, cy: float) -> None:
    """在玩家左右各 30px、前方 10px 位置畫半透明分身。"""
    a_rad = math.radians(angle)   # angle 是 compass bearing（0=北/上）
    # 朝向分量（screen/world 座標，y 向下）
    ux =  math.sin(a_rad)
    uy = -math.cos(a_rad)
    rx, ry = -uy, ux              # 右方向（與 _spawn_bullet 相同）

    SIDE = 30.0
    FWD  = 10.0

    clone_surf = rotated_sprite.copy()
    clone_surf.set_alpha(90)   # 半透明

    for sign in (-1.0, 1.0):
        wx = player.x + rx * sign * SIDE + ux * FWD
        wy = player.y + ry * sign * SIDE + uy * FWD
        sx, sy = _ws(wx, wy, cx, cy)
        screen.blit(clone_surf,
                    (sx - clone_surf.get_width()  // 2,
                     sy - clone_surf.get_height() // 2))


def _draw_stun_indicator(screen, cx: int, top_y: int) -> None:
    """暈眩中：三顆黃色小球繞頭頂順時針旋轉。"""
    t = time.perf_counter()
    for i in range(3):
        angle = t * 5.0 + i * math.tau / 3
        ox = int(math.cos(angle) * 10)
        oy = int(math.sin(angle) * 5) - 6
        pygame.draw.circle(screen, (255, 230,  40), (cx + ox, top_y + oy), 4)
        pygame.draw.circle(screen, (255, 255, 180), (cx + ox, top_y + oy), 2)


def _draw_opponent_hp_bar(screen, hp: int, max_hp: int, cx: int, y: int):
    """對手頭上的血條，依真實 HP 百分比填充。"""
    bar_w = 44
    bar_h = 5
    x = cx - bar_w // 2
    ratio = max(0.0, hp / max_hp) if max_hp > 0 else 0.0
    pygame.draw.rect(screen, COL_HP_BG,   (x, y, bar_w, bar_h), border_radius=2)
    if ratio > 0:
        fill_col = (COL_HP_FILL if ratio > 0.3 else (255, 160, 40))
        pygame.draw.rect(screen, fill_col, (x, y, int(bar_w * ratio), bar_h), border_radius=2)
    pygame.draw.rect(screen, COL_HP_BORDER, (x, y, bar_w, bar_h), 1, border_radius=2)


# ── HUD ──────────────────────────────────────────────────────────────────────

_COL_BLUE_TEAM = ( 80, 160, 255)   # Agent 子彈藍
_COL_RED_TEAM  = (255,  70,  70)   # 紅方

_dm_timer_font: list = []   # lazy-loaded 48pt bold for deathmatch timer


def _draw_mode_hud(screen, state, font, game_mode: str, elapsed_ms: int) -> None:
    """頂部中央模式 HUD：Endless = 擊殺計數；Deathmatch = 菱形生命 + 計時器。"""
    CX = SCREEN_W // 2
    Y  = 14

    pids = sorted(state.players.keys())   # 通常是 [1, 2]
    if len(pids) < 2:
        return
    pid1, pid2 = pids[0], pids[1]

    # ── 共用版型常數 ─────────────────────────────────────────────────────────
    DW, DH    = 27, 36
    D_GAP     = 9
    TIMER_GAP = 24

    if not _dm_timer_font:
        import os as _os
        _dm_timer_font.append(
            pygame.font.Font(
                _os.path.join("assets", "fonts", "MapleMono-NF-Bold.ttf"), 48))
    timer_font = _dm_timer_font[0]

    total_secs = elapsed_ms // 1000
    mm = total_secs // 60
    ss = total_secs % 60
    timer_str  = f"{mm:02d}:{ss:02d}"
    timer_s    = timer_font.render(timer_str, True, (220, 220, 220))

    diamonds_w = 3 * DW + 2 * D_GAP
    total_w    = diamonds_w + TIMER_GAP + timer_s.get_width() + TIMER_GAP + diamonds_w
    hud_x      = CX - total_w // 2
    tx         = hud_x + diamonds_w + TIMER_GAP
    ty         = Y
    timer_cy   = ty + timer_s.get_height() // 2
    rx_start   = tx + timer_s.get_width() + TIMER_GAP

    # 第 2 顆菱形 (j=1) 中心 x
    blue_j1_cx = hud_x    + 1 * (DW + D_GAP) + DW // 2
    red_j1_cx  = rx_start + 1 * (DW + D_GAP) + DW // 2

    screen.blit(timer_s, (tx, ty))

    if game_mode == "endless":
        k1 = state.kill_counts.get(pid1, 0)
        k2 = state.kill_counts.get(pid2, 0)

        s1 = timer_font.render(str(k1), True, _COL_BLUE_TEAM)
        s2 = timer_font.render(str(k2), True, _COL_RED_TEAM)

        screen.blit(s1, (blue_j1_cx - s1.get_width() // 2,
                         timer_cy   - s1.get_height() // 2))
        screen.blit(s2, (red_j1_cx  - s2.get_width() // 2,
                         timer_cy   - s2.get_height() // 2))

    elif game_mode == "deathmatch":
        lives1 = state.lives.get(pid1, 3)
        lives2 = state.lives.get(pid2, 3)

        # 藍方菱形：j=0 最左（最遠），j=2 最右（最近中心），失去從中心（j=2）往外
        for j in range(3):
            filled = (j < lives1)
            dx = hud_x + j * (DW + D_GAP)
            _draw_diamond(screen, dx + DW // 2, timer_cy, DW, DH, _COL_BLUE_TEAM, filled)

        # 紅方菱形：j=0 最左（最近中心），j=2 最右（最遠），失去從中心（j=0）往外
        for j in range(3):
            filled = (j >= 3 - lives2)
            dx = rx_start + j * (DW + D_GAP)
            _draw_diamond(screen, dx + DW // 2, timer_cy, DW, DH, _COL_RED_TEAM, filled)


def _draw_diamond(screen, cx, cy, w, h, color, filled: bool) -> None:
    """在 (cx, cy) 畫一顆菱形。filled=True 實心；False 空心（只有邊框）。"""
    pts = [
        (cx,         cy - h // 2),   # 上
        (cx + w // 2, cy),            # 右
        (cx,         cy + h // 2),   # 下
        (cx - w // 2, cy),            # 左
    ]
    if filled:
        pygame.draw.polygon(screen, color, pts)
    else:
        pygame.draw.polygon(screen, color, pts, 4)


def _draw_hud(screen, state, my_id, font,
              ammo: int = MAGAZINE_SIZE, is_reloading: bool = False,
              skill_cooldowns: dict = None, font_hud=None, my_char: str = "Agent"):
    if font_hud is None:
        font_hud = font
    if my_id in state.players:
        _draw_ammo_hud(screen, font_hud, ammo, is_reloading)
    if skill_cooldowns:
        _draw_skill_hud(screen, font, skill_cooldowns)
    _draw_hp_bar(screen, state, my_id, font_hud, my_char)


def _draw_ammo_hud(screen, font, ammo: int, is_reloading: bool) -> None:
    """右下角顯示子彈數；換彈時顯示進度條。"""
    now      = pygame.time.get_ticks()
    bar_w    = HP_BAR_W
    bar_h    = HP_BAR_H
    bar_x    = SCREEN_W - bar_w - 20
    ammo_y   = SCREEN_H - HP_BAR_Y_FROM_BOTTOM

    if is_reloading:
        # 換彈進度條（從 input 模組的全域取進度）
        elapsed  = now - _inp._state.reload_start_ms
        progress = min(1.0, elapsed / max(1, _inp._state.current_reload_ms))
        pygame.draw.rect(screen, (60, 20, 20),
                         (bar_x, ammo_y, bar_w, bar_h), border_radius=4)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            pygame.draw.rect(screen, (255, 90, 90),
                             (bar_x, ammo_y, fill_w, bar_h), border_radius=4)
        pygame.draw.rect(screen, (200, 80, 80),
                         (bar_x, ammo_y, bar_w, bar_h), 2, border_radius=4)
        label = font.render("RELOADING...", True, (255, 90, 90))
    else:
        # 子彈數字
        mag   = _inp.MAGAZINE_SIZE
        ammo_display = ammo if mag < 9999 else "∞"
        mag_display  = mag  if mag < 9999 else "∞"
        col   = (255, 220, 60) if (mag >= 9999 or ammo > 10) else (255, 90, 90)
        label = font.render(f"AMMO  {ammo_display} / {mag_display}", True, col)

    screen.blit(label, (bar_x + bar_w - label.get_width(), ammo_y - 30))


def _draw_skill_hud(screen, font, skill_cooldowns: dict) -> None:
    """畫面中下方五個技能冷卻圓圈（MB / SP / E / F / Q）。
    冷卻時以從 12 點鐘順時針掃描的扇形遮罩表示剩餘冷卻時間。
    """
    R  = SKILL_CIRCLE_R   # 34
    cy = SCREEN_H - R - 22
    x0 = SCREEN_W // 2 - 2 * SKILL_STEP   # 5 格居中

    for i, (slot, label) in enumerate(zip(_SKILL_SLOTS, _SKILL_LABELS)):
        cx = x0 + i * SKILL_STEP

        remaining_ms, max_ms = skill_cooldowns.get(slot, (-1, -1))
        is_rune = (slot == 'q')
        passive = is_rune and remaining_ms == -1

        if passive:                           # Q 被動魔紋（永久效果）
            border_col = COL_RUNE_PASSIVE_BORDER
            text_col   = COL_RUNE_PASSIVE_TEXT
            text       = label
        elif remaining_ms == -1:              # 未實作
            border_col = COL_SKILL_NONE_BORDER
            text_col   = COL_SKILL_NONE_TEXT
            text       = '?'
        elif remaining_ms == 0:               # 就緒
            border_col = COL_RUNE_READY_BORDER if is_rune else COL_SKILL_READY_BORDER
            text_col   = COL_RUNE_READY_TEXT   if is_rune else COL_SKILL_READY_TEXT
            text       = label
        else:                                 # 冷卻中
            border_col = COL_RUNE_CD_BORDER if is_rune else COL_SKILL_CD_BORDER
            text_col   = COL_RUNE_CD_TEXT   if is_rune else COL_SKILL_CD_TEXT
            secs       = remaining_ms / 1000.0
            text       = f"{secs:.0f}" if secs >= 1.0 else f"{secs:.1f}"

        # ── 背景填充圓 ────────────────────────────────────────────
        pygame.draw.circle(screen, COL_SKILL_FILL, (cx, cy), R)

        # ── 冷卻扇形（從 12 點鐘出發順時針，扇形 = 剩餘時間比例）──
        if 0 < remaining_ms and max_ms > 0:
            fraction  = remaining_ms / max_ms
            sweep_deg = fraction * 360.0
            steps     = max(4, int(sweep_deg / 2) + 1)
            # 扇形多邊形：局部座標圓心 (R,R) + 從 -90° 順時針到 -90°+sweep_deg°
            pts = [(R, R)]
            for j in range(steps + 1):
                angle_rad = math.radians(-90.0 + j * sweep_deg / steps)
                pts.append((R + R * math.cos(angle_rad),
                             R + R * math.sin(angle_rad)))
            global _skill_pie_surf
            if _skill_pie_surf is None:
                _skill_pie_surf = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
            _skill_pie_surf.fill((0, 0, 0, 0))
            pygame.draw.polygon(_skill_pie_surf, (10, 10, 20, 185), pts)
            screen.blit(_skill_pie_surf, (cx - R, cy - R))

        # ── 外框圓 ────────────────────────────────────────────────
        pygame.draw.circle(screen, border_col, (cx, cy), R, 2)

        # ── 文字（居中）──────────────────────────────────────────
        txt = font.render(text, True, text_col)
        screen.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))


def _draw_rune_hud(screen, font, skill_cooldowns: dict) -> None:
    """左下角：魔紋名稱 + 冷卻條（血量上限為被動，不顯示 CD）。"""
    from game.charselect import RUNES as _RUNES

    rune_id = _inp._state.rune_id
    if rune_id < 0 or rune_id >= len(_RUNES):
        return
    rune    = _RUNES[rune_id]
    q_rem, q_max = skill_cooldowns.get('q', (-1, -1))

    bar_w  = 160
    bar_h  = 10
    bar_x  = HP_BAR_X
    hud_y  = SCREEN_H - HP_BAR_Y_FROM_BOTTOM - 48   # 在 HP 條上方

    # 魔紋名稱
    passive   = (q_max < 0)
    ready     = (not passive and q_rem == 0)
    name_col  = ((80, 220, 130) if ready
                 else (160, 190, 230) if passive
                 else (130, 145, 175))
    name_surf = font.render(rune["name"], True, name_col)
    screen.blit(name_surf, (bar_x, hud_y))

    if passive:
        # 血量上限：顯示「PASSIVE」
        ps = font.render("PASSIVE", True, (100, 140, 195))
        screen.blit(ps, (bar_x, hud_y + name_surf.get_height() + 3))
    else:
        # 冷卻進度條
        pygame.draw.rect(screen, (45, 28, 20),
                         (bar_x, hud_y + name_surf.get_height() + 4, bar_w, bar_h),
                         border_radius=4)
        if ready:
            fill_col = (80, 220, 130)
            fill_w   = bar_w
        else:
            fill_col = (70, 120, 200)
            fill_w   = int(bar_w * max(0.0, 1.0 - q_rem / max(1, q_max)))
        if fill_w > 0:
            pygame.draw.rect(screen, fill_col,
                             (bar_x, hud_y + name_surf.get_height() + 4,
                              fill_w, bar_h), border_radius=4)
        pygame.draw.rect(screen, (90, 60, 40),
                         (bar_x, hud_y + name_surf.get_height() + 4, bar_w, bar_h),
                         1, border_radius=4)
        if not ready:
            cd_secs = q_rem // 1000
            cd_s    = font.render(f"{cd_secs}s", True, (160, 180, 215))
            screen.blit(cd_s, (bar_x + bar_w + 6,
                               hud_y + name_surf.get_height() + 4 - 2))


def _draw_hp_bar(screen, state, my_id, font, my_char: str = "Agent"):
    bar_y  = SCREEN_H - HP_BAR_Y_FROM_BOTTOM
    player = state.players.get(my_id)
    hp     = player.hp     if player else 0
    max_hp = player.max_hp if player else 1

    ratio = max(0.0, hp / max_hp) if max_hp > 0 else 0.0

    # Purple bar when the local player is poisoned; red otherwise
    poisoned = player is not None and player.poison_stacks > 0
    if poisoned:
        bg_col   = (28, 12, 34)
        fill_col = (130, 70, 175) if ratio > 0.3 else (185, 90, 165)
    else:
        bg_col   = COL_HP_BG
        fill_col = COL_HP_FILL if ratio > 0.3 else (255, 140, 30)

    pygame.draw.rect(screen, bg_col,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), border_radius=4)

    fill_w = int(HP_BAR_W * ratio)
    if fill_w > 0:
        pygame.draw.rect(screen, fill_col,
                         (HP_BAR_X, bar_y, fill_w, HP_BAR_H), border_radius=4)

    pygame.draw.rect(screen, COL_HP_BORDER,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), 2, border_radius=4)

    # HP 標籤：置左 "HP"，置右 "x / max"
    lbl_left  = font.render("HP", True, COL_TEXT)
    lbl_right = font.render(f"{hp} / {max_hp}", True, COL_TEXT)
    label_y   = bar_y - 30
    screen.blit(lbl_left,  (HP_BAR_X, label_y))
    screen.blit(lbl_right, (HP_BAR_X + HP_BAR_W - lbl_right.get_width(), label_y))

    # ── 護盾條 / 能量條共用位置：疊在 HP 條「上方」，避免向右延伸擋到技能圓圈 ──
    upper_bar_y   = bar_y - HP_BAR_H - 34
    upper_label_y = upper_bar_y - 30

    # ── 護盾血條（Soldier E）─────────────────────────────────────────────
    shield = state.shields.get(my_id)
    if shield is not None and shield.broken_tick < 0:
        sh_ratio  = max(0.0, shield.hp / shield.max_hp) if shield.max_hp > 0 else 0.0
        COL_SH_BG     = (40, 40, 50)
        COL_SH_FILL   = (190, 200, 220)
        COL_SH_BORDER = (150, 160, 180)
        pygame.draw.rect(screen, COL_SH_BG,
                         (HP_BAR_X, upper_bar_y, HP_BAR_W, HP_BAR_H), border_radius=4)
        sh_fill_w = int(HP_BAR_W * sh_ratio)
        if sh_fill_w > 0:
            pygame.draw.rect(screen, COL_SH_FILL,
                             (HP_BAR_X, upper_bar_y, sh_fill_w, HP_BAR_H), border_radius=4)
        pygame.draw.rect(screen, COL_SH_BORDER,
                         (HP_BAR_X, upper_bar_y, HP_BAR_W, HP_BAR_H), 2, border_radius=4)
        # 護盾標籤：置左 "SHIELD"，置右 "x / max"
        sh_lbl_left  = font.render("SHIELD", True, COL_SH_FILL)
        sh_lbl_right = font.render(f"{shield.hp} / {shield.max_hp}", True, COL_SH_FILL)
        screen.blit(sh_lbl_left,  (HP_BAR_X, upper_label_y))
        screen.blit(sh_lbl_right, (HP_BAR_X + HP_BAR_W - sh_lbl_right.get_width(), upper_label_y))

    # ── 能量條（Zombie RMB 體力衝刺；與護盾條互斥，共用同一格）──────────────
    if my_char == 'Zombie' and player is not None:
        en_ratio     = max(0.0, min(1.0, player.zombie_energy / 300.0))
        en_displayed = int(player.zombie_energy // 5)   # 顯示用：除以 5 無條件捨去，避免每 tick 跳動看起來太快
        COL_EN_BG     = (20, 40, 25)
        COL_EN_FILL   = (70, 210, 90)
        COL_EN_BORDER = (50, 150, 65)
        pygame.draw.rect(screen, COL_EN_BG,
                         (HP_BAR_X, upper_bar_y, HP_BAR_W, HP_BAR_H), border_radius=4)
        en_fill_w = int(HP_BAR_W * en_ratio)
        if en_fill_w > 0:
            pygame.draw.rect(screen, COL_EN_FILL,
                             (HP_BAR_X, upper_bar_y, en_fill_w, HP_BAR_H), border_radius=4)
        pygame.draw.rect(screen, COL_EN_BORDER,
                         (HP_BAR_X, upper_bar_y, HP_BAR_W, HP_BAR_H), 2, border_radius=4)
        # 能量標籤：置左 "ENERGY"，置右 "x / 60"（顯示值，內部仍以 0~300 記錄）
        en_lbl_left  = font.render("ENERGY", True, COL_EN_FILL)
        en_lbl_right = font.render(f"{en_displayed} / 60", True, COL_EN_FILL)
        screen.blit(en_lbl_left,  (HP_BAR_X, upper_label_y))
        screen.blit(en_lbl_right, (HP_BAR_X + HP_BAR_W - en_lbl_right.get_width(), upper_label_y))


def _draw_waiting(screen, font):
    msg = font.render("Waiting for server...", True, COL_TEXT)
    screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2,
                      SCREEN_H // 2 - msg.get_height() // 2))


# ── 殘血紅色暈邊 ──────────────────────────────────────────────────────────────

# 快取：避免每幀重建 Surface（key = quantized intensity bucket）
_vignette_cache: dict = {}


def _build_vignette(alpha_mult: float) -> pygame.Surface:
    """建立一張 SRCALPHA 的紅色暈邊 Surface，alpha_mult ∈ [0,1]。"""
    W, H    = LOGICAL_W, LOGICAL_H
    surf    = pygame.Surface((W, H), pygame.SRCALPHA)
    steps   = 36
    max_in  = int(min(W, H) * 0.30)   # 暈邊最深延伸至畫面短邊 30%

    for i in range(steps):
        t     = i / (steps - 1)               # 0 = 最外圈, 1 = 最內圈
        alpha = int(220 * (1.0 - t) ** 1.6 * alpha_mult)
        if alpha <= 0:
            continue
        inset = int(max_in * t)
        thick = max(1, max_in // steps + 2)
        pygame.draw.rect(surf, (210, 12, 12, alpha),
                         (inset, inset, W - 2 * inset, H - 2 * inset),
                         thick)
    return surf


def _draw_low_hp_vignette(screen: pygame.Surface,
                          hp: int, max_hp: int) -> None:
    """血量 ≤ 30% 時在螢幕四邊繪製脈動紅色暈邊。"""
    if max_hp <= 0:
        return
    ratio = hp / max_hp
    if ratio > 0.30:
        _vignette_cache.clear()   # 離開殘血狀態時清快取
        return

    # 強度：30% HP → 0，0% HP → 1
    intensity = 1.0 - (ratio / 0.30)
    # 脈動：~1.6 Hz，振幅隨強度增加
    pulse     = 0.60 + 0.40 * math.sin(time.perf_counter() * math.pi * 1.6)
    alpha_mul = round(intensity * pulse, 2)

    # 以 0.04 為步進做快取分桶，減少重建次數
    bucket = round(alpha_mul / 0.04) * 0.04
    if bucket not in _vignette_cache:
        _vignette_cache[bucket] = _build_vignette(bucket)
        # 防止快取無限增長
        if len(_vignette_cache) > 50:
            _vignette_cache.pop(next(iter(_vignette_cache)))

    screen.blit(_vignette_cache[bucket], (0, 0))


# ── 毒素感染視覺 ──────────────────────────────────────────────────────────────

_poison_overlay_cache: dict = {}


_poison_stack_font: list = []   # lazy-loaded Bold 15 font


def _draw_poison_stack_label(screen: pygame.Surface,
                              font: pygame.font.Font,
                              stacks: int, sx: int, bar_y: int) -> None:
    """在對手頭頂血條上方繪製毒素層數數字（無邊框、無前綴符號）。"""
    if not _poison_stack_font:
        import os
        _poison_stack_font.append(
            pygame.font.Font(
                os.path.join("assets", "fonts", "MapleMono-NF-Bold.ttf"), 15))
    text = str(stacks)
    surf = _poison_stack_font[0].render(text, True, (160, 80, 200))
    tx   = sx - surf.get_width() // 2
    ty   = bar_y - surf.get_height() - 4
    screen.blit(surf, (tx, ty))


def _build_poison_vignette(alpha_mult: float) -> pygame.Surface:
    """建立一張 SRCALPHA 的紫色暈邊 Surface，alpha_mult ∈ [0,1]。"""
    W, H   = LOGICAL_W, LOGICAL_H
    surf   = pygame.Surface((W, H), pygame.SRCALPHA)
    steps  = 36
    max_in = int(min(W, H) * 0.30)

    for i in range(steps):
        t     = i / (steps - 1)
        alpha = int(220 * (1.0 - t) ** 1.6 * alpha_mult)
        if alpha <= 0:
            continue
        inset = int(max_in * t)
        thick = max(1, max_in // steps + 2)
        pygame.draw.rect(surf, (140, 60, 190, alpha),
                         (inset, inset, W - 2 * inset, H - 2 * inset),
                         thick)
    return surf


def _draw_poison_vignette(screen: pygame.Surface, stacks: int) -> None:
    """本地玩家中毒時的紫色邊框脈動（機制與紅色殘血相同，層數越高越明顯）。"""
    # 強度：1 層=0.2，5 層=1.0；脈動 ~1.6 Hz
    intensity = stacks / 5.0
    pulse     = 0.60 + 0.40 * math.sin(time.perf_counter() * math.pi * 1.6)
    alpha_mul = round(intensity * pulse, 2)

    bucket = round(alpha_mul / 0.04) * 0.04
    if bucket not in _poison_overlay_cache:
        _poison_overlay_cache[bucket] = _build_poison_vignette(bucket)
        if len(_poison_overlay_cache) > 50:
            _poison_overlay_cache.pop(next(iter(_poison_overlay_cache)))

    screen.blit(_poison_overlay_cache[bucket], (0, 0))
