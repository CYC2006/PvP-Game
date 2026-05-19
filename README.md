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

One player selects **HOST**, the other selects **JOIN** and enters the host's IP address.  
Port **5000 UDP** must be open for internet play.

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
| **Agent** | 2× dmg power bullet | Sprint in move dir. | Stun grenade; blinds | — |
| **Vince** | Bombs drop in a line | Rush toward cursor | Blast grenade throw | Transform into giant |
| **Marksman** | Explosive bullet hit | — | Deploy auto turret | 18 rapid airstrikes |
| **Hunter** | — | Mini grenade cluster | Place wooden walls | Vanish for 3 seconds |
| **Robot** | — | Dash; recall to mark | — | Launch enemies away |
| **Pioneer** |  Stun bullet on hit | Leap + refill ammo | 120 HP absorb shield | Clones fire with you |
| **Assassin** | Throw a shuriken | Short speed boost | Deploy smoke cloud | Dash + blade sweep |
| **Poisoner** | Toxic splash zone | — | — | — |
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
