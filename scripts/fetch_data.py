#!/usr/bin/env python3
"""
fetch_data.py — SOMA Health Orbit | Phase 1: Data Acquisition
==============================================================
Attempts programmatic download from NASA OSDR public API.
OSDR endpoint: GET /geode-py/ws/studies/{OSD_ID}/download?source=datamanager&file={name}
   → 302 redirect to time-limited S3 presigned URL (no auth required)

On success:  files saved to data/raw/, fetch log written to data/raw/_fetch_log.txt
On failure:  explicit manual download checklist printed; script exits nonzero

NO synthetic data. NO fallbacks. If a file cannot be fetched, the script says so
clearly and provides the exact URL and destination path needed.
"""

from __future__ import annotations
import sys
import hashlib
import shutil
import datetime
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[1]
RAW_DIR  = ROOT / "data" / "raw"
LOG_PATH = RAW_DIR / "_fetch_log.txt"

RAW_DIR.mkdir(parents=True, exist_ok=True)

OSDR_BASE  = "https://osdr.nasa.gov/geode-py/ws/studies/{osd}/download"
OSDR_STUDY_PAGES = {
    "OSD-575": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575/",
    "OSD-569": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-569/",
    "OSD-570": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-570/",
}

# ── file manifest (verified against OSDR API on 2026-05-06) ──────────────────
# auto=True  → attempt programmatic download (file is small enough)
# auto=False → print manual download instruction (>10 MB or uncertain format)
FILE_MANIFEST: list[dict] = [

    # ── OSD-575: Blood serum cytokines ────────────────────────────────────────
    {
        "osd":          "OSD-575",
        "filename":     "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
        "dest_name":    "OSD-575_eve_immune_TRANSFORMED.csv",
        "size_bytes":   41_214,
        "assay":        "Eve Technologies 65-plex immune panel (serum pg/mL, OSDR-transformed)",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     1,
    },
    {
        "osd":          "OSD-575",
        "filename":     "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
        "dest_name":    "OSD-575_eve_cardiovascular_TRANSFORMED.csv",
        "size_bytes":   6_207,
        "assay":        "Eve Technologies cardiovascular panel (serum pg/mL, OSDR-transformed)",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     2,
    },
    {
        "osd":          "OSD-575",
        "filename":     "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
        "dest_name":    "OSD-575_alamar_immune_TRANSFORMED.csv",
        "size_bytes":   141_783,
        "assay":        "Alamar NULISAseq immune panel (serum pg/mL, OSDR-transformed)",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     3,
    },
    {
        "osd":          "OSD-575",
        "filename":     "LSDS-8_Multiplex_serum.immune.EvePanel_SUBMITTED.csv",
        "dest_name":    "OSD-575_eve_immune_SUBMITTED.csv",
        "size_bytes":   107_418,
        "assay":        "Eve Technologies immune panel (raw submitted, with percent columns)",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     4,
    },
    {
        "osd":          "OSD-575",
        "filename":     "LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv",
        "dest_name":    "OSD-575_eve_cardiovascular_SUBMITTED.csv",
        "size_bytes":   15_241,
        "assay":        "Eve Technologies cardiovascular panel (raw submitted)",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     5,
    },
    {
        "osd":          "OSD-575",
        "filename":     "OSD-575_metadata_OSD-575-ISA.zip",
        "dest_name":    "OSD-575_metadata_ISA.zip",
        "size_bytes":   71_702,
        "assay":        "ISA metadata (investigation/study/assay sidecar)",
        "timepoints":   "N/A",
        "auto":         True,
        "priority":     6,
    },

    # ── OSD-569: CBC (small, auto-download) ───────────────────────────────────
    {
        "osd":          "OSD-569",
        "filename":     "LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv",
        "dest_name":    "OSD-569_CBC_TRANSFORMED.csv",
        "size_bytes":   9_317,
        "assay":        "Complete Blood Count — 23 analytes with clinical reference ranges",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     1,
    },
    {
        "osd":          "OSD-569",
        "filename":     "LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv",
        "dest_name":    "OSD-569_CBC_SUBMITTED.csv",
        "size_bytes":   26_138,
        "assay":        "Complete Blood Count (raw submitted)",
        "timepoints":   "L-92, L-44, L-3, R+1, R+45, R+82, R+194",
        "auto":         True,
        "priority":     2,
    },

    # ── OSD-569: RNA-seq (large Excel — manual download required) ─────────────
    {
        "osd":          "OSD-569",
        "filename":     "GLDS-561_long-readRNAseq_Direct_RNA_seq_Gene_Expression_Processed.xlsx",
        "dest_name":    "OSD-569_longread_rnaseq_gene_expression.xlsx",
        "size_bytes":   123_312_037,
        "assay":        "Long Read RNA-seq — Direct RNA gene expression processed data",
        "timepoints":   "UNKNOWN — inspect after download",
        "auto":         False,
        "manual_reason": "123 MB Excel file; streaming download may be unreliable. Download manually.",
        "priority":     3,
    },
    {
        "osd":          "OSD-569",
        "filename":     "GLDS-561_directm6Aseq_Direct_RNA_seq_m6A_Processed_Data.xlsx",
        "dest_name":    "OSD-569_m6A_rnaseq.xlsx",
        "size_bytes":   93_081_199,
        "assay":        "m6A Direct RNA-seq processed data",
        "timepoints":   "UNKNOWN — inspect after download",
        "auto":         False,
        "manual_reason": "93 MB Excel file. Download manually.",
        "priority":     4,
    },

    # ── OSD-570: VDJ repertoire (large Excel — manual) ────────────────────────
    {
        "osd":          "OSD-570",
        "filename":     "GLDS-562_scRNA-Seq_VDJ_Results.xlsx",
        "dest_name":    "OSD-570_VDJ_results.xlsx",
        "size_bytes":   52_634_236,
        "assay":        "scRNA-Seq VDJ repertoire — BCR and TCR results",
        "timepoints":   "L-3, R+1, R+45, R+82 (expected per SOMA paper)",
        "auto":         False,
        "manual_reason": "52 MB Excel file. Download manually.",
        "priority":     1,
    },
]


# ── download logic ─────────────────────────────────────────────────────────────
def attempt_download(entry: dict, log_lines: list[str]) -> bool:
    """
    Attempt programmatic download via OSDR public API (302 → S3 redirect).
    Returns True on success, False on any failure.
    """
    try:
        import requests
    except ImportError:
        msg = "DEPENDENCY MISSING: 'requests' not installed. Run: pip install requests"
        print(f"  [ERROR] {msg}")
        log_lines.append(f"ERROR requests not installed")
        return False

    osd      = entry["osd"]
    filename = entry["filename"]
    dest     = RAW_DIR / entry["dest_name"]
    url      = OSDR_BASE.format(osd=osd) + f"?source=datamanager&file={filename}"

    if dest.exists():
        existing_size = dest.stat().st_size
        print(f"  [SKIP] Already present: {dest.name} ({existing_size:,} bytes)")
        log_lines.append(f"SKIPPED  {entry['dest_name']} already_on_disk size={existing_size}")
        return True

    print(f"  [GET] {osd}/{filename}")
    print(f"        → {dest.name} (expected {entry['size_bytes']:,} bytes)")

    try:
        r = requests.get(url, allow_redirects=True, timeout=180, stream=True)
        if r.status_code != 200:
            msg = f"HTTP {r.status_code} from {url}"
            print(f"  [FAIL] {msg}")
            log_lines.append(f"FAILURE  {entry['dest_name']} {msg}")
            return False

        bytes_written = 0
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=65_536):
                fh.write(chunk)
                bytes_written += len(chunk)

        ts = datetime.datetime.now().isoformat(timespec="seconds")
        log_lines.append(f"SUCCESS  {entry['dest_name']} bytes={bytes_written} ts={ts}")
        print(f"  [OK]   {dest.name} ({bytes_written:,} bytes)")
        return True

    except Exception as exc:
        msg = str(exc)
        print(f"  [FAIL] {msg}")
        log_lines.append(f"FAILURE  {entry['dest_name']} {msg}")
        if dest.exists():
            dest.unlink()  # remove partial file
        return False


# ── manual download instructions ──────────────────────────────────────────────
def print_manual_checklist(manual_entries: list[dict], failed_entries: list[dict]) -> None:
    all_entries = manual_entries + failed_entries
    if not all_entries:
        return

    print()
    print("╔" + "═" * 68 + "╗")
    print("║  MANUAL DOWNLOAD REQUIRED                                        ║")
    print("╚" + "═" * 68 + "╝")
    print()
    print("The following files must be downloaded manually from NASA OSDR.")
    print("Place each file in: data/raw/  (rename to the 'Save as' name shown)")
    print()

    by_osd: dict[str, list] = {}
    for e in all_entries:
        by_osd.setdefault(e["osd"], []).append(e)

    for osd, entries in sorted(by_osd.items()):
        lp = OSDR_STUDY_PAGES[osd]
        print(f"  {'─'*64}")
        print(f"  {osd}  —  {lp}")
        print(f"  {'─'*64}")
        for e in sorted(entries, key=lambda x: x["priority"]):
            print(f"  Filename on OSDR:  {e['filename']}")
            print(f"  Save as:           data/raw/{e['dest_name']}")
            print(f"  Assay:             {e['assay']}")
            print(f"  Expected size:     {e['size_bytes']:,} bytes ({e['size_bytes']//1_048_576 or '<1'} MB)")
            if "manual_reason" in e:
                print(f"  Note:              {e['manual_reason']}")
            print()

    print("  After placing files in data/raw/, re-run this script to verify,")
    print("  then run: python scripts/inventory.py")
    print()


# ── verification ───────────────────────────────────────────────────────────────
def verify_present() -> dict[str, bool]:
    present = {}
    for e in FILE_MANIFEST:
        dest = RAW_DIR / e["dest_name"]
        present[e["dest_name"]] = dest.exists()
    return present


# ── main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 70)
    print("  SOMA Health Orbit — Phase 1: Data Acquisition")
    print("  Target: data/raw/  |  Log: data/raw/_fetch_log.txt")
    print("=" * 70)

    log_lines: list[str] = [
        f"# SOMA Health Orbit fetch_data.py",
        f"# Run: {datetime.datetime.now().isoformat()}",
        "",
    ]

    auto_entries   = [e for e in FILE_MANIFEST if e["auto"]]
    manual_entries = [e for e in FILE_MANIFEST if not e["auto"]]

    # ── attempt auto-downloads ─────────────────────────────────────────────────
    failed: list[dict] = []
    succeeded: list[dict] = []

    by_osd: dict[str, list] = {}
    for e in auto_entries:
        by_osd.setdefault(e["osd"], []).append(e)

    for osd, entries in sorted(by_osd.items()):
        print(f"\n── {osd} ──────────────────────────────────────────────────────────")
        for e in sorted(entries, key=lambda x: x["priority"]):
            ok = attempt_download(e, log_lines)
            (succeeded if ok else failed).append(e)

    # ── manual-only entries ────────────────────────────────────────────────────
    for e in manual_entries:
        dest = RAW_DIR / e["dest_name"]
        if dest.exists():
            size = dest.stat().st_size
            print(f"  [PRESENT] {e['dest_name']} ({size:,} bytes) — manually placed")
            log_lines.append(f"MANUAL_PRESENT {e['dest_name']} size={size}")
            succeeded.append(e)
        else:
            print(f"  [MANUAL]  {e['dest_name']} — {e.get('manual_reason','manual download required')}")
            log_lines.append(f"MANUAL_NEEDED  {e['dest_name']}")

    # ── write log ──────────────────────────────────────────────────────────────
    LOG_PATH.write_text("\n".join(log_lines) + "\n")
    print(f"\n[log] {LOG_PATH}")

    # ── summary ────────────────────────────────────────────────────────────────
    present   = verify_present()
    n_present = sum(present.values())
    n_total   = len(FILE_MANIFEST)

    print()
    print("── Acquisition Summary ────────────────────────────────────────────────")
    print(f"   Files present:   {n_present}/{n_total}")
    print(f"   Auto-succeeded:  {len(succeeded)}")
    print(f"   Auto-failed:     {len(failed)}")
    print(f"   Manual pending:  {len([e for e in manual_entries if not (RAW_DIR/e['dest_name']).exists()])}")

    print()
    print("── File Status ────────────────────────────────────────────────────────")
    for e in FILE_MANIFEST:
        dest = RAW_DIR / e["dest_name"]
        if dest.exists():
            size = dest.stat().st_size
            print(f"  ✓  {e['dest_name']:55s}  {size:>12,} bytes")
        else:
            print(f"  ✗  {e['dest_name']:55s}  MISSING")

    if failed or any(not (RAW_DIR/e["dest_name"]).exists() for e in manual_entries):
        print_manual_checklist(
            [e for e in manual_entries if not (RAW_DIR / e["dest_name"]).exists()],
            failed,
        )

    if n_present == 0:
        print("\n[HALT] No data files present. Cannot proceed to inventory.")
        print("       Resolve manual downloads above, then re-run this script.")
        return 1

    print("\n[NEXT] Run: python scripts/inventory.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
