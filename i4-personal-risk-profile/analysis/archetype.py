"""
Cytokine archetype synthesis.

Assigns each immune measurement to one or more functional archetypes,
then computes per-archetype activation scores for C003 at each post-flight
timepoint.

archetype_synthesis.csv schema:
  archetype, timepoint, days_from_launch,
  n_members, n_elevated, pct_elevated,
  mean_abs_z, max_abs_z, direction_dominant,
  archetype_activation_score,
  constituent_measurements (pipe-separated)

Also adds 'archetype' (pipe-separated archetype names) column to the master
profile for immune rows.
"""
import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FOCAL = "C003"

ARCHETYPES: dict[str, list[str]] = {
    "acute_phase_response": [
        "il_6", "crp", "saa", "tnf_alpha", "il_1_beta", "il_8",
    ],
    "th1_polarization": [
        "ifn_gamma", "il_2", "il_12", "il_12_p70", "tnf_beta",
    ],
    "th2_polarization": [
        "il_4", "il_5", "il_13", "il_33", "tarc", "ctack", "eotaxin", "eotaxin_3",
    ],
    "th17_response": [
        "il_17", "il_17a", "il_17e", "il_17f", "il_22", "il_23", "il_25",
    ],
    "regulatory_response": [
        "il_10", "tgf_beta", "il_1ra",
    ],
    "monocyte_macrophage_recruitment": [
        "mcp_1", "mcp_2", "mcp_3", "mcp_4",
        "mip_1_alpha", "mip_1_beta", "mip_3_alpha", "mip_3_beta",
        "rantes", "fractalkine",
    ],
    "neutrophil_chemoattraction": [
        "il_8", "gro_alpha", "gro_beta", "ena_78",
    ],
    "interferon_response": [
        "ifn_alpha", "ifn_alpha_2", "ifn_gamma", "ip_10", "mig", "i_tac",
    ],
    "vascular_growth": [
        "vegf", "vegf_a", "vegf_c", "vegf_d",
        "fgf_basic", "fgf_2",
        "pdgf_aa", "pdgf_bb", "pdgf_ab_bb", "egf", "ang_2",
    ],
    "tissue_remodeling": [
        "mmp_1", "mmp_3", "mmp_9", "timp_1", "sicam_1", "svcam_1",
    ],
    "hematopoiesis_growth": [
        "g_csf", "gm_csf", "m_csf", "scf", "tpo", "il_3", "il_7",
    ],
}

# Reverse index: canonical_id → list[archetype_name]
_MEMBER_TO_ARCHETYPES: dict[str, list[str]] = {}
for _arch, _members in ARCHETYPES.items():
    for _m in _members:
        _MEMBER_TO_ARCHETYPES.setdefault(_m, []).append(_arch)


def _canonical(measurement: str) -> str:
    """Lower-case, strip spaces, collapse separators to underscore."""
    import re
    s = measurement.lower().strip()
    s = re.sub(r"[\s\-/]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


def _norm(s: str) -> str:
    """Underscore-free form for cross-convention matching (ifngamma ↔ ifn_gamma)."""
    return s.replace("_", "")


def _fuzzy_match(canon: str, member_set: set[str]) -> str | None:
    """
    Try progressively looser matches:
    1. Exact canonical match
    2. Underscore-stripped match (handles ifngamma ↔ ifn_gamma)
    3. canon starts with member / member starts with canon
    4. Substring containment
    """
    if canon in member_set:
        return canon
    # underscore-normalised comparison
    canon_n = _norm(canon)
    for m in member_set:
        if canon_n == _norm(m):
            return m
    for m in member_set:
        mn = _norm(m)
        if canon_n.startswith(mn) or mn.startswith(canon_n):
            return m
    for m in member_set:
        mn = _norm(m)
        if mn in canon_n or canon_n in mn:
            return m
    return None


def assign_archetypes_to_profile(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'archetype' column (pipe-separated archetype names, or '' for non-immune).
    Modifies only immune layer rows; all others get empty string.
    """
    profile = profile.copy()
    profile["archetype"] = ""

    immune_mask = profile["layer"] == "immune"
    if not immune_mask.any():
        log.warning("archetype: no immune rows found in profile")
        return profile

    member_set = set(_MEMBER_TO_ARCHETYPES.keys())
    unmatched: set[str] = set()

    for i in profile[immune_mask].index:
        raw_name = profile.at[i, "measurement"]
        canon = _canonical(raw_name)
        matched = _fuzzy_match(canon, member_set)
        if matched is not None:
            archs = "|".join(_MEMBER_TO_ARCHETYPES[matched])
            profile.at[i, "archetype"] = archs
        else:
            unmatched.add(raw_name)

    if unmatched:
        log.debug("archetype: %d immune measurements unmatched: %s",
                  len(unmatched), sorted(unmatched)[:10])

    n_assigned = (profile.loc[immune_mask, "archetype"] != "").sum()
    log.info("archetype: %d / %d immune rows assigned to at least one archetype",
             n_assigned, immune_mask.sum())
    return profile


def compute_archetype_synthesis(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-archetype × timepoint activation scores for C003.

    Returns archetype_synthesis.csv schema DataFrame.
    """
    focal_immune = profile[
        (profile["crew_id"] == FOCAL)
        & (profile["layer"] == "immune")
        & (~profile["is_baseline_timepoint"])
        & profile["z_score"].notna()
    ].copy()

    if focal_immune.empty:
        log.warning("archetype: no focal immune post-flight rows with z_score")
        return pd.DataFrame()

    focal_immune["_canon"] = focal_immune["measurement"].apply(_canonical)
    member_set = set(_MEMBER_TO_ARCHETYPES.keys())

    records = []
    timepoints = focal_immune["timepoint"].unique()

    for archetype, members in ARCHETYPES.items():
        member_canon_set = set(members)

        for tp in timepoints:
            tp_rows = focal_immune[focal_immune["timepoint"] == tp]

            # Match rows to this archetype's members
            arch_rows = []
            for _, row in tp_rows.iterrows():
                matched = _fuzzy_match(row["_canon"], member_canon_set)
                if matched is not None:
                    arch_rows.append(row)

            if not arch_rows:
                continue

            arch_df = pd.DataFrame(arch_rows)
            abs_z = arch_df["z_score"].abs()
            n_members = len(arch_df)
            n_elevated = int((abs_z >= 1.0).sum())
            pct_elevated = n_elevated / n_members if n_members > 0 else 0.0
            mean_abs_z = float(abs_z.mean())
            max_abs_z = float(abs_z.max())

            # Dominant direction: majority of elevated members
            elevated_rows = arch_df[abs_z >= 1.0]
            if not elevated_rows.empty:
                n_up = (elevated_rows["z_score"] > 0).sum()
                n_dn = (elevated_rows["z_score"] < 0).sum()
                direction_dominant = "up" if n_up >= n_dn else "down"
                if n_up == n_dn:
                    direction_dominant = "mixed"
            else:
                direction_dominant = "stable"

            # Signed mean z for scoring (direction-aware)
            signed_mean = float(arch_df["z_score"].mean())
            archetype_activation_score = float(
                np.sign(signed_mean) * mean_abs_z * (n_elevated / max(n_members, 1))
            )

            constituents = "|".join(sorted(arch_df["measurement"].tolist()))
            days = arch_df["days_from_launch"].iloc[0] if "days_from_launch" in arch_df.columns else np.nan

            records.append({
                "archetype":                   archetype,
                "timepoint":                   tp,
                "days_from_launch":            days,
                "n_members":                   n_members,
                "n_elevated":                  n_elevated,
                "pct_elevated":                round(pct_elevated, 4),
                "mean_abs_z":                  round(mean_abs_z, 4),
                "max_abs_z":                   round(max_abs_z, 4),
                "direction_dominant":          direction_dominant,
                "archetype_activation_score":  round(archetype_activation_score, 4),
                "constituent_measurements":    constituents,
            })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df = df.sort_values(
        ["archetype", "days_from_launch"],
        na_position="last",
    ).reset_index(drop=True)

    log.info(
        "archetype_synthesis: %d (archetype × timepoint) rows; top activation: %.2f",
        len(df),
        df["archetype_activation_score"].abs().max() if not df.empty else 0,
    )
    return df
