"""Zombie Space — 落地衝擊波視覺效果

偵測 zombie_jump_tick active → -1 的轉換（=落地），
在落點繪製從 60→250 px 擴散的土綠色衝擊波圓環，歷時 0.4 秒。
"""
import time
import pygame
from game.render_utils import ws, SCREEN_W

SHOCKWAVE_START_R  = 60
SHOCKWAVE_END_R    = 150
SHOCKWAVE_DURATION = 0.3   # 秒

# {player_id: was_active}  ← 偵測 active→inactive 轉換
_prev_active:       dict = {}
# [(world_x, world_y, start_time)]
_landing_shockwaves: list = []


def update(state) -> None:
    """每幀呼叫：偵測落地並記錄衝擊波起始座標。"""
    now = time.perf_counter()
    for pid, player in state.players.items():
        was_active = _prev_active.get(pid, False)
        is_active  = player.zombie_jump_tick >= 0
        if was_active and not is_active:
            _landing_shockwaves.append((player.x, player.y, now))
        _prev_active[pid] = is_active


def draw_landing_shockwaves(screen, cx: float, cy: float) -> None:
    """繪製落地衝擊波：土綠色圓環從 60→250 px 擴散，逐漸消隱。"""
    now   = time.perf_counter()
    alive = []
    for wx, wy, t0 in _landing_shockwaves:
        elapsed = now - t0
        if elapsed >= SHOCKWAVE_DURATION:
            continue
        alive.append((wx, wy, t0))
        frac  = elapsed / SHOCKWAVE_DURATION
        r     = max(1, int(SHOCKWAVE_START_R
                           + (SHOCKWAVE_END_R - SHOCKWAVE_START_R) * frac))
        alpha = int(210 * (1.0 - frac))
        sx, sy = ws(wx, wy, cx, cy)
        if sx < -SHOCKWAVE_END_R or sx > SCREEN_W + SHOCKWAVE_END_R:
            continue
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        width = max(2, int(9 * (1.0 - frac)))
        pygame.draw.circle(surf, (80, 180, 60, alpha), (r, r), r, width)
        screen.blit(surf, (sx - r, sy - r))
    _landing_shockwaves[:] = alive
