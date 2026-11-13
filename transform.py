"""Transform step: clean raw NCVS records and split them into three tables.

Every cleaning task is its own function. Each takes a DataFrame (and an optional
``stats`` dict that collects counts for the ETL data-quality summary) and returns
a new DataFrame. See docs/ncvs_codebook.md for the reasoning behind each decision.

Entry point: ``transform(records)`` -> ``(tables, stats)`` where ``tables`` has
the keys ``respondents``, ``offense_types`` and ``victimizations``.
"""
import pandas as pd

# --------------------------------------------------------------------------
# Configuration (from the BJS codebook)
# --------------------------------------------------------------------------

RENAME_FIELDS = {":id": "victimization_id", ":updated_at": "updated_at"}

# Socrata system fields we do not keep (:id and :updated_at are renamed above).
DROP_SYSTEM_FIELDS = [":created_at", ":version"]

# Not documented in the codebook and not needed for the dashboard questions.
DROP_COLUMNS = ["pseudostratum", "secucode"]

# Codes that mean "no usable value" for each column -> NULL.
#   98          = "Residue" (respondent gave no usable answer)
#   -1 / -2     = "Invalid until <date>" (question did not exist yet)
# NOT listed on purpose:
#   veteran -1  = "Under age 18" is a real value, so only -2 and 98 are nulled.
#   "Do not know" codes (e.g. notify 3) are real answers and are kept.
NULL_CODES = {
    "hispanic": [98],
    "hincome1": [98],
    "hincome2": [-1],
    "marital": [98],
    "popsize": [-1],
    "region": [-1],
    "locality": [-1],
    "educatn1": [98],
    "educatn2": [-1, 98],
    "veteran": [-2, 98],
    "citizen": [-1, 98],
    "notify": [98],
    "vicservices": [98],
    "injury": [98],  # undocumented in the codebook but occurs in 4 rows
    "serious": [98],
    "treatment": [98],
    "offenderage": [98],
    "offendersex": [98],
    "offtracenew": [-1],
}

RESPONDENT_COLUMNS = [
    "idper", "yearq", "year", "ager", "sex", "hispanic", "race",
    "race_ethnicity", "hincome1", "hincome2", "marital", "popsize", "region",
    "msa", "locality", "educatn1", "educatn2", "veteran", "citizen",
]

VICTIMIZATION_COLUMNS = [
    "victimization_id", "idper", "yearq", "newoff", "notify", "vicservices",
    "locationr", "direl", "weapon", "weapcat", "injury", "serious",
    "treatment", "offenderage", "offendersex", "offtracenew", "wgtviccy",
    "series", "newwgt", "updated_at",
]

# Offense Types lookup (codebook: newoff, newcrime, seriousviolent).
OFFENSE_TYPES = [
    # newoff, newcrime, seriousviolent, offense_name
    (1, 1, 1, "Rape/sexual assault"),
    (2, 1, 1, "Robbery"),
    (3, 1, 1, "Aggravated assault"),
    (4, 1, 2, "Simple assault"),
    (5, 2, 3, "Personal theft/larceny"),
]

TEXT_COLUMNS = ["idper", "yearq", "victimization_id"]
FLOAT_COLUMNS = ["wgtviccy", "newwgt"]
# Everything else that holds a numeric code is stored as a small nullable integer.
CODE_COLUMNS = [
    c for c in RESPONDENT_COLUMNS + VICTIMIZATION_COLUMNS
    if c not in TEXT_COLUMNS + FLOAT_COLUMNS + ["updated_at"]
]
CODE_COLUMNS = list(dict.fromkeys(CODE_COLUMNS))  # de-duplicate, keep order


def _record(stats, section, key, value):
    """Add ``value`` to ``stats[section][key]`` when a stats dict is given."""
    if stats is not None:
        bucket = stats.setdefault(section, {})
        bucket[key] = bucket.get(key, 0) + int(value)


# --------------------------------------------------------------------------
# Cleaning functions (one task each)
# --------------------------------------------------------------------------

def rename_system_fields(df):
    """Rename Socrata ':id' / ':updated_at' to normal column names."""
    return df.rename(columns=RENAME_FIELDS)


def drop_unused_columns(df):
    """Drop Socrata fields and codebook-undocumented columns we do not use."""
    return df.drop(columns=DROP_SYSTEM_FIELDS + DROP_COLUMNS, errors="ignore")


def blank_strings_to_null(df, stats=None):
    """Strip whitespace from text values and turn empty strings into NULL.

    The Socrata API omits a key entirely when a value is null, so such rows
    arrive as NaN after the DataFrame is built. Those are counted together
    with empty strings as 'missing values found' for the summary."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col]):
            cleaned = out[col].astype("string").str.strip()
            missing = cleaned.isna() | (cleaned == "")
            _record(stats, "missing_found", col, missing.sum())
            out[col] = cleaned.mask(missing, pd.NA)
    return out


def convert_types(df):
    """Convert strings to proper types: codes -> nullable integers, weights ->
    floats, updated_at -> timestamp. ID-like columns (idper, yearq) stay text:
    idper is a 27-digit identifier and yearq is 'YYYY.Q'."""
    out = df.copy()
    for col in CODE_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int16")
    for col in FLOAT_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    if "updated_at" in out.columns:
        out["updated_at"] = pd.to_datetime(out["updated_at"], utc=True)
    for col in TEXT_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("string")
    return out


def remove_duplicate_records(df, stats=None):
    """Drop repeated records (same victimization_id), keeping the most recently
    updated copy. Rows that only *look* identical but have different ids are
    kept: they are plausibly separate incidents reported by one person."""
    before = len(df)
    out = (
        df.sort_values("updated_at", kind="stable")
        .drop_duplicates(subset="victimization_id", keep="last")
        .sort_index()
    )
    _record(stats, "duplicates_removed", "victimizations", before - len(out))
    return out


def fill_weapcat_from_weapon(df, stats=None):
    """If weapon == 2 ('No') and weapon category is missing, set weapcat = 0
    ('No weapon'). In the full data weapon == 2 is always paired with
    weapcat == 0, so this is a safe inference."""
    out = df.copy()
    mask = out["weapcat"].isna() & (out["weapon"] == 2)
    out.loc[mask, "weapcat"] = 0
    _record(stats, "filled", "weapcat", mask.sum())
    return out


def fill_treatment_from_injury(df, stats=None):
    """If injury == 0 ('Not injured') and treatment is missing, set treatment
    = 0 ('Not injured'). In the full data injury == 0 is always paired with
    treatment == 0."""
    out = df.copy()
    mask = out["treatment"].isna() & (out["injury"] == 0)
    out.loc[mask, "treatment"] = 0
    _record(stats, "filled", "treatment", mask.sum())
    return out


def replace_sentinel_codes(df, stats=None):
    """Replace 'no usable value' codes (98 residue, -1/-2 invalid-until) with
    NULL, using the per-column table NULL_CODES."""
    out = df.copy()
    for col, codes in NULL_CODES.items():
        if col in out.columns:
            mask = out[col].isin(codes)
            _record(stats, "sentinel_to_null", col, mask.sum())
            out.loc[mask, col] = pd.NA
    return out


# --------------------------------------------------------------------------
# Table builders
# --------------------------------------------------------------------------

def build_offense_types():
    """Static 5-row lookup table (primary key: newoff)."""
    df = pd.DataFrame(
        OFFENSE_TYPES,
        columns=["newoff", "newcrime", "seriousviolent", "offense_name"],
    )
    for col in ["newoff", "newcrime", "seriousviolent"]:
        df[col] = df[col].astype("Int16")
    return df


def build_respondents(df, stats=None):
    """One row per respondent-quarter (primary key: idper, yearq). A person
    with several victimizations appears many times in the flat data, so
    collapse to one row, keeping the most recently updated one."""
    before = len(df)
    out = (
        df.sort_values("updated_at", kind="stable")
        .drop_duplicates(subset=["idper", "yearq"], keep="last")
        [RESPONDENT_COLUMNS]
        .sort_values(["idper", "yearq"])
        .reset_index(drop=True)
    )
    _record(stats, "duplicates_removed", "respondents", before - len(out))
    return out


def build_victimizations(df):
    """One row per victimization (primary key: victimization_id)."""
    return df[VICTIMIZATION_COLUMNS].reset_index(drop=True)


# --------------------------------------------------------------------------
# Pipeline entry point
# --------------------------------------------------------------------------

def transform(records):
    """Clean raw API records. Returns (tables, stats).

    stats keys: received, after_cleaning, duplicates_removed{}, missing_found{},
    filled{}, sentinel_to_null{}, table_rows{}.
    """
    stats = {"received": len(records)}
    df = pd.DataFrame(records)
    if df.empty:
        stats["after_cleaning"] = 0
        empty = pd.DataFrame
        return {
            "respondents": empty(columns=RESPONDENT_COLUMNS),
            "offense_types": build_offense_types(),
            "victimizations": empty(columns=VICTIMIZATION_COLUMNS),
        }, stats

    df = rename_system_fields(df)
    df = drop_unused_columns(df)
    df = blank_strings_to_null(df, stats)
    df = convert_types(df)
    df = remove_duplicate_records(df, stats)
    df = fill_weapcat_from_weapon(df, stats)
    df = fill_treatment_from_injury(df, stats)
    df = replace_sentinel_codes(df, stats)

    tables = {
        "respondents": build_respondents(df, stats),
        "offense_types": build_offense_types(),
        "victimizations": build_victimizations(df),
    }
    stats["after_cleaning"] = len(df)
    stats["table_rows"] = {name: len(t) for name, t in tables.items()}
    return tables, stats


def format_summary(stats):
    """Human-readable lines for the ETL data-quality summary."""
    lines = [
        f"received from API: {stats['received']:,} rows",
        f"after cleaning: {stats['after_cleaning']:,} rows, "
        f"{stats.get('duplicates_removed', {}).get('victimizations', 0):,} "
        "duplicates removed",
    ]
    for label, key in [
        ("missing/blank values found (left NULL unless filled)", "missing_found"),
        ("filled by inference", "filled"),
        ("sentinel codes set to NULL", "sentinel_to_null"),
    ]:
        items = stats.get(key, {})
        if items:
            lines.append(f"{label}: " + ", ".join(f"{k} {v:,}" for k, v in items.items()))
        elif not stats["received"] and key == "missing_found":
            lines.append("missing values: no records to clean")
    for name, n in stats.get("table_rows", {}).items():
        lines.append(f"{name} rows ready to load: {n:,}")
    return lines
