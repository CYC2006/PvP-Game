"""Soldier E — 防護罩視覺效果

活躍期間：以玩家為圓心的白色漸層圓（外緣較不透明，內部透明）。
消失時（破壞或到期）：從 80px 擴散至 400px 的半透明白色衝擊波，歷時 0.5 秒。
"""

import time
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H

SHIELD_RADIUS      = 80      # px（與 shield_state 同步）
SHOCKWAVE_MAX_R    = 400     # 衝擊波最大半徑
SHOCKWAVE_DURATION = 0.5     # 秒
# {owner_id: was_broken_status}  ← 追蹤上一幀的狀態，偵測消失
_known:      dict = {}
# [(wx, wy, start_t)]  ← 衝擊波列表
_shockwaves: list = []


def update(state) -> None:
    """每幀呼叫：追蹤護盾狀態，偵測消失並觸發衝擊波。"""
    current_ids = set(state.shields)
    now = time.perf_counter()

    for oid, shield in state.shields.items():
        broken = shield.broken_tick >= 0
        prev = _known.get(oid)
        if prev is None:
            # 新出現的護盾
            _known[oid] = broken
            if broken:
                # 出現即破壞（罕見），直接觸發衝擊波
                player = state.players.get(oid)
                if player:
                    _shockwaves.append((player.x, player.y, now))
        else:
            # 已知護盾：偵測 active → broken 轉換
            if not prev and broken:
                _known[oid] = True
                player = state.players.get(oid)
                if player:
                    _shockwaves.append((player.x, player.y, now))

    # 清除已消失的護盾（linger 結束後從 state.shields 移除）
    for oid in list(_known):
        if oid not in current_ids:
            # 護盾消失但還沒觸發過衝擊波（active 狀態直接消失，理論上不應發生，但防呆）
            if not _known[oid]:
                player = state.players.get(oid)
                if player:
                    _shockwaves.append((player.x, player.y, now))
            _known.pop(oid)


def draw(screen, state, cx: float, cy: float) -> None:
    """繪製活躍護盾：單一輪廓圓 + 極淡填充。"""
    for oid, shield in state.shields.items():
        if shield.broken_tick >= 0:
            continue   # 已破壞，不再繪製圓形
        player = state.players.get(oid)
        if player is None:
            continue
        sx, sy = ws(player.x, player.y, cx, cy)
        if sx < -SHIELD_RADIUS - 10 or sx > SCREEN_W + SHIELD_RADIUS + 10:
            continue

        hp_ratio = max(0.0, shield.hp / shield.max_hp)
        r = SHIELD_RADIUS

        # 極淡填充（幾乎透明的內部）
        fill_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(fill_surf, (200, 215, 255, int(22 * hp_ratio)), (r, r), r)
        screen.blit(fill_surf, (sx - r, sy - r))

        # 單一清晰輪廓
        ring_surf = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(ring_surf, (220, 235, 255, int(170 * hp_ratio)),
                           (r + 3, r + 3), r, 3)
        screen.blit(ring_surf, (sx - r - 3, sy - r - 3))


def draw_shockwaves(screen, cx: float, cy: float) -> None:
    """繪製衝擊波（從 SHIELD_RADIUS 擴散到 SHOCKWAVE_MAX_R）。"""
    now   = time.perf_counter()
    alive = []
    for wx, wy, t0 in _shockwaves:
        elapsed = now - t0
        if elapsed >= SHOCKWAVE_DURATION:
            continue
        alive.append((wx, wy, t0))
        frac  = elapsed / SHOCKWAVE_DURATION
        r     = max(1, int(SHIELD_RADIUS + (SHOCKWAVE_MAX_R - SHIELD_RADIUS) * frac))
        alpha = int(180 * (1.0 - frac))
        sx, sy = ws(wx, wy, cx, cy)
        if sx < -SHOCKWAVE_MAX_R or sx > SCREEN_W + SHOCKWAVE_MAX_R:
            continue
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        # 外圓
        pygame.draw.circle(surf, (255, 255, 255, alpha), (r, r), r, max(2, int(8 * (1 - frac))))
        screen.blit(surf, (sx - r, sy - r))
    _shockwaves[:] = alive
