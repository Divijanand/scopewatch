"""Ability classes used by the Operator metrics.

Names are the feed's ability ids. Classes describe what an ability is for, not whether it hit
anyone: the feed records the cast (who, when, caster position, aim), never where it landed or
who it affected (UTILITY_SPATIAL_SEMANTICS.md).
"""
from __future__ import annotations

# repositions the caster: dash, teleport, burst of speed
MOVEMENT = frozenset({
    "tailwind", "updraft",                     # Jett
    "rendezvous",                              # Chamber
    "gatecrash", "dimensional-drift",          # Yoru
    "crosscut",                                # Veto
    "blast-pack",                              # Raze
    "high-gear",                               # Neon
    "shrouded-step", "from-the-shadows",       # Omen
    "light-speed", "refract",                  # Waylay
})

# blinds or nearsights
FLASH = frozenset({
    "flashpoint", "curveball", "guiding-light", "flash-drive", "paranoia", "blindside", "leer", "dizzy",
    "arc-rose",
})

# concusses, slows, suppresses or pulls
STUN = frozenset({
    "fault-line", "nova-pulse", "trailblazer", "seize", "gravnet", "thrash", "saturate", "slow-orb",
})

# blocks vision
SMOKE = frozenset({
    "dark-cover", "sky-smoke", "cloudburst", "nebula-dissipate", "ruse", "cove", "poison-cloud",
    "toxic-screen", "high-tide", "cyber-cage",
})

# gathers information
INFO = frozenset({
    "recon-bolt", "owl-drone", "haunt", "prowler", "stealth-drone", "seekers", "wingman",
})


def kind_of(ability: str | None) -> str:
    if ability in MOVEMENT:
        return "movement"
    if ability in FLASH:
        return "flash"
    if ability in STUN:
        return "stun"
    if ability in SMOKE:
        return "smoke"
    if ability in INFO:
        return "info"
    return "other"


def sql_list(names) -> str:
    return "(" + ",".join("'" + n.replace("'", "''") + "'" for n in sorted(names)) + ")"
