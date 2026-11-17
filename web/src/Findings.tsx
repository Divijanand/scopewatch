import type { Profile, Rate } from './api'
import { cap, pct } from './api'
import { timeColor } from './MapView'

const BUCKETS = ['0-20s', '20-40s', '40-60s', '60s+'] as const
export type Bucket = (typeof BUCKETS)[number]
const BUCKET_MID: Record<Bucket, number> = { '0-20s': 10, '20-40s': 30, '40-60s': 50, '60s+': 75 }
const BUCKET_LABEL: Record<Bucket, string> = {
  '0-20s': '0–20s', '20-40s': '20–40s', '40-60s': '40–60s', '60s+': '60s and later',
}

function Evidence({ r, unit }: { r: Rate; unit: string }) {
  if (!r || r.n === 0) return null
  const thin = r.n < 10
  return (
    <span className={thin ? 'evidence thin' : 'evidence'}>
      {r.k} of {r.n} {unit}
      {r.lo != null && r.hi != null && <> (likely {Math.round(r.lo * 100)}–{Math.round(r.hi * 100)}%)</>}
      {thin && <>. Small sample, treat as a hint.</>}
    </span>
  )
}

function Bar({ r, color }: { r: Rate; color?: string }) {
  if (r.p == null) return null
  return (
    <span className="bar" aria-hidden>
      {r.lo != null && r.hi != null && (
        <span className="bar-range" style={{ left: `${r.lo * 100}%`, width: `${(r.hi - r.lo) * 100}%` }} />
      )}
      <span className="bar-fill" style={{ width: `${r.p * 100}%`, background: color }} />
    </span>
  )
}

type Props = {
  p: Profile
  side: string | null
  activePlayer: string | null
  onPlayer: (id: string | null) => void
  buckets: Set<Bucket>
  onBucket: (b: Bucket) => void
}

export function Findings({ p, side, activePlayer, onPlayer, buckets, onBucket }: Props) {
  const sideWord = side === 'attacker' ? 'attack' : side === 'defender' ? 'defense' : null
  const full = p.buy_by_economy.full
  const main = p.carriers[0]
  const kills = p.sample.op_kills

  // the time window holding most Operator kills
  const topBucket = BUCKETS.reduce((a, b) => (p.kill_timing[b].kills > p.kill_timing[a].kills ? b : a), BUCKETS[0])
  const timingRead =
    topBucket === '0-20s' ? 'an opening-pick rifle' : topBucket === '60s+' ? 'a retake and post-plant rifle' : 'a mid-round rifle'

  // forwardness vs the league, only meaningful for one side on one map
  const fwds = p.engagements.filter((e) => e.fwd != null && (!side || e.side === side)).map((e) => e.fwd!)
  const fwdMed = fwds.length ? fwds.sort((a, b) => a - b)[Math.floor(fwds.length / 2)] : null
  const base = side ? p.league_fwd[side as 'attacker' | 'defender'] : undefined
  const delta = fwdMed != null && base != null ? fwdMed - base : null

  if (p.sample.rounds === 0) {
    return <p className="empty">No rounds match these filters. Pick another map or side.</p>
  }

  return (
    <div className="findings">
      <section>
        <h3>How often they buy it</h3>
        <p className="claim">
          {p.buy_rate.k === 0
            ? <>They never bought an Operator here.</>
            : <>They buy an Operator in <b>{pct(full)}</b> of full-buy rounds{sideWord && <> on {sideWord}</>}.</>}
        </p>
        <Evidence r={full} unit="full buys" />
        <dl className="econ">
          {(['full', 'half', 'eco'] as const).map((k) => (
            <div key={k}>
              <dt>{k === 'full' ? 'Full buy' : k === 'half' ? 'Half buy' : 'Eco'}</dt>
              <dd><Bar r={p.buy_by_economy[k] ?? { k: 0, n: 0, p: null, lo: null, hi: null }} /><span className="num">{pct(p.buy_by_economy[k])}</span></dd>
            </div>
          ))}
        </dl>
        {p.win_rate_with_op.n > 0 && (
          <p className="aside">
            They win <b>{pct(p.win_rate_with_op)}</b> of rounds with one, against{' '}
            <b>{pct(p.win_rate_full_buy_without_op)}</b> on full buys without.
          </p>
        )}
      </section>

      {main && (
        <section>
          <h3>Who carries it</h3>
          <p className="claim">
            <b>{main.name}</b> has it in <b>{pct(main.share)}</b> of their Operator rounds, mostly on {cap(main.top_agent)}.
          </p>
          <Evidence r={main.share} unit="Operator rounds" />
          <ul className="carriers">
            {p.carriers.slice(0, 5).map((c) => (
              <li key={c.player_id}>
                <button aria-pressed={activePlayer === c.player_id}
                        onClick={() => onPlayer(activePlayer === c.player_id ? null : c.player_id)}>
                  <span className="who">{c.name}</span>
                  <span className="agents">{c.agents.map(cap).join(', ')}</span>
                  <Bar r={c.share} />
                  <span className="num">{c.rounds}</span>
                </button>
              </li>
            ))}
          </ul>
          {p.possession_shift.n > 0 && (
            <p className="aside">
              In {p.possession_shift.k} of {p.possession_shift.n} Operator rounds someone other than the map's main carrier had it.
            </p>
          )}
        </section>
      )}

      {kills > 0 && (
        <section>
          <h3>When it fires</h3>
          <p className="claim">
            <b>{pct(p.kill_timing[topBucket].share)}</b> of their Operator kills come {topBucket === '60s+' ? 'after 60 seconds' : `in the ${BUCKET_LABEL[topBucket]} window`}: {timingRead}.
          </p>
          <Evidence r={p.kill_timing[topBucket].share} unit="Operator kills" />
          <div className="timing" role="group" aria-label="Filter the map by round time">
            {BUCKETS.map((b) => {
              const t = p.kill_timing[b]
              const on = buckets.has(b)
              return (
                <button key={b} aria-pressed={on} onClick={() => onBucket(b)} className="tbin">
                  <span className="tcol" style={{ height: `${(t.share.p ?? 0) * 100}%`, background: timeColor(BUCKET_MID[b]) }} />
                  <span className="tlabel">{BUCKET_LABEL[b]}</span>
                  <span className="num">{t.kills}</span>
                </button>
              )
            })}
          </div>
          <p className="hint">Time counts from the end of the buy phase. Click a column to show only those fights on the map.</p>
        </section>
      )}

      {delta != null && fwds.length >= 5 && (
        <section>
          <h3>How far forward</h3>
          <p className="claim">
            They take Operator fights{' '}
            <b>{Math.abs(delta) < 0.03 ? 'about as far forward as' : delta > 0 ? 'further forward than' : 'further back than'}</b>{' '}
            the average {sideWord ?? ''} Operator on this map.
          </p>
          <div className="fwd" aria-hidden>
            <span className="fwd-own">Own spawn</span>
            <span className="fwd-track">
              <span className="fwd-mark league" style={{ left: `${base! * 100}%` }} title="League median" />
              <span className="fwd-mark team" style={{ left: `${fwdMed! * 100}%` }} title="This team" />
            </span>
            <span className="fwd-enemy">Enemy spawn</span>
          </div>
          <span className="evidence">Median of {fwds.length} engagements. Hollow mark is the league median.</span>
        </section>
      )}
    </div>
  )
}
