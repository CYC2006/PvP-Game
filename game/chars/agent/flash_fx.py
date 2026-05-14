import math
import os
import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws

_bullet_pos: dict = {}   # bid → (x, y)
_explosions: list = []   # [(wx, wy, spawn_t)]
_spin_angle: dict = {}   # bid → 累積 radians
_sprites:    dict = {}   # owner_id → Surface


def detect_disappeared(state, now: float) -> None:
    """偵測已消失的閃光彈 → 加入爆炸特效佇列。"""
    current = {bid for bid, b in state.bullets.items()
               if getattr(b, 'bullet_type', 0) == 1}
    for bid in set(_bullet_pos) - current:
        if bid in _bullet_pos:
            _explosions.append((*_bullet_pos[bid], now))
        _bullet_pos.pop(bid, None)
        _spin_angle.pop(bid, None)


def draw_bullet(screen, bullet, sx: int, sy: int, color) -> None:
    """繪製飛行中的閃光彈（旋轉圖片）。"""
    prev = _bullet_pos.get(bullet.id)
    speed = (math.hypot(bullet.x - prev[0], bullet.y - prev[1])
             if prev else 0.0)
    _bullet_pos[bullet.id] = (bullet.x, bullet.y)
    angle = _spin_angle.get(bullet.id, 0.0) + speed * 0.06
    _spin_angle[bullet.id] = angle

    owner = bullet.owner_id
    if owner not in _sprites:
        path = os.path.join("assets", "objects", f"flashbang_P{owner}.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (48, 36))
        except Exception:
            img = None
        _sprites[owner] = img

    sprite = _sprites.get(owner)
    if sprite:
        rotated = pygame.transform.rotate(sprite, -math.degrees(angle))
        screen.blit(rotated, (sx - rotated.get_width()  // 2,
                               sy - rotated.get_height() // 2))
    else:
        pygame.draw.circle(screen, color, (sx, sy), 7)


def draw_explosions(screen, cx: float, cy: float) -> None:
    """繪製閃光彈爆炸擴散白圈。"""
    now = time.perf_counter()
    alive = []
    DURATION, MAX_R = 0.5, 130
    for wx, wy, t in _explosions:
        elapsed = now - t
        if elapsed >= DURATION:
            continue
        alive.append((wx, wy, t))
        progress = elapsed / DURATION
        r     = max(1, int(MAX_R * progress))
        alpha = int(230 * (1.0 - progress))
        sx, sy = ws(wx, wy, cx, cy)
        if -MAX_R <= sx <= SCREEN_W + MAX_R and -MAX_R <= sy <= SCREEN_H + MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 220, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _explosions[:] = alive


def draw_screen_flash(screen, state, my_id: int) -> None:
    """被閃光彈命中時全螢幕白色疊加層。"""
    if my_id not in state.players:
        return
    ft = getattr(state.players[my_id], 'flash_ticks', 0)
    if ft <= 0:
        return
    alpha = 255 if ft > 120 else int(255 * ft / 120)
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, alpha))
    screen.blit(overlay, (0, 0))
