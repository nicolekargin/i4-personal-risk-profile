"""
Dashboard export — single source of truth for the Health Orbit dashboard.

Produces:
  dashboard_findings.csv    — one row per (measurement × peak_timepoint)
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
  recovery_velocity

headline_trajectories.csv schema:
  rank_overall, layer, measurement, measurement_label, site,
  timepoint, days_from_launch, phase,
  value_raw, value_transformed,
  z_score, z_score_ci_low, z_score_ci_high,
  z_score_robust,
  deviation_flag, deviation_direction,
  fold_change
"""
import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FOCAL = "C003"
_TOP_N_TRAJECTORIES = 20   # top-N by signal_score get trajectory rows


def _pick_peak_row(
    profile: pd.DataFrame,
    layer: str,
    measurement: str,
    site,
    peak_tp: str,
) -> pd.Series | None:
    """Return the profile row matching (layer, measurement, site, peak_tp) for C003."""
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


def build_dashboard_findings(
    narrative: pd.DataFrame,
    profile: pd.DataFrame,
    kinetics: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join narrative ranking with verify.py columns, kinetics, and archetype/literature.
    """
    records = []

    for _, nr in narrative.iterrows():
        layer      = nr["layer"]
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
            # Fall back to DAYS_FROM_LAUNCH mapping
            from .parse import DAYS_FROM_LAUNCH
            days = DAYS_FROM_LAUNCH.get(peak_tp, np.nan)

        # kinetics lookup
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
        })

    df = pd.DataFrame(records)
    log.info("dashboard_findings: %d rows", len(df))
    return df


def build_headline_trajectories(
    narrative: pd.DataFrame,
    profile: pd.DataFrame,
    top_n: int = _TOP_N_TRAJECTORIES,
) -> pd.DataFrame:
    """
    For the top-N measurements by signal_score, extract full time-series rows
    from the profile for C003.
    """
    top = narrative.head(top_n)

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
