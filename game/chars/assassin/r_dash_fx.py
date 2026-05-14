import math
import random
import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws

# ── 殘影（速度提升 + R 技能共用）──────────────────────────────────────────────
# 每筆：[rotated_surface, world_x, world_y, spawn_tick, max_age]
_afterimages:          list = []
_last_afterimage_tick: int  = 0
_last_r_afterimage_tick: int = 0

# ── R 技能地板刮痕三角形碎片 ──────────────────────────────────────────────────
_trail_triangles:  list = []
_trail_end_ms:     int  = 0
_trail_was_active: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# 殘影
# ─────────────────────────────────────────────────────────────────────────────

def maybe_spawn_afterimage(px: float, py: float,
                            rotated_surf: pygame.Surface,
                            state_tick: int) -> None:
    """R 技能期間每 3 ticks、速度提升期間每 6 ticks 留下殘影。"""
    global _last_afterimage_tick, _last_r_afterimage_tick
    import game.input as _inp
    now_ms   = pygame.time.get_ticks()
    r_active = (now_ms - _inp._r_skill_start_ms < 500 and _inp._r_skill_start_ms > 0)
    if r_active:
        if state_tick - _last_r_afterimage_tick < 3:
            return
        _last_r_afterimage_tick = state_tick
        _afterimages.append([rotated_surf.copy(), px, py, state_tick, 18])
    elif now_ms < _inp._speed_boost_end_ms:
        if state_tick - _last_afterimage_tick < 6:
            return
        _last_afterimage_tick = state_tick
        _afterimages.append([rotated_surf.copy(), px, py, state_tick, 24])


def draw_afterimages(screen, cx: float, cy: float, state_tick: int) -> None:
    """繪製速度提升 / R 技能殘影，須在玩家之前呼叫使其出現在底層。"""
    alive = []
    for item in _afterimages:
        img, wx, wy, spawn_tick = item[0], item[1], item[2], item[3]
        max_age = item[4] if len(item) > 4 else 24
        age = state_tick - spawn_tick
        if age >= max_age:
            continue
        alive.append(item)
        alpha = int(170 * (1.0 - age / max_age))
        tmp = img.copy()
        tmp.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        sx, sy = ws(wx, wy, cx, cy)
        screen.blit(tmp, (sx - img.get_width() // 2, sy - img.get_height() // 2))
    _afterimages[:] = alive


# ─────────────────────────────────────────────────────────────────────────────
# 衝刺塵土（Dash）
# ─────────────────────────────────────────────────────────────────────────────

def spawn_dash_dust(px: float, py: float, particles: list) -> None:
    """衝刺時在玩家後方噴出灰塵粒子（每幀 3 顆）。"""
    import game.input as _inp
    if not _inp._dash_active:
        return
    now  = time.perf_counter()
    base = math.atan2(-_inp._dash_dy, -_inp._dash_dx)
    dust_cols = [(190, 180, 165), (168, 160, 148), (210, 202, 188)]
    for _ in range(3):
        angle = base + random.uniform(-0.65, 0.65)
        speed = random.uniform(25, 70)
        particles.append([
            px + random.uniform(-7, 7),
            py + random.uniform(-7, 7),
            math.cos(angle) * speed,
            math.sin(angle) * speed,
            now,
            random.uniform(0.12, 0.28),
            random.choice(dust_cols),
            random.uniform(2.0, 4.5),
        ])


# ─────────────────────────────────────────────────────────────────────────────
# R 技能地板刮痕
# ─────────────────────────────────────────────────────────────────────────────

def update_r_trail(px: float, py: float) -> None:
    """每幀在本地玩家位置生成刮痕三角形碎片，偵測 R 技能結束以驅動淡出。"""
    global _trail_triangles, _trail_end_ms, _trail_was_active
    import game.input as _inp
    now_ms   = pygame.time.get_ticks()
    r_active = (now_ms - _inp._r_skill_start_ms < 500 and _inp._r_skill_start_ms > 0)
    if r_active:
        if not _trail_was_active:
            _trail_triangles.clear()
            _trail_end_ms = 0
        ox = random.uniform(-10, 10)
        oy = random.uniform(-10, 10)
        angle  = random.uniform(0, math.pi * 2)
        base   = random.uniform(4, 9)
        height = random.uniform(9, 18)
        color  = random.choice([(0, 0, 0), (55, 55, 55), (35, 35, 35), (75, 75, 75)])
        _trail_triangles.append((px + ox, py + oy, angle, base, height, color))
        _trail_was_active = True
    elif _trail_was_active:
        _trail_end_ms    = now_ms
        _trail_was_active = False


def draw_r_trail(screen, cx: float, cy: float) -> None:
    """繪製 R 技能刮痕：技能結束後等待 0.5s，再於 0.5s 內淡出。"""
    global _trail_triangles, _trail_end_ms
    if not _trail_triangles:
        return
    now_ms = pygame.time.get_ticks()
    if _trail_end_ms == 0:
        alpha = 200
    else:
        elapsed = now_ms - _trail_end_ms
        wait_ms, fade_ms = 500, 500
        if elapsed < wait_ms:
            alpha = 200
        elif elapsed < wait_ms + fade_ms:
            alpha = int(200 * (1.0 - (elapsed - wait_ms) / fade_ms))
        else:
            _trail_triangles.clear()
            _trail_end_ms = 0
            return

    surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    for entry in _trail_triangles:
        wx, wy, angle, base, height = entry[0], entry[1], entry[2], entry[3], entry[4]
        color = entry[5] if len(entry) > 5 else (0, 0, 0)
        sx, sy = ws(wx, wy, cx, cy)
        ca, sa = math.cos(angle), math.sin(angle)
        def _rot(lx, ly, _sx=sx, _sy=sy, _ca=ca, _sa=sa):
            return (_sx + lx * _ca - ly * _sa, _sy + lx * _sa + ly * _ca)
        p1 = _rot(0,          -height * 2 / 3)
        p2 = _rot(-base / 2,   height / 3)
        p3 = _rot( base / 2,   height / 3)
        pygame.draw.polygon(surf, (*color, alpha), [p1, p2, p3])
    screen.blit(surf, (0, 0))


def r_skill_angle(aim_angle_deg: float) -> float:
    """R 技能期間覆蓋本地玩家角度為順時針旋轉動畫；技能結束後恢復滑鼠瞄準。"""
    import game.input as _inp
    elapsed = pygame.time.get_ticks() - _inp._r_skill_start_ms
    if elapsed < 0 or elapsed >= 500 or _inp._r_skill_start_ms == 0:
        return aim_angle_deg
    phase_ms = 250
    if elapsed < phase_ms:
        return _inp._r_skill_start_angle + 180.0 * (elapsed / phase_ms)
    else:
        progress = (elapsed - phase_ms) / phase_ms
        return _inp._r_skill_start_angle + 180.0 + 180.0 * progress
