# PvP Game

A top-down 2-player shooter built with **Python + Pygame**. Two players connect over a local network (or the internet via port forwarding) and battle in a destructible arena until one side is eliminated.

---

## Features

- Real-time UDP networking (host / join)
- 9 playable characters, each with up to 4 unique skills
- Destructible obstacles — wooden crates, rocks, and trees
- Gold & gem currency system with a shop and missions
- Lobby with character select, map preview, missions, and settings

---

## Requirements

```
Python 3.9+
pygame-ce
```

Install dependencies:

```bash
pip install pygame-ce
```

---

## How to Run

```bash
python client.py
```

One player selects **HOST** and shares the 4-digit room code shown on screen; the other selects **JOIN** and enters that code. See [Connection Logic](#connection-logic) for how matchmaking works under the hood.

---

## Connection Logic

Players never connect to each other directly — both clients always talk to a shared relay server, matched by a 4-digit room code.

### Matchmaking flow

1. **Host** clicks **HOST** → the client picks a random 4-digit room code and displays it in large text.
2. **Join** clicks **JOIN** → enters that code into the 4-box digit grid.
3. Both clients send `PKT_JOIN` (carrying the room code) to the same server address. The server pairs the two connections that share a room code and starts their session.

### Server address — `network/cloud_config.py`

`CLOUD_SERVER_IP` decides where both clients connect:

| Value | Meaning |
|---|---|
| Oracle VM IP (currently `129.225.195.211`) | Real online play. The server must already be running on the VM — see Deployment below. |
| `127.0.0.1` | Local testing. The client auto-starts `server.py` in a background thread the first time HOST is clicked, so two terminals on the same machine can matchmake without deploying anything. |

This file is excluded from git (`.gitignore`) and from `deploy.sh`'s rsync, so the VM keeps its own copy.

### Multi-room server — `server.py`

`server.py` is a single long-running process that can host many simultaneous matches. Each room's game state, players, and obstacles live in their own `RoomState` instance, keyed by room code (`rooms: dict[room_code → RoomState]`); incoming packets are routed to the right room via `addr_room: dict[addr → room_code]`.

### Deploying server changes to the Oracle VM

```bash
bash deploy.sh
```

Rsyncs server-only files over SSH (excludes client-only modules — `renderer.py`, `lobby.py`, `pages/`, `assets/`, etc.) to the VM, then restarts `server.py` there. Requires the SSH key at `network/pvp-game-server.key` (gitignored, not checked in).

Port **5000 UDP** must be open on the VM, e.g. `sudo iptables -I INPUT -p udp --dport 5000 -j ACCEPT`, and forwarded for internet play in general.

### Legacy packets

`PKT_PING` / `PKT_PONG` (`0x0A` / `0x0B`) are still defined in `network/protocol.py`, and `server.py` still replies to them, but no current client code sends `PKT_PING`. They're left over from an earlier design that auto-probed the Oracle VM's reachability and fell back to localhost on timeout — superseded by the room-code system above. Harmless to leave as-is.

---

## Controls

| Input | Action |
|---|---|
| `W A S D` | Move |
| `LMB` | Shoot |
| `RMB` | Skill — RMB |
| `Space` | Skill — SPACE |
| `E` | Skill — E |
| `R` | Skill — R |
| `Shift` | Hold-fire stance (higher accuracy) |
| `F11` | Toggle fullscreen |
| `ESC` | Settings / back |

---

## Characters

Star ratings out of 5 — **ATK / DEF / AGI / UTL**

Skill descriptions are shortened to fit the table; see the in-game **Characters** page for full details.

| Character | RMB | SPACE | E | R |
|---|---|---|---|---|
| **Agent** | 2× dmg power bullet | Sprint in move dir. | Stun grenade; blinds | 35-bullet fan barrage |
| **Vince** | Bombs drop in a line | Rush toward cursor | Blast grenade throw | Transform into giant |
| **Marksman** | Explosive bullet hit | — | Deploy auto turret | 18 rapid airstrikes |
| **Hunter** | — | Mini grenade cluster | Place wooden walls | Vanish for 3 seconds |
| **Robot** | — | Dash; recall to mark | Pulse ring stun + orbiting teleport mark | Launch enemies away |
| **Pioneer** |  Stun bullet on hit | Leap + refill ammo | 120 HP absorb shield | Clones fire with you |
| **Assassin** | Throw a shuriken | Short speed boost | Deploy smoke cloud | Dash + blade sweep |
| **Poisoner** | Toxic splash zone (pool) | +20% speed, afterimage, 9 mini pools | Shockwave from pool; heals caster | — |
| **Zombie** | — | — | — | — |

> Characters marked **—** have skills still under development.

---

## Map — Grassland

An open field with three types of obstacles:

| Obstacle | Destructible | Notes |
|---|---|---|
| Wooden Crates | ✅ Yes | Drop gold ingots when destroyed |
| Rocks | ❌ No | Solid cover |
| Trees | ❌ No | Players beneath are semi-transparent |

---

## Currency

| Currency | How to Earn | Use |
|---|---|---|
| 🟡 **Gold** | Destroy golden crates in-match | Upgrade guns, buy consumables |
| 💎 **Gems** | Complete missions, win ranked matches | Unlock characters, upgrade skills, cosmetics |

---

## Lobby Pages

| Tab | Description |
|---|---|
| **Game** | Choose match mode, host or join |
| **Shop** | Coming soon |
| **Characters** | Browse stats, ratings, and skills for all characters |
| **Map** | Preview the current map and obstacle legend |
| **Missions** | Daily and career missions with progress tracking |
