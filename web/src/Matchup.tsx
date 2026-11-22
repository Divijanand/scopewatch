import { cap } from './api'
import type { Matchup as MatchupData, MatchupPair, MatchupValue } from './api'

function pos(unit: MatchupPair['unit'], x: number, lo: number, hi: number, league: number) {
  if (unit === 'rate') return Math.max(0, Math.min(1, x)) * 100
  const lim = Math.max(Math.abs(lo), Math.abs(hi), Math.abs(league)) * 1.2 || 1
  return ((x + lim) / (2 * lim)) * 100
}

function barRange(unit: MatchupPair['unit'], v: MatchupValue | null) {
  if (!v || v.lo == null || v.hi == null || v.league == null) return null
  const left = pos(unit, v.lo, v.lo, v.hi, v.league)
  const right = pos(unit, v.hi, v.lo, v.hi, v.league)
  const league = pos(unit, v.league, v.lo, v.hi, v.league)
  return { left, width: Math.max(0, right - left), league }
}

function edgeLabel(pair: MatchupPair, attackerId: string, defenderId: string, attackerName: string, defenderName: string) {
  if (pair.read === 'even') return { text: 'Even', edge: false }
  if (pair.read === 'too_few') return { text: 'Too few rounds', edge: false }
  if (pair.edge === attackerId) return { text: `Edge to ${attackerName}`, edge: true }
  if (pair.edge === defenderId) return { text: `Edge to ${defenderName}`, edge: true }
  if (pair.read === 'attacker') return { text: `Edge to ${attackerName}`, edge: true }
  return { text: `Edge to ${defenderName}`, edge: true }
}

function PairRow({
  pair, attackerId, defenderId, attackerName, defenderName,
}: {
  pair: MatchupPair
  attackerId: string
  defenderId: string
  attackerName: string
  defenderName: string
}) {
  const att = barRange(pair.unit, pair.att)
  const dfn = barRange(pair.unit, pair.dfn)
  const tag = edgeLabel(pair, attackerId, defenderId, attackerName, defenderName)
  return (
    <li className="mu-row">
      <p className="mu-title">{pair.title}</p>
      <p className="mu-sentence">{pair.sentence}</p>
      <div className="mu-bars">
        <div className="mu-bar-row">
          <span className="mu-bar-label">{attackerName}</span>
          <span className="bar mu-bar" aria-hidden>
            {att && <span className="bar-range" style={{ left: `${att.left}%`, width: `${att.width}%` }} />}
            {att && <span className="bar-league" style={{ left: `${att.league}%` }} />}
          </span>
        </div>
        <div className="mu-bar-row">
          <span className="mu-bar-label">{defenderName}</span>
          <span className="bar mu-bar" aria-hidden>
            {dfn && <span className="bar-range" style={{ left: `${dfn.left}%`, width: `${dfn.width}%` }} />}
            {dfn && <span className="bar-league" style={{ left: `${dfn.league}%` }} />}
          </span>
        </div>
      </div>
      <span className={tag.edge ? 'mu-tag mu-tag-edge' : 'mu-tag'}>{tag.text}</span>
    </li>
  )
}

function PairGroup({
  title, pairs, attackerId, defenderId, attackerName, defenderName,
}: {
  title: string
  pairs: MatchupPair[]
  attackerId: string
  defenderId: string
  attackerName: string
  defenderName: string
}) {
  const rows = pairs.filter((p) => p.read !== 'too_few')
  const tooFew = pairs.filter((p) => p.read === 'too_few').map((p) => p.title)
  return (
    <section className="mu-group">
      <h3>{title}</h3>
      {rows.length > 0 && (
        <ul>
          {rows.map((pair) => (
            <PairRow key={pair.id} pair={pair} attackerId={attackerId} defenderId={defenderId} attackerName={attackerName} defenderName={defenderName} />
          ))}
        </ul>
      )}
      {tooFew.length > 0 && <p className="mu-too-few">Too few rounds to compare: {tooFew.join(', ')}.</p>}
    </section>
  )
}

export function Matchup({ matchup, map }: { matchup: MatchupData; map: string }) {
  const a = matchup.team_a
  const b = matchup.team_b
  return (
    <section className="mu">
      <div className="mu-top">
        <section>
          <h2>What stands out about {a.name}</h2>
          {matchup.top.a.length === 0 ? <p className="mu-note">Nothing beyond noise on this map.</p> : (
            <ul>
              {matchup.top.a.map((f) => (
                <li key={`${f.side}:${f.id}`}>
                  <p className="mu-small">{f.title} on {f.side === 'attacker' ? 'attack' : 'defence'}</p>
                  <p className="mu-headline">{f.headline}</p>
                  <p className="mu-prepare"><b>{f.prepare}</b></p>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h2>What stands out about {b.name}</h2>
          {matchup.top.b.length === 0 ? <p className="mu-note">Nothing beyond noise on this map.</p> : (
            <ul>
              {matchup.top.b.map((f) => (
                <li key={`${f.side}:${f.id}`}>
                  <p className="mu-small">{f.title} on {f.side === 'attacker' ? 'attack' : 'defence'}</p>
                  <p className="mu-headline">{f.headline}</p>
                  <p className="mu-prepare"><b>{f.prepare}</b></p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <PairGroup
        title={`${a.name} attacking, ${b.name} defending`}
        pairs={matchup.pairs.slice(0, 5)}
        attackerId={a.id}
        defenderId={b.id}
        attackerName={a.name}
        defenderName={b.name}
      />
      <PairGroup
        title={`${b.name} attacking, ${a.name} defending`}
        pairs={matchup.pairs.slice(5, 10)}
        attackerId={b.id}
        defenderId={a.id}
        attackerName={b.name}
        defenderName={a.name}
      />

      <section className="mu-h2h">
        <h3>Head to head</h3>
        {matchup.head_to_head.length === 0 ? <p className="mu-note">{matchup.note ?? 'No head-to-head series in this filter.'}</p> : (
          <table>
            <thead>
            <tr><th>Date</th><th>Event</th><th>Map</th><th>Score ({a.name}–{b.name})</th><th>Winner</th></tr>
            </thead>
            <tbody>
            {matchup.head_to_head.map((r) => (
              <tr key={`${r.series_id}:${r.game_id}:${r.map}`} className={r.map === map ? 'mu-current-map' : ''}>
                <td>{r.date}</td>
                <td>{r.event}</td>
                <td>{cap(r.map)}</td>
                <td>{r.a_rounds}–{r.b_rounds}</td>
                <td>{r.winner === a.id ? a.name : r.winner === b.id ? b.name : '–'}</td>
              </tr>
            ))}
            </tbody>
          </table>
        )}
      </section>
    </section>
  )
}
