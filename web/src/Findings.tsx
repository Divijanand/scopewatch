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

type Props = {
  t: Tendencies
  side: string | null
  activePlayer: string | null
  onPlayer: (id: string | null) => void
  buckets: Set<Bucket>
  onBucket: (b: Bucket) => void
  onEvidence: (req: EvidenceRequest) => void
}

export function Findings({ t, side, activePlayer, onPlayer, buckets, onBucket, onEvidence }: Props) {
  const sideWord = side === 'attacker' ? 'attack' : side === 'defender' ? 'defense' : null
  const poss = t['op.possession_full_buy']
  const hold = t['op.holder_share']
  const time = t['op.kill_timing']
  const open = t['op.opening']
  const win = t['op.win_association']
  const fwd = t['op.forwardness']
  const main = hold.breakdown[0]
  const shift: Rate | undefined = hold.value.possession_shift
  const top = time.value.top_bucket as Bucket | undefined
  const kills = time.breakdown[0]?.rate.n ?? 0

  const timingRead = top === '0-20s' ? 'an opening-pick rifle' : top === '60s+' ? 'a retake and post-plant rifle' : 'a mid-round rifle'
  const fv = fwd.value as { team_median?: number; league_median?: number; n?: number }
  const delta = fv.team_median != null && fv.league_median != null ? fv.team_median - fv.league_median : null

  return (
    <div className="findings">
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
