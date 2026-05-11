import math
import socket
import sys
import time
import pygame

from game.input    import read_input
from game.renderer import draw, LOGICAL_W, LOGICAL_H
from game.state    import GameState
from game.obstacle import load_map
from network.protocol import (
    PKT_JOINED, PKT_STATE,
    pack_join, pack_command,
    unpack_joined, unpack_state,
    packet_type,
)

PORT                = 5000
BUF_SIZE            = 1024
FPS                 = 60
JOIN_RETRY_INTERVAL = 1.0
MAP_PATH            = "maps/map_01.json"


def connect(sock: socket.socket, server_addr: tuple) -> int:
    print(f"[Client] Connecting to {server_addr[0]}:{server_addr[1]} ...")
    last_sent = 0.0
    while True:
        now = time.perf_counter()
        if now - last_sent >= JOIN_RETRY_INTERVAL:
            sock.sendto(pack_join(), server_addr)
            last_sent = now
        try:
            data, _ = sock.recvfrom(BUF_SIZE)
            if packet_type(data) == PKT_JOINED:
                pid = unpack_joined(data)
                print(f"[Client] Joined as Player {pid}")
                return pid
        except (BlockingIOError, ConnectionResetError, OSError):
            pass
        time.sleep(0.05)


def get_viewport(screen_w: int, screen_h: int) -> tuple:
    scale    = min(screen_w / LOGICAL_W, screen_h / LOGICAL_H)
    scaled_w = int(LOGICAL_W * scale)
    scaled_h = int(LOGICAL_H * scale)
    off_x    = (screen_w - scaled_w) // 2
    off_y    = (screen_h - scaled_h) // 2
    return scaled_w, scaled_h, off_x, off_y, scale


def screen_to_logical(sx: int, sy: int,
                       off_x: int, off_y: int, scale: float) -> tuple:
    return int((sx - off_x) / scale), int((sy - off_y) / scale)


def run(server_ip: str) -> None:
    server_addr = (server_ip, PORT)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)

    player_id = connect(sock, server_addr)

    # 載入地圖（與 server 相同的 JSON）
    obstacles = load_map(MAP_PATH)

    pygame.init()
    pygame.mouse.set_visible(True)
    screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE)
    pygame.display.set_caption(f"PvP Game — Player {player_id}")
    font       = pygame.font.SysFont("monospace", 15)
    clock      = pygame.time.Clock()
    logical_surf = pygame.Surface((LOGICAL_W, LOGICAL_H))

    state      = GameState()
    keys_held: set = set()
    fullscreen = False
    stance     = "stand"   # "stand" | "machine"（E 鍵切換）

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE)
                elif event.key == pygame.K_e:
                    stance = "machine" if stance == "stand" else "stand"
                keys_held.add(event.key)
            elif event.type == pygame.KEYUP:
                keys_held.discard(event.key)

        sw, sh = screen.get_size()
        scaled_w, scaled_h, off_x, off_y, scale = get_viewport(sw, sh)
        raw_mx, raw_my = pygame.mouse.get_pos()
        logical_mouse  = screen_to_logical(raw_mx, raw_my, off_x, off_y, scale)

        shift_held = (pygame.K_LSHIFT in keys_held or pygame.K_RSHIFT in keys_held)
        cmd, effective_stance, ammo, is_reloading = read_input(
            player_id, keys_held, logical_mouse, stance, shift_held)
        # aim_angle: 0° = 上, 90° = 右（用於旋轉 sprite）
        aim_angle_deg = math.degrees(math.atan2(cmd.aim_x, -cmd.aim_y))
        try:
            sock.sendto(pack_command(cmd), server_addr)
        except Exception:
            pass

        latest = None
        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                if packet_type(data) == PKT_STATE:
                    latest = data
            except (BlockingIOError, ConnectionResetError, OSError):
                break
        if latest:
            state = unpack_state(latest)

        draw(logical_surf, state, player_id, font, obstacles,
             effective_stance, aim_angle_deg, ammo, is_reloading)

        screen.fill((0, 0, 0))
        scaled = pygame.transform.scale(logical_surf, (scaled_w, scaled_h))
        screen.blit(scaled, (off_x, off_y))
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sock.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        server_ip = input("Server IP: ").strip()
    else:
        server_ip = sys.argv[1]

    try:
        run(server_ip)
    except KeyboardInterrupt:
        print("\n[Client] Disconnected.")
        sys.exit(0)
