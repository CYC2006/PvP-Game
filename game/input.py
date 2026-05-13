import pygame
from game.command import PlayerCommand

# 預設值（連線前 / 未選角時的 fallback）
SHOOT_COOLDOWN_MS = 333
MAGAZINE_SIZE     = 12
RELOAD_TIME_MS    = 2000

_last_shot_time:  int  = 0
_ammo:            int  = MAGAZINE_SIZE
_reloading:       bool = False
_reload_start_ms: int  = 0


def init_char(char_key: str) -> None:
    """
    遊戲開始後呼叫，依選擇角色設定射速 / 彈夾 / 換彈時間，並重置射擊狀態。
    此後 read_input 會使用這些數值。
    """
    global SHOOT_COOLDOWN_MS, MAGAZINE_SIZE, RELOAD_TIME_MS
    global _ammo, _reloading, _reload_start_ms, _last_shot_time

    from game.char_data import get_stat

    interval = get_stat(char_key, "fire_interval")
    SHOOT_COOLDOWN_MS = int(interval * 1000) if interval and interval > 0 else 9999

    mag_str = get_stat(char_key, "mag")
    MAGAZINE_SIZE = int(mag_str) if mag_str and str(mag_str).strip().isdigit() else 9999

    reload_s = get_stat(char_key, "reload_time")
    RELOAD_TIME_MS = int(reload_s * 1000) if reload_s and reload_s > 0 else 99999

    # 重置射擊狀態
    _ammo            = MAGAZINE_SIZE
    _reloading       = False
    _reload_start_ms = 0
    _last_shot_time  = 0


def read_input(player_id: int, keys_held: set,
               logical_mouse: tuple,
               shift_held: bool) -> tuple:
    """
    shift_held  : Shift 是否被按住（run 模式，速度 ×1.2）

    回傳 (PlayerCommand, effective_stance, ammo, is_reloading)
    effective_stance : "machine" | "reload"
    """
    global _last_shot_time, _ammo, _reloading, _reload_start_ms

    dx, dy = 0.0, 0.0
    if pygame.K_w in keys_held or pygame.K_UP    in keys_held: dy -= 1.0
    if pygame.K_s in keys_held or pygame.K_DOWN  in keys_held: dy += 1.0
    if pygame.K_a in keys_held or pygame.K_LEFT  in keys_held: dx -= 1.0
    if pygame.K_d in keys_held or pygame.K_RIGHT in keys_held: dx += 1.0

    running = shift_held

    now = pygame.time.get_ticks()

    # ── 換彈完成判斷 ──────────────────────────────────────────────
    if _reloading and (now - _reload_start_ms) >= RELOAD_TIME_MS:
        _reloading = False
        _ammo      = MAGAZINE_SIZE

    # ── effective_stance：換彈期間固定 reload，否則一律 machine ──
    effective_stance = "reload" if _reloading else "machine"

    from game.renderer import LOGICAL_W, LOGICAL_H
    lx, ly = logical_mouse
    aim_x = float(lx - LOGICAL_W // 2)
    aim_y = float(ly - LOGICAL_H // 2)

    # ── 射擊（換彈中禁止）────────────────────────────────────────
    shooting = False
    if (not _reloading
            and pygame.mouse.get_pressed()[0]
            and (now - _last_shot_time) >= SHOOT_COOLDOWN_MS):
        shooting        = True
        _last_shot_time = now
        if MAGAZINE_SIZE < 9999:   # 有彈夾限制
            _ammo -= 1
            if _ammo <= 0:
                _ammo            = 0
                _reloading       = True
                _reload_start_ms = now

    cmd = PlayerCommand(
        player_id=player_id,
        move_x=dx, move_y=dy,
        shooting=shooting,
        aim_x=aim_x, aim_y=aim_y,
        running=running,
        stance=effective_stance,
    )
    return cmd, effective_stance, _ammo, _reloading
