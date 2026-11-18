import { useMemo, useState } from 'react'
import type { Engagement, MapMeta } from './api'
import { cap } from './api'

// Round-time colour: Cloud9 sky blue for early fights, amber for late ones.
const EARLY = [28, 159, 224]
const LATE = [224, 154, 43]
const T_MAX = 90

export function timeColor(t: number) {
  const k = Math.max(0, Math.min(1, t / T_MAX))
  const c = EARLY.map((e, i) => Math.round(e + (LATE[i] - e) * k))
  return `rgb(${c.join(',')})`
}

type Props = {
  mapName: string
  meta: MapMeta
  engagements: Engagement[]
  spawns: Record<string, { x: number; y: number }> | null
  showDamage: boolean
}

export function MapView({ mapName, meta, engagements, spawns, showDamage }: Props) {
  const [hover, setHover] = useState<Engagement | null>(null)

  // versioned world->pixel transform from config/maps (native coordinates are never modified)
  const toPx = useMemo(() => {
    const t = meta.transform
    return (x: number, y: number) => [t.a * x + t.b * y + t.c, t.d * x + t.e * y + t.f] as const
  }, [meta])
  const calibrated = meta.calibration_status === 'validated'

  const shown = engagements.filter((e) => e.x != null && (showDamage || e.kind === 'kill'))
  // kills on top of damage, later fights on top of earlier ones
  const ordered = [...shown].sort((a, b) => (a.kind === b.kind ? a.t_round - b.t_round : a.kind === 'kill' ? 1 : -1))

  return (
    <figure className="map">
      {!calibrated && (
        <p className="warn map-warn" role="status">
          {meta.calibration_status === 'needs_review'
            ? 'This map outline failed its landmark check: too few games to draw it fully. Lines may sit off the drawn floor.'
            : 'This map outline hasn’t been checked against landmarks yet. Treat positions as approximate.'}
        </p>
      )}
      <svg viewBox={`0 0 ${meta.width} ${meta.height}`} role="img"
           aria-label={`${cap(mapName)} with ${shown.length} Operator engagements`}>
        <image href={`/api/maps/${mapName}.png`} width={meta.width} height={meta.height}
               style={{ imageRendering: 'pixelated' }} />
        {spawns && Object.entries(spawns).map(([side, s]) => {
          const [x, y] = toPx(s.x, s.y)
          return (
            <g key={side} className="spawn">
              <circle cx={x} cy={y} r={14} />
              <text x={x} y={y + 5} textAnchor="middle">{side === 'attacker' ? 'Atk' : 'Def'}</text>
            </g>
          )
        })}
        {ordered.map((e, i) => {
          const [x1, y1] = toPx(e.x, e.y)
          const [x2, y2] = toPx(e.vx, e.vy)
          const col = timeColor(e.t_round)
          const isKill = e.kind === 'kill'
          const dim = hover && hover !== e
          return (
            <g key={i} className={isKill ? 'eng kill' : 'eng dmg'} opacity={dim ? 0.18 : 1}
               onMouseEnter={() => setHover(e)} onMouseLeave={() => setHover(null)}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={col}
                    strokeWidth={isKill ? 2.4 : 1.2} strokeDasharray={isKill ? undefined : '4 4'} />
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="transparent" strokeWidth={12} />
              <circle cx={x1} cy={y1} r={isKill ? 5.5 : 4} fill={col} stroke="#22324A" strokeWidth={1.4} />
              {isKill && (
                <path d={`M${x2 - 4},${y2 - 4}L${x2 + 4},${y2 + 4}M${x2 + 4},${y2 - 4}L${x2 - 4},${y2 + 4}`}
                      stroke="#22324A" strokeWidth={2} />
              )}
            </g>
          )
        })}
      </svg>
      <figcaption className="map-tip" aria-live="polite">
        {hover ? (
          <>
            <strong>{hover.att_name}</strong>{hover.agent ? ` on ${cap(hover.agent)}` : ''}{' '}
            {hover.kind === 'kill' ? 'killed' : 'hit'} {hover.vic_name} with the {hover.weapon},{' '}
            {Math.round(hover.t_round)}s after the buy phase. Round {hover.round_no},{' '}
            {hover.won ? 'won' : hover.won === false ? 'lost' : 'result unknown'}.
          </>
        ) : (
          <>Each line runs from the Operator player to who they shot. Hover one for the round.</>
        )}
      </figcaption>
    </figure>
  )
}
