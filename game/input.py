import pygame
from game.command import PlayerCommand

SCREEN_W = 1280
SCREEN_H = 720

SHOOT_COOLDOWN_MS = 300

_last_shot_time: int = 0

MOVE_KEYS = {
    pygame.K_w, pygame.K_UP,
    pygame.K_s, pygame.K_DOWN,
    pygame.K_a, pygame.K_LEFT,
    pygame.K_d, pygame.K_RIGHT,
}


def read_input(player_id: int, keys_held: set) -> PlayerCommand:
    """
    keys_held: set of pygame key constants currently pressed,
               maintained via KEYDOWN/KEYUP events in client.py
    """
    global _last_shot_time

    dx, dy = 0.0, 0.0
    if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
    if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
    if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
    if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

    # 滑鼠瞄準：畫面中心 = 自己的位置
    mx, my = pygame.mouse.get_pos()
    aim_x = float(mx - SCREEN_W // 2)
    aim_y = float(my - SCREEN_H // 2)

    # 左鍵射擊（含冷卻）
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
