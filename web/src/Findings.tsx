import type { Rate, Tendencies } from './api'
import { cap, pct } from './api'
import type { EvidenceRequest } from './Evidence'
import { timeColor } from './MapView'

export const BUCKETS = ['0-20s', '20-40s', '40-60s', '60s+'] as const
export type Bucket = (typeof BUCKETS)[number]
const BUCKET_MID: Record<Bucket, number> = { '0-20s': 10, '20-40s': 30, '40-60s': 50, '60s+': 75 }
const BUCKET_LABEL: Record<Bucket, string> = { '0-20s': '0–20s', '20-40s': '20–40s', '40-60s': '40–60s', '60s+': '60s and later' }
export const bucketOf = (t: number): Bucket => (t < 20 ? '0-20s' : t < 40 ? '20-40s' : t < 60 ? '40-60s' : '60s+')

function Evidence({ r, unit }: { r: Rate | null | undefined; unit: string }) {
  if (!r || r.n === 0) return null
  return (
    <span className={r.small_sample ? 'evidence thin' : 'evidence'}>
      {r.k} of {r.n} {unit}
      {r.lo != null && r.hi != null && <> (likely {Math.round(r.lo * 100)}–{Math.round(r.hi * 100)}%)</>}
      {r.small_sample && <>. Small sample, treat as a hint.</>}
    </span>
  )
}

function Bar({ r }: { r: Rate | null | undefined }) {
  if (!r || r.p == null) return <span className="bar" aria-hidden />
  return (
    <span className="bar" aria-hidden>
      {r.lo != null && r.hi != null && (
        <span className="bar-range" style={{ left: `${r.lo * 100}%`, width: `${(r.hi - r.lo) * 100}%` }} />
      )}
      <span className="bar-fill" style={{ width: `${r.p * 100}%` }} />
    </span>
  )
}

function ShowRounds({ onClick, n }: { onClick: () => void; n: number }) {
  if (!n) return null
  return <button className="show-rounds" onClick={onClick}>Show the rounds</button>
}

export type Focus = { metric: string; name: string; rounds: Set<string> }

const list = (xs: string[]) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`)

function Spot({ b, focus, metric, onFocus, detail }: {
  b: Record<string, any> & { rate: Rate }; focus: Focus | null; metric: string
  onFocus: (f: Focus | null) => void; detail: string
}) {
  const on = focus?.metric === metric && focus.name === b.callout
  const league: Rate | null = b.league ?? null
  return (
    <li>
      <button aria-pressed={on}
              onClick={() => onFocus(on ? null : { metric, name: b.callout, rounds: new Set(b.round_keys as string[]) })}>
        <span className="where">{b.callout}</span>
        <span className="detail">{detail}</span>
        <span className="bar" aria-hidden>
          <span className="bar-fill" style={{ width: `${(b.rate.p ?? 0) * 100}%` }} />
          {league?.p != null && <span className="bar-league" style={{ left: `${league.p * 100}%` }} />}
        </span>
        <span className="num">{b.rate.k}</span>
      </button>
    </li>
  )
}

const ability = (a: string) => a.split('-').map(cap).join(' ')
const frac = (r: Rate | null | undefined) => (r && r.n ? `${r.k} of ${r.n}` : '–')

/** One group of rounds in a breakdown; clicking opens exactly those rounds. */
function BucketRow({ b, detail, onOpen }: { b: Record<string, any> & { rate: Rate }; detail: string; onOpen: () => void }) {
  return (
    <li>
      <button onClick={onOpen} disabled={!b.rate.k} title={b.rate.k ? 'Show these rounds' : undefined}>
        <span className="where">{b.label}</span>
        <span className="detail">{detail}</span>
        <Bar r={b.rate} />
        <span className="num">{b.rate.k}</span>
      </button>
    </li>
  )
}

const UTIL_WORD: Record<string, [string, string]> = {
  smoke: ['smoke', 'smokes'], flash: ['flash', 'flashes'], stun: ['stun', 'stuns'], info: ['recon', 'recon'],
}

function SiteBlock({ b, n, onOpen }: { b: Record<string, any> & { rate: Rate }; n: number; onOpen: () => void }) {
  const u = b.utility_per_round as Record<string, number>
  const utilText = Object.entries(UTIL_WORD)
    .filter(([k]) => (u[k] ?? 0) >= 0.1)
    .map(([k, [one, many]]) => `${u[k]} ${u[k] === 1 ? one : many}`)
  const pace = (b.pace as { pace: string; k: number }[]).filter((p) => p.k > 0)
  const vs = b.vs_op as { rounds: number; op_kill: Rate; lost_no_kill: Rate }
  const league: Rate | null = b.league
  return (
    <li className="site">
      <div className="site-head">
        <span className="site-name">{b.site} site</span>
        <Bar r={b.rate} />
        <span className="num">{b.rate.k}<span className="of">/{n}</span></span>
      </div>
      <p>
        Planted here in {pct(b.rate)} of attack rounds{league?.p != null && <> (league {pct(league)})</>}, round won {frac(b.won)}.
        {b.entry_t != null && (
          <> First fight in the {b.site} area at about <b>{Math.round(b.entry_t)}s</b>
            {b.entry_callouts.length > 0 && <>, at {list((b.entry_callouts as { callout: string }[]).map((c) => c.callout))}</>}; plant at about {Math.round(b.plant_t)}s.</>
        )}
        {pace.length > 0 && <> Pace: {pace.map((p) => `${p.pace} ${p.k}`).join(', ')}.</>}
      </p>
      {utilText.length > 0 && (
        <p>
          Utility in the 25 s before the plant, per round: {utilText.join(', ')}.
          {b.abilities.length > 0 && <> Most used: {(b.abilities as { ability: string; rounds: number }[]).slice(0, 4)
            .map((a) => `${ability(a.ability)} (${a.rounds} of ${b.rate.k})`).join(', ')}.</>}
        </p>
      )}
      {vs.rounds > 0 && (
        <p className="site-op">
          Against a defending Operator ({vs.rounds} round{vs.rounds === 1 ? '' : 's'}): it got a kill in {vs.op_kill.k} and
          died without one in <b>{vs.lost_no_kill.k}</b>.
        </p>
      )}
      <button className="show-rounds" onClick={onOpen}>Show the rounds</button>
    </li>
  )
}

type Wpa = { n: number; mean: number; lo: number; hi: number; league_mean: number }
type WpaPlayer = { player_id: string; player_name: string; n: number; mean: number; lo?: number; hi?: number; small_sample?: boolean }

const pts = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`

/** A scale in points of round-win chance: the team's likely range, its mean, and the league mean (hollow). */
function WpaScale({ v }: { v: Wpa }) {
  const lim = Math.max(10, Math.ceil(Math.max(Math.abs(v.lo), Math.abs(v.hi), Math.abs(v.league_mean)) / 5) * 5)
  const x = (p: number) => `${((p + lim) / (2 * lim)) * 100}%`
  return (
    <div className="wpa" aria-hidden>
      <span>{pts(-lim)}</span>
      <span className="wpa-track">
        <span className="wpa-zero" style={{ left: x(0) }} />
        <span className="wpa-range" style={{ left: x(v.lo), width: `calc(${x(v.hi)} - ${x(v.lo)})` }} />
        <span className="fwd-mark league" style={{ left: x(v.league_mean) }} />
        <span className="fwd-mark team" style={{ left: x(v.mean) }} />
      </span>
      <span>{pts(lim)}</span>
    </div>
  )
}

type Props = {
  t: Tendencies
  focus: Focus | null
  onFocus: (f: Focus | null) => void
  side: string | null
  activePlayer: string | null
  onPlayer: (id: string | null) => void
  buckets: Set<Bucket>
  onBucket: (b: Bucket) => void
  onEvidence: (req: EvidenceRequest) => void
}

export function Findings({ t, side, activePlayer, onPlayer, buckets, onBucket, onEvidence, focus, onFocus }: Props) {
  const sideWord = side === 'attacker' ? 'attack' : side === 'defender' ? 'defense' : null
  const poss = t['op.possession_full_buy']
  const hold = t['op.holder_share']
  const time = t['op.kill_timing']
  const open = t['op.opening']
  const win = t['op.win_association']
  const fwd = t['op.forwardness']
  const setups = t['op.setups']
  const deaths = t['op.deaths']
  const s0 = setups?.breakdown[0]
  const d0 = deaths?.breakdown[0]
  const exe = t['att.executes']
  const recon = t['util.recon_timing']
  const duels = t['fights.dry_duels']
  const wpa = t['op.wpa']
  const pred = t['team.predictability']
  const score = pred?.value.score as number | null | undefined
  const wv = wpa?.value as Wpa | undefined
  // most rounds first: a one-round number never headlines
  const wpaPlayers = ([...(wpa?.breakdown ?? [])] as unknown as WpaPlayer[]).sort((a, b) => b.n - a.n || a.player_name.localeCompare(b.player_name))
  const gamble = t['op.gamble']
  const esc = t['op.escapes']
  const broke = t['op.how_it_dies']
  const openBucket = (m: typeof gamble, b: Record<string, any>, claim: string) => onEvidence({
    metric: m.metric, bucket: b.bucket, claim, supportingLabel: `${b.label} (${b.rate.k})`, contraryLabel: 'The rest',
  })
  const gLeague: Rate | null = gamble?.value.league_lost ?? null
  const moved = esc?.breakdown.find((b) => b.bucket === 'moved')
  const stayed = esc?.breakdown.find((b) => b.bucket === 'stayed')
  const sLeague: Rate | null = s0?.league ?? null
  const sCompare = s0 && sLeague?.p != null && s0.rate.p != null
    ? s0.rate.p > sLeague.p * 1.5 ? 'far more often than' : s0.rate.p < sLeague.p / 1.5 ? 'less often than' : 'about as often as'
    : null
  const main = hold.breakdown[0]
  const shift: Rate | undefined = hold.value.possession_shift
  const top = time.value.top_bucket as Bucket | undefined
  const kills = time.breakdown[0]?.rate.n ?? 0

  const timingRead = top === '0-20s' ? 'an opening-pick rifle' : top === '60s+' ? 'a retake and post-plant rifle' : 'a mid-round rifle'
  const fv = fwd.value as { team_median?: number; league_median?: number; n?: number }
  const delta = fv.team_median != null && fv.league_median != null ? fv.team_median - fv.league_median : null
  const rv = recon?.value as any
  const dv = duels?.value as any
  const dpts = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v * 100).toFixed(1)}`
  const duelRows = (duels?.breakdown ?? []).filter((b: any) => b.n > 0).slice(0, 7)
  const agentsBeyond = (duels?.breakdown ?? []).filter((b: any) => b.agent && b.beyond_noise && b.diff > 0).slice(0, 2)

  return (
    <div className="findings">
      {pred && pred.breakdown.length > 0 && (
        <section>
          <h3>How predictable they are</h3>
          {score != null ? (
            <p className="claim">
              More predictable than <b>{score}%</b> of teams on this map{sideWord && <> on {sideWord}</>}.
              {score >= 70 ? ' Easy to prepare for.' : score <= 30 ? ' Hard to prepare for.' : ''}
            </p>
          ) : (
            <p className="claim">Not enough rounds to compare them with other teams yet.</p>
          )}
          <ul className="spots predict">
            {pred.breakdown.map((b) => (
              <li key={b.habit}>
                <button onClick={() => onEvidence({
                  metric: pred.metric, bucket: b.bucket,
                  claim: `${b.label}: rounds where they chose ${b.choice}.`,
                  supportingLabel: `${b.choice} (${b.rate.k})`, contraryLabel: 'Something else',
                })}>
                  <span className="where">{b.label}</span>
                  <span className="detail">
                    Best guess {b.choice}: right {b.rate.k} of {b.rate.n} ({pct(b.rate)})
                    {b.league_median != null && `, typical team ${Math.round(b.league_median * 100)}%`}
                    {b.small_sample && '. Too few rounds to compare'}
                  </span>
                  <span className="bar" aria-hidden>
                    {b.percentile != null && <span className="bar-fill" style={{ width: `${b.percentile}%` }} />}
                  </span>
                  <span className="num">{b.percentile ?? '–'}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="hint">
            For each habit: if an opponent always guessed their most common choice, how often they’d be right. The number on
            the right is the percentage of other teams on this map and side that are less predictable. Click a habit to open those
            rounds. Predictable isn’t bad on its own; it’s what an opponent can prepare for.
          </p>
        </section>
      )}
      {recon && rv?.n >= (rv.min_league ?? 20) && rv.first_recon && (
        <section>
          <h3>Recon timing</h3>
          <p className="claim">
            Their first recon goes out at about <b>{rv.first_recon.median} s</b>
            {rv.vs_league != null && Math.abs(rv.vs_league) >= 1
              ? <> ({Math.abs(rv.vs_league)} s {rv.vs_league < 0 ? 'earlier' : 'later'} than the league’s {rv.league_first_recon.median} s)</>
              : rv.league_first_recon && <> (league {rv.league_first_recon.median} s)</>}
            {side === 'attacker' && rv.recon_to_plant && <>, and they plant about <b>{rv.recon_to_plant.median} s</b> later</>}.
          </p>
          <span className={rv.n < 40 ? 'evidence thin' : 'evidence'}>
            {rv.n} rounds; middle half of first recons {rv.first_recon.q1}–{rv.first_recon.q3} s; no recon in {pct(rv.no_recon)} of rounds.
            {side === 'attacker' && rv.recon_to_contact && <> First fight {rv.recon_to_contact.median} s after the recon.</>}
          </span>
          {rv.late?.n > 0 && rv.on_time?.n > 0 && (
            <p className="aside">
              When their first recon comes late (after {rv.split_at} s, the league’s slowest quarter) or not at all, they win{' '}
              <b>{pct(rv.late)}</b> of rounds (likely {Math.round(rv.late.lo * 100)}–{Math.round(rv.late.hi * 100)}%), against{' '}
              {pct(rv.on_time)} on time (likely {Math.round(rv.on_time.lo * 100)}–{Math.round(rv.on_time.hi * 100)}%).
              {' '}Late recon is sometimes a slow default, not a denial; the feed doesn’t record a dart being destroyed.
            </p>
          )}
          {rv.first_recon_agent?.length > 0 && (
            <p className="hint">First recon usually from {list(rv.first_recon_agent.slice(0, 2).map((a: any) => `${cap(a.agent)} (${a.n})`))}.</p>
          )}
          <ShowRounds n={recon.evidence_counts.supporting + recon.evidence_counts.contrary} onClick={() => onEvidence({
            metric: recon.metric, claim: 'Rounds where their first recon came late or not at all.',
            supportingLabel: `Lost (${recon.evidence_counts.supporting})`,
            contraryLabel: `Won (${recon.evidence_counts.contrary})`,
          })} />
        </section>
      )}
      {duels?.warnings.map((w) => <p key={w} className="hint">{w}</p>)}
      {duels && dv?.total >= 20 && dv.diff != null && (
        <section>
          <h3>Dry duels</h3>
          <p className="claim">
            With no utility around, they win {Math.abs(dv.diff) < 0.01
              ? <>about as many fights as the opener advantage predicts</>
              : <><b>{Math.abs(dv.diff * 100).toFixed(1)} points</b> {dv.diff > 0 ? 'more' : 'fewer'} fights than the opener advantage predicts</>}
            {dv.diff > 0 && agentsBeyond.length > 0 && <>, most clearly on {list(agentsBeyond.map((a: any) => cap(a.agent)))}</>}.
          </p>
          <span className={dv.total < 100 ? 'evidence thin' : 'evidence'}>
            {dv.total} dry fights; likely between {dpts(dv.lo)} and {dpts(dv.hi)} points.
            {' '}{dv.beyond_noise ? 'The range excludes 0.' : 'The range includes 0, so this is a hint, not a real difference yet.'}
          </span>
          <ul className="carriers">
            {duelRows.map((b: any) => (
              <li key={b.bucket + (b.agent ?? '')}>
                <span className="wpa-row">
                  <span className="who">{b.agent ? cap(b.agent) : b.label}</span>
                  <span className="agents">{b.n} fights, won {Math.round(b.actual * 100)}% against {Math.round(b.expected * 100)}% expected</span>
                  <span className="num">{dpts(b.diff)}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="hint">
            The player who shoots first wins most fights, so each fight is compared with the league’s rate for the same
            map, side, players alive and plant. Dry = no flash, smoke, recon, ult or ability damage near the fight in the
            4 s before, from either team.
          </p>
        </section>
      )}
      {wv && wv.n > 0 && (
        <section>
          <h3>What the Operator is worth</h3>
          <p className="claim">
            An Operator round is worth <b>{pts(wv.mean)} points</b> of round-win chance to them
            {sideWord && <> on {sideWord}</>}, against <b>{pts(wv.league_mean)}</b> for every team here.
          </p>
          <span className={wv.n < 10 ? 'evidence thin' : 'evidence'}>
            {wv.n} Operator rounds; likely between {pts(wv.lo)} and {pts(wv.hi)}.
            {wv.n < 10 && ' Small sample, treat as a hint.'}
          </span>
          <WpaScale v={wv} />
          <p className="aside">
            {wv.lo <= wv.league_mean && wv.league_mean <= wv.hi
              ? 'That range includes the league average, so this is a hint, not a real difference yet.'
              : wv.mean > wv.league_mean
                ? 'Their Operator earns more than the league’s, and the range doesn’t overlap the league average.'
                : 'Their Operator earns less than the league’s, and the range doesn’t overlap the league average.'}
          </p>
          {wpaPlayers.length > 1 && (
            <ul className="carriers">
              {wpaPlayers.slice(0, 5).map((p) => (
                <li key={p.player_id}>
                  <span className="wpa-row">
                    <span className="who">{p.player_name}</span>
                    <span className="agents">{p.n} round{p.n === 1 ? '' : 's'}{p.small_sample ? ', too few for a range' : p.lo != null && p.hi != null ? `, likely ${pts(p.lo)} to ${pts(p.hi)}` : ''}</span>
                    <span className="num">{pts(p.mean)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="hint">
            Each Operator kill is credited with how much it moved the round-win chance, and the holder’s death is charged
            the same way, using our win-probability model. The model doesn’t see positions, and trades aren’t split.
          </p>
          <ShowRounds n={wpa.evidence_counts.supporting + wpa.evidence_counts.contrary} onClick={() => onEvidence({
            metric: wpa.metric, claim: 'Operator rounds where the rifle added round-win chance, and where it cost it.',
            supportingLabel: `Added (${wpa.evidence_counts.supporting})`,
            contraryLabel: `Cost (${wpa.evidence_counts.contrary})`,
          })} />
        </section>
      )}
      {wpa?.warnings.map((w) => <p key={w} className="hint">{w}</p>)}
      {exe && side === 'attacker' && exe.breakdown.length > 0 && (
        <section>
          <h3>How they hit sites</h3>
          <p className="claim">
            They plant on <b>{exe.breakdown[0].site}</b> most: <b>{exe.breakdown[0].rate.k} of {exe.breakdown[0].rate.n}</b> attack
            rounds{exe.breakdown[0].entry_t != null && <>, with the first fight there at about {Math.round(exe.breakdown[0].entry_t)}s</>}.
          </p>
          <Evidence r={exe.breakdown[0].rate} unit="attack rounds" />
          <ol className="sites">
            {exe.breakdown.map((b) => (
              <SiteBlock key={b.site} b={b} n={exe.breakdown[0].rate.n}
                         onOpen={() => onEvidence({
                           metric: exe.metric, bucket: b.bucket, claim: `Attack rounds where they planted on ${b.site}.`,
                           supportingLabel: `${b.site} plants (${b.rate.k})`, contraryLabel: 'Other sites',
                         })} />
            ))}
          </ol>
          {exe.value.no_plant?.n > 0 && (
            <p className="hint">
              Pace is by plant time: fast before 35 s, default 35–70 s, late after 70 s.
              No plant in {frac(exe.value.no_plant)} attack rounds (won {frac(exe.value.no_plant_won)}). The feed records where
              utility was thrown from, not where it landed: open the rounds and watch the VOD to see the actual execute.
            </p>
          )}
        </section>
      )}
      {gamble?.rate && gamble.rate.n > 0 && (
        <section>
          <h3>What the Operator buys them</h3>
          <p className="claim">
            They lose the Operator without getting an Operator kill in <b>{pct(gamble.rate)}</b> of their Operator rounds.
          </p>
          <Evidence r={gamble.rate} unit="Operator rounds" />
          {gLeague?.p != null && (
            <p className="aside">
              Every team on this map and side: {pct(gLeague)}.{' '}
              {gamble.rate.p != null && (gamble.rate.p > gLeague.p * 1.25
                ? 'Their Operator is a worse gamble than most.'
                : gamble.rate.p < gLeague.p / 1.25 ? 'Their Operator pays off more often than most.' : 'About the league norm.')}
            </p>
          )}
          <ul className="spots">
            {gamble.breakdown.map((b) => (
              <BucketRow key={b.bucket} b={b}
                         detail={b.won?.n ? `round won ${frac(b.won)}` : ''}
                         onOpen={() => openBucket(gamble, b, `Operator rounds: ${b.label.toLowerCase()}.`)} />
            ))}
          </ul>
          <p className="hint">
            {gamble.value.kills_per_round} Operator kills per Operator round; two or more in {frac(gamble.value.multi_kill)}.
            Click a row to open those rounds.
          </p>
        </section>
      )}

      {esc?.rate && esc.rate.n > 0 && (
        <section>
          <h3>Getting away with it</h3>
          <p className="claim">
            After an Operator kill, the shooter dies within 5 seconds in <b>{pct(esc.rate)}</b> of cases.
          </p>
          <Evidence r={esc.rate} unit="Operator kills" />
          {moved && stayed && (moved.rate.k > 0) && (
            <p className="aside">
              With a dash, teleport or speed ability around the kill they die within 5 s in {frac(moved.punished)};
              without one, {frac(stayed.punished)}.
              {moved.abilities?.length > 0 && <> Most used: {(moved.abilities as { ability: string }[]).map((a) => ability(a.ability)).join(', ')}.</>}
            </p>
          )}
          <ul className="spots">
            {(esc.value.by_agent as { agent: string; kills: number; punished: Rate; moved: Rate }[]).slice(0, 4).map((a) => (
              <li key={a.agent}>
                <span className="spot-static">
                  <span className="where">{cap(a.agent)}</span>
                  <span className="detail">moved after {frac(a.moved)}, died within 5 s {frac(a.punished)}</span>
                  <Bar r={a.punished} />
                  <span className="num">{a.kills}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="hint">Per agent: Operator kills, and how often the shooter was caught after. Movement casts are recorded, not whether they reached cover.</p>
          <ShowRounds n={esc.evidence_counts.supporting} onClick={() => openBucket(esc, esc.breakdown.find((b) => b.bucket === 'punished')!,
            'Rounds where the Operator shooter died within 5 s of a kill.')} />
        </section>
      )}

      {broke?.rate && broke.rate.n > 0 && (
        <section>
          <h3>How it gets broken</h3>
          <p className="claim">
            <b>{pct(broke.rate)}</b> of their Operator deaths come right after an enemy flash or stun from close by.
          </p>
          <Evidence r={broke.rate} unit="Operator-holder deaths" />
          <ul className="spots">
            {broke.breakdown.map((b) => (
              <BucketRow key={b.bucket} b={b} detail=""
                         onOpen={() => openBucket(broke, b, `Operator deaths: ${b.label.toLowerCase()}.`)} />
            ))}
          </ul>
          {broke.value.top_utility?.length > 0 && (
            <p className="aside">Utility seen most before these deaths: {(broke.value.top_utility as { ability: string; k: number }[]).map((a) => `${ability(a.ability)} (${a.k})`).join(', ')}.</p>
          )}
          <p className="hint">
            Counts enemy utility thrown from within 35 m in the 4 s before the death. The feed records where utility was
            thrown from, not where it landed, so treat this as a lead to check in the VOD.
          </p>
        </section>
      )}

      {s0 && (
        <section>
          <h3>Where they play it</h3>
          <p className="claim">
            Their first Operator shot comes from <b>{s0.callout}</b> in <b>{s0.rate.k} of {s0.rate.n}</b> rounds
            {s0.targets[0] && <>, aimed toward {s0.targets[0].callout}</>}. {s0.players[0] && <>Usually {s0.players[0].name}, </>}
            around {Math.round(s0.median_t)}s in.
          </p>
          <Evidence r={s0.rate} unit="rounds with an Operator shot" />
          {sCompare && (
            <p className="aside">
              That’s {sCompare} the rest of the league: every team’s Operator starts from {s0.callout} in{' '}
              {pct(sLeague)} of their rounds here.
            </p>
          )}
          <ul className="spots">
            {setups.breakdown.slice(0, 6).map((b) => (
              <Spot key={b.callout} b={b} focus={focus} metric={setups.metric.id} onFocus={onFocus}
                    detail={`${list((b.players as { name: string }[]).slice(0, 2).map((p) => p.name))}${b.targets[0] ? ` → ${b.targets[0].callout}` : ''}, ${b.kills} kill${b.kills === 1 ? '' : 's'}`} />
            ))}
          </ul>
          <p className="hint">
            Click a callout to show only those rounds on the map. The hollow mark on each bar is the league share.
            Callouts are the nearest community callout, an approximation.
          </p>
          <ShowRounds n={setups.evidence_counts.supporting} onClick={() => onEvidence({
            metric: setups.metric, bucket: (focus?.metric === setups.metric.id ? focus.name : s0.callout),
            claim: `Rounds whose first Operator shot came from ${focus?.metric === setups.metric.id ? focus.name : s0.callout}.`,
            supportingLabel: focus?.metric === setups.metric.id ? focus.name : s0.callout,
            contraryLabel: 'Somewhere else',
          })} />
        </section>
      )}
      {setups && !s0 && setups.warnings.length === 0 && side && (
        <section>
          <h3>Where they play it</h3>
          <p className="claim">They never fired an Operator on this map and side in these games.</p>
        </section>
      )}

      {d0 && (
        <section>
          <h3>Where it dies</h3>
          <p className="claim">
            Their Operator player dies most at <b>{d0.callout}</b>: <b>{d0.rate.k} of {d0.rate.n}</b> deaths
            {d0.from_[0] && <>, usually to someone at {d0.from_[0].callout}</>}.
          </p>
          <Evidence r={d0.rate} unit="Operator-holder deaths" />
          {deaths.value.first_death?.n > 0 && (
            <p className="aside">The holder is the round’s first death in {deaths.value.first_death.k} of {deaths.value.first_death.n} of these.</p>
          )}
          <ul className="spots">
            {deaths.breakdown.slice(0, 5).map((b) => (
              <Spot key={b.callout} b={b} focus={focus} metric={deaths.metric.id} onFocus={onFocus}
                    detail={`${b.from_[0] ? `from ${b.from_[0].callout}, ` : ''}${(b.weapons as { weapon: string }[]).map((w) => cap(w.weapon)).join(' / ')}, ~${Math.round(b.median_t)}s`} />
            ))}
          </ul>
          <p className="hint">Where a counter-play pays off. Click a callout to show those rounds on the map.</p>
          <ShowRounds n={deaths.evidence_counts.supporting} onClick={() => onEvidence({
            metric: deaths.metric, bucket: (focus?.metric === deaths.metric.id ? focus.name : d0.callout),
            claim: `Rounds where the Operator player died at ${focus?.metric === deaths.metric.id ? focus.name : d0.callout}.`,
            supportingLabel: focus?.metric === deaths.metric.id ? focus.name : d0.callout,
            contraryLabel: 'Died elsewhere',
          })} />
        </section>
      )}
      <section>
        <h3>How often they have it</h3>
        <p className="claim">
          {poss.rate && poss.rate.n > 0
            ? poss.rate.k === 0
              ? <>They never had an Operator on a full buy here.</>
              : <>They have an Operator in <b>{pct(poss.rate)}</b> of full-buy rounds{sideWord && <> on {sideWord}</>}.</>
            : <>No full-buy rounds with a known loadout match these filters.</>}
        </p>
        <Evidence r={poss.rate} unit="full buys" />
        {poss.unknown.map((u) => <span key={u.reason} className="evidence">{u.count} rounds unknown: {u.reason}.</span>)}
        <dl className="econ">
          {poss.breakdown.map((b) => (
            <div key={b.economy}>
              <dt>{b.economy === 'full' ? 'Full buy' : b.economy === 'half' ? 'Half buy' : 'Eco'}</dt>
              <dd><Bar r={b.rate} /><span className="num">{pct(b.rate)}</span></dd>
            </div>
          ))}
        </dl>
        {win.rate && win.rate.n > 0 && (
          <p className="aside">
            They win <b>{pct(win.rate)}</b> of full-buy rounds with one, against <b>{pct(win.value.without)}</b> without.
            That’s an association, not proof the rifle caused it.
          </p>
        )}
        <ShowRounds n={poss.evidence_counts.supporting + poss.evidence_counts.contrary} onClick={() => onEvidence({
          metric: poss.metric, claim: `Operator in ${poss.rate?.k} of ${poss.rate?.n} full-buy rounds.`,
          supportingLabel: `With Operator (${poss.evidence_counts.supporting})`,
          contraryLabel: `Without (${poss.evidence_counts.contrary})`,
        })} />
      </section>

      {main && (
        <section>
          <h3>Who carries it</h3>
          <p className="claim">
            <b>{main.name}</b> has it in <b>{pct(main.rate)}</b> of their Operator rounds, mostly on {cap(main.agent)}.
          </p>
          <Evidence r={main.rate} unit="Operator rounds" />
          <ul className="carriers">
            {hold.breakdown.slice(0, 5).map((c) => (
              <li key={c.player_id}>
                <button aria-pressed={activePlayer === c.player_id}
                        onClick={() => onPlayer(activePlayer === c.player_id ? null : c.player_id)}>
                  <span className="who">{c.name}</span>
                  <span className="agents">{(c.agents as string[]).map(cap).join(', ')}</span>
                  <Bar r={c.rate} />
                  <span className="num">{c.rate.k}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="hint">Click a player to show only their fights on the map.</p>
          {shift && shift.n > 0 && (
            <p className="aside">In {shift.k} of {shift.n} Operator rounds someone other than that map’s main carrier had it.</p>
          )}
          <ShowRounds n={hold.evidence_counts.supporting + hold.evidence_counts.contrary} onClick={() => onEvidence({
            metric: hold.metric, claim: `${main.name} carries it in ${main.rate.k} of ${main.rate.n} Operator rounds.`,
            supportingLabel: `${main.name} (${hold.evidence_counts.supporting})`,
            contraryLabel: `Someone else (${hold.evidence_counts.contrary})`,
          })} />
        </section>
      )}

      {kills > 0 && top && (
        <section>
          <h3>When it fires</h3>
          <p className="claim">
            <b>{pct(time.rate)}</b> of their Operator kills come {top === '60s+' ? 'after 60 seconds' : `in the ${BUCKET_LABEL[top]} window`}: {timingRead}.
          </p>
          <Evidence r={time.rate} unit="Operator kills" />
          <div className="timing" role="group" aria-label="Filter the map by round time">
            {time.breakdown.map((b) => {
              const k = b.bucket as Bucket
              return (
                <button key={k} aria-pressed={buckets.has(k)} onClick={() => onBucket(k)} className="tbin">
                  <span className="tcol" style={{ height: `${(b.rate.p ?? 0) * 100}%`, background: timeColor(BUCKET_MID[k]) }} />
                  <span className="tlabel">{BUCKET_LABEL[k]}</span>
                  <span className="num">{b.rate.k}</span>
                </button>
              )
            })}
          </div>
          <p className="hint">
            Time counts from the end of the buy phase. {time.value.post_plant?.k ?? 0} of {kills} kills came after a plant.
            Click a column to show only those fights on the map.
          </p>
          <ShowRounds n={time.evidence_counts.supporting} onClick={() => onEvidence({
            metric: time.metric, bucket: top, claim: `Rounds with an Operator kill in the ${BUCKET_LABEL[top]} window.`,
            supportingLabel: `${BUCKET_LABEL[top]} (${time.evidence_counts.supporting})`,
            contraryLabel: `Other windows only (${time.evidence_counts.contrary})`,
          })} />
        </section>
      )}

      {open.rate && open.rate.n > 0 && (
        <section>
          <h3>Opening duels</h3>
          <p className="claim">
            In Operator rounds the rifle takes the first kill <b>{pct(open.rate)}</b> of the time; the holder dies first in{' '}
            <b>{pct(open.value.holder_died_first)}</b>.
          </p>
          <Evidence r={open.rate} unit="Operator rounds with a first kill" />
          <ShowRounds n={open.evidence_counts.supporting + open.evidence_counts.contrary} onClick={() => onEvidence({
            metric: open.metric, claim: `Operator took the first kill in ${open.rate?.k} of ${open.rate?.n} rounds.`,
            supportingLabel: `Operator opened (${open.evidence_counts.supporting})`,
            contraryLabel: `Didn’t (${open.evidence_counts.contrary})`,
          })} />
        </section>
      )}

      {delta != null && (fv.n ?? 0) >= 5 && (
        <section>
          <h3>How far forward</h3>
          <p className="claim">
            They take Operator fights{' '}
            <b>{Math.abs(delta) < 0.03 ? 'about as far forward as' : delta > 0 ? 'further forward than' : 'further back than'}</b>{' '}
            the average {sideWord ?? ''} Operator on this map.
          </p>
          <div className="fwd" aria-hidden>
            <span>Own spawn</span>
            <span className="fwd-track">
              <span className="fwd-mark league" style={{ left: `${fv.league_median! * 100}%` }} />
              <span className="fwd-mark team" style={{ left: `${fv.team_median! * 100}%` }} />
            </span>
            <span>Enemy spawn</span>
          </div>
          <span className="evidence">Median of {fv.n} engagements. The hollow mark is the median for every team on this map and side.</span>
        </section>
      )}
      {fwd.warnings.map((w) => <p key={w} className="hint">{w}</p>)}
    </div>
  )
}
