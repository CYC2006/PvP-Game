import pygame
from game.command import PlayerCommand

SHOOT_COOLDOWN_MS = 300

_last_shot_time: int = 0


def read_input(player_id: int, keys_held: set,
               logical_mouse: tuple) -> PlayerCommand:
    """
    keys_held     : KEYDOWN/KEYUP 事件追蹤的按鍵集合
    logical_mouse : 已轉換到邏輯畫布座標的滑鼠位置 (lx, ly)
    """
    global _last_shot_time

    dx, dy = 0.0, 0.0
    if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
    if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
    if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
    if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

    from game.renderer import LOGICAL_W, LOGICAL_H
    lx, ly = logical_mouse
    aim_x = float(lx - LOGICAL_W // 2)
    aim_y = float(ly - LOGICAL_H // 2)

    now = pygame.time.get_ticks()
    shooting = False
    if pygame.mouse.get_pressed()[0] and (now - _last_shot_time) >= SHOOT_COOLDOWN_MS:
        shooting = True
        _last_shot_time = now

    return PlayerCommand(
        player_id=player_id,
        move_x=dx, move_y=dy,
        shooting=shooting,
        aim_x=aim_x, aim_y=aim_y,
    )
