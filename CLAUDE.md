# CLAUDE.md — Project Notes for AI Sessions

This file stores important context and conventions for this project.
Claude should read this at the start of every session.

---

## Project Overview

Top-down 2-player PvP shooter. Python + pygame-ce, UDP networking.
Resolution: 1280×720 (LOGICAL_W × LOGICAL_H), `pygame.SCALED`.

---

## Architecture

| File / Folder | Role |
|---|---|
| `client.py` | Main entry point, game loop, event handling |
| `server.py` | UDP game server (runs as daemon thread when hosting) |
| `game/lobby.py` | Lobby screen controller |
| `game/pages/` | One file per lobby sidebar tab (layout.py = shared constants) |
| `game/renderer.py` | All in-game rendering + HUD |
| `game/input.py` | Client-side input → PlayerCommand |
| `game/state.py` | Shared game state (players, bullets, obstacles, …) |
| `game/chars/<name>/` | Per-character skill state + visual FX |
| `network/protocol.py` | Packet definitions + pack/unpack functions |
| `maps/map_01.json` | Grassland map obstacle data |
| `assets/fonts/` | MapleMono-NF-Bold.ttf / MapleMono-NF-Regular.ttf |

---

## Key Conventions

### Icons (Nerd Fonts / Font Awesome via MapleMono-NF)
**Always write icons as `chr(0xfXXX)` — never paste raw PUA glyphs.**
Raw glyphs are silently dropped by editors and round-trips.

Common icons used in this project:
```python
chr(0xf007)  # fa-user
chr(0xf013)  # fa-cog
chr(0xf015)  # fa-home
chr(0xf017)  # fa-clock-o       (skill cooldown)
chr(0xf024)  # fa-flag
chr(0xf028)  # fa-volume-up
chr(0xf05b)  # fa-crosshairs
chr(0xf07a)  # fa-shopping-cart
chr(0xf08b)  # fa-sign-out
chr(0xf090)  # fa-sign-in
chr(0xf0ae)  # fa-tasks
chr(0xf0e7)  # fa-bolt          (level badge)
chr(0xf005)  # fa-star          (filled)
chr(0xf006)  # fa-star-o        (empty)
chr(0xf11b)  # fa-gamepad
chr(0xf140)  # fa-bullseye
chr(0xf233)  # fa-server
chr(0xf279)  # fa-map
```

### Network Packets
| Constant | Value | Direction | Purpose |
|---|---|---|---|
| PKT_JOIN | 0x01 | C→S | Join request |
| PKT_JOINED | 0x02 | S→C | Assigned player ID |
| PKT_CMD | 0x03 | C→S | Per-frame input |
| PKT_STATE | 0x04 | S→C | Game state broadcast |
| PKT_CHAR_SELECT | 0x05 | C→S | Character chosen |
| PKT_GAME_START | 0x06 | S→C | Both selected, start |
| PKT_ALL_JOINED | 0x07 | S→C | Both players connected |
| PKT_QUIT | 0x08 | C→S | Player leaving |
| PKT_GAME_OVER | 0x09 | S→C | Session ended |

### Lobby Pages
Sidebar order: GAME → SHOP → CHARACTERS → MAP → MISSIONS

Each page is a module in `game/pages/` with a `draw(screen, font_lg, font_sm, ...)` entry point.
`game/pages/layout.py` holds all shared colours, constants, and `btn()` / `cx()` helpers.

### Characters
Characters are identified solely by their display name (the `name` column in `chars.csv`).
There is no separate char_key — the name IS the key used everywhere in code.

| Name | Folder |
|---|---|
| Agent | agent |
| Vince | vince |
| Marksman | marksman |
| Hunter | hunter |
| Robot | robot |
| Pioneer | pioneer |
| Assassin | assassin |
| Poisoner | poisoner |
| Zombie | zombie |

### Star Ratings display order
ATTACK → DEFENSE → AGILITY → UTILITY  (stored as ATK, AGI, DEF, UTL in `_RATINGS`)

### Currency
- **Gold** (`gold = 200` initial): earned from destroying golden crates in-match
- **Gems** (`gems = 10` initial): earned from missions / ranked wins

### Settings / Shooting conflict
`renderer.settings_blocks_click(mx, my)` returns True when the mouse is over the
in-game settings UI. Pass result as `suppress_lmb` to `input.read_input()` to
prevent accidental shots when clicking the gear icon.

### Debris / per-game state reset
Call `renderer.reset_game_state()` before each new game loop to clear debris,
particles, shake timers, and the map surface cache.

---

## Things to Know

- Server is started once as a daemon thread (`_start_server_thread()`).
  On `PKT_QUIT` the server resets session state without restarting the thread.
- `run()` in `client.py` loops back to lobby after each game — do NOT call
  `pygame.quit()` mid-loop; only call it after the outer `while app_running` exits.
- Module-level `pygame.Rect` objects in `renderer.py` and `pages/` are safe to
  define before `pygame.init()` — `Rect` is a pure data struct.
- Skill cooldown HUD uses `SKILL_CIRCLE_R = 17` (1.2× the original 14 px).
- `_SKILL_SLOTS = ('space', 'e', 'r', 'rmb')` — order matches HUD left-to-right.

---

## Notes added by user

<!-- Add your own notes below this line -->
