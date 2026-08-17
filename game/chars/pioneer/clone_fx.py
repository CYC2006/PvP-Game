from game import audio

_was_active: dict = {}   # pid → bool，上一幀 clone_until 是否 > tick


def detect_clone_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Pioneer':
            continue
        active = player.clone_until > state.tick
        if active and not _was_active.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('others/pioneer_clone.wav', volume)
        _was_active[pid] = active
