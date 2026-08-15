import json
import socket
import time
import sys

from game.state    import GameState, configure_map, PORTAL_Y_MIN, PORTAL_Y_MAX, PORTAL_COOLDOWN_TICKS, PLAYER_RADIUS
from game.obstacle import load_map
from network.protocol import (
    PKT_JOIN, PKT_CMD, PKT_CHAR_SELECT, PKT_QUIT, PKT_PING, PKT_PONG,
    pack_joined, pack_all_joined, pack_state, pack_game_start, pack_game_over,
    unpack_command, unpack_join, packet_type,
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
    'Zombie':   lambda s, pid, ax, ay: s._activate_zombie_rage(pid),
}

_SKILL_RMB: dict = {
    'Agent':    lambda s, pid, ax, ay: s._activate_burst(pid, ax, ay),
    'Assassin': lambda s, pid, ax, ay: s._spawn_shuriken(pid, ax, ay),
    'Vince':    lambda s, pid, ax, ay: s._activate_airstrike(pid, ax, ay),
    'Pioneer':  lambda s, pid, ax, ay: s._spawn_stun_bullet(pid, ax, ay),
    'Marksman': lambda s, pid, ax, ay: s._spawn_explosion_bullet(pid, ax, ay),
    'Poisoner': lambda s, pid, ax, ay: s._spawn_pool_bullet(pid, ax, ay),
    'Hunter':   lambda s, pid, ax, ay: s._spawn_air_cannon(pid, ax, ay),
    'Robot':    lambda s, pid, ax, ay: s._activate_robot_overload(pid),
}

_SKILL_SPACE: dict = {
    'Agent':    lambda s, pid, ax, ay: s._activate_agent_dash(pid),
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
    'Zombie':   lambda s, pid, ax, ay: s._activate_zombie_spit(pid, ax, ay),
}


HOST                = "0.0.0.0"
PORT                = 5000
TICK_RATE           = 60
TICK_DT             = 1.0 / TICK_RATE
MAX_PLAYERS         = 2
BUF_SIZE            = 8192
TIMEOUT             = 5.0    # secs without packet during game → pause
PAUSE_RESET_TIMEOUT = 5.0    # secs paused before force-reset
QUEUE_TIMEOUT       = 12.0   # secs without JOIN heartbeat → remove from queue

_MAPS_META_PATH = "maps/maps_meta.json"
_maps_meta: list[dict] = []

def _get_maps_meta() -> list[dict]:
    global _maps_meta
    if not _maps_meta:
        with open(_MAPS_META_PATH, encoding="utf-8") as f:
            _maps_meta = json.load(f)
    return _maps_meta


class RoomState:
    __slots__ = (
        'state', 'clients', 'addr_to_id', 'player_chars', 'player_runes',
        'last_seen', 'obstacle_hp', 'game_started', 'paused', 'paused_since',
        'next_tick', 'waiting', 'portal_cooldowns',
        'map_id', 'obstacles', 'obstacle_hp_template', 'portals', 'map_w', 'map_h',
    )

    def __init__(self, map_id: int, map_data: dict):
        self.map_id                = map_id
        self.obstacles             = map_data["obstacles"]
        self.obstacle_hp_template  = map_data["obstacle_hp_template"]
        self.portals               = map_data["portals"]
        self.map_w                 = map_data["width"]
        self.map_h                 = map_data["height"]
        self.state             = GameState()
        self.clients           = {}
        self.addr_to_id        = {}
        self.player_chars      = {}
        self.player_runes      = {}
        self.last_seen         = {}
        self.obstacle_hp       = dict(self.obstacle_hp_template)
        self.game_started      = False
        self.paused            = False
        self.paused_since      = 0.0
        self.next_tick         = time.perf_counter()
        self.waiting           = {}
        self.portal_cooldowns  = {}


def run(map_id: int = 0):
    meta = _get_maps_meta()

    def _load_map_data(mid: int) -> dict:
        entry = meta[mid] if mid < len(meta) else meta[0]
        obs   = load_map(entry["file"])
        w     = entry.get("width",  1920)
        h     = entry.get("height", 1080)
        print(f"[Server] Loaded map '{entry['id']}' ({w}x{h}): {len(obs)} obstacles")
        return {
            "obstacles":            obs,
            "obstacle_hp_template": {oid: o.hp for oid, o in obs.items()},
            "portals":              entry.get("portals", []),
            "width":                w,
            "height":               h,
        }

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.setblocking(False)
    print(f"[Server] Listening on {HOST}:{PORT}")

    rooms:     dict = {}   # room_code (int) → RoomState
    addr_room: dict = {}   # addr (tuple)    → room_code (int)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _broadcast_game_over(room: RoomState) -> None:
        for a in list(room.clients.values()):
            try:
                sock.sendto(pack_game_over(), a)
            except Exception:
                pass

    def _step_portals(state: GameState, room: RoomState, map_portals: list) -> None:
        """Teleport players that walk into a portal edge."""
        map_w = room.map_w
        for pid, player in state.players.items():
            cd = room.portal_cooldowns.get(pid, 0)
            if cd > 0:
                room.portal_cooldowns[pid] = cd - 1
                continue
            if not (PORTAL_Y_MIN <= player.y <= PORTAL_Y_MAX):
                continue
            if player.x <= PLAYER_RADIUS * 2:
                # Entered left portal → emerge at right
                player.x = map_w - PLAYER_RADIUS * 2 - 4
                room.portal_cooldowns[pid] = PORTAL_COOLDOWN_TICKS
            elif player.x >= map_w - PLAYER_RADIUS * 2:
                # Entered right portal → emerge at left
                player.x = PLAYER_RADIUS * 2 + 4
                room.portal_cooldowns[pid] = PORTAL_COOLDOWN_TICKS

    def _reset_room(room: RoomState) -> None:
        for addr in list(room.addr_to_id.keys()):
            addr_room.pop(addr, None)
        room.clients.clear()
        room.addr_to_id.clear()
        room.player_chars.clear()
        room.player_runes.clear()
        room.last_seen.clear()
        room.game_started  = False
        room.paused        = False
        room.state         = GameState()
        room.obstacle_hp.clear()
        room.obstacle_hp.update(room.obstacle_hp_template)
        configure_map(room.map_w, room.map_h)
        room.next_tick     = time.perf_counter()
        room.portal_cooldowns.clear()
        print("[Server] Room reset — waiting for players")

    def _try_match(room: RoomState) -> None:
        while room.waiting and len(room.clients) < MAX_PLAYERS:
            addr = next(iter(room.waiting))
            del room.waiting[addr]
            pid                   = len(room.clients) + 1
            room.clients[pid]     = addr
            room.addr_to_id[addr] = pid
            room.state.add_player(pid)
            sock.sendto(pack_joined(pid), addr)
            room.last_seen[pid]   = time.perf_counter()
            addr_room[addr]       = _code_for(room)
            print(f"[Server] Player {pid} matched from queue ({addr})")
        if len(room.clients) == MAX_PLAYERS:
            for a in room.clients.values():
                sock.sendto(pack_all_joined(), a)
            print("[Server] All players matched — sending PKT_ALL_JOINED")

    def _code_for(room: RoomState) -> int:
        for code, r in rooms.items():
            if r is room:
                return code
        return 0

    # ── Main loop ─────────────────────────────────────────────────────────────
    while True:
        now = time.perf_counter()

        # ── Receive all pending packets ────────────────────────────────────
        while True:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
            except BlockingIOError:
                break

            ptype = packet_type(data)

            # Refresh last_seen for in-session players
            code = addr_room.get(addr)
            if code is not None:
                room = rooms.get(code)
                if room and addr in room.addr_to_id:
                    room.last_seen[room.addr_to_id[addr]] = time.perf_counter()

            # ── PKT_PING ──────────────────────────────────────────────────
            if ptype == PKT_PING:
                sock.sendto(bytes([PKT_PONG]), addr)
                continue

            # ── PKT_JOIN ──────────────────────────────────────────────────
            if ptype == PKT_JOIN:
                join_code, join_map_id = unpack_join(data)
                room = rooms.get(join_code)

                if room and addr in room.addr_to_id:
                    # Already in session — resend relevant packet(s)
                    pid = room.addr_to_id[addr]
                    sock.sendto(pack_joined(pid), addr)
                    if len(room.clients) == MAX_PLAYERS and not room.game_started:
                        sock.sendto(pack_all_joined(), addr)
                    elif room.game_started and room.player_chars:
                        sock.sendto(pack_game_start(room.player_chars, room.map_id), addr)
                else:
                    if room is None:
                        # First player to join a room is treated as host — their map_id wins
                        room = RoomState(join_map_id, _load_map_data(join_map_id))
                        configure_map(room.map_w, room.map_h)
                        rooms[join_code] = room
                    room.waiting[addr] = time.perf_counter()
                    addr_room[addr]    = join_code
                    if len(room.clients) < MAX_PLAYERS:
                        _try_match(room)

            # ── PKT_CHAR_SELECT ───────────────────────────────────────────
            elif ptype == PKT_CHAR_SELECT:
                code = addr_room.get(addr)
                if code is None:
                    continue
                room = rooms.get(code)
                if not room or addr not in room.addr_to_id or len(data) < 2:
                    continue
                if room.game_started:
                    if room.player_chars:
                        sock.sendto(pack_game_start(room.player_chars, room.map_id), addr)
                else:
                    pid     = room.addr_to_id[addr]
                    char_id = data[1]
                    rune_id = data[2] if len(data) >= 3 else 0
                    room.player_chars[pid] = char_id
                    room.player_runes[pid] = rune_id
                    print(f"[Server] Player {pid} selected char {char_id}, rune {rune_id}")

                    if len(room.player_chars) == MAX_PLAYERS:
                        room.game_started = True
                        room.next_tick    = time.perf_counter()
                        from game.char_data import CHAR_ORDER, reload
                        reload()
                        for p_id, c_id in room.player_chars.items():
                            char_name = CHAR_ORDER[c_id]
                            r_id      = room.player_runes.get(p_id, 0)
                            room.state.apply_char_stats(p_id, char_name, r_id)
                            print(f"[Server] Player {p_id} → {char_name}, rune {r_id}")
                        payload = pack_game_start(room.player_chars, room.map_id)
                        for a in room.clients.values():
                            try:
                                sock.sendto(payload, a)
                            except Exception:
                                pass
                        print("[Server] Both selected — Game start!")

            # ── PKT_QUIT ──────────────────────────────────────────────────
            elif ptype == PKT_QUIT:
                code = addr_room.get(addr)
                if code is None:
                    continue
                room = rooms.get(code)
                if not room:
                    continue
                if addr in room.addr_to_id:
                    pid_who = room.addr_to_id.get(addr, "?")
                    print(f"[Server] Player {pid_who} quit — broadcasting GAME_OVER")
                    _broadcast_game_over(room)
                    _reset_room(room)
                    _try_match(room)
                    if not room.clients and not room.waiting:
                        rooms.pop(code, None)
                    break   # restart outer loop
                elif addr in room.waiting:
                    del room.waiting[addr]
                    addr_room.pop(addr, None)
                    if not room.clients and not room.waiting:
                        rooms.pop(code, None)
                    print(f"[Server] Waiting player {addr} cancelled queue")

            # ── PKT_CMD ───────────────────────────────────────────────────
            elif ptype == PKT_CMD:
                code = addr_room.get(addr)
                if code is None:
                    continue
                room = rooms.get(code)
                if not room or addr not in room.addr_to_id or not room.game_started:
                    continue
                try:
                    cmd      = unpack_command(data)
                    p        = room.state.players.get(cmd.player_id)
                    r_active = p and p.r_skill_phase > 0
                    _mercury = p and p.mercury_start_tick >= 0
                    _zombie_spit = p and p.zombie_spit_tick >= 0
                    _stunned = p and room.state.tick < p.stun_until
                    if p and not r_active and not _stunned:
                        pid, ax, ay = cmd.player_id, cmd.aim_x, cmd.aim_y
                        if not _mercury and not _zombie_spit:
                            if cmd.use_skill_e:
                                fn = _SKILL_E.get(p.char_name)
                                if fn:
                                    fn(room.state, pid, ax, ay)
                            _bursting = p.burst_next_tick >= 0
                            if cmd.use_skill_rmb:
                                fn = _SKILL_RMB.get(p.char_name)
                                if fn:
                                    fn(room.state, pid, ax, ay)
                            if not _bursting:
                                if cmd.use_skill_space:
                                    fn = _SKILL_SPACE.get(p.char_name)
                                    if fn:
                                        fn(room.state, pid, ax, ay)
                                if cmd.use_skill_r:
                                    fn = _SKILL_R.get(p.char_name)
                                    if fn:
                                        fn(room.state, pid, ax, ay)
                        if cmd.use_rune:
                            room.state._activate_rune(pid)
                    room.state.apply_command(
                        cmd.player_id,
                        cmd.move_x, cmd.move_y,
                        cmd.shooting, cmd.aim_x, cmd.aim_y,
                        cmd.running, cmd.stance,
                        cmd.speed_mult,
                    )
                except Exception as cmd_err:
                    import traceback
                    print(f"[Server] CMD ERROR room {code}: {cmd_err}")
                    traceback.print_exc()
                    _broadcast_game_over(room)
                    _reset_room(room)
                    _try_match(room)
                    if not room.clients and not room.waiting:
                        rooms.pop(code, None)
                    break   # restart outer loop（room 已重置，addr_room 對應已清除）

        # ── Per-room disconnect detection + game tick ──────────────────────
        now = time.perf_counter()
        empty_codes = []

        for code, room in list(rooms.items()):

            # Remove stale waiting entries
            stale = [a for a, t in room.waiting.items()
                     if now - t > QUEUE_TIMEOUT]
            for a in stale:
                del room.waiting[a]
                addr_room.pop(a, None)
                print(f"[Server] Removed stale queue entry {a} (room {code})")

            if len(room.clients) == MAX_PLAYERS:
                any_dc = any(
                    now - room.last_seen.get(pid, now) > TIMEOUT
                    for pid in room.clients
                )

                if not room.game_started:
                    if any_dc:
                        dc_pids = [pid for pid in room.clients
                                   if now - room.last_seen.get(pid, now) > TIMEOUT]
                        print(f"[Server] Player {dc_pids} disconnected during char select"
                              f" (room {code}) — resetting")
                        _broadcast_game_over(room)
                        _reset_room(room)
                        _try_match(room)
                else:
                    if any_dc and not room.paused:
                        room.paused       = True
                        room.paused_since = now
                        dc_pids = [pid for pid in room.clients
                                   if now - room.last_seen.get(pid, now) > TIMEOUT]
                        print(f"[Server] Player {dc_pids} disconnected (room {code})"
                              f" — game paused")
                    elif not any_dc and room.paused:
                        room.paused = False
                        print(f"[Server] All players reconnected (room {code})"
                              f" — game resumed")
                    elif room.paused and (now - room.paused_since) > PAUSE_RESET_TIMEOUT:
                        print(f"[Server] Pause timeout (room {code}) — force resetting")
                        _broadcast_game_over(room)
                        _reset_room(room)
                        _try_match(room)

            # Game tick
            if room.game_started and not room.paused:
                if now >= room.next_tick:
                    if now - room.next_tick > TICK_DT:
                        room.next_tick = now - TICK_DT
                    room.next_tick += TICK_DT
                    try:
                        s = room.state
                        s.tick += 1
                        s.step_bullets(room.obstacles, room.obstacle_hp)
                        s.step_pending_pellets()
                        s.step_jumps()
                        s.step_zombie_jumps()
                        s.step_zombie_spit()
                        s.step_zombie_rage()
                        s.step_vince_taunt()
                        s.step_vince_dash(room.obstacles)
                        s.step_agent_dash()
                        s.resolve_player_collisions(room.obstacles)
                        s.step_gold_collection()
                        s.step_status_effects()
                        s.step_smoke_patches()
                        s.step_blade_arcs(room.obstacles, room.obstacle_hp)
                        s.step_r_skill()
                        s.step_air_strikes()
                        s.step_giant()
                        s.step_burst()
                        s.step_mercury_barrage()
                        s.step_mines()
                        s.step_turrets(room.obstacles, room.obstacle_hp)
                        s.step_barrage()
                        s.step_poison_pools()
                        s.step_poisoner_space()
                        s.step_poisoner_e()
                        s.step_poison_stacks()
                        s.step_shields()
                        s.step_shockwaves()
                        s.step_pull()
                        s.step_knockback()
                        s.step_push_zones()
                        s.step_robot_marks()
                        s.step_robot_e()
                        s.step_robot_auto_attack()
                        s.step_air_cannons()
                        s.step_rune_recovery()

                        # Portal teleportation (Portal map only)
                        if room.portals:
                            _step_portals(s, room, room.portals)

                        payload = pack_state(s)
                        for a in room.clients.values():
                            try:
                                sock.sendto(payload, a)
                            except Exception:
                                pass
                    except Exception as tick_err:
                        import traceback
                        print(f"[Server] TICK ERROR room {code} tick {room.state.tick}: {tick_err}")
                        traceback.print_exc()
                        _broadcast_game_over(room)
                        _reset_room(room)

            if not room.clients and not room.waiting:
                empty_codes.append(code)

        for code in empty_codes:
            rooms.pop(code, None)

        time.sleep(0.001)


if __name__ == "__main__":
    while True:
        try:
            run()
        except KeyboardInterrupt:
            print("\n[Server] Stopped.")
            sys.exit(0)
        except Exception as e:
            import traceback
            print(f"[Server] FATAL: {e}")
            traceback.print_exc()
            print("[Server] Restarting in 2s...")
            time.sleep(2)
