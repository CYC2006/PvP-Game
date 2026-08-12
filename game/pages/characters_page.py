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
        ("POWER SHOT",    "RMB",   5,
         "Fire a single enhanced bullet — twice the normal size, double damage, "
         "zero spread, and a knockback on hit. A glowing afterimage trail marks its path."),
        ("DASH",          "SPACE", 3,
         "Lunge in the current movement direction for a rapid burst of speed. "
         "Requires an active movement input to trigger; no direction, no dash."),
        ("FLASH GRENADE", "E",     8,
         "Lobs a stun grenade that detonates on landing. "
         "Any enemy inside the blast radius is briefly blinded and disoriented."),
        ("MERCURY BARRAGE","F",    15,
         "Lock your aim and unleash 7 volleys of 5 bullets in a spread fan "
         "(-6° / -3° / 0° / +3° / +6°), one volley every 6 ticks. "
         "35 bullets total over 0.6 seconds. "
         "No spread, same damage and range as normal shots. "
         "Aim is fixed for the full duration; LMB, RMB, SPACE, and E are locked. "
         "Q (rune) and movement remain available."),
    ],
    'Vince': [
        ("AIRSTRIKE",     "RMB",   5,
         "Calls a sequence of bombs along the aimed trajectory. "
         "Impacts land in a line with a short delay, covering a wide zone."),
        ("TAUNT",         "SPACE", 10,
         "Release a lavender shockwave that expands from 60 px to 600 px over 1 second. "
         "Any enemy caught by the ring is stunned for 0.8 s and forcibly pulled toward you "
         "at 120 px/s — they cannot resist while stunned."),
        ("FRAG GRENADE",  "E",     8,
         "Hurls a fragmentation grenade that explodes on impact, "
         "dealing heavy damage to all enemies within the blast radius."),
        ("GIANT FORM",    "F",     20,
         "Transforms into a massive giant for a limited time. "
         "Greatly increases body size, armor thickness, and raw damage output."),
    ],
    'Marksman': [
        ("IMPACT ROUND",  "RMB",   4,
         "Fires an explosive bullet that detonates on contact. "
         "Deals burst damage to everything in a small radius around the point of impact."),
        ("CHARGE",        "SPACE", 9,
         "Dash toward the cursor for 360 px. "
         "Hitting an enemy stops the dash and stuns them for 1 second. "
         "Stopped by intact obstacles; destroyed debris and trees are ignored."),
        ("AUTO TURRET",   "E",     10,
         "Deploys a stationary turret at your position. "
         "It fires automatically at any enemy within 250 px, matching your gun's damage and fire rate. "
         "The turret has 180 HP — loses 1 HP per shot and 1 HP every 0.5 s passively. "
         "Enemy bullets also damage it. Only you can see the detection radius."),
        ("ROLLING BARRAGE","F",    10,
         "Calls in 18 airstrikes toward the cursor in rapid succession (~3 s). "
         "Strikes land from 60 px to 230 px ahead, randomly spread ±100 px left/right. "
         "Each strike shows a shrinking targeting circle before detonating in an 80 px radius."),
    ],
    'Hunter': [
        ("AIR CANNON",    "RMB",   5,
         "Fires a high-speed invisible air blast (800 px/s) in the aimed direction. "
         "Deals no damage, but launches the enemy on contact. "
         "On hit, the RMB cooldown is immediately reset — "
         "land the shot and you can fire again right away."),
        ("MINI GRENADES", "SPACE", 4,
         "Scatters a cluster of small grenades in an arc. "
         "Each grenade lands independently and detonates with its own small explosion."),
        ("LOG BARRIER",   "E",     10,
         "Erects wooden barriers in the aimed direction. "
         "Blocks movement and line of sight, forcing enemies to reposition."),
        ("PHANTOM CLOAK",  "F",    15,
         "Vanishes for 3 seconds with 2× movement speed. "
         "You can still shoot and use all skills while invisible. "
         "Every 0.5 s you briefly flicker into view — and you still take damage."),
    ],
    'Robot': [
        ("—", "RMB",   0, "Skill under development."),
        ("MARK RECALL", "SPACE", 6,
         "Dashes in your movement direction and plants a mark at the origin. "
         "Press Space again within 4 seconds to instantly teleport back. "
         "A yellow timer bar above your head shows the recall window — only you can see it."),
        ("PULSE RING", "E",  9,
         "Instantly expands a 200 px electromagnetic ring centered on you. "
         "Any enemy caught inside is stunned for 1 second. "
         "A glowing marker is also placed at a random cardinal point on the ring and orbits clockwise — "
         "press E again within 4 seconds to instantly blink to the marker's current position. "
         "If your Space mark is active, the ring still fires and stuns, but no orbiting marker is created."),
        ("PUSH ZONE", "F", 5,
         "Projects a 160×100 px force field toward the cursor. "
         "Enemies caught inside are launched away and stunned for 1 second. "
         "Only you see the targeting rectangle before it fires."),
    ],
    'Pioneer': [
        ("STUN ROUND",    "RMB",   6,
         "Fires a specialized round that stuns the target on impact. "
         "Briefly halts enemy movement, leaving them exposed to follow-up fire."),
        ("TACTICAL JUMP",  "SPACE", 8,
         "Leaps 150 px toward the aimed direction. "
         "Instantly refills the magazine and cancels any reload in progress. "
         "Invincible while airborne — can fly over obstacles and is immune to all projectiles."),
        ("FORCE SHIELD", "E", 12,
         "Surrounds yourself with a 60 px shield that absorbs 80 HP of incoming damage for 5 seconds. "
         "Damage never overflows to your HP — the excess is fully blocked. "
         "When the shield breaks or expires, it releases a shockwave ring (60→350 px in 0.5 s): "
         "the first enemy caught by the expanding ring is knocked back and stunned for 0.5 s (no damage)."),
        ("CLONE CORPS", "F", 20,
         "Summons two semi-transparent clones flanking your position. "
         "For 8 seconds, every basic attack fires three parallel shots — "
         "one from each clone — without extra ammo cost."),
    ],
    'Assassin': [
        ("BLADE STRIKE",  "RMB",   5,
         "Hurls a powered shuriken in the aimed direction. "
         "Deals concentrated damage and cuts through any enemy in its path."),
        ("SPEED SURGE",   "SPACE", 10,
         "Activates a short burst of enhanced movement speed. "
         "Use it to close the gap on an enemy or escape a dangerous situation."),
        ("SMOKE SCREEN",  "E",     8,
         "Deploys a smoke grenade creating a persistent cloud. "
         "Both sides lose visibility in the area, ideal for breaking line of sight."),
        ("SHADOW RUSH",   "F",     7,
         "Dashes swiftly toward the cursor, releasing a spinning blade arc "
         "upon arrival that strikes any enemy caught in the sweep."),
    ],
    'Poisoner': [
        ("POISON POOL", "RMB", 9,
         "Fires a toxic projectile that splashes on contact, creating a large poison zone (r 150). "
         "Enemies inside take 3 dmg/tick and move 20% slower. "
         "Each tick in the pool adds 1 poison stack (cap 2 from this source)."),
        ("TOXIC SPRINT", "SPACE", 8,
         "Dash forward at +20% speed for 3 s, leaving afterimages. "
         "Drops 9 small poison pools (r 20-30) at your feet every 20 ticks as you run. "
         "Standing in a mini-pool adds 1 poison stack per 30 ticks (cap 2 from this source)."),
        ("TOXIC RESONANCE", "E", 10,
         "For 3 s, every 30 ticks a green shockwave (r 60→60→400, 0.6 s) erupts from your position. "
         "No pool required. When the ring hits the enemy: deals 3 dmg, adds 1 poison stack, "
         "and heals you for 3 \xd7 (enemy's current poison stacks). Up to 6 shockwaves per activation."),
        ("—", "F",     0, "Skill under development."),
    ],
    'Zombie': [
        ("—", "RMB",   0, "Skill under development."),
        ("GROUND POUND",  "SPACE", 8,
         "Leap 200 px toward your aim, then slam down. "
         "Enemies caught in the landing shockwave are knocked back and stunned. "
         "Instantly refills your magazine and cancels any reload in progress."),
        ("—", "E",     0, "Skill under development."),
        ("—", "F",     0, "Skill under development."),
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
