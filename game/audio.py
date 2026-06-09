"""
game/audio.py — Client-side sound-effect manager.

Usage
-----
    import game.audio as audio
    audio.play_skill('Agent', 'rmb')   # call after read_input() returns True for that slot

Slots:  'rmb' | 'space' | 'e' | 'r'
        ('r' is the F-key ultimate — matches skill_cds_ms key naming in input.py)
"""

import os
import pygame

_IMPACT = os.path.join("assets", "sfx", "impact")
_SCIFI  = os.path.join("assets", "sfx", "scifi")

# ── Skill SFX mapping: char → slot → (pack_dir, filename) ────────────────────
_SKILL_SFX: dict[str, dict[str, tuple[str, str]]] = {
    'Agent': {
        'rmb':   (_SCIFI,  'laserLarge_000.ogg'),       # POWER SHOT  — large enhanced bullet
        'space': (_SCIFI,  'thrusterFire_000.ogg'),     # DASH        — burst of speed
        'e':     (_SCIFI,  'explosionCrunch_000.ogg'),  # FLASH GRENADE — grenade detonation
        'r':     (_SCIFI,  'laserSmall_000.ogg'),       # MERCURY BARRAGE — rapid-fire barrage
    },
    'Vince': {
        'rmb':   (_SCIFI,  'lowFrequency_explosion_000.ogg'),  # AIRSTRIKE   — heavy bombing
        'space': (_SCIFI,  'forceField_000.ogg'),              # TAUNT       — expanding shockwave
        'e':     (_SCIFI,  'explosionCrunch_001.ogg'),         # FRAG GRENADE — frag explosion
        'r':     (_SCIFI,  'spaceEngineLarge_000.ogg'),        # GIANT FORM  — transformation
    },
    'Marksman': {
        'rmb':   (_SCIFI,  'explosionCrunch_002.ogg'),         # IMPACT ROUND  — bullet explosion
        'space': (_SCIFI,  'thrusterFire_001.ogg'),            # CHARGE        — dash toward cursor
        'e':     (_SCIFI,  'computerNoise_000.ogg'),           # AUTO TURRET   — mechanical deploy
        'r':     (_SCIFI,  'lowFrequency_explosion_001.ogg'),  # ROLLING BARRAGE — rolling strikes
    },
    'Hunter': {
        'rmb':   (_SCIFI,  'forceField_001.ogg'),       # AIR CANNON    — invisible force blast
        'space': (_SCIFI,  'explosionCrunch_003.ogg'),  # MINI GRENADES — cluster explosion
        'e':     (_IMPACT, 'impactWood_heavy_000.ogg'), # LOG BARRIER   — wooden slam
        'r':     (_SCIFI,  'laserRetro_000.ogg'),       # PHANTOM CLOAK — stealth tech
    },
    'Robot': {
        # 'rmb' under development — no sound assigned
        'space': (_SCIFI,  'laserRetro_001.ogg'),   # MARK RECALL — teleport / mark place
        'e':     (_SCIFI,  'forceField_002.ogg'),   # PULSE RING  — EM ring burst
        'r':     (_SCIFI,  'forceField_003.ogg'),   # PUSH ZONE   — force field launch
    },
    'Pioneer': {
        'rmb':   (_SCIFI,  'laserSmall_001.ogg'),   # STUN ROUND    — stun bullet
        'space': (_SCIFI,  'thrusterFire_002.ogg'), # TACTICAL JUMP — leap + mag refill
        'e':     (_SCIFI,  'forceField_004.ogg'),   # FORCE SHIELD  — shield activate
        'r':     (_SCIFI,  'computerNoise_001.ogg'), # CLONE CORPS  — clones materialise
    },
    'Assassin': {
        'rmb':   (_SCIFI,  'impactMetal_000.ogg'),   # BLADE STRIKE — shuriken throw
        'space': (_SCIFI,  'thrusterFire_003.ogg'),  # SPEED SURGE  — speed boost
        'e':     (_SCIFI,  'engineCircular_000.ogg'), # SMOKE SCREEN — smoke deploy
        'r':     (_SCIFI,  'thrusterFire_004.ogg'),  # SHADOW RUSH  — dash + blade arc
    },
    'Poisoner': {
        'rmb':   (_SCIFI,  'slime_000.ogg'),           # POISON POOL     — toxic splash
        'space': (_SCIFI,  'spaceEngineSmall_000.ogg'), # TOXIC SPRINT   — dash with afterimages
        'e':     (_SCIFI,  'laserRetro_002.ogg'),      # TOXIC RESONANCE — pulsing shockwaves
        # 'r' under development — no sound assigned
    },
    # Zombie: all skills under development — no sounds assigned yet
}

_SKILL_VOLUME: float = 0.75

# Lazy-loaded sound cache: (pack_dir, filename) → Sound
_cache: dict[tuple[str, str], pygame.mixer.Sound] = {}


def _load(pack_dir: str, filename: str) -> 'pygame.mixer.Sound | None':
    key = (pack_dir, filename)
    if key not in _cache:
        path = os.path.join(pack_dir, filename)
        if not os.path.isfile(path):
            print(f"[audio] missing sfx: {path}")
            return None
        snd = pygame.mixer.Sound(path)
        snd.set_volume(_SKILL_VOLUME)
        _cache[key] = snd
    return _cache[key]


def play_skill(char_name: str, slot: str) -> None:
    """Play the SFX for char_name's skill on the given slot.

    slot: 'rmb' | 'space' | 'e' | 'r'
    Safe to call before mixer is ready — silently skipped.
    """
    if not pygame.mixer.get_init():
        return
    entry = _SKILL_SFX.get(char_name, {}).get(slot)
    if not entry:
        return
    snd = _load(*entry)
    if snd:
        snd.play()
