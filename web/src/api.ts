export type Rate = { k: number; n: number; p: number | null; lo: number | null; hi: number | null }

export type Team = {
  team_id: string
  name: string
  rounds: number
  maps: number
  op_rounds: number
  last_played: string
  league: 'VCT' | 'Game Changers'
}

export type TeamMap = { map: string; maps: number; rounds: number; op_rounds: number }

export type MapMeta = {
  minX: number; minY: number; maxX: number; maxY: number
  width: number; height: number; samples: number
}

export type Engagement = {
  game_id: string
  round_no: number
  map: string
  kind: 'kill' | 'damage'
  weapon: 'operator' | 'outlaw'
  t_round: number
  t_bucket: string
  nth: number
  att_id: string
  att_name: string
  agent: string | null
  side: 'attacker' | 'defender'
  x: number; y: number
  vic_name: string
  vx: number; vy: number
  won: boolean | null
  fwd?: number
}

export type Carrier = {
  player_id: string; name: string; rounds: number; share: Rate; top_agent: string; agents: string[]
}

export type Profile = {
  sample: { rounds: number; maps: number; op_engagements: number; op_kills: number }
  buy_rate: Rate
  buy_by_economy: Record<'eco' | 'half' | 'full', Rate & { win_rate_with_op: Rate }>
  buy_by_side: Record<string, Rate>
  win_rate_with_op: Rate
  win_rate_full_buy_without_op: Rate
  carriers: Carrier[]
  possession_shift: Rate
  kill_timing: Record<string, { kills: number; share: Rate }>
  median_kill_t: number | null
  league_fwd: Partial<Record<'attacker' | 'defender', number>>
  engagements: Engagement[]
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} returned ${r.status}`)
  return r.json()
}

export const api = {
  teams: () => get<Team[]>('/api/teams'),
  teamMaps: (id: string) => get<TeamMap[]>(`/api/teams/${id}/maps`),
  maps: () => get<Record<string, MapMeta>>('/api/maps'),
  spawns: (map: string) => get<Record<string, { x: number; y: number }>>(`/api/spawns/${map}`),
  profile: (q: { team_id: string; map?: string; side?: string; player_id?: string }) => {
    const p = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][])
    return get<Profile>(`/api/profile?${p}`)
  },
}

export const pct = (r: Rate | undefined) => (r && r.p != null ? `${Math.round(r.p * 100)}%` : '–')
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
