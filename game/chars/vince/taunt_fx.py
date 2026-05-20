"""Vince Space — 嘲諷衝擊波視覺效果（薰衣草色）

偵測 vince_taunt_tick inactive→active 的轉換（=技能啟動），
在玩家位置繪製從 60→500 px 擴散的薰衣草色衝擊波圓環，歷時 0.8 秒。
"""
import time
import pygame
from game.render_utils import ws, SCREEN_W

_START_R  = 60
_END_R    = 500
_DURATION = 0.8   # 秒

# {player_id: was_active}  ← 偵測 inactive→active 轉換
_prev_active: dict = {}
# [(world_x, world_y, start_time)]
_shockwaves: list = []


def update(state) -> None:
    """每幀呼叫：偵測嘲諷啟動並記錄衝擊波起始座標。"""
    now = time.perf_counter()
    for pid, player in state.players.items():
        was_active = _prev_active.get(pid, False)
        is_active  = player.vince_taunt_tick >= 0
        if not was_active and is_active:   # inactive → active = 技能啟動
            _shockwaves.append((player.x, player.y, now))
        _prev_active[pid] = is_active


def draw_taunt_shockwaves(screen, cx: float, cy: float) -> None:
    """繪製嘲諷衝擊波：薰衣草色圓環從 60→500 px 擴散，逐漸消隱。"""
    now   = time.perf_counter()
    alive = []
    for wx, wy, t0 in _shockwaves:
        elapsed = now - t0
        if elapsed >= _DURATION:
            continue
        alive.append((wx, wy, t0))
        frac  = elapsed / _DURATION
        r     = max(1, int(_START_R + (_END_R - _START_R) * frac))
        alpha = int(200 * (1.0 - frac))
        sx, sy = ws(wx, wy, cx, cy)
        if sx < -_END_R or sx > SCREEN_W + _END_R:
            continue   # 畫面外，保留但不繪製
        surf  = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        width = max(2, int(10 * (1.0 - frac)))
        pygame.draw.circle(surf, (180, 130, 255, alpha), (r, r), r, width)
        screen.blit(surf, (sx - r, sy - r))
    _shockwaves[:] = alive
