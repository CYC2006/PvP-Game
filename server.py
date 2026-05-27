import socket
import time
import sys

from game.state    import GameState
from game.obstacle import load_map
from network.protocol import (
    PKT_JOIN, PKT_CMD, PKT_CHAR_SELECT, PKT_QUIT,
    pack_joined, pack_all_joined, pack_state, pack_game_start, pack_game_over,
    unpack_command, packet_type,
)


# ── Skill dispatch tables (char name → callable) ─────────────────────────────
_SKILL_E: dict = {
    'Agent':    lambda s, pid, ax, ay: s._spawn_flash_grenade(pid, ax, ay),
    'Vince':    lambda s, pid, ax, ay: s._spawn_grenade(pid, ax, ay),
    'Assassin': lambda s, pid, ax, ay: s._spawn_smoke_grenade(pid, ax, ay),
    'Hunter':   lambda s, pid, ax, ay: s._activate_log_barriers(pid, ax, ay),
    'Marksman': lambda s, pid, ax, ay: s._place_turret(pid),
    'Pioneer':  lambda s, pid, ax, ay: s._activate_shield(pid),
    'Poisoner': lambda s, pid, ax, ay: s._activate_poisoner_e(pid),
    'Robot':    lambda s, pid, ax, ay: s._activate_robot_e(pid),
}

_SKILL_RMB: dict = {
    'Agent':    lambda s, pid, ax, ay: s._activate_burst(pid, ax, ay),
    'Assassin': lambda s, pid, ax, ay: s._spawn_shuriken(pid, ax, ay),
    'Vince':    lambda s, pid, ax, ay: s._activate_airstrike(pid, ax, ay),
    'Pioneer':  lambda s, pid, ax, ay: s._spawn_stun_bullet(pid, ax, ay),
    'Marksman': lambda s, pid, ax, ay: s._spawn_explosion_bullet(pid, ax, ay),
    'Poisoner': lambda s, pid, ax, ay: s._spawn_pool_bullet(pid, ax, ay),
    'Hunter':   lambda s, pid, ax, ay: s._spawn_air_cannon(pid, ax, ay),
}

_SKILL_SPACE: dict = {
    'Assassin': lambda s, pid, ax, ay: s._activate_speed_boost(pid),
    'Hunter':   lambda s, pid, ax, ay: s._spawn_mini_grenades(pid),
    'Robot':    lambda s, pid, ax, ay: s._activate_robot_space(pid),
    'Pioneer':  lambda s, pid, ax, ay: s._activate_jump(pid, ax, ay),
    'Vince':    lambda s, pid, ax, ay: s._activate_vince_taunt(pid),
    'Marksman': lambda s, pid, ax, ay: s._activate_vince_dash(pid, ax, ay),
    'Zombie':   lambda s, pid, ax, ay: s._activate_zombie_jump(pid, ax, ay),
    'Poisoner': lambda s, pid, ax, ay: s._activate_poisoner_space(pid),
}

_SKILL_R: dict = {
    'Assassin': lambda s, pid, ax, ay: s._activate_r_skill(pid, ax, ay),
    'Vince':    lambda s, pid, ax, ay: s._activate_giant(pid),
    'Robot':    lambda s, pid, ax, ay: s._activate_push_zone(pid, ax, ay),
    'Pioneer':  lambda s, pid, ax, ay: s._activate_clones(pid),
    'Hunter':   lambda s, pid, ax, ay: s._activate_cloak(pid),
    'Marksman': lambda s, pid, ax, ay: s._activate_barrage(pid, ax, ay),
    'Agent':    lambda s, pid, ax, ay: s._activate_mercury_barrage(pid, ax, ay),
}


HOST                = "0.0.0.0"
PORT                = 5000
TICK_RATE           = 60
TICK_DT             = 1.0 / TICK_RATE
MAX_PLAYERS         = 2
BUF_SIZE            = 8192
MAP_PATH            = "maps/map_01.json"
TIMEOUT             = 5.0    # secs without packet during game → pause
PAUSE_RESET_TIMEOUT = 5.0    # secs paused before force-reset  (was 20)
QUEUE_TIMEOUT       = 12.0   # secs without JOIN heartbeat → remove from queue


def run():
    obstacles   = load_map(MAP_PATH)
    obstacle_hp = {oid: obs.hp for oid, obs in obstacles.items()}
    print(f"[Server] Loaded map: {len(obstacles)} obstacles")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.setblocking(False)
    print(f"[Server] Listening on {HOST}:{PORT}")

    # ── Session state ──────────────────────────────────────────────────────
    state: GameState            = GameState()
    clients: dict[int, tuple]   = {}   # pid → addr
    addr_to_id: dict            = {}   # addr → pid
    player_chars: dict          = {}   # pid → char_id
    player_runes: dict          = {}   # pid → rune_id
    game_started: bool          = False
    last_seen: dict[int, float] = {}   # pid → perf_counter time
    paused: bool                = False
    paused_since: float         = 0.0
    next_tick: float            = time.perf_counter()

    # ── Matchmaking queue: addr → timestamp of last PKT_JOIN ──────────────
    waiting: dict               = {}

    # ── Helpers ───────────────────────────────────────────────────────────

    def _broadcast_game_over() -> None:
        for a in list(clients.values()):
            try:
                sock.sendto(pack_game_over(), a)
            except Exception:
                pass

    def _reset_session() -> None:
        nonlocal state, game_started, paused, next_tick
        clients.clear()
        addr_to_id.clear()
        player_chars.clear()
        player_runes.clear()
        last_seen.clear()
        game_started = False
        paused       = False
        state        = GameState()
        obstacle_hp.clear()
        obstacle_hp.update({oid: obs.hp for oid, obs in obstacles.items()})
        next_tick    = time.perf_counter()
        print("[Server] Session reset — waiting for players")

    def _try_match() -> None:
        """Pull players from waiting queue into the current session."""
        while waiting and len(clients) < MAX_PLAYERS:
            addr = next(iter(waiting))   # FIFO: oldest entry first
            del waiting[addr]
            pid              = len(clients) + 1
            clients[pid]     = addr
            addr_to_id[addr] = pid
            state.add_player(pid)
            sock.sendto(pack_joined(pid), addr)
            last_seen[pid] = time.perf_counter()
            print(f"[Server] Player {pid} matched from queue ({addr})")
        if len(clients) == MAX_PLAYERS:
            for a in clients.values():
                sock.sendto(pack_all_joined(), a)
            print("[Server] All players matched — sending PKT_ALL_JOINED")

    # ── Main loop ─────────────────────────────────────────────────────────
    while True:
        now = time.perf_counter()

        # Remove stale waiting entries (no PKT_JOIN heartbeat)
        stale = [a for a, t in waiting.items() if now - t > QUEUE_TIMEOUT]
        for a in stale:
            del waiting[a]
            print(f"[Server] Removed stale queue entry {a}")

        # ── Receive all pending packets ────────────────────────────────
        while True:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
            except BlockingIOError:
                break

            ptype = packet_type(data)

            # Refresh last_seen for in-session players
            if addr in addr_to_id:
                last_seen[addr_to_id[addr]] = time.perf_counter()

            # ── PKT_JOIN ───────────────────────────────────────────────
            if ptype == PKT_JOIN:
                if addr in addr_to_id:
                    # Already in session — resend relevant packet(s)
                    pid = addr_to_id[addr]
                    sock.sendto(pack_joined(pid), addr)
                    if len(clients) == MAX_PLAYERS and not game_started:
                        sock.sendto(pack_all_joined(), addr)
                    elif game_started and player_chars:
                        # Client may have missed PKT_GAME_START (Bug fix #2)
                        sock.sendto(pack_game_start(player_chars), addr)
                else:
                    # Not in session: add / refresh queue entry
                    waiting[addr] = time.perf_counter()
                    if len(clients) < MAX_PLAYERS:
                        _try_match()

            # ── PKT_CHAR_SELECT ────────────────────────────────────────
            elif ptype == PKT_CHAR_SELECT:
                if addr in addr_to_id and len(data) >= 2:
                    if game_started:
                        # Client missed PKT_GAME_START — resend (Bug fix #2)
                        if player_chars:
                            sock.sendto(pack_game_start(player_chars), addr)
                    else:
                        pid     = addr_to_id[addr]
                        char_id = data[1]
                        rune_id = data[2] if len(data) >= 3 else 0
                        player_chars[pid] = char_id
                        player_runes[pid] = rune_id
                        print(f"[Server] Player {pid} selected char {char_id}, rune {rune_id}")

                        if len(player_chars) == MAX_PLAYERS:
                            game_started = True
                            next_tick    = time.perf_counter()
                            from game.char_data import CHAR_ORDER, reload
                            reload()
                            for p_id, c_id in player_chars.items():
                                char_name = CHAR_ORDER[c_id]
                                r_id      = player_runes.get(p_id, 0)
                                state.apply_char_stats(p_id, char_name, r_id)
                                print(f"[Server] Player {p_id} → {char_name}, rune {r_id}")
                            payload = pack_game_start(player_chars)
                            for a in clients.values():
                                try:
                                    sock.sendto(payload, a)
                                except Exception:
                                    pass
                            print("[Server] Both selected — Game start!")

            # ── PKT_QUIT ───────────────────────────────────────────────
            elif ptype == PKT_QUIT:
                if addr in addr_to_id:
                    pid_who = addr_to_id.get(addr, "?")
                    print(f"[Server] Player {pid_who} quit — broadcasting GAME_OVER")
                    _broadcast_game_over()
                    _reset_session()
                    _try_match()   # immediately fill from queue if waiting
                    break          # exit inner recv loop; restart outer loop
                elif addr in waiting:
                    # Waiting player cancelled matchmaking
                    del waiting[addr]
                    print(f"[Server] Waiting player {addr} cancelled queue")

            # ── PKT_CMD ────────────────────────────────────────────────
            elif ptype == PKT_CMD:
                if addr in addr_to_id and game_started:
                    cmd      = unpack_command(data)
                    p        = state.players.get(cmd.player_id)
                    r_active = p and p.r_skill_phase > 0
                    _mercury = p and p.mercury_start_tick >= 0
                    _stunned = p and state.tick < p.stun_until
                    if p and not r_active and not _stunned:
                        pid, ax, ay = cmd.player_id, cmd.aim_x, cmd.aim_y
                        if not _mercury:
                            if cmd.use_skill_e:
                                fn = _SKILL_E.get(p.char_name)
                                if fn:
                                    fn(state, pid, ax, ay)
                            _bursting = p.burst_next_tick >= 0
                            if cmd.use_skill_rmb:
                                fn = _SKILL_RMB.get(p.char_name)
                                if fn:
                                    fn(state, pid, ax, ay)
                            if not _bursting:
                                if cmd.use_skill_space:
                                    fn = _SKILL_SPACE.get(p.char_name)
                                    if fn:
                                        fn(state, pid, ax, ay)
                                if cmd.use_skill_r:
                                    fn = _SKILL_R.get(p.char_name)
                                    if fn:
                                        fn(state, pid, ax, ay)
                        if cmd.use_rune:
                            state._activate_rune(pid)
                    state.apply_command(
                        cmd.player_id,
                        cmd.move_x, cmd.move_y,
                        cmd.shooting, cmd.aim_x, cmd.aim_y,
                        cmd.running, cmd.stance,
                        cmd.speed_mult,
                    )

        # ── Disconnect detection (game only) ──────────────────────────
        if game_started:
            now = time.perf_counter()
            any_dc = any(
                now - last_seen.get(pid, now) > TIMEOUT
                for pid in clients
            )
            if any_dc and not paused:
                paused       = True
                paused_since = now
                dc_pids = [
                    pid for pid in clients
                    if now - last_seen.get(pid, now) > TIMEOUT
                ]
                print(f"[Server] Player {dc_pids} disconnected — game paused")
            elif not any_dc and paused:
                paused = False
                print("[Server] All players reconnected — game resumed")
            elif paused and (now - paused_since) > PAUSE_RESET_TIMEOUT:
                print(f"[Server] Pause timeout ({PAUSE_RESET_TIMEOUT}s) — force resetting")
                _broadcast_game_over()
                _reset_session()
                _try_match()

        # ── Game tick ─────────────────────────────────────────────────
        if game_started and not paused:
            now = time.perf_counter()
            if now >= next_tick:
                if now - next_tick > TICK_DT:
                    next_tick = now - TICK_DT
                next_tick += TICK_DT
                state.tick += 1
                state.step_bullets(obstacles, obstacle_hp)
                state.step_pending_pellets()
                state.step_jumps()
                state.step_zombie_jumps()
                state.step_vince_taunt()
                state.step_vince_dash(obstacles)
                state.resolve_player_collisions(obstacles)
                state.step_gold_collection()
                state.step_status_effects()
                state.step_smoke_patches()
                state.step_blade_arcs()
                state.step_r_skill()
                state.step_air_strikes()
                state.step_giant()
                state.step_burst()
                state.step_mercury_barrage()
                state.step_mines()
                state.step_turrets(obstacles, obstacle_hp)
                state.step_barrage()
                state.step_poison_pools()
                state.step_poisoner_space()
                state.step_poisoner_e()
                state.step_poison_stacks()
                state.step_shields()
                state.step_shockwaves()
                state.step_pull()
                state.step_knockback()
                state.step_push_zones()
                state.step_robot_marks()
                state.step_robot_e()
                state.step_air_cannons()
                state.step_rune_recovery()

                payload = pack_state(state)
                for a in clients.values():
                    try:
                        sock.sendto(payload, a)
                    except Exception:
                        pass

        time.sleep(0.001)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[Server] Stopped.")
        sys.exit(0)
