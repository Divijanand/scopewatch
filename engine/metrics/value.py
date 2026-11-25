import duckdb
import pandas as pd
import numpy as np
from engine.config import DB_PATH, V2_DIR
from engine.significance import mean_p
from engine.metrics.core import Filters, MetricDef, MetricResult, Unknown, bootstrap_mean, metric

WPA_PARQUET = V2_DIR / "models" / "event_wp.parquet"
HOLDER_WPA_PARQUET = V2_DIR / "models" / "holder_wpa.parquet"

OP_WPA_DEF = MetricDef(
    id="op.wpa",
    version=1,
    title="What the Operator is worth",
    question="How much win probability does this player add per Operator round?",
    population="Player rounds where the player held an Operator or Outlaw at buy-phase end.",
    numerator="Sum of Win Probability Added (WPA) from Operator kills and holder's death.",
    unit="pp",
    caveats=(
        "The model has no positions, so a kill gets all the credit.",
        "Trades and assists aren't split.",
        "Association, not cause.",
        "The model also scores the series it was trained on."
    )
)

@metric(OP_WPA_DEF)
def get_op_wpa(con: duckdb.DuckDBPyConnection, f: Filters) -> MetricResult:
    res = MetricResult(OP_WPA_DEF, f)
    
    if not HOLDER_WPA_PARQUET.exists():
        res.warnings.append("Run python -m engine.model.wpa first")
        return res

    # 1. Load holder WPA and filter
    df = con.execute(f"SELECT * FROM read_parquet('{HOLDER_WPA_PARQUET.as_posix()}')").df()
    
    # Apply filters
    df = df[df['team_id'] == f.team_id]
    if f.map: df = df[df['map'] == f.map]
    if f.side: df = df[df['side'] == f.side]
    if f.since: df = df[df['started_at'] >= f.since]
    if f.until: df = df[df['started_at'] < f.until]
    if f.player_id: df = df[df['player_id'] == f.player_id]
    
    if df.empty:
        return res

    # Evidence
    res.supporting = sorted(df[df['wpa_pp'] > 0]['round_key'].unique().tolist())
    res.contrary = sorted(df[df['wpa_pp'] < 0]['round_key'].unique().tolist())
    res.series = len(df['series_id'].unique())
    res.maps = len(df['map'].unique())

    # Overall mean and bootstrap
    wpas = df['wpa_pp'].tolist()
    series = df['series_id'].tolist()
    mean_wpa = float(np.mean(wpas))
    lo, hi = bootstrap_mean(wpas, series)
    
    res.value = {
        "n": len(wpas),
        "mean": round(mean_wpa, 2),
        "lo": round(lo, 2),
        "hi": round(hi, 2)
    }

    # Breakdown by player
    player_stats = []
    for (pid, pname), group in df.groupby(['player_id', 'player_name']):
        p_wpas = group['wpa_pp'].tolist()
        p_series = group['series_id'].tolist()
        p_mean = float(np.mean(p_wpas))
        n = len(p_wpas)
        
        stat = {
            "player_id": pid,
            "player_name": pname,
            "n": n,
            "mean": round(p_mean, 2),
        }
        if n >= 10 and len(set(p_series)) > 1:      # one series has no range
            p_lo, p_hi = bootstrap_mean(p_wpas, p_series)
            stat.update({"lo": round(p_lo, 2), "hi": round(p_hi, 2)})
        else:
            stat["small_sample"] = True
            
        player_stats.append(stat)
        
    res.breakdown = sorted(player_stats, key=lambda x: x['mean'], reverse=True)

    # League mean
    ldf = con.execute(f"SELECT * FROM read_parquet('{HOLDER_WPA_PARQUET.as_posix()}')").df()
    if f.map: ldf = ldf[ldf['map'] == f.map]
    if f.side: ldf = ldf[ldf['side'] == f.side]
    if f.since: ldf = ldf[ldf['started_at'] >= f.since]
    if f.until: ldf = ldf[ldf['started_at'] < f.until]
    
    res.value["league_mean"] = round(float(ldf['wpa_pp'].mean()), 2) if not ldf.empty else 0.0
    res.value["p_value"] = mean_p(mean_wpa, lo, hi, res.series, null=res.value["league_mean"])

    return res
