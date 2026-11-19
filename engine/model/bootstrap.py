"""Step 3 of docs/ROADMAP_ML.md: bootstrapping without breaking accuracy or precision.

Two uses, both resampling whole series (rounds in a series are linked):
  1. Ensembles: K models, each trained on a resample of the TRAINING series. Their mean is the prediction; their
     spread says how sure the model is about a state (wide = rarely seen). The test series are never touched.
  2. Ranges on numbers we show (`core.bootstrap_mean`). `simulate_coverage` checks the method is honest: on
     data with known truth and the same clustered structure, a 90% range must contain the truth about 90% of the
     time. Too low = the ranges overclaim; too high = they're wider than they need to be.
"""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from ..metrics.core import bootstrap_mean
from . import winprob


def train_ensemble(train_df, k: int = 20, seed: int = 0):
    """K gradient-boosted models, each on a resample (with replacement) of whole training series."""
    rng = np.random.default_rng(seed)
    series = np.array(sorted(train_df["series_id"].unique()))
    by_series = {s: idx for s, idx in train_df.groupby("series_id").indices.items()}
    models = []
    for b in range(k):
        pick = rng.choice(series, size=len(series), replace=True)
        rows = np.concatenate([by_series[s] for s in pick])
        part = train_df.iloc[rows]
        m = HistGradientBoostingClassifier(random_state=seed + b)
        m.fit(part[winprob.FEATURES], part["label"])
        models.append(m)
    return models


def predict_ensemble(models, df):
    """Mean probability, standard deviation across models, and the 5th-95th percentile band per row."""
    P = np.vstack([m.predict_proba(df[winprob.FEATURES])[:, 1] for m in models])
    return dict(mean=P.mean(axis=0), std=P.std(axis=0), lo=np.percentile(P, 5, axis=0),
                hi=np.percentile(P, 95, axis=0))


def simulate_coverage(n_sims: int = 300, n_groups: int = 30, per_group: int = 8, group_sd: float = 0.15,
                      noise_sd: float = 0.3, seed: int = 0) -> dict:
    """How often core.bootstrap_mean's 90% range contains the true mean, on clustered data with a known truth.

    Each simulated dataset has n_groups 'series', each with its own offset (rounds in a series are correlated),
    and per_group values. Returns the coverage of the series bootstrap and, for contrast, of a naive bootstrap
    that resamples single values as if they were independent."""
    rng = np.random.default_rng(seed)
    hits_series = hits_naive = 0
    widths = []
    for i in range(n_sims):
        offsets = rng.normal(0, group_sd, n_groups)
        values = np.concatenate([o + rng.normal(0, noise_sd, per_group) for o in offsets])
        groups = np.repeat([f"S{g}" for g in range(n_groups)], per_group)
        truth = 0.0                                     # the population mean
        lo, hi = bootstrap_mean(values.tolist(), groups.tolist(), n=400, seed=i)
        hits_series += lo <= truth <= hi
        widths.append(hi - lo)
        nlo, nhi = bootstrap_mean(values.tolist(), [str(j) for j in range(len(values))], n=400, seed=i)
        hits_naive += nlo <= truth <= nhi
    return dict(n_sims=n_sims, series_coverage=hits_series / n_sims, naive_coverage=hits_naive / n_sims,
                mean_width=float(np.mean(widths)), target=0.90)
