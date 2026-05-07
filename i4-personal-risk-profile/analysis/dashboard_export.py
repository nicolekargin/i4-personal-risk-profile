"""
Dashboard export — single source of truth for the Health Orbit dashboard.

Produces:
  dashboard_findings.csv    — one row per (measurement × peak_timepoint),
                               filtered to rank_within_layer ≤ 25 per layer,
                               plus any headline rows meeting the criteria.
  headline_trajectories.csv — time-series trajectories for top-N measurements

dashboard_findings.csv schema:
  rank_overall, rank_within_layer,
  layer, measurement, measurement_label, site,
  archetype, literature_status,
  peak_timepoint, days_from_launch,
  peak_abs_z, peak_z_ci_lower_abs, peak_z_ci_high,
  z_score_robust (at peak TP),
  methods_concordance (at peak TP),
  is_baseline_fragile (at peak TP),
  fragility_reason (at peak TP),
  concordance_class,
  signal_score,
  clinical_flagged_count,
  deviation_flag (at peak TP),
  deviation_direction (at peak TP),
  fold_change (at peak TP),
  recovery_classification,
  return_to_baseline_day,
  recovery_velocity,
  display_priority,         NEW: headline | primary | secondary | context
  dashboard_card_template,  NEW: magnitude_card | trajectory_card | comparison_card | context_card
  one_line_takeaway         NEW: ≤120-char human-readable summary

headline_trajectories.csv schema:
  rank_overall, layer, measurement, measurement_label, site,
  timepoint, days_from_launch, phase,
  value_raw, value_transformed,
  z_score, z_score_ci_low, z_score_ci_high,
  z_score_robust,
  deviation_flag, deviation_direction,
  fold_change

Microbial peak |z| cap (Fix 1):
  Microbial rows with |peak_abs_z| > 50 OR |z_score_robust| > 50 are dropped
  before ranking. These reflect mathematical extremes from baseline fragility
  on rare bacterial functions and are not biologically interpretable.
  Rows are re-ranked after this filter is applied.

Microbial archetype categorization (Fix 3):
  KEGG KO number ranges map to broad functional buckets for dashboard grouping.
  See assign_microbial_archetype() for the mapping. This is a rough first-order
  categorization, not a BRITE hierarchy assignment — see PIPELINE.md.
"""
import logging
import re

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FOCAL = "C003"
_TOP_N_TRAJECTORIES = 20

# Fix 1: microbial |z| cap — values above this are baseline-fragility artefacts
_MICROBIAL_Z_CAP = 50.0

# Fix 2: literature statuses that qualify a finding as "headline"
_HEADLINE_LIT = {"confirmed", "established", "reported"}

_TIMEPOINT_LABELS: dict[str, str] = {
    "R+1":   "one day post-flight",
    "R+45":  "45 days post-flight",
    "R+82":  "82 days post-flight",
    "R+194": "194 days post-flight",
    "FD2":   "flight day 2",
    "FD3":   "flight day 3",
    "FD15":  "flight day 15",
    "FD45":  "flight day 45",
    "FD90":  "flight day 90",
}

_SITE_LABELS: dict[str, str] = {
    "ORC": "Oral cavity",
    "NAC": "Nasal cavity",
}


# ── Fix 3: microbial archetype by KEGG prefix ──────────────────────────────────

def assign_microbial_archetype(ko_id: str) -> str:
    """
    Map a KEGG KO identifier to a broad functional category bucket for dashboard
    grouping.  Ranges follow the rough numeric banding of KEGG KO numbers:

      K00000–K02999 → metabolism_central
      K03000–K05999 → genetic_information_processing
      K06000–K09999 → membrane_transport
      K10000–K12999 → signaling_and_cellular_processes
      K13000–K20999 → metabolism_secondary
      K21000+        → uncategorized_or_novel

    This is a coarse first-order grouping, not a BRITE hierarchy assignment.
    It enables dashboard faceting and should not be cited as a precise
    functional annotation.  See PIPELINE.md for rationale and caveats.
    """
    m = re.match(r"K(\d+)", str(ko_id).strip().upper())
    if m is None:
        return "uncategorized_or_novel"
    n = int(m.group(1))
    if n <= 2999:
        return "metabolism_central"
    if n <= 5999:
        return "genetic_information_processing"
    if n <= 9999:
        return "membrane_transport"
    if n <= 12999:
        return "signaling_and_cellular_processes"
    if n <= 20999:
        return "metabolism_secondary"
    return "uncategorized_or_novel"


# ── Fix 2: display helpers ─────────────────────────────────────────────────────

def _fmt_fold_change(fc) -> str | None:
    """Format fold_change as a human-readable label. Returns None if unusable."""
    try:
        fc = float(fc)
    except (TypeError, ValueError):
        return None
    if np.isnan(fc) or fc <= 0:
        return None
    if fc > 1.0:
        return f"{fc:.1f}-fold above baseline"
    return f"to {fc:.1f}× of baseline"


def _fmt_timepoint(tp: str) -> str:
    """Convert a timepoint code to a human-readable label."""
    if tp in _TIMEPOINT_LABELS:
        return _TIMEPOINT_LABELS[tp]
    m = re.match(r"R\+(\d+)", str(tp))
    if m:
        return f"{m.group(1)} days post-flight"
    m = re.match(r"FD(\d+)", str(tp))
    if m:
        return f"flight day {m.group(1)}"
    return str(tp)


def _generate_one_line_takeaway(row: pd.Series) -> str:
    """
    Generate a ≤120-char human-readable takeaway sentence for a dashboard row.
    No z-score or SD jargon — statistical details go in tooltips.
    Uses template selection by layer, display_priority, concordance_class,
    archetype membership, clinical_flag, literature_status, and direction.
    Falls back to a generic template when any required field is missing or NaN.
    """
    label         = str(row.get("measurement_label") or row.get("measurement") or "This marker")
    tp_label      = _fmt_timepoint(str(row.get("peak_timepoint", "")))
    layer         = str(row.get("layer", ""))
    conc_class    = str(row.get("concordance_class", ""))
    archetype     = str(row.get("archetype", ""))
    lit_status    = str(row.get("literature_status", ""))
    direction     = str(row.get("deviation_direction", ""))
    clinical_flag = str(row.get("_clinical_flag", ""))
    recovery      = str(row.get("recovery_classification", ""))
    site          = str(row.get("site", ""))
    dp            = str(row.get("display_priority", ""))
    fc_label      = _fmt_fold_change(row.get("fold_change"))

    site_label      = _SITE_LABELS.get(site, "")
    site_prefix     = f"{site_label} " if site_label else ""
    recovery_status = recovery if recovery and recovery != "nan" else "unknown"

    if layer == "immune":
        if dp == "headline" and conc_class == "concordant" and "acute_phase_response" in archetype:
            if fc_label:
                txt = f"{label} surged {fc_label} at {tp_label}, the cohort's shared inflammatory signal."
            else:
                txt = f"{label} surged at {tp_label}, the cohort's shared inflammatory signal."
        elif dp == "primary" and conc_class == "idiosyncratic":
            txt = f"{label} elevated sharply for C003 at {tp_label}, while the rest of the crew remained stable."
        elif dp == "primary" and conc_class == "concordant":
            if fc_label:
                txt = f"{label} rose {fc_label} at {tp_label}, mirroring the cohort's response."
            else:
                txt = f"{label} rose at {tp_label}, mirroring the cohort's response."
        elif conc_class == "concordant":
            txt = f"{label} rose at {tp_label}, consistent with the cohort's direction."
        elif conc_class == "discordant":
            txt = f"{label} moved opposite to the cohort at {tp_label}."
        else:
            txt = f"{label} shifted at {tp_label}."

    elif layer == "clinical":
        if lit_status == "contradicted":
            txt = f"{label} moved opposite to typical spaceflight expectations at {tp_label}."
        elif clinical_flag == "above-range":
            txt = f"{label} elevated above the clinical reference range at {tp_label}."
        elif clinical_flag == "below-range":
            txt = f"{label} fell below the clinical reference range at {tp_label}."
        elif clinical_flag == "in-range":
            if direction == "up":
                txt = (
                    f"{label} rose well above C003's personal baseline at {tp_label}, "
                    "while staying within the clinical normal range."
                )
            else:
                txt = (
                    f"{label} dropped well below C003's personal baseline at {tp_label}, "
                    "while staying within the clinical normal range."
                )
        else:
            txt = f"{label} deviated from personal baseline at {tp_label}."

    elif layer == "microbial":
        txt = f"{site_prefix}{label} shifted at {tp_label}; recovery {recovery_status}."

    else:
        txt = f"{label} deviated from personal baseline at {tp_label}."

    # Hard cap at 120 chars; truncate cleanly at the last word boundary
    if len(txt) > 120:
        txt = txt[:117].rsplit(" ", 1)[0] + "…"
    return txt


# ── Fix 1: microbial cap + re-rank ────────────────────────────────────────────

def _apply_microbial_cap(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Drop microbial rows where |peak_abs_z| > _MICROBIAL_Z_CAP or
    |z_score_robust| > _MICROBIAL_Z_CAP, then recompute rank_within_layer
    and rank_overall for all layers.

    Returns (filtered_df, {layer: n_dropped}).
    """
    is_microbial = df["layer"] == "microbial"

    z_robust_abs = df["z_score_robust"].abs().fillna(0)
    peak_z_abs   = df["peak_abs_z"].abs().fillna(0)

    over_cap = is_microbial & ((peak_z_abs > _MICROBIAL_Z_CAP) | (z_robust_abs > _MICROBIAL_Z_CAP))

    drop_counts: dict[str, int] = {}
    for layer in df["layer"].unique():
        drop_counts[layer] = int((over_cap & (df["layer"] == layer)).sum())

    n_dropped = int(over_cap.sum())
    log.info(
        "microbial |z| cap (%.0f): dropped %d rows — %s",
        _MICROBIAL_Z_CAP, n_dropped, drop_counts,
    )

    df = df[~over_cap].copy()

    # Re-rank within each layer by signal_score descending
    df = df.sort_values(["layer", "signal_score"], ascending=[True, False])
    df["rank_within_layer"] = df.groupby("layer").cumcount() + 1

    # Re-rank overall by signal_score descending
    df = df.sort_values("signal_score", ascending=False).reset_index(drop=True)
    df["rank_overall"] = range(1, len(df) + 1)

    return df, drop_counts


# ── Fix 2: display_priority, dashboard_card_template, one_line_takeaway ──────

def _assign_display_priority(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign display_priority using first-match-wins rules.
    Rows that match no rule are left with NaN and will be filtered out.
    """
    df = df.copy()
    df["display_priority"] = pd.NA

    # headline: robust |z| ≥ 5, concordant, confirmed lit, immune or clinical
    headline_mask = (
        df["z_score_robust"].abs().fillna(0).ge(5.0)
        & df["concordance_class"].eq("concordant")
        & df["literature_status"].isin(_HEADLINE_LIT)
        & df["layer"].isin({"immune", "clinical"})
    )
    df.loc[headline_mask, "display_priority"] = "headline"

    # primary: rank ≤ 5, not already headline
    primary_mask = df["rank_within_layer"].le(5) & df["display_priority"].isna()
    df.loc[primary_mask, "display_priority"] = "primary"

    # secondary: rank 6-15
    secondary_mask = df["rank_within_layer"].between(6, 15) & df["display_priority"].isna()
    df.loc[secondary_mask, "display_priority"] = "secondary"

    # context: rank 16-25
    context_mask = df["rank_within_layer"].between(16, 25) & df["display_priority"].isna()
    df.loc[context_mask, "display_priority"] = "context"

    n_headline  = headline_mask.sum()
    n_total_in  = len(df)
    n_total_out = df["display_priority"].notna().sum()
    log.info(
        "display_priority: %d headline, %d total assigned (of %d); %d rows excluded",
        n_headline, n_total_out, n_total_in, n_total_in - n_total_out,
    )
    return df


def _assign_card_template(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign dashboard_card_template.  Requires display_priority and
    _n_post_flight (internal column) to already be set.
    """
    df = df.copy()
    df["dashboard_card_template"] = "context_card"

    # magnitude_card: headline rows
    df.loc[df["display_priority"] == "headline", "dashboard_card_template"] = "magnitude_card"

    # trajectory_card: primary + ≥3 post-flight timepoints with valid z_score_robust
    trajectory_mask = (
        df["display_priority"].eq("primary")
        & df["_n_post_flight"].ge(3)
    )
    df.loc[trajectory_mask, "dashboard_card_template"] = "trajectory_card"

    # comparison_card: primary + concordant/idiosyncratic + not trajectory
    comparison_mask = (
        df["display_priority"].eq("primary")
        & df["concordance_class"].isin({"concordant", "idiosyncratic"})
        & df["dashboard_card_template"].ne("trajectory_card")
    )
    df.loc[comparison_mask, "dashboard_card_template"] = "comparison_card"

    return df


# ── Internal helpers ───────────────────────────────────────────────────────────

def _pick_peak_row(
    profile: pd.DataFrame,
    layer: str,
    measurement: str,
    site,
    peak_tp: str,
) -> pd.Series | None:
    """Return the profile row for (layer, measurement, site, peak_tp) for C003."""
    mask = (
        (profile["crew_id"] == FOCAL)
        & (profile["layer"] == layer)
        & (profile["measurement"] == measurement)
        & (profile["timepoint"] == peak_tp)
    )
    if site is None or (isinstance(site, float) and np.isnan(site)):
        mask &= profile["site"].isna()
    else:
        mask &= profile["site"] == site

    rows = profile[mask]
    return rows.iloc[0] if not rows.empty else None


# ── Public API ─────────────────────────────────────────────────────────────────

def build_dashboard_findings(
    narrative: pd.DataFrame,
    profile: pd.DataFrame,
    kinetics: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join narrative ranking with verify.py columns, kinetics, archetype, and
    literature; apply the microbial |z| cap; add display_priority,
    dashboard_card_template, and one_line_takeaway; filter to displayable rows.
    """
    records = []

    for _, nr in narrative.iterrows():
        layer       = nr["layer"]
        measurement = nr["measurement"]
        site        = nr.get("site", None)
        peak_tp     = nr["peak_timepoint"]

        peak_row = _pick_peak_row(profile, layer, measurement, site, peak_tp)
        if peak_row is None:
            log.debug("dashboard: no profile row for %s / %s / %s @ %s",
                      layer, measurement, site, peak_tp)
            peak_row = pd.Series(dtype=object)

        def _get(col, default=np.nan):
            return peak_row.get(col, default) if not peak_row.empty else default

        days = _get("days_from_launch")
        if isinstance(days, float) and np.isnan(days):
            from .parse import DAYS_FROM_LAUNCH
            days = DAYS_FROM_LAUNCH.get(peak_tp, np.nan)

        kin_mask = (
            (kinetics["layer"] == layer)
            & (kinetics["measurement"] == measurement)
        )
        if site is None or (isinstance(site, float) and np.isnan(site)):
            kin_mask &= kinetics["site"].isna()
        else:
            kin_mask &= kinetics["site"] == site
        kin_rows = kinetics[kin_mask]
        kin = kin_rows.iloc[0] if not kin_rows.empty else pd.Series(dtype=object)

        def _kget(col, default=np.nan):
            return kin.get(col, default) if not kin.empty else default

        records.append({
            "rank_overall":           int(nr["rank_overall"]),
            "rank_within_layer":      int(nr["rank_within_layer"]),
            "layer":                  layer,
            "measurement":            measurement,
            "measurement_label":      nr.get("measurement_label", measurement),
            "site":                   site,
            "archetype":              _get("archetype", ""),
            "literature_status":      _get("literature_status", "not_applicable"),
            "peak_timepoint":         peak_tp,
            "days_from_launch":       days,
            "peak_abs_z":             nr.get("peak_abs_z", np.nan),
            "peak_z_ci_lower_abs":    nr.get("peak_z_ci_lower_abs", np.nan),
            "peak_z_ci_high":         _get("z_score_ci_high"),
            "z_score_robust":         _get("z_score_robust"),
            "methods_concordance":    _get("methods_concordance", "unknown"),
            "is_baseline_fragile":    _get("is_baseline_fragile", False),
            "fragility_reason":       _get("fragility_reason", ""),
            "concordance_class":      nr.get("concordance_class", "ambiguous"),
            "signal_score":           nr.get("signal_score", np.nan),
            "clinical_flagged_count": nr.get("clinical_flagged_count", 0),
            "deviation_flag":         _get("deviation_flag", "stable"),
            "deviation_direction":    _get("deviation_direction", None),
            "fold_change":            _get("fold_change"),
            "recovery_classification":_kget("recovery_classification"),
            "return_to_baseline_day": _kget("return_to_baseline_day"),
            "recovery_velocity":      _kget("recovery_velocity"),
            # internal columns — used for card template and takeaway, then dropped
            "_clinical_flag":         _get("clinical_flag", "in-range"),
            "_n_post_flight":         int(_kget("n_post_flight_points", 0)),
        })

    df = pd.DataFrame(records)
    log.info("dashboard_findings (pre-cap): %d rows", len(df))

    # ── Fix 1: microbial |z| cap + re-rank ────────────────────────────────────
    # Rows dropped per layer are logged above inside _apply_microbial_cap.
    # After dropping, rank_within_layer and rank_overall are recomputed from
    # signal_score so that the rank sequence is contiguous within each layer.
    # Dropped row counts (microbial only, other layers = 0):
    #   Run 2026-05-07: microbial dropped ~4860 of 4906 rows above |z|=50 cap.
    df, _drop_counts = _apply_microbial_cap(df)
    log.info("dashboard_findings (post-cap): %d rows", len(df))

    # ── Fix 3: microbial archetype by KEGG KO prefix ─────────────────────────
    microbial_mask = df["layer"] == "microbial"
    df.loc[microbial_mask, "archetype"] = (
        df.loc[microbial_mask, "measurement"].apply(assign_microbial_archetype)
    )

    # ── Fix 2a: display_priority ───────────────────────────────────────────────
    df = _assign_display_priority(df)

    # Filter: only rows with an assigned display_priority
    df = df[df["display_priority"].notna()].copy()
    log.info("dashboard_findings (post-priority-filter): %d rows", len(df))

    # ── Fix 2b: dashboard_card_template ───────────────────────────────────────
    df = _assign_card_template(df)

    # ── Fix 2c: one_line_takeaway ──────────────────────────────────────────────
    df["one_line_takeaway"] = df.apply(_generate_one_line_takeaway, axis=1)

    # Drop internal columns
    df = df.drop(columns=["_clinical_flag", "_n_post_flight"])

    log.info("dashboard_findings final: %d rows, %d cols", len(df), df.shape[1])
    return df


def build_headline_trajectories(
    narrative: pd.DataFrame,
    profile: pd.DataFrame,
    top_n: int = _TOP_N_TRAJECTORIES,
) -> pd.DataFrame:
    """
    For the top-N measurements by signal_score, extract full time-series rows
    from the profile for C003.  Applies the microbial |z| cap to the narrative
    before selecting top-N so that the trajectory set is consistent with
    dashboard_findings.
    """
    # Apply the same microbial cap to the narrative so top-N reflects capped ranks
    is_microbial = narrative["layer"] == "microbial"
    robust_col = (
        "z_score_robust_at_peak"
        if "z_score_robust_at_peak" in narrative.columns
        else "z_score_robust"
    )
    over_cap = is_microbial & (
        (narrative["peak_abs_z"].abs() > _MICROBIAL_Z_CAP)
        | (narrative[robust_col].abs().fillna(0) > _MICROBIAL_Z_CAP)
    )
    narrative_capped = narrative[~over_cap].copy()

    top = narrative_capped.sort_values("signal_score", ascending=False).head(top_n)

    trajectory_cols = [
        "rank_overall", "layer", "measurement", "measurement_label", "site",
        "timepoint", "days_from_launch", "phase",
        "value_raw", "value_transformed",
        "z_score", "z_score_ci_low", "z_score_ci_high",
        "z_score_robust",
        "deviation_flag", "deviation_direction",
        "fold_change",
    ]

    records = []
    focal_profile = profile[profile["crew_id"] == FOCAL].copy()

    for _, nr in top.iterrows():
        layer       = nr["layer"]
        measurement = nr["measurement"]
        site        = nr.get("site", None)
        rank        = int(nr["rank_overall"])
        label       = nr.get("measurement_label", measurement)

        mask = (
            (focal_profile["layer"] == layer)
            & (focal_profile["measurement"] == measurement)
        )
        if site is None or (isinstance(site, float) and np.isnan(site)):
            mask &= focal_profile["site"].isna()
        else:
            mask &= focal_profile["site"] == site

        rows = focal_profile[mask].copy()
        rows["rank_overall"] = rank
        rows["measurement_label"] = label

        for col in trajectory_cols:
            if col not in rows.columns:
                rows[col] = np.nan

        records.append(rows[trajectory_cols])

    if not records:
        return pd.DataFrame(columns=trajectory_cols)

    df = pd.concat(records, ignore_index=True)
    df = df.sort_values(["rank_overall", "days_from_launch"]).reset_index(drop=True)
    log.info("headline_trajectories: %d rows for top-%d measurements", len(df), top_n)
    return df
