import { Fragment, useEffect, useRef, useState } from 'react'
import type { Evidence, MetricDef, Query, RoundContext } from './api'
import { api, cap } from './api'

export type EvidenceRequest = {
  metric: MetricDef
  claim: string
  supportingLabel: string
  contraryLabel: string
  bucket?: string
}

type Props = { req: EvidenceRequest; q: Query; onClose: () => void }

export function EvidenceDrawer({ req, q, onClose }: Props) {
  const [which, setWhich] = useState<'supporting' | 'contrary'>('supporting')
  const [page, setPage] = useState(0)
  const [ev, setEv] = useState<Evidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const ref = useRef<HTMLElement>(null)

  useEffect(() => { ref.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  useEffect(() => {
    setEv(null); setError(null)
    api.evidence({ ...q, metric: req.metric.id, which, bucket: req.bucket, page })
      .then((r) => setEv(r.data)).catch((e) => setError(e.message))
  }, [q, req, which, page])

  const pages = ev ? Math.ceil(ev.total / 25) : 0

  return (
    <aside className="drawer" role="dialog" aria-modal="false" aria-label={`Rounds behind: ${req.metric.title}`}
           tabIndex={-1} ref={ref}>
      <header className="drawer-head">
        <div>
          <h2>{req.metric.title}</h2>
          <p className="drawer-claim">{req.claim}</p>
        </div>
        <button className="close" onClick={onClose} aria-label="Close">×</button>
      </header>

      <div className="seg" role="tablist" aria-label="Which rounds">
        <button role="tab" aria-selected={which === 'supporting'} onClick={() => { setWhich('supporting'); setPage(0) }}>
          {req.supportingLabel}
        </button>
        <button role="tab" aria-selected={which === 'contrary'} onClick={() => { setWhich('contrary'); setPage(0) }}>
          {req.contraryLabel}
        </button>
      </div>

      {error && <p className="error">Couldn’t load rounds: {error}</p>}
      {!ev && !error && <p className="hint">Loading rounds…</p>}
      {ev && ev.total === 0 && <p className="hint">No rounds in this group.</p>}
      {ev && ev.total > 0 && (
        <>
          <p className="hint">{ev.total} rounds, newest first.</p>
          <ol className="rounds">
            {ev.rounds.map((r) => (
              <li key={r.round_key}>
                <button className="round-row" aria-expanded={open === r.round_key}
                        onClick={() => setOpen(open === r.round_key ? null : r.round_key)}>
                  <span className={r.won ? 'res won' : r.won === false ? 'res lost' : 'res'}>
                    {r.won ? 'Won' : r.won === false ? 'Lost' : '?'}
                  </span>
                  <span className="rr-main">
                    Round {r.round_no} vs {r.opponent}
                    <span className="rr-sub">{r.date}, {r.event}</span>
                  </span>
                  <span className="rr-op">{r.op_players?.length ? r.op_players.join(', ') : 'No Operator'}</span>
                </button>
                {open === r.round_key && <RoundView roundKey={r.round_key} />}
              </li>
            ))}
          </ol>
          {pages > 1 && (
            <nav className="pager" aria-label="Pages">
              <button disabled={page === 0} onClick={() => setPage(page - 1)}>Newer</button>
              <span>Page {page + 1} of {pages}</span>
              <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Older</button>
            </nav>
          )}
        </>
      )}

      <details className="method">
        <summary>How this is measured</summary>
        <dl>
          <dt>Question</dt><dd>{req.metric.question}</dd>
          <dt>Rounds counted</dt><dd>{req.metric.population}</dd>
          <dt>Counted as yes</dt><dd>{req.metric.numerator}</dd>
          {req.metric.caveats.map((c, i) => (<Fragment key={i}><dt>Limit</dt><dd>{c}</dd></Fragment>))}
        </dl>
        <p className="hint">Definition {req.metric.id} v{req.metric.version}</p>
      </details>
    </aside>
  )
}

function RoundView({ roundKey }: { roundKey: string }) {
  const [rc, setRc] = useState<RoundContext | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.round(roundKey).then((r) => setRc(r.data)).catch((e) => setError(e.message)) }, [roundKey])
  if (error) return <p className="error">Couldn’t load this round: {error}</p>
  if (!rc) return <p className="hint">Loading round…</p>
  const r = rc.round
  const ops = rc.players.filter((p) => /operator|outlaw/.test(p.items))
  const timeline = [
    ...rc.kills.map((k) => ({ t: k.t_round, text: `${k.attacker} killed ${k.victim}${k.weapon ? ` (${k.weapon})` : ''}`, opening: k.opening, side: k.attacker_side })),
    ...rc.objectives.map((o) => ({ t: o.t_round, text: o.kind === 'plant' ? 'Spike planted' : o.kind === 'defuse' ? 'Spike defused' : 'Spike detonated', opening: false, side: 'obj' })),
  ].sort((a, b) => (a.t ?? 0) - (b.t ?? 0))
  return (
    <div className="round-view">
      <p className="rv-sum">
        {cap(r.winner_side)} side won{r.duration_s != null && <> after {Math.round(r.duration_s)}s</>}
        {r.win_type === 'defuse' ? ' by defusing' : r.win_type === 'detonation' ? ' by detonation' : ''}. Patch {r.patch}.
        {ops.length > 0 && <> Operator: {ops.map((p) => `${p.name} (${cap(p.agent)})`).join(', ')}.</>}
      </p>
      <ol className="timeline">
        {timeline.map((e, i) => (
          <li key={i} className={`tl-${e.side}`}>
            <span className="num">{e.t != null ? `${e.t.toFixed(1)}s` : '–'}</span>
            <span>{e.text}{e.opening ? ', first kill' : ''}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
