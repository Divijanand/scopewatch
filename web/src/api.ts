export type Rate = { k: number; n: number; p: number | null; lo: number | null; hi: number | null; small_sample: boolean }

export type Envelope<T> = {
  data: T
  warnings: string[]
  definition_versions: string[]
  dataset_revision: string
  parser_version: string
  filter_hash?: string
  coverage?: Coverage
}

export type Team = {
  team_id: string; name: string; rounds: number; maps: number; op_rounds: number
  last_played: string; league: 'VCT' | 'Game Changers'
}
export type TeamMap = { map: string; maps: number; rounds: number; op_rounds: number }
export type Affine = { a: number; b: number; c: number; d: number; e: number; f: number }
export type MapMeta = {
  minX: number; minY: number; maxX: number; maxY: number; width: number; height: number; samples: number
  transform: Affine; transform_version: string; image_sha1?: string; source?: 'minimap' | 'outline'
  callouts?: { name: string; x: number; y: number }[]
  calibration_status: 'validated' | 'needs_review' | 'not_validated'
}
export type MetricDef = {
  id: string; version: number; title: string; question: string; population: string
  numerator: string; unit: string; caveats: string[]
}
export type Catalog = { teams: Team[]; maps: Record<string, MapMeta>; metrics: MetricDef[] }

export type Coverage = {
  rounds: number; rounds_inventory_known: number; rounds_inventory_unknown: number
  maps: number; series: number; first_date: string | null; last_date: string | null
  patches: string[]; events: string[]
  engagements: number; engagements_no_position: number; engagements_position_repeat: number
  casts: number; casts_spatial_ok: number; casts_low_rate: number
  rows_voided_by_reversals: number; warnings: string[]
}

export type MetricResult = {
  metric_id: string
  metric: MetricDef
  rate: Rate | null
  breakdown: Array<Record<string, any> & { rate: Rate }>
  value: Record<string, any>
  unknown: { count: number; reason: string }[]
  maps: number; series: number
  evidence_counts: { supporting: number; contrary: number }
  warnings: string[]
}

export type Tendencies = Record<
  'op.possession_full_buy' | 'op.holder_share' | 'op.kill_timing' | 'op.opening' | 'op.win_association' | 'op.forwardness'
  | 'op.setups' | 'op.deaths',
  MetricResult
>

export type Engagement = {
  round_key: string; event_id: string; kind: 'kill' | 'damage'; weapon: string; t_round: number
  t_plant: number | null; phase: string; opening_kill: boolean | null; att_id: string; att_name: string
  agent: string | null; side: 'attacker' | 'defender'; x: number; y: number; pos_repeat: boolean | null
  vic_name: string; vx: number; vy: number; map: string; round_no: number; won: boolean | null
}
export type Spatial = { layer: string; engagements: Engagement[]; spawns: Record<string, { x: number; y: number }> }

export type EvidenceRound = {
  round_key: string; map: string; round_no: number; side: string; economy: string | null; won: boolean | null
  win_type: string; op_players: string[] | null; op_agents: string[] | null; date: string; event: string; opponent: string
}
export type Evidence = { total: number; which: string; rounds: EvidenceRound[] }

export type RoundContext = {
  round: {
    round_key: string; map: string; round_no: number; winner_team_id: string; winner_side: string
    win_type: string; duration_s: number | null; planted: boolean; plant_t: number | null
    event: string; date: string; patch: string
  }
  players: { team_id: string; team_name: string; side: string; player_id: string; name: string; agent: string; items: string; economy: string | null }[]
  kills: { kind: string; t_round: number | null; phase: string; weapon: string | null; attacker: string; attacker_side: string; victim: string; opening: boolean | null }[]
  objectives: { kind: string; t_round: number | null; player_id: string }[]
}

export type Query = { team_id: string; map?: string; side?: string; player_id?: string; since?: string }

async function get<T>(url: string): Promise<Envelope<T>> {
  const r = await fetch(url)
  if (!r.ok) {
    let detail = `${r.status}`
    try { detail = (await r.json()).detail ?? detail } catch { /* not json */ }
    throw new Error(detail)
  }
  return r.json()
}

const qs = (q: Record<string, string | number | undefined | null>) =>
  new URLSearchParams(Object.entries(q).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)]))

export const api = {
  catalog: () => get<Catalog>('/api/catalog'),
  teamMaps: (id: string) => get<TeamMap[]>(`/api/teams/${id}/maps`),
  tendencies: (q: Query) => get<Tendencies>(`/api/weapons/tendencies?${qs(q)}`),
  spatial: (q: Query) => get<Spatial>(`/api/spatial/operator?${qs(q)}`),
  evidence: (q: Query & { metric: string; which: 'supporting' | 'contrary'; bucket?: string; page?: number }) =>
    get<Evidence>(`/api/evidence?${qs(q)}`),
  round: (key: string) => get<RoundContext>(`/api/rounds/${encodeURIComponent(key)}`),
}

export const pct = (r: Rate | null | undefined) => (r && r.p != null ? `${Math.round(r.p * 100)}%` : '–')
export const cap = (s: string | null | undefined) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '')
