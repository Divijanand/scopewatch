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


## How they hit sites (`att.executes` v1)

**Question:** On attack, which site does the team plant on, how fast, where does first contact happen, and what utility goes in before the plant?

- **Population:** The team's attack rounds on one map (buy-phase end to round result)
- **Numerator:** Rounds with a spike plant on this site
- **Unit:** attack rounds
- **Caveat:** The site is the nearest site callout to the plant position.
- **Caveat:** Rounds without a plant are counted in the total but have no site: retakes and eco saves are mixed in there.
- **Caveat:** Execute utility = abilities cast by the attackers in the 25 s before the plant. The feed records the cast, not where it landed.
- **Caveat:** Against an Operator = rounds where a defender held an Operator/Outlaw at buy-phase end; 'lost it without a kill' means that holder died before the round result with no Operator kill.
- **Caveat:** Site entry = the first hit or kill before the plant where the attacker involved stood in that site's callouts (for example A Main or A Rubble for an A plant). Rounds won without a fight there have no entry.

## Where it dies (`op.deaths` v1)

**Question:** Where does the team's Operator/Outlaw holder die, and from where is the kill taken?

- **Population:** Deaths of a player who held an Operator/Outlaw at buy-phase end, on one map and side, between buy-phase end and the round result
- **Numerator:** Deaths at this callout
- **Unit:** deaths
- **Caveat:** Holder = had the Operator/Outlaw at buy-phase end; they may have dropped or swapped it.
- **Caveat:** Callouts are the nearest reachable community callout anchor, an approximation.

## Getting away with it (`op.escapes` v1)

**Question:** After an Operator kill, does the shooter use a movement ability, and do they survive the next 5 seconds?

- **Population:** Operator/Outlaw kills by the team in scope, between buy-phase end and the round result
- **Numerator:** Kills where the shooter died within 5 s (punished)
- **Unit:** Operator kills
- **Caveat:** Movement = dash, teleport or speed ability (Jett, Chamber, Yoru, Veto, Raze, Neon, Omen, Waylay) cast from 1 s before to 4 s after the kill.
- **Caveat:** A cast is recorded; whether it actually moved the player to safety isn't.
- **Caveat:** Survival is association, not cause: holders who escape may also have picked safer angles.

## How far forward (`op.forwardness` v1)

**Question:** How far toward the enemy spawn are their Operator fights, compared with every team on this map?

- **Population:** Operator/Outlaw kills and hits by the team on one map and side, with a shooter position
- **Numerator:** Median of d(own spawn) / (d(own spawn) + d(enemy spawn)) at the shooter's position
- **Unit:** engagements
- **Caveat:** Needs a single map and side.
- **Caveat:** Positions come from the event, not continuous tracking.

## What the Operator buys them (`op.gamble` v1)

**Question:** In rounds a player holds the Operator/Outlaw, does it earn kills before it's lost, and does the enemy end up with it?

- **Population:** Player rounds in scope where the player holds an Operator/Outlaw at buy-phase end
- **Numerator:** Rounds where the holder died without an Operator kill (lost it for nothing)
- **Unit:** Operator rounds
- **Caveat:** Kept = the holder was alive at the end of the round, so the rifle carries over.
- **Caveat:** Picked up by the enemy = an enemy fired an Operator/Outlaw later in the round without holding one at buy-phase end. The feed has no weapon pickup events, so a pickup that never fired isn't seen.
- **Caveat:** Deaths after the round result count: dying in the post-round still loses the rifle.

## Who carries it (`op.holder_share` v1)

**Question:** Which player has the Operator/Outlaw in the team's Operator rounds?

- **Population:** Team rounds in scope where at least one player holds an Operator/Outlaw at buy-phase end
- **Numerator:** Rounds where this player holds it (a round with two holders counts for both)
- **Unit:** rounds
- **Caveat:** Shares can sum above 100% when two players hold one in the same round.

## How it gets broken (`op.how_it_dies` v1)

**Question:** When the team's Operator holder dies, was it after enemy flashes or stuns, smokes, or several enemies at once?

- **Population:** Deaths of a player who held an Operator/Outlaw at buy-phase end, between buy-phase end and the round result
- **Numerator:** Deaths with an enemy flash or stun cast nearby in the 4 s before
- **Unit:** deaths
- **Caveat:** 'Nearby' = cast by an enemy standing within 35 m of where the holder died. The feed records where utility was thrown from, not where it landed or who it blinded.
- **Caveat:** Casts without a reliable position (ability-supplement quality) aren't counted, so utility is undercounted.
- **Caveat:** Swarmed = two or more different enemies hit the holder in the 3 s before the death.

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
