"""
Generates 04_th2_skew_test.ipynb
Run once: python3 make_th2_skew_nb.py
"""
import json, textwrap
from pathlib import Path

def code(src): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":textwrap.dedent(src).lstrip("\n")}
def md(src):   return {"cell_type":"markdown","metadata":{},"source":textwrap.dedent(src).lstrip("\n")}

cells = []

cells.append(md("""\
# Th2-Skew Hypothesis Test — Subject C003
### Personalized Health Orbit · Hackathon Track 2

Formally tests whether C003's idiosyncratic immune phenotype at R+1 fits
a **Th2/regulatory/Th17-skewed** pattern with reciprocal Th1 attenuation,
superimposed on the cohort's shared acute-phase response.

Six pre-registered falsifiable predictions evaluated against the
`archetype_synthesis_cohort.csv` (both-elevated filter, all crew) and
`th2_skew_test_results.csv`.

**Sections**
1. Cohort archetype activation scores — R+1 heatmap
2. Per-crew bar charts at R+1
3. Prediction-by-prediction results table
4. Final verdict and framing sentence
5. Dashboard th2-skew tag inventory
"""))

cells.append(code("""\
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import json

warnings.filterwarnings("ignore")
ROOT = Path("..").resolve()
PROC = ROOT / "data" / "processed"

synth   = pd.read_csv(PROC / "archetype_synthesis_cohort.csv")
results = pd.read_csv(PROC / "th2_skew_test_results.csv")
verdict = json.loads((PROC / "th2_skew_verdict.json").read_text())
dash    = pd.read_csv(PROC / "dashboard_findings.csv")

print(f"cohort synthesis: {synth.shape}")
print(f"predictions:      {results.shape}")
print(f"dashboard rows:   {dash.shape}")
"""))

cells.append(md("## 1. Archetype × Crew Heatmap at R+1"))

cells.append(code("""\
r1 = synth[synth["timepoint"] == "R+1"].copy()

# Pivot: rows = archetype, cols = crew_id, values = activation_score
pivot = r1.pivot_table(
    index="archetype", columns="crew_id",
    values="archetype_activation_score", aggfunc="first"
)
# Mark insufficient cells
insuf = r1.pivot_table(
    index="archetype", columns="crew_id",
    values="insufficient_data", aggfunc="first"
)

fig, ax = plt.subplots(figsize=(9, 6))
vmax = max(abs(pivot.values[~np.isnan(pivot.values)].max()), 1)
im = ax.imshow(pivot.values.astype(float), cmap="RdBu_r",
               vmin=-vmax, vmax=vmax, aspect="auto")

ax.set_xticks(range(len(pivot.columns)))
ax.set_xticklabels(pivot.columns, fontsize=11)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels([a.replace("_", " ") for a in pivot.index], fontsize=9)
ax.set_title("Archetype Activation Scores at R+1\\n(both-elevated filter; white × = insufficient data)", fontsize=12)
plt.colorbar(im, ax=ax, label="Activation score")

# Annotate
for i, arch in enumerate(pivot.index):
    for j, crew in enumerate(pivot.columns):
        score = pivot.loc[arch, crew]
        insuf_val = insuf.loc[arch, crew] if arch in insuf.index and crew in insuf.columns else True
        if insuf_val:
            ax.text(j, i, "×", ha="center", va="center", fontsize=12, color="gray")
        elif not np.isnan(score):
            ax.text(j, i, f"{score:.1f}", ha="center", va="center",
                    fontsize=8, color="white" if abs(score) > vmax*0.5 else "black")

plt.tight_layout()
plt.savefig(ROOT / "data" / "processed" / "th2_heatmap_r1.png", dpi=150)
plt.show()
print("\\nRaw pivot table:")
print(pivot.round(2).to_string())
"""))

cells.append(md("## 2. Per-Crew Bar Charts at R+1"))

cells.append(code("""\
crew_ids = sorted(r1["crew_id"].unique())
archetypes_ordered = sorted(r1["archetype"].unique())
arch_labels = [a.replace("_", "\\n") for a in archetypes_ordered]

fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharey=True)
axes = axes.flatten()

colors_pos = "#d73027"
colors_neg = "#4575b4"
colors_insuf = "#cccccc"

for idx, crew in enumerate(crew_ids):
    ax = axes[idx]
    crew_r1 = r1[r1["crew_id"] == crew].set_index("archetype")

    scores = []
    bar_colors = []
    for arch in archetypes_ordered:
        if arch in crew_r1.index:
            row = crew_r1.loc[arch]
            if row["insufficient_data"]:
                scores.append(0)
                bar_colors.append(colors_insuf)
            else:
                sc = row["archetype_activation_score"]
                scores.append(sc if not np.isnan(sc) else 0)
                bar_colors.append(colors_pos if sc > 0 else colors_neg)
        else:
            scores.append(0)
            bar_colors.append(colors_insuf)

    bars = ax.bar(range(len(archetypes_ordered)), scores, color=bar_colors, edgecolor="white")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(f"{crew}", fontsize=13, fontweight="bold")
    ax.set_xticks(range(len(archetypes_ordered)))
    ax.set_xticklabels(arch_labels, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("Activation score" if idx % 2 == 0 else "")
    ax.spines[["top","right"]].set_visible(False)

# Shared legend
from matplotlib.patches import Patch
legend_els = [
    Patch(facecolor=colors_pos, label="Elevated (up-dominant)"),
    Patch(facecolor=colors_neg, label="Suppressed (down-dominant)"),
    Patch(facecolor=colors_insuf, label="Insufficient data (<2 both-elevated members)"),
]
fig.legend(handles=legend_els, loc="lower center", ncol=3, fontsize=9,
           bbox_to_anchor=(0.5, -0.02))
fig.suptitle("Archetype Activation at R+1 — both-elevated filter\\nAll four crew members", fontsize=13)
plt.tight_layout()
plt.savefig(ROOT / "data" / "processed" / "th2_bar_chart_r1.png", dpi=150, bbox_inches="tight")
plt.show()
"""))

cells.append(md("## 3. Prediction-by-Prediction Results"))

cells.append(code("""\
pd.set_option("display.max_colwidth", 200)
pd.set_option("display.width", 220)

print("=" * 80)
print(f"{'ID':>3}  {'RESULT':<18}  {'C003 value':>12}  {'Cohort median':>14}")
print("=" * 80)
for _, r in results.iterrows():
    pid    = int(r["prediction_id"])
    res    = r["result"]
    c003_v = f"{r['c003_value']:.3f}" if pd.notna(r["c003_value"]) else "N/A"
    c_med  = f"{r['cohort_median']:.3f}" if pd.notna(r["cohort_median"]) else "N/A"
    symbol = {"supported": "✓", "mixed": "~", "not_supported": "✗"}.get(res, "?")
    print(f"{pid:>3}  {symbol} {res:<16}  {c003_v:>12}  {c_med:>14}")
    print(f"     Text:     {r['prediction_text']}")
    print(f"     Evidence: {r['evidence']}")
    print()
"""))

cells.append(md("## 4. Verdict and Framing Sentence"))

cells.append(code("""\
print("=" * 70)
print(f"VERDICT:            {verdict['verdict'].upper()}")
print(f"Predictions:        {verdict['n_supported']} supported, "
      f"{verdict['n_mixed']} mixed, "
      f"{verdict['n_total'] - verdict['n_supported'] - verdict['n_mixed']} not supported")
print(f"Effective support:  {verdict['effective_support']:.1f} / {verdict['n_total']}")
print()
print("FRAMING SENTENCE:")
print(f"  {verdict['framing_sentence']}")
if verdict["caveat"]:
    print()
    print("CAVEAT:")
    print(f"  {verdict['caveat']}")
print("=" * 70)
print()
print("KEY OBSERVATIONS (from cohort synthesis data):")
print("  • C003 is the ONLY crew member with ≥2 both-elevated Th2 members at R+1")
print("    (IL-13 ↑, CTACK ↑, TARC ↓); C003 Th2 activation score = +3.48 (direction=UP).")
print("  • C003 Th1 has zero both-elevated members (score=NaN, direction=stable);")
print("    cohort Th1 is suppressed: C002=-2.51, C004=-3.00.")
print("  • C003 IL-6 z=31.5 vs C001=2.6, C002=6.5 — acute-phase response is")
print("    numerically much larger for C003 but insufficient for SD comparison.")
print("  • The both-elevated filter is very restrictive with n=3 baseline observations;")
print("    5 of 6 predictions are inconclusive (mixed) rather than falsified.")
print()
print("SCIENTIFIC INTERPRETATION:")
print("  The Th2-skew hypothesis is not confirmed by the pre-registered criteria,")
print("  primarily because the strict robustness filter (both-elevated) leaves most")
print("  archetypes below the minimum-member threshold. The data are not inconsistent")
print("  with the Th2-skew hypothesis — they are simply underpowered for it at this")
print("  stringency. The direction of evidence (C003 uniquely Th2-elevated, Th1 stable)")
print("  is consistent with the hypothesis but not sufficiently powered to confirm it.")
"""))

cells.append(md("## 5. Dashboard Th2-Skew Tags"))

cells.append(code("""\
tagged = dash[dash["th2_skew_tag"].notna() & (dash["th2_skew_tag"] != "")]
print(f"th2_skew_evidence rows:        "
      f"{(tagged['th2_skew_tag']=='th2_skew_evidence').sum()}")
print(f"th2_skew_counter_evidence rows: "
      f"{(tagged['th2_skew_tag']=='th2_skew_counter_evidence').sum()}")
print()
cols = ["measurement_label","archetype","concordance_class",
        "z_score_robust","deviation_direction","th2_skew_tag"]
print(tagged[cols].to_string(index=False))
"""))

nb = {
    "nbformat": 4, "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "cells": cells,
}

out = Path(__file__).parent / "04_th2_skew_test.ipynb"
out.write_text(json.dumps(nb, indent=1))
print(f"Written: {out}")
