#!/usr/bin/env python3
"""
inventory.py — SOMA Health Orbit | Phase 1: Schema Inspection & Completeness Audit
====================================================================================
Run ONLY after data/raw/ is populated by fetch_data.py or manual download.

For each data file found in data/raw/:
  - Prints path, size, shape, first 5 columns, first 3 rows (values truncated to 80 chars)
  - Detects orientation: rows=samples or rows=features
  - Extracts crew IDs (C001-C004) and timepoints from sample names
  - Builds completeness matrix: crew × timepoint × n_features_present
  - Saves full structured report to data/processed/inventory.json
  - Prints human-readable summary table to stdout

NO analysis. NO Z-scores. NO synthetic data. Inspection only.
"""

from __future__ import annotations
import json
import re
import sys
from pathlib import Path
import datetime

import numpy as np
import pandas as pd

# Import file manifest from fetch_data so the closeout summary
# can report which expected files are still missing.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from fetch_data import FILE_MANIFEST
except Exception:
    FILE_MANIFEST = []

ROOT     = Path(__file__).resolve().parents[1]
RAW_DIR  = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

CREW_PATTERN      = re.compile(r"C00[1-4]")
TIMEPOINT_PATTERN = re.compile(r"(L-\d+|R\+\d+|FD\d+)")
SAMPLE_PATTERN    = re.compile(
    r"^(C00[1-4])_(serum|whole-blood|blood|pbmc|plasma)_(L-\d+|R\+\d+|FD\d+)",
    re.IGNORECASE,
)

KNOWN_CREW      = ["C001", "C002", "C003", "C004"]
KNOWN_TIMEPOINTS = ["L-92", "L-44", "L-3", "FD1", "FD2", "FD3",
                    "R+1", "R+45", "R+82", "R+194"]

MAX_CELL_LEN = 80  # truncate printed cell values to this length


# ── file loading ───────────────────────────────────────────────────────────────
def load_file(path: Path) -> pd.DataFrame | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(path)
        elif suffix in (".tsv", ".txt"):
            return pd.read_csv(path, sep="\t")
        elif suffix in (".xlsx", ".xls"):
            return pd.read_excel(path, sheet_name=0)
        else:
            return None
    except Exception as exc:
        print(f"  [load-error] {path.name}: {exc}")
        return None


# ── sample-name parsing ────────────────────────────────────────────────────────
def parse_sample_name(name: str) -> dict | None:
    """
    Extract crew ID and timepoint from a sample name string.
    Handles both:
      C001_serum_L-3              → Eve/Alamar panels
      C001_whole-blood_R+1_cbc   → CBC
      C001_blood_L-44             → generic variants
    Returns None if neither crew nor timepoint can be parsed.
    """
    name = str(name).strip()
    crew_m = CREW_PATTERN.search(name)
    tp_m   = TIMEPOINT_PATTERN.search(name)
    if not crew_m and not tp_m:
        return None
    crew = crew_m.group(0) if crew_m else None
    tp   = tp_m.group(0)   if tp_m   else None

    # determine tissue type
    tissue = "unknown"
    for token in ["whole-blood", "serum", "plasma", "pbmc", "blood"]:
        if token in name.lower():
            tissue = token
            break

    return {"crew_id": crew, "timepoint": tp, "tissue": tissue, "raw": name}


def detect_sample_column(df: pd.DataFrame) -> str | None:
    """Return the column name that contains sample identifiers, or None."""
    candidates = ["Sample Name", "sample_name", "SampleName", "sample", "ID",
                  "Sample_Name", "sample name"]
    for c in candidates:
        if c in df.columns:
            return c
    # Fall back: first column if it looks like sample names
    first_col = df.columns[0]
    if df[first_col].dtype == object:
        sample_vals = df[first_col].dropna().astype(str)
        if sample_vals.apply(lambda x: bool(CREW_PATTERN.search(x))).mean() > 0.5:
            return first_col
    return None


# ── orientation detection ──────────────────────────────────────────────────────
def detect_orientation(df: pd.DataFrame) -> dict:
    """
    Determine whether rows represent samples or features (genes/analytes).

    Returns a dict with:
      orientation: "samples_as_rows" | "features_as_rows" | "ambiguous"
      sample_col:  name of the column containing sample IDs (if rows=samples)
      evidence:    human-readable explanation
    """
    sample_col = detect_sample_column(df)
    if sample_col is not None:
        sample_vals = df[sample_col].dropna().astype(str)
        has_crew = sample_vals.apply(lambda x: bool(CREW_PATTERN.search(x))).any()
        if has_crew:
            return {
                "orientation": "samples_as_rows",
                "sample_col":  sample_col,
                "evidence": (
                    f"Column '{sample_col}' contains crew ID patterns "
                    f"(e.g. {sample_vals.iloc[0]!r}). Each row is one sample."
                ),
            }

    # Check if column names contain crew IDs (features_as_rows orientation)
    col_with_crew = [c for c in df.columns if CREW_PATTERN.search(str(c))]
    if len(col_with_crew) > 2:
        return {
            "orientation": "features_as_rows",
            "sample_col":  None,
            "evidence": (
                f"{len(col_with_crew)} column names contain crew ID patterns "
                f"(e.g. {col_with_crew[0]!r}). Each column is one sample."
            ),
        }

    return {
        "orientation": "ambiguous",
        "sample_col":  None,
        "evidence": "Could not determine orientation from column or row content.",
    }


# ── feature detection ──────────────────────────────────────────────────────────
def detect_features(df: pd.DataFrame, orientation: dict) -> list[str]:
    """
    Return the list of measurement columns (analyte/gene columns, not metadata).
    """
    if orientation["orientation"] == "samples_as_rows":
        sample_col = orientation["sample_col"]
        meta_suffixes = ("_range_min", "_range_max", "_percent")
        all_data_cols = [
            c for c in df.columns
            if c != sample_col
            and not str(c).endswith(meta_suffixes)
            and df[c].dtype != object
        ]
        # For Eve/Alamar: take only _concentration_ columns as primary features
        conc_cols = [c for c in all_data_cols if "concentration" in str(c)]
        if conc_cols:
            return conc_cols
        # For CBC: take _value_ columns
        value_cols = [c for c in df.columns if "_value_" in str(c)]
        if value_cols:
            return value_cols
        return all_data_cols

    elif orientation["orientation"] == "features_as_rows":
        sample_col = orientation["sample_col"]
        return [c for c in df.columns if CREW_PATTERN.search(str(c))]

    return []


# ── completeness matrix ────────────────────────────────────────────────────────
def build_completeness_matrix(
    df: pd.DataFrame,
    orientation: dict,
    feature_cols: list[str],
) -> dict:
    """
    Build a crew × timepoint completeness matrix.
    Returns nested dict: crew → timepoint → {n_features, n_missing, pct_complete, present}
    """
    matrix: dict[str, dict] = {c: {} for c in KNOWN_CREW}
    crew_found: set[str]      = set()
    tp_found:   set[str]      = set()

    if orientation["orientation"] == "samples_as_rows":
        sc = orientation["sample_col"]
        for _, row in df.iterrows():
            parsed = parse_sample_name(str(row.get(sc, "")))
            if not parsed or not parsed["crew_id"] or not parsed["timepoint"]:
                continue
            crew = parsed["crew_id"]
            tp   = parsed["timepoint"]
            crew_found.add(crew)
            tp_found.add(tp)

            n_feat    = len(feature_cols)
            n_missing = int(row[feature_cols].isna().sum()) if feature_cols else 0
            n_present = n_feat - n_missing
            matrix.setdefault(crew, {})[tp] = {
                "n_features":   n_feat,
                "n_present":    n_present,
                "n_missing":    n_missing,
                "pct_complete": round(n_present / n_feat * 100, 1) if n_feat else None,
                "status":       "present" if n_present > 0 else "all_missing",
            }

    elif orientation["orientation"] == "features_as_rows":
        for col in feature_cols:
            parsed = parse_sample_name(col)
            if not parsed or not parsed["crew_id"] or not parsed["timepoint"]:
                continue
            crew = parsed["crew_id"]
            tp   = parsed["timepoint"]
            crew_found.add(crew)
            tp_found.add(tp)
            n_feat    = len(df)
            n_missing = int(df[col].isna().sum())
            n_present = n_feat - n_missing
            matrix.setdefault(crew, {})[tp] = {
                "n_features":   n_feat,
                "n_present":    n_present,
                "n_missing":    n_missing,
                "pct_complete": round(n_present / n_feat * 100, 1) if n_feat else None,
                "status":       "present" if n_present > 0 else "all_missing",
            }

    # Mark absent crew × timepoint combinations
    for crew in KNOWN_CREW:
        for tp in KNOWN_TIMEPOINTS:
            if tp not in matrix.get(crew, {}):
                matrix.setdefault(crew, {})[tp] = {"status": "absent"}

    return {
        "matrix":      matrix,
        "crew_found":  sorted(crew_found),
        "tp_found":    sorted(tp_found, key=lambda x: KNOWN_TIMEPOINTS.index(x)
                                                       if x in KNOWN_TIMEPOINTS else 99),
    }


# ── single-file inspection ─────────────────────────────────────────────────────
def inspect_file(path: Path) -> dict:
    """Full schema inspection of one file. Returns structured dict."""
    size = path.stat().st_size

    print(f"\n{'─'*70}")
    print(f"  FILE: {path.name}")
    print(f"  Size: {size:,} bytes ({size / 1_048_576:.2f} MB)")

    if path.suffix.lower() == ".zip":
        import zipfile
        try:
            with zipfile.ZipFile(path) as zf:
                members = zf.namelist()
            print(f"  Type: ZIP archive, {len(members)} member(s)")
            for m in members[:10]:
                print(f"    {m}")
            return {
                "path":     str(path),
                "name":     path.name,
                "size":     size,
                "format":   "zip",
                "members":  members,
                "inspected": False,
                "note":     "ZIP: extracted members listed above; not parsed for schema",
            }
        except Exception as e:
            return {"path": str(path), "name": path.name, "size": size,
                    "format": "zip", "error": str(e), "inspected": False}

    df = load_file(path)
    if df is None:
        return {"path": str(path), "name": path.name, "size": size,
                "format": path.suffix, "error": "load failed", "inspected": False}

    rows, cols = df.shape
    print(f"  Shape: {rows} rows × {cols} columns")

    first5_cols = list(df.columns[:5])
    print(f"  First 5 columns: {first5_cols}")

    print(f"  First 3 rows (values truncated to {MAX_CELL_LEN} chars):")
    for _, row in df.head(3).iterrows():
        vals = {str(k): (str(v)[:MAX_CELL_LEN] if not pd.isna(v) else "NA")
                for k, v in row.items()}
        print(f"    {vals}")

    orientation   = detect_orientation(df)
    feature_cols  = detect_features(df, orientation)
    completeness  = build_completeness_matrix(df, orientation, feature_cols)

    print(f"  Orientation: {orientation['orientation']}")
    print(f"  Evidence:    {orientation['evidence']}")
    print(f"  Features:    {len(feature_cols)} (e.g. {feature_cols[:3]})")
    print(f"  Crew found:  {completeness['crew_found']}")
    print(f"  Timepoints:  {completeness['tp_found']}")

    # completeness table
    print(f"\n  Completeness Matrix (crew × timepoint):")
    tp_list = completeness["tp_found"]
    header  = f"  {'Crew':6s}" + "".join(f"  {tp:6s}" for tp in tp_list)
    print(header)
    for crew in KNOWN_CREW:
        row_str = f"  {crew:6s}"
        for tp in tp_list:
            cell = completeness["matrix"].get(crew, {}).get(tp, {})
            if not cell or cell.get("status") == "absent":
                row_str += f"  {'—':6s}"
            elif cell.get("status") == "all_missing":
                row_str += f"  {'0%':6s}"
            else:
                pct = cell.get("pct_complete")
                row_str += f"  {f'{pct:.0f}%' if pct is not None else '?':6s}"
        print(row_str)

    return {
        "path":             str(path),
        "name":             path.name,
        "size_bytes":       size,
        "format":           path.suffix.lower(),
        "rows":             rows,
        "columns":          cols,
        "first_5_columns":  first5_cols,
        "first_3_rows":     [
            {str(k): (str(v)[:MAX_CELL_LEN] if not pd.isna(v) else None)
             for k, v in row.items()}
            for _, row in df.head(3).iterrows()
        ],
        "orientation":      orientation["orientation"],
        "orientation_evidence": orientation["evidence"],
        "sample_col":       orientation.get("sample_col"),
        "feature_count":    len(feature_cols),
        "feature_examples": feature_cols[:5],
        "crew_present":     completeness["crew_found"],
        "timepoints_present": completeness["tp_found"],
        "completeness_matrix": completeness["matrix"],
        "inspected":        True,
    }


# ── schema deviation notes ─────────────────────────────────────────────────────
def compile_schema_surprises(results: dict) -> list[str]:
    surprises = []

    for name, info in results.items():
        if not info.get("inspected"):
            continue

        orient = info.get("orientation")

        if orient == "samples_as_rows":
            surprises.append(
                f"[{name}] ORIENTATION REVERSED from Phase 0 assumption: "
                "rows=SAMPLES (not rows=features). Phase 2 parse logic must be rewritten."
            )

        tps = info.get("timepoints_present", [])
        fd_tps = [t for t in tps if t.startswith("FD")]
        if "OSD-575" in name and not fd_tps:
            surprises.append(
                f"[{name}] CONFIRMED: No in-flight (FD) timepoints in OSD-575 cytokines. "
                "Phase 0 pipeline referenced FD1/FD2/FD3 — these do not exist in this dataset."
            )
        if fd_tps:
            surprises.append(
                f"[{name}] UNEXPECTED: FD timepoints {fd_tps} present — investigate."
            )

        cols = info.get("first_5_columns", [])
        if any("concentration_picogram" in str(c) for c in cols):
            surprises.append(
                f"[{name}] COLUMN NAMING: analytes encoded as "
                "'{{name}}_concentration_picogram_per_milliliter', not simple 'IL-6'. "
                "Phase 2 will need a column-name normalizer."
            )
        if any("_value_" in str(c) and "_range_" not in str(c) for c in cols):
            surprises.append(
                f"[{name}] CBC SCHEMA: triplet columns per analyte: "
                "_value_, _range_min_, _range_max_. Phase 2 must select only _value_ columns."
            )

    return surprises


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 70)
    print("  SOMA Health Orbit — Phase 1: Schema Inventory")
    print(f"  Scanning: {RAW_DIR}")
    print("=" * 70)

    # find all data files (skip log and hidden files)
    extensions = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".zip"}
    data_files = sorted(
        p for p in RAW_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in extensions
        and not p.name.startswith("_")
        and not p.name.startswith(".")
    )

    if not data_files:
        print(f"\n[HALT] No data files found in {RAW_DIR}")
        print("       Run: python scripts/fetch_data.py")
        return 1

    print(f"\n  Found {len(data_files)} file(s) to inspect.")

    results: dict[str, dict] = {}
    for path in data_files:
        info = inspect_file(path)
        results[path.name] = info

    # ── schema surprise analysis ───────────────────────────────────────────────
    surprises = compile_schema_surprises(results)

    print(f"\n{'━'*70}")
    print("  SCHEMA SURPRISES vs Phase 0 Assumptions")
    print(f"{'━'*70}")
    if surprises:
        for s in surprises:
            print(f"  ⚠  {s}")
    else:
        print("  None detected.")

    # ── cross-dataset completeness summary ─────────────────────────────────────
    print(f"\n{'━'*70}")
    print("  CREW-LEVEL COMPLETENESS SUMMARY (across all datasets)")
    print(f"{'━'*70}")

    crew_summary: dict[str, dict] = {c: {"datasets": []} for c in KNOWN_CREW}
    for name, info in results.items():
        if not info.get("inspected"):
            continue
        for crew in info.get("crew_present", []):
            tps = [
                tp for tp in KNOWN_TIMEPOINTS
                if info["completeness_matrix"].get(crew, {}).get(tp, {}).get("status") == "present"
            ]
            crew_summary[crew]["datasets"].append({
                "file": name,
                "timepoints_with_data": tps,
                "n_features": info.get("feature_count"),
            })

    for crew in KNOWN_CREW:
        ds_list = crew_summary[crew]["datasets"]
        if not ds_list:
            print(f"  {crew}: NO DATA FOUND in any file")
            continue
        print(f"  {crew}:")
        for ds in ds_list:
            print(f"    {ds['file']}: {len(ds['timepoints_with_data'])} timepoints"
                  f" ({', '.join(ds['timepoints_with_data'])})"
                  f" | {ds['n_features']} features")

    # ── save inventory.json ────────────────────────────────────────────────────
    inventory = {
        "meta": {
            "generated":       datetime.datetime.now().isoformat(),
            "pipeline":        "SOMA Health Orbit — Phase 1",
            "script":          "inventory.py",
            "raw_dir":         str(RAW_DIR),
            "files_inspected": len(data_files),
        },
        "files":           results,
        "schema_surprises": surprises,
        "crew_summary":    crew_summary,
    }

    out_path = PROC_DIR / "inventory.json"
    with open(out_path, "w") as fh:
        json.dump(inventory, fh, indent=2, default=str)
    print(f"\n[output] {out_path}")

    # ── phase 1 closeout block ─────────────────────────────────────────────────
    print()
    print("╔" + "═" * 68 + "╗")
    print("║  PHASE 1 CLOSEOUT SUMMARY — paste this block back into chat       ║")
    print("╚" + "═" * 68 + "╝")
    print()

    osd_status: dict[str, dict] = {}
    for name, info in results.items():
        for osd in ["OSD-575", "OSD-569", "OSD-570"]:
            if osd in name or (osd == "OSD-569" and "CBC" in name) \
                    or (osd == "OSD-569" and "rnaseq" in name.lower()) \
                    or (osd == "OSD-570" and "VDJ" in name.upper()):
                osd_status.setdefault(osd, {"files": []})["files"].append(name)

    print("DOWNLOADED OSDs:")
    for osd in ["OSD-575", "OSD-569", "OSD-570"]:
        files = osd_status.get(osd, {}).get("files", [])
        print(f"  {osd}: {'✓ ' + str(len(files)) + ' file(s)' if files else '✗ none'}")

    print()
    print("FILES IN data/raw/:")
    for path in sorted(RAW_DIR.iterdir()):
        if path.is_file() and not path.name.startswith("_"):
            print(f"  {path.name}  ({path.stat().st_size:,} bytes)")

    print()
    print("COMPLETENESS PER CREW:")
    for crew in KNOWN_CREW:
        ds_list = crew_summary[crew]["datasets"]
        all_tps: set[str] = set()
        for ds in ds_list:
            all_tps.update(ds.get("timepoints_with_data", []))
        tps_sorted = [t for t in KNOWN_TIMEPOINTS if t in all_tps]
        has_3 = sum(1 for t in tps_sorted if t.startswith("L-"))
        has_r = sum(1 for t in tps_sorted if t.startswith("R+"))
        print(f"  {crew}: {len(tps_sorted)} total timepoints | "
              f"{has_3} L-minus (baseline) | {has_r} R-plus (return) | "
              f"{'suitable for n=1 Z-score analysis' if has_3 >= 2 else 'INSUFFICIENT BASELINE'}")

    print()
    print("SCHEMA SURPRISES vs PHASE 0 ASSUMPTIONS:")
    for s in (surprises or ["None"]):
        print(f"  {s}")

    print()
    missing = [e for e in FILE_MANIFEST if not (RAW_DIR / e["dest_name"]).exists()]
    print("MISSING/MANUAL FILES:")
    if missing:
        for e in missing:
            print(f"  ✗ {e['dest_name']}  ({e['osd']}, {e['assay']})")
    else:
        print("  None — all expected files present")

    return 0


if __name__ == "__main__":
    sys.exit(main())
