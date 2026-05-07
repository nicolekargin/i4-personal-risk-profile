# Health Orbit — SOMA n=1 Longitudinal Risk Pipeline
**Torchlight Biosovereignty Hackathon | Track 2: Individualized Risk Profile**

## Overview
Transforms SOMA/Inspiration4 multi-omics data into astronaut-specific "Health Orbit" dashboards.
Every risk score is fully explainable: raw pg/mL or CPM → personal Z-score → gauge reading.

## Data Provenance

All data sourced from NASA Open Science Data Repository (OSDR).
Programmatic access via `scripts/fetch_data.py` (no authentication required for public studies).
Inventory verified on **2026-05-06** via `scripts/inventory.py`.

---

### OSD-575 — Blood Serum Cytokine Multiplex
**Landing page:** https://osdr.nasa.gov/bio/repo/data/studies/OSD-575/
**Mission:** Inspiration4 (SpaceX, Sept 2021) — 4 crew, 3-day LEO mission
**Assays:** Eve Technologies 65-plex immune panel + cardiovascular panel; Alamar NULISAseq ~200-plex immune panel
**Biological matrix:** Blood serum
**Timepoints:** L-92, L-44, L-3 (pre-flight baselines); R+1, R+45, R+82, R+194 (post-flight return)
**No in-flight (FD) timepoints** — serum draws were not taken during the 3-day flight.

| Local filename | OSDR filename | Size | Contents |
|---|---|---|---|
| `OSD-575_eve_immune_TRANSFORMED.csv` | `LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv` | 41 KB | Eve immune panel, OSDR-normalized. **Primary cytokine file.** rows=samples, Sample Name = `C00X_serum_{TP}` |
| `OSD-575_eve_cardiovascular_TRANSFORMED.csv` | `LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv` | 6 KB | Eve cardiovascular panel, normalized |
| `OSD-575_alamar_immune_TRANSFORMED.csv` | `LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv` | 142 KB | Alamar NULISAseq panel. **Units are NPQ (Normalized Proximity Quantity), not pg/mL.** |
| `OSD-575_eve_immune_SUBMITTED.csv` | `LSDS-8_Multiplex_serum.immune.EvePanel_SUBMITTED.csv` | 107 KB | Eve immune panel raw-submitted (includes `_percent` columns) |
| `OSD-575_eve_cardiovascular_SUBMITTED.csv` | `LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv` | 15 KB | Eve cardiovascular raw-submitted |
| `OSD-575_metadata_ISA.zip` | `OSD-575_metadata_OSD-575-ISA.zip` | 72 KB | ISA-Tab investigation/study/assay metadata sidecar |

**Column schema (TRANSFORMED files):** `{analyte_name}_concentration_picogram_per_milliliter` (Eve) or `{analyte_name}_concentration_npq` (Alamar), plus a corresponding `_percent_normalized_value` column per analyte.

---

### OSD-569 — Complete Blood Count (CBC)
**Landing page:** https://osdr.nasa.gov/bio/repo/data/studies/OSD-569/
**Mission:** Inspiration4 (same 4 crew)
**Assay:** Clinical CBC with differential — 23 analytes including WBC, RBC, Hgb, Hct, platelet count, absolute differentials
**Timepoints:** L-92, L-44, L-3, R+1, R+45, R+82, R+194

| Local filename | OSDR filename | Size | Contents |
|---|---|---|---|
| `OSD-569_CBC_TRANSFORMED.csv` | `LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv` | 9 KB | **Primary CBC file.** rows=samples, Sample Name = `C00X_whole-blood_{TP}_cbc`, triplet columns: `{analyte}_value_`, `{analyte}_range_min_`, `{analyte}_range_max_` |
| `OSD-569_CBC_SUBMITTED.csv` | `LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv` | 26 KB | CBC raw-submitted, **long format**: cols = ANALYTE, VALUE, RANGE_MIN, RANGE_MAX, UNITS, SUBJECT_ID, TEST_DATE |

**Also in OSD-569 (manual download required — too large for auto):**

| Local filename | OSDR filename | Size | Contents |
|---|---|---|---|
| `OSD-569_longread_rnaseq_gene_expression.xlsx` | `GLDS-561_long-readRNAseq_Direct_RNA_seq_Gene_Expression_Processed.xlsx` | 123 MB | Long-read (direct) RNA-seq gene expression processed data |
| `OSD-569_m6A_rnaseq.xlsx` | `GLDS-561_directm6Aseq_Direct_RNA_seq_m6A_Processed_Data.xlsx` | 93 MB | m6A-modified RNA-seq processed data |

---

### OSD-570 — VDJ Repertoire (TCR/BCR)
**Landing page:** https://osdr.nasa.gov/bio/repo/data/studies/OSD-570/
**Mission:** Inspiration4 (same 4 crew)
**Assay:** 10x scRNA-Seq VDJ — B-cell receptor (BCR) and T-cell receptor (TCR) clonotype analysis
**Timepoints:** L-3, R+1, R+45, R+82 (expected; confirm after download)
**Priority:** Lower — listed as optional in Phase 1 spec

| Local filename | OSDR filename | Size | Contents |
|---|---|---|---|
| `OSD-570_VDJ_results.xlsx` | `GLDS-562_scRNA-Seq_VDJ_Results.xlsx` | 52 MB | BCR/TCR repertoire processed results (manual download required) |

---

## Pipeline Execution

```bash
pip install -r requirements.txt

# Phase 1 — Data acquisition and schema inventory
python scripts/fetch_data.py      # downloads all auto-fetchable files
python scripts/inventory.py       # inspects schema; saves data/processed/inventory.json

# Phase 2 (pending real data) — n=1 longitudinal analysis
python scripts/process_baselines.py   # cytokine individualized baselines
python scripts/analyze_trajectories.py
python scripts/honesty_check.py
```

## Output Files
| File | Contents |
|------|----------|
| `data/processed/risk_scores.json` | Per-crew Z-scores, gauge values, 2σ alerts |
| `data/processed/trajectories.json` | Full longitudinal data for all crew × all timepoints |
| `data/processed/multiomics_triangulation.json` | High-confidence cross-layer signals |
| `data/processed/data_quality_report.json` | Missingness, power warnings, n=1 caveats |

## Health Orbit Gauges
Three dimensions, each [0–100], anchored to personal ground baseline:
- **Immune Stability** — deviation in adaptive immune signaling (IL-2, IL-7, IFN-γ, …)
- **Inflammatory Load** — aggregate pro-inflammatory burden (IL-6, IL-8, TNF-α, IP-10, …)
- **Recovery Velocity** — compensatory anti-inflammatory signal (IL-10, IL-1RA, VEGF)

Zero = perfect alignment with pre-flight personal baseline. Higher = further from center.

## Key Scientific References
- Overbey et al., *Nature* 2024 — SOMA multi-omic atlas
- Crucian et al., *NPJ Microgravity* 2020 — Spaceflight immune dysregulation
- Garrett-Bakelman et al., *Science* 2019 — NASA Twins Study
- Bhatt et al., *Cell* 2024 — Single-cell resolution of spaceflight immunome
