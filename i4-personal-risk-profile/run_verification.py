"""
Verification, Robustness, and Dashboard-Ready Synthesis Pipeline

Runs on top of the base pipeline outputs (personal_profile_C003.csv,
narrative_ranking.csv, recovery_kinetics_C003.csv) and produces:

Updated CSVs (extended columns):
  personal_profile_C003.csv       — + fragility, robust-z, methods_concordance,
                                      archetype, literature_status
  narrative_ranking.csv           — + is_baseline_fragile, fragility_reason,
                                      z_score_robust_at_peak, methods_concordance_at_peak

New CSVs:
  archetype_synthesis.csv
  headline_trajectories.csv
  dashboard_findings.csv

New docs:
  docs/LITERATURE_CONTEXT.md
"""
import logging
import sys
from pathlib import Path

import pandas as pd

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent
PROC    = ROOT / "data" / "processed"
DOCS    = ROOT / "docs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("run_verification")


def main() -> None:
    # ── 1. Load existing pipeline outputs ─────────────────────────────────────
    log.info("Loading pipeline outputs …")
    profile   = pd.read_csv(PROC / "personal_profile_C003.csv", low_memory=False)
    narrative = pd.read_csv(PROC / "narrative_ranking.csv")
    kinetics  = pd.read_csv(PROC / "recovery_kinetics_C003.csv")
    concordance = pd.read_csv(PROC / "cohort_concordance.csv")

    log.info("profile: %d rows, narrative: %d, kinetics: %d",
             len(profile), len(narrative), len(kinetics))

    # is_baseline_timepoint may have been stored as bool or 0/1
    profile["is_baseline_timepoint"] = profile["is_baseline_timepoint"].astype(bool)

    # ── 2. verify.py — fragility + robust z-scores ────────────────────────────
    log.info("Stage 2: verify — fragility flags + robust (median+MAD) z-scores …")
    from analysis.verify import run_verification
    profile = run_verification(profile)

    # ── 3. archetype.py — assign archetypes + synthesis CSV ──────────────────
    log.info("Stage 3: archetype — assign archetypes …")
    from analysis.archetype import assign_archetypes_to_profile, compute_archetype_synthesis
    profile = assign_archetypes_to_profile(profile)
    archetype_df = compute_archetype_synthesis(profile)

    # ── 4. literature_context.py — annotate + write docs ─────────────────────
    log.info("Stage 4: literature_context — annotate …")
    from analysis.literature_context import annotate_literature_context, write_literature_context_md
    profile = annotate_literature_context(profile)
    write_literature_context_md(DOCS / "LITERATURE_CONTEXT.md")

    # ── 5. Update narrative ranking with verify columns ───────────────────────
    log.info("Stage 5: merging verify columns into narrative_ranking …")
    focal_profile = profile[profile["crew_id"] == "C003"].copy()

    # For each narrative row, pull verify/archetype/literature columns at peak TP
    def _enrich_narrative_row(nr: pd.Series) -> pd.Series:
        layer = nr["layer"]
        measurement = nr["measurement"]
        site = nr.get("site", None)
        peak_tp = nr["peak_timepoint"]

        mask = (
            (focal_profile["layer"] == layer)
            & (focal_profile["measurement"] == measurement)
            & (focal_profile["timepoint"] == peak_tp)
        )
        if pd.isna(site) or site is None:
            mask &= focal_profile["site"].isna()
        else:
            mask &= focal_profile["site"] == site

        rows = focal_profile[mask]
        if rows.empty:
            nr["is_baseline_fragile"]       = False
            nr["fragility_reason"]          = ""
            nr["z_score_robust_at_peak"]    = float("nan")
            nr["methods_concordance_at_peak"] = "unknown"
            return nr

        r = rows.iloc[0]
        nr["is_baseline_fragile"]         = r.get("is_baseline_fragile", False)
        nr["fragility_reason"]            = r.get("fragility_reason", "")
        nr["z_score_robust_at_peak"]      = r.get("z_score_robust", float("nan"))
        nr["methods_concordance_at_peak"] = r.get("methods_concordance", "unknown")
        return nr

    narrative = narrative.apply(_enrich_narrative_row, axis=1)

    # ── 6. Build dashboard files ──────────────────────────────────────────────
    log.info("Stage 6: building dashboard_findings and headline_trajectories …")
    from analysis.dashboard_export import build_dashboard_findings, build_headline_trajectories
    dashboard_df     = build_dashboard_findings(narrative, profile, kinetics)
    trajectories_df  = build_headline_trajectories(narrative, profile)

    # ── 7. Write outputs ──────────────────────────────────────────────────────
    log.info("Stage 7: writing updated and new CSVs …")

    # Updated profile (all crew, with new columns)
    profile.to_csv(PROC / "personal_profile_C003.csv", index=False)
    log.info("  ✓ personal_profile_C003.csv  (%d rows, %d cols)",
             len(profile), profile.shape[1])

    # Updated narrative ranking
    narrative.to_csv(PROC / "narrative_ranking.csv", index=False)
    log.info("  ✓ narrative_ranking.csv  (%d rows, %d cols)",
             len(narrative), narrative.shape[1])

    # New CSVs
    archetype_df.to_csv(PROC / "archetype_synthesis.csv", index=False)
    log.info("  ✓ archetype_synthesis.csv  (%d rows)", len(archetype_df))

    trajectories_df.to_csv(PROC / "headline_trajectories.csv", index=False)
    log.info("  ✓ headline_trajectories.csv  (%d rows)", len(trajectories_df))

    dashboard_df.to_csv(PROC / "dashboard_findings.csv", index=False)
    log.info("  ✓ dashboard_findings.csv  (%d rows)", len(dashboard_df))

    log.info("Verification pipeline complete.")


if __name__ == "__main__":
    main()
