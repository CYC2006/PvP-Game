import os
import math
import time
import random
import pygame
from game.state import GameState, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS, BULLET_RADIUS
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
         player_chars: dict = None) -> None:
    # player_chars: {pid: char_key}，None 時全部用 hitman1
    screen.fill(COL_BG)

    if my_id not in state.players:
        _draw_waiting(screen, font)
        return

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
    _draw_players(screen, state, my_id, cx, cy, font, my_stance, aim_angle_deg,
                  player_chars or {})

    # 樹/草叢繪製在玩家之上（最頂層），本地玩家在樹下時半透明
    if obstacles:
        _draw_trees(screen, obstacles, state.destroyed_obstacles,
                    cx, cy, me.x, me.y)

    _draw_hud(screen, state, my_id, font, my_stance, ammo, is_reloading)


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

    for bullet in state.bullets.values():
        sx, sy = _ws(bullet.x, bullet.y, cx, cy)
        if -60 <= sx <= SCREEN_W + 60 and -60 <= sy <= SCREEN_H + 60:
            color    = COL_BULLET.get(bullet.owner_id, (255, 255, 200))
            char_key = player_chars.get(bullet.owner_id, "hitman1")

            if char_key == "womanGreen":
                # 首次出現：記錄 spawn time；最終半徑由 server 設定，保持雙端一致
                if bullet.id not in _bubble_spawn_time:
                    _bubble_spawn_time[bullet.id] = now
                    # 優先使用 server 傳來的 bubble_radius_max，否則取預設值
                    rmax = getattr(bullet, "bubble_radius_max", 0.0)
                    _bubble_max_radius[bullet.id] = (
                        rmax if rmax > 0 else BULLET_RADIUS * 6)
                age = now - _bubble_spawn_time[bullet.id]
                t   = min(1.0, age / _BUBBLE_LIFE)              # 0→1 over 2s
                r   = max(1, int(_BUBBLE_INIT_R + (_bubble_max_radius[bullet.id]
                                                    - _BUBBLE_INIT_R) * t))
                surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*color, 120), (r, r), r)
                screen.blit(surf, (sx - r, sy - r))
            else:
                _draw_bullet_shape(screen, char_key, color, sx, sy, bullet.aim_angle)


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

        if pid == my_id:
            stance = my_stance
            angle  = aim_angle_deg
        else:
            stance = player.stance       # 從 server 同步的 stance
            angle  = player.aim_angle    # 從 server 同步的瞄準角度

        char_key = player_chars.get(pid, "hitman1")
        sprite   = _get_player_sprite(char_key, stance)
        # sprite 預設朝右（+x 方向），pygame rotate 逆時針為正
        # 90 - angle 讓 angle=0（瞄準正上方）時轉 +90°（逆時針），sprite 正確朝上
        rotated = pygame.transform.rotate(sprite, 90 - angle)
        screen.blit(rotated, (sx - rotated.get_width()  // 2,
                               sy - rotated.get_height() // 2))

        # 對方頭上顯示 HP bar（依真實血量百分比）
        if pid != my_id:
            head_y = sy - rotated.get_height() // 2 - 10
            _draw_opponent_hp_bar(screen, player.hp, player.max_hp, sx, head_y)

        # 玩家名稱標籤
        label_y = sy - rotated.get_height() // 2 - 20
        label = font.render(f"P{pid}", True, COL_TEXT)
        screen.blit(label, (sx - label.get_width() // 2, label_y))


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
              ammo: int = MAGAZINE_SIZE, is_reloading: bool = False):
    if my_id in state.players:
        me = state.players[my_id]
        screen.blit(font.render(f"Tick {state.tick}", True, COL_TEXT), (8, 8))
        screen.blit(font.render(f"P{my_id}  ({int(me.x)}, {int(me.y)})", True, COL_TEXT), (8, 26))
        stance_col = COL_STANCE.get(my_stance, COL_TEXT)
        screen.blit(font.render(f"[E] {my_stance.upper()}", True, stance_col), (8, 44))
        # 彈藥 HUD
        _draw_ammo_hud(screen, font, ammo, is_reloading)
        # 金錠計數
        gold = state.gold_counts.get(my_id, 0)
        gold_surf = font.render(f"◆ {gold}", True, (255, 215, 0))
        screen.blit(gold_surf, (8, 62))
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
