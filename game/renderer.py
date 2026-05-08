import pygame
from game.state import GameState, MAX_HP, MAP_WIDTH, MAP_HEIGHT, PLAYER_RADIUS, BULLET_RADIUS

SCREEN_W = 1280
SCREEN_H = 720

# colours
COL_BG          = (30,  30,  30)
COL_MAP_BG      = (45,  55,  45)
COL_GRID        = (55,  65,  55)
COL_MAP_BORDER  = (80,  80,  80)
COL_TEXT        = (220, 220, 220)
COL_SELF_RIM    = (255, 255, 255)
COL_OTHER_RIM   = (200, 200, 200)
COL_PLAYERS     = {1: (100, 180, 255), 2: (255, 120, 100)}
COL_BULLET      = {1: (160, 220, 255), 2: (255, 180, 140)}
COL_HP_BG       = (60,  20,  20)
COL_HP_FILL     = (220, 60,  60)
COL_HP_BORDER   = (180, 180, 180)
GRID_SIZE = 120

# HUD constants
HP_BAR_X      = 20
HP_BAR_Y_FROM_BOTTOM = 50
HP_BAR_W      = 160
HP_BAR_H      = 18
HP_PIP_GAP    = 4


def _camera(my_player) -> tuple[float, float]:
    return SCREEN_W // 2 - my_player.x, SCREEN_H // 2 - my_player.y


def _ws(wx, wy, cx, cy) -> tuple[int, int]:
    return int(wx + cx), int(wy + cy)


def draw(screen: pygame.Surface, state: GameState, my_id: int,
         font: pygame.font.Font) -> None:
    screen.fill(COL_BG)

    if my_id not in state.players:
        _draw_waiting(screen, font)
        return

    me = state.players[my_id]
    cx, cy = _camera(me)

    _draw_map(screen, cx, cy)
    _draw_bullets(screen, state, cx, cy)
    _draw_players(screen, state, my_id, cx, cy, font)
    _draw_hud(screen, state, my_id, font)


# ── map ──────────────────────────────────────────────────────────────────────

def _draw_map(screen, cx, cy):
    map_rect = pygame.Rect(int(cx), int(cy), MAP_WIDTH, MAP_HEIGHT)
    pygame.draw.rect(screen, COL_MAP_BG, map_rect)

    for x in range(0, MAP_WIDTH + 1, GRID_SIZE):
        sx, _ = _ws(x, 0, cx, cy)
        if 0 <= sx <= SCREEN_W:
            pygame.draw.line(screen, COL_GRID,
                             (sx, max(0, int(cy))),
                             (sx, min(SCREEN_H, int(cy + MAP_HEIGHT))))

    for y in range(0, MAP_HEIGHT + 1, GRID_SIZE):
        _, sy = _ws(0, y, cx, cy)
        if 0 <= sy <= SCREEN_H:
            pygame.draw.line(screen, COL_GRID,
                             (max(0, int(cx)), sy),
                             (min(SCREEN_W, int(cx + MAP_WIDTH)), sy))

    pygame.draw.rect(screen, COL_MAP_BORDER, map_rect, 2)


# ── bullets ───────────────────────────────────────────────────────────────────

def _draw_bullets(screen, state, cx, cy):
    for bullet in state.bullets.values():
        sx, sy = _ws(bullet.x, bullet.y, cx, cy)
        if -BULLET_RADIUS <= sx <= SCREEN_W + BULLET_RADIUS \
                and -BULLET_RADIUS <= sy <= SCREEN_H + BULLET_RADIUS:
            color = COL_BULLET.get(bullet.owner_id, (255, 255, 200))
            pygame.draw.circle(screen, color, (sx, sy), BULLET_RADIUS)


# ── players ───────────────────────────────────────────────────────────────────

def _draw_players(screen, state, my_id, cx, cy, font):
    for pid, player in state.players.items():
        sx, sy = _ws(player.x, player.y, cx, cy)
        if not (-PLAYER_RADIUS <= sx <= SCREEN_W + PLAYER_RADIUS
                and -PLAYER_RADIUS <= sy <= SCREEN_H + PLAYER_RADIUS):
            continue

        color = COL_PLAYERS.get(pid, (180, 180, 180))
        rim   = COL_SELF_RIM if pid == my_id else COL_OTHER_RIM

        pygame.draw.circle(screen, color, (sx, sy), PLAYER_RADIUS)
        pygame.draw.circle(screen, rim,   (sx, sy), PLAYER_RADIUS, 2)

        # small HP pips above the other player (not self — self has the bar)
        if pid != my_id:
            _draw_pip_bar(screen, player.hp, sx - 20, sy - PLAYER_RADIUS - 10)

        label = font.render(f"P{pid}", True, COL_TEXT)
        screen.blit(label, (sx - label.get_width() // 2, sy - PLAYER_RADIUS - 20))


def _draw_pip_bar(screen, hp: int, x: int, y: int):
    pip_w = 7
    for i in range(MAX_HP):
        col = COL_HP_FILL if i < hp else COL_HP_BG
        pygame.draw.rect(screen, col,
                         (x + i * (pip_w + 2), y, pip_w, 5))


# ── HUD ──────────────────────────────────────────────────────────────────────

def _draw_hud(screen, state, my_id, font):
    # top-left tick + position
    if my_id in state.players:
        me = state.players[my_id]
        screen.blit(font.render(f"Tick {state.tick}", True, COL_TEXT), (8, 8))
        screen.blit(font.render(f"P{my_id}  ({int(me.x)}, {int(me.y)})", True, COL_TEXT), (8, 26))

    # bottom-left HP bar
    _draw_hp_bar(screen, state, my_id, font)


def _draw_hp_bar(screen, state, my_id, font):
    bar_y = SCREEN_H - HP_BAR_Y_FROM_BOTTOM
    hp    = state.players[my_id].hp if my_id in state.players else 0

    # background
    pygame.draw.rect(screen, COL_HP_BG, (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), border_radius=4)

    # filled portion
    fill_w = int(HP_BAR_W * max(0, hp) / MAX_HP)
    if fill_w > 0:
        pygame.draw.rect(screen, COL_HP_FILL,
                         (HP_BAR_X, bar_y, fill_w, HP_BAR_H), border_radius=4)

    # border
    pygame.draw.rect(screen, COL_HP_BORDER,
                     (HP_BAR_X, bar_y, HP_BAR_W, HP_BAR_H), 2, border_radius=4)

    # pips inside bar
    pip_w = (HP_BAR_W - HP_PIP_GAP * (MAX_HP + 1)) // MAX_HP
    for i in range(MAX_HP):
        pip_x = HP_BAR_X + HP_PIP_GAP + i * (pip_w + HP_PIP_GAP)
        col = (255, 90, 90) if i < hp else (80, 30, 30)
        pygame.draw.rect(screen, col,
                         (pip_x, bar_y + 3, pip_w, HP_BAR_H - 6), border_radius=2)

    # label
    label = font.render(f"HP  {hp} / {MAX_HP}", True, COL_TEXT)
    screen.blit(label, (HP_BAR_X, bar_y - 18))


def _draw_waiting(screen, font):
    msg = font.render("Waiting for server...", True, COL_TEXT)
    screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2,
                      SCREEN_H // 2 - msg.get_height() // 2))
