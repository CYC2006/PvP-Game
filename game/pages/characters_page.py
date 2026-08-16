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
    'Agent':    (3, 3, 2, 4),
    'Vince':    (4, 1, 5, 3),
    'Marksman': (4, 2, 3, 2),
    'Hunter':   (5, 3, 1, 3),
    'Robot':    (3, 2, 3, 2),
    'Pioneer':  (3, 4, 4, 2),
    'Assassin': (3, 5, 1, 4),
    'Poisoner': (2, 3, 2, 5),
    'Zombie':   (3, 3, 4, 1),
}

# ── Skill data: fixed order → RMB / SPACE / E / R ────────────────────────────
# (skill_name, key_label, cooldown_secs, description)
_SKILLS: dict = {
    'Agent': [
        ("POWER SHOT",    "RMB",   4,
         "Fires a single oversized bullet — twice the normal size — trailing "
         "a glowing afterimage. It flies dead straight for double damage and "
         "knocks the target back on hit."),
        ("DASH",          "SPACE", 3,
         "Lunges forward in a quick burst of speed, moving in whatever "
         "direction you're currently heading."),
        ("FLASH GRENADE", "E",     6,
         "Lobs a grenade that flashes on landing, blinding and disorienting "
         "any enemy caught in the blast."),
        ("MERCURY BARRAGE","F",    12,
         "Locks your aim and unleashes a fan-shaped barrage of 7 volleys, "
         "5 bullets each. Movement and your rune stay usable, but shooting "
         "and other skills are locked until it finishes."),
    ],
    'Vince': [
        ("AIRSTRIKE",     "RMB",   5,
         "Calls in a line of bombs along your aim, each impact landing a "
         "moment after the last to blanket a wide area."),
        ("TAUNT",         "SPACE", 9,
         "Releases a lavender shockwave that expands outward, stunning any "
         "enemy it touches for 0.8 seconds and dragging them helplessly "
         "toward you."),
        ("FRAG GRENADE",  "E",     6,
         "Hurls a grenade that explodes on impact, dealing heavy damage to "
         "everyone caught in the blast."),
        ("GIANT FORM",    "F",     20,
         "Transforms you into a massive giant for a limited time, growing "
         "far larger and tougher while hitting much harder."),
    ],
    'Marksman': [
        ("IMPACT ROUND",  "RMB",   4,
         "Fires an explosive round that detonates on contact, damaging "
         "everything close to the point of impact."),
        ("CHARGE",        "SPACE", 9,
         "Dashes toward your cursor, crashing through debris and trees but "
         "halted by solid obstacles. Slamming into an enemy stops the dash "
         "and stuns them for 1 second."),
        ("AUTO TURRET",   "E",     8,
         "Deploys a stationary turret with 180 HP that automatically fires "
         "at nearby enemies, matching your gun's damage and fire rate. It "
         "slowly loses HP over time and also takes damage from enemy fire."),
        ("ROLLING BARRAGE","F",    10,
         "Calls in 18 waves of 3 strikes that creep outward toward your "
         "cursor in rapid succession, each strike marked by a crosshair a "
         "moment before it detonates."),
    ],
    'Hunter': [
        ("AIR CANNON",    "RMB",   4,
         "Fires an invisible blast of air that launches any enemy it hits, "
         "though it deals no damage. Landing the hit instantly resets this "
         "skill's cooldown."),
        ("MINI GRENADES", "SPACE", 8,
         "Launches you backward away from your aim while scattering a "
         "cluster of small grenades that each explode independently where "
         "they land."),
        ("LOG BARRIER",   "E",     10,
         "Plants three crystalline log chunks in a fan ahead of you, "
         "sealing off the path forward and blocking enemy movement and "
         "bullets."),
        ("PHANTOM CLOAK",  "F",    15,
         "Turns you invisible for 3 seconds and doubles your movement "
         "speed, though you still take damage. You can keep shooting and "
         "using skills, and briefly flicker into view every so often."),
    ],
    'Robot': [
        ("OVERLOAD", "RMB", 10,
         "Doubles your movement speed for 3 seconds — a pure mobility burst "
         "with no other effect."),
        ("MARK RECALL", "SPACE", 6,
         "Dashes forward and drops a mark at your starting point. Press "
         "Space again within 4 seconds to instantly teleport back to it."),
        ("PULSE RING", "E",  9,
         "Bursts an electromagnetic ring outward around you, stunning any "
         "enemy it touches for 1 second. A marker also orbits the ring's "
         "edge — press E again within 4 seconds to instantly blink to it."),
        ("PUSH ZONE", "F", 5,
         "Projects a force field toward your cursor that launches and "
         "stuns any enemy caught inside for 1 second."),
    ],
    'Pioneer': [
        ("STUN ROUND",    "RMB",   6,
         "Fires a specialized round that stuns the target on impact, "
         "briefly halting their movement and leaving them open to "
         "follow-up fire."),
        ("TACTICAL JUMP",  "SPACE", 8,
         "Leaps toward your aim, instantly refilling your magazine and "
         "canceling any reload in progress. You're invincible in the air, "
         "flying over obstacles and immune to all projectiles."),
        ("FORCE SHIELD", "E", 12,
         "Surrounds you with a shield that fully absorbs up to 80 HP of "
         "damage for 5 seconds, with no overflow to your health. When it "
         "breaks or expires, it releases an expanding shockwave ring that "
         "knocks back and stuns the first enemy it touches for 0.5 seconds."),
        ("CLONE CORPS", "F", 18,
         "Summons two semi-transparent clones flanking you. For 8 seconds, "
         "every basic attack fires three parallel shots — one from each "
         "clone — at no extra ammo cost."),
    ],
    'Assassin': [
        ("BLADE STRIKE",  "RMB",   5,
         "Hurls a powered shuriken that pierces through every enemy in its "
         "path, dealing concentrated damage."),
        ("SPEED SURGE",   "SPACE", 10,
         "Activates a short burst of greatly increased movement speed."),
        ("SMOKE SCREEN",  "E",     6,
         "Deploys a smoke grenade that fills the area with a lingering "
         "cloud, blocking sight for both sides."),
        ("SHADOW RUSH",   "F",     8,
         "Dashes swiftly toward your cursor and releases a spinning blade "
         "arc on arrival, striking any enemy caught in the sweep."),
    ],
    'Poisoner': [
        ("POISON POOL", "RMB", 9,
         "Fires a toxic projectile that bursts into a lingering poison "
         "pool on contact. Enemies standing in it are slowed by 20%, take "
         "3 damage per pulse, and build up to 2 stacks of poison the "
         "longer they stay."),
        ("TOXIC SPRINT", "SPACE", 8,
         "Dashes forward at 20% increased speed for 3 seconds, leaving a "
         "trail of afterimages and 9 small poison pools behind you. "
         "Standing in one stacks poison, up to 2 stacks from this skill."),
        ("TOXIC RESONANCE", "E", 10,
         "For 3 seconds, a green shockwave ring pulses outward from you "
         "again and again — up to 5 in total. Each ring that touches an "
         "enemy deals 3 damage, adds a poison stack, and heals you for "
         "3 times their current poison stacks."),
        ("—", "F",     0, "Skill under development."),
    ],
    'Zombie': [
        ("ENERGY SPRINT", "RMB", 0,
         "Hold RMB to sprint at greatly increased speed, drawing from an "
         "energy meter that drains while sprinting and slowly refills when "
         "released. Sprint speed fades as the meter runs low, but never "
         "drops below a light jog. No cooldown — it runs on the energy "
         "meter instead."),
        ("GROUND POUND",  "SPACE", 4,
         "Leaps toward your aim and slams down, knocking back and "
         "stunning enemies caught in the shockwave. Also instantly refills "
         "your magazine and cancels any reload in progress."),
        ("BLOODLUST", "E",     10,
         "For 4 seconds, you move and act with no stiffness, take 50% "
         "less damage, and heal for half of the damage dealt by your "
         "basic attacks. A dark red glow pools beneath your feet."),
        ("CORROSIVE SPEW", "F",   8,
         "Locks your aim and freezes you in place for 0.5 seconds, then "
         "spews 10 waves of 3 orbs outward in a growing spray, each wave "
         "landing farther and wider than the last. Orbs deal 6-8 damage "
         "on contact, and the very first hit also stuns for 1 second."),
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
    char_name = char["name"]

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
    atk, agi, dfs, utl = _RATINGS.get(char_name, (3, 3, 3, 3))
    rating_rows = [
        ("ATTACK",  atk, (255, 198,  52)),
        ("DEFENSE", dfs, (102, 172, 248)),
        ("AGILITY", agi, ( 72, 218, 158)),
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

    # ── Right — 2×2 skill grid (RMB / SPACE / E / F) ─────────────────────
    SK_GAP = 10
    SK_W   = (RW - SK_GAP) // 2
    SK_H   = (DET_H - SK_GAP) // 2

    skills = _SKILLS.get(char_name, [("—", k, 0, "Skill under development.")
                                     for k in ("RMB", "SPACE", "E", "F")])
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
        HDR_H = font_lg.get_height()

        # Key badge — vertically centred relative to font_lg row height
        badge_top = HDR_Y + (HDR_H - 24) // 2
        badge_r = pygame.Rect(skx + 10, badge_top, BADGE_W, 24)
        pygame.draw.rect(screen, (30, 42, 66), badge_r, border_radius=5)
        pygame.draw.rect(screen, (55, 75, 115), badge_r, 1, border_radius=5)
        bk = font_sm.render(skey, True, (110, 148, 205))
        screen.blit(bk, (badge_r.centerx - bk.get_width() // 2,
                          badge_r.centery - bk.get_height() // 2))

        # Skill name
        sn_c = (185, 210, 248) if sname != "—" else (55, 68, 95)
        screen.blit(font_lg.render(sname, True, sn_c),
                    (skx + 10 + BADGE_W + 8, HDR_Y))

        # Cooldown (right-aligned, vertically centred with font_lg row)
        if scd > 0:
            cd_s = font_sm.render(f"{IC_CLOCK}  {scd}s", True, (95, 140, 195))
            cd_top = HDR_Y + (HDR_H - cd_s.get_height()) // 2
            screen.blit(cd_s, (skx + SK_W - cd_s.get_width() - 10, cd_top))

        # Separator
        SEP_Y = HDR_Y + font_lg.get_height() + 6
        pygame.draw.line(screen, (38, 50, 75),
                         (skx + 10, SEP_Y), (skx + SK_W - 10, SEP_Y), 1)

        # Description
        DESC_Y = SEP_Y + 8
        dc = (135, 160, 198) if sname != "—" else (55, 68, 95)
        _draw_wrapped(screen, font_sm, sdesc,
                      skx + 12, DESC_Y, SK_W - 24, sky + SK_H - DESC_Y - 8, dc)
