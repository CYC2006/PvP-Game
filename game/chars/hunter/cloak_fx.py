from game import audio

_was_active: dict = {}   # pid → bool，上一幀 cloak_until 是否 > tick


def detect_cloak_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Hunter':
            continue
        active = player.cloak_until > state.tick
        if active and not _was_active.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('others/hunter_phantom_cloak.wav', volume)
        _was_active[pid] = active
