import type { Finding, MetricDef } from './api'
import type { EvidenceRequest } from './Evidence'

function pos(unit: Finding['unit'], x: number, lo: number, hi: number, league: number) {
  if (unit === 'rate') return Math.max(0, Math.min(1, x)) * 100
  const lim = Math.max(Math.abs(lo), Math.abs(hi), Math.abs(league)) * 1.2 || 1
  return ((x + lim) / (2 * lim)) * 100
}

export function Summary({ findings, note, metricDefs, onEvidence }: {
  findings: Finding[]
  note: string | null
  metricDefs: Record<string, MetricDef>
  onEvidence: (req: EvidenceRequest) => void
}) {
  if (!findings.length) return <p className="summary-note">{note ?? 'No clear tendencies stood out in this filter yet.'}</p>
  return (
    <section className="summary">
      <h2>Prepare for these</h2>
      <ul>
        {findings.map((f) => {
          const metric = metricDefs[f.evidence.metric]
          return (
          <li key={f.id}>
            <p className="summary-title">{f.title}</p>
            <p className="summary-headline">{f.headline}</p>
            <p className="summary-prepare"><b>{f.prepare}</b></p>
            <span className="bar" aria-hidden>
              <span className="bar-range" style={{ left: `${pos(f.unit, f.lo, f.lo, f.hi, f.league)}%`, width: `${Math.max(0, pos(f.unit, f.hi, f.lo, f.hi, f.league) - pos(f.unit, f.lo, f.lo, f.hi, f.league))}%` }} />
              <span className="bar-league" style={{ left: `${pos(f.unit, f.league, f.lo, f.hi, f.league)}%` }} />
            </span>
            {metric && <button className="show-rounds" onClick={() => onEvidence({ metric, claim: f.headline, supportingLabel: 'Supporting', contraryLabel: 'Contrary' })}>Show the rounds</button>}
          </li>
        )})}
      </ul>
    </section>
  )
}