import math

import pygame

from game import audio
from game.render_utils import SCREEN_W, SCREEN_H, ws
from game.state import PLAYER_RADIUS

_SMOKE_FULL = 360   # 與 smoke_state.SMOKE_DURATION 一致
_SMOKE_FADE = 60

_SFX_DELAY_TICKS = 72   # 1.2s × 60fps：從煙霧彈施放到真正「變成煙霧」的預估時間差

_was_casting: dict = {}   # pid → bool，上一幀 assassin_smoke_tick 是否 >= 0
_sfx_due_tick: dict = {}  # pid → 排定播放音效的 tick（None = 沒有排程中）


def detect_smoke_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Assassin':
            continue
        casting = player.assassin_smoke_tick >= 0
        if casting and not _was_casting.get(pid, False):
            _sfx_due_tick[pid] = state.tick + _SFX_DELAY_TICKS
        _was_casting[pid] = casting

        due = _sfx_due_tick.get(pid)
        if due is not None and state.tick >= due:
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('others/assassin_smoke.wav', volume)
            _sfx_due_tick[pid] = None


def is_hidden_by_smoke(opponent, local_player, state) -> bool:
    """對手在煙霧中且本地玩家不在同一煙霧內時回傳 True（對手不可見）。"""
    for patch in state.smoke_patches.values():
        if state.tick - patch.spawn_tick >= _SMOKE_FULL:
            continue
        if math.hypot(opponent.x - patch.x, opponent.y - patch.y) > patch.radius:
            continue
        if math.hypot(local_player.x - patch.x, local_player.y - patch.y) <= patch.radius:
            continue
        return True
    return False


def draw_patches(screen, state, cx: float, cy: float, my_id: int) -> None:
    """繪製煙霧區域。本地玩家在內部時半透明，外部時不透明遮蔽。"""
    me = state.players.get(my_id)
    for patch in state.smoke_patches.values():
        age = state.tick - patch.spawn_tick
        if age >= _SMOKE_FULL + _SMOKE_FADE:
            continue
        base_alpha = 220 if age < _SMOKE_FULL else int(220 * (1.0 - (age - _SMOKE_FULL) / _SMOKE_FADE))
        if base_alpha <= 0:
            continue
        my_inside = (me and math.hypot(me.x - patch.x, me.y - patch.y) <= patch.radius)
        alpha = 70 if my_inside else base_alpha
        r  = int(patch.radius)
        sx, sy = ws(patch.x, patch.y, cx, cy)
        if sx < -r or sx > SCREEN_W + r or sy < -r or sy > SCREEN_H + r:
            continue
        surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 255, alpha), (r + 1, r + 1), r)
        screen.blit(surf, (sx - r - 1, sy - r - 1))
