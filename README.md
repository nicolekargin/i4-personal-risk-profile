# i4-personal-risk-profile

**Sovereignty Hackathon — Track 2: Individualized Health Risk Profiling**

Subject: SpaceX Inspiration 4 crew member **C003** | Mission: 2021 all-civilian orbital flight | Data source: NASA Open Science Data Repository (OSDR)

---

## What this project does

Translates the multi-omics complexity of the SOMA / Inspiration 4 atlas into individualized, astronaut-readable health intelligence. We focus on a **single crew member (C003)** and build a personal health profile across three biological layers — clinical lab markers, immune cytokine signaling, and oral/nasal microbiome function — using each crew member's own pre-flight measurements as their baseline rather than population norms.

The output is a **Personalized Health Orbit** — an interpretive framework that distinguishes:
- **Shared spaceflight signals** (where C003's response matches the cohort)
- **Personal phenotype signals** (where C003's response is idiosyncratic)
- **Persistent vs. resolving alterations** (recovery kinetics through 194 days post-flight)

## Team

- Nicole Kargin
- Lucy Taylor

## Track and scope

**Track 2: Individualized Risk Profile.** We deliberately chose depth over breadth — one crew member analyzed across three primary datasets, with the other three crew members serving as a reference cohort for direction-of-effect concordance (never for inferential statistics, given n=4).

## Primary findings (preliminary)

- **C003 mounted a major inflammatory event at R+1.** IL-6 elevated 2.9-fold above personal baseline (z = +31.5, 95% CI bootstrap-derived), concordant across all four crew members. Recovery is incomplete through R+194.
- **Most immune perturbations are not transient.** 47% of measured cytokines never returned to personal baseline within the 194-day observation window.
- **Personal phenotype layered on shared signal.** Roughly half of C003's strongest immune responses are idiosyncratic to C003 while the cohort remained stable. Candidate Th2-skew framing under formal evaluation.
- **Clinically normal is not personally normal.** C003's white blood cell count dropped 10.2 SD below personal baseline at R+1 while remaining within Quest Diagnostics' clinical reference range — illustrating why individualized monitoring matters.

## Methodology summary

- Personal baselines computed from each individual's pre-flight timepoints (L-92, L-44, L-3)
- Bootstrap 95% confidence intervals on all z-scores (1000 resamples) to honestly represent baseline uncertainty
- Robustness stress test: every finding re-computed under both mean+SD and median+MAD baseline methods; only findings that survive both are displayed
- Cohort comparisons reported only as direction-of-effect concordance, never as inferential statistics
- Cytokine measurements grouped into immunological archetypes (acute-phase, Th1/Th2/Th17, regulatory, etc.)
- Literature-context tagging: each finding labeled as confirmed / novel / contradicted relative to published spaceflight findings
- Full methodology documented in `PIPELINE.md`

## Datasets used

- **OSD-569** — Whole-blood Complete Blood Count (CBC), 23 clinical analytes with reference ranges
- **OSD-575** — Serum cytokine panel (Eve Technologies), 71 immune analytes
- **OSD-572** — Oral and nasal microbiome metagenomics, KEGG functional annotations

Stretch datasets (deferred): OSD-575 Alamar cytokine panel, OSD-569 RNA-seq, OSD-656 urine inflammation panel, OSD-571 plasma metabolomics/proteomics.

## Repository structure

```
i4-personal-risk-profile/
├── analysis/                # Pipeline modules (loading, parsing, baselines, deviation, archetypes, etc.)
├── data/processed/          # Output CSVs (master profile, kinetics, concordance, dashboard-ready findings)
├── notebooks/               # Data inventory + verification + hypothesis-test notebooks
├── docs/                    # Literature context and methodology documentation
└── PIPELINE.md              # Detailed methodological justifications
```

## Limitations

- **n = 4** prohibits inferential statistics; all cohort comparisons are direction-of-effect concordance only
- **No R+194 microbiome data** exists; microbial recovery kinetics capped at R+82
- **Eve and Alamar cytokine panels cannot be directly merged** due to different unit scales (pg/mL vs. NPQ)
- **RNA-seq has no recovery timepoints** beyond R+1, so cannot inform recovery velocity
- **Microbiome analysis restricted to oral and nasal cavities** for interpretability; gut/skin sites deferred to stretch goals

## Status

In progress — analysis pipeline complete, dashboard layer in development, formal hypothesis tests being refined.

---

*Built for the Torchlight Hackathon at the University of Austin, May 2026. Sponsored by the Space Exploration and Research Agency and BioAstra.*
