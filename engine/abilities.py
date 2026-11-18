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

# placed and left on the map: Sentinel setups first (the brief's priority), plus Chamber's anchor
PLACEABLE = frozenset({
    "trapwire", "cyber-cage", "spycam",                 # Cypher
    "alarmbot", "turret", "nanoswarm",                  # Killjoy
    "trademark", "rendezvous",                          # Chamber
    "razorvine", "shear", "arc-rose",                   # Vyse
    "gravnet", "sonic-sensor", "barrier-mesh",          # Deadlock
    "barrier-orb", "slow-orb",                          # Sage
})

# thrown utility that deals damage: GRID records each hit with the victim's position, which shows where it landed
DAMAGE_THROWN = frozenset({
    "snake-bite", "nanoswarm", "incendiary", "hot-hands", "paint-shells", "shock-bolt", "aftershock",
    "frag-ment", "mosh-pit", "guided-salvo", "orbital-strike", "special-delivery", "boom-bot",
})

# walls that run out from the caster along the aim direction
WALLS = frozenset({"toxic-screen", "high-tide", "fast-lane", "blaze"})

# smokes placed from the tactical map or thrown to a spot the feed never records: no position shown
UNPLACED_SMOKES = frozenset({"dark-cover", "sky-smoke", "ruse", "nebula-dissipate", "cove", "poison-cloud"})

# map layer groups for the utility view
GROUPS = {
    "setup": PLACEABLE,
    "damage": DAMAGE_THROWN,
    "smoke": WALLS | UNPLACED_SMOKES,
    "flash": FLASH | STUN,
    "recon": INFO,
}

# ---------------------------------------------------------------- every ability, by what its position means
# placed     set down next to the player: drawn where the player stood
# landing    thrown and deals damage: drawn where it hurt an enemy (GRID damage records), linked to the throw
# direction  runs out from the player along their aim (walls, cones): drawn as a line
# thrown     thrown or sent elsewhere, landing not recorded: drawn where it was used from
# self       affects the player or a teammate where they stand (movement, heals, revives, weapons)
# unplaced   placed from the map or far away with no recorded spot: timing only, never drawn
MODE = {
    # astra
    "nova-pulse": "unplaced", "nebula-dissipate": "unplaced", "gravity-well": "unplaced", "stars": "unplaced",
    # breach
    "flashpoint": "thrown", "fault-line": "direction", "aftershock": "landing", "rolling-thunder": "direction",
    # brimstone
    "incendiary": "landing", "sky-smoke": "unplaced", "stim-beacon": "thrown", "orbital-strike": "landing",
    # chamber
    "headhunter": "self", "rendezvous": "placed", "trademark": "placed", "tour-de-force": "self",
    # clove
    "meddle": "thrown", "ruse": "unplaced", "pick-me-up": "self", "not-dead-yet": "self",
    # cypher
    "cyber-cage": "placed", "spycam": "placed", "trapwire": "placed", "neural-theft": "self",
    # deadlock
    "sonic-sensor": "placed", "gravnet": "thrown", "barrier-mesh": "placed", "annihilation": "landing",
    # fade
    "seize": "thrown", "haunt": "thrown", "prowler": "thrown", "nightfall": "direction",
    # gekko
    "wingman": "thrown", "dizzy": "thrown", "mosh-pit": "landing", "thrash": "thrown",
    # harbor
    "cove": "unplaced", "high-tide": "direction", "cascade": "direction", "storm-surge": "thrown",
    "reckoning": "direction",
    # iso
    "undercut": "thrown", "double-tap": "self", "contingency": "direction", "kill-contract": "direction",
    # jett
    "updraft": "self", "tailwind": "self", "cloudburst": "thrown",
    # kay/o
    "flash-drive": "thrown", "zero-point": "thrown", "frag-ment": "landing", "null-cmd": "self",
    # killjoy
    "alarmbot": "placed", "turret": "placed", "nanoswarm": "landing", "lockdown": "placed",
    # miks (new agent: kit not classified yet, shown honestly as "used from")
    "harmonize": "thrown", "waveform": "thrown", "m-pulse": "thrown", "bassquake": "thrown",
    # neon
    "relay-bolt": "thrown", "high-gear": "self", "fast-lane": "direction",
    # omen
    "paranoia": "direction", "dark-cover": "unplaced", "shrouded-step": "self", "from-the-shadows": "self",
    # phoenix
    "hot-hands": "landing", "curveball": "thrown", "blaze": "direction",
    # raze
    "blast-pack": "self", "paint-shells": "landing", "boom-bot": "landing", "showstopper": "landing",
    # reyna
    "devour": "self", "leer": "thrown",
    # sage
    "slow-orb": "thrown", "healing-orb": "self", "barrier-orb": "placed", "resurrection": "self",
    # skye
    "trailblazer": "thrown", "guiding-light": "thrown", "regrowth": "self", "seekers": "unplaced",
    # sova
    "shock-bolt": "landing", "recon-bolt": "thrown", "owl-drone": "thrown", "hunter's-fury": "landing",
    # tejo
    "special-delivery": "landing", "guided-salvo": "landing", "stealth-drone": "thrown", "armageddon": "landing",
    # veto
    "chokehold": "placed", "interceptor": "placed", "crosscut": "placed",
    # viper
    "poison-cloud": "unplaced", "toxic-screen": "direction", "snake-bite": "landing", "viper's-pit": "placed",
    # vyse
    "shear": "placed", "arc-rose": "placed", "razorvine": "placed", "steel-garden": "placed",
    # waylay
    "light-speed": "self", "refract": "self", "saturate": "thrown", "convergent-paths": "direction",
    # yoru
    "blindside": "thrown", "gatecrash": "thrown", "fakeout": "thrown", "dimensional-drift": "self",
}


def mode_of(ability: str) -> str:
    return MODE.get(ability, "thrown")
