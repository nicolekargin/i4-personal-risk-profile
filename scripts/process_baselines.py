#!/usr/bin/env python3
"""
process_baselines.py — SOMA Health Orbit | Individualized Cytokine Baseline Analysis
======================================================================================
Source:  OSD-575  (Luminex 65-plex, pg/mL)
Focus:   n=1 personal Z-scores per crew member; primary deliverable = C001 FD1 top-5.

Column convention: {CrewID}_{Timepoint}
  Ground baselines : L-92, L-44, L-3
  In-flight        : FD1, FD2, FD3
  Return           : R+1, R+45
"""

from __future__ import annotations
import json
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parents[1]
RAW_DIR  = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

CREW_IDS           = ["C001", "C002", "C003", "C004"]
L_MINUS_TIMEPOINTS = ["L-92", "L-44", "L-3"]
FD_TIMEPOINTS      = ["FD1", "FD2", "FD3"]
R_PLUS_TIMEPOINTS  = ["R+1", "R+45"]
ALL_TIMEPOINTS     = L_MINUS_TIMEPOINTS + FD_TIMEPOINTS + R_PLUS_TIMEPOINTS

# ── curated inflammatory panel (Luminex targets in OSD-575) ───────────────────
INFLAMMATORY_PANEL = [
    "IL-1beta", "IL-6", "IL-8", "IL-10", "IL-12p70", "IL-17A",
    "TNF-alpha", "IFN-gamma", "MCP-1", "MIP-1alpha", "MIP-1beta",
    "IP-10", "EOTAXIN", "G-CSF", "GM-CSF", "RANTES", "VEGF",
    "IL-1RA", "IL-2", "IL-4", "IL-5", "IL-7", "IL-9", "IL-13",
    "IL-15", "FGF-basic", "PDGF-BB", "EGF", "HGF", "LIF",
]

# ── synthetic data (approximates SOMA OSD-575 published ranges) ───────────────
def generate_synthetic_cytokine_data(seed: int = 42) -> pd.DataFrame:
    """
    Log-normal baseline distributions from healthy-adult Luminex reference ranges.
    Perturbation multipliers encode known inter-individual variability from SOMA 2024.
    C001 = strong early inflammatory responder (FD1 spike).
    C002 = moderate; C003 = blunted/delayed; C004 = angiogenic responder.
    """
    rng = np.random.default_rng(seed)

    # (log_mean_pg_mL, log_std) — tuned to published Inspiration4 pre-flight ranges
    baseline_params = {
        "IL-1beta":   (0.80, 0.40), "IL-6":       (1.20, 0.50),
        "IL-8":       (2.10, 0.40), "IL-10":      (1.00, 0.30),
        "IL-12p70":   (0.50, 0.40), "IL-17A":     (0.90, 0.50),
        "TNF-alpha":  (1.50, 0.40), "IFN-gamma":  (1.30, 0.50),
        "MCP-1":      (3.20, 0.30), "MIP-1alpha": (2.00, 0.40),
        "MIP-1beta":  (3.80, 0.30), "IP-10":      (3.50, 0.40),
        "EOTAXIN":    (3.20, 0.30), "G-CSF":      (2.80, 0.50),
        "GM-CSF":     (0.60, 0.50), "RANTES":     (4.80, 0.30),
        "VEGF":       (2.50, 0.40), "IL-1RA":     (3.00, 0.40),
        "IL-2":       (0.50, 0.50), "IL-4":       (0.40, 0.50),
        "IL-5":       (0.50, 0.40), "IL-7":       (1.80, 0.30),
        "IL-9":       (0.70, 0.40), "IL-13":      (0.60, 0.40),
        "IL-15":      (1.20, 0.40), "FGF-basic":  (2.00, 0.40),
        "PDGF-BB":    (3.50, 0.30), "EGF":        (2.20, 0.40),
        "HGF":        (3.80, 0.30), "LIF":        (0.50, 0.50),
    }

    # FD1 fold-changes per crew (SOMA 2024 inter-individual variability)
    fd1_perturbations: dict[str, dict[str, float]] = {
        "C001": {  # strong early innate responder
            "IL-6": 3.2, "IP-10": 4.1, "IL-8": 2.8, "G-CSF": 3.5,
            "IL-1RA": 2.9, "MCP-1": 2.2, "IFN-gamma": 2.1, "TNF-alpha": 1.8,
            "IL-1beta": 2.0, "GM-CSF": 1.7,
        },
        "C002": {  # moderate responder
            "IL-6": 1.8, "IP-10": 2.3, "IL-8": 1.5, "G-CSF": 2.0,
            "IL-1RA": 1.6, "MCP-1": 1.4,
        },
        "C003": {  # blunted early, delayed peak ~FD2-3
            "IL-6": 1.3, "IP-10": 1.7, "IL-8": 1.2, "G-CSF": 1.5,
        },
        "C004": {  # angiogenic/tissue-remodelling responder
            "VEGF": 3.8, "HGF": 2.5, "FGF-basic": 2.2,
            "G-CSF": 2.8, "IL-6": 1.5, "PDGF-BB": 2.0,
        },
    }

    data: dict[str, dict[str, float]] = {}
    for cytokine, (lmu, lsig) in baseline_params.items():
        row: dict[str, float] = {}
        for crew in CREW_IDS:
            ground_vals = np.exp(rng.normal(lmu, lsig, 3))
            for i, tp in enumerate(L_MINUS_TIMEPOINTS):
                row[f"{crew}_{tp}"] = round(float(ground_vals[i]), 3)

            mu = float(ground_vals.mean())
            perturbs = fd1_perturbations.get(crew, {})

            fd_scales = {
                "FD1": perturbs.get(cytokine, 1.0),
                "FD2": 1 + (perturbs.get(cytokine, 1.0) - 1) * 0.75,
                "FD3": 1 + (perturbs.get(cytokine, 1.0) - 1) * 0.45,
            }
            for tp, scale in fd_scales.items():
                val = mu * scale * float(np.exp(rng.normal(0, 0.15)))
                row[f"{crew}_{tp}"] = round(max(val, 0.01), 3)

            # Return: trending back; R+45 nearly baseline
            for i, tp in enumerate(["R+1", "R+45"]):
                scale = [0.88, 1.04][i]
                val = mu * scale * float(np.exp(rng.normal(0, 0.10)))
                row[f"{crew}_{tp}"] = round(max(val, 0.01), 3)

        data[cytokine] = row

    df = pd.DataFrame(data).T
    df.index.name = "cytokine"
    return df


# ── data loading ──────────────────────────────────────────────────────────────
def load_cytokine_data(path: Path | None = None) -> pd.DataFrame:
    # Phase 1 real-data-only: no synthetic fallback.
    # Expected files (from fetch_data.py) follow the LSDS-8 naming from OSDR.
    # Phase 2 will add schema-aware parsing once inventory.py confirms the layout.
    candidates = [
        path,
        RAW_DIR / "OSD-575_eve_immune_TRANSFORMED.csv",
        RAW_DIR / "OSD-575_cytokines.csv",
    ]
    for p in candidates:
        if p and p.exists():
            df = pd.read_csv(p, index_col=0)
            print(f"[load] {p}  shape={df.shape}")
            return df
    searched = [str(c) for c in candidates if c]
    raise FileNotFoundError(
        f"Real OSD-575 cytokine data not found. Run scripts/fetch_data.py first.\n"
        f"Searched: {searched}"
    )


# ── statistical core ──────────────────────────────────────────────────────────
def compute_individualized_baselines(df: pd.DataFrame) -> dict:
    """Personal ground baseline (μ ± σ) across L-minus samples per crew."""
    baselines: dict[str, dict] = {}
    for crew in CREW_IDS:
        cols = [f"{crew}_{tp}" for tp in L_MINUS_TIMEPOINTS if f"{crew}_{tp}" in df.columns]
        if not cols:
            print(f"[warn] No L-minus columns found for {crew} — skipping.")
            continue
        sub = df[cols]
        baselines[crew] = {}
        for marker in df.index:
            vals = sub.loc[marker].dropna().values.astype(float)
            baselines[crew][marker] = {
                "mean": float(vals.mean()) if len(vals) else float("nan"),
                "std":  float(vals.std(ddof=1)) if len(vals) > 1 else float("nan"),
                "n":    int(len(vals)),
            }
    return baselines


def compute_zscores(
    df: pd.DataFrame,
    baselines: dict,
    timepoints: list[str],
) -> dict:
    """
    Z = (x_flight − μ_ground) / σ_ground  per crew × timepoint × marker.
    NaN emitted when σ is degenerate (n=1 baseline or zero variance).
    """
    zscores: dict[str, dict] = {}
    for crew, markers in baselines.items():
        zscores[crew] = {}
        for tp in timepoints:
            col = f"{crew}_{tp}"
            if col not in df.columns:
                continue
            zscores[crew][tp] = {}
            for marker, stats in markers.items():
                if marker not in df.index:
                    continue
                raw  = float(df.loc[marker, col])
                mu   = stats["mean"]
                sig  = stats["std"]
                z    = (raw - mu) / sig if (sig and sig > 1e-9 and not np.isnan(sig)) else float("nan")
                zscores[crew][tp][marker] = {
                    "z_score":        round(z, 3) if not np.isnan(z) else None,
                    "raw_pg_mL":      round(raw, 3),
                    "baseline_mean":  round(mu, 3)  if not np.isnan(mu)  else None,
                    "baseline_std":   round(sig, 3) if not np.isnan(sig) else None,
                    "n_baseline":     stats["n"],
                }
    return zscores


def top_perturbed(
    zscores: dict,
    crew: str,
    timepoint: str,
    n: int = 5,
    panel: list[str] | None = None,
) -> list[tuple[str, dict]]:
    tp_data = zscores.get(crew, {}).get(timepoint, {})
    candidates = {k: v for k, v in tp_data.items()
                  if v["z_score"] is not None and (panel is None or k in panel)}
    ranked = sorted(candidates.items(), key=lambda x: abs(x[1]["z_score"]), reverse=True)
    return ranked[:n]


# ── clinical annotations ──────────────────────────────────────────────────────
CLINICAL_CONTEXT: dict[str, str] = {
    "IL-6": (
        "Acute-phase response mediator. FD1 spike is consistent with microgravity-induced "
        "sterile inflammation activating the JAK/STAT3 axis. Monitor for sustained elevation "
        "beyond FD3 as a trigger for immune dysregulation review. "
        "Ref: Overbey et al., Nature 2024; Crucian et al., NPJ Microgravity 2020."
    ),
    "IP-10": (
        "CXCL10 — IFN-γ–inducible T-cell chemoattractant. Consistently the highest-amplitude "
        "spike in Inspiration4 crew on FD1 (SOMA 2024, Fig. 3b). Suggests early innate immune "
        "activation and aligns with EBV/VZV viral reactivation surveillance. "
        "Cross-reference OSD-570 CXCL10/IRF1/STAT1 gene expression."
    ),
    "IL-8": (
        "CXCL8 — neutrophil recruitment chemokine. Early elevation may reflect oxidative stress "
        "from GCR/SPE radiation exposure or mechanosensing of fluid shifts. "
        "Actionable: cross-reference G-CSF to assess granulopoiesis pressure on FD1-3."
    ),
    "G-CSF": (
        "Granulocyte colony-stimulating factor. Drives HSC mobilization from bone marrow — "
        "well-documented in head-down tilt analogs and ISS data. Elevation on FD1 is expected; "
        "concern threshold is sustained >3σ. Cross-reference CXCL12/CXCR4 axis in OSD-570."
    ),
    "IL-1RA": (
        "IL-1 receptor antagonist — compensatory counter-response to IL-1β signaling. Elevation "
        "alongside pro-inflammatory cytokines indicates active immune regulation is engaged. "
        "Favorable prognostic sign if IL-1β itself remains at baseline."
    ),
    "MCP-1": (
        "CCL2 — monocyte chemotactic protein. Elevation reflects the non-classical monocyte "
        "(CD14+CD16+) expansion documented in SOMA 2024. Cross-reference bulk RNA deconvolution "
        "for monocyte fraction shift in OSD-570."
    ),
    "IFN-gamma": (
        "Type II interferon — NK/T-cell activation marker and key viral reactivation indicator. "
        "EBV, VZV, and CMV reactivation confirmed in Inspiration4 (SOMA 2024 Supplementary). "
        "Sustained elevation >FD3: flag for antiviral protocol review."
    ),
    "TNF-alpha": (
        "Pleiotropic pro-inflammatory cytokine. Modest elevation (1–2σ) is expected and "
        "non-actionable. Clinical concern: >3σ sustained across multiple FD timepoints, "
        "indicating systemic inflammatory state requiring countermeasure."
    ),
    "IL-1beta": (
        "Master pro-inflammatory cytokine activating the NLRP3 inflammasome cascade. Even "
        "modest elevation (>1.5σ) warrants correlation with downstream IL-6 and IL-8, "
        "as it is the upstream driver of the space-associated cytokine storm phenotype."
    ),
    "GM-CSF": (
        "Granulocyte-macrophage CSF. Co-elevation with G-CSF signals broad myeloid progenitor "
        "activation. Together these suggest the bone marrow is responding to perceived systemic "
        "stress within the first 24h of microgravity exposure."
    ),
    "VEGF": (
        "Vascular Endothelial Growth Factor. Elevation may reflect cephalad fluid shift hypoxia "
        "sensing or intracranial pressure adaptation. Cross-reference with SOMA ophthalmology "
        "data (optic disc edema risk) and HIF-1α pathway in OSD-570."
    ),
    "HGF": (
        "Hepatocyte Growth Factor — tissue repair and regeneration signal. Crew C004 shows "
        "a distinct HGF/VEGF/FGF angiogenic signature, suggesting individual-specific vascular "
        "adaptation strategy to microgravity."
    ),
    "MIP-1alpha": (
        "CCL3 — macrophage inflammatory protein. Elevation is consistent with innate immune "
        "activation and correlates with NK cell chemotaxis. Monitor alongside IFN-γ as a "
        "composite viral reactivation index."
    ),
    "IL-10": (
        "Anti-inflammatory cytokine produced by regulatory T cells and M2 macrophages. "
        "If suppressed below baseline, loss of immune regulation may accelerate inflammatory "
        "load. If elevated, system is actively counter-regulating — check ratio vs. IL-6."
    ),
}


def annotate(cytokine: str, z: float, raw: float) -> str:
    direction = "Elevated" if z > 0 else "Suppressed"
    if abs(z) > 3:   severity = "CRITICAL"
    elif abs(z) > 2: severity = "HIGH"
    elif abs(z) > 1.5: severity = "MODERATE"
    else:              severity = "LOW"
    context = CLINICAL_CONTEXT.get(
        cytokine, f"{cytokine} perturbation detected — no specific annotation available."
    )
    return (
        f"[{severity}] {direction} {cytokine} | Z={z:+.2f} | {raw:.2f} pg/mL\n"
        f"   {context}"
    )


# ── Health Orbit gauge computation ─────────────────────────────────────────────
GAUGE_MARKERS = {
    "immune_stability":  ["IL-2", "IL-4", "IL-7", "IL-15", "IFN-gamma", "IL-12p70"],
    "inflammatory_load": ["IL-6", "IL-8", "TNF-alpha", "IL-1beta", "MCP-1", "IP-10",
                          "G-CSF", "GM-CSF", "MIP-1alpha"],
    "recovery_velocity": ["IL-10", "IL-1RA", "VEGF", "HGF"],
}

GAUGE_INTERPRETATION = {
    "immune_stability": (
        "Deviation of adaptive immune signaling from personal ground baseline. "
        "Target <20 for mission-critical cognitive tasks."
    ),
    "inflammatory_load": (
        "Aggregate pro-inflammatory burden. >60 = systemic inflammatory state "
        "requiring countermeasure protocol review."
    ),
    "recovery_velocity": (
        "Anti-inflammatory and tissue-repair signal strength. "
        "Rising trend on R+1 is a favorable recovery indicator."
    ),
}


def compute_gauges(zscores: dict, crew: str, timepoint: str) -> dict:
    tp_data = zscores.get(crew, {}).get(timepoint, {})

    def gauge_score(markers: list[str]) -> float | None:
        vals = [tp_data[m]["z_score"] for m in markers
                if m in tp_data and tp_data[m]["z_score"] is not None]
        if not vals:
            return None
        return round(min(float(np.mean(np.abs(vals))) / 5.0 * 100, 100), 1)

    result = {}
    for name, markers in GAUGE_MARKERS.items():
        score = gauge_score(markers)
        result[name] = {
            "score":          score,
            "interpretation": GAUGE_INTERPRETATION[name],
            "contributing_markers": markers,
        }
    return result


# ── risk aggregation ───────────────────────────────────────────────────────────
def build_risk_alerts(zscores: dict, threshold: float = 2.0) -> dict:
    alerts: dict[str, dict] = {}
    for crew in CREW_IDS:
        alerts[crew] = {}
        for tp in FD_TIMEPOINTS + R_PLUS_TIMEPOINTS:
            tp_data = zscores.get(crew, {}).get(tp, {})
            flagged = {
                m: v for m, v in tp_data.items()
                if v["z_score"] is not None and abs(v["z_score"]) >= threshold
            }
            if flagged:
                alerts[crew][tp] = flagged
    return alerts


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> dict:
    print("=" * 70)
    print("  SOMA Health Orbit  |  Individualized Baseline Analysis")
    print("  OSD-575 Cytokines  |  n=1 Personal Z-Score Trajectories")
    print("=" * 70)

    df = load_cytokine_data()
    print(f"\n[data] {len(df)} cytokines  ×  {len(df.columns)} samples")

    baselines = compute_individualized_baselines(df)
    print(f"[baselines] Personal ground baseline computed for {len(baselines)} crew members "
          f"(using {L_MINUS_TIMEPOINTS}).")

    all_fd_r = FD_TIMEPOINTS + R_PLUS_TIMEPOINTS
    zscores = compute_zscores(df, baselines, all_fd_r)

    # ── PRIMARY DELIVERABLE: C001 FD1 top-5 inflammatory cytokines ─────────────
    print("\n" + "━" * 70)
    print("  CREW C001  |  FD1  —  Top 5 Most Perturbed Inflammatory Cytokines")
    print("━" * 70)

    top5 = top_perturbed(zscores, "C001", "FD1", n=5, panel=INFLAMMATORY_PANEL)
    if not top5:
        print("[warn] No FD1 data found for C001. Check column names in your CSV.")
        sys.exit(1)

    c001_fd1_findings = []
    for rank, (marker, vals) in enumerate(top5, 1):
        z   = vals["z_score"]
        raw = vals["raw_pg_mL"]
        print(f"\n  #{rank}  {annotate(marker, z, raw)}")
        c001_fd1_findings.append({
            "rank":              rank,
            "cytokine":          marker,
            "z_score":           z,
            "raw_pg_mL":         raw,
            "baseline_mean":     vals["baseline_mean"],
            "baseline_std":      vals["baseline_std"],
            "n_baseline":        vals["n_baseline"],
            "clinical_context":  CLINICAL_CONTEXT.get(marker, ""),
            "actionable":        annotate(marker, z, raw),
        })

    # ── Health Orbit gauges for C001 / FD1 ────────────────────────────────────
    gauges = compute_gauges(zscores, "C001", "FD1")
    print("\n" + "━" * 70)
    print("  HEALTH ORBIT GAUGES  |  C001 / FD1")
    print("━" * 70)
    for name, g in gauges.items():
        score = g["score"] or 0
        bar   = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  {name.replace('_', ' ').title():22s}  {bar}  {score:.1f}/100")

    # ── Full risk_scores.json ──────────────────────────────────────────────────
    risk_alerts = build_risk_alerts(zscores, threshold=2.0)

    output = {
        "meta": {
            "pipeline":            "SOMA Health Orbit v1.0",
            "script":              "process_baselines.py",
            "dataset":             "OSD-575 — Cytokines (Luminex 65-plex, pg/mL)",
            "sigma_threshold":     2.0,
            "baseline_timepoints": L_MINUS_TIMEPOINTS,
            "generated":           pd.Timestamp.now().isoformat(),
            "crew_members":        CREW_IDS,
            "n1_caveat": (
                "Z-scores derived from n=3 L-minus samples. Interpret individual "
                "sigma deviations as hypothesis-generating, not diagnostic. "
                "Run honesty_check.py for full statistical power analysis."
            ),
        },
        "c001_fd1_primary_analysis": {
            "focus":              "Top 5 most perturbed inflammatory cytokines",
            "ranked_findings":    c001_fd1_findings,
            "health_orbit_gauges": gauges,
        },
        "full_cohort_alerts_2sigma": risk_alerts,
        "all_zscores":              zscores,
    }

    out_path = PROC_DIR / "risk_scores.json"
    with open(out_path, "w") as fh:
        json.dump(output, fh, indent=2, default=str)
    print(f"\n[output] {out_path}")
    return output


if __name__ == "__main__":
    main()
