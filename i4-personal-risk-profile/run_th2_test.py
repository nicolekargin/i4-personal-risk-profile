"""
Th2-skew hypothesis test runner.

Loads existing processed CSVs (no upstream re-computation), runs the
six pre-registered predictions, and writes:

  data/processed/archetype_synthesis_cohort.csv
  data/processed/th2_skew_test_results.csv
  data/processed/th2_skew_verdict.json
  data/processed/personal_profile_C003.csv   (updated: + polarization_role)
  data/processed/dashboard_findings.csv      (updated: + th2_skew_tag)

Usage:
  python run_th2_test.py [--debug]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
PROC = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT))

from analysis.th2_skew_test import (
    add_polarization_role,
    add_th2_skew_tags,
    compute_cohort_archetype_synthesis,
    run_th2_skew_test,
)


def setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    log = logging.getLogger("run_th2_test")

    log.info("Loading processed CSVs …")
    profile   = pd.read_csv(PROC / "personal_profile_C003.csv", low_memory=False)
    narrative = pd.read_csv(PROC / "narrative_ranking.csv")
    dashboard = pd.read_csv(PROC / "dashboard_findings.csv")

    profile["is_baseline_timepoint"] = profile["is_baseline_timepoint"].astype(bool)
    log.info("profile: %d rows; narrative: %d; dashboard: %d",
             len(profile), len(narrative), len(dashboard))

    # ── 1. Cohort archetype synthesis ─────────────────────────────────────────
    log.info(
        "Stage 1: cohort archetype synthesis "
        "(fragility-filtered cohort; both-elevated for C003) …"
    )
    cohort_synth = compute_cohort_archetype_synthesis(
        profile, fragility_only_for_cohort=True
    )
    path = PROC / "archetype_synthesis_cohort.csv"
    cohort_synth.to_csv(path, index=False)
    log.info("  ✓ archetype_synthesis_cohort.csv  (%d rows)", len(cohort_synth))

    # ── 2. Run predictions ────────────────────────────────────────────────────
    log.info("Stage 2: running 6 pre-registered predictions …")
    results_df, verdict = run_th2_skew_test(cohort_synth, narrative, profile=profile)

    path = PROC / "th2_skew_test_results.csv"
    results_df.to_csv(path, index=False)
    log.info("  ✓ th2_skew_test_results.csv  (%d rows)", len(results_df))

    path = PROC / "th2_skew_verdict.json"
    path.write_text(json.dumps(verdict, indent=2))
    log.info("  ✓ th2_skew_verdict.json  — verdict: %s", verdict["verdict"])

    # ── 3. Add polarization_role to profile ───────────────────────────────────
    log.info("Stage 3: adding polarization_role to profile …")
    profile = add_polarization_role(profile)
    path = PROC / "personal_profile_C003.csv"
    profile.to_csv(path, index=False)
    log.info("  ✓ personal_profile_C003.csv  (%d rows, %d cols)",
             len(profile), profile.shape[1])

    # ── 4. Add th2_skew_tag to dashboard findings ─────────────────────────────
    log.info("Stage 4: adding th2_skew_tag to dashboard_findings …")
    dashboard = add_th2_skew_tags(dashboard, profile)
    path = PROC / "dashboard_findings.csv"
    dashboard.to_csv(path, index=False)
    log.info("  ✓ dashboard_findings.csv  (%d rows, %d cols)",
             len(dashboard), dashboard.shape[1])

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("")
    log.info("━━━ Verdict ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  %s  (%d/%d supported, %d mixed)",
             verdict["verdict"].upper(),
             verdict["n_supported"], verdict["n_total"], verdict["n_mixed"])
    log.info("  Framing: %s", verdict["framing_sentence"])
    if verdict["caveat"]:
        log.info("  Caveat:  %s", verdict["caveat"])
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    log.info("run_th2_test complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    setup_logging(args.debug)
    main()
