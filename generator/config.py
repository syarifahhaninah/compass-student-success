"""Central configuration for the Compass synthetic data generator.

Every statistical target here is calibrated against published sector figures
(DoE Section 15 attrition/retention tables; ACSES 2026 retention update) so the
generated institution behaves like a plausible Australian multi-campus,
equity-heavy university. All knobs are in one place so calibration runs only
touch this file.
"""

from datetime import date

SEED = 20260716  # application closing date, for luck and reproducibility

# ---------------------------------------------------------------- terms ----
# S1 census ~ end of week 4; 13 teaching weeks. 2026S1 is in progress: the
# warehouse "as of" date sits at the start of week 9.
TERMS = [
    {"code": "2023S1", "start": date(2023, 2, 27), "weeks": 13},
    {"code": "2023S2", "start": date(2023, 7, 24), "weeks": 13},
    {"code": "2024S1", "start": date(2024, 2, 26), "weeks": 13},
    {"code": "2024S2", "start": date(2024, 7, 22), "weeks": 13},
    {"code": "2025S1", "start": date(2025, 2, 24), "weeks": 13},
    {"code": "2025S2", "start": date(2025, 7, 21), "weeks": 13},
    {"code": "2026S1", "start": date(2026, 2, 23), "weeks": 13},
]
CENSUS_WEEK = 4
CURRENT_TERM = "2026S1"
AS_OF_WEEK = 8          # engagement data exists through this week of 2026S1
AS_OF_DATE = date(2026, 4, 27)

# ------------------------------------------------------------- cohorts ----
# Commencing intake per year, split S1/S2. Online share grows year on year
# (the institution is expanding online delivery via an OPM partner).
INTAKE = {
    2023: {"total": 5200, "s2_share": 0.16, "online_share": 0.12},
    2024: {"total": 5500, "s2_share": 0.16, "online_share": 0.14},
    2025: {"total": 5800, "s2_share": 0.17, "online_share": 0.17},
    2026: {"total": 4950, "s2_share": 0.00, "online_share": 0.21},
}

# ------------------------------------------------------------ campuses ----
# (code, name, state, weight among on-campus students)
CAMPUSES = [
    ("NSY", "North Sydney", "NSW", 0.24),
    ("STR", "Strathfield", "NSW", 0.12),
    ("BLK", "Blacktown", "NSW", 0.06),
    ("MEL", "Melbourne", "VIC", 0.26),
    ("BAL", "Ballarat", "VIC", 0.06),
    ("BRI", "Brisbane", "QLD", 0.19),
    ("CAN", "Canberra", "ACT", 0.07),
]
ONLINE_CAMPUS = ("ONL", "Online", "MULTI")

# ------------------------------------------------------------ programs ----
# (code, name, weight) — weighted toward health and education, care-economy style.
PROGRAMS = [
    ("BNURS", "Bachelor of Nursing", 0.20),
    ("BEDPR", "Bachelor of Education (Primary)", 0.11),
    ("BEDSE", "Bachelor of Education (Secondary)", 0.07),
    ("BPHYS", "Bachelor of Physiotherapy", 0.06),
    ("BOCCT", "Bachelor of Occupational Therapy", 0.05),
    ("BSOCW", "Bachelor of Social Work", 0.07),
    ("BPSYC", "Bachelor of Psychological Science", 0.10),
    ("BEXSC", "Bachelor of Exercise and Sports Science", 0.06),
    ("BPARA", "Bachelor of Paramedicine", 0.05),
    ("BBUSI", "Bachelor of Business Administration", 0.09),
    ("BINFT", "Bachelor of Information Technology", 0.06),
    ("BLAWS", "Bachelor of Laws", 0.05),
    ("BARTS", "Bachelor of Arts", 0.03),
]
UNITS_PER_LEVEL = 8       # catalogue units per program per year level
FT_UNITS = 4              # units per term full-time
PT_UNITS = 2
UNIT_EFTSL = 0.125
PROGRAM_UNITS_TO_COMPLETE = 24   # 3-year degrees; simplification noted in docs

# ---------------------------------------------------------- demography ----
P_INTERNATIONAL = 0.11
P_FEMALE = 0.66
P_GENDER_X = 0.015
P_PART_TIME = 0.20            # on-campus
P_PART_TIME_ONLINE = 0.52
AGE_MIX = {"<=19": 0.60, "20-24": 0.19, "25+": 0.21}   # online skews mature in code

# Equity incidence (domestic students; conditional adjustments in code)
P_FIRST_NATIONS = 0.032
P_DISABILITY = 0.095
P_NESB = 0.09
P_REGIONAL_BASE = 0.11
P_LOW_SES_BASE = 0.15
P_FIRST_IN_FAMILY = 0.28

# --------------------------------------------------- latent risk model ----
# engagement_base = ENG_INTERCEPT + ENG_ABILITY*ability - ENG_NEED*need + noise
ENG_INTERCEPT = 0.40
ENG_ABILITY = 0.35
ENG_NEED = 0.36
ENG_NOISE_SD = 0.65
AR_RHO = 0.70             # week-to-week engagement autocorrelation
AR_SD = 0.32
CLIFF_BASE = -2.55        # logit of "disengagement cliff" probability
CLIFF_NEED = 0.85
CLIFF_DROP = 1.80         # engagement drop when a cliff happens

SUPPORT_NEED_WEIGHTS = {
    "low_ses": 0.35, "first_nations": 0.55, "disability": 0.26,
    "regional": 0.22, "nesb": 0.18, "first_in_family": 0.16,
    "part_time": 0.28, "online": 0.34, "first_year": 0.34,
}

# ----------------------------------------------------- marks and grades ----
MARK_INTERCEPT = 65.5
MARK_ENGAGE = 11.0
MARK_ABILITY = 7.0
MARK_SD = 7.5
ONTIME_INTERCEPT = 1.25   # logit intercept of on-time submission probability

# ----------------------------------------------------------- retention ----
# Term-to-term persistence logit; calibrated so year-over-year retention lands
# near published rates (overall ~88-90%, equity gaps a few points, online lower).
RET_INTERCEPT = 4.05
RET_ENGAGE = 0.80
RET_PASS = 0.60
RET_FIRST_YEAR = -0.55
RET_NEED = -0.34
RET_ONLINE = -0.34
RET_INTL = 0.25

# ------------------------------------------------------- withdrawals ----
WITHDRAW_PRE_MEANE = -1.75    # mean engagement below this at census => candidate
WITHDRAW_PRE_P = 0.55
WITHDRAW_POST_E = -1.85
WITHDRAW_POST_P = 0.30

# -------------------------------------------------- alerts and outreach ----
ALERT_START_WEEK = 3
ALERT_END_WEEK = 11
INACTIVITY_LOGINS_2WK = 2      # rolling two-week login total at or below this
NON_SUBMISSION_MISSED = 3      # cumulative missed assessment items
ONTIME_RATE_FLOOR = 0.40       # by week >= 6 with >= 3 items due
# Advisors triage worst-first on OBSERVABLE severity: how many alert reasons
# fired together, and whether the student is currently inactive. This
# deliberately CONFOUNDS naive contacted-vs-uncontacted comparisons — but
# because the triage inputs are observable in the warehouse, a matched
# comparison on those same variables can remove the bias. (If triage keyed on
# unobservables, no evaluation design short of an RCT could recover truth.)
P_CONTACT_BASE = 0.35
P_CONTACT_PER_REASON = 0.22    # added per simultaneous alert reason beyond the first
P_CONTACT_LOWLOGIN = 0.18      # added when rolling 2-week logins <= threshold
P_CONTACT_MIN, P_CONTACT_MAX = 0.15, 0.92
CONTACT_LAG_DAYS = (2, 7)
P_REACHED = 0.70               # of contacted: successful conversation
P_VOICEMAIL = 0.20
# Injected ground-truth intervention effect (recovered later by the
# matched-comparison evaluation — this is the validation of the evaluator):
P_EFFECT_IF_REACHED = 0.65
EFFECT_ENGAGE_UPLIFT = 0.65    # added to engagement base from contact week
EFFECT_RETENTION_LOGIT = 0.80  # added to persistence logit in that term

P_SELF_REFERRAL = 0.045        # non-alert cases per active student-term

# ------------------------------------------------------------- defects ----
DEFECT_RATES = {
    "duplicate_student": 0.003,
    "missing_equity_flag": 0.030,
    "campus_code_variant": 0.020,
    "mark_out_of_range": 0.002,
    "name_whitespace_case": 0.010,
    "dob_format_dmy": 0.015,
}

# --------------------------------------------------------------- SEHEEF ----
# Simplified SEHEEF program-logic tags: (activity_type, student_life_stage)
SEHEEF_BY_CASE_TYPE = {
    "Early intervention outreach": ("Outreach and engagement", "Participation"),
    "Academic recovery support": ("Academic support", "Participation"),
    "Progression advising": ("Progression advising", "Attainment"),
    "Financial hardship support": ("Financial support", "Participation"),
    "Wellbeing referral": ("Wellbeing support", "Participation"),
    "Disability support plan": ("Inclusive support", "Participation"),
    "Peer mentoring referral": ("Peer mentoring", "Transition in"),
}

ADVISORS = [
    ("ADV01", "Mia Trần", ["NSY", "STR"]),
    ("ADV02", "Daniel Okafor", ["NSY", "BLK"]),
    ("ADV03", "Grace Kelleher", ["STR", "BLK"]),
    ("ADV04", "Hannah Kovač", ["MEL"]),
    ("ADV05", "Liam O'Callaghan", ["MEL", "BAL"]),
    ("ADV06", "Priya Raman", ["MEL", "BAL"]),
    ("ADV07", "Sofia Marino", ["BRI"]),
    ("ADV08", "Jacob Ngata", ["BRI", "CAN"]),
    ("ADV09", "Amira Haddad", ["ONL"]),
    ("ADV10", "Tom Beaumont", ["ONL"]),
]

FIRST_NAMES = [
    "Olivia", "Noah", "Amelia", "Jack", "Isla", "William", "Mia", "Leo",
    "Grace", "Lucas", "Chloe", "Ethan", "Sofia", "Mason", "Aisha", "Omar",
    "Mei", "Hiro", "Anh", "Minh", "Priya", "Arjun", "Fatima", "Hassan",
    "Kirra", "Jarrah", "Talia", "Xavier", "Ruby", "Patrick", "Siobhan",
    "Declan", "Elena", "Marco", "Ana", "Diego", "Zoe", "Samuel", "Hana",
    "David", "Sarah", "Daniel", "Leilani", "Kai", "Ingrid", "Stefan",
]
LAST_NAMES = [
    "Smith", "Nguyen", "Chen", "Singh", "Williams", "Tran", "Kelly",
    "Martin", "Lee", "Wilson", "Taylor", "Kumar", "Brown", "Pham",
    "O'Brien", "Jones", "Garcia", "Silva", "Rossi", "Ferrari", "Ali",
    "Hassan", "Ivanov", "Novak", "Kowalski", "Andersen", "Larsen",
    "Yamamoto", "Kim", "Park", "Santos", "Reyes", "Mabo", "Anderson",
    "Thompson", "White", "Walker", "Harris", "Robinson", "Clarke",
    "Mitchell", "Carter", "Bennett", "Murphy", "Cooper", "Fitzgerald",
]

# Synthetic postcode reference: 80 postcodes, each with an SES (IEO-style)
# quartile and a remoteness class, generated deterministically in code.
N_POSTCODES_PER_STATE = 20
