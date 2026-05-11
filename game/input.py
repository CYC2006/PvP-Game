import pygame
from game.command import PlayerCommand

SHOOT_COOLDOWN_MS = 60
MAGAZINE_SIZE     = 45
RELOAD_TIME_MS    = 2000

_last_shot_time:  int  = 0
_ammo:            int  = MAGAZINE_SIZE
_reloading:       bool = False
_reload_start_ms: int  = 0


def read_input(player_id: int, keys_held: set,
               logical_mouse: tuple,
               stance: str,
               shift_held: bool) -> tuple:
    """
    stance      : "stand" | "machine"（由 client 透過 E 鍵切換）
    shift_held  : Shift 是否被按住

    回傳 (PlayerCommand, effective_stance, ammo, is_reloading)
    effective_stance : "stand" | "machine" | "hold" | "reload"
      - reload  = 換彈中，無法射擊，蹲下也不切換造型
      - hold    = shift，0.5× 速度，無法射擊
      - stand   = 無武器模式，無法射擊
      - machine = 持機槍模式，可射擊
    """
    global _last_shot_time, _ammo, _reloading, _reload_start_ms

    dx, dy = 0.0, 0.0
    if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
    if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
    if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
    if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

    crouching = shift_held

    now = pygame.time.get_ticks()

    # ── 換彈完成判斷 ──────────────────────────────────────────────
    if _reloading and (now - _reload_start_ms) >= RELOAD_TIME_MS:
        _reloading = False
        _ammo      = MAGAZINE_SIZE

    # ── effective_stance：換彈期間固定 reload，不受 Shift 影響 ──
    if _reloading:
        effective_stance = "reload"
    elif crouching:
        effective_stance = "hold"
    else:
        effective_stance = stance

    from game.renderer import LOGICAL_W, LOGICAL_H
    lx, ly = logical_mouse
    aim_x = float(lx - LOGICAL_W // 2)
    aim_y = float(ly - LOGICAL_H // 2)

    # ── 射擊（換彈中禁止）────────────────────────────────────────
    shooting = False
    if (not _reloading
            and effective_stance == "machine"
            and pygame.mouse.get_pressed()[0]
            and (now - _last_shot_time) >= SHOOT_COOLDOWN_MS):
        shooting        = True
        _last_shot_time = now
        _ammo          -= 1
        if _ammo <= 0:
            _ammo            = 0
            _reloading       = True
            _reload_start_ms = now

    cmd = PlayerCommand(
        player_id=player_id,
        move_x=dx, move_y=dy,
        shooting=shooting,
        aim_x=aim_x, aim_y=aim_y,
        crouching=crouching,
        stance=effective_stance,
    )
    return cmd, effective_stance, _ammo, _reloading
