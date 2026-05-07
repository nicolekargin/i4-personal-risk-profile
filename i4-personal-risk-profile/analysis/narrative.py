"""
Narrative ranking — composite signal-strength score for each measurement.

signal_score = peak_z_ci_lower_abs
               × (1 + 0.5 × clinical_flagged_count)
               × concordance_weight

concordance_weight: concordant=1.2, idiosyncratic=1.0, discordant=0.7, ambiguous=0.8

Ranking by peak_z_ci_lower_abs (lower-CI bound) rather than point z ensures
we surface measurements whose signal survives baseline uncertainty.
A measurement with z=4 but CI [0.5, 7] ranks below z=2.5 with CI [2.0, 3.1].
"""
import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FOCAL = "C003"

_CONCORDANCE_WEIGHTS = {
    "concordant":    1.2,
    "idiosyncratic": 1.0,
    "discordant":    0.7,
    "ambiguous":     0.8,
}

POST_FLIGHT_PHASES = {"post-flight"}


def compute_narrative_ranking(
    profile: pd.DataFrame,
    concordance: pd.DataFrame,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    profile     : master profile (all crew, all timepoints).
    concordance : cohort_concordance DataFrame.

    Returns
    -------
    narrative_ranking.csv schema DataFrame.
    """
    focal_post = profile[
        (profile["crew_id"] == FOCAL)
        & (profile["phase"].isin(POST_FLIGHT_PHASES))
        & profile["z_score"].notna()
    ].copy()

    group_cols = ["layer", "measurement", "site"]
    records = []

    for key, grp in focal_post.groupby(group_cols, dropna=False):
        layer, measurement, site = key
        site_val = None if (isinstance(site, float) and np.isnan(site)) else site

        abs_z = grp["z_score"].abs()
        if abs_z.empty or abs_z.isna().all():
            continue

        peak_idx = abs_z.idxmax()
        peak_abs_z = float(abs_z.loc[peak_idx])
        peak_tp = grp.loc[peak_idx, "timepoint"]

        # Conservative effect size: min |z| within the bootstrap CI.
        # If CI = [lo, hi]:
        #   both positive → min |z| = lo
        #   both negative → min |z| = |hi|
        #   crosses zero  → min |z| = 0  (signal could be noise)
        ci_low = grp.loc[peak_idx, "z_score_ci_low"]
        ci_high = grp.loc[peak_idx, "z_score_ci_high"]
        if not np.isnan(ci_low) and not np.isnan(ci_high):
            if ci_low >= 0:
                peak_z_ci_lower_abs = float(ci_low)
            elif ci_high <= 0:
                peak_z_ci_lower_abs = float(abs(ci_high))
            else:
                peak_z_ci_lower_abs = 0.0   # CI crosses zero
        else:
            peak_z_ci_lower_abs = 0.0  # no CI → conservative: treat as 0

        # clinical_flagged_count: CBC only
        clinical_flagged_count = 0
        if layer == "clinical":
            clinical_flagged_count = int(
                (grp["clinical_flag"].isin(["above-range", "below-range"])).sum()
            )

        # concordance class at peak timepoint
        conc_mask = (
            (concordance["layer"] == layer)
            & (concordance["measurement"] == measurement)
            & (concordance["timepoint"] == peak_tp)
        )
        if site_val is not None:
            conc_mask &= concordance["site"] == site_val
        else:
            conc_mask &= concordance["site"].isna()

        conc_row = concordance[conc_mask]
        if not conc_row.empty:
            concordance_class = conc_row.iloc[0]["concordance_class"]
        else:
            concordance_class = "ambiguous"

        cw = _CONCORDANCE_WEIGHTS.get(concordance_class, 0.8)
        signal_score = peak_z_ci_lower_abs * (1 + 0.5 * clinical_flagged_count) * cw

        # measurement label
        label = grp["measurement_label"].dropna().iloc[0] if grp["measurement_label"].notna().any() else measurement

        records.append({
            "layer":                  layer,
            "measurement":            measurement,
            "measurement_label":      label,
            "site":                   site_val,
            "peak_abs_z":             peak_abs_z,
            "peak_z_ci_lower_abs":    peak_z_ci_lower_abs,
            "peak_timepoint":         peak_tp,
            "clinical_flagged_count": clinical_flagged_count,
            "concordance_class":      concordance_class,
            "signal_score":           signal_score,
        })

    df = pd.DataFrame(records)

    # rank within layer and overall
    df = df.sort_values("signal_score", ascending=False).reset_index(drop=True)
    df["rank_overall"] = df.index + 1
    df["rank_within_layer"] = (
        df.groupby(["layer", "site"], dropna=False)["signal_score"]
        .rank(ascending=False, method="first")
        .astype(int)
    )

    log.info(
        "narrative: %d measurements ranked; top-3 scores: %s",
        len(df),
        df["signal_score"].head(3).round(3).tolist(),
    )
    return df.reset_index(drop=True)
