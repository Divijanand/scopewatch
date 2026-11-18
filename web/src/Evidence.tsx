import { Fragment, useEffect, useRef, useState } from 'react'
import type { Evidence, MetricDef, Query, RoundContext, VodRound } from './api'
import { api, cap, clock, parseClock, vodLink } from './api'

const LEAD_S = 5   // open the VOD a few seconds before the moment

export type EvidenceRequest = {
  metric: MetricDef
  claim: string
  supportingLabel: string
  contraryLabel: string
  bucket?: string
  group?: string
  agent?: string
}

type Props = { req: EvidenceRequest; q: Query; onClose: () => void }

export function EvidenceDrawer({ req, q, onClose }: Props) {
  const [which, setWhich] = useState<'supporting' | 'contrary'>('supporting')
  const [page, setPage] = useState(0)
  const [ev, setEv] = useState<Evidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [vodVersion, setVodVersion] = useState(0)
  const ref = useRef<HTMLElement>(null)

  useEffect(() => { ref.current?.focus() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  useEffect(() => {
    setEv(null); setError(null)
    api.evidence({ ...q, metric: req.metric.id, which, bucket: req.bucket, group: req.group, agent: req.agent, page })
      .then((r) => setEv(r.data)).catch((e) => setError(e.message))
  }, [q, req, which, page, vodVersion])

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
                <WatchLink vod={r.vod} at={0} label="Watch" />
                {open === r.round_key && (
                  <RoundView roundKey={r.round_key} version={vodVersion} onVodChange={() => setVodVersion((v) => v + 1)} />
                )}
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

/** Opens the VOD `at` seconds after this round's buy-phase end (minus a short lead). */
function WatchLink({ vod, at, label }: { vod: VodRound | null | undefined; at: number; label?: string }) {
  if (!vod || vod.buy_end_s == null) return null
  const s = Math.max(0, vod.buy_end_s + at - LEAD_S)
  const { href, exact } = vodLink(vod.url, s)
  return (
    <a className="watch" href={href} target="_blank" rel="noopener noreferrer"
       title={exact ? `Open the VOD at ${clock(s)}` : `This host can’t open at a time: skip to ${clock(s)}`}>
      ▶ {label ? `${label} ` : ''}{clock(s)}
    </a>
  )
}

function VodPanel({ rc, onSaved }: { rc: RoundContext; onSaved: () => void }) {
  const [editing, setEditing] = useState(!rc.vod)
  const [url, setUrl] = useState(rc.vod?.url ?? '')
  const [at, setAt] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const r = rc.round

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    const s = parseClock(at)
    if (!url.trim()) { setErr('Paste the VOD link for this map.'); return }
    if (s == null) { setErr('Enter the VOD time as minutes:seconds, for example 31:42.'); return }
    setBusy(true); setErr(null)
    try {
      await api.saveVod(rc.game_id, { url: url.trim(), round_no: r.round_no, vod_s: s })
      setEditing(false); onSaved()
    } catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }

  if (!editing && rc.vod) {
    return (
      <div className="vod">
        <WatchLink vod={rc.vod} at={0} label="Watch from buy end" />
        <span className="hint">
          Timed from round {rc.vod.synced_at_round}.{' '}
          <button className="linkish" onClick={() => setEditing(true)}>Off by a few seconds? Re-time at this round</button>
        </span>
      </div>
    )
  }
  return (
    <form className="vod vod-form" onSubmit={save}>
      <p className="hint">
        {rc.vod ? 'Re-time the VOD at this round.' : 'Link a VOD for this map once and every round in it becomes a timestamp.'}
      </p>
      <label>VOD link (YouTube or Twitch)
        <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" />
      </label>
      <label>In the VOD, round {r.round_no}’s buy phase ends at
        <input value={at} onChange={(e) => setAt(e.target.value)} placeholder="31:42" inputMode="numeric" />
      </label>
      {err && <p className="error" role="alert">{err}</p>}
      <div className="vod-actions">
        <button type="submit" disabled={busy}>Save VOD timing</button>
        {rc.vod && <button type="button" className="linkish" onClick={() => setEditing(false)}>Cancel</button>}
      </div>
    </form>
  )
}

function RoundView({ roundKey, version, onVodChange }: { roundKey: string; version: number; onVodChange: () => void }) {
  const [rc, setRc] = useState<RoundContext | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.round(roundKey).then((r) => setRc(r.data)).catch((e) => setError(e.message)) }, [roundKey, version])
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
      <VodPanel key={`${rc.game_id}:${version}`} rc={rc} onSaved={onVodChange} />
      <ol className="timeline">
        {timeline.map((e, i) => (
          <li key={i} className={`tl-${e.side}`}>
            <span className="num">{e.t != null ? `${e.t.toFixed(1)}s` : '–'}</span>
            <span>{e.text}{e.opening ? ', first kill' : ''}</span>
            {e.t != null && <WatchLink vod={rc.vod} at={e.t} />}
          </li>
        ))}
      </ol>
    </div>
  )
}
