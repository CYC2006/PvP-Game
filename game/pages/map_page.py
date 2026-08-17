"""
Lobby MAP page — map browser.

Layout
------
  Left column  — scrollable list of map cards (click to select)
  Right section — minimap preview (scaled render) + map details & legend

Map metadata is loaded from maps/maps_meta.json so all map info lives
in the maps/ directory alongside the obstacle JSONs.
"""
import json
import pygame
from game.pages.layout import LOGICAL_W, LOGICAL_H, _TB, _SW

# ── Load map metadata from maps/ ─────────────────────────────────────────────

def _load_maps_meta() -> list[dict]:
    with open("maps/maps_meta.json", encoding="utf-8") as f:
        raw = json.load(f)
    result = []
    for m in raw:
        result.append({
            "id":         m["id"],
            "file":       m["file"],
            "name":       m["name"],
            "desc":       m["desc"],
            "tags":       [(t["label"], t["destructible"], tuple(t["color"])) for t in m["tags"]],
            "minimap_bg": tuple(m["minimap_bg"]),
            "width":      m.get("width", 1920),
            "height":     m.get("height", 1080),
            "portals":    m.get("portals", []),
        })
    return result


MAPS: list[dict] = _load_maps_meta()

# Colour mapping used when rendering the minimap
_KIND_COLOUR: dict = {
    "box_normal":  (180, 125, 65),
    "box_special": (200, 145, 75),
    "rock_1":      (110, 122, 135),
    "rock_2":      (100, 112, 128),
    "tree_1":      ( 52, 148,  68),
}

# ── Layout ────────────────────────────────────────────────────────────────────
_PAD_L, _PAD_R = 14, 10
_IX  = _SW + _PAD_L                    # 184
_IW  = LOGICAL_W - _IX - _PAD_R       # 1086

_LW  = 230                             # left card-list width
_RX  = _IX + _LW + 14                 # right section x
_RW  = (_IX + _IW) - _RX              # right section width (~826)

_DET_Y = _TB + 12                     # content top  (80)
_DET_B = LOGICAL_H - 10              # content bottom (710)
_DET_H = _DET_B - _DET_Y             # 630

# Minimap preview: full right-section width, 16∶9
_PREV_W = _RW - 0
_PREV_H = int(_PREV_W * 9 / 16)

# Map card: tall enough for name + 3 tag rows + padding
_CARD_H   = 126
_CARD_GAP = 10

MAP_RS: list[pygame.Rect] = [
    pygame.Rect(_IX, _DET_Y + i * (_CARD_H + _CARD_GAP), _LW, _CARD_H)
    for i in range(len(MAPS))
]

# ── Minimap cache ─────────────────────────────────────────────────────────────
_minimap_cache: dict[tuple, pygame.Surface] = {}


def _build_minimap(map_def: dict, w: int, h: int) -> pygame.Surface:
    from game.obstacle import load_map

    map_w = map_def["width"]
    map_h = map_def["height"]

    surf = pygame.Surface((w, h))
    surf.fill(map_def["minimap_bg"])

    # Subtle grid
    grid_col = tuple(max(0, c + 6) for c in map_def["minimap_bg"])
    GRID = 80
    sx = w / map_w
    sy = h / map_h
    for gx in range(0, map_w, GRID):
        pygame.draw.line(surf, grid_col, (int(gx * sx), 0), (int(gx * sx), h))
    for gy in range(0, map_h, GRID):
        pygame.draw.line(surf, grid_col, (0, int(gy * sy)), (w, int(gy * sy)))

    obstacles = load_map(map_def["file"])

    # Draw trees first
    for obs in obstacles.values():
        if obs.kind != "tree_1":
            continue
        col  = _KIND_COLOUR.get(obs.kind, (120, 120, 120))
        dark = tuple(max(0, c - 30) for c in col)
        ox, oy = int(obs.x * sx), int(obs.y * sy)
        r = max(4, int(obs.width * sx * obs.radius_ratio / 2))
        pygame.draw.circle(surf, dark, (ox, oy), r + 2)
        pygame.draw.circle(surf, col,  (ox, oy), r)

    # Draw rocks
    for obs in obstacles.values():
        if obs.kind not in ("rock_1", "rock_2"):
            continue
        col = _KIND_COLOUR.get(obs.kind, (120, 120, 120))
        ox, oy = int(obs.x * sx), int(obs.y * sy)
        r = max(3, int(obs.width * sx * obs.radius_ratio / 2))
        pygame.draw.circle(surf, (80, 88, 100), (ox, oy), r + 2)
        pygame.draw.circle(surf, col,           (ox, oy), r)

    # Draw boxes
    for obs in obstacles.values():
        if obs.kind not in ("box_normal", "box_special"):
            continue
        col = _KIND_COLOUR.get(obs.kind, (140, 100, 60))
        ow = max(3, int(obs.width  * sx))
        oh = max(3, int(obs.height * sy))
        ox, oy = int(obs.x * sx) - ow // 2, int(obs.y * sy) - oh // 2
        pygame.draw.rect(surf, (100, 68, 35), (ox - 1, oy - 1, ow + 2, oh + 2))
        pygame.draw.rect(surf, col,           (ox, oy, ow, oh))

    # Draw portals
    PW_MINI = max(8, int(20 * sx))
    for portal in map_def.get("portals", []):
        if "x" in portal:
            # Left / right portal (vertical slab, purple)
            px     = portal["x"]
            sy1    = int(portal["y_min"] * sy)
            sy2    = int(portal["y_max"] * sy)
            ph     = sy2 - sy1
            rect_x = 0 if px == 0 else w - PW_MINI
            for col, inset in [((80, 30, 120), 0), ((140, 60, 200), 2), ((190, 120, 255), 4)]:
                r = pygame.Rect(rect_x + inset, sy1 + inset,
                                PW_MINI - inset * 2, ph - inset * 2)
                if r.width > 0 and r.height > 0:
                    pygame.draw.rect(surf, col, r)
            cx_line = rect_x + PW_MINI // 2
            pygame.draw.line(surf, (230, 180, 255), (cx_line, sy1 + 4), (cx_line, sy2 - 4), 1)
        elif "y" in portal:
            # Top / bottom portal (horizontal slab, pink)
            PH_MINI = max(8, int(20 * sy))
            py_val  = portal["y"]
            sx1     = int(portal["x_min"] * sx)
            sx2     = int(portal["x_max"] * sx)
            pw      = sx2 - sx1
            rect_y  = 0 if py_val == 0 else h - PH_MINI
            for col, inset in [((120, 30, 80), 0), ((200, 60, 140), 2), ((255, 120, 190), 4)]:
                r = pygame.Rect(sx1 + inset, rect_y + inset,
                                pw - inset * 2, PH_MINI - inset * 2)
                if r.width > 0 and r.height > 0:
                    pygame.draw.rect(surf, col, r)
            cy_line = rect_y + PH_MINI // 2
            pygame.draw.line(surf, (255, 200, 230), (sx1 + 4, cy_line), (sx2 - 4, cy_line), 1)

    return surf


def _get_minimap(map_def: dict, w: int, h: int) -> pygame.Surface:
    key = (map_def["id"], w, h)
    if key not in _minimap_cache:
        _minimap_cache[key] = _build_minimap(map_def, w, h)
    return _minimap_cache[key]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_wrapped(screen: pygame.Surface, font: pygame.font.Font,
                  text: str, x: int, y: int,
                  max_w: int, max_h: int, color) -> None:
    words = text.split()
    lines: list[str] = []
    line:  list[str] = []
    for word in words:
        test = ' '.join(line + [word])
        if font.size(test)[0] <= max_w:
            line.append(word)
        else:
            if line:
                lines.append(' '.join(line))
            line = [word]
    if line:
        lines.append(' '.join(line))
    lh = font.get_height() + 3
    for i, ln in enumerate(lines):
        if i * lh >= max_h:
            break
        screen.blit(font.render(ln, True, color), (x, y + i * lh))


# ── Main draw entry point ─────────────────────────────────────────────────────

def draw(screen: pygame.Surface,
         font_lg: pygame.font.Font,
         font_sm: pygame.font.Font,
         sel_map: int) -> None:

    map_def = MAPS[sel_map]

    # ── Left: map card list ───────────────────────────────────────────────
    for i, (m, r) in enumerate(zip(MAPS, MAP_RS)):
        sel = (i == sel_map)

        pygame.draw.rect(screen,
                         (28, 45, 68) if sel else (20, 26, 40), r, border_radius=10)
        pygame.draw.rect(screen,
                         (68, 148, 235) if sel else (38, 50, 72), r, 2, border_radius=10)

        if sel:
            pygame.draw.rect(screen, (68, 148, 235),
                             (r.x, r.y + 8, 3, r.h - 16), border_radius=2)

        # Map name
        nc = (185, 218, 255) if sel else (90, 110, 145)
        ns = font_lg.render(m["name"], True, nc)
        screen.blit(ns, (r.x + 14, r.y + 12))

        # Portal map: show small portal indicator badge
        if m.get("portals"):
            badge_col = (130, 60, 200) if sel else (80, 40, 130)
            pygame.draw.rect(screen, badge_col,
                             (r.x + r.w - 36, r.y + 10, 28, 14), border_radius=4)
            bt = font_sm.render("TP", True, (220, 170, 255))
            screen.blit(bt, (r.x + r.w - 36 + (28 - bt.get_width()) // 2,
                             r.y + 10 + (14 - bt.get_height()) // 2))

        # Obstacle colour dots — stacked vertically from bottom of name
        dot_y = r.y + 12 + ns.get_height() + 8
        dot_x = r.x + 14
        for lbl, _destr, dcol in m["tags"]:
            pygame.draw.circle(screen, dcol, (dot_x + 5, dot_y + 7), 5)
            ls = font_sm.render(lbl, True,
                                (115, 142, 178) if sel else (75, 92, 118))
            screen.blit(ls, (dot_x + 14, dot_y))
            dot_y += font_sm.get_height() + 4

    # ── Right: minimap preview ────────────────────────────────────────────
    # Fit the map inside the envelope while preserving its true aspect ratio.
    map_w  = map_def["width"]
    map_h  = map_def["height"]
    scale  = min(_PREV_W / map_w, _PREV_H / map_h)
    disp_w = int(map_w * scale)
    disp_h = int(map_h * scale)
    off_x  = (_PREV_W - disp_w) // 2
    off_y  = (_PREV_H - disp_h) // 2

    frame_rect = pygame.Rect(_RX, _DET_Y, _PREV_W, _PREV_H)
    # Dark letterbox background (clearly distinct from any map floor colour)
    pygame.draw.rect(screen, (10, 10, 16), frame_rect, border_radius=4)
    # Map surface at true aspect ratio, centred inside the frame
    prev_surf = _get_minimap(map_def, disp_w, disp_h)
    screen.blit(prev_surf, (_RX + off_x, _DET_Y + off_y))
    # Thick border around the whole frame
    pygame.draw.rect(screen, (68, 92, 138), frame_rect, 3, border_radius=4)

    # ── Right: map info below preview ─────────────────────────────────────
    INFO_Y = _DET_Y + _PREV_H + 10
    INFO_X = _RX

    # Map name
    nm_s = font_lg.render(map_def["name"], True, (210, 228, 252))
    screen.blit(nm_s, (INFO_X, INFO_Y))
    INFO_Y += nm_s.get_height() + 6

    # Description
    _draw_wrapped(screen, font_sm, map_def["desc"],
                  INFO_X, INFO_Y,
                  _RW, 60, (128, 152, 192))
    INFO_Y += 54  # ~3 lines

    # Obstacle legend
    LEGEND_X = INFO_X
    for lbl, destr, dcol in map_def["tags"]:
        sw_r = pygame.Rect(LEGEND_X, INFO_Y + 3, 12, 12)
        pygame.draw.rect(screen, dcol, sw_r, border_radius=3)

        destr_txt = "destructible" if destr else "indestructible"
        full_lbl  = f"{lbl}  ({destr_txt})"
        ls = font_sm.render(full_lbl, True, (105, 128, 165))
        screen.blit(ls, (LEGEND_X + 18, INFO_Y))

        LEGEND_X += 18 + ls.get_width() + 22
