"""Intervention effectiveness: naive vs matched comparison.

Advisors triage worst-first, so contacted students are systematically more
disengaged than uncontacted ones — a naive comparison is biased AGAINST the
intervention (the Purdue Course Signals failure, in reverse). This script
runs both estimators on next-term persistence for alerted students:

  1. Naive difference in means (reported to show why it's wrong)
  2. Coarsened Exact Matching (CEM): compare only within strata of
     alert timing, pre-alert engagement, missed assessments, mode,
     equity cohort and commencement status.

Because the generator INJECTED a known positive effect (engagement uplift for
60% of reached students + retention bonus), ground truth exists: the matched
estimate should recover a positive effect where the naive one shows negative.

Run after run_etl.py:  python etl/effectiveness.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WH = ROOT / "data" / "warehouse"
QUALITY = ROOT / "data" / "quality"
RNG = np.random.default_rng(7)
BOOTSTRAP = 400


def att_naive(df):
    return df[df.contacted == 1].retained_next_term.mean() \
        - df[df.contacted == 0].retained_next_term.mean()


def make_strata(df):
    """Bins mirror the observable triage inputs: simultaneous reasons at the
    first alert and inactivity at the alert, plus context covariates. All are
    pre-treatment."""
    s = pd.DataFrame(index=df.index)
    s["week"] = pd.cut(df.alert_week, [0, 5, 8, 12], labels=["w3-5", "w6-8", "w9-11"])
    s["reasons"] = df.reasons_at_alert.clip(1, 3).astype(int).astype(str)
    s["logins"] = pd.cut(df.logins_2wk_at_alert, [-1, 2, 6, 999],
                         labels=["inactive", "low", "normal"])
    s["missed"] = pd.cut(df.pre_missed, [-1, 2, 99], labels=["0-2", "3+"])
    s["online"] = df.online.astype(str)
    s["equity"] = df.nbf_equity.astype(str)
    s["first"] = df.first_term.astype(str)
    return s.astype(str).agg("|".join, axis=1)


def att_cem(df):
    d = df.copy()
    d["stratum"] = make_strata(d)
    g = d.groupby("stratum")
    rows = []
    for _, grp in g:
        t = grp[grp.contacted == 1]
        c = grp[grp.contacted == 0]
        if len(t) == 0 or len(c) == 0:
            continue
        rows.append((len(t), t.retained_next_term.mean() - c.retained_next_term.mean()))
    if not rows:
        return np.nan, 0, 0.0
    w = np.array([r[0] for r in rows], dtype=float)
    eff = np.array([r[1] for r in rows])
    matched_share = w.sum() / max((d.contacted == 1).sum(), 1)
    return float(np.average(eff, weights=w)), len(rows), float(matched_share)


def bootstrap_ci(df, fn, reps=BOOTSTRAP):
    stats = []
    n = len(df)
    for _ in range(reps):
        sample = df.iloc[RNG.integers(0, n, n)]
        v = fn(sample)
        stats.append(v[0] if isinstance(v, tuple) else v)
    return float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5))


def main():
    df = pd.read_csv(WH / "mart_effectiveness_input.csv")
    df["online"] = df.online.astype(bool)
    df["nbf_equity"] = df.nbf_equity.astype(bool)
    df["first_term"] = df.first_term.astype(bool)
    manifest = json.loads((QUALITY / "generation_manifest.json").read_text())

    naive = att_naive(df)
    naive_lo, naive_hi = bootstrap_ci(df, att_naive)
    cem, n_strata, matched_share = att_cem(df)
    cem_lo, cem_hi = bootstrap_ci(df, att_cem)

    print(f"alerted student-terms: {len(df):,}  "
          f"(contacted: {(df.contacted == 1).sum():,}, "
          f"uncontacted: {(df.contacted == 0).sum():,})")
    print("\n=== Effect of outreach on next-term persistence (percentage points) ===")
    print(f"  Naive difference:   {naive * 100:+6.1f}pp  [{naive_lo * 100:+.1f}, {naive_hi * 100:+.1f}]"
          f"   <- biased: advisors triage worst-first")
    print(f"  Matched (CEM):      {cem * 100:+6.1f}pp  [{cem_lo * 100:+.1f}, {cem_hi * 100:+.1f}]"
          f"   ({n_strata} strata, {matched_share:.0%} of treated matched)")
    inj = manifest["injected_effect"]
    print(f"\n  Ground truth: uplift injected for "
          f"~{0.7 * inj['p_effect_if_reached']:.0%} of contacted students "
          f"(engagement +{inj['engagement_uplift']}, retention logit "
          f"+{inj['retention_logit_bonus']}) -> true effect is POSITIVE.")
    verdict = "RECOVERED" if cem > 0 and cem > naive else "NOT RECOVERED"
    print(f"  Matched estimator {verdict} the injected positive effect; "
          f"naive estimator sign is {'wrong' if naive < 0 else 'attenuated'}.")

    out = pd.DataFrame([
        {"estimator": "Naive difference", "estimate_pp": round(naive * 100, 2),
         "ci_low_pp": round(naive_lo * 100, 2), "ci_high_pp": round(naive_hi * 100, 2),
         "note": "Biased: contacted students are selected for severity"},
        {"estimator": "Coarsened exact matching", "estimate_pp": round(cem * 100, 2),
         "ci_low_pp": round(cem_lo * 100, 2), "ci_high_pp": round(cem_hi * 100, 2),
         "note": f"{n_strata} strata; {matched_share:.0%} of treated matched"},
    ])
    out.to_csv(WH / "mart_effectiveness_results.csv", index=False)
    print(f"\nwrote {WH / 'mart_effectiveness_results.csv'}")


if __name__ == "__main__":
    main()
