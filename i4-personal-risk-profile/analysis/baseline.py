"""
Personal baseline computation with bootstrap CI.

For each (crew_id × layer × measurement × site) tuple:
  - Collect pre-flight value_transformed values (L-92, L-44, L-3; n=3).
  - Compute point-estimate mean and SD.
  - Bootstrap 1000 resamples with replacement → distribution of (mean, SD).
  - baseline_ci_low / baseline_ci_high: 2.5 / 97.5 percentiles of bootstrapped means.
  - Store boot_means / boot_sds for downstream z-score CI propagation.

Emits warnings for insufficient baselines and zero-SD cases.
"""
import logging
import warnings
from typing import NamedTuple

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

N_BOOTS = 1000
BASELINE_TPS = {"L-92", "L-44", "L-3"}
_RNG = np.random.default_rng(42)


class BaselineStats(NamedTuple):
    mean: float          # point estimate
    sd: float            # point estimate (ddof=1)
    ci_low: float        # 2.5th pct of bootstrapped means
    ci_high: float       # 97.5th pct of bootstrapped means
    boot_means: np.ndarray   # shape (N_BOOTS,)
    boot_sds: np.ndarray     # shape (N_BOOTS,)


def _bootstrap_baseline(values: np.ndarray) -> BaselineStats:
    """
    Bootstrap 1000 resamples from `values` (n=3 pre-flight observations).
    Returns point estimates + CI + full bootstrap distribution.
    """
    n = len(values)
    idx = _RNG.integers(0, n, size=(N_BOOTS, n))   # (1000, n)
    resampled = values[idx]                          # (1000, n)

    boot_means = resampled.mean(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        boot_sds = resampled.std(axis=1, ddof=1)    # NaN when all resampled same

    return BaselineStats(
        mean=float(np.mean(values)),
        sd=float(np.std(values, ddof=1)),
        ci_low=float(np.nanpercentile(boot_means, 2.5)),
        ci_high=float(np.nanpercentile(boot_means, 97.5)),
        boot_means=boot_means,
        boot_sds=boot_sds,
    )


def _group_key(row) -> tuple:
    site = row["site"] if not (isinstance(row["site"], float) and np.isnan(row["site"])) else None
    return (row["crew_id"], row["layer"], row["measurement"], site)


def compute_baselines(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Parameters
    ----------
    df : transformed long DataFrame (has value_transformed).

    Returns
    -------
    df_with_baselines : input DataFrame with baseline columns added.
    boot_store : dict mapping (crew_id, layer, measurement, site_or_None)
                 → BaselineStats — needed by deviation.py for z CI propagation.
    """
    group_cols = ["crew_id", "layer", "measurement", "site"]
    baseline_mask = df["is_baseline_timepoint"]

    # initialise output columns
    for col in ["baseline_mean", "baseline_sd", "baseline_ci_low", "baseline_ci_high"]:
        df[col] = np.nan

    boot_store: dict[tuple, BaselineStats] = {}
    n_ok = 0
    n_few = 0
    n_zero_sd = 0

    for key, grp in df[baseline_mask].groupby(group_cols, dropna=False):
        crew_id, layer, measurement, site = key
        site_key = None if (isinstance(site, float) and np.isnan(site)) else site

        vals = grp["value_transformed"].dropna().values.astype(float)

        if len(vals) < 2:
            log.warning(
                "baseline: %s/%s/%s/%s — only %d pre-flight values; "
                "setting baseline to NaN",
                crew_id, layer, measurement, site_key, len(vals),
            )
            n_few += 1
            continue

        stats = _bootstrap_baseline(vals)
        store_key = (crew_id, layer, measurement, site_key)
        boot_store[store_key] = stats

        # propagate baseline stats to ALL rows for this group (not just baseline TPs)
        mask = (
            (df["crew_id"] == crew_id)
            & (df["layer"] == layer)
            & (df["measurement"] == measurement)
        )
        if site_key is not None:
            mask &= df["site"] == site_key
        else:
            mask &= df["site"].isna()

        df.loc[mask, "baseline_mean"] = stats.mean
        df.loc[mask, "baseline_sd"] = stats.sd
        df.loc[mask, "baseline_ci_low"] = stats.ci_low
        df.loc[mask, "baseline_ci_high"] = stats.ci_high

        if stats.sd == 0.0:
            log.warning(
                "baseline: %s/%s/%s/%s — SD=0 (constant pre-flight); "
                "z-scores will be NaN",
                crew_id, layer, measurement, site_key,
            )
            n_zero_sd += 1
        else:
            n_ok += 1

    log.info(
        "baseline: %d tuples computed (ok=%d, few_tps=%d, zero_sd=%d)",
        n_ok + n_few + n_zero_sd, n_ok, n_few, n_zero_sd,
    )
    return df, boot_store
