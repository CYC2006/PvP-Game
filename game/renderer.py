import os
import math
import time
import random
import pygame
from game.state import (GameState, MAP_WIDTH, MAP_HEIGHT,
                        PLAYER_RADIUS, BULLET_RADIUS)
from game.input import MAGAZINE_SIZE, RELOAD_TIME_MS

LOGICAL_W = 1280
LOGICAL_H = 720
SCREEN_W  = LOGICAL_W
SCREEN_H  = LOGICAL_H

# colours
COL_BG         = (30,  30,  30)
COL_MAP_BG     = (45,  55,  45)
COL_GRID       = (55,  65,  55)
COL_MAP_BORDER = (80,  80,  80)
COL_TEXT       = (220, 220, 220)
COL_SELF_RIM   = (255, 255, 255)
COL_OTHER_RIM  = (200, 200, 200)
COL_PLAYERS    = {1: (100, 180, 255), 2: (255, 120, 100)}
COL_BULLET     = {1: (160, 220, 255), 2: (255, 180, 140)}
COL_HP_BG      = (60,  20,  20)
COL_HP_FILL    = (220, 60,  60)
COL_HP_BORDER  = (180, 180, 180)

GRID_SIZE            = 120
HP_BAR_X             = 20
HP_BAR_Y_FROM_BOTTOM = 50
HP_BAR_W             = 160
HP_BAR_H             = 18
HP_PIP_GAP           = 4
PLAYER_SPRITE_SCALE  = 1.5   # 原圖 33–54 × 43 px，放大後約 50–81 × 65 px

SKILL_CIRCLE_R   = 14
SKILL_CIRCLE_GAP = 6
SKILL_STEP       = SKILL_CIRCLE_R * 2 + SKILL_CIRCLE_GAP   # 34 px
_SKILL_SLOTS     = ('space', 'e', 'r', 'rmb')
_SKILL_LABELS    = ('SP', 'E', 'R', 'MB')

COL_SKILL_READY_BORDER = (220, 220, 255)
COL_SKILL_CD_BORDER    = ( 80,  80,  80)
COL_SKILL_NONE_BORDER  = ( 50,  50,  50)
COL_SKILL_READY_TEXT   = (255, 255, 255)
COL_SKILL_CD_TEXT      = (180, 180, 180)
COL_SKILL_NONE_TEXT    = ( 70,  70,  70)
COL_SKILL_FILL         = ( 25,  25,  38)

# 角色定義：char_key → (資料夾名稱, 檔名前綴)
# folder 來自 chars.csv，不在此處維護
from game.char_data import CHAR_STATS as _CHAR_STATS
CHAR_DIR: dict = {key: (s['folder'], key) for key, s in _CHAR_STATS.items()}

# 障礙物圖片快取：(kind, w, h) → Surface
_sprite_cache: dict = {}
# 角色圖片快取：(char_key, stance) → Surface（原尺寸 × PLAYER_SPRITE_SCALE）
_player_cache: dict = {}

# ── 障礙物被擊中震動 ──────────────────────────────────────────────
# {oid: (expiry, duration)}  ← perf_counter 時間戳 + 本次持續秒數
_shake_timers: dict = {}
# 上一幀子彈位置 {bid: (x, y)}，用來偵測消失的子彈
_prev_bullet_pos: dict = {}

# 毒氣泡動畫追蹤：bid → spawn_time, bid → max_radius（5~7× agent bullet）
_bubble_spawn_time: dict = {}
_bubble_max_radius: dict = {}

# 閃光彈追蹤：bid → 最後世界座標；消失時觸發爆炸特效
_flash_bullet_pos: dict = {}
# 爆炸特效佇列：[(world_x, world_y, spawn_perf_time)]
_flash_explosions: list = []
# 閃光彈旋轉角度累積：bid → 累積 radians
_flash_spin_angle: dict = {}
# 閃光彈圖片快取：owner_id → Surface
_flashbang_sprites: dict = {}
# 手榴彈追蹤
_grenade_bullet_pos: dict = {}
_grenade_spin_angle: dict = {}
_grenade_sprites:    dict = {}
# 手榴彈爆炸特效佇列：[(world_x, world_y, spawn_time, owner_id)]
_grenade_explosions: list = []
# 手裡劍（bullet_type=3）：bid → 第一次出現時的 state.tick（推算成長大小用）
_shuriken_first_tick: dict = {}
_SHURIKEN_GROW_RATE = 0.3   # px/tick，與 state.py 保持一致
# 速度提升殘影：[rotated_surface, world_x, world_y, spawn_tick]
_afterimages: list = []
_last_afterimage_tick: int = 0

# 月刀弧形（blade arc）：預計算月牙形多邊形頂點（朝右，凹側朝右）
def _build_crescent_pts():
    n = 14
    outer_r, inner_r, offset = 13, 10, 8
    pts = []
    for i in range(n + 1):
        a = math.pi / 2 - math.pi * i / n
        pts.append((outer_r * math.cos(a), outer_r * math.sin(a)))
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((offset + inner_r * math.cos(a), inner_r * math.sin(a)))
    return pts

_crescent_pts = _build_crescent_pts()

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

# HUD stance 顯示顏色
COL_STANCE = {
    "stand":   (160, 160, 160),
    "machine": (255, 200,  60),
    "hold":    ( 80, 160, 255),
    "reload":  (255,  90,  90),
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


def _get_player_sprite(char_key: str, stance: str) -> pygame.Surface:
    """載入並快取角色 sprite（按 PLAYER_SPRITE_SCALE 放大，保持原始比例）。"""
    key = (char_key, stance)
    if key not in _player_cache:
        folder, prefix = CHAR_DIR.get(char_key, ("Hitman 1", "hitman1"))
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


def _camera(my_player) -> tuple:
    return SCREEN_W // 2 - my_player.x, SCREEN_H // 2 - my_player.y


def _ws(wx, wy, cx, cy) -> tuple:
    return int(wx + cx), int(wy + cy)


# ── 主繪圖入口 ────────────────────────────────────────────────────────────────

def draw(screen: pygame.Surface, state: GameState, my_id: int,
         font: pygame.font.Font, obstacles: dict = None,
         my_stance: str = "stand", aim_angle_deg: float = 0.0,
         ammo: int = MAGAZINE_SIZE, is_reloading: bool = False,
         player_chars: dict = None,
         skill_cooldowns: dict = None) -> None:
    # player_chars: {pid: char_key}，None 時全部用 hitman1

    if my_id not in state.players:
        screen.fill(COL_BG)
        _draw_waiting(screen, font)
        return

    screen.fill(COL_BG)
    me = state.players[my_id]
    cx, cy = _camera(me)

    _draw_map(screen, cx, cy)

    if obstacles:
        _process_hits(state, obstacles)
        _draw_obstacles(screen, obstacles, state.destroyed_obstacles, cx, cy)

    _draw_debris(screen, cx, cy)
    _draw_particles(screen, cx, cy)
    _draw_gold_ingots(screen, state, cx, cy)
    _draw_bullets(screen, state, cx, cy, player_chars or {})
    _draw_boost_afterimages(screen, cx, cy, state.tick)
    _draw_players(screen, state, my_id, cx, cy, font, my_stance, aim_angle_deg,
                  player_chars or {})
    _draw_blade_arcs(screen, state, cx, cy)

    # 樹/草叢繪製在玩家之上（最頂層），本地玩家在樹下時半透明
    if obstacles:
        _draw_trees(screen, obstacles, state.destroyed_obstacles,
                    cx, cy, me.x, me.y)

    _draw_smoke_patches(screen, state, cx, cy, my_id)
    _draw_flash_explosions(screen, cx, cy)
    _draw_grenade_explosions(screen, cx, cy)
    _draw_flash_screen(screen, state, my_id)  # 白色太陽眼鏡疊加層

    _draw_hud(screen, state, my_id, font, my_stance, ammo, is_reloading, skill_cooldowns)


# ── 地圖底層 ──────────────────────────────────────────────────────────────────

def _draw_map(screen, cx, cy):
    map_rect = pygame.Rect(int(cx), int(cy), MAP_WIDTH, MAP_HEIGHT)
    pygame.draw.rect(screen, COL_MAP_BG, map_rect)

    for x in range(0, MAP_WIDTH + 1, GRID_SIZE):
        sx, _ = _ws(x, 0, cx, cy)
        if 0 <= sx <= SCREEN_W:
            pygame.draw.line(screen, COL_GRID,
                             (sx, max(0, int(cy))),
                             (sx, min(SCREEN_H, int(cy + MAP_HEIGHT))))

    for y in range(0, MAP_HEIGHT + 1, GRID_SIZE):
        _, sy = _ws(0, y, cx, cy)
        if 0 <= sy <= SCREEN_H:
            pygame.draw.line(screen, COL_GRID,
                             (max(0, int(cx)), sy),
                             (min(SCREEN_W, int(cx + MAP_WIDTH)), sy))

    pygame.draw.rect(screen, COL_MAP_BORDER, map_rect, 2)


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

        sprite  = _get_obstacle_sprite(obs.kind, w, h)
        rotated = pygame.transform.rotate(sprite, -math.degrees(obs.angle))
        ox, oy  = _shake_offset(oid)
        screen.blit(rotated, (sx - rotated.get_width()  // 2 + ox,
                               sy - rotated.get_height() // 2 + oy))


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

        sprite  = _get_obstacle_sprite(obs.kind, w, h)
        rotated = pygame.transform.rotate(sprite, -math.degrees(obs.angle))
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
            r    = 20 if ingot.kind == "health" else 10
            pts  = [(sx + r * math.cos(a + i * math.pi / 2),
                     sy + r * math.sin(a + i * math.pi / 2)) for i in range(4)]

            if ingot.kind == "health":
                col_main = (220,  80, 100)   # 紅偏粉
                col_ring = (240, 130, 145)
                col_glow = (255, 180, 190)
            else:
                col_main = (255, 215,   0)   # 金色
                col_ring = (255, 230,  80)
                col_glow = (255, 255, 180)

            pygame.draw.polygon(screen, col_main, pts)
            pygame.draw.circle(screen, col_ring, (sx, sy), r + 3, 1)
            pygame.draw.circle(screen, col_glow, (int(sx - 2), int(sy - 2)), 3)


def _rot_pts(cx, cy, pts, angle_rad):
    """將一組相對座標點以 (cx,cy) 為原點旋轉後回傳螢幕座標。"""
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return [(cx + x * cos_a - y * sin_a,
             cy + x * sin_a + y * cos_a) for x, y in pts]


def _draw_bullet_shape(screen, char_key: str, color, sx, sy, angle_deg: float):
    """依角色繪製不同形狀的子彈，color 為玩家顏色（藍/紅）。"""
    a = math.radians(angle_deg)   # 飛行方向（標準數學角，0=右，90=下）

    if char_key == "manBrown":          # Bear — 短矩形彈殼（10×4）
        pts = [(-5, -2), (5, -2), (5, 2), (-5, 2)]
        pygame.draw.polygon(screen, color, _rot_pts(sx, sy, pts, a))

    elif char_key == "manOld":          # Sniper — 細長針形（24×2），前白後漸暗
        tip  = [(-12, 0), (12, -1), (12, 1)]          # 針尖三角
        body = [(-12, -1), (4, -1), (4, 1), (-12, 1)] # 針身矩形
        dim  = tuple(max(0, c - 60) for c in color)
        pygame.draw.polygon(screen, dim,   _rot_pts(sx, sy, body, a))
        pygame.draw.polygon(screen, color, _rot_pts(sx, sy, tip,  a))

    elif char_key == "soldier1":        # Soldier — 與 Machine Gun 相同的短矩形彈殼（10×4）
        pts = [(-5, -2), (5, -2), (5, 2), (-5, 2)]
        pygame.draw.polygon(screen, color, _rot_pts(sx, sy, pts, a))

    elif char_key == "survivor1":       # Assassin — 旋轉手裡劍（4角星）
        spin = math.radians(time.perf_counter() * 540 % 360)  # 1.5轉/秒
        outer, inner = 8, 4
        pts = []
        for i in range(8):
            r = outer if i % 2 == 0 else inner
            ang = spin + i * math.pi / 4
            pts.append((r * math.cos(ang), r * math.sin(ang)))
        pygame.draw.polygon(screen, color, [(sx + x, sy + y) for x, y in pts])

    # womanGreen 改在 _draw_bullets 直接處理（需要 bid 與時間資訊）

    elif char_key == "manBlue":          # Rambo — 散彈圓點
        pygame.draw.circle(screen, color, (sx, sy), 4)

    else:                               # Agent（Pistol）& 其他 — 標準圓形
        pygame.draw.circle(screen, color, (sx, sy), BULLET_RADIUS)


_BUBBLE_INIT_R  = BULLET_RADIUS * 2        # 初始半徑：2× agent 子彈（10px）
_BUBBLE_LIFE    = 2.0                       # 氣泡總壽命（秒）：1s 飛行 + 1s 停留


def _draw_bullets(screen, state, cx, cy, player_chars: dict):
    now = time.perf_counter()
    current_bids = set(state.bullets.keys())

    # 清除已消失子彈的動畫快取
    for bid in list(_bubble_spawn_time.keys()):
        if bid not in current_bids:
            _bubble_spawn_time.pop(bid, None)
            _bubble_max_radius.pop(bid, None)
    for bid in list(_shuriken_first_tick.keys()):
        if bid not in current_bids:
            _shuriken_first_tick.pop(bid, None)

    # ── 閃光彈消失偵測 → 觸發爆炸特效 ───────────────────────────
    current_flash = {bid for bid, b in state.bullets.items()
                     if getattr(b, 'bullet_type', 0) == 1}
    for bid in set(_flash_bullet_pos) - current_flash:
        if bid in _flash_bullet_pos:
            _flash_explosions.append((*_flash_bullet_pos[bid], now))
        _flash_bullet_pos.pop(bid, None)
        _flash_spin_angle.pop(bid, None)

    # ── 手榴彈消失偵測 → 觸發爆炸特效 ───────────────────────────
    current_grenade = {bid for bid, b in state.bullets.items()
                       if getattr(b, 'bullet_type', 0) == 2}
    for bid in set(_grenade_bullet_pos) - current_grenade:
        if bid in _grenade_bullet_pos:
            bx, by, bowner = _grenade_bullet_pos[bid]
            _grenade_explosions.append((bx, by, now, bowner))
        _grenade_bullet_pos.pop(bid, None)
        _grenade_spin_angle.pop(bid, None)

    for bullet in state.bullets.values():
        sx, sy = _ws(bullet.x, bullet.y, cx, cy)
        btype  = getattr(bullet, 'bullet_type', 0)
        if -60 <= sx <= SCREEN_W + 60 and -60 <= sy <= SCREEN_H + 60:
            color    = COL_BULLET.get(bullet.owner_id, (255, 255, 200))
            char_key = player_chars.get(bullet.owner_id, "hitman1")

            # ── 煙霧彈：小灰綠色圓點 ──────────────────────────────
            if btype == 4:
                pygame.draw.circle(screen, (90, 120, 70), (sx, sy), 6)
                continue

            # ── 手裡劍（RMB）：等速旋轉，隨時間成長 ─────────────
            if btype == 3:
                if bullet.id not in _shuriken_first_tick:
                    _shuriken_first_tick[bullet.id] = state.tick
                age  = state.tick - _shuriken_first_tick[bullet.id]
                grow = age * _SHURIKEN_GROW_RATE
                r_outer = max(BULLET_RADIUS, BULLET_RADIUS + grow)
                r_inner = r_outer * 0.45
                spin = time.perf_counter() * 6.0   # 約 1 轉/秒（rad/s）
                pts = []
                for i in range(8):
                    r = r_outer if i % 2 == 0 else r_inner
                    ang = spin + i * math.pi / 4
                    pts.append((sx + r * math.cos(ang), sy + r * math.sin(ang)))
                # 發光外圈
                glow_r = int(r_outer + 3)
                glow_surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*color, 60),
                                   (glow_r + 1, glow_r + 1), glow_r)
                screen.blit(glow_surf, (sx - glow_r - 1, sy - glow_r - 1))
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, color, pts)
                continue

            # ── 閃光彈：等減速旋轉圖片 ───────────────────────────
            if btype == 1:
                prev_pos = _flash_bullet_pos.get(bullet.id)
                speed = (math.hypot(bullet.x - prev_pos[0], bullet.y - prev_pos[1])
                         if prev_pos else 0.0)
                _flash_bullet_pos[bullet.id] = (bullet.x, bullet.y)
                prev  = _flash_spin_angle.get(bullet.id, 0.0)
                angle = prev + speed * 0.06
                _flash_spin_angle[bullet.id] = angle
                owner = bullet.owner_id
                if owner not in _flashbang_sprites:
                    path = os.path.join("assets", "objects", f"flashbang_P{owner}.png")
                    try:
                        img = pygame.image.load(path).convert_alpha()
                        img = pygame.transform.smoothscale(img, (48, 36))
                    except Exception:
                        img = None
                    _flashbang_sprites[owner] = img
                sprite = _flashbang_sprites.get(owner)
                if sprite:
                    rotated = pygame.transform.rotate(sprite, -math.degrees(angle))
                    screen.blit(rotated, (sx - rotated.get_width()  // 2,
                                         sy - rotated.get_height() // 2))
                else:
                    pygame.draw.circle(screen, color, (sx, sy), 7)
                continue

            # ── 手榴彈：等減速旋轉圖片 ───────────────────────────
            if btype == 2:
                prev_pos = _grenade_bullet_pos.get(bullet.id)
                speed = (math.hypot(bullet.x - prev_pos[0], bullet.y - prev_pos[1])
                         if prev_pos else 0.0)
                _grenade_bullet_pos[bullet.id] = (bullet.x, bullet.y, bullet.owner_id)
                prev  = _grenade_spin_angle.get(bullet.id, 0.0)
                angle = prev + speed * 0.06
                _grenade_spin_angle[bullet.id] = angle
                owner = bullet.owner_id
                if owner not in _grenade_sprites:
                    path = os.path.join("assets", "objects", f"grenade_P{owner}.png")
                    try:
                        img = pygame.image.load(path).convert_alpha()
                        img = pygame.transform.smoothscale(img, (48, 48))
                    except Exception:
                        img = None
                    _grenade_sprites[owner] = img
                sprite = _grenade_sprites.get(owner)
                if sprite:
                    rotated = pygame.transform.rotate(sprite, -math.degrees(angle))
                    screen.blit(rotated, (sx - rotated.get_width()  // 2,
                                         sy - rotated.get_height() // 2))
                else:
                    pygame.draw.circle(screen, color, (sx, sy), 8)
                continue

            if char_key == "womanGreen":
                if bullet.id not in _bubble_spawn_time:
                    _bubble_spawn_time[bullet.id] = now
                    rmax = getattr(bullet, "bubble_radius_max", 0.0)
                    _bubble_max_radius[bullet.id] = (
                        rmax if rmax > 0 else BULLET_RADIUS * 6)
                age = now - _bubble_spawn_time[bullet.id]
                t   = min(1.0, age / _BUBBLE_LIFE)
                r   = max(1, int(_BUBBLE_INIT_R + (_bubble_max_radius[bullet.id]
                                                    - _BUBBLE_INIT_R) * t))
                surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*color, 120), (r, r), r)
                screen.blit(surf, (sx - r, sy - r))
            else:
                _draw_bullet_shape(screen, char_key, color, sx, sy, bullet.aim_angle)


def _draw_blade_arcs(screen, state, cx: float, cy: float) -> None:
    """繪製 Assassin R 技能的月牙形刀片（隨公轉旋轉，玩家所屬顏色）。"""
    now = time.perf_counter()
    for blade in state.blade_arcs.values():
        owner = state.players.get(blade.owner_id)
        sx, sy = _ws(blade.x, blade.y, cx, cy)
        if sx < -40 or sx > SCREEN_W + 40 or sy < -40 or sy > SCREEN_H + 40:
            continue
        color = COL_BULLET.get(blade.owner_id, (255, 255, 200))

        # 公轉角（刀片位置相對玩家的方向角）
        orbit_angle = (math.atan2(blade.y - owner.y, blade.x - owner.x)
                       if owner else 0.0)
        # 行進切線方向 + 時間自轉
        travel_dir = orbit_angle + blade.direction * math.pi / 2
        spin = travel_dir + now * 4.0

        # 淡入前 5 tick、淡出後 5 tick
        age   = blade.age
        alpha = min(1.0, min(age / 5.0, (30 - age) / 5.0))
        if alpha <= 0:
            continue

        # 旋轉月牙形頂點
        cos_s, sin_s = math.cos(spin), math.sin(spin)
        pts = [(sx + x * cos_s - y * sin_s, sy + x * sin_s + y * cos_s)
               for x, y in _crescent_pts]

        r, g, b = color
        draw_col = (int(r * alpha), int(g * alpha), int(b * alpha))
        pygame.draw.polygon(screen, draw_col, pts)


# ── 玩家 ──────────────────────────────────────────────────────────────────────

_SMOKE_FULL  = 360   # 6s × 60 fps（與 state._SMOKE_DURATION 一致）
_SMOKE_FADE  = 60    # 1s fade


def _is_hidden_by_smoke(opponent, local_player, state) -> bool:
    """對手在煙霧中且本地玩家不在同一煙霧區域時回傳 True（對手不可見）。"""
    for patch in state.smoke_patches.values():
        if state.tick - patch.spawn_tick >= _SMOKE_FULL:
            continue   # 淡出期間不再遮蔽視線，只剩薄紗視覺
        if math.hypot(opponent.x - patch.x, opponent.y - patch.y) > patch.radius:
            continue
        # 對手在煙霧內：再看本地玩家是否也在同一個煙霧
        if math.hypot(local_player.x - patch.x, local_player.y - patch.y) <= patch.radius:
            continue   # 雙方都在 → 可見
        return True
    return False


def _draw_smoke_patches(screen, state, cx: float, cy: float, my_id: int) -> None:
    """繪製煙霧區域（對本地玩家呈半透明；對外部玩家呈不透明遮蔽）。"""
    me = state.players.get(my_id)
    for patch in state.smoke_patches.values():
        age = state.tick - patch.spawn_tick
        if age >= _SMOKE_FULL + _SMOKE_FADE:
            continue
        # alpha：全期 220，最後 1 秒線性淡出
        if age < _SMOKE_FULL:
            base_alpha = 220
        else:
            base_alpha = int(220 * (1.0 - (age - _SMOKE_FULL) / _SMOKE_FADE))
        if base_alpha <= 0:
            continue
        # 本地玩家在煙霧內 → 半透明（仍可見場景）
        my_inside = (me and
                     math.hypot(me.x - patch.x, me.y - patch.y) <= patch.radius)
        alpha = 70 if my_inside else base_alpha
        r  = int(patch.radius)
        sx, sy = _ws(patch.x, patch.y, cx, cy)
        if sx < -r or sx > SCREEN_W + r or sy < -r or sy > SCREEN_H + r:
            continue
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 255, alpha), (r + 1, r + 1), r)
        screen.blit(surf, (sx - r - 1, sy - r - 1))


def _draw_flash_explosions(screen, cx: float, cy: float) -> None:
    """繪製閃光彈爆炸擴散白圈（投擲者螢幕可見）。"""
    now   = time.perf_counter()
    alive = []
    DURATION = 0.5
    MAX_R    = 130
    for wx, wy, t in _flash_explosions:
        elapsed = now - t
        if elapsed >= DURATION:
            continue
        alive.append((wx, wy, t))
        progress = elapsed / DURATION
        r     = max(1, int(MAX_R * progress))
        alpha = int(230 * (1.0 - progress))
        sx, sy = _ws(wx, wy, cx, cy)
        if -MAX_R <= sx <= SCREEN_W + MAX_R and -MAX_R <= sy <= SCREEN_H + MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 220, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _flash_explosions[:] = alive


def _draw_grenade_explosions(screen, cx: float, cy: float) -> None:
    """繪製手榴彈爆炸擴散圈（投擲者所屬顏色）。"""
    now      = time.perf_counter()
    alive    = []
    DURATION = 0.5
    MAX_R    = 130
    for wx, wy, t, owner in _grenade_explosions:
        elapsed = now - t
        if elapsed >= DURATION:
            continue
        alive.append((wx, wy, t, owner))
        progress = elapsed / DURATION
        r     = max(1, int(MAX_R * progress))
        alpha = int(200 * (1.0 - progress))
        col   = COL_BULLET.get(owner, (255, 200, 100))
        sx, sy = _ws(wx, wy, cx, cy)
        if -MAX_R <= sx <= SCREEN_W + MAX_R and -MAX_R <= sy <= SCREEN_H + MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _grenade_explosions[:] = alive


def _draw_flash_screen(screen, state, my_id: int) -> None:
    """被閃光彈命中時全螢幕白色太陽眼鏡疊加層（HUD 在其上方）。"""
    if my_id not in state.players:
        return
    ft = getattr(state.players[my_id], 'flash_ticks', 0)
    if ft <= 0:
        return
    alpha = 255 if ft > 120 else int(255 * ft / 120)  # >120: 全白; 1~120: 2秒漸退
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, alpha))
    screen.blit(overlay, (0, 0))


def _maybe_spawn_afterimage(px: float, py: float,
                             rotated_surf: pygame.Surface,
                             state_tick: int) -> None:
    """每 6 ticks 在本地玩家位置留下一個殘影。"""
    global _last_afterimage_tick
    import game.input as _inp
    if pygame.time.get_ticks() >= _inp._speed_boost_end_ms:
        return
    if state_tick - _last_afterimage_tick < 6:
        return
    _last_afterimage_tick = state_tick
    _afterimages.append([rotated_surf.copy(), px, py, state_tick])


def _draw_boost_afterimages(screen, cx: float, cy: float, state_tick: int) -> None:
    """繪製速度提升殘影（18 tick 內線性淡出），須在玩家之前呼叫使其出現在底層。"""
    alive = []
    for img, wx, wy, spawn_tick in _afterimages:
        age = state_tick - spawn_tick
        if age >= 24:
            continue
        alive.append([img, wx, wy, spawn_tick])
        alpha = int(170 * (1.0 - age / 24))
        tmp = img.copy()
        tmp.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        sx, sy = _ws(wx, wy, cx, cy)
        screen.blit(tmp, (sx - img.get_width() // 2, sy - img.get_height() // 2))
    _afterimages[:] = alive


def _spawn_dash_dust(px: float, py: float) -> None:
    """衝刺時在玩家後方噴出灰塵粒子（每幀 3 顆）。"""
    import game.input as _inp
    if not _inp._dash_active:
        return
    now  = time.perf_counter()
    ddx, ddy = _inp._dash_dx, _inp._dash_dy
    base = math.atan2(-ddy, -ddx)          # 衝刺反方向
    dust_cols = [(190, 180, 165), (168, 160, 148), (210, 202, 188)]
    for _ in range(3):
        angle = base + random.uniform(-0.65, 0.65)
        speed = random.uniform(25, 70)
        _particles.append([
            px + random.uniform(-7, 7),
            py + random.uniform(-7, 7),
            math.cos(angle) * speed,
            math.sin(angle) * speed,
            now,
            random.uniform(0.12, 0.28),
            random.choice(dust_cols),
            random.uniform(2.0, 4.5),
        ])


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
            if me and _is_hidden_by_smoke(player, me, state):
                continue

        if pid == my_id:
            stance = my_stance
            angle  = aim_angle_deg
            _spawn_dash_dust(player.x, player.y)
        else:
            stance = player.stance
            angle  = player.aim_angle

        char_key = player_chars.get(pid, "hitman1")
        sprite   = _get_player_sprite(char_key, stance)
        rotated = pygame.transform.rotate(sprite, 90 - angle)
        screen.blit(rotated, (sx - rotated.get_width()  // 2,
                               sy - rotated.get_height() // 2))

        if pid == my_id:
            _maybe_spawn_afterimage(player.x, player.y, rotated, state.tick)

        # 對方頭上顯示 HP bar（依真實血量百分比）
        if pid != my_id:
            head_y = sy - rotated.get_height() // 2 - 10
            _draw_opponent_hp_bar(screen, player.hp, player.max_hp, sx, head_y)



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

def _draw_hud(screen, state, my_id, font, my_stance="stand",
              ammo: int = MAGAZINE_SIZE, is_reloading: bool = False,
              skill_cooldowns: dict = None):
    if my_id in state.players:
        me = state.players[my_id]
        screen.blit(font.render(f"Tick {state.tick}", True, COL_TEXT), (8, 8))
        screen.blit(font.render(f"P{my_id}  ({int(me.x)}, {int(me.y)})", True, COL_TEXT), (8, 26))
        stance_col = COL_STANCE.get(my_stance, COL_TEXT)
        screen.blit(font.render(f"[E] {my_stance.upper()}", True, stance_col), (8, 44))
        _draw_ammo_hud(screen, font, ammo, is_reloading)
        gold = state.gold_counts.get(my_id, 0)
        gold_surf = font.render(f"◆ {gold}", True, (255, 215, 0))
        screen.blit(gold_surf, (8, 62))
    if skill_cooldowns:
        _draw_skill_hud(screen, font, skill_cooldowns)
    _draw_hp_bar(screen, state, my_id, font)


def _draw_ammo_hud(screen, font, ammo: int, is_reloading: bool) -> None:
    """右下角顯示子彈數；換彈時顯示進度條。"""
    now      = pygame.time.get_ticks()
    bar_w    = 160
    bar_h    = 14
    bar_x    = SCREEN_W - bar_w - 20
    ammo_y   = SCREEN_H - 80

    if is_reloading:
        # 換彈進度條（從 input 模組的全域取進度）
        import game.input as _inp
        elapsed  = now - _inp._reload_start_ms
        progress = min(1.0, elapsed / _inp.RELOAD_TIME_MS)
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
        import game.input as _inp
        mag   = _inp.MAGAZINE_SIZE
        ammo_display = ammo if mag < 9999 else "∞"
        mag_display  = mag  if mag < 9999 else "∞"
        col   = (255, 220, 60) if (mag >= 9999 or ammo > 10) else (255, 90, 90)
        label = font.render(f"AMMO  {ammo_display} / {mag_display}", True, col)

    screen.blit(label, (bar_x + bar_w - label.get_width(), ammo_y - 18))


def _draw_skill_hud(screen, font, skill_cooldowns: dict) -> None:
    """血條上方四個技能冷卻圓圈。"""
    bar_y = SCREEN_H - HP_BAR_Y_FROM_BOTTOM
    # 圓圈中心 y：血條頂端往上 18px（HP label）再往上 5px + 圓半徑
    cy = bar_y - 18 - 5 - SKILL_CIRCLE_R   # ≈ 633

    for i, (slot, label) in enumerate(zip(_SKILL_SLOTS, _SKILL_LABELS)):
        cx = HP_BAR_X + SKILL_CIRCLE_R + i * SKILL_STEP

        remaining_ms, max_ms = skill_cooldowns.get(slot, (-1, -1))

        if remaining_ms == -1:                # 未實作
            border_col = COL_SKILL_NONE_BORDER
            text_col   = COL_SKILL_NONE_TEXT
            text       = '?'
        elif remaining_ms == 0:               # 就緒
            border_col = COL_SKILL_READY_BORDER
            text_col   = COL_SKILL_READY_TEXT
            text       = label
        else:                                 # 冷卻中
            border_col = COL_SKILL_CD_BORDER
            text_col   = COL_SKILL_CD_TEXT
            secs       = remaining_ms / 1000.0
            text       = f"{secs:.0f}" if secs >= 1.0 else f"{secs:.1f}"

        # ── 背景填充 ──────────────────────────────────────────────
        surf = pygame.Surface((SKILL_CIRCLE_R * 2, SKILL_CIRCLE_R * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*COL_SKILL_FILL, 200),
                           (SKILL_CIRCLE_R, SKILL_CIRCLE_R), SKILL_CIRCLE_R)
        screen.blit(surf, (cx - SKILL_CIRCLE_R, cy - SKILL_CIRCLE_R))

        # ── 冷卻覆蓋（暗色扇形）────────────────────────────────────
        if 0 < remaining_ms and max_ms > 0:
            fraction = remaining_ms / max_ms
            steps    = max(4, int(fraction * 32))
            start_a  = -math.pi / 2              # 12 點鐘方向
            sweep    = math.tau * fraction        # 順時針覆蓋
            pts      = [(cx, cy)]
            for j in range(steps + 1):
                a = start_a + sweep * j / steps
                pts.append((cx + SKILL_CIRCLE_R * math.cos(a),
                             cy + SKILL_CIRCLE_R * math.sin(a)))
            pie = pygame.Surface((SKILL_CIRCLE_R * 2 + 2, SKILL_CIRCLE_R * 2 + 2),
                                  pygame.SRCALPHA)
            lpts = [(x - cx + SKILL_CIRCLE_R + 1, y - cy + SKILL_CIRCLE_R + 1)
                    for x, y in pts]
            pygame.draw.polygon(pie, (10, 10, 20, 180), lpts)
            screen.blit(pie, (cx - SKILL_CIRCLE_R - 1, cy - SKILL_CIRCLE_R - 1))

        # ── 外框 ──────────────────────────────────────────────────
        pygame.draw.circle(screen, border_col, (cx, cy), SKILL_CIRCLE_R, 2)

        # ── 文字（居中）──────────────────────────────────────────────
        txt = font.render(text, True, text_col)
        screen.blit(txt, (cx - txt.get_width() // 2, cy - txt.get_height() // 2))


def _draw_hp_bar(screen, state, my_id, font):
    bar_y  = SCREEN_H - HP_BAR_Y_FROM_BOTTOM
    player = state.players.get(my_id)
    hp     = player.hp     if player else 0
    max_hp = player.max_hp if player else 1

    ratio = max(0.0, hp / max_hp) if max_hp > 0 else 0.0

    pygame.draw.rect(screen, COL_HP_BG,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), border_radius=4)

    fill_w = int(HP_BAR_W * ratio)
    if fill_w > 0:
        fill_col = COL_HP_FILL if ratio > 0.3 else (255, 140, 30)
        pygame.draw.rect(screen, fill_col,
                         (HP_BAR_X, bar_y, fill_w, HP_BAR_H), border_radius=4)

    pygame.draw.rect(screen, COL_HP_BORDER,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), 2, border_radius=4)

    label = font.render(f"HP  {hp} / {max_hp}", True, COL_TEXT)
    screen.blit(label, (HP_BAR_X, bar_y - 18))


def _draw_waiting(screen, font):
    msg = font.render("Waiting for server...", True, COL_TEXT)
    screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2,
                      SCREEN_H // 2 - msg.get_height() // 2))
