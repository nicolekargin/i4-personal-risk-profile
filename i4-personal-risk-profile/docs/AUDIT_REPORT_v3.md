# Health Orbit Dashboard — Phase 3 Verification Report
**Generated:** 2026-05-09  
**Scope:** Pre-submission factual cleanup — verification only (no dashboard changes in this file)  
**Source CSVs:** `data/processed/cohort_concordance.csv`, `data/processed/personal_profile_C003.csv`

---

## 1. Hgb, Hct, RBC — Cohort Concordance at Literature Contradiction Timepoints

Source: `data/processed/cohort_concordance.csv`  
Column order: `layer, measurement, site, timepoint, c003_z, c003_direction, cohort_mean_z, cohort_sd_z, cohort_n, cohort_direction_agree, concordance_class`

| Measurement | Timepoint (as shown in dashboard) | c003_z | c003_direction | cohort_n | cohort_direction_agree | concordance_class | Assessment |
|---|---|---|---|---|---|---|---|
| red_blood_cell_count | R+45 | +6.765 | up | 3 | **0** | **idiosyncratic** | **C003 only** — 0 of 3 other crew elevated |
| hemoglobin | R+45 | +1.452 | up | 3 | **0** | **idiosyncratic** | **C003 only** — 0 of 3 other crew elevated |
| hematocrit | R+82 | +3.121 | up | 3 | **1** | **discordant** | **2 of 4 crew elevated** — C003 + 1 other; 2 others not elevated |

**Verdict:** None of the three are cohort-wide. RBC and Hgb are C003-specific findings (idiosyncratic). Hct at R+82 is split 2/4. Current dashboard CONTRADICTED_FINDINGS notes do not falsely claim cohort-wide behavior, but they also do not mention cohort concordance. Fix B should add explicit concordance framing to the notes.

**Additional context checked:**
- Hematocrit at R+45 (also in CSV): c003_z=+2.806, cohort_direction_agree=0, idiosyncratic — but dashboard uses R+82 timepoint, which is correct as it shows the later persistence.
- Hemoglobin at R+82 (also in CSV): c003_z=+1.151, cohort_direction_agree=1, discordant — not the dashboard timepoint; R+45 is used.

---

## 2. Monocytes — Peak Deviation and z-Values at R+1 and R+194

Source: `data/processed/personal_profile_C003.csv`, measurement=`monocytes` (% form), crew_id=`C003`

| Timepoint | z_score (mean+SD) | z_score_robust (median+MAD) | value_raw (%) | clinical_flag |
|---|---|---|---|---|
| **R+1** | **5.692004** | **4.384190** | 9.4 | in-range |
| **R+194** | **7.687901** | **5.901794** | 10.3 | in-range |

**R+1:** z = 5.692 ≈ **+5.7 SD** (mean+SD). Both methods confirm signal (robust z = 4.38 > threshold). Value 9.4% is within reference range (0–13%).  
**R+194:** z = 7.688 ≈ **+7.7 SD** (mean+SD). Peak timepoint. Robust z = 5.90. Value 10.3% is within reference range.  

**Current dashboard shows R+194 only (7.7 SD).** R+1 finding (5.7 SD) is not displayed. Both timepoints confirm a persistent monocyte elevation through the 194-day window — the persistence narrative. Fix D should add R+1 as a second row.

---

## 3. IL-4 and IL-13 Fold-Changes — Exact CSV Values

Source: `data/processed/personal_profile_C003.csv`

| Measurement | Crew | Timepoint | fold_change (raw) | To 3 decimals | To 2 decimals | Dashboard PERSONAL_FINDINGS | MISSED_CYTOKINE |
|---|---|---|---|---|---|---|---|
| il_4 | C003 | R+194 | 5.153917050691244 | **5.154** | **5.15** | `foldChange: 5.15` ✅ | `"5.2× fold"` ❌ |
| il_13 | C003 | R+1 | 8.042047531992688 | **8.042** | **8.04** | `foldChange: 8.04` ✅ | `"8.0× fold"` ❌ |

**Rounding inconsistency confirmed:** PERSONAL_FINDINGS cards render via `{foldChange.toFixed(2)}` → 5.15× and 8.04× correctly. But MISSED_CYTOKINE hardcodes "5.2× fold" (rounds away the .15 precision) and "8.0× fold" (rounds away the .04 precision). The dashboard thus displays 5.15× in one section and 5.2× in another for the same finding.

**Also checked for full MISSED_CYTOKINE audit:**
- IL-6 fold_change = 2.897078 → 2.90 (hardcoded as "2.9×" — loses 1 decimal)
- I-309 fold_change = 8.324503 → 8.32 (hardcoded as "8.3×" — loses 1 decimal)

---

## Summary: What Phase 3 Fixes Should Do

| Fix | Location | Change |
|---|---|---|
| A | CONTRADICTED_FINDINGS[MCV].observedNote | "all 4 crew shifted" → "3 of 4 crew shifted (C001: stable)" |
| A | CONTRADICTED_FINDINGS[MCV].note | "dropped cohort-wide" → "dropped in 3 of 4 crew; C001 remained at baseline" |
| B | CONTRADICTED_FINDINGS[RBC].note | Add: "C003-specific: 0 of 3 other crew shared this elevation." |
| B | CONTRADICTED_FINDINGS[Hgb].note | Add: "C003-specific: 0 of 3 other crew elevated." |
| B | CONTRADICTED_FINDINGS[Hct].note | Replace with: "2 of 4 crew elevated (C003 + 1 other); C003 elevation persists 82 days post-flight." |
| C | FindingCard badge text | "vs. literature: contradicted" → "literature mismatch" (applies to IFNγ and MCV cards) |
| D | MISSED_CBC Monocytes | Replace single R+194 row with two rows: R+1 (+5.7 SD) and R+194 (+7.7 SD) |
| E | MISSED_CYTOKINE IL-4 | "5.2× fold" → "5.15× fold" |
| E | MISSED_CYTOKINE IL-13 | "8.0× fold" → "8.04× fold" |
| E | MISSED_CYTOKINE IL-6 | "2.9× fold" → "2.90× fold" |
| E | MISSED_CYTOKINE I-309 | "8.3× fold" → "8.32× fold" |
| F(i) | IL6MiniChart XAxis ticks | Remove -3 from ticks array (L-3 and R+1 overlap at 4-day separation) |
| F(ii) | IL6MiniChart ReferenceLine label | Add `fontStyle: 'italic'` to C003 baseline label |
| G | WBCDualScale SVG | Expand viewBox to 560×120, push reference bar and axis down 10px to clear value label overlap |

*Report generated by automated read-only verification. All values traced to specific CSV rows.*
