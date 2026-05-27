import math
import os
import socket
import sys
import time
import threading
import pygame

from game.input      import (read_input, set_giant_age, set_dash_context,
                             set_burst_shots_left, set_cloak_ticks,
                             get_mercury_aim_angle, notify_air_cannon_hit,
                             cancel_mercury_barrage, init_char, init_rune)
from game.renderer   import draw, handle_settings_click, reset_game_state, settings_blocks_click, LOGICAL_W, LOGICAL_H
from game.state      import GameState
from game.obstacle   import load_map
import game.charselect as charselect
from game.charselect import CHARACTERS as _CHAR_LIST
from game.chars.vince.giant_state import TOTAL_TICKS as _GIANT_TOTAL_TICKS
from game.lobby      import lobby_screen
from network.protocol import (
    PKT_JOINED, PKT_STATE, PKT_GAME_START, PKT_ALL_JOINED,
    PKT_QUIT, PKT_GAME_OVER,
    pack_join, pack_command, pack_char_select, pack_quit,
    unpack_joined, unpack_state, unpack_game_start,
    packet_type,
)

PORT     = 5000
BUF_SIZE = 8192
FPS      = 60
MAP_PATH = "maps/map_01.json"

COL_BG   = (20, 24, 32)
COL_TEXT = (220, 220, 220)
COL_HINT = (110, 130, 160)


# ── Local server thread (used when CLOUD_SERVER_IP = "127.0.0.1") ────────────

_local_server_started = False

def _start_server_thread() -> None:
    """Start server.py as a daemon thread for local / same-machine testing.
    Silently ignores bind errors (another terminal may already own the port)."""
    def _run_safe():
        try:
            from server import run as server_run
            server_run()
        except OSError as e:
            print(f"[Server] Could not bind port (already in use?): {e}")
    t = threading.Thread(target=_run_safe, daemon=True)
    t.start()
    time.sleep(0.4)   # give the server time to bind


# ── Matchmaking screen ────────────────────────────────────────────────────────

def matchmaking_screen(sock: socket.socket, server_addr: tuple,
                       screen: pygame.Surface,
                       font_lg: pygame.font.Font,
                       font_sm: pygame.font.Font,
                       clock: pygame.time.Clock):
    """
    Send PKT_JOIN until server matches us with an opponent.
    Waits for PKT_JOINED (our pid) + PKT_ALL_JOINED (match confirmed).
    Both arrive together when a match is made, so this usually resolves
    within one frame after the second player connects.

    Returns player_id on success, None if cancelled.
    """
    player_id  = None   # set when PKT_JOINED received
    all_joined = False  # set when PKT_ALL_JOINED received
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
                _cancel_matchmaking(sock, server_addr, player_id)
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                _cancel_matchmaking(sock, server_addr, player_id)
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if BACK_R.collidepoint(mx, my):
                    _cancel_matchmaking(sock, server_addr, player_id)
                    return None

        # Send PKT_JOIN heartbeat every second
        if now_perf - last_sent >= 1.0:
            try:
                sock.sendto(pack_join(), server_addr)
            except Exception:
                pass
            last_sent = now_perf

        # Drain socket — handles any arrival order of PKT_JOINED / PKT_ALL_JOINED
        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                pkt = packet_type(data)
                if pkt == PKT_JOINED:
                    player_id = unpack_joined(data)
                    if all_joined:
                        return player_id   # both arrived (uncommon order)
                elif pkt == PKT_ALL_JOINED:
                    all_joined = True
                    if player_id is not None:
                        return player_id   # match complete
                # Other packets (stale GAME_OVER etc.): discard
            except (BlockingIOError, ConnectionResetError, OSError):
                break

        # ── Draw ─────────────────────────────────────────────────────
        screen.fill(COL_BG)
        dots = "." * dot_count
        if player_id is None:
            msg = f"Searching for opponent{dots}"
        else:
            msg = f"Match found! Starting{dots}"
        t = font_lg.render(msg, True, COL_TEXT)
        screen.blit(t, (CX - t.get_width() // 2, CY - 30))

        s = font_sm.render(f"{server_addr[0]}:{server_addr[1]}", True, COL_HINT)
        screen.blit(s, (CX - s.get_width() // 2, CY + 15))

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


def _cancel_matchmaking(sock, server_addr, player_id):
    """Send PKT_QUIT if already assigned a pid (in session), else just return."""
    if player_id is not None:
        try:
            sock.sendto(pack_quit(player_id), server_addr)
        except Exception:
            pass


# ── 選角畫面 ──────────────────────────────────────────────────────────────────

def char_select_loop(sock, server_addr, player_id, screen,
                     font_lg, font_sm, clock) -> tuple:
    charselect.reset()
    my_ready        = False
    last_time       = pygame.time.get_ticks()
    resend_timer    = 0.0    # PKT_CHAR_SELECT retry every 1.5s while confirmed
    heartbeat_timer = 0.0    # PKT_JOIN heartbeat every 1s (keep-alive for server)
    RESEND_INTERVAL    = 1.5
    HEARTBEAT_INTERVAL = 1.0

    while True:
        now = pygame.time.get_ticks()
        dt  = (now - last_time) / 1000.0
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                try:
                    sock.sendto(pack_quit(player_id), server_addr)
                except Exception:
                    pass
                return None, None, 0
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                try:
                    sock.sendto(pack_quit(player_id), server_addr)
                except Exception:
                    pass
                return None, None, 0
            just_confirmed = charselect.handle_event(event)
            if just_confirmed:
                idx     = charselect.selected_idx()
                rune_id = charselect.selected_rune()
                sock.sendto(pack_char_select(idx, rune_id), server_addr)
                resend_timer = 0.0
            my_ready = charselect.is_confirmed()

        # Heartbeat: send PKT_JOIN every second so server can detect if we vanish
        heartbeat_timer += dt
        if heartbeat_timer >= HEARTBEAT_INTERVAL:
            heartbeat_timer = 0.0
            try:
                sock.sendto(pack_join(), server_addr)
            except Exception:
                pass

        # Periodically resend PKT_CHAR_SELECT while confirmed (survive packet loss)
        if my_ready:
            resend_timer += dt
            if resend_timer >= RESEND_INTERVAL:
                resend_timer = 0.0
                try:
                    sock.sendto(
                        pack_char_select(charselect.selected_idx(),
                                         charselect.selected_rune()),
                        server_addr)
                except Exception:
                    pass

        # Drain socket
        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                pkt = packet_type(data)
                if pkt == PKT_GAME_START:
                    raw_chars    = unpack_game_start(data)
                    player_chars = {pid: _CHAR_LIST[cid]["name"]
                                    for pid, cid in raw_chars.items()
                                    if 0 <= cid < len(_CHAR_LIST)}
                    return player_chars, charselect.selected_char()["name"], charselect.selected_rune()
                elif pkt == PKT_GAME_OVER:
                    # Opponent left (PKT_QUIT) or server force-reset — go back to lobby
                    return None, None, 0
            except (BlockingIOError, ConnectionResetError, OSError):
                break

        charselect.update(dt)
        charselect.draw_char_select(screen, font_lg, font_sm, my_ready, False)
        pygame.display.flip()
        clock.tick(FPS)


# ── 遊戲結束提示畫面 ─────────────────────────────────────────────────────────

def _show_game_over_msg(screen: pygame.Surface,
                        font_lg: pygame.font.Font,
                        font_sm: pygame.font.Font,
                        clock: pygame.time.Clock,
                        message: str,
                        duration: float = 2.5) -> None:
    CX, CY  = LOGICAL_W // 2, LOGICAL_H // 2
    elapsed = 0.0
    while elapsed < duration:
        dt = clock.tick(FPS) / 1000.0
        elapsed += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                return
        screen.fill((15, 18, 26))
        t = font_lg.render(message, True, (220, 180, 80))
        screen.blit(t, (CX - t.get_width() // 2, CY - 20))
        hint = font_sm.render("Returning to lobby...", True, (80, 100, 140))
        screen.blit(hint, (CX - hint.get_width() // 2, CY + 20))
        pygame.display.flip()


# ── 主流程 ────────────────────────────────────────────────────────────────────

def run() -> None:
    os.environ['SDL_WINDOW_ALLOW_HIGHDPI'] = '1'
    pygame.init()
    screen = pygame.display.set_mode(
        (LOGICAL_W, LOGICAL_H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("PvP Game")

    _font_bold = os.path.join("assets", "fonts", "MapleMono-NF-Bold.ttf")
    _font_reg  = os.path.join("assets", "fonts", "MapleMono-NF-Regular.ttf")
    font_lg  = pygame.font.Font(_font_bold, 24)
    font_sm  = pygame.font.Font(_font_reg,  15)
    font_hud = pygame.font.Font(_font_bold, 24)
    clock    = pygame.time.Clock()

    app_running = True
    global _local_server_started

    from network.cloud_config import CLOUD_SERVER_IP, CLOUD_SERVER_PORT
    server_addr = (CLOUD_SERVER_IP, CLOUD_SERVER_PORT)

    # Auto-start a local server thread when connecting to localhost.
    # This lets two terminals on the same machine test without Oracle VM.
    # For production (Oracle VM IP), this block is skipped entirely.
    if CLOUD_SERVER_IP in ("127.0.0.1", "localhost") and not _local_server_started:
        _start_server_thread()
        _local_server_started = True

    while app_running:

        # ── Lobby ────────────────────────────────────────────────────
        mode, _ = lobby_screen(screen, font_lg, font_sm, clock)
        if mode is None:
            break   # user closed window

        # ── Matchmaking ──────────────────────────────────────────────
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        player_id = matchmaking_screen(sock, server_addr,
                                       screen, font_lg, font_sm, clock)
        if player_id is None:
            sock.close()
            continue

        pygame.display.set_caption(f"PvP Game — Player {player_id}")

        # ── Load map ─────────────────────────────────────────────────
        obstacles = load_map(MAP_PATH)

        # ── Char select ──────────────────────────────────────────────
        player_chars, my_char_name, my_rune_id = char_select_loop(
            sock, server_addr, player_id, screen, font_lg, font_sm, clock)
        if player_chars is None:
            sock.close()
            pygame.display.set_caption("PvP Game")
            continue

        init_char(my_char_name)
        init_rune(my_rune_id)

        # ── Game loop ────────────────────────────────────────────────
        reset_game_state()
        state         = GameState()
        keys_held     = set()
        fullscreen    = False
        game_running  = True
        opponent_quit = False

        while game_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try:
                        sock.sendto(pack_quit(player_id), server_addr)
                    except Exception:
                        pass
                    game_running = False
                    app_running  = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        try:
                            sock.sendto(pack_quit(player_id), server_addr)
                        except Exception:
                            pass
                        game_running = False
                    elif event.key == pygame.K_F11:
                        fullscreen = not fullscreen
                        if fullscreen:
                            screen = pygame.display.set_mode(
                                (LOGICAL_W, LOGICAL_H),
                                pygame.SCALED | pygame.FULLSCREEN)
                        else:
                            screen = pygame.display.set_mode(
                                (LOGICAL_W, LOGICAL_H),
                                pygame.SCALED | pygame.RESIZABLE)
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
            shift_held    = (pygame.K_LSHIFT in keys_held
                             or pygame.K_RSHIFT in keys_held)
            suppress_lmb  = settings_blocks_click(mx, my_pos)
            _lp_prev      = state.players.get(player_id)
            _is_stunned   = bool(_lp_prev and _lp_prev.stun_until > state.tick)
            cmd, effective_stance, ammo, is_reloading, skill_cooldowns = read_input(
                player_id, keys_held, logical_mouse, shift_held,
                suppress_lmb, _is_stunned)
            aim_angle_deg = math.degrees(math.atan2(cmd.aim_x, -cmd.aim_y))
            _mercury_locked = get_mercury_aim_angle()
            if _mercury_locked is not None:
                aim_angle_deg = _mercury_locked

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
                gt  = local_player.giant_tick
                age = state.tick - gt if gt >= 0 else -1
                set_giant_age(age if 0 <= age < _GIANT_TOTAL_TICKS else -1)
            else:
                set_giant_age(-1)
            set_burst_shots_left(
                max(0, 3 - local_player.burst_shots_fired)
                if local_player and local_player.burst_next_tick >= 0
                else 0)
            set_cloak_ticks(
                max(0, local_player.cloak_until - state.tick)
                if local_player and local_player.cloak_until > state.tick
                else 0)
            if local_player:
                notify_air_cannon_hit(local_player.air_cannon_hit_seq)
                if local_player.mercury_start_tick < 0 and _is_stunned:
                    cancel_mercury_barrage()
            draw(screen, state, player_id, font_sm, obstacles,
                 effective_stance, aim_angle_deg, ammo, is_reloading,
                 player_chars, skill_cooldowns,
                 mx=mx, my=my_pos, font_hud=font_hud)
            pygame.display.flip()
            clock.tick(FPS)

        # ── Post-game ────────────────────────────────────────────────
        sock.close()
        pygame.display.set_caption("PvP Game")

        if not app_running:
            break

        if opponent_quit:
            _show_game_over_msg(screen, font_lg, font_sm, clock,
                                "Opponent has left the game")

    pygame.quit()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[Client] Disconnected.")
        sys.exit(0)
