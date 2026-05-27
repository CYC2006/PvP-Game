"""
Main menu / lobby screen — primary controller.

Returns:
  ("online", None)  – user clicked ONLINE (auto-matchmaking)
  (None,     None)  – user closed the window
"""
import socket
import threading
import pygame

from game.pages.layout import (
    LOGICAL_W, LOGICAL_H,
    _TB, _SW,
    COL_BG, COL_SEP, COL_HINT, COL_TITLE,
    COL_BTN, COL_BTN_HOV, COL_BTN_BD, COL_BTN_TXT,
    COL_PL_BG, COL_PL_BD, COL_PL_NAME, COL_LEVEL,
    IC_USER, IC_COG, IC_VOLUME, IC_BOLT, IC_SERVER, IC_GAMEPAD,
    IC_CART, IC_TASKS,
    btn, cx,
)
from game.pages import game_page, characters_page, map_page, shop_page, missions_page


# ── Sidebar tab definitions ───────────────────────────────────────────────────
_TAB_W    = _SW - 20
_TAB_H    = 50
_TAB_X    = 10
_TAB_Y0   = _TB + 18
_TAB_STEP = _TAB_H + 8

IC_MAP = ''   # nf-fa-map (Nerd Fonts)

SIDEBAR_TABS = [
    ("game",       IC_GAMEPAD, "GAME"),
    ("shop",       IC_CART,    "SHOP"),
    ("characters", IC_USER,    "CHARACTERS"),
    ("map",        IC_MAP,     "MAP"),
    ("missions",   IC_TASKS,   "MISSIONS"),
]

TAB_RS = [
    pygame.Rect(_TAB_X, _TAB_Y0 + i * _TAB_STEP, _TAB_W, _TAB_H)
    for i in range(len(SIDEBAR_TABS))
]

# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Persistent chrome ─────────────────────────────────────────────────────────

def _draw_topbar(screen, font_lg, font_sm, sfx_r, set_r, mx, my,
                 gold: int = 0, gems: int = 0):
    pygame.draw.line(screen, COL_SEP, (0, _TB), (LOGICAL_W, _TB), 1)

    PY, PH = 10, 48   # vertical position & height shared by all containers
    PAD    = 12        # inner horizontal padding

    # ── Player name container (icon + name, left-aligned) ─────────────────
    pl_r = pygame.Rect(18, PY, 220, PH)
    pygame.draw.rect(screen, COL_PL_BG, pl_r, border_radius=8)
    pygame.draw.rect(screen, COL_PL_BD, pl_r, 2, border_radius=8)
    ns = font_lg.render(f"{IC_USER}  PLAYER_001", True, COL_PL_NAME)
    screen.blit(ns, (pl_r.x + PAD, pl_r.centery - ns.get_height() // 2))

    # ── Level container  [⚡ Lv.  ···  1] ────────────────────────────────
    lv_r = pygame.Rect(pl_r.right + 8, PY, 148, PH)
    pygame.draw.rect(screen, COL_PL_BG, lv_r, border_radius=8)
    pygame.draw.rect(screen, COL_PL_BD, lv_r, 2, border_radius=8)
    # Left: bolt icon + label
    lv_lbl = font_sm.render(f"{IC_BOLT}  Lv.", True, COL_LEVEL)
    screen.blit(lv_lbl, (lv_r.x + PAD,
                          lv_r.centery - lv_lbl.get_height() // 2))
    # Right: level value
    lv_val = font_lg.render("1", True, COL_LEVEL)
    screen.blit(lv_val, (lv_r.right - PAD - lv_val.get_width(),
                          lv_r.centery - lv_val.get_height() // 2))

    # ── Gold container  [[ingot] GOLD  ···  0] ────────────────────────────
    gd_r = pygame.Rect(lv_r.right + 8, PY, 190, PH)
    pygame.draw.rect(screen, COL_PL_BG, gd_r, border_radius=8)
    pygame.draw.rect(screen, (75, 62, 22), gd_r, 2, border_radius=8)
    # Left: ingot icon
    ix, iy = gd_r.x + PAD, gd_r.centery - 6
    pygame.draw.rect(screen, (175, 128, 25), (ix,     iy,     22, 12), border_radius=3)
    pygame.draw.rect(screen, (235, 190, 55), (ix + 3, iy + 2, 16,  5), border_radius=2)
    # Left: "GOLD" label
    gl_s = font_sm.render("GOLD", True, (152, 118, 45))
    screen.blit(gl_s, (ix + 28, gd_r.centery - gl_s.get_height() // 2))
    # Right: value
    gv_s = font_lg.render(str(gold), True, (225, 182, 65))
    screen.blit(gv_s, (gd_r.right - PAD - gv_s.get_width(),
                        gd_r.centery - gv_s.get_height() // 2))

    # ── Gem container  [[diamond] GEMS  ···  0] ───────────────────────────
    gm_r = pygame.Rect(gd_r.right + 8, PY, 190, PH)
    pygame.draw.rect(screen, COL_PL_BG, gm_r, border_radius=8)
    pygame.draw.rect(screen, (22, 72, 48), gm_r, 2, border_radius=8)
    # Left: gem diamond icon
    gx2, gy2 = gm_r.x + PAD + 7, gm_r.centery
    gem_pts = [(gx2, gy2 - 8), (gx2 + 7, gy2), (gx2, gy2 + 8), (gx2 - 7, gy2)]
    pygame.draw.polygon(screen, (42, 165, 100), gem_pts)
    pygame.draw.polygon(screen, (95, 230, 158), gem_pts, 1)
    # Left: "GEMS" label
    gml_s = font_sm.render("GEMS", True, (42, 138, 82))
    screen.blit(gml_s, (gm_r.x + PAD + 20, gm_r.centery - gml_s.get_height() // 2))
    # Right: value
    gmv_s = font_lg.render(str(gems), True, (85, 215, 140))
    screen.blit(gmv_s, (gm_r.right - PAD - gmv_s.get_width(),
                         gm_r.centery - gmv_s.get_height() // 2))

    # ── SFX / Settings buttons ─────────────────────────────────────────────
    for r, icon in ((sfx_r, IC_VOLUME), (set_r, IC_COG)):
        bg = COL_BTN_HOV if r.collidepoint(mx, my) else COL_BTN
        btn(screen, r, bg, COL_BTN_BD, font_lg, icon, COL_BTN_TXT, radius=8)


def _draw_sidebar(screen, font_lg, font_sm, page, mx, my):
    pygame.draw.line(screen, COL_SEP, (_SW, _TB), (_SW, LOGICAL_H), 1)

    COL_TAB_ACT    = (28,  38,  58)
    COL_TAB_ACT_BD = (60, 140, 230)
    COL_TAB_TXT_A  = (180, 215, 255)

    for (pg, icon, lbl), r in zip(SIDEBAR_TABS, TAB_RS):
        active   = (pg == page)
        hovering = (not active) and r.collidepoint(mx, my)

        if active:
            bg, bd, tc = COL_TAB_ACT, COL_TAB_ACT_BD, COL_TAB_TXT_A
        elif hovering:
            bg, bd, tc = COL_BTN_HOV, COL_BTN_BD, COL_BTN_TXT
        else:
            bg, bd, tc = COL_BTN,     COL_BTN_BD, COL_BTN_TXT

        pygame.draw.rect(screen, bg, r, border_radius=8)
        pygame.draw.rect(screen, bd, r, 2, border_radius=8)

        if active:
            pygame.draw.rect(screen, COL_TAB_ACT_BD,
                             (r.x, r.y + 6, 3, r.h - 12), border_radius=2)

        ic_s = font_sm.render(icon, True, tc)
        nm_s = font_sm.render(lbl,  True, tc)
        bx   = r.x + 14   # left-aligned with padding
        screen.blit(ic_s, (bx, r.centery - ic_s.get_height() // 2))
        screen.blit(nm_s, (bx + ic_s.get_width() + 8,
                            r.centery - nm_s.get_height() // 2))


# ── Quit confirm dialog ───────────────────────────────────────────────────────

def _draw_quit_dialog(screen: pygame.Surface,
                      font_lg: pygame.font.Font,
                      font_sm: pygame.font.Font,
                      confirm_r: pygame.Rect,
                      cancel_r:  pygame.Rect,
                      mx: int, my: int) -> None:
    """半透明遮罩 + 確認離開對話框。"""
    # 半透明暗色遮罩
    overlay = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 155))
    screen.blit(overlay, (0, 0))

    # 對話框面板
    CX  = LOGICAL_W // 2
    PW, PH = 400, 190
    panel = pygame.Rect(CX - PW // 2, LOGICAL_H // 2 - PH // 2, PW, PH)
    pygame.draw.rect(screen, (18, 22, 34), panel, border_radius=14)
    pygame.draw.rect(screen, (58, 72, 108), panel, 2, border_radius=14)

    # 標題
    title = font_lg.render("Exit Game?", True, (220, 225, 242))
    screen.blit(title, (CX - title.get_width() // 2, panel.y + 26))

    # 提示文字
    sub = font_sm.render("Are you sure you want to quit?", True, (88, 105, 145))
    screen.blit(sub, (CX - sub.get_width() // 2, panel.y + 62))

    # CANCEL 按鈕
    hov_c = cancel_r.collidepoint(mx, my)
    pygame.draw.rect(screen, COL_BTN_HOV if hov_c else COL_BTN,
                     cancel_r, border_radius=9)
    pygame.draw.rect(screen, COL_BTN_BD, cancel_r, 2, border_radius=9)
    cs = font_sm.render("CANCEL", True,
                        (210, 220, 245) if hov_c else COL_BTN_TXT)
    screen.blit(cs, (cancel_r.centerx - cs.get_width()  // 2,
                     cancel_r.centery - cs.get_height() // 2))

    # YES, QUIT 按鈕
    hov_q = confirm_r.collidepoint(mx, my)
    pygame.draw.rect(screen, (185, 45, 45) if hov_q else (130, 30, 30),
                     confirm_r, border_radius=9)
    pygame.draw.rect(screen, (235, 90, 90) if hov_q else (175, 55, 55),
                     confirm_r, 2, border_radius=9)
    qs = font_sm.render("YES, QUIT", True, (255, 205, 205))
    screen.blit(qs, (confirm_r.centerx - qs.get_width()  // 2,
                     confirm_r.centery - qs.get_height() // 2))


# ── Main entry point ──────────────────────────────────────────────────────────

def lobby_screen(screen: pygame.Surface,
                 font_lg: pygame.font.Font,
                 font_sm: pygame.font.Font,
                 clock: pygame.time.Clock) -> tuple:

    FPS          = 60
    page         = "game"
    sel_mode     = 0
    char_page_idx = 0
    map_page_idx  = 0
    gold         = 200
    gems         = 10
    confirm_quit = False

    # Top-right icon buttons
    SFX_R  = pygame.Rect(LOGICAL_W - 26 - 46 - 10 - 46, 11, 46, 46)
    SET_R  = pygame.Rect(LOGICAL_W - 26 - 46,            11, 46, 46)

    # Quit confirm dialog buttons
    _DCX       = LOGICAL_W // 2
    _DY        = LOGICAL_H // 2 - 190 // 2
    DCANCEL_R  = pygame.Rect(_DCX - 186, _DY + 120, 170, 44)
    DCONFIRM_R = pygame.Rect(_DCX + 16,  _DY + 120, 170, 44)

    while True:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()

        # ── Events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None, None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit:
                        confirm_quit = False
                    else:
                        confirm_quit = True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if confirm_quit:
                    if DCONFIRM_R.collidepoint(mx, my):
                        return None, None
                    elif DCANCEL_R.collidepoint(mx, my):
                        confirm_quit = False
                    continue

                # Sidebar tab switching
                for (pg, _, _lbl), r in zip(SIDEBAR_TABS, TAB_RS):
                    if r.collidepoint(mx, my):
                        page = pg

                if page == "game":
                    for i, r in enumerate(game_page.MODE_RS):
                        if r.collidepoint(mx, my):
                            sel_mode = i
                    if game_page.ONLINE_R.collidepoint(mx, my):
                        return "online", None

                elif page == "characters":
                    for i, r in enumerate(characters_page.CHAR_THUMB_RS):
                        if r.collidepoint(mx, my):
                            char_page_idx = i

                elif page == "map":
                    for i, r in enumerate(map_page.MAP_RS):
                        if r.collidepoint(mx, my):
                            map_page_idx = i

            if event.type == pygame.MOUSEWHEEL and page == "missions":
                missions_page.handle_scroll(event)

        # ── Render ────────────────────────────────────────────────────────
        screen.fill(COL_BG)
        _draw_topbar(screen, font_lg, font_sm, SFX_R, SET_R, mx, my, gold, gems)
        _draw_sidebar(screen, font_lg, font_sm, page, mx, my)

        if page == "game":
            game_page.draw(screen, font_lg, font_sm, mx, my, sel_mode)
        elif page == "characters":
            characters_page.draw(screen, font_lg, font_sm, char_page_idx)
        elif page == "map":
            map_page.draw(screen, font_lg, font_sm, map_page_idx)
        elif page == "shop":
            shop_page.draw(screen, font_lg, font_sm)
        elif page == "missions":
            missions_page.draw(screen, font_lg, font_sm, mx, my)

        if confirm_quit:
            _draw_quit_dialog(screen, font_lg, font_sm,
                              DCONFIRM_R, DCANCEL_R, mx, my)

        pygame.display.flip()
