from game import audio

_was_jumping: dict = {}   # pid → bool，上一幀 jump_tick 是否 >= 0


def detect_jump_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Pioneer':
            continue
        jumping = player.jump_tick >= 0
        if jumping and not _was_jumping.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('movement/pioneer_jump.wav', volume)
        _was_jumping[pid] = jumping
