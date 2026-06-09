"""
game/audio.py — Client-side sound-effect manager.

Usage
-----
    import game.audio as audio
    audio.play_skill('Agent', 'rmb')   # call after read_input() returns True for that slot

Slots:  'rmb' | 'space' | 'e' | 'r'
        ('r' is the F-key ultimate — matches skill_cds_ms key naming in input.py)

Sound files
-----------
All skill SFX are loaded from assets/sfx/skill_sfx/.
Naming convention:  {char_lower}_{slot}.ogg
  e.g. pioneer_rmb.ogg, agent_space.ogg, vince_r.ogg

LMB variants:  {char_lower}_lmb_1.ogg, _lmb_2.ogg, …  (randomly chosen each shot)
               Falls back to {char_lower}_lmb.ogg if no numbered variants.

If a file is missing the skill plays silently — no crash.
Add / replace files in skill_sfx/ at any time; they are loaded lazily on first use.

Volume control
--------------
Edit _VOLUME below.  Key = filename, value = % of master volume (default 100).
  80  → quieter   (80 % of master)
  200 → louder    (200 % of master, capped at pygame's maximum of 1.0)
Master volume _MASTER is the baseline applied to every sound before the per-file %.
"""

import os
import random
import numpy as np
import pygame
import pygame.sndarray

_SKILL_SFX_DIR = os.path.join("assets", "sfx", "skill_sfx")

# ── Master volume (0.0 – 1.0) ────────────────────────────────────────────────
_MASTER: float = 0.75

# ── Per-file volume overrides (% of master) ──────────────────────────────────
# Add an entry whenever a sound is too loud or too quiet.
# final_volume = min(1.0,  _MASTER  ×  pct / 100)
_VOLUME: dict[str, int] = {
    # 'robot_lmb_1.ogg': 80,
    # 'pioneer_e.ogg':   120,
}

# ─────────────────────────────────────────────────────────────────────────────

# Lazy-loaded sound cache: filename → Sound
_cache: dict[str, pygame.mixer.Sound] = {}

# Per-char LMB variant list, built on first use: char_lower → [Sound, ...]
_lmb_variants: dict[str, list] = {}


def _load(filename: str) -> 'pygame.mixer.Sound | None':
    if filename not in _cache:
        path = os.path.join(_SKILL_SFX_DIR, filename)
        if not os.path.isfile(path):
            return None
        snd = pygame.mixer.Sound(path)
        pct = _VOLUME.get(filename, 100)
        factor = _MASTER * pct / 100          # e.g. 0.75 × 200/100 = 1.5

        if factor <= 1.0:
            # Simple case: pure volume attenuation, no data manipulation needed
            snd.set_volume(factor)
        else:
            # Amplify PCM samples directly so we can exceed pygame's 1.0 cap.
            # Clips at dtype limits to prevent wraparound distortion.
            samples = pygame.sndarray.array(snd)
            amplified = np.clip(
                (samples.astype(np.float32) * factor),
                np.iinfo(samples.dtype).min,
                np.iinfo(samples.dtype).max,
            ).astype(samples.dtype)
            snd = pygame.sndarray.make_sound(amplified)
            snd.set_volume(1.0)

        _cache[filename] = snd
    return _cache[filename]


def play_lmb(char_name: str) -> None:
    """Play the normal-attack SFX for char_name.

    On first call per character, scans skill_sfx/ for numbered variants:
        {char_lower}_lmb_1.ogg, _lmb_2.ogg, _lmb_3.ogg, …
    Each shot picks one at random.
    Falls back to {char_lower}_lmb.ogg if no numbered variants exist.
    Safe to call before mixer is ready — silently skipped.
    """
    if not pygame.mixer.get_init():
        return
    key = char_name.lower()
    if key not in _lmb_variants:
        sounds = []
        for i in range(1, 10):          # scan _lmb_1 … _lmb_9
            snd = _load(f"{key}_lmb_{i}.ogg")
            if snd:
                sounds.append(snd)
            else:
                break                   # stop at first gap
        if not sounds:                  # fallback: single file
            snd = _load(f"{key}_lmb.ogg")
            if snd:
                sounds.append(snd)
        _lmb_variants[key] = sounds
    variants = _lmb_variants[key]
    if variants:
        random.choice(variants).play()


def play_skill(char_name: str, slot: str) -> None:
    """Play the SFX for char_name's skill on the given slot.

    slot: 'rmb' | 'space' | 'e' | 'r'
    Looks for  assets/sfx/skill_sfx/{char_lower}_{slot}.ogg
    Safe to call before mixer is ready — silently skipped.
    """
    if not pygame.mixer.get_init():
        return
    filename = f"{char_name.lower()}_{slot}.ogg"
    snd = _load(filename)
    if snd:
        snd.play()
