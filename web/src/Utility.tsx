import { useMemo, useState } from 'react'
import type { Cast, MapMeta, MetricDef, Rate, UtilityGroup, UtilityLayer } from './api'
import { cap, pct } from './api'
import type { EvidenceRequest } from './Evidence'

export const GROUP_LABEL: Record<UtilityGroup, string> = {
  setup: 'Setups', smoke: 'Smokes', flash: 'Flashes and stuns', recon: 'Recon',
}
// one colour per layer; the layer is always named, so colour never carries meaning alone
const GROUP_COLOR: Record<UtilityGroup, string> = {
  setup: '#1C9FE0', smoke: '#5B6B84', flash: '#E09A2B', recon: '#1F9E89',
}
const THROWN = new Set<UtilityGroup>(['smoke', 'flash', 'recon'])

export const abilityName = (a: string) => a.split('-').map(cap).join(' ')
const when = (t: number | null, buyShare: number) =>
  buyShare >= 0.5 ? 'in the buy phase' : t == null ? '' : t < 0 ? `${Math.round(-t)}s before the round starts` : `about ${Math.round(t)}s in`

export type UtilFocus = { ability: string; callout: string | null; rounds: Set<string> | null }

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
  const color = GROUP_COLOR[layer.group]
  const shown = useMemo(() => layer.casts.filter((c) =>
    !focus || (c.ability === focus.ability && (!focus.rounds || focus.rounds.has(c.round_key)))), [layer, focus])
  const ticks = shown.length <= 400

  return (
    <figure className="map">
      <svg viewBox={`0 0 ${meta.width} ${meta.height}`} role="img"
           aria-label={`${cap(mapName)}: ${shown.length} ${GROUP_LABEL[layer.group].toLowerCase()} by where they were cast from`}>
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
          {shown.map((c, i) => { const [x, y] = toPx(c.x, c.y); return <circle key={i} cx={x} cy={y} r={14} fill={color} opacity={0.22} /> })}
        </g>
        {shown.map((c, i) => {
          const [x, y] = toPx(c.x, c.y)
          const on = hover === c
          const d = c.vx != null && c.vy != null ? dir(c.vx, c.vy) : null
          return (
            <g key={i} className="cast" onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)}
               opacity={hover && !on ? 0.35 : 1}>
              {d && (ticks || on) && (
                <line x1={x} y1={y} x2={x + d[0] * (on ? 34 : 18)} y2={y + d[1] * (on ? 34 : 18)}
                      stroke="#22324A" strokeWidth={on ? 2 : 1.2} strokeLinecap="round" />
              )}
              <circle cx={x} cy={y} r={on ? 6 : 3.6} fill={color} stroke="#22324A" strokeWidth={1}
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
        {hover ? (
          <>
            <strong>{hover.player ?? 'Unknown player'}</strong>{hover.agent ? ` (${cap(hover.agent)})` : ''} used{' '}
            {abilityName(hover.ability)} {THROWN.has(layer.group) ? 'from' : 'at'} {hover.callout ?? 'an unnamed spot'},{' '}
            {hover.t_round == null ? '' : hover.t_round < 0 ? `${Math.abs(Math.round(hover.t_round))}s before the round started` : `${Math.round(hover.t_round)}s in`}.
            {hover.low_rate && ' Position from 1 Hz sampling, so less precise.'}
          </>
        ) : (
          <>
            Each dot is where a player stood when using the ability; the tick shows where they were aiming.
            {THROWN.has(layer.group) ? ' Thrown utility lands somewhere else, and the feed doesn’t record where.' : ' Setups are placed next to where the player stands.'}
            {' '}Dashed dots come from lower-rate position data.
          </>
        )}
      </figcaption>
    </figure>
  )
}

// ------------------------------------------------------------------ findings
type FindProps = {
  layer: UtilityLayer; side: string | null; def: MetricDef | undefined
  focus: UtilFocus | null; onFocus: (f: UtilFocus | null) => void; onEvidence: (r: EvidenceRequest) => void
}

export function UtilityFindings({ layer, side, def, focus, onFocus, onEvidence }: FindProps) {
  const res = layer.result
  const rows = res.breakdown as (Record<string, any> & { rate: Rate })[]
  const abilities = (res.value.abilities ?? []) as { ability: string; rate: Rate }[]
  const sideWord = side === 'attacker' ? 'attack' : 'defense'
  const thrown = THROWN.has(layer.group)
  const top = rows[0]

  if (res.warnings.length) return <div className="findings"><p className="hint">{res.warnings[0]}</p></div>
  if (!top) {
    return (
      <div className="findings">
        <section><h3>{GROUP_LABEL[layer.group]}</h3>
          <p className="claim">No {GROUP_LABEL[layer.group].toLowerCase()} with a reliable position on this map and side.</p></section>
      </div>
    )
  }
  const open = (b: Record<string, any>) => def && onEvidence({
    metric: def, bucket: b.bucket, group: layer.group,
    claim: `Rounds with ${abilityName(b.ability)} ${thrown ? 'used from' : 'at'} ${b.callout}.`,
    supportingLabel: `${b.callout} (${b.rate.k})`, contraryLabel: 'Other rounds',
  })

  return (
    <div className="findings">
      <section>
        <h3>{GROUP_LABEL[layer.group]} on {sideWord}</h3>
        <p className="claim">
          {top.players[0]?.name ?? 'They'}’s <b>{abilityName(top.ability)}</b> {thrown ? 'is used from' : 'goes down at'}{' '}
          <b>{top.callout}</b> in <b>{top.rate.k} of {top.rate.n}</b> {sideWord} rounds, {when(top.median_t, top.buy_phase / top.casts)}.
        </p>
        <span className={top.rate.small_sample ? 'evidence thin' : 'evidence'}>
          {top.rate.k} of {top.rate.n} rounds ({pct(top.rate)})
        </span>
        <ul className="spots">
          {rows.slice(0, 8).map((b) => {
            const on = focus?.ability === b.ability && focus.callout === b.callout
            return (
              <li key={b.bucket}>
                <button aria-pressed={on}
                        onClick={() => onFocus(on ? null : { ability: b.ability, callout: b.callout, rounds: new Set(b.round_keys as string[]) })}>
                  <span className="where">{abilityName(b.ability)}</span>
                  <span className="detail">
                    {thrown ? 'from' : 'at'} {b.callout}, {(b.players as { name: string }[]).map((p) => p.name).join(', ') || cap(b.agent)}
                    {b.median_t != null && `, ${b.median_t < 0 ? `${Math.round(-b.median_t)}s before start` : `~${Math.round(b.median_t)}s`}`}
                  </span>
                  <span className="bar" aria-hidden><span className="bar-fill" style={{ width: `${(b.rate.p ?? 0) * 100}%` }} /></span>
                  <span className="num">{b.rate.k}</span>
                </button>
              </li>
            )
          })}
        </ul>
        <p className="hint">Click a row to show only those casts on the map; click again to show all.</p>
        {focus && (() => {
          const b = rows.find((r) => r.ability === focus.ability && r.callout === focus.callout)
          return b ? <button className="show-rounds" onClick={() => open(b)}>Show the rounds</button> : null
        })()}
      </section>

      <section>
        <h3>By ability</h3>
        <div className="chips" role="group" aria-label="Show one ability on the map">
          {abilities.map((a) => {
            const on = focus?.ability === a.ability && focus.callout == null
            return (
              <button key={a.ability} aria-pressed={on}
                      onClick={() => onFocus(on ? null : { ability: a.ability, callout: null, rounds: null })}>
                {abilityName(a.ability)} <span className="num">{a.rate.k}/{a.rate.n}</span>
              </button>
            )
          })}
        </div>
        <p className="hint">Rounds with at least one use, out of all their {sideWord} rounds on this map.</p>
        {res.unknown.map((u) => <p key={u.reason} className="hint">{u.count} casts left off the map: {u.reason}.</p>)}
      </section>
    </div>
  )
}
