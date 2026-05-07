"""
Pure I/O loaders — no transformation, no filtering, no parsing.
Each function reads its source file and returns the raw DataFrame.
"""
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_RAW = Path(__file__).parent.parent.parent / "data" / "raw"


def load_cbc() -> pd.DataFrame:
    """
    OSD-569 CBC (DS09) — long format.
    Index = ANALYTE, columns: VALUE, RANGE_MIN, RANGE_MAX, UNITS, TEST_TYPE,
                               SUBJECT_ID, SEX, TEST_DATE
    """
    path = _RAW / "OSD-569_CBC_SUBMITTED.csv"
    df = pd.read_csv(path, index_col=0)
    log.info("CBC loaded: %d rows from %s", len(df), path.name)
    return df


def load_cytokines() -> pd.DataFrame:
    """
    OSD-575 Eve immune cytokine panel (DS04) — long format.
    Columns: Analyte, Concentration, Timepoint, ID, Unit, Timepoint2, Type, Percent
    71 analytes × 4 crew × 7 timepoints = 1988 rows.
    """
    path = _RAW / "OSD-575_eve_immune_SUBMITTED.csv"
    df = pd.read_csv(path)
    log.info("Cytokines loaded: %d rows from %s", len(df), path.name)
    return df


def load_metagenomics_ko() -> pd.DataFrame:
    """
    OSD-572 metagenomics KEGG KO function coverage (DS01) — wide format.
    Index = KO_ID (e.g. K00001).
    Columns: KO_function (description), then sample IDs (C00X_TP_SITE).
    10537 KO functions × 328 columns (1 description + 327 samples).
    """
    path = _RAW / "OSD-572_metagenomics_KEGG_KO.tsv"
    df = pd.read_csv(path, sep="\t", index_col=0, low_memory=False)
    log.info("Metagenomics KO loaded: %d KOs × %d cols from %s",
             len(df), len(df.columns), path.name)
    return df
