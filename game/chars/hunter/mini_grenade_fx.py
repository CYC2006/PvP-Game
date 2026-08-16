import time

import pygame

from game import audio
from game.render_utils import SCREEN_W, SCREEN_H, ws, COL_BULLET

_positions:  dict = {}   # bid → (wx, wy, owner_id)
_explosions: list = []   # [(wx, wy, spawn_t, owner_id)]

_BOMB_SFX_COUNT         = 3
_BOMB_SFX_INTERVAL_TICKS = 8   # 播三次、間隔開來，避免 5-6 顆各自爆炸時疊在一起很雜

_was_casting:   dict = {}   # pid → bool，上一幀 hunter_bomb_tick 是否 >= 0
_pending_plays: dict = {}   # pid → [(due_tick, volume), ...] 尚未播放的排程


def detect_disappeared(state, now: float) -> None:
    current = {bid for bid, b in state.bullets.items()
               if getattr(b, 'bullet_type', 0) == 5}
    for bid in set(_positions) - current:
        if bid in _positions:
            bx, by, bowner = _positions[bid]
            _explosions.append((bx, by, now, bowner))
        _positions.pop(bid, None)


def detect_bomb_sfx(state, my_id: int, player_chars: dict) -> None:
    """丟出手雷的瞬間排程固定 3 次音效播放，不跟著每顆實際爆炸觸發（顆數不固定、時間點太密集會疊音）。"""
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Hunter':
            continue
        casting = player.hunter_bomb_tick >= 0
        if casting and not _was_casting.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            _pending_plays[pid] = [(state.tick + i * _BOMB_SFX_INTERVAL_TICKS, volume)
                                    for i in range(_BOMB_SFX_COUNT)]
        _was_casting[pid] = casting

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
