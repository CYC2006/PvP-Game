---
name: char_key removal
description: The char_key concept (hitman1, manBlue, etc.) was removed; display names are now the canonical identifier everywhere
type: project
---

The `char_key` concept (internal IDs like `hitman1`, `manBlue`, `survivor1`, etc.) has been fully removed from the project. Characters are now identified solely by their display name.

**Why:** The char_key was redundant — everywhere a char_key was used, the display name could be used directly. Removing it eliminates a layer of indirection.

**How to apply:** When writing new code, use the character's display name (e.g. `'Assassin'`, `'Vince'`, `'Pioneer'`) everywhere — in dicts, comparisons, CSV keys, etc. The canonical mapping is the `name` column in `chars.csv` and in `CHAR_STATS` / `CHAR_ORDER`.

Name → folder mapping:
- Agent → agent
- Vince → vince
- Marksman → marksman
- Hunter → hunter
- Robot → robot
- Pioneer → pioneer
- Assassin → assassin
- Poisoner → poisoner
- Zombie → zombie
