import math
import os
import random
import socket
import sys
import time
import threading
import pygame

from game.input      import (read_input, set_giant_age, set_dash_context,
                             set_burst_shots_left, set_cloak_ticks,
                             get_mercury_aim_angle, notify_air_cannon_hit,
                             cancel_mercury_barrage, cancel_zombie_spit,
                             init_char, init_rune,
                             apply_gem_cd_reduction)
from game.renderer   import draw, handle_settings_click, reset_game_state, set_map_portals, trigger_portal_flash, settings_blocks_click, LOGICAL_W, LOGICAL_H
from game.state      import GameState, configure_map
from game.obstacle   import load_map
import game.charselect as charselect
from game.charselect import CHARACTERS as _CHAR_LIST
from game.chars.vince.giant_state import TOTAL_TICKS as _GIANT_TOTAL_TICKS
from game.lobby      import lobby_screen
from network.cloud_config import CLOUD_SERVER_IP, CLOUD_SERVER_PORT
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

_MAPS_META_PATH = "maps/maps_meta.json"
_maps_meta: list[dict] = []

def _get_maps_meta() -> list[dict]:
    global _maps_meta
    if not _maps_meta:
        import json
        with open(_MAPS_META_PATH, encoding="utf-8") as f:
            _maps_meta = json.load(f)
    return _maps_meta

COL_BG   = (20, 24, 32)
COL_TEXT = (220, 220, 220)
COL_HINT = (110, 130, 160)


# ── Giant font (room code — the single most important glyph on the page) ─────

_giant_font_cache: list = []

def _get_giant_font() -> pygame.font.Font:
    if not _giant_font_cache:
        path = os.path.join("assets", "fonts", "MapleMono-NF-Bold.ttf")
        _giant_font_cache.append(pygame.font.Font(path, 100))
    return _giant_font_cache[0]


def _draw_spaced_digits(screen: pygame.Surface, font: pygame.font.Font,
                        text: str, color, center_x: int, y: int,
                        gap: int = 18) -> None:
    """Render `text` one glyph at a time with a fixed gap between glyphs,
    centred horizontally on center_x."""
    surfs   = [font.render(ch, True, color) for ch in text]
    total_w = sum(s.get_width() for s in surfs) + gap * (len(surfs) - 1)
    x = center_x - total_w // 2
    for s in surfs:
        screen.blit(s, (x, y))
        x += s.get_width() + gap


# ── Local server thread (used only when CLOUD_SERVER_IP = "127.0.0.1") ───────

_local_server_started = False

def _start_server_thread(map_id: int = 0) -> None:
    """Start server.py as a daemon thread for local / same-machine testing."""
    def _run_safe():
        try:
            from server import run as server_run
            server_run(map_id=map_id)
        except OSError as e:
            print(f"[Server] Could not bind port (already in use?): {e}")
    t = threading.Thread(target=_run_safe, daemon=True)
    t.start()
    time.sleep(0.4)


# ── Matchmaking screen ────────────────────────────────────────────────────────

def matchmaking_screen(sock: socket.socket, server_addr: tuple,
                       room_code: int, is_host: bool,
                       screen: pygame.Surface,
                       font_lg: pygame.font.Font,
                       font_sm: pygame.font.Font,
                       clock: pygame.time.Clock,
                       map_id: int = 0, game_mode: int = 0):
    """
    Send PKT_JOIN(room_code) every second to server_addr.
    Wait for PKT_JOINED + PKT_ALL_JOINED from the server.
    Returns (player_id, server_addr) on success, (None, None) on cancel.
    """
    player_id         = None
    all_joined        = False
    last_join         = -999.0
    _lobby_game_mode  = game_mode

    dot_count = 0
    dot_timer = 0.0
    CX        = LOGICAL_W // 2
    BACK_R    = pygame.Rect(CX - 80, 580, 160, 44)

    # ── Map selection (host only) ──────────────────────────────────────
    _maps       = _get_maps_meta()
    _RANDOM_IDX = len(_maps)          # last button = Random
    _N_BTNS     = _RANDOM_IDX + 1
    _BTN_W      = 200
    _BTN_H      = 46
    _BTN_GAP    = 16
    _btn_total  = _N_BTNS * _BTN_W + (_N_BTNS - 1) * _BTN_GAP
    _BTN_Y      = 430
    _MAP_BTN_RS = [
        pygame.Rect(CX - _btn_total // 2 + i * (_BTN_W + _BTN_GAP),
                    _BTN_Y, _BTN_W, _BTN_H)
        for i in range(_N_BTNS)
    ]
    sel_map_idx   = map_id if map_id < _RANDOM_IDX else 0
    actual_map_id = sel_map_idx

    while True:
        dt    = clock.tick(FPS) / 1000.0
        now   = time.perf_counter()
        dot_timer += dt
        if dot_timer >= 0.4:
            dot_timer = 0.0
            dot_count = (dot_count + 1) % 4

        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _cancel_matchmaking(sock, server_addr, player_id)
                return None, None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                _cancel_matchmaking(sock, server_addr, player_id)
                return None, None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if BACK_R.collidepoint(mx, my):
                    _cancel_matchmaking(sock, server_addr, player_id)
                    return None, None
                if is_host:
                    for _i, _r in enumerate(_MAP_BTN_RS):
                        if _r.collidepoint(mx, my):
                            sel_map_idx   = _i
                            actual_map_id = (random.randint(0, _RANDOM_IDX - 1)
                                             if _i == _RANDOM_IDX else _i)

        # Send PKT_JOIN every second with current map selection and game mode
        if now - last_join >= 1.0:
            try:
                sock.sendto(pack_join(room_code, actual_map_id, _lobby_game_mode), server_addr)
            except Exception:
                pass
            last_join = now

        # Drain socket
        while True:
            try:
                data, _ = sock.recvfrom(BUF_SIZE)
                pkt = packet_type(data)
                if pkt == PKT_JOINED:
                    player_id = unpack_joined(data)
                    if all_joined:
                        return player_id, server_addr
                elif pkt == PKT_ALL_JOINED:
                    all_joined = True
                    if player_id is not None:
                        return player_id, server_addr
            except (BlockingIOError, ConnectionResetError, OSError):
                break

        # ── Draw ──────────────────────────────────────────────────────
        screen.fill(COL_BG)
        dots = "." * dot_count
        msg  = (f"Match found! Starting{dots}" if all_joined
                else "Waiting for Opponent")

        t = font_lg.render(msg, True, COL_TEXT)
        screen.blit(t, (CX - t.get_width() // 2, 130))

        if is_host:
            lbl_surf = font_sm.render("ROOM CODE  —  SHARE WITH YOUR FRIEND", True, COL_HINT)
            screen.blit(lbl_surf, (CX - lbl_surf.get_width() // 2, 210))
            _draw_spaced_digits(screen, _get_giant_font(), str(room_code),
                                (235, 195, 70), CX, 245)

            # ── Map selection row ──────────────────────────────────────
            sel_hint = font_sm.render("SELECT MAP", True, COL_HINT)
            screen.blit(sel_hint, (CX - sel_hint.get_width() // 2, _BTN_Y - 26))

            for _i, _r in enumerate(_MAP_BTN_RS):
                _sel = (_i == sel_map_idx)
                _hov = _r.collidepoint(mx, my)
                _rnd = (_i == _RANDOM_IDX)
                _lbl = (chr(0xf074) + "  RANDOM") if _rnd else _maps[_i]["name"]

                if _sel:
                    _bg = (32, 20, 60) if _rnd else (28, 52, 88)
                    _bd = (120, 60, 210) if _rnd else (68, 148, 235)
                    _tc = (200, 150, 255) if _rnd else (185, 218, 255)
                elif _hov:
                    _bg = (22, 16, 42) if _rnd else (22, 36, 60)
                    _bd = (80, 40, 140) if _rnd else (48, 82, 138)
                    _tc = (160, 110, 230) if _rnd else (140, 175, 225)
                else:
                    _bg, _bd, _tc = (16, 22, 36), (36, 48, 74), (82, 105, 148)

                pygame.draw.rect(screen, _bg, _r, border_radius=8)
                pygame.draw.rect(screen, _bd, _r, 2, border_radius=8)
                _ns = font_sm.render(_lbl, True, _tc)
                screen.blit(_ns, (_r.centerx - _ns.get_width()  // 2,
                                  _r.centery - _ns.get_height() // 2))
        else:
            hint = font_sm.render(f"Joining room {room_code}…", True, COL_HINT)
            screen.blit(hint, (CX - hint.get_width() // 2, 300))

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
    """Send PKT_QUIT if already matched (has pid), else just stop sending JOINs."""
    if player_id is not None and server_addr is not None:
        try:
            sock.sendto(pack_quit(player_id), server_addr)
        except Exception:
            pass


# ── 選角畫面 ──────────────────────────────────────────────────────────────────

def char_select_loop(sock, server_addr, player_id, room_code, screen,
                     font_lg, font_sm, clock, game_mode: int = 0) -> tuple:
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
                return None, None, 0, 0
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                try:
                    sock.sendto(pack_quit(player_id), server_addr)
                except Exception:
                    pass
                return None, None, 0, 0
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
                sock.sendto(pack_join(room_code, game_mode=game_mode), server_addr)
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
                    raw_chars, map_id, game_mode_wire, side_flip = unpack_game_start(data)
                    player_chars = {pid: _CHAR_LIST[cid]["name"]
                                    for pid, cid in raw_chars.items()
                                    if 0 <= cid < len(_CHAR_LIST)}
                    gmode = "deathmatch" if game_mode_wire == 0 else "endless"
                    return player_chars, charselect.selected_char()["name"], charselect.selected_rune(), map_id, gmode, side_flip
                elif pkt == PKT_GAME_OVER:
                    return None, None, 0, 0, "endless", False
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

    app_running  = True
    global _local_server_started

    while app_running:

        # ── Lobby ────────────────────────────────────────────────────
        mode, join_code, lobby_map_id, lobby_game_mode_idx = lobby_screen(screen, font_lg, font_sm, clock)
        if mode is None:
            break   # user closed window

        # ── Resolve server address + room code ────────────────────────
        is_host = (mode == "host")
        if is_host:
            room_code = random.randint(1000, 9999)
            if CLOUD_SERVER_IP == "127.0.0.1":
                if not _local_server_started:
                    _start_server_thread(map_id=lobby_map_id)
                    _local_server_started = True
        else:
            room_code = int(join_code)
        server_addr = (CLOUD_SERVER_IP, CLOUD_SERVER_PORT)

        # ── Matchmaking ──────────────────────────────────────────────
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        player_id, server_addr = matchmaking_screen(sock, server_addr,
                                                    room_code, is_host,
                                                    screen, font_lg, font_sm, clock,
                                                    map_id=lobby_map_id,
                                                    game_mode=lobby_game_mode_idx)
        if player_id is None:
            sock.close()
            continue

        pygame.display.set_caption(f"PvP Game — Player {player_id}")

        # ── Char select ──────────────────────────────────────────────
        player_chars, my_char_name, my_rune_id, map_id, game_mode, side_flip = char_select_loop(
            sock, server_addr, player_id, room_code, screen, font_lg, font_sm, clock,
            game_mode=lobby_game_mode_idx)
        if player_chars is None:
            sock.close()
            pygame.display.set_caption("PvP Game")
            continue

        # ── Load map (using map_id from server) ───────────────────────
        meta      = _get_maps_meta()
        map_entry = meta[map_id] if map_id < len(meta) else meta[0]
        configure_map(map_entry.get("width", 1920), map_entry.get("height", 1080))
        obstacles = load_map(map_entry["file"])

        init_char(my_char_name)
        init_rune(my_rune_id)

        # ── Game loop ────────────────────────────────────────────────
        set_map_portals(map_entry.get("portals", []))
        reset_game_state()
        state              = GameState()
        keys_held          = set()
        fullscreen         = False
        game_running       = True
        opponent_quit      = False
        _prev_gem_count    = 0
        _game_start_ms     = pygame.time.get_ticks()

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
                _prev_lp = state.players.get(player_id)
                state    = unpack_state(latest)
                _next_lp = state.players.get(player_id)
                if (_prev_lp and _next_lp and
                        abs(_next_lp.x - _prev_lp.x) > 300):
                    trigger_portal_flash()
                new_gem_count = state.gold_counts.get(player_id, 0)
                for _ in range(new_gem_count - _prev_gem_count):
                    apply_gem_cd_reduction()
                _prev_gem_count = new_gem_count

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
                if _is_stunned:
                    cancel_zombie_spit()
            draw(screen, state, player_id, font_sm, obstacles,
                 effective_stance, aim_angle_deg, ammo, is_reloading,
                 player_chars, skill_cooldowns,
                 mx=mx, my=my_pos, font_hud=font_hud,
                 game_mode=game_mode,
                 elapsed_ms=pygame.time.get_ticks() - _game_start_ms)
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
