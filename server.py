import socket
import time
import sys

from game.state    import GameState
from game.obstacle import load_map
from network.protocol import (
    PKT_JOIN, PKT_CMD, PKT_CHAR_SELECT,
    pack_joined, pack_state, pack_game_start,
    unpack_command, packet_type,
)


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

    print(f"[Server] Listening on {get_local_ip()}:{PORT}")
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

            # ── 加入 ──────────────────────────────────────────────
            if ptype == PKT_JOIN:
                if addr not in addr_to_id:
                    if len(clients) < MAX_PLAYERS:
                        pid = len(clients) + 1
                        clients[pid]     = addr
                        addr_to_id[addr] = pid
                        state.add_player(pid)
                        sock.sendto(pack_joined(pid), addr)
                        print(f"[Server] Player {pid} joined from {addr}")

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

            # ── 指令（遊戲進行中才處理）──────────────────────────
            elif ptype == PKT_CMD:
                if addr in addr_to_id and game_started:
                    cmd = unpack_command(data)
                    state.apply_command(
                        cmd.player_id,
                        cmd.move_x, cmd.move_y,
                        cmd.shooting, cmd.aim_x, cmd.aim_y,
                        cmd.crouching, cmd.stance,
                    )

        # ── Tick（遊戲進行中才跑）────────────────────────────────
        if game_started:
            now = time.perf_counter()
            if now >= next_tick:
                next_tick += TICK_DT
                state.tick += 1
                state.step_bullets(obstacles, obstacle_hp)
                state.resolve_player_collisions(obstacles)
                state.step_gold_collection()

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
