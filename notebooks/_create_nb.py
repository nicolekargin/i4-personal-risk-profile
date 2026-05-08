"""Generate notebooks/01_data_inventory.ipynb from structured cell definitions."""
import json, uuid, pathlib

ROOT = pathlib.Path(__file__).parent

def uid(): return str(uuid.uuid4())[:8]

def md(src): return {"cell_type":"markdown","id":uid(),"metadata":{},"source":src}
def code(src): return {"cell_type":"code","execution_count":None,"id":uid(),"metadata":{},"outputs":[],"source":src}

SETUP = '''import io, re, sys, warnings
import numpy as np
import pandas as pd

# ── dependency guard ────────────────────────────────────────────────────────────
for pkg, pip_name in [("openpyxl","openpyxl"),("requests","requests")]:
    try: __import__(pkg)
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable,"-m","pip","install",pip_name,"-q"])

import requests
warnings.filterwarnings("ignore")

# ── constants ──────────────────────────────────────────────────────────────────
CREW_RE    = re.compile(r\'(C00[1-4])\', re.IGNORECASE)
TP_RE      = re.compile(r\'(L-\\\\d+|R\\\\+\\\\d+|FD\\\\d+)\')
TP_ORDER   = [\'L-92\',\'L-44\',\'L-3\',\'FD1\',\'FD2\',\'FD3\',\'R+1\',\'R+45\',\'R+82\',\'R+194\']
CREW_ORDER = [\'C001\',\'C002\',\'C003\',\'C004\']
RESULTS    = {}   # accumulates dataset summaries for synthesis table

# ── helpers ────────────────────────────────────────────────────────────────────
def fetch(url, timeout=600):
    """Fetch URL into memory (follows OSDR→S3 redirect)."""
    r = requests.get(url, allow_redirects=True, timeout=timeout,
                     headers={"User-Agent":"SOMA-Inventory/1.0"})
    r.raise_for_status()
    return io.BytesIO(r.content)

def parse_s(s):
    cm = CREW_RE.search(str(s)); tm = TP_RE.search(str(s))
    return (cm.group(1).upper() if cm else None, tm.group(1) if tm else None)

def sort_tp(tps):
    return sorted(tps, key=lambda x: TP_ORDER.index(x) if x in TP_ORDER else 99)

def build_cov(strings):
    pairs = [parse_s(s) for s in strings]
    tps   = sort_tp({t for _,t in pairs if t})
    mat   = pd.DataFrame(0, index=CREW_ORDER, columns=tps or ["—"])
    for crew, tp in pairs:
        if crew in mat.index and tp in mat.columns: mat.loc[crew,tp] = 1
    return mat

def build_cov_explicit(df, crew_col, tp_col):
    tps = sort_tp(df[tp_col].dropna().unique())
    mat = pd.DataFrame(0, index=CREW_ORDER, columns=tps or ["—"])
    for _,row in df.drop_duplicates([crew_col,tp_col]).iterrows():
        c,t = row[crew_col], row[tp_col]
        if c in mat.index and t in mat.columns: mat.loc[c,t] = 1
    return mat

def miss(df):
    nas  = df.isna().sum(); nas = nas[nas>0].sort_values(ascending=False)
    tot  = df.shape[0]*df.shape[1]; n = int(df.isna().sum().sum())
    return nas, f"{n:,}/{tot:,} ({100*n/max(tot,1):.1f}%)"

def vscale(df):
    nums = df.select_dtypes(include=\'number\')
    if nums.empty: return "no numerics"
    flat = nums.values.ravel(); flat = flat[~np.isnan(flat)]
    if not len(flat): return "all NaN"
    mn,mx,med = float(np.nanmin(flat)),float(np.nanmax(flat)),float(np.nanmedian(flat))
    cs   = nums.sum(); near_cpm = bool(((cs>5e5)&(cs<5e6)).mean()>0.6)
    log_ = mn>=0 and mx<30 and med<15
    ints = np.all(flat==flat.astype(int)) and mx>500
    note = ("CPM-normalized" if near_cpm
            else "log/NPQ scale" if log_
            else "raw counts"   if ints
            else "linear continuous")
    return f"min={mn:.3g}  median={med:.3g}  max={mx:.3g}  → {note}"

def abbrev_dtypes(df, n=10):
    dt = df.dtypes
    if len(dt)<=2*n: return dt
    stub = pd.Series({"… (%d cols omitted) …"%(len(dt)-2*n):"…"})
    return pd.concat([dt.head(n), stub, dt.tail(n)])

def show(df, sample_strings, key, osd, assay, granularity, aggregated, notes=""):
    """Print full characterization and store in RESULTS."""
    rows,cols = df.shape
    mem = df.memory_usage(deep=True).sum()/1e6
    nas, miss_str = miss(df)
    dup_idx = int(df.index.duplicated().sum())

    print(f"Shape : {rows:,} rows × {cols} cols    Memory : {mem:.2f} MB")
    print(f"Miss  : {miss_str}    Dup index : {dup_idx}")
    print()
    print("── head(5) ──"); print(df.head().to_string(max_cols=8)); print()
    print("── dtypes ──")
    print(abbrev_dtypes(df).to_string()); print()
    if not nas.empty:
        print("── Missing (>0) ──"); print(nas.head(10).to_string()); print()
    print(f"── Value scale: {vscale(df)} ──"); print()

    # crew / timepoint
    crews = sorted({c for s in sample_strings for m in [CREW_RE.search(str(s))] if m for c in [m.group(1).upper()]})
    tps   = sort_tp({t for s in sample_strings for m in [TP_RE.search(str(s))] if m for t in [m.group(1)]})
    print(f"Crew encoding  : {\'embedded_in_string\' if crews else \'none_per_crew\'}")
    print(f"  crews found  : {crews}")
    print(f"Timepoint enc  : {\'embedded_in_string\' if tps else \'none\'}")
    print(f"  TPs found    : {tps}")
    print()

    if aggregated:
        print("COVERAGE MATRIX: skipped — cohort-level / pre-aggregated dataset")
    else:
        cov = build_cov(sample_strings)
        print("── Coverage matrix (1=present, 0=absent) ──")
        print(cov.to_string()); print()

    n_feat = rows
    n_samp = len([s for s in sample_strings if CREW_RE.search(str(s))]) if sample_strings else 0

    RESULTS[key] = dict(
        osd=osd, assay=assay, granularity=granularity,
        per_crew=bool(crews), timepoints=tps,
        n_features=n_feat, n_samples=n_samp,
        aggregated=aggregated, notes=notes,
    )

print("Setup complete. Helpers loaded.")
'''

URLS = {
    1: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Combined-gene-level-KO-function-coverages_GLmetagenomics.tsv",
    2: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Combined-gene-level-taxonomy-coverages-CPM_GLmetagenomics.tsv",
    3: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    4: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
    5: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
    6: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
    7: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-656/download?source=datamanager&file=LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv",
    8: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=GLDS-561_long-readRNAseq_Direct_RNA_seq_Gene_Expression_Processed.xlsx",
    9: "https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv",
    10:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_snRNA-Seq_PBMC_Gene_Expression_snRNA-seq_Processed_Data.xlsx",
    11:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_snATAC-Seq_PBMC_Chromatin_Accessibility_snATAC-seq_Processed_Data.xlsx",
    12:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_scRNA-Seq_VDJ_Results.xlsx",
    13:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-566_SpatialTranscriptomics_Skin_Biopsy_Spatially_Resolved_Transcriptomics_Processed_Data.xlsx",
    14:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_metabolomics_Plasma_Metabolomics_Processed_Data.xlsx",
    15:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_proteomics_Plasma_Proteomics_Processed_Data.xlsx",
    16:"https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_proteomics_EVP_Proteomics_Processed_Data.xlsx",
}

DS_HEADERS = {
    1:  ("## 1. OSD-572 · Metagenomics — KEGG KO Function Coverage\n\n"
         "- **Reader:** `pd.read_csv(sep='\\t', index_col=0, low_memory=False)`\n"
         "- **Format:** Wide; KO IDs as rows, `CrewID_Timepoint_BodySite` samples as columns\n"
         "- **Expected:** includes FD2/FD3 in-flight timepoints; body sites ARM, EAR, GLU, NAC\n"),
    2:  ("## 2. OSD-572 · Metagenomics — Taxonomy CPM\n\n"
         "- **Reader:** `pd.read_csv(sep='\\t', index_col=0, low_memory=False)`\n"
         "- **Format:** First 7 cols = taxonomic ranks; remainder = sample columns\n"
         "- **Note:** `DtypeWarning` expected on col 0 — suppressed with `low_memory=False`\n"),
    3:  ("## 3. OSD-575 · Comprehensive Metabolic Panel (CMP)\n\n"
         "- **Reader:** `pd.read_csv(index_col=0).transpose()`\n"
         "- **Format after transpose:** rows=analyte rows (value/range_min/range_max), cols=samples\n"
         "- **Note:** 5% missingness expected from range reference columns\n"),
    4:  ("## 4. OSD-575 · Immune Cytokines — Eve Technologies Panel\n\n"
         "- **Reader:** `pd.read_csv(index_col=0).transpose()`\n"
         "- **Format after transpose:** rows=analytes (71 analytes × 2 cols: _concentration + _percent), cols=samples\n"
         "- **Units:** pg/mL (concentration columns); dimensionless (percent columns)\n"),
    5:  ("## 5. OSD-575 · Immune Cytokines — Alamar NULISAseq\n\n"
         "- **Reader:** `pd.read_csv(index_col=0).transpose()`\n"
         "- **Format after transpose:** rows=analytes (203 × 2), cols=samples\n"
         "- **Units:** NPQ (Normalized Proximity Quantity) — log2-like scale; NOT pg/mL\n"
         "- **Note:** C003 L-44 missing\n"),
    6:  ("## 6. OSD-575 · Cardiac Cytokines — Eve Technologies Panel\n\n"
         "- **Reader:** `pd.read_csv(index_col=0).transpose()`\n"
         "- **Format:** 9 cardiac analytes (CRP, AGP, etc.) × 2 cols each; mixed units (pg/mL and ng/mL)\n"),
    7:  ("## 7. OSD-656 · Urine Inflammation — Alamar NULISAseq\n\n"
         "- **Reader:** `pd.read_csv(index_col=0)` (no transpose — samples already in index)\n"
         "- **Format:** rows=samples (`C00X_urine_TP`), cols=analytes\n"
         "- **Note:** `Unnamed: 2` artifact column; C001 missing L-3 and R+1; max=inf (LLOQ artifact)\n"),
    8:  ("## 8. OSD-569 · Whole Blood RNA-seq — Long-Read Direct RNA\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5,6,9], header=[0,1], index_col=0)` then flatten MultiIndex\n"
         "- **Format:** 61852 transcripts × 38 cols; 16 per-sample count cols + DESeq2 + pipeline stats appended\n"
         "- **Note:** Only 4 timepoints (L-92, L-44, L-3, R+1); no return beyond R+1. Caution: 123 MB download.\n"),
    9:  ("## 9. OSD-569 · Complete Blood Count (CBC)\n\n"
         "- **Reader:** `pd.read_csv(index_col=0)`\n"
         "- **Format:** Long; rows=(analyte × subject × timepoint); SUBJECT_ID + TEST_DATE columns; includes clinical reference ranges\n"
         "- **Note:** 530 duplicate index entries expected (multiple subjects share same ANALYTE name)\n"),
    10: ("## 10. OSD-570 · PBMC snRNA-seq — FindMarkers Output\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5,6], index_col=0)`\n"
         "- **Format:** Seurat FindMarkers output: gene × cell-type rows, 6 stat columns (p_val, avg_log2FC, pct.1, pct.2, p_val_adj, …)\n"
         "- **⚠ PRE-AGGREGATED — cohort-level only.** No per-crew columns. Comparison: R+45 vs R+1\n"),
    11: ("## 11. OSD-570 · PBMC snATAC-seq — DARs Output\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5,6], index_col=0)`\n"
         "- **Format:** Peak × cell-type rows, 6 stat columns. Comparison: R+1 vs pre-flight\n"
         "- **⚠ PRE-AGGREGATED — cohort-level only.**\n"),
    12: ("## 12. OSD-570 · T/B Cell V(D)J Profiles\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2], index_col=0)`\n"
         "- **Format:** One row per clonotype; explicit `crewID` and `timepoint` columns\n"
         "- **Note:** 258K clonotype rows (~341 MB). Earliest timepoint is L-3 — NO L-92/L-44 baseline.\n"),
    13: ("## 13. OSD-574 · Skin Biopsy Spatial Transcriptomics (GeoMx WTA)\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5,6], index_col=0)`\n"
         "- **Format:** DESeq2 output; one row per gene; 6 stat columns\n"
         "- **⚠ PRE-AGGREGATED — cohort-level only.** Comparison: R+1 vs L-44\n"),
    14: ("## 14. OSD-571 · Plasma Metabolomics\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5], index_col=0)`\n"
         "- **Format:** limma output; one row per metabolite; 6 stat columns\n"
         "- **⚠ PRE-AGGREGATED — cohort-level only.**\n"),
    15: ("## 15. OSD-571 · Plasma Proteomics\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5], index_col=0)`\n"
         "- **Format:** limma output; one row per protein; 6 stat columns\n"
         "- **⚠ PRE-AGGREGATED — cohort-level only.**\n"),
    16: ("## 16. OSD-571 · EVP Proteomics (Mass Spec)\n\n"
         "- **Reader:** `pd.read_excel(skiprows=[0,1,2,3,4,5], index_col=0)`\n"
         "- **Format:** limma output; one row per protein; 6 stat columns\n"
         "- **⚠ PRE-AGGREGATED — cohort-level only.**\n"),
}

def ds_code(n, body):
    url = URLS[n]
    return f'''_URL = "{url}"
try:
{body}
except Exception as _e:
    print(f"FAILED: {{type(_e).__name__}}: {{_e}}")
    print(f"URL: {{_URL}}")
    RESULTS["DS{n:02d}"] = dict(error=f"{{type(_e).__name__}}: {{_e}}")
'''

# ── per-dataset code bodies ────────────────────────────────────────────────────
BODIES = {}

BODIES[1] = '''    df = pd.read_csv(fetch(_URL), sep='\\t', index_col=0, low_memory=False)
    # first col is KO_function description, rest are sample columns
    sample_cols = [c for c in df.columns if CREW_RE.search(str(c))]
    show(df, sample_cols, "DS01", "OSD-572", "Metagenomics KEGG KO",
         "sample-level", False,
         "Wide: KO IDs as rows, C00X_TP_Site samples as cols. Incl. FD2/FD3 in-flight.")
    print(f"Feature axis: KEGG Orthology function IDs (e.g., K00001)")
    print(f"  {len(df):,} KO functions  |  Dup index: {df.index.duplicated().sum()}")
    print(f"  Body sites: {sorted(set(c.split(\'_\')[2] for c in sample_cols if len(c.split(\'_\'))>=3))}")'''

BODIES[2] = '''    df = pd.read_csv(fetch(_URL), sep='\\t', index_col=0, low_memory=False)
    tax_cols  = ['domain','phylum','class','order','family','genus','species']
    tax_cols  = [c for c in tax_cols if c in df.columns]
    samp_cols = [c for c in df.columns if CREW_RE.search(str(c))]
    show(df, samp_cols, "DS02", "OSD-572", "Metagenomics Taxonomy CPM",
         "sample-level", False,
         "Wide: taxon rows, sample cols. First 7 cols are taxonomic ranks. CPM-normalized.")
    print(f"Feature axis: NCBI taxonomy IDs (numeric). {len(df):,} taxa.")
    print(f"  Taxonomic rank cols: {tax_cols}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[3] = '''    df = pd.read_csv(fetch(_URL), index_col=0).transpose()
    show(df, list(df.columns), "DS03", "OSD-575", "Comprehensive Metabolic Panel",
         "clinical-panel", False,
         "Post-transpose: rows=analyte rows (value/range_min/range_max), cols=samples. 5% missing.")
    print("Feature axis: CMP analyte name + _value_/_range_min_/_range_max_ suffix per row.")
    print(f"  Total rows: {len(df)}  (= {len([i for i in df.index if '_value_' in str(i)])} analytes × 3 rows)")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[4] = '''    df = pd.read_csv(fetch(_URL), index_col=0).transpose()
    conc_rows  = [i for i in df.index if 'concentration' in str(i)]
    pct_rows   = [i for i in df.index if '_percent' in str(i)]
    show(df, list(df.columns), "DS04", "OSD-575", "Immune Cytokines Eve",
         "sample-level", False,
         "71 analytes × 2 rows each (concentration pg/mL + percent). 0% missing. Primary cytokine signal.")
    print(f"Feature axis: Eve Technologies immune panel analytes.")
    print(f"  Total rows: {len(df)} = {len(conc_rows)} concentration rows + {len(pct_rows)} percent rows")
    print(f"  Value note: _concentration rows in pg/mL; _percent rows = normalized abundance")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[5] = '''    df = pd.read_csv(fetch(_URL), index_col=0).transpose()
    conc_rows = [i for i in df.index if 'concentration_npq' in str(i)]
    show(df, list(df.columns), "DS05", "OSD-575", "Immune Cytokines Alamar NULISAseq",
         "sample-level", False,
         "203 analytes × 2 rows (NPQ + percent). C003 L-44 missing. Units: NPQ not pg/mL.")
    print(f"Feature axis: Alamar NULISAseq immune panel analytes.")
    print(f"  Total rows: {len(df)} = {len(conc_rows)} _concentration_npq rows + {len(df)-len(conc_rows)} _percent rows")
    print(f"  NPQ: Normalized Proximity Quantity — log2-like scale. NOT directly comparable to Eve pg/mL.")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[6] = '''    df = pd.read_csv(fetch(_URL), index_col=0).transpose()
    show(df, list(df.columns), "DS06", "OSD-575", "Cardiac Cytokines Eve",
         "sample-level", False,
         "9 cardiac analytes (CRP, AGP, A2M, etc.) × 2 rows. Mixed units: pg/mL and ng/mL.")
    print(f"Feature axis: Eve Technologies cardiovascular panel analytes.")
    print(f"  Total rows: {len(df)} = {len(df)//2} analytes × 2 (concentration + percent)")
    print(f"  Unit note: CRP in pg/mL; A2-macroglobulin and AGP in ng/mL")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[7] = '''    df = pd.read_csv(fetch(_URL), index_col=0)
    # drop Unnamed artifact col
    unnamed_cols = [c for c in df.columns if str(c).startswith('Unnamed')]
    if unnamed_cols:
        print(f"  Dropping artifact cols: {unnamed_cols}")
        df = df.drop(columns=unnamed_cols)
    # replace inf
    n_inf = int(np.isinf(df.select_dtypes(include=\'number\')).sum().sum())
    if n_inf > 0:
        print(f"  WARNING: {n_inf} inf values detected — replacing with NaN")
        df = df.replace([np.inf, -np.inf], np.nan)
    show(df, list(df.index), "DS07", "OSD-656", "Urine Inflammation Alamar",
         "sample-level", False,
         "22 urine samples × 203 NPQ analytes. Inverted orientation vs serum. C001 missing L-3 and R+1.")
    print(f"Feature axis: Alamar NULISAseq analytes (same panel as DS05 but urine matrix).")
    print(f"  Unnamed artifact cols removed: {unnamed_cols}")
    print(f"  Orientation: samples in INDEX (not columns); analytes in columns")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[8] = '''    print("NOTE: Fetching 123 MB file — this may take 1-2 minutes.")
    buf = fetch(_URL)
    with warnings.catch_warnings(): warnings.simplefilter(\'ignore\')
    df  = pd.read_excel(buf, skiprows=[0,1,2,3,4,5,6,9], header=[0,1], index_col=0, engine=\'openpyxl\')
    # flatten MultiIndex columns
    orig_mi = df.columns.tolist()[:4]
    df.columns = [\' | \'.join(str(c) for c in col if str(c)!=\'nan\') for col in df.columns]
    print(f"MultiIndex examples (pre-flatten): {orig_mi}")
    samp_cols = [c for c in df.columns if CREW_RE.search(str(c))]
    show(df, samp_cols, "DS08", "OSD-569", "Whole Blood RNA-seq long-read",
         "sample-level", False,
         "61852 transcripts × 38 cols. 16 per-crew count cols; rest = DESeq2+pipeline stats. Only 4 TPs.")
    print(f"Feature axis: Transcript/gene IDs from long-read direct RNA sequencing.")
    print(f"  Per-crew sample columns ({len(samp_cols)}): {samp_cols[:4]}")
    stat_cols = [c for c in df.columns if not CREW_RE.search(str(c))]
    print(f"  Aggregated stat columns ({len(stat_cols)}): {stat_cols[:4]}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[9] = '''    df = pd.read_csv(fetch(_URL), index_col=0)
    # build synthetic sample string from SUBJECT_ID + TEST_DATE
    subj_col = next((c for c in df.columns if \'SUBJECT\' in c.upper()), None)
    date_col = next((c for c in df.columns if \'DATE\' in c.upper() or \'TIME\' in c.upper()), None)
    if subj_col and date_col:
        samp_strings = [f"{r[subj_col]}_{r[date_col]}" for _,r in df.iterrows()]
    else:
        samp_strings = []
    show(df, samp_strings, "DS09", "OSD-569", "Complete Blood Count",
         "clinical-panel", False,
         "Long format: 553 rows = 23 analytes × 4 crew × 7 TPs (some TPs vary). Includes clinical ranges.")
    print(f"Feature axis: Clinical CBC analytes (WBC, RBC, Hgb, Plt, etc.) — 23 unique analytes.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  SUBJECT_ID col: {subj_col}  |  TEST_DATE col: {date_col}")
    print(f"  Dup index (expected for long format): {df.index.duplicated().sum()}")
    print(f"  Clinical reference ranges included: RANGE_MIN and RANGE_MAX columns")'''

BODIES[10] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2,3,4,5,6], index_col=0, engine=\'openpyxl\')
    show(df, [], "DS10", "OSD-570", "PBMC snRNA-seq FindMarkers",
         "differential-stats-only", True,
         "Seurat FindMarkers output. No per-crew cols. Comparison: R+45 vs R+1.")
    print("PRE-AGGREGATED: columns are statistical outputs, NOT per-crew measurements.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Feature axis: gene symbol × cell-type combination")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[11] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2,3,4,5,6], index_col=0, engine=\'openpyxl\')
    show(df, [], "DS11", "OSD-570", "PBMC snATAC-seq DARs",
         "differential-stats-only", True,
         "Differentially accessible regions. No per-crew cols. Comparison: R+1 vs pre-flight.")
    print("PRE-AGGREGATED: chromatin peak × cell-type rows, statistical columns only.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[12] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2], index_col=0, engine=\'openpyxl\')
    crew_col = next((c for c in df.columns if \'crew\' in str(c).lower()), None)
    tp_col   = next((c for c in df.columns if \'time\' in str(c).lower()), None)
    print(f"  crewID col: {crew_col}  |  timepoint col: {tp_col}")
    if crew_col and tp_col:
        cov = build_cov_explicit(df, crew_col, tp_col)
        print("Coverage matrix:")
        print(cov.to_string())
    samp_strings = [f"{r[crew_col]}_{r[tp_col]}" for _,r in df.iterrows()] if crew_col and tp_col else []
    show(df, samp_strings, "DS12", "OSD-570", "VDJ T/B cell profiles",
         "clonotype-level", False,
         "258K clonotype rows. Explicit crewID+timepoint cols. Only L-3,R+1,R+45,R+82 — NO L-92/L-44 baseline.")
    print(f"Feature axis: one row per clonotype. Columns include chain, CDR3, V/D/J gene, count, frequency.")
    print(f"  All columns: {list(df.columns)}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[13] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2,3,4,5,6], index_col=0, engine=\'openpyxl\')
    show(df, [], "DS13", "OSD-574", "Skin Biopsy Spatial Transcriptomics",
         "differential-stats-only", True,
         "DESeq2 output from GeoMx WTA. No per-crew cols. Comparison: R+1 vs L-44.")
    print("PRE-AGGREGATED: gene-level DESeq2 results only. No spatial sample-level matrix available.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[14] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2,3,4,5], index_col=0, engine=\'openpyxl\')
    show(df, [], "DS14", "OSD-571", "Plasma Metabolomics",
         "differential-stats-only", True,
         "limma output. No per-sample/per-crew columns. Cohort-level only.")
    print("PRE-AGGREGATED: limma statistical output. Columns are test statistics, not measurements.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[15] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2,3,4,5], index_col=0, engine=\'openpyxl\')
    show(df, [], "DS15", "OSD-571", "Plasma Proteomics",
         "differential-stats-only", True,
         "limma output. No per-sample/per-crew columns. Cohort-level only.")
    print("PRE-AGGREGATED: limma statistical output.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

BODIES[16] = '''    df = pd.read_excel(fetch(_URL), skiprows=[0,1,2,3,4,5], index_col=0, engine=\'openpyxl\')
    show(df, [], "DS16", "OSD-571", "EVP Proteomics",
         "differential-stats-only", True,
         "limma output. Extracellular vesicle proteomics. Cohort-level only.")
    print("PRE-AGGREGATED: limma statistical output.")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Dup index: {df.index.duplicated().sum()}")'''

SYNTHESIS = '''import pandas as pd

rows = []
for key, r in sorted(RESULTS.items()):
    if "error" in r:
        rows.append({
            "OSD": r.get("osd","?"), "Assay": r.get("assay","?"),
            "Granularity": "—", "Per-crew?": "ERROR",
            "Timepoints": "—", "N features": "—", "Sample N": "—",
            "Joinable on (crew,tp)?": "—",
            "Recommended for individualized?": "NO (load error)",
            "Notes": r["error"]
        })
        continue
    tps = r.get("timepoints", [])
    per = "Yes" if r.get("per_crew") else "No"
    agg = r.get("aggregated", False)
    gran = r.get("granularity","?")

    # recommendation logic
    if agg:
        rec = "No — cohort-level/pre-aggregated"
        join = "No"
    elif not r.get("per_crew"):
        rec = "No — no per-crew data"
        join = "No"
    elif gran == "clonotype-level":
        rec = "Partial — no pre-flight baseline"
        join = "Partial"
    elif len(tps) < 4:
        rec = "Partial — limited timepoints"
        join = "Partial"
    else:
        rec = "Yes"
        join = "Yes"

    rows.append({
        "OSD":   r.get("osd","?"),
        "Assay": r.get("assay","?"),
        "Granularity": gran,
        "Per-crew?": per,
        "Timepoints": ", ".join(tps) if tps else "N/A (cohort)",
        "N features": f"{r.get(\'n_features\',\'?\'):,}" if isinstance(r.get(\'n_features\'),int) else r.get(\'n_features\',\'?\'),
        "Sample N": r.get("n_samples","?"),
        "Joinable on (crew,tp)?": join,
        "Recommended for individualized?": rec,
        "Notes": r.get("notes",""),
    })

syn = pd.DataFrame(rows)
print(syn.to_markdown(index=False))
'''

# ── assemble notebook ──────────────────────────────────────────────────────────
cells = [
    md("# SOMA / Inspiration4 Multi-Omics Data Inventory\n\n"
       "**Hackathon Track 2 — Individualized Risk Profile | Phase 1 Asset Audit**\n\n"
       "Characterizes 16 datasets across 7 OSDR accessions (OSD-569 → OSD-574).\n"
       "Per-dataset: shape, memory, missingness, crew/timepoint encoding, coverage matrix, "
       "feature axis, value scale.\n\n"
       "Pre-aggregated datasets (no per-crew columns) are flagged explicitly.\n\n"
       "**Reproducibility:** no local caching — refetches from OSDR on every run.\n"),
    code(SETUP),
]

for n in range(1, 17):
    cells.append(md(DS_HEADERS[n]))
    cells.append(code(ds_code(n, BODIES[n])))

cells.append(md("## Synthesis Table\n\nOne row per dataset. "
                "Built programmatically from `RESULTS` dict populated above.\n"))
cells.append(code(SYNTHESIS))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name":"Python 3","language":"python","name":"python3"},
        "language_info": {
            "codemirror_mode": {"name":"ipython","version":3},
            "file_extension": ".py","mimetype":"text/x-python",
            "name":"python","version":"3.10.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = ROOT / "01_data_inventory.ipynb"
with open(out, "w") as f:
    json.dump(nb, f, indent=1)
print(f"Written: {out}  ({out.stat().st_size//1024} KB)")
