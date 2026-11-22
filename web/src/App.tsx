import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, cap } from './api'
import type { Catalog, Coverage, Finding, Query, Spatial, Team, TeamMap, Tendencies, UtilityGroup, UtilityLayer } from './api'
import { GROUP_LABEL, UtilityFindings, UtilityMap } from './Utility'
import type { UtilFocus } from './Utility'
import { MapView } from './MapView'
import { Findings, bucketOf } from './Findings'
import type { Bucket, Focus } from './Findings'
import { EvidenceDrawer } from './Evidence'
import type { EvidenceRequest } from './Evidence'
import { Summary } from './Summary'

type Side = 'attacker' | 'defender' | null

function CoverageStrip({ c, warnings }: { c: Coverage; warnings: string[] }) {
  return (
    <div className="coverage" aria-label="What this view is based on">
      <p>
        {c.rounds} rounds across {c.maps} maps in {c.series} series
        {c.first_date && <>, {c.first_date} to {c.last_date}</>}, {c.patches.length} patch{c.patches.length === 1 ? '' : 'es'}.
        {c.rounds_inventory_unknown > 0 && <> {c.rounds_inventory_unknown} rounds have no loadout snapshot and are left out.</>}
        {c.rows_voided_by_reversals > 0 && <> {c.rows_voided_by_reversals} records the feed later retracted were removed.</>}
      </p>
      {warnings.map((w) => <p key={w} className="warn">{w}</p>)}
    </div>
  )
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [teamId, setTeamId] = useState('')
  const [teamMaps, setTeamMaps] = useState<TeamMap[]>([])
  const [map, setMap] = useState('')
  const [side, setSide] = useState<Side>('defender')
  const [player, setPlayer] = useState<string | null>(null)
  const [buckets, setBuckets] = useState<Set<Bucket>>(new Set())
  const [showDamage, setShowDamage] = useState(true)
  const [focus, setFocus] = useState<Focus | null>(null)
  const [view, setView] = useState<'report' | 'operator' | 'utility'>('report')
  const [group, setGroup] = useState<UtilityGroup>('setup')
  const [util, setUtil] = useState<UtilityLayer | null>(null)
  const [utilFocus, setUtilFocus] = useState<UtilFocus | null>(null)
  const [utilAgent, setUtilAgent] = useState<string | null>(null)
  const [agentList, setAgentList] = useState<{ agent: string; rounds: number }[]>([])
  const [tend, setTend] = useState<Tendencies | null>(null)
  const [summary, setSummary] = useState<Finding[]>([])
  const [summaryNote, setSummaryNote] = useState<string | null>(null)
  const [coverage, setCoverage] = useState<Coverage | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [spatial, setSpatial] = useState<Spatial | null>(null)
  const [evidence, setEvidence] = useState<EvidenceRequest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.catalog()
      .then((r) => { setCatalog(r.data); setTeamId(r.data.teams[0]?.team_id ?? '') })
      .catch(() => setError('Can’t reach the Scopewatch API. Start it from the repo root with: uvicorn api.server:app --port 8000'))
  }, [])

  useEffect(() => {
    if (!teamId || !catalog) return
    setPlayer(null); setBuckets(new Set()); setEvidence(null)
    api.teamMaps(teamId).then((r) => {
      const usable = r.data.filter((m) => catalog.maps[m.map])
      setTeamMaps(usable)
      setMap((cur) => (usable.some((m) => m.map === cur) ? cur : usable[0]?.map ?? ''))
    })
  }, [teamId, catalog])

  const q: Query | null = useMemo(
    () => (teamId && map ? { team_id: teamId, map, side: side ?? undefined, player_id: player ?? undefined } : null),
    [teamId, map, side, player],
  )

  useEffect(() => {
    if (!q) return
    setFocus(null)
    setLoading(true)
    Promise.all([api.tendencies(q), api.spatial(q)])
      .then(([t, s]) => {
        setTend(t.data.tendencies); setSummary(t.data.summary ?? []); setSummaryNote(t.data.summary_note ?? null)
        setCoverage(t.coverage ?? null); setWarnings(t.warnings); setSpatial(s.data); setError(null)
      })
      .catch((e) => setError(`Couldn’t load this view: ${e.message}`))
      .finally(() => setLoading(false))
  }, [q])

  useEffect(() => {
    if (!q || view !== 'utility') return
    setUtilFocus(null)
    setLoading(true)
    api.utility({ ...q, side: q.side ?? 'defender', group, agent: utilAgent ?? undefined })
      .then((r) => {
        setUtil(r.data); setError(null)
        setAgentList((r.data.result.value.agents ?? []) as { agent: string; rounds: number }[])
      })
      .catch((e) => setError(`Couldn’t load utility: ${e.message}`))
      .finally(() => setLoading(false))
  }, [q, view, group, utilAgent])

  // a different team, map or side has a different roster: go back to the layer view
  useEffect(() => { setUtilAgent(null) }, [teamId, map, side])

  const team: Team | undefined = catalog?.teams.find((t) => t.team_id === teamId)
  const metricDefs = useMemo(() => {
    const byId: Record<string, any> = {}
    if (!tend) return byId
    for (const m of Object.values(tend)) byId[m.metric.id] = m.metric
    return byId
  }, [tend])
  const engagements = useMemo(
    () => (spatial?.engagements ?? []).filter((e) => buckets.size === 0 || buckets.has(bucketOf(e.t_round))),
    [spatial, buckets],
  )
  const toggleBucket = (b: Bucket) =>
    setBuckets((s) => { const n = new Set(s); if (n.has(b)) n.delete(b); else n.add(b); return n })
  const closeEvidence = useCallback(() => setEvidence(null), [])

  const grouped = useMemo(() => {
    const g: Record<string, Team[]> = { 'Cloud9 (self-scout)': [], VCT: [], 'Game Changers': [] }
    for (const t of catalog?.teams ?? []) (t.name?.toLowerCase().startsWith('cloud9') ? g['Cloud9 (self-scout)'] : g[t.league]).push(t)
    for (const k of ['VCT', 'Game Changers']) g[k].sort((a, b) => a.name.localeCompare(b.name))
    return g
  }, [catalog])

  const playerName = tend?.['op.holder_share'].breakdown.find((c) => c.player_id === player)?.name

  return (
    <div className={evidence ? 'app with-drawer' : 'app'}>
      <header className="top">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden>
            <circle cx="16" cy="16" r="11" fill="none" stroke="currentColor" strokeWidth="3" />
            <path d="M16 2v8M16 22v8M2 16h8M22 16h8" stroke="var(--sky)" strokeWidth="3" />
          </svg>
          Scopewatch
        </div>
        <label className="team-pick">
          <span className="sr">Team</span>
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
            {Object.entries(grouped).map(([g, ts]) => ts.length > 0 && (
              <optgroup key={g} label={g}>
                {ts.map((t) => <option key={t.team_id} value={t.team_id}>{t.name} ({t.maps} maps)</option>)}
              </optgroup>
            ))}
          </select>
        </label>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      {team && (
        <main>
          <div className="title">
            <h1>{team.name}</h1>
            <p className="sub">
              Scouting report{map && <> for {cap(map)}</>}
              {side && <>, {side === 'attacker' ? 'attack' : 'defense'}</>}
              {playerName && <>, {playerName} only</>}.
            </p>
            {coverage && <CoverageStrip c={coverage} warnings={warnings} />}
          </div>

          <nav className="controls" aria-label="Filters">
            <div className="maps" role="tablist" aria-label="Map">
              {teamMaps.map((m) => (
                <button key={m.map} role="tab" aria-selected={m.map === map} onClick={() => setMap(m.map)}>
                  {cap(m.map)} <span className="count">{m.maps}</span>
                </button>
              ))}
            </div>
            <div className="seg" role="group" aria-label="Side">
              {([['defender', 'Defense'], ['attacker', 'Attack'], [null, 'Both']] as const).map(([v, l]) => (
                <button key={l} aria-pressed={side === v} onClick={() => setSide(v)}>{l}</button>
              ))}
            </div>
            <label className="check">
              <input type="checkbox" checked={showDamage} onChange={(e) => setShowDamage(e.target.checked)} />
              Show hits that didn’t kill
            </label>
            {(player || buckets.size > 0 || focus) && (
              <button className="reset" onClick={() => { setPlayer(null); setBuckets(new Set()); setFocus(null) }}>Clear filters</button>
            )}
          </nav>

          <div className="views" role="tablist" aria-label="What to show">
            <button role="tab" aria-selected={view === 'report'} onClick={() => setView('report')}>Report</button>
            <button role="tab" aria-selected={view === 'operator'} onClick={() => setView('operator')}>Operator</button>
            <button role="tab" aria-selected={view === 'utility'} onClick={() => { setView('utility'); if (!side) setSide('defender') }}>Utility</button>
            {view === 'utility' && (
              <div className="seg" role="group" aria-label="Utility type">
                {(Object.keys(GROUP_LABEL) as UtilityGroup[]).map((g) => (
                  <button key={g} aria-pressed={!utilAgent && group === g} onClick={() => { setUtilAgent(null); setGroup(g) }}>{GROUP_LABEL[g]}</button>
                ))}
              </div>
            )}
          </div>
          {view === 'utility' && agentList.length > 0 && (
            <div className="agents" role="group" aria-label="Show one agent's whole kit">
              <span className="agents-label">Or one agent’s whole kit:</span>
              {agentList.map((a) => (
                <button key={a.agent} aria-pressed={utilAgent === a.agent}
                        onClick={() => setUtilAgent(utilAgent === a.agent ? null : a.agent)}>
                  {cap(a.agent)} <span className="num">{a.rounds}</span>
                </button>
              ))}
            </div>
          )}

          {view === 'utility' ? (
            <div className={loading ? 'board loading' : 'board'} aria-busy={loading}>
              {map && catalog?.maps[map] && util && (
                <UtilityMap mapName={map} meta={catalog.maps[map]} layer={util} focus={utilFocus} />
              )}
              {util && (
                <UtilityFindings layer={util} side={side} def={catalog?.metrics.find((m) => m.id === 'util.placements')}
                                 ultDef={catalog?.metrics.find((m) => m.id === 'ult.usage')}
                                 focus={utilFocus} onFocus={setUtilFocus} onEvidence={setEvidence} />
              )}
            </div>
          ) : (
          <div className={loading ? 'board loading' : 'board'} aria-busy={loading}>
            {view === 'operator' && map && catalog?.maps[map] && spatial && (
              <MapView mapName={map} meta={catalog.maps[map]} engagements={engagements}
                       spawns={spatial.spawns} showDamage={showDamage} focus={focus} />
            )}
            {tend && (
              <>
                {view === 'report' && <Summary findings={summary} note={summaryNote} metricDefs={metricDefs} onEvidence={setEvidence} />}
                <Findings t={tend} side={side} activePlayer={player} onPlayer={setPlayer}
                        buckets={buckets} onBucket={toggleBucket} onEvidence={setEvidence}
                        focus={focus} onFocus={setFocus} sections={view === 'report' ? 'report' : 'operator'} />
              </>
            )}
          </div>
          )}
          {view === 'operator' && <footer className="legend">
            <span className="grad" aria-hidden /> Early fight to late fight
            <span className="lg-kill" aria-hidden>×</span> Kill
            <span className="lg-dmg" aria-hidden /> Hit, no kill
            <span className="lg-src">Positions are where each shot was recorded, not continuous tracking.</span>
          </footer>}
        </main>
      )}

      <p className="legal">
        Match data © GRID eSports GmbH and Riot Games, Inc., used under the hackathon data license.
        Scopewatch was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games.
        Riot Games does not endorse or sponsor this project.
      </p>

      {evidence && q && <EvidenceDrawer req={evidence} q={q} onClose={closeEvidence} />}
    </div>
  )
}
