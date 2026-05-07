"""
Value transformations.
Adds `value_transformed` to a parsed long DataFrame.
No in-place mutations — returns a new DataFrame.
"""
import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# CBC stays on raw clinical scale; z-scoring is supplementary.
_IDENTITY_LAYERS = {"clinical"}
# Cytokines and microbial get log1p to compress the dynamic range.
_LOG1P_LAYERS = {"immune", "microbial"}


def apply_transforms(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply layer-appropriate value transform.
    Returns DataFrame with `value_transformed` and `unit` (updated for log layers).
    """
    df = df.copy()
    df["value_transformed"] = np.nan

    for layer, grp_idx in df.groupby("layer").groups.items():
        vals = df.loc[grp_idx, "value_raw"].values.astype(float)

        if layer in _IDENTITY_LAYERS:
            df.loc[grp_idx, "value_transformed"] = vals
            # unit unchanged

        elif layer in _LOG1P_LAYERS:
            df.loc[grp_idx, "value_transformed"] = np.log1p(vals)
            # update unit to reflect transformation
            orig_units = df.loc[grp_idx, "unit"].unique()
            for orig in orig_units:
                mask = (df.index.isin(grp_idx)) & (df["unit"] == orig)
                df.loc[mask, "unit"] = f"{orig}-log1p"

        else:
            log.warning("transform: unknown layer '%s', leaving value_transformed=NaN", layer)

    log.info("transform: applied identity to %d clinical rows, log1p to %d immune+microbial rows",
             (df["layer"] == "clinical").sum(),
             df["layer"].isin(_LOG1P_LAYERS).sum())

    return df


def filter_zero_inflated(df: pd.DataFrame,
                         threshold: float = 0.5) -> pd.DataFrame:
    """
    For microbial (and immune if ever applicable): for each
    (crew_id × measurement × site) tuple, if ≥threshold fraction of
    pre-flight value_transformed values are 0, drop all rows for that tuple.

    threshold=0.5 with n=3 baseline → drops if ≥2 of 3 baseline values are 0.

    Returns filtered DataFrame and logs dropped measurements per crew.
    """
    log1p_layers = df[df["layer"].isin(_LOG1P_LAYERS)]
    baseline_rows = log1p_layers[log1p_layers["is_baseline_timepoint"]]

    group_cols = ["crew_id", "layer", "measurement", "site"]

    drop_keys: set[tuple] = set()
    for key, grp in baseline_rows.groupby(group_cols, dropna=False):
        n_total = len(grp)
        if n_total == 0:
            continue
        n_zero = (grp["value_transformed"] == 0.0).sum()
        if n_total > 0 and n_zero / n_total >= threshold:
            drop_keys.add(key)

    if not drop_keys:
        return df

    # Build mask for rows to drop
    site_col = df["site"].fillna("__nan__")
    key_series = list(zip(df["crew_id"], df["layer"],
                          df["measurement"], site_col))
    # Normalise drop_keys to use __nan__ for NaN sites
    norm_drop = {
        (k[0], k[1], k[2], "__nan__" if (isinstance(k[3], float) and np.isnan(k[3])) else k[3])
        for k in drop_keys
    }
    drop_mask = pd.Series([k in norm_drop for k in key_series], index=df.index)

    n_dropped = drop_mask.sum()
    n_meas_dropped = len(drop_keys)
    log.warning(
        "zero-inflation filter: dropping %d (crew×measurement×site) tuples "
        "(%d rows) where ≥%.0f%% baseline values are 0",
        n_meas_dropped, n_dropped, threshold * 100,
    )

    return df[~drop_mask].reset_index(drop=True)
