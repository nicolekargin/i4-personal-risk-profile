# Health Orbit
### Personalized multi-omics health profiling for one Inspiration 4 crew member

**Live demo:** https://nicolekargin.github.io/i4-personal-risk-profile/

Built by Nicole Kargin and Lucy Taylor for **Track 2: Individualized Risk Profile** at the Sovereignty Hackathon, University of Austin, May 2026.

---

## What it shows

Standard clinical tests compare your values against population reference ranges. Health Orbit compares them against *your own pre-flight baseline.*

> C003's white blood cell count at R+1 was approximately 7.0 K/μL — within the clinical reference range of 3.8–10.8 K/μL — yet 10 standard deviations below C003's own pre-flight baseline. No standard clinical test would have flagged this.

This dashboard maps how one Inspiration 4 crew member (C003) responded to 3 days in space, across:
- 71 cytokine measurements (Eve panel, OSD-575)
- Complete blood count over 7 timepoints (OSD-569)
- Oral/nasal microbiome (OSD-572)

## Key findings

| Finding | Deviation | Missed by standard tests? |
|---|---|---|
| IL-6 at R+1 | +31.5 SD (mean+SD) · 2.9× fold | Yes — no clinical range |
| WBC at R+1 | −10.2 SD below personal baseline | Yes — within clinical range |
| I-309 at R+194 | +41.0 SD (robust z) · 8.3× fold | Yes — no clinical range |
| 34/71 cytokines | Not recovered at R+194 (48% incomplete) | Invisible to standard care |

## Methodology

Personal baselines computed from 3 pre-flight measurements (L-92, L-44, L-3 days).
Every finding must survive both mean+SD and median+MAD normalization (robustness test).
Bootstrap 95% CIs (n=1000 resamples) on every z-score.
Cohort comparisons are direction-of-effect concordance only — n=4 prohibits inferential statistics.

**Full pipeline:** [PIPELINE.md](PIPELINE.md)

## Data sources

Overbey EG, Kim JK, Tierney BT et al. *Nature* 632, 1145–1154 (2024). doi:10.1038/s41586-024-07639-y

NASA Open Science Data Repository:
- OSD-569 (CBC)
- OSD-572 (metagenomics)
- OSD-575 (Eve cytokine panel)

> **n=4 caveat:** This study covers 4 crew members. All cohort comparisons are descriptive direction-of-effect concordance only. No inferential statistics are reported.

## Repository structure

```
docs/          # Dashboard (React + Recharts, deployed via GitHub Pages)
data/processed/  # Processed CSVs from analysis pipeline
analysis/      # Python analysis scripts
PIPELINE.md    # Full methodology documentation
```
