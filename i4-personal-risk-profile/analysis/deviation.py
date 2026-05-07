"""
Deviation scoring: z-scores with bootstrap CI, fold changes, clinical flags.

For each non-baseline timepoint row:
  - z_score = (value_transformed - baseline_mean) / baseline_sd
  - z CI: re-derive z under each of the 1000 bootstrapped (mean, sd) pairs,
    take 2.5/97.5 percentiles.
  - fold_change = value_raw / mean(raw baseline values).
  - clinical_flag: CBC only — in-range / above-range / below-range.
  - deviation_flag: |z| binned into stable / elevated / high / extreme.
  - deviation_direction: "up" / "down" / NaN (if stable).

The z-score CI computation is vectorized per (crew × measurement × site) group
to keep runtime manageable over ~100k metagenomics rows.
"""
import logging

import numpy as np
import pandas as pd

from .baseline import BaselineStats

log = logging.getLogger(__name__)

# numpy's vectorised std produces machine-epsilon values (~5e-16) for identical
# bootstrap resamples rather than exactly 0.  Values below this threshold are
# treated as zero-SD bootstrap draws and excluded from z-CI computation.
_BOOT_SD_MIN = 1e-10

_DEVIATION_THRESHOLDS = np.array([1.0, 2.0, 3.0])
_DEVIATION_LABELS = ["stable", "elevated", "high", "extreme"]


def _deviation_flag_series(abs_z: pd.Series) -> pd.Series:
    flags = pd.Series("stable", index=abs_z.index, dtype=object)
    flags[abs_z >= 3.0] = "extreme"
    flags[(abs_z >= 2.0) & (abs_z < 3.0)] = "high"
    flags[(abs_z >= 1.0) & (abs_z < 2.0)] = "elevated"
    flags[abs_z.isna()] = "stable"
    return flags


def compute_deviations(df: pd.DataFrame, boot_store: dict) -> pd.DataFrame:
    """
    Parameters
    ----------
    df         : DataFrame after compute_baselines.
    boot_store : mapping (crew_id, layer, measurement, site_or_None) → BaselineStats.

    Returns
    -------
    DataFrame with z_score, z_score_ci_low, z_score_ci_high, fold_change,
    clinical_flag, deviation_flag, deviation_direction added.
    """
    df = df.copy()

    # initialise output columns with correct dtypes upfront
    df["z_score"]         = np.nan
    df["z_score_ci_low"]  = np.nan
    df["z_score_ci_high"] = np.nan
    df["fold_change"]     = np.nan
    df["clinical_flag"]   = pd.array([None] * len(df), dtype=object)
    df["deviation_flag"]  = pd.array(["stable"] * len(df), dtype=object)
    df["deviation_direction"] = pd.array([None] * len(df), dtype=object)

    group_cols = ["crew_id", "layer", "measurement", "site"]

    # pre-compute raw baseline means per (crew × measurement × site)
    baseline_df = df[df["is_baseline_timepoint"]]
    raw_bm_map: dict[tuple, float] = {}
    for key, grp in baseline_df.groupby(group_cols, dropna=False):
        crew_id, layer, measurement, site = key
        sk = None if (isinstance(site, float) and np.isnan(site)) else site
        raw_bm_map[(crew_id, layer, measurement, sk)] = grp["value_raw"].dropna().mean()

    n_scored = 0
    n_no_stats = 0
    n_zero_sd = 0

    for key, grp in df.groupby(group_cols, dropna=False):
        crew_id, layer, measurement, site = key
        sk = None if (isinstance(site, float) and np.isnan(site)) else site
        store_key = (crew_id, layer, measurement, sk)

        stats: BaselineStats | None = boot_store.get(store_key)
        raw_bm = raw_bm_map.get(store_key, np.nan)

        idx = grp.index

        # fold_change — vectorised for the whole group
        if not np.isnan(raw_bm) and raw_bm != 0:
            df.loc[idx, "fold_change"] = grp["value_raw"].values / raw_bm

        # clinical flag (CBC only)
        if layer == "clinical":
            vr  = grp["value_raw"]
            cmin = grp["clinical_min"]
            cmax = grp["clinical_max"]
            has_range = cmin.notna() & cmax.notna()
            flags = pd.array([None] * len(grp), dtype=object)
            flags[has_range & (vr < cmin)] = "below-range"
            flags[has_range & (vr > cmax)] = "above-range"
            flags[has_range & (vr >= cmin) & (vr <= cmax)] = "in-range"
            df.loc[idx, "clinical_flag"] = flags

        if stats is None or np.isnan(stats.mean):
            n_no_stats += len(grp)
            continue

        if stats.sd == 0.0:
            n_zero_sd += len(grp)
            # z_score stays NaN
            continue

        # z-score point estimate — vectorised
        vt = grp["value_transformed"].values.astype(float)
        z_vals = (vt - stats.mean) / stats.sd
        df.loc[idx, "z_score"] = z_vals
        n_scored += len(grp)

        # z-score CI — propagate baseline uncertainty
        # For each value, compute z under each of the 1000 bootstrap (mean, sd) pairs.
        # boot_means shape (1000,), boot_sds shape (1000,)
        # z_boot shape: (n_rows, 1000)
        bm = stats.boot_means   # (1000,)
        bs = stats.boot_sds     # (1000,)
        valid = bs >= _BOOT_SD_MIN   # exclude machine-epsilon near-zero SDs

        if valid.any():
            vt_col = vt[:, np.newaxis]              # (n_rows, 1)
            bm_v = bm[np.newaxis, valid]             # (1, n_valid)
            bs_v = bs[np.newaxis, valid]             # (1, n_valid)
            z_boot = (vt_col - bm_v) / bs_v         # (n_rows, n_valid)

            # fill NaN where vt was NaN
            nan_mask = np.isnan(vt)
            z_boot[nan_mask, :] = np.nan

            ci_lo = np.nanpercentile(z_boot, 2.5,  axis=1)  # (n_rows,)
            ci_hi = np.nanpercentile(z_boot, 97.5, axis=1)  # (n_rows,)
            df.loc[idx, "z_score_ci_low"]  = ci_lo
            df.loc[idx, "z_score_ci_high"] = ci_hi

    # deviation_flag and direction — fully vectorised
    abs_z = df["z_score"].abs()
    df["deviation_flag"] = _deviation_flag_series(abs_z)
    dirs = pd.array([None] * len(df), dtype=object)
    dirs[df["z_score"] > 0] = "up"
    dirs[df["z_score"] < 0] = "down"
    # stable rows get None (will appear as NaN in CSV)
    dirs[df["deviation_flag"] == "stable"] = None
    df["deviation_direction"] = dirs

    log.info(
        "deviations: %d z-scores computed (no_stats=%d, zero_sd=%d)",
        n_scored, n_no_stats, n_zero_sd,
    )
    return df


def assemble_master_profile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select and order the 25 schema-mandated columns for personal_profile_C003.csv.
    """
    schema_cols = [
        "crew_id", "timepoint", "days_from_launch", "phase",
        "layer", "site",
        "measurement", "measurement_label",
        "value_raw", "value_transformed", "unit",
        "baseline_mean", "baseline_sd", "baseline_ci_low", "baseline_ci_high",
        "z_score", "z_score_ci_low", "z_score_ci_high",
        "fold_change",
        "clinical_min", "clinical_max", "clinical_flag",
        "deviation_flag", "deviation_direction",
        "is_baseline_timepoint",
    ]
    for col in schema_cols:
        if col not in df.columns:
            df[col] = np.nan
    return df[schema_cols].reset_index(drop=True)
