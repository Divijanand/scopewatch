import { useEffect, useMemo, useState } from 'react'
import { api, cap } from './api'
import type { MapMeta, Profile, Team, TeamMap } from './api'
import { MapView } from './MapView'
import { Findings } from './Findings'
import type { Bucket } from './Findings'

type Side = 'attacker' | 'defender' | null

export default function App() {
  const [teams, setTeams] = useState<Team[]>([])
  const [mapsMeta, setMapsMeta] = useState<Record<string, MapMeta>>({})
  const [teamId, setTeamId] = useState<string>('')
  const [teamMaps, setTeamMaps] = useState<TeamMap[]>([])
  const [map, setMap] = useState<string>('')
  const [side, setSide] = useState<Side>('defender')
  const [player, setPlayer] = useState<string | null>(null)
  const [buckets, setBuckets] = useState<Set<Bucket>>(new Set())
  const [showDamage, setShowDamage] = useState(true)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [spawns, setSpawns] = useState<Record<string, { x: number; y: number }> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    Promise.all([api.teams(), api.maps()])
      .then(([t, m]) => { setTeams(t); setMapsMeta(m); setTeamId(t[0]?.team_id ?? '') })
      .catch(() => setError('Can’t reach the Scopewatch API. Start it with: uvicorn api.server:app --port 8000'))
  }, [])

  useEffect(() => {
    if (!teamId) return
    setPlayer(null)
    api.teamMaps(teamId).then((ms) => {
      const usable = ms.filter((m) => mapsMeta[m.map])
      setTeamMaps(usable)
      setMap((cur) => (usable.some((m) => m.map === cur) ? cur : usable[0]?.map ?? ''))
    })
  }, [teamId, mapsMeta])

  useEffect(() => {
    if (!teamId || !map) return
    setLoading(true)
    api.profile({ team_id: teamId, map, side: side ?? undefined, player_id: player ?? undefined })
      .then((p) => { setProfile(p); setError(null) })
      .catch((e) => setError(String(e.message)))
      .finally(() => setLoading(false))
  }, [teamId, map, side, player])

  useEffect(() => { if (map) api.spawns(map).then(setSpawns).catch(() => setSpawns(null)) }, [map])

  const team = teams.find((t) => t.team_id === teamId)
  const engagements = useMemo(
    () => (profile?.engagements ?? []).filter((e) => buckets.size === 0 || buckets.has(e.t_bucket as Bucket)),
    [profile, buckets],
  )
  const toggleBucket = (b: Bucket) =>
    setBuckets((s) => { const n = new Set(s); if (n.has(b)) n.delete(b); else n.add(b); return n })

  const grouped = useMemo(() => {
    const g: Record<string, Team[]> = { 'Cloud9 (self-scout)': [], VCT: [], 'Game Changers': [] }
    for (const t of teams) (t.name?.toLowerCase().startsWith('cloud9') ? g['Cloud9 (self-scout)'] : g[t.league]).push(t)
    for (const k of ['VCT', 'Game Changers']) g[k].sort((a, b) => a.name.localeCompare(b.name))
    return g
  }, [teams])

  const playerName = profile?.carriers.find((c) => c.player_id === player)?.name

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="22" height="22" aria-hidden>
            <circle cx="16" cy="16" r="11" fill="none" stroke="currentColor" strokeWidth="3" />
            <path d="M16 2v8M16 22v8M2 16h8M22 16h8" stroke="var(--sky)" strokeWidth="3" />
          </svg>
          Scopewatch
        </div>
        <label className="team-pick">
          <span className="sr">Opponent</span>
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
              Operator report{map && <> for {cap(map)}</>}
              {side && <>, {side === 'attacker' ? 'attack' : 'defense'}</>}
              {playerName && <>, {playerName} only</>}.
              {profile && <> Based on {profile.sample.rounds} rounds across {profile.sample.maps} maps.</>}
            </p>
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
          </nav>

          <div className={loading ? 'board loading' : 'board'}>
            {map && mapsMeta[map] && profile && (
              <MapView mapName={map} meta={mapsMeta[map]} engagements={engagements}
                       spawns={spawns} showDamage={showDamage} />
            )}
            {profile && (
              <Findings p={profile} side={side} activePlayer={player} onPlayer={setPlayer}
                        buckets={buckets} onBucket={toggleBucket} />
            )}
          </div>
          <footer className="legend">
            <span className="grad" aria-hidden /> Early fight to late fight
            <span className="lg-kill" aria-hidden>×</span> Kill
            <span className="lg-dmg" aria-hidden /> Hit, no kill
          </footer>
        </main>
      )}
    </div>
  )
}
