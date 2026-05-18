import math
import os
import socket
import sys
import time
import threading
import pygame

from game.input      import read_input, set_giant_age, set_dash_context, set_burst_shots_left, set_cloak_ticks
from game.renderer   import draw, handle_settings_click, reset_game_state, LOGICAL_W, LOGICAL_H
from game.state      import GameState
from game.obstacle   import load_map
import game.charselect as charselect
from game.lobby      import lobby_screen
from network.protocol import (
    PKT_JOINED, PKT_STATE, PKT_GAME_START, PKT_ALL_JOINED,
    PKT_QUIT, PKT_GAME_OVER,
    pack_join, pack_command, pack_char_select, pack_quit,
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
    BACK_R     = pygame.Rect(CX - 80, CY + 110, 160, 44)

    while True:
        dt       = clock.tick(FPS) / 1000.0
        now_perf = time.perf_counter()
        dot_timer += dt
        if dot_timer >= 0.4:
            dot_timer  = 0.0
            dot_count  = (dot_count + 1) % 4

        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if BACK_R.collidepoint(mx, my):
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

        # BACK 按鈕
        hov = BACK_R.collidepoint(mx, my)
        pygame.draw.rect(screen, (36, 46, 68) if hov else (24, 30, 46),
                         BACK_R, border_radius=9)
        pygame.draw.rect(screen, (72, 92, 138) if hov else (48, 62, 95),
                         BACK_R, 2, border_radius=9)
        lbl = font_sm.render("← BACK", True,
                              (200, 215, 248) if hov else (130, 150, 195))
        screen.blit(lbl, (BACK_R.centerx - lbl.get_width()  // 2,
                          BACK_R.centery - lbl.get_height() // 2))

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
    BACK_R    = pygame.Rect(CX - 80, CY + 80, 160, 44)

    while True:
        dt = clock.tick(FPS) / 1000.0
        dot_timer += dt
        if dot_timer >= 0.4:
            dot_timer  = 0.0
            dot_count  = (dot_count + 1) % 4

        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if BACK_R.collidepoint(mx, my):
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
        hint = font_sm.render("Share your IP with the other player", True, COL_HINT)
        screen.blit(hint, (CX - hint.get_width() // 2, CY + 20))

        # BACK 按鈕
        hov = BACK_R.collidepoint(mx, my)
        pygame.draw.rect(screen, (36, 46, 68) if hov else (24, 30, 46),
                         BACK_R, border_radius=9)
        pygame.draw.rect(screen, (72, 92, 138) if hov else (48, 62, 95),
                         BACK_R, 2, border_radius=9)
        lbl = font_sm.render("← BACK", True,
                              (200, 215, 248) if hov else (130, 150, 195))
        screen.blit(lbl, (BACK_R.centerx - lbl.get_width()  // 2,
                          BACK_R.centery - lbl.get_height() // 2))

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


# ── 遊戲結束提示畫面（短暫顯示後回到 lobby）────────────────────────────

def _show_game_over_msg(screen: pygame.Surface,
                        font_lg: pygame.font.Font,
                        font_sm: pygame.font.Font,
                        clock: pygame.time.Clock,
                        message: str,
                        duration: float = 2.5) -> None:
    CX, CY = LOGICAL_W // 2, LOGICAL_H // 2
    elapsed = 0.0
    while elapsed < duration:
        dt = clock.tick(FPS) / 1000.0
        elapsed += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                return   # 任意鍵跳過
        screen.fill((15, 18, 26))
        t = font_lg.render(message, True, (220, 180, 80))
        screen.blit(t, (CX - t.get_width() // 2, CY - 20))
        hint = font_sm.render("Returning to lobby...", True, (80, 100, 140))
        screen.blit(hint, (CX - hint.get_width() // 2, CY + 20))
        pygame.display.flip()


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

    _server_started = False   # server daemon 只啟動一次
    app_running     = True    # False → 離開整個程式

    while app_running:

        # ── Lobby：Host / Join 選擇 ──────────────────────────────────
        mode, entered_ip = lobby_screen(screen, font_lg, font_sm, clock)
        if mode is None:
            break   # 使用者關閉視窗 → 結束程式

        if mode == "host":
            if not _server_started:
                _start_server_thread()
                _server_started = True
            server_ip = "127.0.0.1"
        else:
            server_ip = entered_ip

        server_addr = (server_ip, PORT)

        # ── 連線 ────────────────────────────────────────────────────
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        player_id = connect_screen(sock, server_addr, screen, font_lg, font_sm, clock)
        if player_id is None:
            sock.close()
            # 若是視窗關閉事件，connect_screen 回傳 None
            # 這裡直接 continue 回 lobby（不結束程式）
            continue

        pygame.display.set_caption(f"PvP Game — Player {player_id}")

        # ── 等待所有玩家連線 ─────────────────────────────────────────
        if not wait_for_all_players(sock, screen, font_lg, font_sm, clock):
            sock.close()
            pygame.display.set_caption("PvP Game")
            continue

        # ── 載入地圖 ────────────────────────────────────────────────
        obstacles = load_map(MAP_PATH)

        # ── 選角 ────────────────────────────────────────────────────
        player_chars, my_char_key = char_select_loop(
            sock, server_addr, screen, font_lg, font_sm, clock)
        if player_chars is None:
            sock.close()
            pygame.display.set_caption("PvP Game")
            continue

        from game.input import init_char
        init_char(my_char_key)

        # ── 遊戲主迴圈 ──────────────────────────────────────────────
        reset_game_state()          # 清除上一局的殘骸、粒子、震動等視覺狀態
        state          = GameState()
        keys_held      = set()
        fullscreen     = False
        game_running   = True
        opponent_quit  = False   # 對方先離開

        while game_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # 關閉視窗 → 通知 server + 結束程式
                    try:
                        sock.sendto(pack_quit(player_id), server_addr)
                    except Exception:
                        pass
                    game_running = False
                    app_running  = False

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

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx_click, my_click = pygame.mouse.get_pos()
                    action = handle_settings_click(mx_click, my_click)
                    if action == "quit":
                        try:
                            sock.sendto(pack_quit(player_id), server_addr)
                        except Exception:
                            pass
                        game_running = False

            logical_mouse = pygame.mouse.get_pos()
            mx, my_pos    = logical_mouse
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
                    pkt = packet_type(data)
                    if pkt == PKT_STATE:
                        latest = data
                    elif pkt == PKT_GAME_OVER:
                        opponent_quit = True
                        game_running  = False
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
            set_cloak_ticks(
                max(0, local_player.cloak_until - state.tick)
                if local_player and local_player.cloak_until > state.tick
                else 0
            )

            draw(screen, state, player_id, font_sm, obstacles,
                 effective_stance, aim_angle_deg, ammo, is_reloading,
                 player_chars, skill_cooldowns,
                 mx=mx, my=my_pos)
            pygame.display.flip()
            clock.tick(FPS)

        # ── 遊戲結束後處理 ───────────────────────────────────────────
        sock.close()
        pygame.display.set_caption("PvP Game")

        if not app_running:
            break   # 視窗被關閉 → 直接離開

        if opponent_quit:
            _show_game_over_msg(screen, font_lg, font_sm, clock,
                                "Opponent has left the game")

        # 否則直接 continue → 回到 lobby

    pygame.quit()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[Client] Disconnected.")
        sys.exit(0)
