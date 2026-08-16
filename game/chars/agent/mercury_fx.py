from game import audio

_was_casting: dict = {}   # pid → bool，上一幀 mercury_start_tick 是否 >= 0


def detect_mercury_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Agent':
            continue
        casting = player.mercury_start_tick >= 0
        if casting and not _was_casting.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('others/agent_mercury_barrage.wav', volume)
        _was_casting[pid] = casting
