"""
Regex-based sample name parsers — one per dataset.
Each parser returns a tidy long-format DataFrame ready for transform.py.
No value transformation happens here.
"""
import logging
import re
import warnings

import pandas as pd

log = logging.getLogger(__name__)

# ── canonical timepoint → days mapping ────────────────────────────────────────
DAYS_FROM_LAUNCH: dict[str, int] = {
    "L-92": -92,
    "L-44": -44,
    "L-3":  -3,
    "FD1":   1,
    "FD2":   2,
    "FD3":   3,
    "R+1":   1,
    "R+45":  45,
    "R+82":  82,
    "R+194": 194,
}

BASELINE_TPS = {"L-92", "L-44", "L-3"}

_CBC_ANALYTE_RENAME: dict[str, str] = {
    # (FEMALE) variants: keep as-is — they apply to female crew only.
}


def _tp_to_phase(tp: str) -> str:
    if tp in BASELINE_TPS:
        return "pre-flight"
    if tp.startswith("FD"):
        return "in-flight"
    return "post-flight"


def _analyte_to_machine_id(name: str) -> str:
    """Human-readable analyte name → snake_case machine ID."""
    name = (name
            .replace("α", "alpha")
            .replace("β", "beta")
            .replace("γ", "gamma")
            .replace("δ", "delta"))
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    return name


# ── CBC ───────────────────────────────────────────────────────────────────────

def parse_cbc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: raw CBC DataFrame (index=ANALYTE, SUBJECT_ID + TEST_DATE columns).
    Output: long DataFrame with standardised columns.
    """
    df = df.reset_index()  # ANALYTE becomes a column
    df = df.rename(columns={
        "ANALYTE":    "measurement_label",
        "VALUE":      "value_raw",
        "RANGE_MIN":  "clinical_min",
        "RANGE_MAX":  "clinical_max",
        "UNITS":      "unit",
        "SUBJECT_ID": "crew_id",
        "TEST_DATE":  "timepoint",
    })

    # reject rows with unrecognised crew or timepoint
    valid_crew = {"C001", "C002", "C003", "C004"}
    n_before = len(df)
    bad_crew = ~df["crew_id"].isin(valid_crew)
    bad_tp   = ~df["timepoint"].isin(DAYS_FROM_LAUNCH)
    if bad_crew.any():
        log.warning("CBC: dropping %d rows with unrecognised crew_id: %s",
                    bad_crew.sum(), df.loc[bad_crew, "crew_id"].unique().tolist())
    if bad_tp.any():
        log.warning("CBC: dropping %d rows with unrecognised timepoint: %s",
                    bad_tp.sum(), df.loc[bad_tp, "timepoint"].unique().tolist())
    df = df[~bad_crew & ~bad_tp].copy()
    log.info("CBC parse: %d → %d rows (dropped %d)", n_before, len(df), n_before - len(df))

    df["measurement"] = df["measurement_label"].map(_analyte_to_machine_id)
    df["days_from_launch"] = df["timepoint"].map(DAYS_FROM_LAUNCH)
    df["phase"] = df["timepoint"].map(_tp_to_phase)
    df["is_baseline_timepoint"] = df["timepoint"].isin(BASELINE_TPS)
    df["layer"] = "clinical"
    df["site"] = float("nan")
    df["value_raw"] = pd.to_numeric(df["value_raw"], errors="coerce")
    df["clinical_min"] = pd.to_numeric(df["clinical_min"], errors="coerce")
    df["clinical_max"] = pd.to_numeric(df["clinical_max"], errors="coerce")

    cols = ["crew_id", "timepoint", "days_from_launch", "phase", "layer", "site",
            "measurement", "measurement_label", "value_raw", "unit",
            "clinical_min", "clinical_max", "is_baseline_timepoint"]
    return df[cols].reset_index(drop=True)


# ── Cytokines (Eve panel, SUBMITTED format) ────────────────────────────────────

_CYTO_SAMPLE_RE = re.compile(r"^(C00[1-4])_serum_(L-\d+|R\+\d+)$")


def parse_cytokines(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: raw Eve cytokine SUBMITTED DataFrame.
    Drops *_percent rows (we compute our own baseline).
    Output: long DataFrame with standardised columns.
    """
    # Construct synthetic sample ID to validate format
    df = df.copy()
    df["sample_id"] = df["ID"].astype(str) + "_serum_" + df["Timepoint"].astype(str)

    n_before = len(df)
    bad_match = ~df["sample_id"].str.match(_CYTO_SAMPLE_RE)
    if bad_match.any():
        log.warning("Cytokines: dropping %d rows with unrecognised sample pattern: %s",
                    bad_match.sum(),
                    df.loc[bad_match, "sample_id"].unique()[:10].tolist())
    df = df[~bad_match].copy()

    # rename
    df = df.rename(columns={
        "ID":            "crew_id",
        "Timepoint":     "timepoint",
        "Analyte":       "measurement_label",
        "Concentration": "value_raw",
        "Unit":          "unit",
    })

    df["measurement"] = df["measurement_label"].map(_analyte_to_machine_id)
    df["days_from_launch"] = df["timepoint"].map(DAYS_FROM_LAUNCH)
    df["phase"] = df["timepoint"].map(_tp_to_phase)
    df["is_baseline_timepoint"] = df["timepoint"].isin(BASELINE_TPS)
    df["layer"] = "immune"
    df["site"] = float("nan")
    df["clinical_min"] = float("nan")
    df["clinical_max"] = float("nan")
    df["value_raw"] = pd.to_numeric(df["value_raw"], errors="coerce")

    log.info("Cytokines parse: %d → %d rows (dropped %d percent/bad rows)",
             n_before, len(df), n_before - len(df))

    cols = ["crew_id", "timepoint", "days_from_launch", "phase", "layer", "site",
            "measurement", "measurement_label", "value_raw", "unit",
            "clinical_min", "clinical_max", "is_baseline_timepoint"]
    return df[cols].reset_index(drop=True)


# ── Metagenomics (KEGG KO, wide → long) ───────────────────────────────────────

_META_SAMPLE_RE = re.compile(r"^(C00[1-4])_(L-\d+|FD\d+|R\+\d+)_([A-Z]{3})$")
_PRIMARY_SITES = {"ORC", "NAC"}


def parse_metagenomics_ko(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: raw metagenomics TSV (index=KO_ID, first col=KO_function, rest=samples).
    Parses column names, rejects non-matching samples, filters to ORC+NAC sites.
    Output: long DataFrame, one row per (KO × sample).
    """
    ko_fn = df["KO_function"].copy()
    mat = df.drop(columns=["KO_function"])

    sample_cols = mat.columns.tolist()
    matched: list[str] = []
    rejected: list[str] = []
    for col in sample_cols:
        if _META_SAMPLE_RE.match(col):
            matched.append(col)
        else:
            rejected.append(col)

    if rejected:
        log.warning("Metagenomics: rejecting %d non-matching columns: %s",
                    len(rejected), rejected)

    mat = mat[matched]

    # Parse matched sample columns into metadata
    parsed = []
    for col in matched:
        m = _META_SAMPLE_RE.match(col)
        crew_id, tp, site = m.group(1), m.group(2), m.group(3)
        if site not in _PRIMARY_SITES:
            continue
        parsed.append({"col": col, "crew_id": crew_id, "timepoint": tp, "site": site})

    if not parsed:
        raise ValueError("No ORC/NAC samples found in metagenomics data.")

    keep_cols = [p["col"] for p in parsed]
    meta_df = pd.DataFrame(parsed).set_index("col")

    # melt: (n_KO × n_samples) → long
    sub = mat[keep_cols]
    sub.index.name = "measurement"  # KO_ID

    long = sub.stack().reset_index()
    long.columns = ["measurement", "col", "value_raw"]
    long = long.merge(meta_df.reset_index(), on="col")

    # attach human-readable label
    ko_fn_df = ko_fn.reset_index()
    ko_fn_df.columns = ["measurement", "measurement_label"]
    long = long.merge(ko_fn_df, on="measurement", how="left")

    long["days_from_launch"] = long["timepoint"].map(DAYS_FROM_LAUNCH)
    long["phase"] = long["timepoint"].map(_tp_to_phase)
    long["is_baseline_timepoint"] = long["timepoint"].isin(BASELINE_TPS)
    long["layer"] = "microbial"
    long["unit"] = "CPM"
    long["clinical_min"] = float("nan")
    long["clinical_max"] = float("nan")
    long["value_raw"] = pd.to_numeric(long["value_raw"], errors="coerce").fillna(0.0)

    log.info("Metagenomics parse: %d KOs × %d ORC/NAC samples = %d long rows",
             len(sub), len(keep_cols), len(long))

    cols = ["crew_id", "timepoint", "days_from_launch", "phase", "layer", "site",
            "measurement", "measurement_label", "value_raw", "unit",
            "clinical_min", "clinical_max", "is_baseline_timepoint"]
    return long[cols].reset_index(drop=True)
