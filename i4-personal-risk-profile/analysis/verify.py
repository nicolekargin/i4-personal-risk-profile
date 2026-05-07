"""
Baseline fragility detection + robustness stress test.

Adds to personal_profile_C003.csv:
  Fragility flags (per row):
    is_baseline_fragile   bool
    fragility_reason      str  ("constant-baseline", "unstable-ci",
                                "lower-ci-below-threshold"; comma-separated)

  Robust parallel pipeline (median ± MAD):
    baseline_median
    baseline_mad           (scaled: × 1.4826, comparable to SD under normality)
    z_score_robust
    z_score_robust_ci_low
    z_score_robust_ci_high

  Concordance between methods (non-baseline rows):
    methods_concordance    ("both-elevated" | "both-stable" | "discordant" | "borderline")

Implementation note — degenerate bootstrap for MAD with n=3:
  For 3 distinct baseline values, exactly 6/27 bootstrap resamples (≈22%) draw all
  3 distinct values; only those give MAD > 0.  The remaining ≈78% have MAD = 0 and
  are excluded.  All 22% contributing resamples produce the same z_robust (since median
  and MAD are fixed for the set {a,b,c}), so the bootstrap CI for the robust z-score
  collapses to [z_robust, z_robust].  This is an honest representation of MAD's
  limitation with n=3 — the robust estimator has no uncertainty range at this sample size.
"""
import logging
import warnings

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

N_BOOTS = 1000
_BOOT_SD_MIN = 1e-10
BASELINE_TPS = {"L-92", "L-44", "L-3"}
_CONSISTENCY_FACTOR = 1.4826   # makes MAD comparable to SD under normality
_RNG = np.random.default_rng(42)


# ── fragility ────────────────────────────────────────────────────────────────

def _compute_fragility_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add is_baseline_fragile (bool) and fragility_reason (str) to df.
    Fragility is assessed per-row; baseline rows are not flagged for ci checks.
    """
    df = df.copy()
    df["is_baseline_fragile"] = False
    df["fragility_reason"] = ""

    group_cols = ["crew_id", "layer", "measurement", "site"]

    # --- 1. constant-baseline: raw SD of pre-flight values < 1e-8 ---
    bl = df[df["is_baseline_timepoint"] == True]
    raw_sd_map: dict[tuple, float] = {}
    for key, grp in bl.groupby(group_cols, dropna=False):
        crew_id, layer, measurement, site = key
        sk = None if (isinstance(site, float) and np.isnan(site)) else site
        vals = grp["value_raw"].dropna().values.astype(float)
        raw_sd_map[(crew_id, layer, measurement, sk)] = float(np.std(vals, ddof=1)) if len(vals) > 1 else np.nan

    site_norm = df["site"].where(df["site"].notna(), None)
    for i, row in df.iterrows():
        sk = row["site"] if not (isinstance(row["site"], float) and np.isnan(row["site"])) else None
        key = (row["crew_id"], row["layer"], row["measurement"], sk)
        raw_sd = raw_sd_map.get(key, np.nan)
        if not np.isnan(raw_sd) and raw_sd < 1e-8:
            df.at[i, "is_baseline_fragile"] = True
            df.at[i, "fragility_reason"] = _append_reason(df.at[i, "fragility_reason"], "constant-baseline")

    # --- 2. unstable-ci: |z_ci_high − z_ci_low| > 10 × |z_score| ---
    # Only for non-baseline rows where the z-score exists.
    non_bl = ~df["is_baseline_timepoint"] & df["z_score"].notna() & df["z_score_ci_low"].notna()
    ci_width = (df.loc[non_bl, "z_score_ci_high"] - df.loc[non_bl, "z_score_ci_low"]).abs()
    abs_z = df.loc[non_bl, "z_score"].abs()
    # Use max(|z|, 0.5) as denominator to avoid flagging near-zero signals
    relative_width = ci_width / np.maximum(abs_z, 0.5)
    unstable_idx = relative_width[relative_width > 10].index
    df.loc[unstable_idx, "is_baseline_fragile"] = True
    for i in unstable_idx:
        df.at[i, "fragility_reason"] = _append_reason(df.at[i, "fragility_reason"], "unstable-ci")

    # --- 3. lower-ci-below-threshold: conservative |z| < 1.0 ---
    # For non-baseline rows: the lower-CI bound of |z| must reach the "elevated" threshold.
    # peak_z_ci_lower_abs = min |z| in CI = 0 if CI crosses zero, |edge| otherwise.
    for i in df[non_bl].index:
        ci_low = df.at[i, "z_score_ci_low"]
        ci_high = df.at[i, "z_score_ci_high"]
        if pd.isna(ci_low) or pd.isna(ci_high):
            continue
        if ci_low >= 0:
            lower_abs = float(ci_low)
        elif ci_high <= 0:
            lower_abs = float(abs(ci_high))
        else:
            lower_abs = 0.0
        if lower_abs < 1.0:
            df.at[i, "is_baseline_fragile"] = True
            df.at[i, "fragility_reason"] = _append_reason(df.at[i, "fragility_reason"], "lower-ci-below-threshold")

    n_fragile = df["is_baseline_fragile"].sum()
    log.info("fragility: %d fragile rows out of %d", n_fragile, len(df))
    return df


def _append_reason(existing: str, reason: str) -> str:
    if existing:
        return f"{existing},{reason}"
    return reason


# ── robust (median + MAD) baseline ───────────────────────────────────────────

def _bootstrap_robust(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (boot_medians, boot_mads_scaled) for 1000 resamples."""
    n = len(values)
    idx = _RNG.integers(0, n, size=(N_BOOTS, n))
    resampled = values[idx]                                       # (1000, n)
    boot_medians = np.median(resampled, axis=1)                   # (1000,)
    devs = np.abs(resampled - boot_medians[:, np.newaxis])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        boot_mads = np.median(devs, axis=1) * _CONSISTENCY_FACTOR  # (1000,)
    return boot_medians, boot_mads


def _compute_robust_z_for_group(
    values_t: np.ndarray,   # (n_rows,) all timepoints' log1p values
    baseline_t: np.ndarray, # (n_baseline,) pre-flight log1p values
) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns: (pt_median, pt_mad_scaled, z_robustArr, ci_low_arr, ci_high_arr)
    """
    pt_median = float(np.median(baseline_t))
    devs = np.abs(baseline_t - pt_median)
    pt_mad = float(np.median(devs) * _CONSISTENCY_FACTOR)

    n_rows = len(values_t)
    z_robust = np.full(n_rows, np.nan)
    ci_low = np.full(n_rows, np.nan)
    ci_high = np.full(n_rows, np.nan)

    if pt_mad < _BOOT_SD_MIN:
        return pt_median, pt_mad, z_robust, ci_low, ci_high

    z_robust = (values_t - pt_median) / pt_mad

    # Bootstrap CI
    boot_medians, boot_mads = _bootstrap_robust(baseline_t)
    valid = boot_mads >= _BOOT_SD_MIN
    if valid.sum() == 0:
        ci_low[:] = z_robust
        ci_high[:] = z_robust
        return pt_median, pt_mad, z_robust, ci_low, ci_high

    bm_v = boot_medians[np.newaxis, valid]  # (1, n_valid)
    bm_s = boot_mads[np.newaxis, valid]     # (1, n_valid)
    vt_col = values_t[:, np.newaxis]        # (n_rows, 1)
    z_boot = (vt_col - bm_v) / bm_s        # (n_rows, n_valid)

    nan_mask = np.isnan(values_t)
    z_boot[nan_mask, :] = np.nan

    ci_low = np.nanpercentile(z_boot, 2.5, axis=1)
    ci_high = np.nanpercentile(z_boot, 97.5, axis=1)

    return pt_median, pt_mad, z_robust, ci_low, ci_high


def _compute_robust_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Add baseline_median, baseline_mad, z_score_robust, and CI columns."""
    df = df.copy()
    for col in ["baseline_median", "baseline_mad", "z_score_robust",
                "z_score_robust_ci_low", "z_score_robust_ci_high"]:
        df[col] = np.nan

    group_cols = ["crew_id", "layer", "measurement", "site"]
    n_ok = n_skip = 0

    for key, grp in df.groupby(group_cols, dropna=False):
        crew_id, layer, measurement, site = key
        bl_mask = grp["is_baseline_timepoint"] == True
        baseline_t = grp.loc[bl_mask, "value_transformed"].dropna().values.astype(float)

        if len(baseline_t) < 2:
            n_skip += 1
            continue

        idx = grp.index
        values_t = grp["value_transformed"].values.astype(float)

        pt_median, pt_mad, z_rob, ci_lo, ci_hi = _compute_robust_z_for_group(values_t, baseline_t)

        df.loc[idx, "baseline_median"] = pt_median
        df.loc[idx, "baseline_mad"] = pt_mad
        df.loc[idx, "z_score_robust"] = z_rob
        df.loc[idx, "z_score_robust_ci_low"] = ci_lo
        df.loc[idx, "z_score_robust_ci_high"] = ci_hi
        n_ok += 1

    log.info("robust pipeline: %d groups computed, %d skipped (< 2 baseline TPs)", n_ok, n_skip)
    return df


# ── methods concordance ───────────────────────────────────────────────────────

def _concordance(z: float, z_rob: float) -> str:
    if pd.isna(z) or pd.isna(z_rob):
        return "unknown"
    abs_z, abs_r = abs(z), abs(z_rob)
    same_sign = (z > 0 and z_rob > 0) or (z < 0 and z_rob < 0)

    if abs_z < 1 and abs_r < 1:
        return "both-stable"
    if abs_z >= 2 and abs_r >= 2:
        return "both-elevated" if same_sign else "discordant"
    if (abs_z >= 2 and abs_r < 1) or (abs_z < 1 and abs_r >= 2):
        return "discordant"
    if not same_sign and abs_z >= 1 and abs_r >= 1:
        return "discordant"
    return "borderline"


def _compute_methods_concordance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    conc = [
        _concordance(row.z_score, row.z_score_robust)
        for row in df[["z_score", "z_score_robust"]].itertuples()
    ]
    df["methods_concordance"] = conc
    counts = pd.Series(conc).value_counts()
    log.info("methods_concordance: %s", counts.to_dict())
    return df


# ── public entry point ────────────────────────────────────────────────────────

def run_verification(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Master function: compute all new verify.py columns.
    Returns updated profile DataFrame.
    """
    log.info("verify: computing fragility flags …")
    profile = _compute_fragility_flags(profile)

    log.info("verify: computing robust (median+MAD) z-scores …")
    profile = _compute_robust_pipeline(profile)

    log.info("verify: computing methods_concordance …")
    profile = _compute_methods_concordance(profile)

    return profile
