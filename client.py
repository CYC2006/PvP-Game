import math
import os
import socket
import sys
import time
import threading
import pygame

from game.input      import read_input, set_giant_age, set_dash_context, set_burst_shots_left
from game.renderer   import draw, LOGICAL_W, LOGICAL_H
from game.state      import GameState
from game.obstacle   import load_map
import game.charselect as charselect
from game.lobby      import lobby_screen
from network.protocol import (
    PKT_JOINED, PKT_STATE, PKT_GAME_START, PKT_ALL_JOINED,
    pack_join, pack_command, pack_char_select,
    unpack_joined, unpack_state, unpack_game_start,
    packet_type,
)

PORT                = 5000
BUF_SIZE            = 1024
FPS                 = 60
MAP_PATH            = "maps/map_01.json"

COL_BG   = (20, 24, 32)
COL_TEXT = (220, 220, 220)
COL_HINT = (110, 130, 160)


# ── Server 背景執行緒 ─────────────────────────────────────────────────────

def _start_server_thread() -> None:
    """以 daemon thread 啟動 server，主程式結束時自動停止。"""
    from server import run as server_run
    t = threading.Thread(target=server_run, daemon=True)
    t.start()
    time.sleep(0.4)   # 給 server 時間 bind port


# ── 連線中畫面 ───────────────────────────────────────────────────────────

def connect_screen(sock: socket.socket, server_addr: tuple,
                   screen: pygame.Surface,
                   font_lg: pygame.font.Font,
                   font_sm: pygame.font.Font,
                   clock: pygame.time.Clock):
    """
    顯示「連線中…」畫面並持續嘗試連線。
    成功回傳 player_id；使用者關閉則回傳 None。
    """
    last_sent  = 0.0
    dot_count  = 0
    dot_timer  = 0.0
    CX, CY     = LOGICAL_W // 2, LOGICAL_H // 2

    while True:
        dt       = clock.tick(FPS) / 1000.0
        now_perf = time.perf_counter()
        dot_timer += dt
        if dot_timer >= 0.4:
            dot_timer  = 0.0
            dot_count  = (dot_count + 1) % 4

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None

        # 每秒發一次 JOIN
        if now_perf - last_sent >= 1.0:
            try:
                sock.sendto(pack_join(), server_addr)
            except Exception:
                pass
            last_sent = now_perf

        # 看有沒有收到 JOINED
        try:
            data, _ = sock.recvfrom(BUF_SIZE)
            if packet_type(data) == PKT_JOINED:
                return unpack_joined(data)
        except (BlockingIOError, ConnectionResetError, OSError):
            pass

        # 繪製
        screen.fill(COL_BG)
        dots = "." * dot_count
        t = font_lg.render(f"Connecting{dots}", True, COL_TEXT)
        screen.blit(t, (CX - t.get_width() // 2, CY - 30))
        s = font_sm.render(f"{server_addr[0]}:{server_addr[1]}", True, COL_HINT)
        screen.blit(s, (CX - s.get_width() // 2, CY + 15))
        e = font_sm.render("ESC to cancel", True, COL_HINT)
        screen.blit(e, (CX - e.get_width() // 2, CY + 50))
        pygame.display.flip()


# ── 等待第二位玩家 ────────────────────────────────────────────────────────

def wait_for_all_players(sock: socket.socket,
                         screen: pygame.Surface,
                         font_lg: pygame.font.Font,
                         font_sm: pygame.font.Font,
                         clock: pygame.time.Clock) -> bool:
    """
    顯示「等待玩家加入…」畫面，收到 PKT_ALL_JOINED 後回傳 True；
    玩家關閉視窗則回傳 False。
    """
    dot_count = 0
    dot_timer = 0.0
    CX, CY    = LOGICAL_W // 2, LOGICAL_H // 2

    while True:
        dt = clock.tick(FPS) / 1000.0
        dot_timer += dt
        if dot_timer >= 0.4:
            dot_timer  = 0.0
            dot_count  = (dot_count + 1) % 4

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        try:
            data, _ = sock.recvfrom(BUF_SIZE)
            if packet_type(data) == PKT_ALL_JOINED:
                return True
        except (BlockingIOError, ConnectionResetError, OSError):
            pass

        screen.fill(COL_BG)
        dots = "." * dot_count
        t = font_lg.render(f"Waiting for player{dots}", True, COL_TEXT)
        screen.blit(t, (CX - t.get_width() // 2, CY - 20))
        pygame.display.flip()


# ── 選角畫面 ──────────────────────────────────────────────────────────────

def char_select_loop(sock, server_addr, screen,
                     font_lg, font_sm, clock) -> tuple:
    charselect.reset()
    my_ready  = False
    last_time = pygame.time.get_ticks()

    while True:
        now = pygame.time.get_ticks()
        dt  = (now - last_time) / 1000.0
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None, None
            just_confirmed = charselect.handle_event(event)
            if just_confirmed:
                # 每次確認（含重新確認）都送一次選角封包
                idx = charselect.selected_idx()
                sock.sendto(pack_char_select(idx), server_addr)
            my_ready = charselect.is_confirmed()

        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                if packet_type(data) == PKT_GAME_START:
                    raw_chars = unpack_game_start(data)
                    from game.charselect import CHARACTERS
                    player_chars = {pid: CHARACTERS[cid]["char_key"]
                                    for pid, cid in raw_chars.items()
                                    if 0 <= cid < len(CHARACTERS)}
                    return player_chars, charselect.selected_char()["char_key"]
            except (BlockingIOError, ConnectionResetError, OSError):
                break

        charselect.update(dt)
        charselect.draw_char_select(screen, font_lg, font_sm, my_ready, False)
        pygame.display.flip()
        clock.tick(FPS)


# ── 主流程 ────────────────────────────────────────────────────────────────

def run() -> None:
    os.environ['SDL_WINDOW_ALLOW_HIGHDPI'] = '1'
    pygame.init()
    screen = pygame.display.set_mode(
        (LOGICAL_W, LOGICAL_H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("PvP Game")

    _font_bold = os.path.join("assets", "fonts", "MapleMono-NF-Bold.ttf")
    _font_reg  = os.path.join("assets", "fonts", "MapleMono-NF-Regular.ttf")
    font_lg = pygame.font.Font(_font_bold, 22)
    font_sm = pygame.font.Font(_font_reg,  15)
    clock   = pygame.time.Clock()

    # ── Lobby：Host / Join 選擇 ──────────────────────────────────────
    mode, entered_ip = lobby_screen(screen, font_lg, font_sm, clock)
    if mode is None:
        pygame.quit()
        return

    if mode == "host":
        _start_server_thread()
        server_ip = "127.0.0.1"
    else:
        server_ip = entered_ip

    server_addr = (server_ip, PORT)

    # ── 連線 ────────────────────────────────────────────────────────
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)

    player_id = connect_screen(sock, server_addr, screen, font_lg, font_sm, clock)
    if player_id is None:
        pygame.quit()
        sock.close()
        return

    pygame.display.set_caption(f"PvP Game — Player {player_id}")

    # ── 等待所有玩家連線 ─────────────────────────────────────────────
    if not wait_for_all_players(sock, screen, font_lg, font_sm, clock):
        pygame.quit()
        sock.close()
        return

    # ── 載入地圖 ────────────────────────────────────────────────────
    obstacles = load_map(MAP_PATH)

    # ── 選角 ────────────────────────────────────────────────────────
    player_chars, my_char_key = char_select_loop(
        sock, server_addr, screen, font_lg, font_sm, clock)
    if player_chars is None:
        pygame.quit()
        sock.close()
        return

    from game.input import init_char
    init_char(my_char_key)

    # ── 遊戲主迴圈 ──────────────────────────────────────────────────
    state        = GameState()
    keys_held    = set()
    fullscreen   = False
    game_running = True

    while game_running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game_running = False
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode(
                            (LOGICAL_W, LOGICAL_H), pygame.SCALED | pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode(
                            (LOGICAL_W, LOGICAL_H), pygame.SCALED | pygame.RESIZABLE)
                keys_held.add(event.key)
            elif event.type == pygame.KEYUP:
                keys_held.discard(event.key)

        logical_mouse = pygame.mouse.get_pos()
        shift_held    = (pygame.K_LSHIFT in keys_held or pygame.K_RSHIFT in keys_held)
        cmd, effective_stance, ammo, is_reloading, skill_cooldowns = read_input(
            player_id, keys_held, logical_mouse, shift_held)
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

        local_player = state.players.get(player_id)
        if local_player:
            set_dash_context(local_player.x, local_player.y,
                             obstacles, state.destroyed_obstacles)
        if local_player:
            gt = local_player.giant_tick
            from game.chars.rambo.giant_state import TOTAL_TICKS
            age = state.tick - gt if gt >= 0 else -1
            set_giant_age(age if 0 <= age < TOTAL_TICKS else -1)
        else:
            set_giant_age(-1)
        set_burst_shots_left(max(0, 3 - local_player.burst_shots_fired)
                             if local_player and local_player.burst_next_tick >= 0
                             else 0)

        draw(screen, state, player_id, font_sm, obstacles,
             effective_stance, aim_angle_deg, ammo, is_reloading,
             player_chars, skill_cooldowns)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sock.close()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[Client] Disconnected.")
        sys.exit(0)
