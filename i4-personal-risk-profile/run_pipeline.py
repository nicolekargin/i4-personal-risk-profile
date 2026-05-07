"""
End-to-end pipeline for the Personalized Health Orbit — Subject C003.

Produces four output files in data/processed/:
  personal_profile_C003.csv
  recovery_kinetics_C003.csv
  cohort_concordance.csv
  narrative_ranking.csv

Usage:
  python run_pipeline.py [--debug]
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from analysis.load import load_cbc, load_cytokines, load_metagenomics_ko
from analysis.parse import parse_cbc, parse_cytokines, parse_metagenomics_ko
from analysis.transform import apply_transforms, filter_zero_inflated
from analysis.baseline import compute_baselines
from analysis.deviation import compute_deviations, assemble_master_profile
from analysis.kinetics import compute_kinetics
from analysis.concordance import compute_concordance
from analysis.narrative import compute_narrative_ranking

OUT_DIR = Path(__file__).parent / "data" / "processed"


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def run() -> dict[str, pd.DataFrame]:
    t0 = time.time()
    log = logging.getLogger("pipeline")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load ──────────────────────────────────────────────────────────────
    log.info("=== LOAD ===")
    raw_cbc   = load_cbc()
    raw_cyto  = load_cytokines()
    raw_meta  = load_metagenomics_ko()

    # ── 2. Parse ─────────────────────────────────────────────────────────────
    log.info("=== PARSE ===")
    cbc_long  = parse_cbc(raw_cbc)
    cyto_long = parse_cytokines(raw_cyto)
    meta_long = parse_metagenomics_ko(raw_meta)

    # ── 3. Transform ─────────────────────────────────────────────────────────
    log.info("=== TRANSFORM ===")
    cbc_t  = apply_transforms(cbc_long)
    cyto_t = apply_transforms(cyto_long)
    meta_t = apply_transforms(meta_long)

    # Filter zero-inflated metagenomics features (≥50% pre-flight zeros)
    meta_t = filter_zero_inflated(meta_t, threshold=0.5)

    # ── 4. Baseline ──────────────────────────────────────────────────────────
    log.info("=== BASELINE ===")
    cbc_b,  cbc_boots  = compute_baselines(cbc_t)
    cyto_b, cyto_boots = compute_baselines(cyto_t)
    meta_b, meta_boots = compute_baselines(meta_t)

    # ── 5. Deviations ────────────────────────────────────────────────────────
    log.info("=== DEVIATIONS ===")
    cbc_d  = compute_deviations(cbc_b,  cbc_boots)
    cyto_d = compute_deviations(cyto_b, cyto_boots)
    meta_d = compute_deviations(meta_b, meta_boots)

    # ── 6. Assemble master profile ───────────────────────────────────────────
    log.info("=== ASSEMBLE ===")
    combined = pd.concat([cbc_d, cyto_d, meta_d], ignore_index=True)
    profile  = assemble_master_profile(combined)

    path = OUT_DIR / "personal_profile_C003.csv"
    profile.to_csv(path, index=False)
    log.info("Saved %s  (%d rows)", path.name, len(profile))

    # ── 7. Kinetics ──────────────────────────────────────────────────────────
    log.info("=== KINETICS ===")
    kinetics = compute_kinetics(profile)
    path = OUT_DIR / "recovery_kinetics_C003.csv"
    kinetics.to_csv(path, index=False)
    log.info("Saved %s  (%d rows)", path.name, len(kinetics))

    # ── 8. Concordance ───────────────────────────────────────────────────────
    log.info("=== CONCORDANCE ===")
    concordance = compute_concordance(profile)
    path = OUT_DIR / "cohort_concordance.csv"
    concordance.to_csv(path, index=False)
    log.info("Saved %s  (%d rows)", path.name, len(concordance))

    # ── 9. Narrative ranking ─────────────────────────────────────────────────
    log.info("=== NARRATIVE ===")
    ranking = compute_narrative_ranking(profile, concordance)
    path = OUT_DIR / "narrative_ranking.csv"
    ranking.to_csv(path, index=False)
    log.info("Saved %s  (%d rows)", path.name, len(ranking))

    elapsed = time.time() - t0
    log.info("Pipeline complete in %.1f s", elapsed)

    return {
        "profile":     profile,
        "kinetics":    kinetics,
        "concordance": concordance,
        "ranking":     ranking,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    setup_logging(args.debug)
    run()
