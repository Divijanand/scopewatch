import { useMemo, useState } from 'react'
import type { AbilityMode, Cast, MapMeta, MetricDef, MetricResult, Rate, UtilityGroup, UtilityLayer } from './api'
import { cap, pct } from './api'
import type { EvidenceRequest } from './Evidence'

export const GROUP_LABEL: Record<UtilityGroup, string> = {
  setup: 'Setups', damage: 'Mollies and damage', smoke: 'Walls and smokes', flash: 'Flashes and stuns', recon: 'Recon',
  ultimate: 'Ultimates',
}
// one colour per layer; on an agent, one colour per ability. Colour never carries meaning alone: every dot is named
const GROUP_COLOR: Record<UtilityGroup, string> = {
  setup: '#1C9FE0', damage: '#C8553D', smoke: '#5B6B84', flash: '#E09A2B', recon: '#1F9E89', ultimate: '#7A5BC7',
}
const KIT_COLORS = ['#1C9FE0', '#E09A2B', '#C8553D', '#1F9E89', '#7A5BC7']

// what a position means for each kind of ability, in the words the UI uses
const VERB: Record<AbilityMode, string> = {
  placed: 'goes down at', landing: 'lands at', direction: 'runs from', thrown: 'is used from', self: 'is used at', unplaced: '',
}
const MODE_NOTE: Record<AbilityMode, string> = {
  placed: 'placed where the player stood',
  landing: 'where it hurt an enemy, linked to the throw',
  direction: 'a line from the player along their aim; length not measured',
  thrown: 'where it was used from; it lands elsewhere and the data doesn’t record where',
  self: 'where the player was when using it',
  unplaced: 'placed from the map or far away: timing only, no position',
}
const WALL_PX = 120

export const abilityName = (a: string) => a.split('-').map(cap).join(' ')
const whenText = (t: number | null) =>
  t == null ? '' : t < 0 ? `${Math.round(-t)}s before the round starts` : `about ${Math.round(t)}s in`

export type UtilFocus = { ability: string; callout: string | null; rounds: Set<string> | null }

function colorFor(layer: UtilityLayer) {
  if (!layer.agent) return () => GROUP_COLOR[layer.group ?? 'setup']
  const kit = ((layer.result.value.kit ?? []) as { ability: string }[]).map((k) => k.ability)
  return (ability: string) => KIT_COLORS[Math.max(0, kit.indexOf(ability)) % KIT_COLORS.length]
}

// ------------------------------------------------------------------ map layer
type MapProps = { mapName: string; meta: MapMeta; layer: UtilityLayer; focus: UtilFocus | null }

export function UtilityMap({ mapName, meta, layer, focus }: MapProps) {
  const [hover, setHover] = useState<Cast | null>(null)
  const t = meta.transform
  const toPx = (x: number, y: number) => [t.a * x + t.b * y + t.c, t.d * x + t.e * y + t.f] as const
  const dir = (vx: number, vy: number) => {
    const dx = t.a * vx + t.b * vy, dy = t.d * vx + t.e * vy
    const n = Math.hypot(dx, dy) || 1
    return [dx / n, dy / n] as const
  }
  const color = colorFor(layer)
  const shown = useMemo(() => layer.casts.filter((c) =>
    !focus || (c.ability === focus.ability && (!focus.rounds || focus.rounds.has(c.round_key)))), [layer, focus])
  const ticks = shown.length <= 400
  const what = layer.agent ? `${cap(layer.agent)}’s abilities` : GROUP_LABEL[layer.group ?? 'setup'].toLowerCase()

  return (
    <figure className="map">
      <svg viewBox={`0 0 ${meta.width} ${meta.height}`} role="img" aria-label={`${cap(mapName)}: ${shown.length} uses of ${what}`}>
        <defs>
          <filter id="heat" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="9" /></filter>
        </defs>
        <image href={`/api/maps/${mapName}.png?v=${encodeURIComponent(meta.transform_version)}`} width={meta.width} height={meta.height} />
        <g className="callouts" aria-hidden>
          {(meta.callouts ?? []).filter((c) => !c.name.endsWith('Spawn')).map((c) => {
            const [x, y] = toPx(c.x, c.y)
            return <text key={c.name} x={x} y={y} textAnchor="middle" className={focus?.callout === c.name ? 'callout on' : 'callout'}>{c.name}</text>
          })}
        </g>
        <g filter="url(#heat)" aria-hidden>
          {shown.filter((c) => c.kind !== 'wall').map((c, i) => {
            const [x, y] = toPx(c.x, c.y)
            return <circle key={i} cx={x} cy={y} r={14} fill={color(c.ability)} opacity={0.2} />
          })}
        </g>
        {shown.map((c, i) => {
          const [x, y] = toPx(c.x, c.y)
          const on = hover === c
          const col = color(c.ability)
          const d = c.vx != null && c.vy != null ? dir(c.vx, c.vy) : null
          const from = c.fx != null && c.fy != null ? toPx(c.fx, c.fy) : null
          return (
            <g key={i} className="cast" onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)}
               opacity={hover && !on ? 0.3 : 1}>
              {c.kind === 'wall' && d && (
                <line x1={x} y1={y} x2={x + d[0] * WALL_PX} y2={y + d[1] * WALL_PX} stroke={col}
                      strokeWidth={on ? 6 : 4} strokeLinecap="round" opacity={0.75} />
              )}
              {c.kind === 'landing' && from && on && (
                <>
                  <line x1={from[0]} y1={from[1]} x2={x} y2={y} stroke="#22324A" strokeWidth={1.5} strokeDasharray="5 4" />
                  <circle cx={from[0]} cy={from[1]} r={4} fill="#fff" stroke="#22324A" strokeWidth={1.5} />
                </>
              )}
              {c.kind === 'cast' && d && (ticks || on) && (
                <line x1={x} y1={y} x2={x + d[0] * (on ? 34 : 18)} y2={y + d[1] * (on ? 34 : 18)}
                      stroke="#22324A" strokeWidth={on ? 2 : 1.2} strokeLinecap="round" />
              )}
              <circle cx={x} cy={y} r={on ? 6 : 3.6} fill={col} stroke="#22324A" strokeWidth={1}
                      strokeDasharray={c.low_rate ? '2 2' : undefined} />
              <circle cx={x} cy={y} r={10} fill="transparent" />
            </g>
          )
        })}
        {Object.entries(layer.spawns).map(([side, s]) => {
          const [x, y] = toPx(s.x, s.y)
          return (
            <g key={side} className="spawn"><circle cx={x} cy={y} r={14} />
              <text x={x} y={y + 5} textAnchor="middle">{side === 'attacker' ? 'Atk' : 'Def'}</text></g>
          )
        })}
      </svg>
      <figcaption className="map-tip" aria-live="polite">
        {hover ? <HoverText c={hover} /> : (
          <>Each ability is drawn by what its position means: setups where they’re placed, mollies where they hurt someone,
            walls as lines along the aim, flashes and recon where they were used from. Hover any mark for details.
            Dashed dots come from lower-rate position data.</>
        )}
      </figcaption>
    </figure>
  )
}

function HoverText({ c }: { c: Cast }) {
  const who = <><strong>{c.player ?? 'Unknown player'}</strong>{c.agent ? ` (${cap(c.agent)})` : ''}</>
  const when = c.t_round == null ? '' : `, ${whenText(c.t_round)}`
  if (c.kind === 'landing') {
    return <>{who}: {abilityName(c.ability)} hit an enemy at {c.callout ?? 'an unnamed spot'}
      {c.from_callout ? `, thrown from ${c.from_callout}` : ''}{when}. The dashed line runs from the throw to the hit.</>
  }
  if (c.kind === 'wall') {
    return <>{who}: {abilityName(c.ability)} from {c.callout ?? 'an unnamed spot'}{c.toward ? `, aimed toward ${c.toward}` : ''}{when}.</>
  }
  const verb = c.mode === 'placed' ? 'placed' : 'used'
  return <>{who} {verb} {abilityName(c.ability)} at {c.callout ?? 'an unnamed spot'}{when}.
    {c.mode === 'thrown' && ' It lands somewhere else; the data doesn’t record where.'}
    {c.low_rate && ' Position from 1 Hz sampling, so less precise.'}</>
}

// ------------------------------------------------------------------ findings
type FindProps = {
  layer: UtilityLayer; side: string | null; def: MetricDef | undefined; ultDef?: MetricDef
  focus: UtilFocus | null; onFocus: (f: UtilFocus | null) => void; onEvidence: (r: EvidenceRequest) => void
}
type Row = Record<string, any> & { rate: Rate }

const sgn = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`

/** When each ult is used and what the 10 s after it are worth, against the league on this map and side. */
function UltFindings({ ults, sideWord, def, onEvidence }: {
  ults: MetricResult; sideWord: string; def: MetricDef | undefined; onEvidence: (r: EvidenceRequest) => void
}) {
  const rows = ults.breakdown as Row[]
  if (!rows.length) return <section><h3>Ultimates on {sideWord}</h3><p className="claim">No ultimates recorded on this map and side.</p></section>
  const scored = rows.filter((r) => r.swing != null && r.league_swing != null && r.uses >= 5)
  const best = [...scored].sort((a, b) => (b.swing - b.league_swing) - (a.swing - a.league_swing))[0]
  const worst = [...scored].sort((a, b) => (a.swing - a.league_swing) - (b.swing - b.league_swing))[0]
  const sure = (r: Row) => r.swing_lo != null && r.swing_hi != null && (r.league_swing < r.swing_lo || r.league_swing > r.swing_hi)
  return (
    <section>
      <h3>Ultimates on {sideWord}</h3>
      {worst && worst.swing < worst.league_swing && (
        <p className="claim">
          In the 10 s after their <b>{abilityName(worst.ability)}</b>, their round-win chance moves <b>{sgn(worst.swing)} points</b>,
          against {sgn(worst.league_swing)} for every team here{sure(worst) ? '.' : ', a hint for now.'}
        </p>
      )}
      {best && best !== worst && best.swing > best.league_swing && (
        <p className="aside">
          Their best: <b>{abilityName(best.ability)}</b>, {sgn(best.swing)} points against {sgn(best.league_swing)}
          {sure(best) ? '' : ' (a hint for now)'}.
        </p>
      )}
      <ul className="spots ult-list">
        {rows.map((r) => (
          <li key={r.ability}>
            <button onClick={() => def && onEvidence({
              metric: def, bucket: r.bucket,
              claim: `Rounds where they used ${abilityName(r.ability)}.`,
              supportingLabel: `Used (${r.rate.k})`, contraryLabel: `${cap(r.agent)} without it`,
            })}>
              <span className="where">{abilityName(r.ability)}</span>
              <span className="detail">
                {cap(r.agent)}, {r.rate.k} of {r.rate.n} rounds, {whenText(r.median_t)}{r.post_plant ? `, ${r.post_plant} after a plant` : ''}.
                {' '}Next 10 s: {r.kills} kills, {r.deaths} deaths
                {r.swing != null && <>, {sgn(r.swing)} pts{r.swing_lo != null && ` (${sgn(r.swing_lo)} to ${sgn(r.swing_hi)})`}
                  {r.league_swing != null && `; league ${sgn(r.league_swing)}`}</>}
                {r.seen_only_on_hit && '. Seen only when it hit someone'}
              </span>
              <span className="num">{r.rate.k}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="hint">
        Each ult opens a 10 s window: every kill and death in it, and the change in round-win chance from our model, is
        credited to the ult. Teams ult when they’re about to fight anyway, so compare with the league, not with zero.
        Ranges appear from 10 uses. Click an ult to open its rounds.
      </p>
    </section>
  )
}
type Timing = { ability: string; agent: string; rate: Rate; per_round: number; median_t: number | null }

function rowDetail(b: Row) {
  const who = (b.players as { name: string }[]).map((p) => p.name).join(', ') || cap(b.agent)
  const t = b.median_t == null ? '' : b.median_t < 0 ? `, ${Math.round(-b.median_t)}s before start` : `, ~${Math.round(b.median_t)}s`
  if (b.mode === 'landing') {
    const from = (b.from_callouts as { callout: string }[])[0]?.callout
    return `${who}${from ? `, thrown from ${from}` : ''}${t}`
  }
  if (b.mode === 'direction') {
    const to = (b.toward as { callout: string }[])[0]?.callout
    return `from ${b.callout}${to ? ` toward ${to}` : ''}, ${who}${t}`
  }
  return `${b.mode === 'placed' ? 'at' : b.mode === 'self' ? 'at' : 'from'} ${b.callout}, ${who}${t}`
}

function SpotList({ rows, focus, onFocus, max = 8 }: { rows: Row[]; focus: UtilFocus | null; onFocus: (f: UtilFocus | null) => void; max?: number }) {
  return (
    <ul className="spots">
      {rows.slice(0, max).map((b) => {
        const on = focus?.ability === b.ability && focus?.callout === b.callout
        return (
          <li key={b.bucket}>
            <button aria-pressed={on}
                    onClick={() => onFocus(on ? null : { ability: b.ability, callout: b.callout, rounds: new Set(b.round_keys as string[]) })}>
              <span className="where">{b.mode === 'landing' ? `→ ${b.callout}` : abilityName(b.ability)}</span>
              <span className="detail">{rowDetail(b)}</span>
              <span className="bar" aria-hidden><span className="bar-fill" style={{ width: `${(b.rate.p ?? 0) * 100}%` }} /></span>
              <span className="num">{b.rate.k}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function TimingTable({ timing }: { timing: Timing[] }) {
  return (
    <table className="timing-table">
      <thead><tr><th scope="col">Ability</th><th scope="col">Rounds used</th><th scope="col">Per round</th><th scope="col">Typical time</th></tr></thead>
      <tbody>
        {timing.map((s) => (
          <tr key={s.ability}>
            <th scope="row">{abilityName(s.ability)} <span className="agent">{cap(s.agent)}</span></th>
            <td>{s.rate.k} of {s.rate.n}</td><td>{s.per_round}</td><td>{whenText(s.median_t)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function UtilityFindings({ layer, side, def, ultDef, focus, onFocus, onEvidence }: FindProps) {
  const res = layer.result
  const rows = res.breakdown as Row[]
  const abilities = (res.value.abilities ?? []) as { ability: string; mode: AbilityMode; rate: Rate }[]
  const timing = (res.value.timing ?? []) as Timing[]
  const sideWord = side === 'attacker' ? 'attack' : 'defense'
  const g = layer.group ?? 'setup'

  if (res.warnings.length) return <div className="findings"><p className="hint">{res.warnings[0]}</p></div>

  const open = (b: Row) => def && onEvidence({
    metric: def, bucket: b.bucket, group: layer.agent ? undefined : g, agent: layer.agent ?? undefined,
    claim: `Rounds where ${abilityName(b.ability)} ${VERB[b.mode as AbilityMode] || 'is used at'} ${b.callout}.`,
    supportingLabel: `${b.callout} (${b.rate.k})`, contraryLabel: 'Other rounds',
  })
  const focusRow = focus && rows.find((r) => r.ability === focus.ability && r.callout === focus.callout)
  const showRounds = focusRow ? <button className="show-rounds" onClick={() => open(focusRow)}>Show the rounds</button> : null

  // ---------------- one agent's whole kit
  if (layer.agent) {
    const kit = (res.value.kit ?? []) as { ability: string; mode: AbilityMode }[]
    const color = colorFor(layer)
    return (
      <div className="findings">
        <section>
          <h3>{cap(layer.agent)} on {sideWord}</h3>
          <p className="aside">
            Across {res.value.rounds} {sideWord} rounds where they played {cap(layer.agent)}. Each ability is shown by what
            its position means.
          </p>
          {showRounds}
        </section>
        {kit.map((k) => {
          const its = rows.filter((r) => r.ability === k.ability)
          const tm = timing.find((x) => x.ability === k.ability)
          const used = abilities.find((a) => a.ability === k.ability)
          return (
            <section key={k.ability}>
              <h3><span className="kit-dot" style={{ background: color(k.ability) }} aria-hidden /> {abilityName(k.ability)}</h3>
              <p className="hint">{MODE_NOTE[k.mode]}{used && <>. Used in {used.rate.k} of {used.rate.n} rounds ({pct(used.rate)}){k.mode === 'landing' && ', counting only uses that hit an enemy'}.</>}</p>
              {its.length > 0 && <SpotList rows={its} focus={focus} onFocus={onFocus} max={4} />}
              {tm && <TimingTable timing={[tm]} />}
              {!its.length && !tm && <p className="hint">Not used on this map and side, or never with a reliable position.</p>}
            </section>
          )
        })}
      </div>
    )
  }

  // ---------------- one layer across agents
  const top = rows[0]
  const topWhen = top ? (top.casts && top.buy_phase / top.casts >= 0.5 ? 'in the buy phase' : whenText(top.median_t)) : ''
  return (
    <div className="findings">
      {layer.ults && <UltFindings ults={layer.ults} sideWord={sideWord} def={ultDef} onEvidence={onEvidence} />}
      <section>
        <h3>{g === 'ultimate' ? 'Where they use them' : `${GROUP_LABEL[g]} on ${sideWord}`}</h3>
        {top ? (
          <>
            <p className="claim">
              {top.players[0]?.name ?? 'They'}’s <b>{abilityName(top.ability)}</b> {VERB[top.mode as AbilityMode] || 'is used at'} <b>{top.callout}</b>
              {top.mode === 'direction' && top.toward?.[0] && <> toward <b>{top.toward[0].callout}</b></>}
              {top.mode === 'landing' && top.from_callouts?.[0] && <>, thrown from {top.from_callouts[0].callout}</>}
              {' '}in <b>{top.rate.k} of {top.rate.n}</b> {sideWord} rounds{topWhen && `, ${topWhen}`}.
            </p>
            <span className={top.rate.small_sample ? 'evidence thin' : 'evidence'}>
              {top.rate.k} of {top.rate.n} rounds ({pct(top.rate)}{top.rate.lo != null && top.rate.hi != null && `, likely ${Math.round(top.rate.lo * 100)}–${Math.round(top.rate.hi * 100)}%`}){top.mode === 'landing' && ', counting only uses that hit an enemy'}
            </span>
            <SpotList rows={rows} focus={focus} onFocus={onFocus} />
            <p className="hint">Click a row to show only those on the map; click again to show all.</p>
            {showRounds}
          </>
        ) : timing.length === 0 && (
          <p className="claim">Nothing in this layer with a reliable position on this map and side.</p>
        )}
      </section>
      {timing.length > 0 && (
        <section>
          <h3>Smokes the data can’t place</h3>
          <p className="aside">Placed from the map or thrown to a spot the data never records, so here’s how often and when, not where.</p>
          <TimingTable timing={timing} />
        </section>
      )}
      {abilities.length > 0 && (
        <section>
          <h3>By ability</h3>
          <div className="chips" role="group" aria-label="Show one ability on the map">
            {abilities.map((a) => {
              const on = focus?.ability === a.ability && focus.callout == null
              return (
                <button key={a.ability} aria-pressed={on} onClick={() => onFocus(on ? null : { ability: a.ability, callout: null, rounds: null })}>
                  {abilityName(a.ability)} <span className="num">{a.rate.k}/{a.rate.n}</span>
                </button>
              )
            })}
          </div>
          <p className="hint">Rounds with at least one use, out of all their {sideWord} rounds on this map.</p>
          {res.unknown.map((u) => <p key={u.reason} className="hint">{u.count} left off the map: {u.reason}.</p>)}
        </section>
      )}
    </div>
  )
}
