import pygame
from game.command import PlayerCommand

SHOOT_COOLDOWN_MS = 60

_last_shot_time: int = 0


def read_input(player_id: int, keys_held: set,
               logical_mouse: tuple,
               stance: str,
               shift_held: bool) -> tuple:
    """
    stance      : "stand" | "machine"（由 client 透過 E 鍵切換）
    shift_held  : Shift 是否被按住

    回傳 (PlayerCommand, effective_stance)
    effective_stance : "stand" | "machine" | "hold"
      - hold  = shift + 移動中，0.5× 速度，無法射擊
      - stand = 無武器模式，無法射擊
      - machine = 持機槍模式，可射擊
    """
    global _last_shot_time

    dx, dy = 0.0, 0.0
    if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
    if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
    if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
    if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

    crouching = shift_held   # 按住 Shift 即蹲下，不需移動

    effective_stance = "hold" if crouching else stance

    from game.renderer import LOGICAL_W, LOGICAL_H
    lx, ly = logical_mouse
    aim_x = float(lx - LOGICAL_W // 2)
    aim_y = float(ly - LOGICAL_H // 2)

    now = pygame.time.get_ticks()
    shooting = False
    if (effective_stance == "machine"
            and pygame.mouse.get_pressed()[0]
            and (now - _last_shot_time) >= SHOOT_COOLDOWN_MS):
        shooting = True
        _last_shot_time = now

    cmd = PlayerCommand(
        player_id=player_id,
        move_x=dx, move_y=dy,
        shooting=shooting,
        aim_x=aim_x, aim_y=aim_y,
        crouching=crouching,
        stance=effective_stance,
    )
    return cmd, effective_stance
