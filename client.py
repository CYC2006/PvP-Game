import socket
import sys
import time
import pygame

from game.input    import read_input
from game.renderer import draw, LOGICAL_W, LOGICAL_H
from game.state    import GameState
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
        except BlockingIOError:
            pass
        time.sleep(0.05)


def get_viewport(screen_w: int, screen_h: int) -> tuple:
    """
    計算在實際螢幕上，等比例放大邏輯畫面的位置與尺寸。
    回傳 (scaled_w, scaled_h, offset_x, offset_y, scale)
    """
    scale     = min(screen_w / LOGICAL_W, screen_h / LOGICAL_H)
    scaled_w  = int(LOGICAL_W * scale)
    scaled_h  = int(LOGICAL_H * scale)
    offset_x  = (screen_w - scaled_w) // 2
    offset_y  = (screen_h - scaled_h) // 2
    return scaled_w, scaled_h, offset_x, offset_y, scale


def screen_to_logical(sx: int, sy: int,
                      offset_x: int, offset_y: int, scale: float) -> tuple:
    """螢幕座標 → 邏輯畫布座標"""
    lx = int((sx - offset_x) / scale)
    ly = int((sy - offset_y) / scale)
    return lx, ly


def run(server_ip: str) -> None:
    server_addr = (server_ip, PORT)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)

    player_id = connect(sock, server_addr)

    pygame.init()
    pygame.mouse.set_visible(True)

    # 起始為視窗模式（邏輯解析度）
    screen     = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE)
    fullscreen = False
    pygame.display.set_caption(f"PvP Game — Player {player_id}")
    font  = pygame.font.SysFont("monospace", 15)
    clock = pygame.time.Clock()

    # 邏輯畫布：所有遊戲繪圖都在這裡
    logical_surf = pygame.Surface((LOGICAL_W, LOGICAL_H))

    state     = GameState()
    keys_held: set = set()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11:
                    # F11 切換全螢幕
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((LOGICAL_W, LOGICAL_H), pygame.RESIZABLE)
                keys_held.add(event.key)

            elif event.type == pygame.KEYUP:
                keys_held.discard(event.key)

        # 計算當前縮放參數
        sw, sh = screen.get_size()
        scaled_w, scaled_h, off_x, off_y, scale = get_viewport(sw, sh)

        # 滑鼠螢幕座標 → 邏輯座標
        raw_mx, raw_my = pygame.mouse.get_pos()
        logical_mouse  = screen_to_logical(raw_mx, raw_my, off_x, off_y, scale)

        cmd = read_input(player_id, keys_held, logical_mouse)
        try:
            sock.sendto(pack_command(cmd), server_addr)
        except Exception:
            pass

        # 接收最新 state（drain 全部，只保留最新一筆）
        latest = None
        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                if packet_type(data) == PKT_STATE:
                    latest = data
            except BlockingIOError:
                break
        if latest:
            state = unpack_state(latest)

        # 畫到邏輯畫布
        draw(logical_surf, state, player_id, font)

        # 縮放到實際螢幕（黑邊填充）
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
