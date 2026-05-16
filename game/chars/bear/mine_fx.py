import time
import pygame
from game.render_utils import ws, SCREEN_W, SCREEN_H, COL_BULLET

TRIGGER_RADIUS = 60.0
FUSE_TICKS     = 30
EXPL_MAX_R     = 130
EXPL_DURATION  = 0.5

_known:      dict = {}   # mid → (wx, wy, owner_id, triggered_wall_t)
_explosions: list = []   # [(wx, wy, owner_id, start_t)]


def update(state, my_player_id: int) -> None:
    """每幀呼叫：更新追蹤、偵測消失並排爆炸 FX。"""
    current_ids = set(state.mines)
    now = time.perf_counter()

    for mid, mine in state.mines.items():
        prev = _known.get(mid)
        if prev is None:
            trig_t = now if mine.triggered_tick >= 0 else None
            _known[mid] = (mine.x, mine.y, mine.owner_id, trig_t)
        else:
            # 剛剛進入觸發狀態
            if mine.triggered_tick >= 0 and prev[3] is None:
                _known[mid] = (mine.x, mine.y, mine.owner_id, now)

    for mid in list(_known):
        if mid not in current_ids:
            wx, wy, owner, trig_t = _known.pop(mid)
            if trig_t is not None:
                _explosions.append((wx, wy, owner, now))


def draw(screen, state, cx: float, cy: float, my_player_id: int) -> None:
    """繪製地雷：己方看全貌，對方只看到觸發後縮小環。"""
    now = time.perf_counter()
    for mid, mine in state.mines.items():
        sx, sy = ws(mine.x, mine.y, cx, cy)
        color  = COL_BULLET.get(mine.owner_id, (255, 200, 100))

        if mine.owner_id == my_player_id:
            # ── 己方：圓點 + 60px 半透明填充圓 ──
            r = int(TRIGGER_RADIUS)
            surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, 45), (r + 1, r + 1), r)         # 半透明填充
            pygame.draw.circle(surf, (*color, 180), (r + 1, r + 1), r, 2)    # 邊框
            screen.blit(surf, (sx - r - 1, sy - r - 1))
            pygame.draw.circle(screen, color, (sx, sy), 5)                    # 中心圓點
        else:
            # ── 對方：只有觸發後才顯示縮小環 ──
            info = _known.get(mid)
            if info is None or info[3] is None:
                continue
            trig_t = info[3]
            elapsed = now - trig_t
            fuse_s  = FUSE_TICKS / 60.0
            if elapsed >= fuse_s:
                continue
            t = elapsed / fuse_s          # 0 → 1
            r = max(1, int(TRIGGER_RADIUS * (1.0 - t)))
            alpha = int(220 * (1.0 - t * 0.5))
            surf = pygame.Surface((int(TRIGGER_RADIUS) * 2 + 4,
                                    int(TRIGGER_RADIUS) * 2 + 4), pygame.SRCALPHA)
            sc = (int(TRIGGER_RADIUS) + 2, int(TRIGGER_RADIUS) + 2)
            pygame.draw.circle(surf, (*color, alpha), sc, r, 3)
            screen.blit(surf, (sx - int(TRIGGER_RADIUS) - 2,
                                sy - int(TRIGGER_RADIUS) - 2))


def draw_explosions(screen, cx: float, cy: float) -> None:
    now = time.perf_counter()
    alive = []
    for wx, wy, owner, t in _explosions:
        elapsed = now - t
        if elapsed >= EXPL_DURATION:
            continue
        alive.append((wx, wy, owner, t))
        progress = elapsed / EXPL_DURATION
        r     = max(1, int(EXPL_MAX_R * progress))
        alpha = int(200 * (1.0 - progress))
        col   = COL_BULLET.get(owner, (255, 200, 100))
        sx, sy = ws(wx, wy, cx, cy)
        if -EXPL_MAX_R <= sx <= SCREEN_W + EXPL_MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _explosions[:] = alive
