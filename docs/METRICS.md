# Metrics

Generated from `engine/metrics` by `scripts/gen_metrics_doc.py`. Do not edit by hand.

Every rate in Scopewatch reports:
- numerator *k* and denominator *n*;
- a Wilson 95% interval;
- a small-sample flag when *n* < 10;
- unknown or excluded counts with a reason;
- the number of maps and series;
- the round keys behind it (`game_id:round_no`), split into supporting and contrary.

Rounds inside a match aren't independent, so the intervals are a little optimistic. Treat them as a guide to sample size, not as exact probabilities.

Shared definitions:
- **Round clock** `t_round`: seconds since the buy phase ended (DECISIONS D-004).
- **Phase**: `buy`, `pre_plant`, `post_plant` or `post_round`.
- **Possession**: the item is in a player's inventory when the buy phase ends. The feed has no purchase events.
- **Economy**: team loadout value at buy-phase end: eco < 5,000 ≤ half < 15,000 ≤ full (D-006).


## Where it dies (`op.deaths` v1)

**Question:** Where does the team's Operator/Outlaw holder die, and from where is the kill taken?

- **Population:** Deaths of a player who held an Operator/Outlaw at buy-phase end, on one map and side, between buy-phase end and the round result
- **Numerator:** Deaths at this callout
- **Unit:** deaths
- **Caveat:** Holder = had the Operator/Outlaw at buy-phase end; they may have dropped or swapped it.
- **Caveat:** Callouts are the nearest reachable community callout anchor, an approximation.

## How far forward (`op.forwardness` v1)

**Question:** How far toward the enemy spawn are their Operator fights, compared with every team on this map?

- **Population:** Operator/Outlaw kills and hits by the team on one map and side, with a shooter position
- **Numerator:** Median of d(own spawn) / (d(own spawn) + d(enemy spawn)) at the shooter's position
- **Unit:** engagements
- **Caveat:** Needs a single map and side.
- **Caveat:** Positions come from the event, not continuous tracking.

## Who carries it (`op.holder_share` v1)

**Question:** Which player has the Operator/Outlaw in the team's Operator rounds?

- **Population:** Team rounds in scope where at least one player holds an Operator/Outlaw at buy-phase end
- **Numerator:** Rounds where this player holds it (a round with two holders counts for both)
- **Unit:** rounds
- **Caveat:** Shares can sum above 100% when two players hold one in the same round.

## When it fires (`op.kill_timing` v1)

**Question:** When in the round do the team's Operator/Outlaw kills happen?

- **Population:** Kills by the team with an Operator or Outlaw, after buy-phase end and before the round result
- **Numerator:** Kills in each window of time since buy-phase end
- **Unit:** kills
- **Caveat:** A kill is when the duel ended, not when the hold started.
- **Caveat:** Windows are an analytical choice (0-20, 20-40, 40-60, 60+ s); short rounds can't reach late windows.

## Opening duels (`op.opening` v1)

**Question:** In rounds where they have an Operator, how often does it take or lose the round's first kill?

- **Population:** Team rounds in scope with an Operator/Outlaw holder and a recorded first kill
- **Numerator:** Rounds whose first kill is by the holder with the rifle (won) / of the holder (lost)
- **Unit:** rounds
- **Caveat:** First recorded kill of the round; duels that ended in damage only are not counted.

## Operator on full buys (`op.possession_full_buy` v1)

**Question:** How often does the team have an Operator or Outlaw when it full-buys?

- **Population:** Team rounds in scope with a buy-phase-end inventory snapshot and team loadout >= 15,000
- **Numerator:** Those rounds where at least one player holds an Operator or Outlaw at buy-phase end
- **Unit:** rounds
- **Caveat:** Possession at buy-phase end, not purchase: the feed has no purchase events.
- **Caveat:** Rounds without an inventory snapshot are reported as unknown, never as 'no Operator'.

## Where they play it (`op.setups` v1)

**Question:** Where is the Operator/Outlaw when the team fires it for the first time in a round?

- **Population:** Team rounds on one map and side where the team fired an Operator/Outlaw (kill or hit) between buy-phase end and the round result
- **Numerator:** Rounds whose first Operator shot was taken from this callout
- **Unit:** rounds
- **Caveat:** Callouts are the nearest community callout anchor the shooter could reach on the minimap; an approximation, not an official zone.
- **Caveat:** First recorded Operator shot of the round: where the rifle fought, not necessarily where it set up.
- **Caveat:** A first shot counts as a kill when the same player gets an Operator kill within 1 s.
- **Caveat:** League share uses every team's rounds on the same map and side.

## Rounds won with it (`op.win_association` v1)

**Question:** How often does the team win full-buy rounds with an Operator vs without?

- **Population:** Team full-buy rounds in scope with a known inventory
- **Numerator:** Rounds won
- **Unit:** rounds
- **Caveat:** Association, not cause: economy, opponent and map choice also differ between these rounds.
