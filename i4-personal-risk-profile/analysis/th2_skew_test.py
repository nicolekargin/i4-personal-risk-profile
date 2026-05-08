"""
Th2-skew hypothesis test for C003's idiosyncratic immune phenotype.

Tests whether C003's idiosyncratic immune deviations at R+1 fit a
Th2/regulatory/Th17-skewed pattern with reciprocal Th1 attenuation —
a recognisable immunological signature distinct from the cohort's
shared acute-phase response.

Six pre-registered falsifiable predictions.  See PIPELINE.md for
threshold justifications and pre-registration statement.

Outputs (written by run_th2_test.py):
  archetype_synthesis_cohort.csv   — per-archetype × crew × timepoint scores
  th2_skew_test_results.csv        — one row per prediction
  th2_skew_verdict.json            — verdict + framing sentence
"""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .archetype import ARCHETYPES, _canonical

log = logging.getLogger(__name__)

FOCAL   = "C003"
COHORT  = ["C001", "C002", "C004"]

# ── Pre-registered thresholds (do not tune post-hoc) ──────────────────────────
# See PIPELINE.md §Th2-skew hypothesis test
_FOLD_THRESHOLD     = 2.0   # C003 score must be ≥ this multiple of the cohort median
_ACUTE_SD_THRESHOLD = 1.0   # P5: C003 acute-phase within this many SDs of cohort mean
_MIN_ROBUST_MEMBERS = 2     # minimum both-elevated archetype members to compute a score

# ── Strict matching — replaces the too-broad _fuzzy_match from archetype.py ───
# Root cause of the fix: _fuzzy_match's startswith step allows "il22".startswith("il2"),
# causing IL-22 to be false-positively matched as IL-2 (Th1), producing a spurious
# Th1 activation score for C003 equal to the real IL-22 Th17 score.
# _strict_match uses only exact or underscore-stripped equality.

# Explicit aliases for combined analytes and subunit measurements that the Eve
# panel names differently from the bare ARCHETYPES canonical strings.
_MEASUREMENT_OVERRIDES: dict[str, str] = {
    # IL-17E and IL-25 are measured together in the Eve panel
    "il_17e_il_25":  "th17_response",
    # IL-12 p40 subunit — in Eve panel as il_12p40, not il_12
    "il_12p40":      "th1_polarization",
    # IL-12 p70 — in Eve panel as il_12p70; ARCHETYPES has il_12_p70
    "il_12p70":      "th1_polarization",
}


def _strict_match(canon: str, member_set: set[str]) -> str | None:
    """
    Strict archetype member match: exact canonical or underscore-stripped equality
    only.  Does NOT use startswith or substring — those are too broad given the
    Eve panel's naming (e.g., 'il22' would false-positively startswith 'il2').
    """
    if canon in member_set:
        return canon
    canon_n = canon.replace("_", "")
    for m in member_set:
        if canon_n == m.replace("_", ""):
            return m
    return None

# Archetypes under test for each prediction
_TH2_ARCH       = "th2_polarization"
_REG_ARCH       = "regulatory_response"
_TH17_ARCH      = "th17_response"
_TH1_ARCH       = "th1_polarization"
_ACUTE_ARCH     = "acute_phase_response"

_POLARIZATION_MAP = [
    ("th1",        "th1_polarization"),
    ("th2",        "th2_polarization"),
    ("th17",       "th17_response"),
    ("regulatory", "regulatory_response"),
    ("acute_phase","acute_phase_response"),
]


# ── Cohort archetype synthesis ────────────────────────────────────────────────

def compute_cohort_archetype_synthesis(
    profile: pd.DataFrame,
    *,
    fragility_only_for_cohort: bool = False,
) -> pd.DataFrame:
    """
    Compute per-archetype × timepoint × crew_id activation scores for all
    four crew members.

    By default (fragility_only_for_cohort=False) all crew members are
    filtered to methods_concordance = 'both-elevated'.

    When fragility_only_for_cohort=True (hypothesis-test refinement):
      - FOCAL (C003): still filtered to methods_concordance = 'both-elevated'
      - Cohort (C001/C002/C004): filtered to is_baseline_fragile = False only
        (fragility-filtered denominator — excludes measurement artifacts but
        does not require both statistical methods to independently confirm the
        deviation).  Documented in PIPELINE.md §Hypothesis Test Methodology
        Refinement.

    Schema mirrors archetype_synthesis.csv plus a leading crew_id column.
    The additional column insufficient_data (bool) flags archetypes where
    n_members_matched < _MIN_ROBUST_MEMBERS so downstream code can exclude
    them from comparisons.
    """
    base_mask = (
        (profile["layer"] == "immune")
        & (~profile["is_baseline_timepoint"].astype(bool))
        & profile["z_score"].notna()
    )

    if fragility_only_for_cohort:
        focal_immune = profile[
            base_mask
            & (profile["crew_id"] == FOCAL)
            & (profile["methods_concordance"] == "both-elevated")
        ].copy()
        cohort_immune = profile[
            base_mask
            & (profile["crew_id"] != FOCAL)
            & (~profile["is_baseline_fragile"].astype(bool))
        ].copy()
        immune = pd.concat([focal_immune, cohort_immune], ignore_index=True)
        log.info(
            "cohort filter: fragility-only for cohort; C003=%d rows, cohort=%d rows",
            len(focal_immune), len(cohort_immune),
        )
    else:
        # Filter: immune, post-flight, both-elevated, valid z_score
        immune = profile[
            base_mask
            & (profile["methods_concordance"] == "both-elevated")
        ].copy()

    immune["_canon"] = immune["measurement"].apply(_canonical)

    records = []
    for crew_id in sorted(profile["crew_id"].unique()):
        crew_rows = immune[immune["crew_id"] == crew_id]

        for arch_name, arch_members in ARCHETYPES.items():
            member_canon_set = set(arch_members)

            for tp in sorted(crew_rows["timepoint"].unique()):
                tp_rows = crew_rows[crew_rows["timepoint"] == tp]

                arch_rows = []
                for _, row in tp_rows.iterrows():
                    canon = row["_canon"]
                    # Check explicit overrides first, then strict match
                    override_arch = _MEASUREMENT_OVERRIDES.get(canon)
                    if override_arch is not None:
                        matched = (override_arch == arch_name)
                    else:
                        matched = _strict_match(canon, member_canon_set) is not None
                    if matched:
                        arch_rows.append(row)

                # Record even if 0 members so insufficient_data is explicit
                n_matched = len(arch_rows)
                insufficient = n_matched < _MIN_ROBUST_MEMBERS

                if n_matched == 0:
                    days = (
                        tp_rows["days_from_launch"].iloc[0]
                        if not tp_rows.empty and "days_from_launch" in tp_rows.columns
                        else np.nan
                    )
                    records.append({
                        "crew_id":                    crew_id,
                        "archetype":                  arch_name,
                        "timepoint":                  tp,
                        "days_from_launch":           days,
                        "n_members":                  0,
                        "n_elevated":                 0,
                        "pct_elevated":               0.0,
                        "mean_abs_z":                 np.nan,
                        "max_abs_z":                  np.nan,
                        "direction_dominant":         "stable",
                        "archetype_activation_score": np.nan,
                        "insufficient_data":          True,
                        "constituent_measurements":   "",
                    })
                    continue

                arch_df  = pd.DataFrame(arch_rows)
                abs_z    = arch_df["z_score"].abs()
                n_elev   = int((abs_z >= 1.0).sum())
                mean_abs = float(abs_z.mean())
                max_abs  = float(abs_z.max())

                elev_rows = arch_df[abs_z >= 1.0]
                if not elev_rows.empty:
                    n_up = int((elev_rows["z_score"] > 0).sum())
                    n_dn = int((elev_rows["z_score"] < 0).sum())
                    direction = "up" if n_up > n_dn else ("down" if n_dn > n_up else "mixed")
                else:
                    direction = "stable"

                signed_mean = float(arch_df["z_score"].mean())
                act_score = float(
                    np.sign(signed_mean) * mean_abs * (n_elev / max(n_matched, 1))
                )
                days = (
                    arch_df["days_from_launch"].iloc[0]
                    if "days_from_launch" in arch_df.columns
                    else np.nan
                )

                records.append({
                    "crew_id":                    crew_id,
                    "archetype":                  arch_name,
                    "timepoint":                  tp,
                    "days_from_launch":           float(days) if not pd.isna(days) else np.nan,
                    "n_members":                  n_matched,
                    "n_elevated":                 n_elev,
                    "pct_elevated":               round(n_elev / n_matched, 4),
                    "mean_abs_z":                 round(mean_abs, 4),
                    "max_abs_z":                  round(max_abs, 4),
                    "direction_dominant":         direction,
                    "archetype_activation_score": round(act_score, 4) if not np.isnan(act_score) else np.nan,
                    "insufficient_data":          insufficient,
                    "constituent_measurements":   "|".join(sorted(arch_df["measurement"].tolist())),
                })

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values(
        ["crew_id", "archetype", "days_from_launch"],
        na_position="last",
    ).reset_index(drop=True)

    log.info(
        "cohort archetype synthesis: %d rows; %d crew × %d archetypes × timepoints",
        len(df),
        df["crew_id"].nunique(),
        df["archetype"].nunique(),
    )
    return df


# ── Prediction helpers ────────────────────────────────────────────────────────

def _r1_scores(
    synth: pd.DataFrame,
    arch: str,
    tp: str = "R+1",
) -> dict[str, dict]:
    """
    Extract activation scores and metadata at a given timepoint for an archetype.
    Returns {crew_id: {score, direction, n_members, insufficient}}.
    """
    rows = synth[(synth["archetype"] == arch) & (synth["timepoint"] == tp)]
    out: dict[str, dict] = {}
    for _, r in rows.iterrows():
        out[r["crew_id"]] = {
            "score":        r["archetype_activation_score"],
            "direction":    r["direction_dominant"],
            "n_members":    r["n_members"],
            "insufficient": bool(r["insufficient_data"]),
        }
    return out


def _cohort_stats(
    scores: dict[str, dict],
    cohort_ids: list[str],
) -> tuple[float, float, list[float]]:
    """
    Compute cohort (non-focal) median and SD, excluding insufficient entries.
    Returns (median, sd, valid_values_list).
    """
    vals = [
        scores[c]["score"]
        for c in cohort_ids
        if c in scores and not scores[c]["insufficient"] and not np.isnan(scores[c]["score"])
    ]
    if len(vals) == 0:
        return np.nan, np.nan, vals
    med = float(np.median(vals))
    sd  = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
    return med, sd, vals


def _ratio_label(c003: float, med: float) -> str:
    if np.isnan(med) or abs(med) < 1e-6:
        return "cohort_median≈0_or_nan"
    return f"{c003 / med:.2f}×"


# ── Six predictions ───────────────────────────────────────────────────────────

def _pred_polarization(
    pred_id: int,
    arch: str,
    pred_text: str,
    synth: pd.DataFrame,
) -> dict:
    """
    Generic check for Predictions 1–3: C003 archetype score ≥ 2× cohort median
    AND C003 direction_dominant = 'up'.
    """
    scores = _r1_scores(synth, arch)
    c003   = scores.get(FOCAL, {})
    c003_score = c003.get("score", np.nan)
    c003_dir   = c003.get("direction", "stable")
    c003_insuf = c003.get("insufficient", True)

    cohort_med, _, cohort_vals = _cohort_stats(scores, COHORT)

    # Threshold logic:
    #   If cohort median > 0: C003 must be ≥ FOLD_THRESHOLD × cohort_median
    #   If cohort median ≤ 0: any positive C003 score satisfies the criterion
    #     (documented: 2× a non-positive number is more negative, not a useful bound)
    if c003_insuf or np.isnan(c003_score):
        result = "mixed"
        evidence = (
            f"C003 has insufficient data (<{_MIN_ROBUST_MEMBERS} both-elevated members) "
            f"for {arch} at R+1. Cannot evaluate threshold."
        )
    elif c003_dir != "up":
        result = "not_supported"
        evidence = (
            f"C003 {arch} direction_dominant='{c003_dir}' (required 'up'). "
            f"Score={c003_score:.3f}, cohort median={cohort_med:.3f}."
        )
    elif np.isnan(cohort_med):
        # All cohort members have insufficient data; C003 is uniquely elevated
        result = "mixed"
        evidence = (
            f"C003 {arch} score={c003_score:.3f} (direction=up). "
            f"All cohort members have insufficient data — ratio cannot be computed. "
            f"C003 uniquely elevated in this archetype."
        )
    elif cohort_med <= 0:
        # Cohort ≤ 0 means cohort is stable/suppressed; any positive C003 is elevated
        result = "supported"
        evidence = (
            f"C003 {arch} score={c003_score:.3f} (direction=up) vs cohort median={cohort_med:.3f}. "
            f"Cohort median ≤ 0; C003 positive score meets criterion by definition. "
            f"Cohort values: {[round(v,3) for v in cohort_vals]}."
        )
    else:
        ratio = c003_score / cohort_med
        meets = ratio >= _FOLD_THRESHOLD
        result = "supported" if meets else "not_supported"
        evidence = (
            f"C003 {arch} score={c003_score:.3f} (direction={c003_dir}) vs "
            f"cohort median={cohort_med:.3f} ({_ratio_label(c003_score, cohort_med)}). "
            f"Threshold: ≥{_FOLD_THRESHOLD}×. "
            f"Cohort values: {[round(v,3) for v in cohort_vals]}."
        )

    return {
        "prediction_id":   pred_id,
        "prediction_text": pred_text,
        "c003_value":      round(c003_score, 4) if not np.isnan(c003_score) else None,
        "cohort_median":   round(cohort_med, 4) if not np.isnan(cohort_med) else None,
        "cohort_values":   str([round(v, 3) for v in cohort_vals]),
        "result":          result,
        "evidence":        evidence,
    }


def _pred4_th1_attenuation(synth: pd.DataFrame) -> dict:
    """
    Prediction 4: Th1 attenuation.
    C003's Th1 score ≤ cohort median, OR C003 direction 'down'/'stable'
    while ≥2 cohort members show 'up'.
    """
    scores = _r1_scores(synth, _TH1_ARCH)
    c003   = scores.get(FOCAL, {})
    c003_score = c003.get("score", np.nan)
    c003_dir   = c003.get("direction", "stable")
    c003_insuf = c003.get("insufficient", True)

    cohort_med, _, cohort_vals = _cohort_stats(scores, COHORT)
    n_cohort_up = sum(
        1 for c in COHORT
        if c in scores and not scores[c]["insufficient"] and scores[c]["direction"] == "up"
    )

    if c003_insuf or np.isnan(c003_score):
        # C003 has no both-elevated Th1 members → effectively stable/not activating Th1
        # Check second condition: ≥2 cohort "up"
        if n_cohort_up >= 2:
            result = "supported"
            evidence = (
                f"C003 Th1 has insufficient data (score=NaN; direction=stable). "
                f"{n_cohort_up}/3 cohort members show Th1 'up', so C003 is NOT amplifying Th1. "
                f"Cohort values: {[round(v,3) for v in cohort_vals]}."
            )
        elif c003_dir in ("down", "stable"):
            # C003 stable/down is consistent with attenuation even without cohort going up
            result = "supported"
            evidence = (
                f"C003 Th1 score=NaN (direction='{c003_dir}'; no both-elevated Th1 members). "
                f"C003 is not amplifying Th1 at R+1. "
                f"Cohort values: {[round(v,3) for v in cohort_vals]}."
            )
        else:
            result = "mixed"
            evidence = (
                f"C003 Th1 insufficient data and direction='{c003_dir}'. Cannot evaluate. "
                f"Cohort values: {[round(v,3) for v in cohort_vals]}."
            )
    elif np.isnan(cohort_med):
        # All cohort insufficient → only check C003 direction
        if c003_dir in ("down", "stable"):
            result = "supported"
            evidence = (
                f"C003 Th1 score={c003_score:.3f} (direction='{c003_dir}'). "
                f"Cohort all insufficient. C003 not amplifying Th1 — attenuation criterion met."
            )
        else:
            result = "not_supported"
            evidence = (
                f"C003 Th1 score={c003_score:.3f} (direction='{c003_dir}'). "
                f"Cohort all insufficient. C003 Th1 is elevated, not attenuated."
            )
    else:
        cond_a = c003_score <= cohort_med
        cond_b = c003_dir in ("down", "stable") and n_cohort_up >= 2
        result = "supported" if (cond_a or cond_b) else "not_supported"
        evidence = (
            f"C003 Th1 score={c003_score:.3f} (direction='{c003_dir}') vs "
            f"cohort median={cohort_med:.3f}. "
            f"Cond-A (score ≤ median): {cond_a}. "
            f"Cond-B (C003 down/stable AND ≥2 cohort up): "
            f"direction={c003_dir}, n_cohort_up={n_cohort_up}. "
            f"Cohort values: {[round(v,3) for v in cohort_vals]}."
        )

    return {
        "prediction_id":   4,
        "prediction_text": (
            "Th1 archetype activation_score for C003 at R+1 ≤ cohort median, "
            "OR C003 direction_dominant in {down, stable} while ≥2 cohort members show 'up'."
        ),
        "c003_value":      round(c003_score, 4) if not np.isnan(c003_score) else None,
        "cohort_median":   round(cohort_med, 4) if not np.isnan(cohort_med) else None,
        "cohort_values":   str([round(v, 3) for v in cohort_vals]),
        "result":          result,
        "evidence":        evidence,
    }


def _pred5_acute_negative_control(synth: pd.DataFrame) -> dict:
    """
    Prediction 5 (negative control): C003's acute-phase score is within 1 SD of the
    cohort mean — i.e., the acute-phase response is genuinely shared, not C003-specific.
    """
    scores = _r1_scores(synth, _ACUTE_ARCH)
    c003   = scores.get(FOCAL, {})
    c003_score = c003.get("score", np.nan)
    c003_insuf = c003.get("insufficient", True)

    cohort_med, cohort_sd, cohort_vals = _cohort_stats(scores, COHORT)
    cohort_mean = float(np.mean(cohort_vals)) if cohort_vals else np.nan

    if c003_insuf or np.isnan(c003_score):
        result = "mixed"
        evidence = (
            f"C003 acute_phase_response has insufficient both-elevated members. "
            f"Cannot evaluate negative control. Cohort values: {[round(v,3) for v in cohort_vals]}."
        )
    elif np.isnan(cohort_mean) or np.isnan(cohort_sd):
        result = "mixed"
        evidence = (
            f"C003 acute_phase score={c003_score:.3f}; insufficient cohort data for SD. "
            f"Cohort values: {[round(v,3) for v in cohort_vals]}."
        )
    else:
        deviation = abs(c003_score - cohort_mean)
        within = deviation <= _ACUTE_SD_THRESHOLD * cohort_sd if cohort_sd > 0 else (c003_score == cohort_mean)
        result = "supported" if within else "not_supported"
        evidence = (
            f"C003 acute_phase score={c003_score:.3f}; "
            f"cohort mean={cohort_mean:.3f}, SD={cohort_sd:.3f}. "
            f"|C003 - mean| = {deviation:.3f} vs threshold {_ACUTE_SD_THRESHOLD}×SD={_ACUTE_SD_THRESHOLD * cohort_sd:.3f}. "
            f"Within threshold: {within}. "
            f"Cohort values: {[round(v,3) for v in cohort_vals]}."
        )

    return {
        "prediction_id":   5,
        "prediction_text": (
            f"Acute-phase archetype activation_score for C003 at R+1 is within "
            f"{_ACUTE_SD_THRESHOLD} SD of the cohort mean (negative control: shared signal)."
        ),
        "c003_value":      round(c003_score, 4) if not np.isnan(c003_score) else None,
        "cohort_median":   round(cohort_mean, 4) if not np.isnan(cohort_mean) else None,
        "cohort_values":   str([round(v, 3) for v in cohort_vals]),
        "result":          result,
        "evidence":        evidence,
    }


_RECLASSIFY_TP = "R+1"


def _reclassify_ambiguous(
    imm_nar: pd.DataFrame,
    profile: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reclassify 'ambiguous' concordance_class as 'idiosyncratic' when:
      - C003's z_score at R+1 > 1 (unambiguously up at the primary test timepoint)
      - ≥2 cohort members have |z_score| < 1 at R+1 (stable)

    Documented in PIPELINE.md §Hypothesis Test Methodology Refinement.
    """
    r1 = profile[profile["timepoint"] == _RECLASSIFY_TP]
    c003_r1 = r1[r1["crew_id"] == FOCAL]
    cohort_r1 = r1[r1["crew_id"].isin(COHORT)]

    reclassify_idx: list = []
    for idx, row in imm_nar.iterrows():
        if row["concordance_class"] != "ambiguous":
            continue
        m = row["measurement"]
        c003_row = c003_r1[c003_r1["measurement"] == m]
        if c003_row.empty:
            continue
        c003_z = c003_row["z_score"].values[0]
        if pd.isna(c003_z) or c003_z <= 1.0:
            continue
        n_stable = sum(
            1
            for c in COHORT
            for c_row in [cohort_r1[(cohort_r1["crew_id"] == c) & (cohort_r1["measurement"] == m)]]
            if not c_row.empty and not pd.isna(c_row["z_score"].values[0])
            and abs(c_row["z_score"].values[0]) < 1.0
        )
        if n_stable >= 2:
            reclassify_idx.append(idx)
            log.info(
                "P6 reclassify: %s ambiguous → idiosyncratic "
                "(C003 z=%.2f at R+1, %d cohort stable)",
                m, c003_z, n_stable,
            )

    if reclassify_idx:
        imm_nar = imm_nar.copy()
        imm_nar.loc[reclassify_idx, "concordance_class"] = "idiosyncratic"
    return imm_nar


def _pred6_member_concordance(
    narrative: pd.DataFrame,
    profile: pd.DataFrame | None = None,
) -> dict:
    """
    Prediction 6: Within Th2/regulatory/Th17, C003's elevated members are
    predominantly idiosyncratic. Within acute-phase, predominantly concordant.

    When profile is provided, ambiguous concordance_class entries are
    reclassified using raw R+1 z-scores before counting — see
    _reclassify_ambiguous for the reclassification rule.
    """
    imm_nar = narrative[narrative["layer"] == "immune"].copy()
    if profile is not None:
        imm_nar = _reclassify_ambiguous(imm_nar, profile)

    def _classify_arch(arch_flag: str) -> dict:
        """Return concordance_class breakdown for members of a polarization category."""
        matching = imm_nar[
            imm_nar["measurement"].apply(
                lambda m: _polarization_role_for_measurement(m) == arch_flag
            )
        ]
        return dict(matching["concordance_class"].value_counts()) if not matching.empty else {}

    th2_counts  = _classify_arch("th2")
    reg_counts  = _classify_arch("regulatory")
    th17_counts = _classify_arch("th17")
    th1_counts  = _classify_arch("th1")
    acute_counts= _classify_arch("acute_phase")

    # Combine Th2/regulatory/Th17
    skew_counts: dict[str, int] = {}
    for d in [th2_counts, reg_counts, th17_counts]:
        for k, v in d.items():
            skew_counts[k] = skew_counts.get(k, 0) + v

    n_skew_total  = sum(skew_counts.values())
    n_skew_idio   = skew_counts.get("idiosyncratic", 0)
    pct_skew_idio = n_skew_idio / n_skew_total if n_skew_total > 0 else 0.0

    n_acute_total = sum(acute_counts.values())
    n_acute_conc  = acute_counts.get("concordant", 0)
    pct_acute_conc = n_acute_conc / n_acute_total if n_acute_total > 0 else 0.0

    # "predominantly" = strict majority (>50%)
    skew_ok  = pct_skew_idio  > 0.5 and n_skew_total  >= 2
    acute_ok = pct_acute_conc > 0.5 and n_acute_total >= 1

    if skew_ok and acute_ok:
        result = "supported"
    elif skew_ok or acute_ok:
        result = "mixed"
    else:
        result = "not_supported"

    evidence = (
        f"Th2/reg/Th17 members: {n_skew_idio}/{n_skew_total} idiosyncratic "
        f"({pct_skew_idio:.0%}); breakdown: {skew_counts}. "
        f"Acute-phase members: {n_acute_conc}/{n_acute_total} concordant "
        f"({pct_acute_conc:.0%}); breakdown: {acute_counts}. "
        f"Th1 breakdown: {th1_counts}."
    )

    return {
        "prediction_id":   6,
        "prediction_text": (
            "Th2/regulatory/Th17 members predominantly idiosyncratic in C003; "
            "acute-phase members predominantly concordant."
        ),
        "c003_value":      round(pct_skew_idio, 4),
        "cohort_median":   None,
        "cohort_values":   str(skew_counts),
        "result":          result,
        "evidence":        evidence,
    }


# ── Polarization role helpers ─────────────────────────────────────────────────

def _polarization_role_for_measurement(measurement: str) -> str:
    """Map a raw measurement name to a polarization role string."""
    canon = _canonical(str(measurement))
    # Check explicit overrides first (handles combined analytes like il_17e_il_25)
    override_arch = _MEASUREMENT_OVERRIDES.get(canon)
    if override_arch is not None:
        for role, arch_name in _POLARIZATION_MAP:
            if arch_name == override_arch:
                return role
    for role, arch_name in _POLARIZATION_MAP:
        member_set = set(ARCHETYPES.get(arch_name, []))
        if _strict_match(canon, member_set) is not None:
            return role
    return "other"


def add_polarization_role(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Add polarization_role column to the master profile.
    Only meaningful for immune layer; non-immune rows receive 'not_applicable'.
    """
    profile = profile.copy()
    profile["polarization_role"] = "not_applicable"
    immune_mask = profile["layer"] == "immune"
    profile.loc[immune_mask, "polarization_role"] = (
        profile.loc[immune_mask, "measurement"].apply(_polarization_role_for_measurement)
    )
    n_assigned = (profile.loc[immune_mask, "polarization_role"] != "other").sum()
    log.info(
        "polarization_role: %d/%d immune rows assigned (not 'other' or 'not_applicable')",
        n_assigned, immune_mask.sum(),
    )
    return profile


def add_th2_skew_tags(
    dashboard: pd.DataFrame,
    profile: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add th2_skew_tag column to dashboard_findings.

    Values:
      'th2_skew_evidence'        — immune; Th2/regulatory/Th17 role; idiosyncratic; direction up
      'th2_skew_counter_evidence'— immune; Th1 role; direction down (attenuation evidence)
      ''                          — everything else
    """
    dashboard = dashboard.copy()

    # Derive polarization_role for dashboard rows via measurement name lookup
    dashboard["_pol_role"] = dashboard["measurement"].apply(_polarization_role_for_measurement)

    evidence_mask = (
        (dashboard["layer"] == "immune")
        & dashboard["_pol_role"].isin({"th2", "regulatory", "th17"})
        & (dashboard["concordance_class"] == "idiosyncratic")
        & (dashboard["deviation_direction"] == "up")
    )
    counter_mask = (
        (dashboard["layer"] == "immune")
        & (dashboard["_pol_role"] == "th1")
        & (dashboard["deviation_direction"] == "down")
    )

    dashboard["th2_skew_tag"] = ""
    dashboard.loc[evidence_mask,  "th2_skew_tag"] = "th2_skew_evidence"
    dashboard.loc[counter_mask,   "th2_skew_tag"] = "th2_skew_counter_evidence"

    dashboard = dashboard.drop(columns=["_pol_role"])

    n_ev = int(evidence_mask.sum())
    n_ce = int(counter_mask.sum())
    log.info("th2_skew_tags: %d th2_skew_evidence, %d th2_skew_counter_evidence", n_ev, n_ce)
    return dashboard


# ── Top-level test runner ─────────────────────────────────────────────────────

def run_th2_skew_test(
    synth: pd.DataFrame,
    narrative: pd.DataFrame,
    profile: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Run all six predictions.  Returns (results_df, verdict_dict).

    Parameters
    ----------
    synth     : archetype_synthesis_cohort.csv (cohort under fragility filter,
                C003 under both-elevated filter when fragility_only_for_cohort=True)
    narrative : narrative_ranking.csv (for concordance_class per measurement)
    profile   : full personal_profile_C003.csv (all crew); when supplied, P6
                reclassifies ambiguous concordance_class entries using R+1 z-scores
    """
    results = [
        _pred_polarization(
            1, _TH2_ARCH,
            f"Th2 archetype activation_score for C003 at R+1 ≥ {_FOLD_THRESHOLD}× "
            "cohort median AND direction_dominant = 'up'.",
            synth,
        ),
        _pred_polarization(
            2, _REG_ARCH,
            f"Regulatory archetype activation_score for C003 at R+1 ≥ {_FOLD_THRESHOLD}× "
            "cohort median AND direction_dominant = 'up'.",
            synth,
        ),
        _pred_polarization(
            3, _TH17_ARCH,
            f"Th17 archetype activation_score for C003 at R+1 ≥ {_FOLD_THRESHOLD}× "
            "cohort median AND direction_dominant = 'up'.",
            synth,
        ),
        _pred4_th1_attenuation(synth),
        _pred5_acute_negative_control(synth),
        _pred6_member_concordance(narrative, profile=profile),
    ]

    results_df = pd.DataFrame(results)

    n_supported = int((results_df["result"] == "supported").sum())
    n_mixed     = int((results_df["result"] == "mixed").sum())
    n_total     = len(results_df)

    # Effective support: "mixed" counts as 0.5 for verdict purposes
    effective = n_supported + 0.5 * n_mixed

    failed_ids = results_df[results_df["result"] != "supported"]["prediction_id"].tolist()

    if effective >= 5.5:
        verdict   = "strongly supported"
        framing   = (
            "Subject C003 exhibits a Th2/regulatory/Th17-skewed personal immune phenotype "
            "superimposed on the cohort's shared acute-phase response, with reciprocal Th1 attenuation."
        )
        caveat = ""
    elif effective >= 4.5:
        verdict   = "supported with one exception"
        framing   = (
            "Subject C003 exhibits a Th2/regulatory/Th17-skewed personal immune phenotype "
            "superimposed on the cohort's shared acute-phase response, with reciprocal Th1 attenuation."
        )
        caveat = (
            f"Prediction(s) {failed_ids} did not fully meet the pre-registered threshold — "
            "see th2_skew_test_results.csv for details."
        )
    elif effective >= 3.5:
        verdict   = "partially supported"
        framing   = (
            "Subject C003 shows elements of a Th2-skewed personal immune phenotype, "
            "though the pattern is not fully consistent with classical type 2 polarization."
        )
        caveat = f"Predictions {failed_ids} not supported."
    else:
        verdict   = "not supported"
        framing   = (
            "Subject C003 exhibits a broad idiosyncratic immune activation pattern that "
            "does not cleanly match a classical polarization archetype."
        )
        caveat = f"Only {n_supported}/{n_total} predictions supported (threshold: ≥4)."

    verdict_dict = {
        "verdict":          verdict,
        "n_supported":      n_supported,
        "n_mixed":          n_mixed,
        "n_total":          n_total,
        "effective_support":effective,
        "framing_sentence": framing,
        "caveat":           caveat,
        "failed_predictions": failed_ids,
    }

    log.info(
        "th2_skew_test: %d supported, %d mixed, %d not_supported → verdict: %s",
        n_supported, n_mixed, n_total - n_supported - n_mixed, verdict,
    )
    return results_df, verdict_dict
