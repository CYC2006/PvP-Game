import math
import socket
import sys
import time
import pygame

from game.input      import read_input
from game.renderer   import draw, LOGICAL_W, LOGICAL_H
from game.state      import GameState
from game.obstacle   import load_map
import game.charselect as charselect
from network.protocol import (
    PKT_JOINED, PKT_STATE, PKT_GAME_START,
    pack_join, pack_command, pack_char_select,
    unpack_joined, unpack_state, unpack_game_start,
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


def char_select_loop(sock, server_addr, screen, logical_surf,
                     font_lg, font_sm, clock) -> tuple:
    """
    選角畫面主迴圈（carousel 版）。
    回傳 (player_chars_dict, my_char_key)，或 (None, None) 表示玩家關閉視窗。
    player_chars_dict: {pid: char_key}  由 PKT_GAME_START 解析
    """
    charselect.reset()
    my_ready       = False
    opponent_ready = False
    last_time      = pygame.time.get_ticks()

    while True:
        now = pygame.time.get_ticks()
        dt  = (now - last_time) / 1000.0
        last_time = now

        # ── 事件 ──────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None, None
            if not my_ready:
                confirmed = charselect.handle_event(event)
                if confirmed:
                    my_ready = True
                    charselect.set_waiting(True)
                    idx = charselect.selected_idx()
                    sock.sendto(pack_char_select(idx), server_addr)
                    print(f"[Client] Selected char {idx} ({charselect.selected_char()['name']})")

        # ── 收封包 ────────────────────────────────────────────────
        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                ptype = packet_type(data)
                if ptype == PKT_GAME_START:
                    # 解析雙方角色 id → char_key
                    raw_chars = unpack_game_start(data)   # {pid: char_id}
                    from game.charselect import CHARACTERS
                    player_chars = {pid: CHARACTERS[cid]["char_key"]
                                    for pid, cid in raw_chars.items()
                                    if 0 <= cid < len(CHARACTERS)}
                    my_char_key = charselect.selected_char()["char_key"]
                    return player_chars, my_char_key
            except (BlockingIOError, ConnectionResetError, OSError):
                break

        # ── 更新 & 繪製 ───────────────────────────────────────────
        charselect.update(dt)

        sw, sh = screen.get_size()
        scaled_w, scaled_h, off_x, off_y, _ = get_viewport(sw, sh)

        charselect.draw_char_select(logical_surf, font_lg, font_sm,
                                    my_ready, opponent_ready)
        screen.fill((0, 0, 0))
        scaled = pygame.transform.scale(logical_surf, (scaled_w, scaled_h))
        screen.blit(scaled, (off_x, off_y))
        pygame.display.flip()
        clock.tick(FPS)


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
    font_lg      = pygame.font.SysFont("monospace", 22, bold=True)
    font_sm      = pygame.font.SysFont("monospace", 15)
    clock        = pygame.time.Clock()
    logical_surf = pygame.Surface((LOGICAL_W, LOGICAL_H))

    # ── 選角畫面 ──────────────────────────────────────────────────
    player_chars, my_char_key = char_select_loop(
        sock, server_addr, screen, logical_surf, font_lg, font_sm, clock)
    if player_chars is None:
        pygame.quit()
        sock.close()
        return

    print(f"[Client] Game start! My char: {my_char_key}  All chars: {player_chars}")

    # 依選擇角色設定射速 / 彈夾 / 換彈
    from game.input import init_char
    init_char(my_char_key)

    # ── 遊戲主迴圈 ────────────────────────────────────────────────
    state      = GameState()
    keys_held: set = set()
    fullscreen = False
    stance     = "stand"

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

        draw(logical_surf, state, player_id, font_sm, obstacles,
             effective_stance, aim_angle_deg, ammo, is_reloading,
             player_chars)

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
