#!/usr/bin/env python3
"""
Probe all 16 datasets from OSDR, print key characterization info.
Large Excel files (>10 MB): fetch full file, load with openpyxl.
Output goes to _probe_out.json for use in notebook synthesis table.
"""
import io, re, json, sys, warnings
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

CREW_RE   = re.compile(r'(C00[1-4])', re.IGNORECASE)
TP_RE     = re.compile(r'(L-\d+|R\+\d+|FD\d+)')
TP_ORDER  = ['L-92','L-44','L-3','FD1','FD2','FD3','R+1','R+45','R+82','R+194']
CREW_ORDER= ['C001','C002','C003','C004']

def fetch(url, timeout=600):
    r = requests.get(url, allow_redirects=True, timeout=timeout,
                     headers={"User-Agent": "SOMA-probe/1.0"})
    r.raise_for_status()
    return io.BytesIO(r.content)

def parse_s(s):
    cm = CREW_RE.search(str(s)); tm = TP_RE.search(str(s))
    return (cm.group(1).upper() if cm else None, tm.group(1) if tm else None)

def sort_tp(tps):
    return sorted(tps, key=lambda x: TP_ORDER.index(x) if x in TP_ORDER else 99)

def cov_mat(strings):
    pairs = [parse_s(s) for s in strings]
    tps = sort_tp({t for _,t in pairs if t})
    mat = {crew: {tp: 0 for tp in tps} for crew in CREW_ORDER}
    for crew, tp in pairs:
        if crew in mat and tp in tps: mat[crew][tp] = 1
    return mat, tps

def vscale(df):
    nums = df.select_dtypes(include='number')
    if nums.empty: return "no numerics"
    flat = nums.values.ravel(); flat = flat[~np.isnan(flat)]
    if len(flat)==0: return "all NaN"
    mn,mx,med = float(np.min(flat)),float(np.max(flat)),float(np.median(flat))
    cs = nums.sum(); near_cpm = bool(((cs>5e5)&(cs<5e6)).mean()>0.6)
    log_like  = mn>=0 and mx<30 and med<15
    all_int   = len(flat)>0 and np.all(flat==flat.astype(int))
    if near_cpm: note="CPM-normalized"
    elif log_like: note="log/NPQ scale"
    elif all_int and mx>500: note="raw counts"
    else: note="linear continuous"
    return f"min={mn:.3g} med={med:.3g} max={mx:.3g} [{note}]"

def missingness_rate(df):
    total = df.shape[0]*df.shape[1]
    miss  = int(df.isna().sum().sum())
    return miss, total, f"{miss}/{total} ({100*miss/max(total,1):.1f}%)"

DATASETS = [
    dict(n=1, osd="OSD-572", assay="Metagenomics KEGG KO",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Combined-gene-level-KO-function-coverages_GLmetagenomics.tsv",
         load=lambda b: pd.read_csv(b, sep='\t', index_col=0, low_memory=False),
         sample_loc="columns", granularity="sample-level", aggregated=False),
    dict(n=2, osd="OSD-572", assay="Metagenomics Taxonomy CPM",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-572/download?source=datamanager&file=GLDS-564_GMetagenomics_Combined-gene-level-taxonomy-coverages-CPM_GLmetagenomics.tsv",
         load=lambda b: pd.read_csv(b, sep='\t', index_col=0, low_memory=False),
         sample_loc="columns", granularity="sample-level", aggregated=False),
    dict(n=3, osd="OSD-575", assay="Comprehensive Metabolic Panel",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
         load=lambda b: pd.read_csv(b, index_col=0).transpose(),
         sample_loc="columns", granularity="clinical-panel", aggregated=False),
    dict(n=4, osd="OSD-575", assay="Immune Cytokines Eve",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
         load=lambda b: pd.read_csv(b, index_col=0).transpose(),
         sample_loc="columns", granularity="sample-level", aggregated=False),
    dict(n=5, osd="OSD-575", assay="Immune Cytokines Alamar NULISAseq",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
         load=lambda b: pd.read_csv(b, index_col=0).transpose(),
         sample_loc="columns", granularity="sample-level", aggregated=False),
    dict(n=6, osd="OSD-575", assay="Cardiac Cytokines Eve",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
         load=lambda b: pd.read_csv(b, index_col=0).transpose(),
         sample_loc="columns", granularity="sample-level", aggregated=False),
    dict(n=7, osd="OSD-656", assay="Urine Inflammation Alamar",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-656/download?source=datamanager&file=LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv",
         load=lambda b: pd.read_csv(b, index_col=0),
         sample_loc="index", granularity="sample-level", aggregated=False),
    dict(n=8, osd="OSD-569", assay="Whole Blood RNA-seq long-read",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=GLDS-561_long-readRNAseq_Direct_RNA_seq_Gene_Expression_Processed.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5,6,9], header=[0,1], index_col=0, engine='openpyxl'),
         sample_loc="columns_multiindex", granularity="sample-level", aggregated=False),
    dict(n=9, osd="OSD-569", assay="Complete Blood Count",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-569/download?source=datamanager&file=LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv",
         load=lambda b: pd.read_csv(b, index_col=0),
         sample_loc="dedicated_columns_SUBJECT_ID_TEST_DATE", granularity="clinical-panel", aggregated=False),
    dict(n=10, osd="OSD-570", assay="PBMC snRNA-seq",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_snRNA-Seq_PBMC_Gene_Expression_snRNA-seq_Processed_Data.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5,6], index_col=0, engine='openpyxl'),
         sample_loc="none_per_crew", granularity="differential-stats-only", aggregated=True),
    dict(n=11, osd="OSD-570", assay="PBMC snATAC-seq",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_snATAC-Seq_PBMC_Chromatin_Accessibility_snATAC-seq_Processed_Data.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5,6], index_col=0, engine='openpyxl'),
         sample_loc="none_per_crew", granularity="differential-stats-only", aggregated=True),
    dict(n=12, osd="OSD-570", assay="T/B cell VDJ profiles",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-562_scRNA-Seq_VDJ_Results.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2], index_col=0, engine='openpyxl'),
         sample_loc="dedicated_column_crewID", granularity="clonotype-level", aggregated=False),
    dict(n=13, osd="OSD-574", assay="Skin Biopsy Spatial Transcriptomics",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-570/download?source=datamanager&file=GLDS-566_SpatialTranscriptomics_Skin_Biopsy_Spatially_Resolved_Transcriptomics_Processed_Data.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5,6], index_col=0, engine='openpyxl'),
         sample_loc="none_per_crew", granularity="differential-stats-only", aggregated=True),
    dict(n=14, osd="OSD-571", assay="Plasma Metabolomics",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_metabolomics_Plasma_Metabolomics_Processed_Data.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5], index_col=0, engine='openpyxl'),
         sample_loc="none_per_crew", granularity="differential-stats-only", aggregated=True),
    dict(n=15, osd="OSD-571", assay="Plasma Proteomics",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_proteomics_Plasma_Proteomics_Processed_Data.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5], index_col=0, engine='openpyxl'),
         sample_loc="none_per_crew", granularity="differential-stats-only", aggregated=True),
    dict(n=16, osd="OSD-571", assay="EVP Proteomics",
         url="https://osdr.nasa.gov/geode-py/ws/studies/OSD-571/download?source=datamanager&file=GLDS-563_proteomics_EVP_Proteomics_Processed_Data.xlsx",
         load=lambda b: pd.read_excel(b, skiprows=[0,1,2,3,4,5], index_col=0, engine='openpyxl'),
         sample_loc="none_per_crew", granularity="differential-stats-only", aggregated=True),
]

results = []

for ds in DATASETS:
    n = ds['n']
    print(f"\n{'='*60}")
    print(f"DS{n:02d}: {ds['osd']} — {ds['assay']}")
    print(f"{'='*60}")
    rec = dict(n=n, osd=ds['osd'], assay=ds['assay'],
               granularity=ds['granularity'], aggregated=ds['aggregated'],
               url=ds['url'])
    try:
        buf = fetch(ds['url'])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            df = ds['load'](buf)

        # flatten MultiIndex columns if needed
        if isinstance(df.columns, pd.MultiIndex):
            orig_cols = df.columns.tolist()
            df.columns = [' | '.join(str(c) for c in col if str(c)!='nan') for col in df.columns]
            rec['multiindex_note'] = f"Flattened MultiIndex: {orig_cols[:4]}"

        rows, cols = df.shape
        mem = df.memory_usage(deep=True).sum() / 1e6
        miss_n, miss_t, miss_str = missingness_rate(df)
        print(f"Shape: {df.shape}  Memory: {mem:.2f} MB")
        print(f"Missingness: {miss_str}")
        print(f"Index[:5]: {list(df.index[:5])}")
        print(f"Columns[:5]: {list(df.columns[:5])}")
        print(f"Dtypes: {dict(df.dtypes.value_counts())}")
        print(f"Value scale: {vscale(df)}")
        print(f"Dup index: {df.index.duplicated().sum()}")

        # crew / timepoint detection
        loc = ds['sample_loc']
        if loc == "columns":
            sample_strings = list(df.columns)
        elif loc == "index":
            sample_strings = list(df.index)
        elif loc == "dedicated_columns_SUBJECT_ID_TEST_DATE":
            sid_col = next((c for c in df.columns if 'SUBJECT' in str(c).upper() or c=='SUBJECT_ID'), None)
            tdt_col = next((c for c in df.columns if 'DATE' in str(c).upper() or 'TIME' in str(c).upper()), None)
            if sid_col and tdt_col:
                sample_strings = [f"{r[sid_col]}_{r[tdt_col]}" for _, r in df.iterrows()]
            else:
                sample_strings = list(df.columns)
        elif loc == "dedicated_column_crewID":
            crew_col = next((c for c in df.columns if 'crew' in str(c).lower()), None)
            tp_col   = next((c for c in df.columns if 'time' in str(c).lower()), None)
            if crew_col and tp_col:
                sample_strings = [f"{r[crew_col]}_{r[tp_col]}" for _, r in df.iterrows()]
            else:
                sample_strings = list(df.columns)
        elif loc == "columns_multiindex":
            sample_strings = [str(c) for c in df.columns]
        else:
            sample_strings = []

        mat, tps = cov_mat(sample_strings)
        crews_found = sorted({c for s in sample_strings for m in [CREW_RE.search(str(s))] if m for c in [m.group(1).upper()]})
        tps_found   = sort_tp({t for s in sample_strings for m in [TP_RE.search(str(s))] if m for t in [m.group(1)]})

        print(f"Crew found: {crews_found}")
        print(f"Timepoints: {tps_found}")
        print(f"Coverage matrix:")
        for crew in CREW_ORDER:
            row_str = f"  {crew}: " + "  ".join(f"{tp}={'1' if mat[crew].get(tp,0) else '0'}" for tp in tps_found)
            print(row_str)

        # feature count
        if loc == "columns" or loc == "columns_multiindex":
            n_samples = len([c for c in df.columns if CREW_RE.search(str(c))])
            n_features = rows
        elif loc == "none_per_crew":
            n_samples = 0
            n_features = rows
        elif "dedicated" in loc:
            n_samples = len(df[sid_col].unique()) if sid_col in df.columns else 0
            n_features = len(df.index.unique()) if 'ANALYTE' in str(df.index.name or '') else rows
        else:
            n_samples = len([s for s in sample_strings if CREW_RE.search(s)])
            n_features = rows

        rec.update(dict(
            shape=(rows, cols), mem_mb=round(mem,2),
            miss=miss_str, n_features=n_features,
            n_samples=n_samples,
            crews=crews_found, timepoints=tps_found,
            coverage=mat, value_scale=vscale(df),
            dup_index=int(df.index.duplicated().sum()),
            col_examples=list(df.columns[:5]),
            idx_examples=list(df.index[:5]),
            per_crew=bool(len(crews_found)>0),
            error=None,
        ))

    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        rec['error'] = f"{type(e).__name__}: {e}"
        rec['per_crew'] = None

    results.append(rec)
    sys.stdout.flush()

# write JSON
with open('/Users/lucyvanpelt/health_orbit/notebooks/_probe_out.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)
print("\n\n=== DONE === written to notebooks/_probe_out.json")
