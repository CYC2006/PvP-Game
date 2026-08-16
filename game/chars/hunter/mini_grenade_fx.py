import time

import pygame

from game import audio
from game.render_utils import SCREEN_W, SCREEN_H, ws, COL_BULLET

_positions:  dict = {}   # bid → (wx, wy, owner_id)
_explosions: list = []   # [(wx, wy, spawn_t, owner_id)]

_BOMB_SFX_COUNT          = 2
_BOMB_SFX_INTERVAL_TICKS = 8   # 兩次間隔開來，避免緊貼著疊音

_was_casting:       dict = {}   # pid → bool，上一幀 hunter_bomb_tick 是否 >= 0
_awaiting_first_hit: set = set()  # 這波施放中，還在等第一顆真正爆炸的 owner pid
_pending_plays:     dict = {}   # pid → [(due_tick, volume), ...] 尚未播放的排程


def detect_disappeared(state, now: float, my_id: int = None, player_chars: dict = None) -> None:
    # 偵測新一輪施放：從這一刻起，等第一顆真正炸開才開始播音效（丟出到落地引爆有延遲，不能一丟就播）
    if my_id is not None and player_chars is not None:
        for pid, player in state.players.items():
            if player_chars.get(pid) != 'Hunter':
                continue
            casting = player.hunter_bomb_tick >= 0
            if casting and not _was_casting.get(pid, False):
                _awaiting_first_hit.add(pid)
                volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
                audio.play('movement/hunter_swoosh.wav', volume)
            _was_casting[pid] = casting

    current = {bid for bid, b in state.bullets.items()
               if getattr(b, 'bullet_type', 0) == 5}
    for bid in set(_positions) - current:
        if bid in _positions:
            bx, by, bowner = _positions[bid]
            _explosions.append((bx, by, now, bowner))
            if my_id is not None and bowner in _awaiting_first_hit:
                _awaiting_first_hit.discard(bowner)
                volume = audio.VOLUME_SELF if bowner == my_id else audio.VOLUME_OTHER
                _pending_plays[bowner] = [(state.tick + i * _BOMB_SFX_INTERVAL_TICKS, volume)
                                          for i in range(_BOMB_SFX_COUNT)]
        _positions.pop(bid, None)

    for pid, plays in list(_pending_plays.items()):
        remaining = []
        for due_tick, volume in plays:
            if state.tick >= due_tick:
                audio.play('others/hunter_mini_bomb.wav', volume)
            else:
                remaining.append((due_tick, volume))
        if remaining:
            _pending_plays[pid] = remaining
        else:
            _pending_plays.pop(pid, None)


def track(bullet) -> None:
    _positions[bullet.id] = (bullet.x, bullet.y, bullet.owner_id)


def draw_explosions(screen, cx: float, cy: float) -> None:
    now = time.perf_counter()
    alive = []
    DURATION, MAX_R = 0.4, 65
    for wx, wy, t, owner in _explosions:
        elapsed = now - t
        if elapsed >= DURATION:
            continue
        alive.append((wx, wy, t, owner))
        progress = elapsed / DURATION
        r     = max(1, int(MAX_R * progress))
        alpha = int(200 * (1.0 - progress))
        col   = COL_BULLET.get(owner, (255, 200, 100))
        sx, sy = ws(wx, wy, cx, cy)
        if -MAX_R <= sx <= SCREEN_W + MAX_R and -MAX_R <= sy <= SCREEN_H + MAX_R:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, alpha), (r, r), r)
            screen.blit(surf, (sx - r, sy - r))
    _explosions[:] = alive
