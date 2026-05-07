"""
Recovery velocity computation.

For each measurement in the focal subject (C003) with ≥2 post-flight timepoints:
  - peak_z_score:  max |z| across post-flight timepoints.
  - peak_timepoint: where that max occurs.
  - return_to_baseline_day: first post-flight day where |z| < 1; NaN if never.
  - recovery_velocity: (peak_z − final_z) / (final_day − peak_day).
  - recovery_classification: fast (<45d) | slow (45–194d) | incomplete (never).
  - n_post_flight_points: number of post-flight timepoints with a valid z-score.

Measurements with only 1 post-flight point are skipped.
"""
import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FOCAL = "C003"
POST_FLIGHT_PHASES = {"post-flight"}


def compute_kinetics(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Parameters
    ----------
    profile : master long-format DataFrame (all layers, all crew).

    Returns
    -------
    recovery_kinetics_C003.csv schema DataFrame.
    """
    focal = profile[
        (profile["crew_id"] == FOCAL)
        & (profile["phase"].isin(POST_FLIGHT_PHASES))
        & profile["z_score"].notna()
    ].copy()

    group_cols = ["layer", "measurement", "site"]
    records = []

    for key, grp in focal.groupby(group_cols, dropna=False):
        layer, measurement, site = key
        site_val = None if (isinstance(site, float) and np.isnan(site)) else site

        # sort by days_from_launch
        grp = grp.sort_values("days_from_launch")

        n_pts = len(grp)
        if n_pts < 2:
            continue  # can't compute kinetics

        abs_z = grp["z_score"].abs()
        peak_idx = abs_z.idxmax()
        peak_z = float(abs_z.loc[peak_idx])
        peak_tp = grp.loc[peak_idx, "timepoint"]
        peak_day = int(grp.loc[peak_idx, "days_from_launch"])

        # return_to_baseline_day: first post-peak timepoint with |z| < 1
        post_peak = grp[grp["days_from_launch"] >= peak_day]
        returned = post_peak[post_peak["z_score"].abs() < 1.0]
        if not returned.empty:
            return_day = int(returned.iloc[0]["days_from_launch"])
        else:
            return_day = np.nan

        # recovery_velocity: (peak_z − last_z) / (last_day − peak_day)
        last_row = grp.iloc[-1]
        final_z = float(last_row["z_score"].real if hasattr(last_row["z_score"], "real")
                        else last_row["z_score"])
        final_day = int(last_row["days_from_launch"])
        elapsed = final_day - peak_day
        if elapsed > 0:
            velocity = (peak_z - abs(final_z)) / elapsed
        else:
            velocity = np.nan

        # recovery_classification
        if not np.isnan(return_day):
            if return_day < 45:
                classification = "fast"
            else:
                classification = "slow"
        else:
            classification = "incomplete"

        # measurement label (first non-null)
        label = grp["measurement_label"].dropna().iloc[0] if grp["measurement_label"].notna().any() else measurement

        records.append({
            "crew_id":                 FOCAL,
            "layer":                   layer,
            "measurement":             measurement,
            "measurement_label":       label,
            "site":                    site_val,
            "peak_z_score":            peak_z,
            "peak_timepoint":          peak_tp,
            "return_to_baseline_day":  return_day,
            "recovery_velocity":       velocity,
            "recovery_classification": classification,
            "n_post_flight_points":    n_pts,
        })

    df = pd.DataFrame(records)
    log.info("kinetics: %d measurement×site kinetics rows for %s", len(df), FOCAL)
    return df.reset_index(drop=True)
