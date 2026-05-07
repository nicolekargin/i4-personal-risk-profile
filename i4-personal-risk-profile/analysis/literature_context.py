"""
Literature context annotation.

Tags each measurement in the master profile with a literature_status
based on KNOWN_FINDINGS — a curated dictionary of spaceflight-published
findings from the NASA GeneLab / TWINS / ISS microbiome literature.

literature_status values:
  "confirmed"      — finding matches a published spaceflight observation
  "novel"          — elevated/changed but no matching published finding
  "contradicted"   — direction opposite to the published finding
  "not_applicable" — baseline rows, stable signals, or non-immune non-microbial

Also produces docs/LITERATURE_CONTEXT.md from the KNOWN_FINDINGS dict.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ── Known findings ────────────────────────────────────────────────────────────
# Format: canonical_measurement_id → {direction, source, note}
# direction: "up" = elevated in spaceflight; "down" = depleted; "variable"
KNOWN_FINDINGS: dict[str, dict] = {
    # Acute-phase / inflammatory cytokines
    "il_6": {
        "direction": "up",
        "source": "Crucian et al. 2014 (J Interferon Cytokine Res); Crucian et al. 2015",
        "note": "Persistently elevated IL-6 across ISS missions; marker of spaceflight immune dysregulation.",
    },
    "il_8": {
        "direction": "up",
        "source": "Crucian et al. 2014",
        "note": "Neutrophil chemoattractant elevated in-flight and early post-flight.",
    },
    "tnf_alpha": {
        "direction": "up",
        "source": "Crucian et al. 2014",
        "note": "Pro-inflammatory cytokine elevated in long-duration spaceflight.",
    },
    "il_1_beta": {
        "direction": "up",
        "source": "Crucian et al. 2014",
        "note": "Elevated early post-flight in multiple ISS crew members.",
    },
    # T-helper polarization
    "ifn_gamma": {
        "direction": "up",
        "source": "Crucian et al. 2015; Mehta et al. 2013",
        "note": "Th1 marker persistently elevated; associated with herpesvirus reactivation risk.",
    },
    "il_4": {
        "direction": "up",
        "source": "Crucian et al. 2015",
        "note": "Th2 shift observed; IL-4 elevation accompanies IFN-γ in some crew.",
    },
    "il_2": {
        "direction": "variable",
        "source": "Crucian et al. 2014",
        "note": "IL-2 responses variable across crew; sometimes reduced (T-cell hyporesponsiveness).",
    },
    # Regulatory
    "il_10": {
        "direction": "up",
        "source": "Crucian et al. 2014",
        "note": "Anti-inflammatory counter-regulation elevated alongside pro-inflammatory cytokines.",
    },
    # Monocyte/macrophage
    "mcp_1": {
        "direction": "up",
        "source": "Crucian et al. 2014; Makedonas et al. 2019",
        "note": "Monocyte chemoattractant protein elevated; monocyte dysregulation noted in spaceflight.",
    },
    "mip_1_alpha": {
        "direction": "up",
        "source": "Crucian et al. 2014",
        "note": "Macrophage inflammatory protein elevated post-flight.",
    },
    "mip_1_beta": {
        "direction": "up",
        "source": "Crucian et al. 2014",
        "note": "MIP-1β elevated; associated with innate immune activation.",
    },
    # Interferon pathway
    "ip_10": {
        "direction": "up",
        "source": "Crucian et al. 2015; Mehta et al. 2013",
        "note": "CXCL10 / IP-10 elevated in herpesvirus-positive crew; interferon-stimulated gene product.",
    },
    # Vascular / growth factors
    "vegf": {
        "direction": "up",
        "source": "Scott et al. 2012 (vascular adaptation review)",
        "note": "VEGF elevated in microgravity; vascular remodeling response.",
    },
    "fgf_basic": {
        "direction": "up",
        "source": "Scott et al. 2012",
        "note": "FGF-2 elevated; fibroblast and angiogenic response to spaceflight stress.",
    },
    # Clinical — CBC
    "white_blood_cell_count": {
        "direction": "up",
        "source": "Crucian et al. 2008 (Aviat Space Environ Med)",
        "note": "WBC commonly elevated early post-landing; stress leukocytosis and gravitational re-adaptation.",
    },
    "lymphocyte_percent": {
        "direction": "down",
        "source": "Crucian et al. 2008",
        "note": "Relative lymphopenia post-flight as neutrophils dominate re-entry stress response.",
    },
    "neutrophil_percent": {
        "direction": "up",
        "source": "Crucian et al. 2008",
        "note": "Neutrophilia at landing; mirrors cortisol spike from re-entry physical stress.",
    },
    "red_blood_cell_count": {
        "direction": "down",
        "source": "Trudel et al. 2020 (Nat Med) — space anemia",
        "note": "RBC destruction accelerated 50× above normal in-flight; hemolytic anemia post-flight.",
    },
    "hemoglobin": {
        "direction": "down",
        "source": "Trudel et al. 2020",
        "note": "Hemoglobin reduced; resolves slowly post-flight (~3 months).",
    },
    "hematocrit": {
        "direction": "down",
        "source": "Trudel et al. 2020",
        "note": "Hematocrit reduced consistent with hemolytic space anemia.",
    },
    "mcv": {
        "direction": "up",
        "source": "Trudel et al. 2020",
        "note": "MCV elevation consistent with macrocytic shift during erythrocyte regeneration.",
    },
    # Microbial — oral/nasal
    "oral_microbiome_diversity": {
        "direction": "down",
        "source": "Voorhies et al. 2019 (NPJ Microgravity)",
        "note": "Alpha diversity reduction in oral microbiome during spaceflight.",
    },
    "nasal_microbiome_diversity": {
        "direction": "down",
        "source": "Voorhies et al. 2019",
        "note": "Nasal microbiome diversity reduced in-flight; microbial community destabilization.",
    },
}

# Canonical mapping helpers (reuse logic from archetype.py)
import re as _re


def _canonical(s: str) -> str:
    s = s.lower().strip()
    s = _re.sub(r"[\s\-/]+", "_", s)
    s = _re.sub(r"[^a-z0-9_]", "", s)
    return s


_KNOWN_CANON: dict[str, str] = {_canonical(k): k for k in KNOWN_FINDINGS}


def _norm(s: str) -> str:
    """Underscore-free form for cross-convention matching (ifngamma ↔ ifn_gamma)."""
    return s.replace("_", "")


def _fuzzy_literature_key(canon: str) -> str | None:
    """Return best-matching KNOWN_FINDINGS key or None."""
    if canon in _KNOWN_CANON:
        return _KNOWN_CANON[canon]
    # underscore-normalised comparison
    canon_n = _norm(canon)
    for kc, orig in _KNOWN_CANON.items():
        if canon_n == _norm(kc):
            return orig
    for kc, orig in _KNOWN_CANON.items():
        kn = _norm(kc)
        if canon_n.startswith(kn) or kn.startswith(canon_n):
            return orig
    for kc, orig in _KNOWN_CANON.items():
        kn = _norm(kc)
        if kn in canon_n or canon_n in kn:
            return orig
    return None


# ── Profile annotation ────────────────────────────────────────────────────────

def _direction_from_z(z: float) -> str:
    if np.isnan(z):
        return "stable"
    if z > 1.0:
        return "up"
    if z < -1.0:
        return "down"
    return "stable"


def annotate_literature_context(profile: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'literature_status' column to every row of profile.

    Rules:
    - baseline rows → "not_applicable"
    - z NaN or |z| < 1 → "not_applicable"
    - no matching known finding → "novel"
    - direction matches published → "confirmed"
    - direction opposite to published → "contradicted"
    - published direction "variable" → "confirmed" if elevated
    """
    profile = profile.copy()
    profile["literature_status"] = "not_applicable"

    relevant = (
        (~profile["is_baseline_timepoint"])
        & profile["z_score"].notna()
        & (profile["z_score"].abs() >= 1.0)
    )

    for i in profile[relevant].index:
        raw_name = profile.at[i, "measurement"]
        canon = _canonical(raw_name)
        key = _fuzzy_literature_key(canon)

        if key is None:
            profile.at[i, "literature_status"] = "novel"
            continue

        finding = KNOWN_FINDINGS[key]
        pub_dir = finding["direction"]
        obs_dir = _direction_from_z(float(profile.at[i, "z_score"]))

        if pub_dir == "variable":
            profile.at[i, "literature_status"] = "confirmed"
        elif obs_dir == pub_dir:
            profile.at[i, "literature_status"] = "confirmed"
        else:
            profile.at[i, "literature_status"] = "contradicted"

    counts = profile["literature_status"].value_counts().to_dict()
    log.info("literature_context: %s", counts)
    return profile


# ── Markdown documentation ────────────────────────────────────────────────────

def write_literature_context_md(out_path: Path) -> None:
    """Write LITERATURE_CONTEXT.md from KNOWN_FINDINGS dict."""
    lines = [
        "# Literature Context",
        "## Known Spaceflight Findings — Annotation Reference",
        "",
        "Used by `literature_context.py` to tag each measurement in the",
        "personal profile as `confirmed`, `novel`, or `contradicted`.",
        "",
        "| Measurement | Direction | Source | Note |",
        "|---|---|---|---|",
    ]
    for canon_key, finding in sorted(KNOWN_FINDINGS.items()):
        label = canon_key.replace("_", " ").title()
        row = (
            f"| {label} | {finding['direction']} "
            f"| {finding['source']} "
            f"| {finding['note']} |"
        )
        lines.append(row)

    lines += [
        "",
        "## Status Definitions",
        "",
        "| Status | Definition |",
        "|---|---|",
        "| confirmed | Observed direction matches the published spaceflight finding |",
        "| novel | Elevated (|z| ≥ 1) but no matching published finding exists |",
        "| contradicted | Direction opposite to the published finding |",
        "| not_applicable | Baseline timepoint, stable signal (|z| < 1), or no z-score |",
        "",
        "## Sources",
        "",
        "- Crucian et al. 2014. J Interferon Cytokine Res — 10 ISS crew, cytokine profiles",
        "- Crucian et al. 2015. J Interferon Cytokine Res — Th1/Th2 dysregulation",
        "- Crucian et al. 2008. Aviat Space Environ Med — CBC changes at landing",
        "- Mehta et al. 2013. J Allergy Clin Immunol — herpesvirus & immune dysregulation",
        "- Makedonas et al. 2019. Front Immunol — monocyte/T-cell spaceflight phenotype",
        "- Trudel et al. 2020. Nat Med — space anemia mechanism",
        "- Voorhies et al. 2019. NPJ Microgravity — oral/nasal microbiome ISS",
        "- Scott et al. 2012. vascular adaptation review",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    log.info("literature_context: wrote %s", out_path)
