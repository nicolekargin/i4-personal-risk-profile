"""
Generate notebooks/03_verification_and_synthesis.ipynb from the
verification pipeline outputs.

Run from the i4-personal-risk-profile directory:
    python3 notebooks/make_verification_nb.py
"""
import json
from pathlib import Path

NB_PATH = Path(__file__).parent / "03_verification_and_synthesis.ipynb"


def code(src: str | list[str]) -> dict:
    lines = src if isinstance(src, list) else src.split("\n")
    lines = [ln + "\n" for ln in lines[:-1]] + [lines[-1]]
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines,
    }


def md(src: str) -> dict:
    lines = src.split("\n")
    lines = [ln + "\n" for ln in lines[:-1]] + [lines[-1]]
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": lines,
    }


CELLS = [
    md("""# Verification & Synthesis — Subject C003
**Personalized Health Orbit · Inspiration 4**

This notebook validates the outputs from `run_verification.py`:
1. Fragility flags (constant-baseline / unstable-CI / lower-CI-below-threshold)
2. Robust z-scores (median ± MAD parallel pipeline)
3. Methods concordance (mean+SD vs median+MAD)
4. Cytokine archetype activation
5. Literature context annotation
6. Dashboard-ready findings summary"""),

    # ── Setup ──────────────────────────────────────────────────────────────────
    md("## 0 · Setup"),
    code("""\
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

PROC = Path("data/processed")
DOCS = Path("docs")

prof    = pd.read_csv(PROC / "personal_profile_C003.csv", low_memory=False)
narr    = pd.read_csv(PROC / "narrative_ranking.csv")
dash    = pd.read_csv(PROC / "dashboard_findings.csv")
arch    = pd.read_csv(PROC / "archetype_synthesis.csv")
traj    = pd.read_csv(PROC / "headline_trajectories.csv")
kinetics = pd.read_csv(PROC / "recovery_kinetics_C003.csv")

prof["is_baseline_timepoint"] = prof["is_baseline_timepoint"].astype(bool)
focal = prof[prof["crew_id"] == "C003"].copy()

print(f"Profile: {len(prof):,} rows × {prof.shape[1]} cols")
print(f"Dashboard findings: {len(dash):,} rows")
print(f"Archetype synthesis: {len(arch)} rows")
print(f"Headline trajectories: {len(traj)} rows")
print(f"Narrative ranking: {len(narr):,} rows")\
"""),

    # ── 1. Fragility ───────────────────────────────────────────────────────────
    md("""## 1 · Fragility Flags

Three fragility criteria:
- **constant-baseline** — pre-flight SD < 1e-8 (no variability to define a baseline)
- **unstable-ci** — bootstrap CI width > 10 × max(|z|, 0.5) (z-score dominated by baseline estimation noise)
- **lower-ci-below-threshold** — conservative |z| < 1.0 (signal may be noise even at its upper bound)"""),

    code("""\
# --- 1a. Overall fragility breakdown ---
print("=== Fragility breakdown (all 124,541 rows) ===")
print(prof["is_baseline_fragile"].value_counts().to_string())
print()

# Decompose by reason
from collections import Counter
reason_counts = Counter()
for r in prof["fragility_reason"].dropna():
    for part in str(r).split(","):
        if part:
            reason_counts[part.strip()] += 1
print("Fragility reason breakdown:")
for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {cnt:,}")\
"""),

    code("""\
# --- 1b. Fragility by layer ---
layer_frag = (
    prof.groupby("layer")["is_baseline_fragile"]
    .agg(total="count", fragile="sum")
)
layer_frag["pct_fragile"] = (layer_frag["fragile"] / layer_frag["total"] * 100).round(1)
print("Fragility by layer:")
print(layer_frag.to_string())\
"""),

    code("""\
# --- 1c. Top fragile immune measurements ---
immune_fragile = (
    focal[focal["layer"] == "immune"]
    .groupby("measurement")
    .agg(
        n_fragile=("is_baseline_fragile", "sum"),
        n_total=("is_baseline_fragile", "count"),
        reasons=("fragility_reason", lambda x: "|".join(sorted(set(str(v) for v in x if str(v) and v == v))))
    )
    .query("n_fragile > 0")
    .sort_values("n_fragile", ascending=False)
)
print(f"Fragile immune measurements: {len(immune_fragile)}")
print(immune_fragile.head(15).to_string())\
"""),

    # ── 2. Robust z-scores ─────────────────────────────────────────────────────
    md("""## 2 · Robust z-Scores (Median ± MAD)

The median+MAD pipeline runs in parallel with the mean+SD baseline, providing a
robustness check. Under normality, MAD × 1.4826 ≈ SD; divergence between the two
z-score estimates flags outlier-sensitive results.

**Caveat:** With n=3 baseline timepoints, ~78% of bootstrap resamples produce MAD=0
(non-distinct draws), so bootstrap CIs are degenerate (zero-width). This is an honest
representation of the limitation — the robust CI cannot be wider than the point estimate
with only 3 baseline samples."""),

    code("""\
# --- 2a. Robust z-score availability ---
c003_post = focal[~focal["is_baseline_timepoint"]].copy()
has_z = c003_post["z_score"].notna()
has_zr = c003_post["z_score_robust"].notna()

print(f"C003 post/in-flight rows with z_score: {has_z.sum():,}")
print(f"C003 post/in-flight rows with z_score_robust: {has_zr.sum():,}")
print(f"Both available: {(has_z & has_zr).sum():,}")\
"""),

    code("""\
# --- 2b. Correlation: z_score vs z_score_robust ---
both = c003_post[has_z & has_zr].copy()
both["abs_z"] = both["z_score"].abs()
both["abs_zr"] = both["z_score_robust"].abs()

# Cap at 50 for plotting (extreme microbial z-scores)
cap = 50
plot_z  = both["abs_z"].clip(upper=cap)
plot_zr = both["abs_zr"].clip(upper=cap)

fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(plot_z, plot_zr, alpha=0.07, s=6, color="steelblue", label="measurements")
ax.axline((0, 0), slope=1, color="crimson", lw=1, ls="--", label="x=y")
ax.set_xlabel("|z_score| (mean+SD, capped at 50)")
ax.set_ylabel("|z_score_robust| (median+MAD, capped at 50)")
ax.set_title("Method concordance: point z-scores (C003)")
ax.legend(fontsize=9)
plt.tight_layout()
plt.savefig("docs/fig_robust_z_scatter.png", dpi=150, bbox_inches="tight")
plt.show()

from scipy.stats import spearmanr
rho, pval = spearmanr(both["abs_z"], both["abs_zr"])
print(f"Spearman ρ = {rho:.3f}  (p ≈ {pval:.2e})")\
"""),

    code("""\
# --- 2c. Methods concordance breakdown ---
print("methods_concordance (all 124,541 rows):")
print(prof["methods_concordance"].value_counts().to_string())
print()
c003_mc = focal[~focal["is_baseline_timepoint"]]["methods_concordance"].value_counts()
print("methods_concordance (C003 post-flight only):")
print(c003_mc.to_string())\
"""),

    code("""\
# --- 2d. Discordant signals: where methods disagree ---
discordant = focal[
    (~focal["is_baseline_timepoint"])
    & (focal["methods_concordance"] == "discordant")
    & (focal["z_score"].abs() >= 2)
].copy()
print(f"Discordant rows with |z_mean| ≥ 2: {len(discordant)}")
if not discordant.empty:
    show = discordant.sort_values("z_score", key=abs, ascending=False)
    print(show[["layer","measurement","timepoint","z_score","z_score_robust","methods_concordance"]].head(10).to_string(index=False))\
"""),

    # ── 3. Archetype Synthesis ─────────────────────────────────────────────────
    md("""## 3 · Cytokine Archetype Activation

Eleven immune-functional archetypes are scored at each post-flight timepoint.
`archetype_activation_score` = signed(mean z) × mean|z| × (n_elevated / n_members)."""),

    code("""\
# --- 3a. Archetype summary ---
print("Archetype synthesis: %d rows" % len(arch))
print()
top_arch = arch.reindex(arch["archetype_activation_score"].abs().sort_values(ascending=False).index)
print(top_arch[["archetype","timepoint","n_members","n_elevated",
                "direction_dominant","archetype_activation_score"]].head(12).to_string(index=False))\
"""),

    code("""\
# --- 3b. Heatmap of archetype activation across timepoints ---
pivot = arch.pivot_table(
    index="archetype", columns="timepoint",
    values="archetype_activation_score", aggfunc="first"
)
# Order timepoints
tp_order = ["R+1", "R+45", "R+82", "R+194"]
tp_cols = [t for t in tp_order if t in pivot.columns]
pivot = pivot[tp_cols]

fig, ax = plt.subplots(figsize=(7, 5))
vmax = pivot.abs().max().max()
im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
ax.set_xticks(range(len(tp_cols)))
ax.set_xticklabels(tp_cols, fontsize=10)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index, fontsize=9)
plt.colorbar(im, ax=ax, label="archetype_activation_score")
ax.set_title("Cytokine archetype activation (C003)")
plt.tight_layout()
plt.savefig("docs/fig_archetype_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()\
"""),

    code("""\
# --- 3c. Archetype coverage ---
immune_rows = focal[focal["layer"] == "immune"]
arch_coverage = immune_rows["archetype"].value_counts(dropna=False)
no_arch = (immune_rows["archetype"].isna() | (immune_rows["archetype"] == "")).sum()
print(f"Immune rows with archetype assignment: {(~immune_rows['archetype'].isna() & (immune_rows['archetype'] != '')).sum()}")
print(f"Immune rows with no archetype: {no_arch}")
print()
# Unique measurements not in any archetype
unmatched_meas = (
    immune_rows[immune_rows["archetype"].isna() | (immune_rows["archetype"] == "")]
    ["measurement"].unique()
)
print(f"Unmatched measurements ({len(unmatched_meas)}): {sorted(unmatched_meas)}")\
"""),

    # ── 4. Literature Context ──────────────────────────────────────────────────
    md("""## 4 · Literature Context

Each measurement is tagged:
- **confirmed** — direction matches a published spaceflight finding
- **novel** — elevated (|z| ≥ 1) but no matching finding in the reference list
- **contradicted** — direction opposite to the published finding
- **not_applicable** — baseline row, stable signal, or no z-score"""),

    code("""\
# --- 4a. Literature status breakdown ---
print("Literature status (all rows):")
print(prof["literature_status"].value_counts().to_string())
print()
print("Literature status (C003 post-flight, |z| ≥ 1):")
elevated = focal[
    (~focal["is_baseline_timepoint"])
    & (focal["z_score"].abs() >= 1)
]
print(elevated["literature_status"].value_counts().to_string())\
"""),

    code("""\
# --- 4b. Confirmed findings ---
confirmed = focal[focal["literature_status"] == "confirmed"].copy()
confirmed_top = (
    confirmed.sort_values("z_score", key=abs, ascending=False)
    .drop_duplicates(subset=["layer","measurement"])
    .head(15)
)
print("Top confirmed findings (C003):")
print(confirmed_top[["layer","measurement","timepoint","z_score","z_score_robust"]].to_string(index=False))\
"""),

    code("""\
# --- 4c. Contradicted findings ---
contradicted = focal[focal["literature_status"] == "contradicted"].copy()
print(f"Contradicted findings: {len(contradicted)} rows")
contr_top = (
    contradicted.sort_values("z_score", key=abs, ascending=False)
    .drop_duplicates(subset=["layer","measurement"])
    .head(10)
)
if not contr_top.empty:
    print(contr_top[["layer","measurement","timepoint","z_score","z_score_robust","literature_status"]].to_string(index=False))\
"""),

    # ── 5. Dashboard Findings ──────────────────────────────────────────────────
    md("""## 5 · Dashboard Findings

`dashboard_findings.csv` is the single source of truth for the Health Orbit dashboard.
One row per (measurement × peak_timepoint) for all 4,997 C003 signals."""),

    code("""\
# --- 5a. Layer distribution ---
print("Dashboard findings by layer:")
print(dash["layer"].value_counts().to_string())
print()
print("Methods concordance at peak TP (dashboard):")
print(dash["methods_concordance"].value_counts().to_string())\
"""),

    code("""\
# --- 5b. Top-20 findings ---
top20 = dash.head(20)
cols = ["rank_overall","layer","measurement","peak_timepoint",
        "signal_score","methods_concordance","literature_status",
        "concordance_class","is_baseline_fragile"]
print(top20[cols].to_string(index=False))\
"""),

    code("""\
# --- 5c. Top immune findings ---
immune_dash = dash[dash["layer"] == "immune"].sort_values("rank_within_layer").head(15)
print("Top immune signals:")
print(immune_dash[["rank_overall","measurement","peak_timepoint","peak_abs_z",
                   "signal_score","archetype","literature_status",
                   "methods_concordance"]].to_string(index=False))\
"""),

    code("""\
# --- 5d. Fragile signals in top-50 ---
fragile_top50 = dash.head(50)[dash.head(50)["is_baseline_fragile"] == True]
print(f"Fragile signals in top-50: {len(fragile_top50)}")
if not fragile_top50.empty:
    print(fragile_top50[["rank_overall","layer","measurement","fragility_reason",
                          "signal_score"]].to_string(index=False))\
"""),

    # ── 6. Headline Trajectories ───────────────────────────────────────────────
    md("## 6 · Headline Trajectories (Top-20 Signals)"),

    code("""\
# --- 6a. Trajectory data overview ---
print("Headline trajectories: %d rows across %d measurements" % (
    len(traj), traj["measurement"].nunique()))
print()
print("Timepoints covered:")
print(traj.groupby("rank_overall")["timepoint"].apply(list).head(5).to_string())\
"""),

    code("""\
# --- 6b. Plot: IL-6 full trajectory with CI ---
il6 = traj[traj["measurement"] == "il_6"].copy() if "il_6" in traj["measurement"].values else pd.DataFrame()

if not il6.empty:
    il6 = il6.sort_values("days_from_launch")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axhline(0, color="gray", lw=0.8, ls="--")
    ax.axhline(2, color="orange", lw=0.8, ls=":", label="z=±2")
    ax.axhline(-2, color="orange", lw=0.8, ls=":")
    ax.fill_between(il6["days_from_launch"],
                    il6["z_score_ci_low"].clip(-20, 50),
                    il6["z_score_ci_high"].clip(-20, 50),
                    alpha=0.2, color="steelblue", label="95% bootstrap CI")
    ax.plot(il6["days_from_launch"], il6["z_score"].clip(-20, 50),
            "o-", color="steelblue", lw=2, ms=6, label="z_score (mean+SD)")
    if "z_score_robust" in il6.columns:
        ax.plot(il6["days_from_launch"], il6["z_score_robust"].clip(-20, 50),
                "s--", color="crimson", lw=1.5, ms=5, label="z_score_robust (median+MAD)")
    ax.axvspan(-100, 0, alpha=0.06, color="gray", label="pre-flight")
    ax.axvspan(0, 14, alpha=0.06, color="skyblue", label="in-flight (~14d)")
    ax.set_xlabel("Days from launch")
    ax.set_ylabel("z-score")
    ax.set_title("IL-6 trajectory — C003 (z-score relative to personal baseline)")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig("docs/fig_il6_trajectory.png", dpi=150, bbox_inches="tight")
    plt.show()
else:
    print("IL-6 not in top-20 trajectories — plot skipped")\
"""),

    # ── 7. Methods comparison table ────────────────────────────────────────────
    md("""## 7 · Methods Comparison Table

Side-by-side: mean+SD z-score vs median+MAD robust z-score for the top-20 immune signals."""),

    code("""\
top_immune_narr = narr[narr["layer"] == "immune"].head(20)

rows = []
for _, nr in top_immune_narr.iterrows():
    rows.append({
        "measurement":        nr["measurement"],
        "peak_tp":            nr["peak_timepoint"],
        "z_mean_sd":          round(nr["peak_abs_z"], 2),
        "z_robust_at_peak":   round(nr.get("z_score_robust_at_peak", float("nan")), 2),
        "methods_concordance": nr.get("methods_concordance_at_peak", "unknown"),
        "is_fragile":         nr.get("is_baseline_fragile", False),
        "fragility_reason":   nr.get("fragility_reason", ""),
        "signal_score":       round(nr["signal_score"], 3),
        "concordance_class":  nr["concordance_class"],
    })

methods_tbl = pd.DataFrame(rows)
print(methods_tbl.to_string(index=False))\
"""),

    code("""\
print("\\n=== Summary statistics ===")
print(f"Total measurements in narrative ranking: {len(narr):,}")
print(f"Fragile measurements (top-50): {dash.head(50)['is_baseline_fragile'].sum()}")
print(f"Methods-concordant signals (both-elevated): {(dash['methods_concordance'] == 'both-elevated').sum():,}")
print(f"Literature-confirmed signals: {(dash['literature_status'] == 'confirmed').sum():,}")
print(f"Novel elevated signals: {(dash['literature_status'] == 'novel').sum():,}")
print(f"Contradicted signals: {(dash['literature_status'] == 'contradicted').sum():,}")\
"""),
]

notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11.0"},
    },
    "cells": CELLS,
}

NB_PATH.write_text(json.dumps(notebook, indent=1))
print(f"Written: {NB_PATH}  ({len(CELLS)} cells)")
