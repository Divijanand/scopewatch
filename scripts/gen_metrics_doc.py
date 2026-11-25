"""Render docs/METRICS.md from the metric registry so definitions and docs can't drift.

Usage: python -m scripts.gen_metrics_doc
"""
from engine.config import ROOT
from engine.metrics import REGISTRY
from engine.metrics.core import SMALL_SAMPLE

HEAD = f"""# Metrics

Generated from `engine/metrics` by `scripts/gen_metrics_doc.py`. Do not edit by hand.

Every rate in Scopewatch reports:
- numerator *k* and denominator *n*;
- a Wilson 95% interval, widened because rounds of one game repeat each other (D-025, EVAL_RANGES.md);
- a small-sample flag when *n* < {SMALL_SAMPLE};
- unknown or excluded counts with a reason;
- the number of maps and series;
- the round keys behind it (`game_id:round_no`), split into supporting and contrary.

Each measure's within-game correlation is measured league-wide, not per team, so one team can be more or less steady than its range assumes. Treat the intervals as a guide to sample size, not as exact probabilities. They describe the games in scope; they don't forecast the next one.

Shared definitions:
- **Round clock** `t_round`: seconds since the buy phase ended (DECISIONS D-004).
- **Phase**: `buy`, `pre_plant`, `post_plant` or `post_round`.
- **Possession**: the item is in a player's inventory when the buy phase ends. The feed has no purchase events.
- **Economy**: team loadout value at buy-phase end: eco < 5,000 ≤ half < 15,000 ≤ full (D-006).
"""


def main():
    out = [HEAD]
    for d, _ in sorted(REGISTRY.values(), key=lambda x: x[0].id):
        out.append(f"\n## {d.title} (`{d.id}` v{d.version})\n")
        out.append(f"**Question:** {d.question}\n")
        out.append(f"- **Population:** {d.population}")
        out.append(f"- **Numerator:** {d.numerator}")
        out.append(f"- **Unit:** {d.unit}")
        for c in d.caveats:
            out.append(f"- **Caveat:** {c}")
    (ROOT / "docs" / "METRICS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {len(REGISTRY)} metrics")


if __name__ == "__main__":
    main()
