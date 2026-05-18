"""
Lobby CHARACTERS page.

Layout
------
  Top area (detail view):
    Left column  — sprite | name | base stats | star ratings
    Right section — 2×2 skill grid (RMB / SPACE / E / R)

  Bottom strip — 9 character thumbnail buttons (click to switch)
"""
import pygame
from game.pages.layout import LOGICAL_W, LOGICAL_H, _TB, _SW
from game.charselect import CHARACTERS as _CHAR_LIST, _load_sprite as _cs_load_sprite

# ── Icons ────────────────────────────────────────────────────────────────
IC_STAR  = chr(0xf005)   # fa-star  (filled)
IC_STAR0 = chr(0xf006)   # fa-star-o (empty)
IC_CLOCK = chr(0xf017)   # fa-clock-o (cooldown)

# ── Per-character ratings (ATK, AGI, DEF, UTL) out of 5 ──────────────────────
_RATINGS: dict = {
    'hitman1':    (3, 3, 2, 4),
    'manBlue':    (4, 1, 5, 3),
    'manBrown':   (4, 2, 3, 2),
    'manOld':     (5, 3, 1, 3),
    'robot1':     (3, 2, 3, 2),
    'soldier1':   (3, 4, 4, 2),
    'survivor1':  (3, 5, 1, 4),
    'womanGreen': (2, 3, 2, 5),
    'zoimbie1':   (3, 3, 4, 1),
}

# ── Skill data: fixed order → RMB / SPACE / E / R ────────────────────────────
# (skill_name, key_label, cooldown_secs, description)
_SKILLS: dict = {
    'hitman1': [
        ("POWER SHOT",    "RMB",   5,
         "Fire a single enhanced bullet — twice the normal size, double damage, "
         "and zero spread. A glowing afterimage trail marks its path through the air."),
        ("DASH",          "SPACE", 3,
         "Lunge in the current movement direction for a rapid burst of speed. "
         "Requires an active movement input to trigger; no direction, no dash."),
        ("FLASH GRENADE", "E",     8,
         "Lobs a stun grenade that detonates on landing. "
         "Any enemy inside the blast radius is briefly blinded and disoriented."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'manBlue': [
        ("AIRSTRIKE",     "RMB",   5,
         "Calls a sequence of bombs along the aimed trajectory. "
         "Impacts land in a line with a short delay, covering a wide zone."),
        ("CHARGE",        "SPACE", 6,
         "Surge toward the cursor at high speed for a fixed distance. "
         "Closes gaps aggressively or repositions through open terrain."),
        ("FRAG GRENADE",  "E",     8,
         "Hurls a fragmentation grenade that explodes on impact, "
         "dealing heavy damage to all enemies within the blast radius."),
        ("GIANT FORM",    "R",     20,
         "Transforms into a massive giant for a limited time. "
         "Greatly increases body size, armor thickness, and raw damage output."),
    ],
    'manBrown': [
        ("IMPACT ROUND",  "RMB",   4,
         "Fires an explosive bullet that detonates on contact. "
         "Deals burst damage to everything in a small radius around the point of impact."),
        ("—",             "SPACE", 0,
         "Skill under development."),
        ("PROXIMITY MINE","E",     10,
         "Places a hidden mine at the current position. "
         "Triggers automatically when an enemy steps within detection range."),
        ("—",             "R",     0,
         "Skill under development."),
    ],
    'manOld': [
        ("—",             "RMB",   0,
         "Skill under development."),
        ("MINI GRENADES", "SPACE", 4,
         "Scatters a cluster of small grenades in an arc. "
         "Each grenade lands independently and detonates with its own small explosion."),
        ("LOG BARRIER",   "E",     10,
         "Erects wooden barriers in the aimed direction. "
         "Blocks movement and line of sight, forcing enemies to reposition."),
        ("PHANTOM CLOAK",  "R",    15,
         "Vanishes for 3 seconds with 2× movement speed. "
         "You can still shoot and use all skills while invisible. "
         "Every 0.5 s you briefly flicker into view — and you still take damage."),
    ],
    'robot1': [
        ("—", "RMB",   0, "Skill under development."),
        ("MARK RECALL", "SPACE", 6,
         "Dashes in your movement direction and plants a mark at the origin. "
         "Press Space again within 3 seconds to instantly teleport back. "
         "A yellow timer bar above your head shows the recall window — only you can see it."),
        ("—", "E",     0, "Skill under development."),
        ("PUSH ZONE", "R", 5,
         "Projects a 160×100 px force field toward the cursor. "
         "Enemies caught inside are launched away and stunned for 1 second. "
         "Only you see the targeting rectangle before it fires."),
    ],
    'soldier1': [
        ("STUN ROUND",    "RMB",   6,
         "Fires a specialized round that stuns the target on impact. "
         "Briefly halts enemy movement, leaving them exposed to follow-up fire."),
        ("TACTICAL JUMP",  "SPACE", 8,
         "Leaps 150 px toward the aimed direction. "
         "Instantly refills the magazine and cancels any reload in progress. "
         "Invincible while airborne — can fly over obstacles and is immune to all projectiles."),
        ("—", "E",     0, "Skill under development."),
        ("CLONE CORPS", "R", 20,
         "Summons two semi-transparent clones flanking your position. "
         "For 8 seconds, every basic attack fires three parallel shots — "
         "one from each clone — without extra ammo cost."),
    ],
    'survivor1': [
        ("BLADE STRIKE",  "RMB",   5,
         "Hurls a powered shuriken in the aimed direction. "
         "Deals concentrated damage and cuts through any enemy in its path."),
        ("SPEED SURGE",   "SPACE", 10,
         "Activates a short burst of enhanced movement speed. "
         "Use it to close the gap on an enemy or escape a dangerous situation."),
        ("SMOKE SCREEN",  "E",     8,
         "Deploys a smoke grenade creating a persistent cloud. "
         "Both sides lose visibility in the area, ideal for breaking line of sight."),
        ("SHADOW RUSH",   "R",     7,
         "Dashes swiftly toward the cursor, releasing a spinning blade arc "
         "upon arrival that strikes any enemy caught in the sweep."),
    ],
    'womanGreen': [
        ("POISON POOL", "RMB", 9,
         "Fires a toxic projectile that splashes on contact, creating a poison zone. "
         "Enemies caught inside take continuous damage and move 20% slower."),
        ("—", "SPACE", 0, "Skill under development."),
        ("—", "E",     0, "Skill under development."),
        ("—", "R",     0, "Skill under development."),
    ],
    'zoimbie1': [
        ("—", "RMB",   0, "Skill under development."),
        ("—", "SPACE", 0, "Skill under development."),
        ("—", "E",     0, "Skill under development."),
        ("—", "R",     0, "Skill under development."),
    ],
}

# ── Layout (mirrors draw() — computed once at module level) ───────────────────
_PAD_L, _PAD_R = 14, 10
_IX   = _SW + _PAD_L
_IW   = LOGICAL_W - _IX - _PAD_R

_STRIP_H = 90
_STRIP_Y  = LOGICAL_H - _STRIP_H

_N_CHARS = len(_CHAR_LIST)
_T_GAP   = 8
_TW      = (_IW - _T_GAP * (_N_CHARS - 1)) // _N_CHARS
_TH      = _STRIP_H - 18

# Thumbnail rects — used by lobby.py for click detection
CHAR_THUMB_RS: list[pygame.Rect] = [
    pygame.Rect(_IX + i * (_TW + _T_GAP), _STRIP_Y + 8, _TW, _TH)
    for i in range(_N_CHARS)
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_wrapped(screen: pygame.Surface, font: pygame.font.Font,
                  text: str, x: int, y: int,
                  max_w: int, max_h: int, color) -> None:
    """Word-wrap `text` and draw within the given bounding box."""
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
         char_idx: int) -> None:

    char     = _CHAR_LIST[char_idx]
    char_key = char["char_key"]

    DET_Y = _TB + 12
    DET_H = _STRIP_Y - DET_Y - 8

    LW  = 268
    RX  = _IX + LW + 12
    RW  = (_IX + _IW) - RX

    # ── Thumbnail strip ───────────────────────────────────────────────────
    pygame.draw.line(screen, (36, 46, 66),
                     (_IX, _STRIP_Y - 5), (_IX + _IW, _STRIP_Y - 5), 1)

    for i, c in enumerate(_CHAR_LIST):
        r   = CHAR_THUMB_RS[i]
        sel = (i == char_idx)

        pygame.draw.rect(screen,
                         (28, 48, 72) if sel else (20, 26, 40), r, border_radius=6)
        pygame.draw.rect(screen,
                         (72, 150, 238) if sel else (38, 48, 70), r, 2, border_radius=6)

        sp = _cs_load_sprite(c)
        if sp.get_width() > 0 and sp.get_height() > 0:
            max_th = _TH - font_sm.get_height() - 6
            sc  = min((_TW - 8) / sp.get_width(), max_th / sp.get_height())
            sw2 = max(1, int(sp.get_width()  * sc))
            sh2 = max(1, int(sp.get_height() * sc))
            mini = pygame.transform.scale(sp, (sw2, sh2))
            screen.blit(mini, (r.centerx - sw2 // 2, r.y + 2))

        nc = (180, 215, 255) if sel else (80, 100, 135)
        ns = font_sm.render(c["name"], True, nc)
        screen.blit(ns, (r.centerx - ns.get_width() // 2,
                          r.y + _TH - ns.get_height() - 2))

    # ── Left column — sprite box ──────────────────────────────────────────
    SP_H    = 210
    sp_rect = pygame.Rect(_IX, DET_Y, LW, SP_H)
    pygame.draw.rect(screen, (20, 26, 40), sp_rect, border_radius=10)
    pygame.draw.rect(screen, (38, 50, 75), sp_rect, 2, border_radius=10)

    sp = _cs_load_sprite(char)
    if sp.get_width() > 0 and sp.get_height() > 0:
        sc  = min((LW - 16) / sp.get_width(), (SP_H - 16) / sp.get_height())
        sw2 = max(1, int(sp.get_width()  * sc))
        sh2 = max(1, int(sp.get_height() * sc))
        big = pygame.transform.scale(sp, (sw2, sh2))
        screen.blit(big, (_IX + LW // 2 - sw2 // 2, DET_Y + SP_H // 2 - sh2 // 2))

    # Character name
    nm_s = font_lg.render(char["name"], True, (220, 232, 250))
    nm_y = DET_Y + SP_H + 6
    screen.blit(nm_s, (_IX + LW // 2 - nm_s.get_width() // 2, nm_y))

    # ── Left column — stats + ratings panel ──────────────────────────────
    PANEL_Y = nm_y + nm_s.get_height() + 6
    PANEL_H = DET_Y + DET_H - PANEL_Y
    pan_r   = pygame.Rect(_IX, PANEL_Y, LW, PANEL_H)
    pygame.draw.rect(screen, (20, 26, 40), pan_r, border_radius=10)
    pygame.draw.rect(screen, (38, 50, 75), pan_r, 2, border_radius=10)

    LBL_X = _IX + 10
    VAL_X = _IX + LW - 8
    sy    = PANEL_Y + 10

    spd = char["speed"]
    rt  = char["reload_time"]
    fi  = char["fire_interval"]
    stats_rows = [
        ("HP",       str(char["hp"])   if char["hp"]    else "—"),
        ("SPEED",    f"{spd} px/s"     if spd           else "—"),
        ("GUN",      char["gun"]       if char["gun"]   else "—"),
        ("DAMAGE",   char["damage"]    if char["damage"] else "—"),
        ("AMMO",     str(char["ammo"]) if char["ammo"]  else "—"),
        ("RELOAD",   f"{rt}s"         if rt            else "—"),
        ("INTERVAL", f"{fi}s"         if fi            else "—"),
    ]
    for lbl, val in stats_rows:
        ls = font_sm.render(lbl, True, (90, 112, 155))
        vs = font_sm.render(val, True, (195, 210, 232))
        screen.blit(ls, (LBL_X, sy))
        screen.blit(vs, (VAL_X - vs.get_width(), sy))
        sy += font_sm.get_height() + 3

    # Divider
    sy += 4
    pygame.draw.line(screen, (38, 50, 75),
                     (_IX + 8, sy), (_IX + LW - 8, sy), 1)
    sy += 8

    # Star ratings
    atk, agi, dfs, utl = _RATINGS.get(char_key, (3, 3, 3, 3))
    rating_rows = [
        ("ATTACK",  atk, (255, 198,  52)),
        ("AGILITY", agi, ( 72, 218, 158)),
        ("DEFENSE", dfs, (102, 172, 248)),
        ("UTILITY", utl, (218, 142, 255)),
    ]
    star_w     = font_sm.size(IC_STAR)[0]
    star_gap   = 3
    stars_span = 5 * star_w + 4 * star_gap

    for rname, rval, rcol in rating_rows:
        screen.blit(font_sm.render(rname, True, (90, 112, 155)), (LBL_X, sy))
        sx0 = _IX + LW - stars_span - 10
        for si in range(5):
            ic  = IC_STAR if si < rval else IC_STAR0
            col = rcol    if si < rval else (45, 55, 80)
            screen.blit(font_sm.render(ic, True, col),
                        (sx0 + si * (star_w + star_gap), sy))
        sy += font_sm.get_height() + 5

    # ── Right — 2×2 skill grid (RMB / SPACE / E / R) ─────────────────────
    SK_GAP = 10
    SK_W   = (RW - SK_GAP) // 2
    SK_H   = (DET_H - SK_GAP) // 2

    skills = _SKILLS.get(char_key, [("—", k, 0, "Skill under development.")
                                     for k in ("RMB", "SPACE", "E", "R")])
    BADGE_W = 54

    for si, (sname, skey, scd, sdesc) in enumerate(skills):
        col = si % 2
        row = si // 2
        skx = RX + col * (SK_W + SK_GAP)
        sky = DET_Y + row * (SK_H + SK_GAP)
        sr  = pygame.Rect(skx, sky, SK_W, SK_H)

        pygame.draw.rect(screen, (20, 26, 40), sr, border_radius=10)
        pygame.draw.rect(screen, (38, 50, 75), sr, 2, border_radius=10)

        HDR_Y = sky + 12

        # Key badge
        badge_r = pygame.Rect(skx + 10, HDR_Y - 3, BADGE_W, 24)
        pygame.draw.rect(screen, (30, 42, 66), badge_r, border_radius=5)
        pygame.draw.rect(screen, (55, 75, 115), badge_r, 1, border_radius=5)
        bk = font_sm.render(skey, True, (110, 148, 205))
        screen.blit(bk, (badge_r.centerx - bk.get_width() // 2,
                          badge_r.centery - bk.get_height() // 2))

        # Skill name
        sn_c = (185, 210, 248) if sname != "—" else (55, 68, 95)
        screen.blit(font_lg.render(sname, True, sn_c),
                    (skx + 10 + BADGE_W + 8, HDR_Y - 1))

        # Cooldown (right-aligned in header row)
        if scd > 0:
            cd_s = font_sm.render(f"{IC_CLOCK}  {scd}s", True, (95, 140, 195))
            screen.blit(cd_s, (skx + SK_W - cd_s.get_width() - 10, HDR_Y + 4))

        # Separator
        SEP_Y = HDR_Y + font_lg.get_height() + 6
        pygame.draw.line(screen, (38, 50, 75),
                         (skx + 10, SEP_Y), (skx + SK_W - 10, SEP_Y), 1)

        # Description
        DESC_Y = SEP_Y + 8
        dc = (135, 160, 198) if sname != "—" else (55, 68, 95)
        _draw_wrapped(screen, font_sm, sdesc,
                      skx + 12, DESC_Y, SK_W - 24, sky + SK_H - DESC_Y - 8, dc)
