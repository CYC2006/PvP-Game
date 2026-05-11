import os
import math
import time
import random
import pygame
from game.state import GameState, MAX_HP, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS, BULLET_RADIUS
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
CHAR_DIR: dict = {
    "hitman1":    ("Hitman 1",    "hitman1"),
    "manBlue":    ("Man Blue",    "manBlue"),
    "manBrown":   ("Man Brown",   "manBrown"),
    "manOld":     ("Man Old",     "manOld"),
    "robot1":     ("Robot 1",     "robot1"),
    "soldier1":   ("Soldier 1",   "soldier1"),
    "survivor1":  ("Survivor 1",  "survivor1"),
    "womanGreen": ("Woman Green", "womanGreen"),
    "zoimbie1":   ("Zombie 1",    "zoimbie1"),
}

# 障礙物圖片快取：(kind, w, h) → Surface
_sprite_cache: dict = {}
# 角色圖片快取：(char_key, stance) → Surface（原尺寸 × PLAYER_SPRITE_SCALE）
_player_cache: dict = {}

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

# 各障礙物種類的粒子顏色（同色系深淺變化）
PARTICLE_COLORS: dict = {
    "box_1":  [(165, 108, 52), (195, 142, 68), (145, 88, 38),
               (220, 168, 92), (130,  75, 30)],
    "rock_1": [(138, 132, 122), (112, 108, 100), (158, 152, 142),
               ( 88,  84,  78), (175, 170, 160)],
    "rock_2": [(118, 113, 105), (143, 138, 128), ( 93,  90,  84),
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
            _spawn_particles(obs.x, obs.y, obs.kind, count=18)  # 多一點粒子
    _prev_destroyed.clear()
    _prev_destroyed.update(state.destroyed_obstacles)

    # ── 2. 消失子彈偵測 ───────────────────────────────────────────
    for bid, (bx, by) in _prev_bullet_pos.items():
        if bid not in cur_ids and obstacles:
            for oid, obs in obstacles.items():
                if oid in state.destroyed_obstacles:
                    continue
                check_r = BULLET_RADIUS + max(obs.width, obs.height) * 0.55
                if obs.collides_circle(bx, by, check_r):
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


def _spawn_particles(bx: float, by: float, kind: str, count: int = 12) -> None:
    """在被擊中位置朝四周噴出同色系粒子。"""
    now    = time.perf_counter()
    colors = PARTICLE_COLORS.get(kind, [(128, 128, 128)])
    for _ in range(count):
        angle    = random.uniform(0, math.tau)
        speed    = random.uniform(40, 140)
        max_life = random.uniform(0.20, 0.45)
        color    = random.choice(colors)
        max_size = random.uniform(2.0, 5.5)
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

    _draw_particles(screen, cx, cy)
    _draw_bullets(screen, state, cx, cy)
    _draw_players(screen, state, my_id, cx, cy, font, my_stance, aim_angle_deg,
                  player_chars or {})
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
    for oid, obs in obstacles.items():
        if oid in destroyed:
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


# ── 子彈 ──────────────────────────────────────────────────────────────────────

def _draw_bullets(screen, state, cx, cy):
    for bullet in state.bullets.values():
        sx, sy = _ws(bullet.x, bullet.y, cx, cy)
        if -BULLET_RADIUS <= sx <= SCREEN_W + BULLET_RADIUS \
                and -BULLET_RADIUS <= sy <= SCREEN_H + BULLET_RADIUS:
            color = COL_BULLET.get(bullet.owner_id, (255, 255, 200))
            pygame.draw.circle(screen, color, (sx, sy), BULLET_RADIUS)


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

        # 對方頭上顯示 HP pip bar
        if pid != my_id:
            head_y = sy - rotated.get_height() // 2 - 8
            _draw_pip_bar(screen, player.hp, sx - 20, head_y)

        # 玩家名稱標籤
        label_y = sy - rotated.get_height() // 2 - 20
        label = font.render(f"P{pid}", True, COL_TEXT)
        screen.blit(label, (sx - label.get_width() // 2, label_y))


def _draw_pip_bar(screen, hp: int, x: int, y: int):
    pip_w = 7
    for i in range(MAX_HP):
        col = COL_HP_FILL if i < hp else COL_HP_BG
        pygame.draw.rect(screen, col, (x + i * (pip_w + 2), y, pip_w, 5))


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
        progress = min(1.0, elapsed / RELOAD_TIME_MS)
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
        col   = (255, 220, 60) if ammo > 10 else (255, 90, 90)
        label = font.render(f"AMMO  {ammo} / {MAGAZINE_SIZE}", True, col)

    screen.blit(label, (bar_x + bar_w - label.get_width(), ammo_y - 18))


def _draw_hp_bar(screen, state, my_id, font):
    bar_y = SCREEN_H - HP_BAR_Y_FROM_BOTTOM
    hp    = state.players[my_id].hp if my_id in state.players else 0

    pygame.draw.rect(screen, COL_HP_BG,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), border_radius=4)

    fill_w = int(HP_BAR_W * max(0, hp) / MAX_HP)
    if fill_w > 0:
        pygame.draw.rect(screen, COL_HP_FILL,
                         (HP_BAR_X, bar_y, fill_w, HP_BAR_H), border_radius=4)

    pygame.draw.rect(screen, COL_HP_BORDER,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), 2, border_radius=4)

    pip_w = (HP_BAR_W - HP_PIP_GAP * (MAX_HP + 1)) // MAX_HP
    for i in range(MAX_HP):
        pip_x = HP_BAR_X + HP_PIP_GAP + i * (pip_w + HP_PIP_GAP)
        col = (255, 90, 90) if i < hp else (80, 30, 30)
        pygame.draw.rect(screen, col,
                         (pip_x, bar_y + 3, pip_w, HP_BAR_H - 6), border_radius=2)

    label = font.render(f"HP  {hp} / {MAX_HP}", True, COL_TEXT)
    screen.blit(label, (HP_BAR_X, bar_y - 18))


def _draw_waiting(screen, font):
    msg = font.render("Waiting for server...", True, COL_TEXT)
    screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2,
                      SCREEN_H // 2 - msg.get_height() // 2))
