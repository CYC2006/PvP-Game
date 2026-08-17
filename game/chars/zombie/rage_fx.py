"""Zombie E — 嗜血 Bloodlust 視覺效果（client-only）

zombie_rage_tick 生效期間，在玩家腳下畫半徑 60px 的血紅色光暈。
繪製順序被安排在 _draw_players() 之前（見 renderer.py），所以光暈中心
會被玩家造型完全蓋住；越靠外緣顏色越淡、alpha 越低，直到完全透明。
"""
import pygame
from game import audio
from game.render_utils import ws, SCREEN_W

RADIUS     = 60
CORE_COLOR = (110, 8, 12)     # 深血紅：光暈中心（被玩家蓋住）
EDGE_COLOR = (200, 50, 40)    # 較淺的紅：光暈外緣
CORE_ALPHA = 190
EDGE_ALPHA = 0
STEPS      = 14

_glow_surf: pygame.Surface = None   # 常數形狀，所有玩家共用同一張快取貼圖

_was_active: dict = {}   # pid → bool，上一幀 zombie_rage_tick 是否 >= 0


def detect_bloodlust_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Zombie':
            continue
        active = player.zombie_rage_tick >= 0
        if active and not _was_active.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('others/zombie_bloodlust.wav', volume)
        _was_active[pid] = active


def _build_glow() -> pygame.Surface:
    surf = pygame.Surface((RADIUS * 2, RADIUS * 2), pygame.SRCALPHA)
    for i in range(STEPS, 0, -1):
        t     = i / STEPS   # 1.0＝最外層 → 接近 0＝最內層
        r     = max(1, int(RADIUS * t))
        color = tuple(int(EDGE_COLOR[c] + (CORE_COLOR[c] - EDGE_COLOR[c]) * (1 - t))
                      for c in range(3))
        alpha = int(EDGE_ALPHA + (CORE_ALPHA - EDGE_ALPHA) * (1 - t))
        pygame.draw.circle(surf, (*color, alpha), (RADIUS, RADIUS), r)
    return surf


def draw(screen, state, cx: float, cy: float) -> None:
    global _glow_surf
    if _glow_surf is None:
        _glow_surf = _build_glow()
    for player in state.players.values():
        if player.zombie_rage_tick < 0:
            continue
        sx, sy = ws(player.x, player.y, cx, cy)
        if sx < -RADIUS or sx > SCREEN_W + RADIUS:
            continue
        screen.blit(_glow_surf, (sx - RADIUS, sy - RADIUS))
