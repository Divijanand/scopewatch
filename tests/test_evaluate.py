"""The evaluation measures behave as their definitions say (docs/ML_TAXONOMY.md section 3)."""
import numpy as np
import pytest

from engine.model import evaluate as ev


def test_coin_flip_reference_values():
    y = [0, 1] * 50
    p = [0.5] * 100
    assert ev.log_loss(y, p) == pytest.approx(np.log(2))
    assert ev.brier(y, p) == pytest.approx(0.25)
    assert ev.auc(y, p) == pytest.approx(0.5)


def test_perfect_and_backwards_ranking():
    y = [0, 0, 1, 1]
    assert ev.auc(y, [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert ev.auc(y, [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert ev.auc([1, 1], [0.3, 0.4]) is None


def test_calibration_honest_vs_overconfident():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 20000)
    y = (rng.uniform(0, 1, 20000) < p).astype(int)          # outcomes drawn from the stated probability
    assert ev.calibration(y, p)["ece"] < 0.02
    overconfident = np.where(p > 0.5, 0.99, 0.01)
    assert ev.calibration(y, overconfident)["ece"] > 0.2
    table = ev.calibration(y, p)["table"]
    assert sum(b["n"] for b in table) == 20000 and len(table) == 10


def test_multiclass_and_baseline():
    train_y = ["A", "A", "A", "B", "C", "B"]
    train_g = ["t1", "t1", "t1", "t1", "t2", "t2"]
    probs = ev.baseline_most_common(train_y, train_g, ["t1", "t9"])
    assert max(probs[0], key=probs[0].get) == "A"                # team t1's habit
    assert probs[1]["A"] == pytest.approx(4 / 9)                 # unseen team: smoothed overall rate
    assert all(abs(sum(d.values()) - 1) < 1e-9 for d in probs)
    assert ev.top1(["A", "B"], [{"A": 0.6, "B": 0.4}, {"A": 0.6, "B": 0.4}]) == 0.5
    assert ev.multiclass_log_loss(["A"], [{"A": 1.0}]) == pytest.approx(0, abs=1e-9)


def test_paired_difference_finds_a_real_improvement_and_not_noise():
    rng = np.random.default_rng(2)
    n = 6000
    groups = np.repeat(np.arange(300), n // 300)
    truth = rng.uniform(0.05, 0.95, n)
    y = (rng.uniform(0, 1, n) < truth).astype(int)
    vague = np.full(n, 0.5)
    real = ev.paired_difference(y, vague, truth, groups, n=300)
    assert real["difference"] < 0 and real["b_better"]                 # the true probabilities beat 50/50
    # the same model again is never a win, and its range sits on 0
    same = ev.paired_difference(y, truth, truth.copy(), groups, n=300)
    assert not same["b_better"] and same["lo"] == same["hi"] == same["difference"] == 0
    # a worse model (the truth pulled toward 50%) is reported as worse, not better
    worse = ev.paired_difference(y, truth, 0.5 + 0.5 * (truth - 0.5), groups, n=300)
    assert worse["difference"] > 0 and worse["lo"] > 0 and not worse["b_better"]


def test_coverage_measures_accuracy_and_width_of_ranges():
    out = ev.coverage([(0, 2), (0, 2), (5, 6), (1, 1)], [1, 3, 5.5, 1])
    assert out["coverage"] == 0.75 and out["mean_width"] == pytest.approx(1.25)
