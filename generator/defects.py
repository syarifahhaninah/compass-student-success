"""Deliberate data-quality defect injection.

Real institutional extracts are never clean. Each defect injected here is
logged to data/quality/injected_defects.csv so the ETL's validation layer can
be scored on its catch rate — the defect log is the answer key.
"""

import numpy as np
import pandas as pd

import config as cfg

VARIANTS = {
    "NSY": ["Nth Sydney", "NORTH SYDNEY", "NSY "],
    "MEL": ["Melb", "MELBOURNE ", "mel"],
    "BRI": ["Brisbane", "BRIS"],
    "STR": ["Strathfield", "STRATH"],
}


def inject(rng: np.random.Generator, tables: dict) -> pd.DataFrame:
    log = []
    students = tables["banner_students"]
    enrol = tables["banner_enrolments"]

    # 1. duplicate shell student records (same person, second ID)
    k = max(1, int(len(students) * cfg.DEFECT_RATES["duplicate_student"]))
    dupes = students.sample(k, random_state=int(rng.integers(1e9))).copy()
    new_ids = (students.student_id.astype(int).max() + 1 + np.arange(k)).astype(str)
    log += [{"defect_type": "duplicate_student", "table": "banner_students",
             "row_key": nid, "detail": f"duplicate of {oid}"}
            for nid, oid in zip(new_ids, dupes.student_id)]
    dupes["student_id"] = new_ids
    dupes["student_status"] = "active"
    tables["banner_students"] = pd.concat([students, dupes], ignore_index=True)
    students = tables["banner_students"]

    # 2. missing equity flags
    k = int(len(students) * cfg.DEFECT_RATES["missing_equity_flag"])
    rows = rng.choice(len(students), size=k, replace=False)
    for r in rows:
        col = "first_nations_flag" if rng.random() < 0.5 else "disability_flag"
        students.loc[r, col] = ""
        log.append({"defect_type": "missing_equity_flag", "table": "banner_students",
                    "row_key": students.loc[r, "student_id"], "detail": col})

    # 3. campus code variants in enrolments
    eligible = enrol.index[enrol.campus_code.isin(VARIANTS)].to_numpy()
    k = int(len(enrol) * cfg.DEFECT_RATES["campus_code_variant"])
    rows = rng.choice(eligible, size=min(k, len(eligible)), replace=False)
    for r in rows:
        good = enrol.loc[r, "campus_code"]
        bad = VARIANTS[good][int(rng.integers(0, len(VARIANTS[good])))]
        enrol.loc[r, "campus_code"] = bad
        log.append({"defect_type": "campus_code_variant", "table": "banner_enrolments",
                    "row_key": f"{enrol.loc[r, 'student_id']}|{enrol.loc[r, 'unit_code']}|{enrol.loc[r, 'term_code']}",
                    "detail": f"{good} -> {bad}"})

    # 4. out-of-range marks
    graded = enrol.index[enrol.mark.notna()].to_numpy()
    k = max(1, int(len(enrol) * cfg.DEFECT_RATES["mark_out_of_range"]))
    rows = rng.choice(graded, size=min(k, len(graded)), replace=False)
    for r in rows:
        bad = 105.0 if rng.random() < 0.5 else -1.0
        enrol.loc[r, "mark"] = bad
        log.append({"defect_type": "mark_out_of_range", "table": "banner_enrolments",
                    "row_key": f"{enrol.loc[r, 'student_id']}|{enrol.loc[r, 'unit_code']}|{enrol.loc[r, 'term_code']}",
                    "detail": str(bad)})

    # 5. whitespace / case noise in names
    k = int(len(students) * cfg.DEFECT_RATES["name_whitespace_case"])
    rows = rng.choice(len(students), size=k, replace=False)
    for r in rows:
        v = students.loc[r, "first_name"]
        students.loc[r, "first_name"] = f"  {v.upper()}" if rng.random() < 0.5 else f"{v} "
        log.append({"defect_type": "name_whitespace_case", "table": "banner_students",
                    "row_key": students.loc[r, "student_id"], "detail": "first_name"})

    # 6. DD/MM/YYYY dates in dob
    k = int(len(students) * cfg.DEFECT_RATES["dob_format_dmy"])
    rows = rng.choice(len(students), size=k, replace=False)
    for r in rows:
        iso = students.loc[r, "dob"]
        y, mo, d = iso.split("-")
        students.loc[r, "dob"] = f"{d}/{mo}/{y}"
        log.append({"defect_type": "dob_format_dmy", "table": "banner_students",
                    "row_key": students.loc[r, "student_id"], "detail": iso})

    return pd.DataFrame(log)
