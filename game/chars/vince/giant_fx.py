from game import audio

_was_active: dict = {}   # pid → bool，上一幀 giant_tick 是否 >= 0


def detect_giant_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Vince':
            continue
        active = player.giant_tick >= 0
        if active and not _was_active.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('others/vince_giant.wav', volume)
        _was_active[pid] = active
