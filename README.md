# Personalized Health Orbit
### Individualized health risk profiling for SpaceX Inspiration 4 Subject C003

> **🚀 Live dashboard:** [coming soon — link will be added once GitHub Pages deployment is live]

---

## The thesis

Spaceflight changes the human body in measurable ways. But every body is different.

This project takes data from one Inspiration 4 crew member (anonymized as C003) and builds a personal health profile that compares each post-flight measurement to **that individual's own pre-flight baseline** — not population averages. The result reveals something standard clinical tests cannot: deviations that are striking for an individual yet remain within normal population reference ranges.

In one finding: C003's white blood cell count dropped 10 standard deviations below their personal baseline one day after returning from space. A standard lab test would have called the value normal. Personal baselines did not.

That is the case for individualized health monitoring in spaceflight, demonstrated.

---

## Team

- **Nicole Kargin**
- **Lucy Taylor**

Built for the **Sovereignty Hackathon**, University of Austin, May 2026.

---

## Track and scope

**Track 2: Individualized Risk Profile.**

We deliberately chose depth over breadth — one crew member analyzed across three biological layers, with the other three crew members serving as a reference cohort for direction-of-effect concordance only. With n=4, no inferential statistics are possible; every cohort comparison is descriptive.

---

## Headline findings

### 1. C003 mounted a textbook acute-phase inflammatory response one day after return.

**IL-6 elevated 2.9-fold** above C003's pre-flight baseline at R+1 (z = +31.5; 95% CI lower bound +29.9 by mean+SD method, +105.7 by median+MAD method). **Concordant across all four crew members.** Literature status: **confirmed**. The response was incomplete through R+194 — IL-6 remained elevated 6 months later.

### 2. C003's most extreme personal deviation would have been called normal by standard tests.

**WBC dropped 10.2 SD below personal baseline at R+1** while remaining within Quest Diagnostics' clinical reference range (4.0–11.0 K/μL). Population-based reference ranges cannot detect a value that is unusual for a specific individual. This single finding is the strongest argument we can make for individualized monitoring.

### 3. Nearly half of all immune perturbations remained unresolved 194 days post-flight.

Of 71 measured cytokines, **34 (47%) had not returned to personal baseline within the 194-day observation window.** Spaceflight is not a transient stress — it produces sustained physiological alterations.

### 4. C003 exhibits an idiosyncratic immune signature layered on the shared response.

While the cohort showed a shared acute-phase inflammatory response (IL-6, MCP-1, CTACK), C003 *uniquely* mounted a broad activation of type 2 immune markers (IL-4 elevated 5-fold, IL-13 elevated 8-fold, IL-5 elevated through the full 194-day window) accompanied by elevated regulatory IL-10. The other three crew members remained stable on these markers. The pattern is consistent with — though does not formally meet our pre-registered criteria for — classical Th2 polarization.

### 5. Six measurements moved opposite to published spaceflight literature expectations.

WBC, RBC, hemoglobin, hematocrit, MCV, and IFNγ all deviated in directions opposite to typical spaceflight responses documented in long-duration mission data. These contradictions may reflect the unique conditions of a short-duration civilian mission compared to the professional astronaut data underlying most published spaceflight literature.

---

## Methodology

We applied the same rigorous machinery a clinical research team would use, with explicit honesty about the constraints of n=4.

### Personal baselines with bootstrap confidence intervals

Each crew member's baseline is computed from their three pre-flight measurements (L-92, L-44, L-3). Because n=3 baseline samples produces noisy point estimates, we propagate uncertainty into every downstream metric using a 1000-resample bootstrap. Every z-score in the analysis carries an explicit 95% confidence interval that reflects baseline uncertainty.

### Robustness stress test (the methodological centerpiece)

Every finding is computed twice — once using mean ± SD baselines, and once using median ± MAD baselines. These two methods have different failure modes: mean+SD is sensitive to outliers, median+MAD is more robust but can be unstable on small samples. Findings displayed on the dashboard are restricted to those that survive **both** methods (`methods_concordance = "both-elevated"`). This neutralizes the most common methodological challenge to individualized analyses on small baseline samples.

### Cohort comparison via direction-of-effect concordance

n = 4 prohibits inferential statistics. Instead, every measurement at every post-flight timepoint is classified as:
- **Concordant**: ≥2 cohort members agree with C003's direction (shared spaceflight signal)
- **Idiosyncratic**: C003 deviates while the cohort remains stable (personal phenotype)
- **Discordant**: ≥2 cohort members move opposite to C003
- **Ambiguous**: insufficient data or mixed signal

### Cytokine archetype synthesis

Individual cytokines are not the right unit of biological interpretation. We group the 71 measured cytokines into 11 immunological archetypes (acute-phase response, Th1/Th2/Th17 polarization, regulatory response, monocyte/macrophage recruitment, etc.) and compute archetype-level activation scores. This allows phenotype-level claims rather than molecule-level observations.

### Pre-registered hypothesis testing

We pre-registered a six-prediction test of whether C003's idiosyncratic profile fits a Th2-polarization phenotype, with thresholds and decision rules documented before computation. The test was partially supported (2/6 predictions strictly passed; 4/6 inconclusive due to insufficient cohort data after robustness filtering). We report the result honestly rather than re-tuning to achieve a passing verdict. Methodology refinement (when discovered) is documented as a methodological correction in `PIPELINE.md`.

### Literature-context tagging

Each finding is labeled by its relationship to published spaceflight literature: **confirmed** (well-documented response), **novel** (no prior literature), or **contradicted** (observed direction opposite to published expectation). This distinguishes "we recovered known biology" from "we may have observed something new" — both valuable, but different.

### Numerical safety

Baseline-fragility detection identifies measurements where the math is unstable (raw SD < 1e-8, CI ratio > 10×, or lower-CI |z| < 1.0) and excludes them from displayed findings. Microbial z-scores are capped at |z| ≤ 50 in the dashboard layer (preserved in the audit master file) to exclude mathematical extremes from low-baseline rare bacterial functions.

Full methodology is documented in [`PIPELINE.md`](./PIPELINE.md).

---

## Datasets

Three primary datasets, all from NASA's Open Science Data Repository (OSDR):

| Dataset | Layer | What it measures |
|---|---|---|
| **OSD-569** | Clinical | Complete Blood Count (23 analytes with Quest reference ranges, 7 timepoints) |
| **OSD-575** | Immune | Serum cytokine panel (71 analytes, pg/mL, Eve Technologies, 7 timepoints) |
| **OSD-572** | Microbial | Oral and nasal microbiome metagenomics (KEGG functional annotations, 8 timepoints including in-flight) |

Stretch datasets evaluated and deferred: OSD-575 Alamar cytokine panel (incompatible units), OSD-569 RNA-seq (no recovery timepoints), OSD-656 urine inflammation (data quality issues), OSD-571 plasma multi-omics (cohort-aggregated only, no per-individual values).

Timepoints: L-92, L-44, L-3 (pre-flight), FD2, FD3 (in-flight, microbial only), R+1, R+45, R+82, R+194 (post-flight).

---

## Repository structure

```
i4-personal-risk-profile/
│
├── README.md                         ← You are here
├── PIPELINE.md                         Methodological decisions and justifications
│
├── analysis/                           Pipeline modules
│   ├── load.py                           Raw data ingestion from OSDR
│   ├── parse.py                          Sample name parsing (regex-based)
│   ├── transform.py                      log1p, pivots, site filtering
│   ├── baseline.py                       Personal baselines + bootstrap CIs
│   ├── deviation.py                      z-scores, fold-changes, clinical flagging
│   ├── kinetics.py                       Recovery kinetics computation
│   ├── concordance.py                    Direction-of-effect classification
│   ├── archetype.py                      Cytokine functional archetypes
│   ├── literature_context.py             Confirmed/novel/contradicted tagging
│   ├── verify.py                         Fragility + robustness stress test
│   ├── th2_skew_test.py                  Pre-registered hypothesis test
│   ├── narrative.py                      Composite signal scoring + ranking
│   └── dashboard_export.py               Final dashboard-ready findings
│
├── data/processed/                     Output CSVs
│   ├── personal_profile_C003.csv         Master long-format file (~125k rows × 35+ cols)
│   ├── recovery_kinetics_C003.csv        Per-measurement recovery rates
│   ├── cohort_concordance.csv            Direction-of-effect by measurement × timepoint
│   ├── narrative_ranking.csv             Composite signal-strength rankings
│   ├── archetype_synthesis.csv           Archetype activation per timepoint
│   ├── headline_trajectories.csv         Time courses for top findings
│   ├── dashboard_findings.csv            ★ Single source the dashboard reads
│   └── th2_skew_verdict.json             Hypothesis test verdict + framing
│
├── notebooks/                          Validation notebooks
│   ├── 01_data_inventory.ipynb           Initial dataset characterization
│   ├── 02_pipeline_validation.ipynb      Pipeline sanity checks
│   ├── 03_verification_and_synthesis.ipynb   Robustness audit + synthesis
│   └── 04_th2_skew_test.ipynb            Hypothesis test details
│
├── docs/                               Live dashboard (GitHub Pages)
│   ├── index.html                        Dashboard entry point
│   └── dashboard.js                      React component tree
│
└── docs/LITERATURE_CONTEXT.md           Comparison to published spaceflight findings
```

---

## How to navigate this repository

For a judge or reviewer with limited time, here is a recommended reading order:

1. **This README** — the project at a glance.
2. **The live dashboard** (link at top) — the astronaut-facing presentation.
3. **`PIPELINE.md`** — the methodology document. Every analytical choice is justified against alternatives considered. This is the strongest single artifact for evaluating scientific rigor.
4. **`data/processed/dashboard_findings.csv`** — the 70-row CSV that the dashboard renders. The single source of truth.
5. **`notebooks/03_verification_and_synthesis.ipynb`** — the audit trail, including robustness survival rates, fragility flagging, and cross-method comparisons.
6. **`docs/LITERATURE_CONTEXT.md`** — how our findings compare to the published Inspiration 4 literature.

For replication: the entire pipeline runs from raw data to dashboard via `analysis/` modules in dependency order. Every intermediate output is committed for inspection. No external compute or proprietary data required.

---

## Limitations

- **n = 4** crew members prohibits inferential statistics. All cohort comparisons are direction-of-effect concordance only.
- **n = 3** pre-flight timepoints per individual is small for baseline estimation. Bootstrap CIs explicitly represent this uncertainty in every downstream metric.
- **No R+194 microbiome data** exists in the public release; microbial recovery kinetics capped at R+82.
- **Anonymized subject identity** (C003) is not linked to any specific named crew member.
- **Microbiome analysis restricted to oral and nasal cavities** for interpretability; gut, skin, and other body sites not included as primary analysis (the public OSD-572 release covers these but adds complexity without clear payoff for an individualized phenotype).
- **Cytokine analysis uses only the Eve Technologies panel** (pg/mL); the Alamar NULISAseq panel (NPQ scale) cannot be naively merged across units and was deferred.
- **RNA-seq excluded from primary analysis** — the long-read direct RNA-seq dataset has no recovery timepoints beyond R+1 and cannot inform recovery kinetics.

---

## Acknowledgements

- **NASA Open Science Data Repository (OSDR)** for the publicly released Inspiration 4 multi-omics datasets
- **Dr. Overbey** and the SOMA / Inspiration 4 research consortium whose published work provided the literature context for our comparisons
- **The University of Austin** for hosting the Sovereignty Hackathon
- **The Inspiration 4 crew** for participating in this groundbreaking civilian space-medicine research

---

## Status

This project was completed during the May 2026 Sovereignty Hackathon (May 6–9, 2026). Submission deadline: Saturday, May 9, 4:00 PM CT.

Last updated: [auto-fill date on commit]
