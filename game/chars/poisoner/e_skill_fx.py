"""Poisoner E — 毒素衝擊波視覺效果（client-only）

偵測 player.poisoner_e_shockwave_seq 變化，在施法者位置繪製
60→400 px 的紫色擴散圓環，歷時 0.6 秒。
"""
import time
import pygame
from game.render_utils import ws, SCREEN_W

SW_START_R  = 60
SW_END_R    = 400
SW_DURATION = 0.6   # 秒
SW_COLOR    = (150, 80, 205)   # 紫色

_prev_seq:   dict = {}   # player_id → last seen seq
_shockwaves: list = []   # [(world_x, world_y, start_t)]


def update(state) -> None:
    for pid, player in state.players.items():
        prev = _prev_seq.get(pid, -1)
        seq  = player.poisoner_e_shockwave_seq
        if seq != prev and prev != -1:
            _shockwaves.append((player.x, player.y, time.perf_counter()))
        _prev_seq[pid] = seq


def draw(screen, cx: float, cy: float) -> None:
    now   = time.perf_counter()
    alive = []
    for wx, wy, t0 in _shockwaves:
        elapsed = now - t0
        if elapsed >= SW_DURATION:
            continue
        alive.append((wx, wy, t0))
        frac  = elapsed / SW_DURATION
        r     = max(1, int(SW_START_R + (SW_END_R - SW_START_R) * frac))
        alpha = int(220 * (1.0 - frac))
        sx, sy = ws(wx, wy, cx, cy)
        if sx < -SW_END_R or sx > SCREEN_W + SW_END_R:
            continue
        surf  = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        width = max(2, int(8 * (1.0 - frac)))
        pygame.draw.circle(surf, (*SW_COLOR, alpha), (r, r), r, width)
        screen.blit(surf, (sx - r, sy - r))
    _shockwaves[:] = alive
