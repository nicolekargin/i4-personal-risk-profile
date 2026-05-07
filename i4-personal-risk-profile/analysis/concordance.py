"""
Cohort concordance: does C003's z-score direction agree with C001/C002/C004?

For each (measurement × timepoint) at post-flight timepoints:
  - c003_direction: "up" (z>1) | "down" (z<-1) | "stable" (|z|<1)
  - cohort_direction_agree: count of cohort members whose direction matches C003
  - concordance_class:
      "concordant"    — ≥2 cohort members agree with C003 (C003 non-stable)
      "discordant"    — ≥2 cohort members in opposite direction
      "idiosyncratic" — C003 non-stable, ≥2 cohort members stable
      "ambiguous"     — anything else

n=4 forbids inferential statistics; concordance class is the most
defensible cohort-level claim we can make.
"""
import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FOCAL = "C003"
COHORT = ["C001", "C002", "C004"]
POST_FLIGHT_PHASES = {"post-flight"}


def _direction(z: float) -> str:
    if np.isnan(z):
        return "stable"  # treat NaN as stable for concordance
    if z > 1.0:
        return "up"
    if z < -1.0:
        return "down"
    return "stable"


def _opposite(d: str) -> str:
    return {"up": "down", "down": "up"}.get(d, "")


def compute_concordance(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Parameters
    ----------
    profile : master long-format DataFrame, ALL crew included.

    Returns
    -------
    cohort_concordance.csv schema DataFrame.
    """
    post = profile[profile["phase"].isin(POST_FLIGHT_PHASES)].copy()

    group_cols = ["layer", "measurement", "site", "timepoint"]
    records = []

    for key, grp in post.groupby(group_cols, dropna=False):
        layer, measurement, site, timepoint = key
        site_val = None if (isinstance(site, float) and np.isnan(site)) else site

        c003_rows = grp[grp["crew_id"] == FOCAL]
        if c003_rows.empty or c003_rows["z_score"].isna().all():
            continue
        c003_z = float(c003_rows["z_score"].dropna().iloc[0])
        c003_dir = _direction(c003_z)

        cohort_zs: list[float] = []
        cohort_dirs: list[str] = []
        for member in COHORT:
            member_rows = grp[grp["crew_id"] == member]
            if member_rows.empty or member_rows["z_score"].isna().all():
                continue
            mz = float(member_rows["z_score"].dropna().iloc[0])
            cohort_zs.append(mz)
            cohort_dirs.append(_direction(mz))

        n_cohort = len(cohort_zs)
        cohort_mean_z = float(np.mean(cohort_zs)) if cohort_zs else np.nan
        cohort_sd_z   = float(np.std(cohort_zs, ddof=1)) if len(cohort_zs) > 1 else np.nan

        n_agree    = cohort_dirs.count(c003_dir)
        n_opposite = cohort_dirs.count(_opposite(c003_dir)) if c003_dir != "stable" else 0
        n_stable   = cohort_dirs.count("stable")

        if c003_dir != "stable":
            if n_agree >= 2:
                concordance = "concordant"
            elif n_opposite >= 2:
                concordance = "discordant"
            elif n_stable >= 2:
                concordance = "idiosyncratic"
            else:
                concordance = "ambiguous"
        else:
            concordance = "ambiguous"  # C003 stable → can't classify

        records.append({
            "layer":                   layer,
            "measurement":             measurement,
            "site":                    site_val,
            "timepoint":               timepoint,
            "c003_z":                  c003_z,
            "c003_direction":          c003_dir,
            "cohort_mean_z":           cohort_mean_z,
            "cohort_sd_z":             cohort_sd_z,
            "cohort_n":                n_cohort,
            "cohort_direction_agree":  n_agree,
            "concordance_class":       concordance,
        })

    df = pd.DataFrame(records)
    log.info(
        "concordance: %d (measurement×timepoint) rows; class distribution:\n%s",
        len(df),
        df["concordance_class"].value_counts().to_string() if len(df) else "empty",
    )
    return df.reset_index(drop=True)
