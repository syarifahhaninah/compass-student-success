"""Compass synthetic data generator — entry point.

Usage:  python generator/generate.py [--seed N]

Writes Banner/Canvas/CRM-shaped source extracts to data/raw/, reference data,
and the simulation answer key (latent variables, injected defects, injected
intervention effect) to data/quality/. The answer key never enters the
warehouse — it exists so validation can compare what the pipeline finds
against what is actually true.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

import config as cfg
import defects
import population
from engine import Simulator

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
QUALITY = ROOT / "data" / "quality"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=cfg.SEED)
    args = ap.parse_args()

    t0 = time.time()
    rng = np.random.default_rng(args.seed)
    RAW.mkdir(parents=True, exist_ok=True)
    QUALITY.mkdir(parents=True, exist_ok=True)

    print("Building population ...")
    postcodes = population.make_postcode_lookup(rng)
    students, truth = population.make_students(rng, postcodes)
    catalogue = population.make_unit_catalogue(rng)
    advisors = population.make_advisors_df()
    print(f"  {len(students):,} students across {len(cfg.TERMS)} terms")

    print("Simulating terms ...")
    sim = Simulator(students, truth, catalogue, rng)
    sim.run()
    out = sim.outputs()

    print("Injecting data defects ...")
    defect_log = defects.inject(rng, out)

    print("Writing extracts ...")
    out["banner_students"].to_csv(RAW / "banner_students.csv", index=False)
    out["banner_enrolments"].to_csv(RAW / "banner_enrolments.csv", index=False)
    out["canvas_activity"].to_csv(RAW / "canvas_activity.csv", index=False)
    out["crm_cases"].to_csv(RAW / "crm_cases.csv", index=False)
    out["alerts_history"].to_csv(RAW / "alerts_history.csv", index=False)
    postcodes.to_csv(RAW / "ref_postcode_ses.csv", index=False)
    catalogue.to_csv(RAW / "ref_units.csv", index=False)
    advisors.to_csv(RAW / "ref_advisors.csv", index=False)

    truth.to_csv(QUALITY / "simulation_truth_students.csv", index=False)
    out["simulation_truth_events"].to_csv(
        QUALITY / "simulation_truth_events.csv", index=False)
    defect_log.to_csv(QUALITY / "injected_defects.csv", index=False)

    manifest = {
        "seed": args.seed,
        "as_of_date": str(cfg.AS_OF_DATE),
        "current_term": cfg.CURRENT_TERM,
        "students": len(out["banner_students"]),
        "enrolment_rows": len(out["banner_enrolments"]),
        "weekly_activity_rows": len(out["canvas_activity"]),
        "cases": len(out["crm_cases"]),
        "alerts": len(out["alerts_history"]),
        "injected_defects": len(defect_log),
        "injected_effect": {
            "p_effect_if_reached": cfg.P_EFFECT_IF_REACHED,
            "engagement_uplift": cfg.EFFECT_ENGAGE_UPLIFT,
            "retention_logit_bonus": cfg.EFFECT_RETENTION_LOGIT,
        },
    }
    (QUALITY / "generation_manifest.json").write_text(json.dumps(manifest, indent=2))

    for k, v in manifest.items():
        print(f"  {k}: {v}")
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
