from game import audio

_was_active: dict = {}   # pid → bool，上一幀 speed_boost_ticks 是否 > 0


def detect_speed_sfx(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Assassin':
            continue
        active = player.speed_boost_ticks > 0
        if active and not _was_active.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('movement/assassin_speed_surge.wav', volume)
        _was_active[pid] = active
