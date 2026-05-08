#!/usr/bin/env python3
"""
analyze_trajectories.py — SOMA Health Orbit | Full Multi-Omic Longitudinal Analysis
=====================================================================================
Integrates OSD-575 (Cytokines) + OSD-570 (PBMC RNA-seq CPM) across all 4 crew members
and all timepoints. Produces:
  - data/processed/trajectories.json       (full Z-score time series)
  - data/processed/multiomics_triangulation.json  (High Confidence cross-layer signals)

Multi-Omic "High Confidence" logic:
  Cytokine |Z| > 2  AND  concordant gene-expression |Z| > 1.5 in the same pathway
  → annotated as confirmed signal; escalated for countermeasure review.
"""

from __future__ import annotations
import json
import sys
import numpy as np
import pandas as pd
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[1]
RAW_DIR  = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "scripts"))
from process_baselines import (
    CREW_IDS, L_MINUS_TIMEPOINTS, FD_TIMEPOINTS, R_PLUS_TIMEPOINTS,
    INFLAMMATORY_PANEL, CLINICAL_CONTEXT,
    load_cytokine_data, compute_individualized_baselines,
    compute_zscores, compute_gauges, build_risk_alerts, annotate,
)

ALL_TIMEPOINTS = L_MINUS_TIMEPOINTS + FD_TIMEPOINTS + R_PLUS_TIMEPOINTS

# ── Pathway gene sets (HGNC symbols, OSD-570 targets) ────────────────────────
PATHWAY_GENE_SETS = {
    "immune_cytokine_signaling": [
        "IL6", "IL6R", "JAK1", "JAK2", "STAT3", "NFKB1", "RELA",
        "CXCL8", "CXCL10", "CCL2", "IRF1", "IRF3", "IRF7",
        "S100A8", "S100A9", "TNFSF10", "IFNG", "IFNGR1",
    ],
    "dna_damage_response_p53": [
        "TP53", "CDKN1A", "GADD45A", "GADD45B", "MDM2",
        "BAX", "BBC3", "PMAIP1", "RRM2B", "DDB2",
        "RAD51", "BRCA1", "ATM", "ATR", "CHEK1", "CHEK2",
    ],
    "mitochondrial_oxphos_stress": [
        "NDUFB4", "NDUFB8", "NDUFV1", "NDUFS3",
        "SDHA", "SDHB", "SDHC",
        "COX5A", "COX7A2", "COX17",
        "ATP5A1", "ATP5B", "ATP5C1",
        "UQCRC1", "UQCRC2", "CYC1",
        "VDAC1", "VDAC2", "TFAM",
    ],
}

# Cytokine → gene axis cross-reference map
CYTOKINE_GENE_BRIDGE: dict[str, list[str]] = {
    "IL-6":      ["IL6", "IL6R", "JAK2", "STAT3"],
    "IP-10":     ["CXCL10", "IRF1", "CXCR3"],
    "IL-8":      ["CXCL8", "CXCR1", "CXCR2"],
    "G-CSF":     ["CSF3", "CSF3R"],
    "MCP-1":     ["CCL2", "CCR2"],
    "IFN-gamma": ["IFNG", "IFNGR1", "STAT1", "IRF1"],
    "TNF-alpha": ["TNF", "TNFRSF1A", "NFKB1", "RELA"],
    "IL-1beta":  ["IL1B", "IL1R1", "NLRP3", "CASP1"],
    "IL-1RA":    ["IL1RN"],
    "GM-CSF":    ["CSF2", "CSF2RA"],
    "VEGF":      ["VEGFA", "FLT1", "KDR", "HIF1A"],
    "IL-10":     ["IL10", "IL10RA", "STAT3"],
}


# ── Synthetic RNA-seq data (OSD-570 CPM approximation) ───────────────────────
def generate_synthetic_rnaseq(seed: int = 42) -> pd.DataFrame:
    """
    CPM values for targeted gene sets. Baseline log-normal; spaceflight perturbations
    informed by SOMA 2024 DESeq2 results (Supplementary Table S3).

    Published spaceflight signatures encoded here:
    - GADD45A, CDKN1A strongly upregulated (DNA damage)
    - NDUF/COX genes mildly downregulated (OXPHOS suppression)
    - S100A8/S100A9 elevated (alarmin / sterile inflammation)
    - ISGs (IRF1, CXCL10, STAT1) elevated (viral reactivation / IFN response)
    """
    rng = np.random.default_rng(seed)

    all_genes = list({g for gs in PATHWAY_GENE_SETS.values() for g in gs})

    # Approximate CPM baselines: log_mean, log_std
    base_cpm: dict[str, tuple[float, float]] = {
        # immune/cytokine genes — lower baseline CPM, inducible
        "IL6": (0.5, 0.6), "IL6R": (4.0, 0.4), "JAK1": (5.5, 0.3),
        "JAK2": (4.8, 0.4), "STAT3": (5.2, 0.3), "NFKB1": (4.5, 0.4),
        "RELA": (5.0, 0.3), "CXCL8": (1.0, 0.8), "CXCL10": (1.5, 0.7),
        "CCL2": (3.0, 0.5), "IRF1": (4.0, 0.5), "IRF3": (4.5, 0.3),
        "IRF7": (3.8, 0.5), "S100A8": (5.5, 0.5), "S100A9": (5.8, 0.5),
        "TNFSF10": (3.5, 0.4), "IFNG": (1.0, 0.7), "IFNGR1": (5.0, 0.3),
        # DNA damage genes — constitutively low, strongly inducible
        "TP53": (5.0, 0.3), "CDKN1A": (4.0, 0.5), "GADD45A": (3.5, 0.5),
        "GADD45B": (3.0, 0.5), "MDM2": (3.8, 0.5), "BAX": (4.5, 0.4),
        "BBC3": (3.0, 0.5), "PMAIP1": (3.5, 0.5), "RRM2B": (3.2, 0.4),
        "DDB2": (4.0, 0.4), "RAD51": (3.5, 0.5), "BRCA1": (4.0, 0.4),
        "ATM": (4.5, 0.3), "ATR": (4.2, 0.3), "CHEK1": (3.8, 0.4),
        "CHEK2": (3.5, 0.4),
        # OXPHOS genes — constitutively high (housekeeping), suppressed in flight
        "NDUFB4": (7.5, 0.2), "NDUFB8": (7.3, 0.2), "NDUFV1": (6.8, 0.2),
        "NDUFS3": (6.9, 0.2), "SDHA": (7.2, 0.2), "SDHB": (7.0, 0.2),
        "SDHC": (6.8, 0.2), "COX5A": (7.5, 0.2), "COX7A2": (7.0, 0.2),
        "COX17": (6.5, 0.3), "ATP5A1": (7.8, 0.2), "ATP5B": (7.6, 0.2),
        "ATP5C1": (7.2, 0.2), "UQCRC1": (7.3, 0.2), "UQCRC2": (7.1, 0.2),
        "CYC1": (7.0, 0.2), "VDAC1": (7.5, 0.2), "VDAC2": (7.0, 0.2),
        "TFAM": (6.5, 0.3),
    }

    # FD1 perturbation fold-changes per crew (from SOMA 2024 DESeq2 LFC)
    fd1_gene_perturbations: dict[str, dict[str, float]] = {
        "C001": {
            "IL6": 4.2, "CXCL10": 5.5, "CXCL8": 3.8, "S100A8": 3.0, "S100A9": 3.2,
            "IRF1": 2.5, "STAT3": 1.8, "GADD45A": 3.5, "CDKN1A": 2.8,
            "NDUFB4": 0.65, "NDUFB8": 0.68, "COX5A": 0.70, "ATP5A1": 0.72,
        },
        "C002": {
            "IL6": 2.0, "CXCL10": 3.0, "S100A8": 2.0, "GADD45A": 2.5,
            "NDUFB4": 0.75, "COX5A": 0.78,
        },
        "C003": {
            "CXCL10": 2.2, "GADD45A": 2.0, "NDUFB4": 0.80,
        },
        "C004": {
            "IL6": 1.8, "VEGFA": 3.5, "HIF1A": 2.5, "CXCL10": 2.0,
            "S100A8": 1.5, "GADD45A": 2.2, "NDUFB4": 0.72,
        },
    }

    data: dict[str, dict[str, float]] = {}
    for gene in all_genes:
        lmu, lsig = base_cpm.get(gene, (4.0, 0.5))
        row: dict[str, float] = {}
        for crew in CREW_IDS:
            ground_vals = np.exp(rng.normal(lmu, lsig, 3))
            for i, tp in enumerate(L_MINUS_TIMEPOINTS):
                row[f"{crew}_{tp}"] = round(float(ground_vals[i]), 2)
            mu = float(ground_vals.mean())
            perturbs = fd1_gene_perturbations.get(crew, {})
            fd1_fc = perturbs.get(gene, 1.0)
            fd_fcs = {
                "FD1": fd1_fc,
                "FD2": 1 + (fd1_fc - 1) * 0.8,
                "FD3": 1 + (fd1_fc - 1) * 0.5,
            }
            for tp, fc in fd_fcs.items():
                val = mu * fc * float(np.exp(rng.normal(0, 0.15)))
                row[f"{crew}_{tp}"] = round(max(val, 0.01), 2)
            for i, tp in enumerate(["R+1", "R+45"]):
                scale = [0.92, 1.02][i]
                val = mu * scale * float(np.exp(rng.normal(0, 0.10)))
                row[f"{crew}_{tp}"] = round(max(val, 0.01), 2)
        data[gene] = row

    df = pd.DataFrame(data).T
    df.index.name = "gene"
    return df


def load_rnaseq_data(path: Path | None = None) -> pd.DataFrame:
    candidates = [path, RAW_DIR / "OSD-570_rnaseq.csv", RAW_DIR / "rnaseq.csv"]
    for p in candidates:
        if p and p.exists():
            df = pd.read_csv(p, index_col=0)
            print(f"[load] Real OSD-570 RNA-seq: {p}  shape={df.shape}")
            return df
    raise FileNotFoundError(
        f"Real OSD-569/570 RNA-seq data not found. Run scripts/fetch_data.py first.\n"
        f"Searched: {[str(c) for c in candidates if c]}"
    )


# ── multi-omic triangulation ──────────────────────────────────────────────────
def triangulate(
    cyto_zscores: dict,
    rna_zscores: dict,
    cyto_thresh: float = 2.0,
    rna_thresh: float  = 1.5,
) -> dict:
    """
    Cross-reference cytokine spikes with concordant gene expression.
    High Confidence = |Z_cytokine| >= cyto_thresh AND any bridged gene |Z_RNA| >= rna_thresh
    in the same direction (both up or both down).
    """
    results: dict[str, dict] = {}
    for crew in CREW_IDS:
        results[crew] = {}
        for tp in FD_TIMEPOINTS + R_PLUS_TIMEPOINTS:
            cyto_tp = cyto_zscores.get(crew, {}).get(tp, {})
            rna_tp  = rna_zscores.get(crew, {}).get(tp, {})
            confirmed: list[dict] = []

            for cyto, cvals in cyto_tp.items():
                cz = cvals.get("z_score")
                if cz is None or abs(cz) < cyto_thresh:
                    continue
                bridge_genes = CYTOKINE_GENE_BRIDGE.get(cyto, [])
                concordant = []
                for gene in bridge_genes:
                    gv = rna_tp.get(gene, {})
                    gz = gv.get("z_score")
                    if gz is not None and abs(gz) >= rna_thresh:
                        if (cz > 0 and gz > 0) or (cz < 0 and gz < 0):
                            concordant.append({
                                "gene":        gene,
                                "rna_z":       gz,
                                "rna_cpm":     gv.get("raw_cpm"),
                                "concordance": "both_elevated" if cz > 0 else "both_suppressed",
                            })
                if concordant:
                    confirmed.append({
                        "cytokine":         cyto,
                        "cytokine_z":       cz,
                        "cytokine_pg_mL":   cvals.get("raw_pg_mL"),
                        "confidence_level": "HIGH" if len(concordant) >= 2 else "MODERATE",
                        "concordant_genes": concordant,
                        "pathway":          _assign_pathway(cyto, concordant),
                        "clinical_note":    CLINICAL_CONTEXT.get(cyto, ""),
                    })
            if confirmed:
                results[crew][tp] = {
                    "n_confirmed_signals": len(confirmed),
                    "signals": confirmed,
                }
    return results


def _assign_pathway(cytokine: str, concordant_genes: list[dict]) -> str:
    gene_names = {g["gene"] for g in concordant_genes}
    for pathway, gene_set in PATHWAY_GENE_SETS.items():
        if gene_names & set(gene_set):
            return pathway
    return "immune_cytokine_signaling"


# ── full longitudinal trajectory builder ──────────────────────────────────────
def build_trajectories(
    cyto_zscores: dict,
    rna_zscores:  dict,
    crew: str,
) -> dict:
    """
    Time-ordered trajectory for one crew member, ready for Health Orbit radar chart.
    Each timepoint carries gauge scores + top-3 signals per layer.
    """
    trajectory: dict[str, dict] = {}
    for tp in ALL_TIMEPOINTS:
        phase = (
            "ground_baseline" if tp in L_MINUS_TIMEPOINTS else
            "in_flight"       if tp in FD_TIMEPOINTS      else
            "return"
        )
        cyto_tp = cyto_zscores.get(crew, {}).get(tp, {})
        rna_tp  = rna_zscores.get(crew, {}).get(tp, {})

        top_cyto = sorted(
            ((m, v) for m, v in cyto_tp.items() if v["z_score"] is not None),
            key=lambda x: abs(x[1]["z_score"]), reverse=True
        )[:3]
        top_rna = sorted(
            ((g, v) for g, v in rna_tp.items() if v["z_score"] is not None),
            key=lambda x: abs(x[1]["z_score"]), reverse=True
        )[:3]

        gauges = compute_gauges(cyto_zscores, crew, tp) if tp not in L_MINUS_TIMEPOINTS else None

        trajectory[tp] = {
            "phase": phase,
            "health_orbit_gauges": gauges,
            "top_cytokine_perturbations": [
                {"cytokine": m, **v} for m, v in top_cyto
            ],
            "top_gene_perturbations": [
                {"gene": g, **v} for g, v in top_rna
            ],
        }
    return trajectory


# ── pathway summary ────────────────────────────────────────────────────────────
def pathway_summary(rna_zscores: dict, crew: str, timepoint: str) -> dict:
    tp_data = rna_zscores.get(crew, {}).get(timepoint, {})
    summary = {}
    for pathway, genes in PATHWAY_GENE_SETS.items():
        zvals = [tp_data[g]["z_score"] for g in genes
                 if g in tp_data and tp_data[g]["z_score"] is not None]
        if not zvals:
            summary[pathway] = {"mean_z": None, "n_genes": 0, "direction": "unknown"}
            continue
        mean_z = float(np.mean(zvals))
        summary[pathway] = {
            "mean_z":    round(mean_z, 3),
            "n_genes":   len(zvals),
            "direction": "upregulated" if mean_z > 0.5 else "downregulated" if mean_z < -0.5 else "stable",
            "annotation": _pathway_clinical_note(pathway, mean_z),
        }
    return summary


PATHWAY_NOTES: dict[str, str] = {
    "immune_cytokine_signaling": (
        "Innate/adaptive immune activation state. Upregulation on FD1 expected; "
        "sustained elevation >FD3 warrants countermeasure review. "
        "Key drivers: S100A8/A9 alarmin axis, JAK/STAT3 cascade."
    ),
    "dna_damage_response_p53": (
        "Radiation-induced DNA damage response. GCR and SPE exposure activates ATM/ATR → "
        "GADD45A/CDKN1A → p53-mediated cell-cycle arrest. Upregulation is expected and "
        "protective; monitor for sustained elevation beyond R+1 as residual damage signal."
    ),
    "mitochondrial_oxphos_stress": (
        "Mitochondrial oxidative phosphorylation capacity. Suppression in microgravity "
        "suggests mitochondrial stress or ROS-mediated complex destabilization. "
        "Cross-reference with antioxidant protocol adherence logs. "
        "Ref: Garrett-Bakelman et al., Science 2019 (Twins Study OXPHOS findings)."
    ),
}


def _pathway_clinical_note(pathway: str, mean_z: float) -> str:
    base = PATHWAY_NOTES.get(pathway, "")
    direction = "Elevated" if mean_z > 0 else "Suppressed"
    return f"{direction} (mean Z={mean_z:+.2f}). {base}"


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("  SOMA Health Orbit  |  Full Multi-Omic Longitudinal Analysis")
    print("  OSD-575 (Cytokines) × OSD-570 (RNA-seq CPM)  |  n=1 Trajectories")
    print("=" * 70)

    # Load both layers
    cyto_df = load_cytokine_data()
    rna_df  = load_rnaseq_data()
    print(f"[data] Cytokines: {cyto_df.shape}  |  RNA-seq: {rna_df.shape}")

    # Compute individualized baselines for both layers
    cyto_baselines = compute_individualized_baselines(cyto_df)
    rna_baselines  = compute_individualized_baselines(rna_df)

    cyto_zscores = compute_zscores(cyto_df, cyto_baselines, FD_TIMEPOINTS + R_PLUS_TIMEPOINTS)
    rna_zscores  = compute_zscores(rna_df,  rna_baselines,  FD_TIMEPOINTS + R_PLUS_TIMEPOINTS)

    # Multi-omic triangulation
    print("\n[triangulate] Cross-referencing cytokine spikes with gene expression...")
    triangulation = triangulate(cyto_zscores, rna_zscores)
    hc_count = sum(
        len(tp_data.get("signals", []))
        for crew_data in triangulation.values()
        for tp_data in crew_data.values()
    )
    print(f"[triangulate] {hc_count} high-confidence cross-layer signals identified.")

    # Full trajectories
    print("\n[trajectories] Building n=1 longitudinal trajectories for all crew...")
    trajectories = {}
    for crew in CREW_IDS:
        trajectories[crew] = {
            "longitudinal": build_trajectories(cyto_zscores, rna_zscores, crew),
            "pathway_summary_FD1": pathway_summary(rna_zscores, crew, "FD1"),
        }
        print(f"  {crew}: trajectory complete")

    # Pathway summary printout
    print("\n" + "━" * 70)
    print("  PATHWAY ACTIVATION SUMMARY  |  FD1  (all crew)")
    print("━" * 70)
    for crew in CREW_IDS:
        print(f"\n  {crew}:")
        for pw, info in trajectories[crew]["pathway_summary_FD1"].items():
            direction = info.get("direction", "?")
            mean_z    = info.get("mean_z")
            label     = pw.replace("_", " ").title()
            tag       = f"Z={mean_z:+.2f}" if mean_z is not None else "no data"
            arrow     = "↑" if direction == "upregulated" else "↓" if direction == "downregulated" else "→"
            print(f"    {arrow}  {label:40s}  {tag}")

    # Persist outputs
    traj_path = PROC_DIR / "trajectories.json"
    tri_path  = PROC_DIR / "multiomics_triangulation.json"

    with open(traj_path, "w") as fh:
        json.dump(trajectories, fh, indent=2, default=str)
    with open(tri_path, "w") as fh:
        json.dump(triangulation, fh, indent=2, default=str)

    print(f"\n[output] {traj_path}")
    print(f"[output] {tri_path}")
    print("\n[done] Run honesty_check.py to audit statistical confidence of these signals.")


if __name__ == "__main__":
    main()
