"""How much the rounds of one game repeat each other, and what that does to a range (D-025).

A team's plan is partly set per game, so 100 rounds from 8 games carry less evidence than 100 independent rounds.
`RHO` is the league-wide within-game correlation of each measure, measured by `python -m scripts.eval_ranges`
(team-map-sides, every team pooled, nothing tuned per team). A rate's design effect is 1 + (m - 1) * rho, where m is
the size-weighted number of its units per game; its range is the Wilson range on n / design-effect units.

Cards always have one map, and a series plays a map once, so one game is one series here.
"""
from __future__ import annotations

from collections import Counter

RHO: dict[str, float] = {
    "att.executes.entry": 0.028,
    "att.executes.lost_no_kill": 0.000,
    "att.executes.no_plant": 0.071,
    "att.executes.op_kill": 0.000,
    "att.executes.site": 0.004,
    "att.executes.won": 0.084,
    "op.broken.how": 0.025,
    "op.deaths.callout": 0.000,
    "op.deaths.first": 0.000,
    "op.escapes.moved": 0.005,
    "op.escapes.punished": 0.080,
    "op.gamble.multi_kill": 0.000,
    "op.gamble.outcome": 0.000,
    "op.gamble.won": 0.073,
    "op.holder": 0.946,
    "op.kill_timing": 0.052,
    "op.kill_timing.post_plant": 0.140,
    "op.opening.lost": 0.000,
    "op.opening.won": 0.000,
    "op.possession": 0.184,
    "op.possession_shift": 0.000,
    "op.setups.callout": 0.000,
    "op.win.with": 0.049,
    "op.win.without": 0.072,
    "team.closing.comebacks": 0.030,
    "team.closing.throws": 0.027,
    "team.economy.full_vs_anti": 0.044,
    "team.economy.full_vs_full": 0.066,
    "team.economy.pistol": 0.000,
    "team.economy.scrappy_vs_full": 0.097,
    "team.openings.after_first_blood": 0.083,
    "team.openings.after_first_death": 0.088,
    "team.openings.first_blood": 0.027,
    "team.post_plant.by_numbers": 0.073,
    "team.post_plant.plant_share": 0.071,
    "team.post_plant.pre_plant_losses": 0.026,
    "team.post_plant.win": 0.070,
    "team.predictability.contact_when": 0.019,
    "team.predictability.contact_where": 0.002,
    "team.predictability.site": 0.000,
    "team.predictability.sniper_spot": 0.000,
    "team.retakes.by_numbers": 0.075,
    "team.retakes.plants_faced": 0.075,
    "team.retakes.retake": 0.075,
    "util.kit.ability": 0.000,
    "util.kit.spot": 0.026,
    "util.kit.unplaced": 0.028,
    "util.placements.ability": 0.546,
    "util.placements.spot": 0.117,
    "util.placements.unplaced": 0.491,
    "util.recon_timing.before": 0.167,
    "util.recon_timing.none": 0.140,
    "util.recon_timing.won": 0.103,
    "util.ults.used": 0.000,
    "util.ults.won": 0.054,
}
DEFAULT_RHO = 0.078      # an unmeasured rate: the 75th percentile of the measured ones

RECORD: list | None = None      # scripts.eval_ranges sets this to collect every clustered rate a metric builds


def rho(measure: str) -> float:
    return RHO.get(measure, DEFAULT_RHO)


def game_of(u) -> str:
    """The game of a round key (game_id:round_no), or of a row whose first column is one."""
    key = u if isinstance(u, str) else u[0]
    return key.rsplit(":", 1)[0]


def design_effect(measure: str, units) -> float:
    sizes = Counter(game_of(u) for u in units).values()
    n = sum(sizes)
    if n == 0:
        return 1.0
    return 1.0 + (sum(s * s for s in sizes) / n - 1.0) * rho(measure)


def record(measure: str, hits, units):
    if RECORD is not None:
        h, n = Counter(game_of(u) for u in hits), Counter(game_of(u) for u in units)
        RECORD.append((measure, {g: (h.get(g, 0), m) for g, m in n.items()}))
