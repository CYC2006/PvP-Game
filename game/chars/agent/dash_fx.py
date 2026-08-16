from game import audio

_was_dashing: dict = {}   # pid → bool，上一幀 agent_dash_tick 是否 >= 0


def detect(state, my_id: int, player_chars: dict) -> None:
    for pid, player in state.players.items():
        if player_chars.get(pid) != 'Agent':
            continue
        dashing = player.agent_dash_tick >= 0
        if dashing and not _was_dashing.get(pid, False):
            volume = audio.VOLUME_SELF if pid == my_id else audio.VOLUME_OTHER
            audio.play('movement/agent_swoosh.wav', volume)
        _was_dashing[pid] = dashing
