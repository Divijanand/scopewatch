import duckdb
import pandas as pd
from engine.config import DB_PATH, V2_DIR
from engine.model import winprob
from engine.weapons import SNIPERS  # Operator, Outlaw and Chamber's Tour de Force (D-016)

MODEL_DIR = V2_DIR / "models"
EVENT_WP_PATH = MODEL_DIR / "event_wp.parquet"
HOLDER_WPA_PATH = MODEL_DIR / "holder_wpa.parquet"

def build_event_wp():
    model = winprob.load_model()
    if model is None:
        print("Model not found. Run python -m engine.model.winprob first.")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)
    
    # Kills in pre_plant and post_plant
    # Join rounds for series_id, team_rounds for side loadouts
    kills = con.execute("""
        SELECT e.event_id, e.round_key, e.t_round, e.kind, e.phase, e.weapon,
               e.att_id, e.att_team, e.att_side, e.vic_id, e.vic_team, e.vic_side,
               r.series_id, e.seq
        FROM engagements e
        JOIN rounds r ON e.round_key = r.round_key
        WHERE e.kind = 'kill' AND e.phase IN ('pre_plant', 'post_plant')
    """).df()
    
    # Plants
    plants = con.execute("""
        SELECT o.event_id, o.round_key, o.t_round, o.kind, 'pre_plant' as phase, NULL as weapon,
               o.player_id as att_id, o.team_id as att_team, 'attacker' as att_side,
               NULL as vic_id, NULL as vic_team, NULL as vic_side,
               r.series_id, 0 as seq
        FROM objectives o
        JOIN rounds r ON o.round_key = r.round_key
        WHERE o.kind = 'plant'
    """).df()
    
    # Round context
    rounds = con.execute("""
        SELECT r.round_key, r.series_id, r.map,
               tra.team_loadout as att_loadout, trd.team_loadout as def_loadout
        FROM rounds r
        JOIN team_rounds tra ON r.round_key = tra.round_key AND tra.side = 'attacker'
        JOIN team_rounds trd ON r.round_key = trd.round_key AND trd.side = 'defender'
    """).df().set_index('round_key')
    
    # Initial Operator holders
    player_ops = con.execute("""
        SELECT round_key, player_id, player_name, team_id, side, started_at
        FROM player_rounds 
        WHERE has_op = true
    """).df()
    con.close()

    ops_by_round = {k: g for k, g in player_ops.groupby('round_key')}
    
    # Order events deterministically: t_round, kind (kills before plants), then seq/event_id
    # 'kill' comes before 'plant' alphabetically, so we can sort by kind.
    all_events = pd.concat([kills, plants]).sort_values(['round_key', 't_round', 'kind', 'seq', 'event_id'], kind='stable')
    
    results = []
    
    # Pre-calculate all states for batch prediction
    states_to_predict = []
    event_metadata = []

    for round_key, group in all_events.groupby('round_key'):
        if round_key not in rounds.index:
            continue
            
        r_ctx = rounds.loc[round_key]
        r_ops = ops_by_round.get(round_key, pd.DataFrame(columns=['side', 'player_id']))
        
        att_alive = 5
        def_alive = 5
        att_ops = set(r_ops[r_ops['side'] == 'attacker']['player_id'])
        def_ops = set(r_ops[r_ops['side'] == 'defender']['player_id'])
        is_planted = False
        plant_t = None
        
        # State at t=0
        states_to_predict.append({
            'seconds_since_buy_phase_end': 0,
            'planted': False,
            'seconds_since_plant': 0,
            'attackers_alive': 5,
            'defenders_alive': 5,
            'att_loadout_value': r_ctx.att_loadout,
            'def_loadout_value': r_ctx.def_loadout,
            'att_has_op': len(att_ops) > 0,
            'def_has_op': len(def_ops) > 0
        })
        event_metadata.append(('start', round_key, None))
        
        for ev in group.itertuples():
            # Update state based on event
            if ev.kind == 'kill':
                if ev.vic_side == 'attacker':
                    att_alive -= 1
                    att_ops.discard(ev.vic_id)
                else:
                    def_alive -= 1
                    def_ops.discard(ev.vic_id)
            elif ev.kind == 'plant':
                is_planted = True
                plant_t = ev.t_round
            
            states_to_predict.append({
                'seconds_since_buy_phase_end': ev.t_round,
                'planted': is_planted,
                'seconds_since_plant': (ev.t_round - plant_t) if is_planted else 0,
                'attackers_alive': att_alive,
                'defenders_alive': def_alive,
                'att_loadout_value': r_ctx.att_loadout,
                'def_loadout_value': r_ctx.def_loadout,
                'att_has_op': len(att_ops) > 0,
                'def_has_op': len(def_ops) > 0
            })
            event_metadata.append(('event', round_key, ev))

    print(f"Predicting WP for {len(states_to_predict)} states...")
    all_wps = winprob.predict_wp(model, pd.DataFrame(states_to_predict))
    
    wp_idx = 0
    wp_before = None
    
    for meta_type, rk, ev in event_metadata:
        wp = all_wps[wp_idx]
        if meta_type == 'start':
            wp_before = wp
        else:
            results.append({
                'round_key': ev.round_key,
                'series_id': ev.series_id,
                'event_id': ev.event_id,
                'kind': ev.kind,
                'att_id': ev.att_id,
                'att_team': ev.att_team,
                'att_side': ev.att_side,
                'vic_id': ev.vic_id,
                'vic_team': ev.vic_team,
                'vic_side': ev.vic_side,
                'weapon': ev.weapon,
                'wp_before': wp_before,
                'wp_after': wp
            })
            wp_before = wp
        wp_idx += 1

    df_events = pd.DataFrame(results)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df_events.to_parquet(EVENT_WP_PATH)
    print(f"Wrote {len(df_events)} events to {EVENT_WP_PATH}")

    # Compute holder WPA
    # holder WPA = sum(dwp for holder kills) + sum(dwp for holder deaths)
    # dwp is from attacker perspective, so we need to flip it for defenders.
    
    # Aggregated WPA per (round_key, player_id)
    # Kills
    op_kills = df_events[(df_events['kind'] == 'kill') & 
                         (df_events['weapon'].isin(SNIPERS))]
    # Sum dwp per (round_key, att_id)
    if not op_kills.empty:
        kills_wpa = op_kills.assign(dwp = lambda d: d['wp_after'] - d['wp_before']).groupby(['round_key', 'att_id'])['dwp'].sum().reset_index()
        kills_wpa.columns = ['round_key', 'player_id', 'dwp']
    else:
        kills_wpa = pd.DataFrame(columns=['round_key', 'player_id', 'dwp'])
    
    # Deaths
    deaths = df_events[df_events['kind'] == 'kill']
    # Sum dwp per (round_key, vic_id)
    if not deaths.empty:
        deaths_wpa = deaths.assign(dwp = lambda d: d['wp_after'] - d['wp_before']).groupby(['round_key', 'vic_id'])['dwp'].sum().reset_index()
        deaths_wpa.columns = ['round_key', 'player_id', 'dwp']
    else:
        deaths_wpa = pd.DataFrame(columns=['round_key', 'player_id', 'dwp'])
    
    # Combine
    # Note: kills_wpa and deaths_wpa might have overlapping (round_key, player_id)
    # for example if a holder kills and then dies in the same round.
    wpa_agg = pd.concat([kills_wpa, deaths_wpa])
    if not wpa_agg.empty:
        wpa_agg = wpa_agg.groupby(['round_key', 'player_id'])['dwp'].sum().reset_index()
    else:
        wpa_agg = pd.DataFrame(columns=['round_key', 'player_id', 'dwp'])

    # Merge with population
    holder_wpa = player_ops.merge(wpa_agg, on=['round_key', 'player_id'], how='left').fillna(0)
    holder_wpa['wpa_pp'] = holder_wpa.apply(
        lambda r: (r['dwp'] if r['side'] == 'attacker' else -r['dwp']) * 100.0, axis=1
    )
    
    # Add series_id and map from rounds
    holder_wpa = holder_wpa.merge(rounds[['series_id', 'map']], on='round_key', how='left')
    
    holder_wpa = holder_wpa[['round_key', 'series_id', 'player_id', 'player_name', 'team_id', 'side', 'map', 'started_at', 'wpa_pp']]
    holder_wpa.to_parquet(HOLDER_WPA_PATH)
    print(f"Wrote {len(holder_wpa)} holder rounds to {HOLDER_WPA_PATH}")

if __name__ == "__main__":
    build_event_wp()
