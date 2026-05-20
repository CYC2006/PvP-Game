import math
import os
import time

import pygame

from game.render_utils import SCREEN_W, SCREEN_H, ws, COL_BULLET

_bullet_pos: dict = {}   # bid → (x, y, owner_id)
_explosions: list = []   # [(wx, wy, spawn_t, owner_id)]
_spin_angle: dict = {}   # bid → 累積 radians
_sprites:    dict = {}   # owner_id → Surface


def detect_disappeared(state, now: float) -> None:
    """偵測已消失的手榴彈 → 加入爆炸特效佇列。"""
    current = {bid for bid, b in state.bullets.items()
               if getattr(b, 'bullet_type', 0) == 2}
    for bid in set(_bullet_pos) - current:
        if bid in _bullet_pos:
            bx, by, bowner = _bullet_pos[bid]
            _explosions.append((bx, by, now, bowner))
        _bullet_pos.pop(bid, None)
        _spin_angle.pop(bid, None)


def draw_bullet(screen, bullet, sx: int, sy: int, color) -> None:
    """繪製飛行中的手榴彈（旋轉圖片）。"""
    prev = _bullet_pos.get(bullet.id)
    speed = (math.hypot(bullet.x - prev[0], bullet.y - prev[1])
             if prev else 0.0)
    _bullet_pos[bullet.id] = (bullet.x, bullet.y, bullet.owner_id)
    angle = _spin_angle.get(bullet.id, 0.0) + speed * 0.06
    _spin_angle[bullet.id] = angle

    owner = bullet.owner_id
    if owner not in _sprites:
        path = os.path.join("assets", "objects", f"grenade_P{owner}.png")
        try:
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (48, 48))
        except Exception:
            img = None
        _sprites[owner] = img

    sprite = _sprites.get(owner)
    if sprite:
        rotated = pygame.transform.rotate(sprite, -math.degrees(angle))
        screen.blit(rotated, (sx - rotated.get_width()  // 2,
                               sy - rotated.get_height() // 2))
    else:
        pygame.draw.circle(screen, color, (sx, sy), 8)


def draw_explosions(screen, cx: float, cy: float) -> None:
    """繪製手榴彈爆炸擴散圈。"""
    now = time.perf_counter()
    alive = []
    DURATION, MAX_R = 0.5, 130
    for wx, wy, t, owner in _explosions:
        elapsed = now - t
        if elapsed >= DURATION:
            continue
        alive.append((wx, wy, t, owner))
        progress = elapsed / DURATION
        r     = max(1, int(MAX_R * progress))
        alpha = int(200 * (1.0 - progress))
        col   = COL_BULLET.get(owner, (255, 200, 100))
        sx, sy = ws(wx, wy, cx, cy)
        if -MAX_R <= sx <= SCREEN_W + MAX_R and -MAX_R <= sy <= SCREEN_H + MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _explosions[:] = alive
