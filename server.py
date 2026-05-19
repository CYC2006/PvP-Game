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


# ── 技能 dispatch 表（char_key → callable(state, pid, aim_x, aim_y)）────────
# 新增角色時只需在對應欄位加一行，不用改動 run() 本體
_SKILL_E: dict = {
    'hitman1':  lambda s, pid, ax, ay: s._spawn_flash_grenade(pid, ax, ay),
    'manBlue':  lambda s, pid, ax, ay: s._spawn_grenade(pid, ax, ay),
    'survivor1': lambda s, pid, ax, ay: s._spawn_smoke_grenade(pid, ax, ay),
    'manOld':   lambda s, pid, ax, ay: s._activate_log_barriers(pid, ax, ay),
    'manBrown': lambda s, pid, ax, ay: s._place_turret(pid),
}

_SKILL_RMB: dict = {
    'hitman1':   lambda s, pid, ax, ay: s._activate_burst(pid, ax, ay),
    'survivor1': lambda s, pid, ax, ay: s._spawn_shuriken(pid, ax, ay),
    'manBlue':   lambda s, pid, ax, ay: s._activate_airstrike(pid, ax, ay),
    'soldier1':  lambda s, pid, ax, ay: s._spawn_stun_bullet(pid, ax, ay),
    'manBrown':  lambda s, pid, ax, ay: s._spawn_explosion_bullet(pid, ax, ay),
    'womanGreen': lambda s, pid, ax, ay: s._spawn_pool_bullet(pid, ax, ay),
}

_SKILL_SPACE: dict = {
    'survivor1': lambda s, pid, ax, ay: s._activate_speed_boost(pid),
    'manOld':    lambda s, pid, ax, ay: s._spawn_mini_grenades(pid),
    'robot1':    lambda s, pid, ax, ay: s._activate_robot_space(pid),
    'soldier1':  lambda s, pid, ax, ay: s._activate_jump(pid, ax, ay),
}

_SKILL_R: dict = {
    'survivor1': lambda s, pid, ax, ay: s._activate_r_skill(pid, ax, ay),
    'manBlue':   lambda s, pid, ax, ay: s._activate_giant(pid),
    'robot1':    lambda s, pid, ax, ay: s._activate_push_zone(pid, ax, ay),
    'soldier1':  lambda s, pid, ax, ay: s._activate_clones(pid),
    'manOld':    lambda s, pid, ax, ay: s._activate_cloak(pid),
    'manBrown':  lambda s, pid, ax, ay: s._activate_barrage(pid, ax, ay),
}


HOST        = "0.0.0.0"
PORT        = 5000
TICK_RATE   = 60
TICK_DT     = 1.0 / TICK_RATE
MAX_PLAYERS = 2
BUF_SIZE    = 1024
MAP_PATH    = "maps/map_01.json"


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def get_public_ip() -> str:
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=3) as r:
            return r.read().decode().strip()
    except Exception:
        return "unavailable"


def run():
    # 載入地圖
    obstacles   = load_map(MAP_PATH)
    obstacle_hp = {oid: obs.hp for oid, obs in obstacles.items()}
    print(f"[Server] Loaded map: {len(obstacles)} obstacles")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.setblocking(False)

    state: GameState          = GameState()
    clients: dict[int, tuple] = {}   # pid → addr
    addr_to_id: dict          = {}   # addr → pid
    player_chars: dict        = {}   # pid → char_id（選角完成後才有）
    game_started: bool        = False
    last_seen: dict[int, float] = {}  # pid → 最後收到封包的時間
    paused: bool              = False
    TIMEOUT                   = 3.0   # 超過幾秒沒收到封包視為斷線

    import threading
    _pub = ["fetching..."]
    def _fetch():
        _pub[0] = get_public_ip()
        print(f"[Server] Public IP : {_pub[0]}:{PORT}")
    threading.Thread(target=_fetch, daemon=True).start()

    print(f"[Server] Local  IP : {get_local_ip()}:{PORT}")
    print(f"[Server] Waiting for {MAX_PLAYERS} players...")

    next_tick = time.perf_counter()

    while True:
        # ── 收封包 ────────────────────────────────────────────────
        while True:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
            except BlockingIOError:
                break

            ptype = packet_type(data)

            # ── 更新最後收到封包時間 ──────────────────────────────
            if addr in addr_to_id:
                last_seen[addr_to_id[addr]] = time.perf_counter()

            # ── 加入 ──────────────────────────────────────────────
            if ptype == PKT_JOIN:
                if addr not in addr_to_id:
                    if len(clients) < MAX_PLAYERS:
                        pid = len(clients) + 1
                        clients[pid]     = addr
                        addr_to_id[addr] = pid
                        state.add_player(pid)
                        sock.sendto(pack_joined(pid), addr)
                        last_seen[pid] = time.perf_counter()
                        print(f"[Server] Player {pid} joined from {addr}")
                        if len(clients) == MAX_PLAYERS:
                            for a in clients.values():
                                sock.sendto(pack_all_joined(), a)
                            print("[Server] All players joined — sending PKT_ALL_JOINED")

            # ── 選角 ──────────────────────────────────────────────
            elif ptype == PKT_CHAR_SELECT:
                if addr in addr_to_id and not game_started and len(data) >= 2:
                    pid     = addr_to_id[addr]
                    char_id = data[1]
                    player_chars[pid] = char_id
                    print(f"[Server] Player {pid} selected char {char_id}")

                    # 雙方都選完 → 套用角色數值 → 開始遊戲
                    if len(player_chars) == MAX_PLAYERS:
                        game_started = True
                        from game.char_data import CHAR_ORDER, reload
                        reload()   # 每局開始重新讀取 chars.csv
                        for p_id, c_id in player_chars.items():
                            char_key = CHAR_ORDER[c_id]
                            state.apply_char_stats(p_id, char_key)
                            print(f"[Server] Player {p_id} → {char_key}")
                        payload = pack_game_start(player_chars)
                        for a in clients.values():
                            try:
                                sock.sendto(payload, a)
                            except Exception:
                                pass
                        print("[Server] Both selected — Game start!")

            # ── 主動離場：重置 session，廣播 GAME_OVER ───────────
            elif ptype == PKT_QUIT:
                pid_who = addr_to_id.get(addr, "?")
                print(f"[Server] Player {pid_who} quit — broadcasting GAME_OVER and resetting session")
                for a in list(clients.values()):
                    try:
                        sock.sendto(pack_game_over(), a)
                    except Exception:
                        pass
                clients.clear()
                addr_to_id.clear()
                player_chars.clear()
                last_seen.clear()
                game_started = False
                paused       = False
                state        = GameState()
                obstacle_hp.clear()
                obstacle_hp.update({oid: obs.hp for oid, obs in obstacles.items()})
                next_tick = time.perf_counter()
                print("[Server] Session reset — waiting for new players")
                break   # 跳出本輪封包迴圈，回到外層 while True 繼續等待

            # ── 指令（遊戲進行中才處理）──────────────────────────
            elif ptype == PKT_CMD:
                if addr in addr_to_id and game_started:
                    cmd = unpack_command(data)
                    # 技能觸發（依 dispatch 表查角色 char_key）
                    p        = state.players.get(cmd.player_id)
                    r_active = p and p.r_skill_phase > 0
                    if p and not r_active:
                        pid, ax, ay = cmd.player_id, cmd.aim_x, cmd.aim_y
                        if cmd.use_skill_e:
                            fn = _SKILL_E.get(p.char_key)
                            if fn:
                                fn(state, pid, ax, ay)
                        _bursting = p.burst_next_tick >= 0
                        if cmd.use_skill_rmb:
                            fn = _SKILL_RMB.get(p.char_key)
                            if fn:
                                fn(state, pid, ax, ay)
                        if not _bursting:
                            if cmd.use_skill_space:
                                fn = _SKILL_SPACE.get(p.char_key)
                                if fn:
                                    fn(state, pid, ax, ay)
                            if cmd.use_skill_r:
                                fn = _SKILL_R.get(p.char_key)
                                if fn:
                                    fn(state, pid, ax, ay)
                    state.apply_command(
                        cmd.player_id,
                        cmd.move_x, cmd.move_y,
                        cmd.shooting, cmd.aim_x, cmd.aim_y,
                        cmd.running, cmd.stance,
                        cmd.speed_mult,
                    )

        # ── 斷線偵測（遊戲中才檢查）─────────────────────────────
        if game_started:
            now = time.perf_counter()
            any_disconnected = any(
                now - last_seen.get(pid, now) > TIMEOUT
                for pid in clients
            )
            if any_disconnected and not paused:
                paused = True
                disconnected = [
                    pid for pid in clients
                    if now - last_seen.get(pid, now) > TIMEOUT
                ]
                print(f"[Server] Player {disconnected} disconnected — game paused")
            elif not any_disconnected and paused:
                paused = False
                print("[Server] All players reconnected — game resumed")

        # ── Tick（遊戲進行中且未暫停才跑）───────────────────────
        if game_started and not paused:
            now = time.perf_counter()
            if now >= next_tick:
                next_tick += TICK_DT
                state.tick += 1
                state.step_bullets(obstacles, obstacle_hp)
                state.step_pending_pellets()
                state.step_jumps()
                state.resolve_player_collisions(obstacles)
                state.step_gold_collection()
                state.step_status_effects()
                state.step_smoke_patches()
                state.step_blade_arcs()
                state.step_r_skill()
                state.step_air_strikes()
                state.step_giant()
                state.step_burst()
                state.step_mines()
                state.step_turrets(obstacles, obstacle_hp)
                state.step_barrage()
                state.step_poison_pools()
                state.step_knockback()
                state.step_push_zones()
                state.step_robot_marks()

                payload = pack_state(state)
                for addr in clients.values():
                    try:
                        sock.sendto(payload, addr)
                    except Exception:
                        pass

        time.sleep(0.001)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[Server] Stopped.")
        sys.exit(0)
