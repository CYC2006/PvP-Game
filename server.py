import socket
import time
import sys

from game.state import GameState
from network.protocol import (
    PKT_JOIN, PKT_CMD,
    pack_joined, pack_state,
    unpack_command, packet_type,
)

HOST        = "0.0.0.0"
PORT        = 5000
TICK_RATE   = 60
TICK_DT     = 1.0 / TICK_RATE
MAX_PLAYERS = 2
BUF_SIZE    = 512


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def run():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.setblocking(False)

    state: GameState       = GameState()
    clients: dict[int, tuple]     = {}   # player_id → (ip, port)
    addr_to_id: dict[tuple, int]  = {}

    print(f"[Server] Listening on {get_local_ip()}:{PORT}")
    print(f"[Server] Waiting for {MAX_PLAYERS} players...")

    next_tick = time.perf_counter()

    while True:
        # ── receive all pending packets ───────────────────────────────────
        while True:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
            except BlockingIOError:
                break

            ptype = packet_type(data)

            if ptype == PKT_JOIN:
                if addr not in addr_to_id:
                    if len(clients) < MAX_PLAYERS:
                        pid = len(clients) + 1
                        clients[pid]     = addr
                        addr_to_id[addr] = pid
                        state.add_player(pid)
                        sock.sendto(pack_joined(pid), addr)
                        print(f"[Server] Player {pid} joined from {addr}")
                        if len(clients) == MAX_PLAYERS:
                            print("[Server] Game start!")
                    else:
                        print(f"[Server] Rejected {addr}: server full")

            elif ptype == PKT_CMD:
                if addr in addr_to_id and len(clients) == MAX_PLAYERS:
                    cmd = unpack_command(data)
                    state.apply_command(
                        cmd.player_id,
                        cmd.move_x, cmd.move_y,
                        cmd.shooting, cmd.aim_x, cmd.aim_y,
                    )

        # ── tick ──────────────────────────────────────────────────────────
        now = time.perf_counter()
        if now >= next_tick:
            next_tick += TICK_DT
            state.tick += 1
            state.step_bullets()   # move bullets + resolve hits

            if len(clients) == MAX_PLAYERS:
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
