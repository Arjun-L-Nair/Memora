"""
ml/data_loader.py

Downloads, caches, and preprocesses the three real, published datasets
named in the implementation plan (Component 1):

  1. ASD Screening Dataset (UCI ML Repository, Thabtah 2017/2018)
     https://archive.ics.uci.edu/dataset/426/autism+screening+adult
     Used for: learner profiling / initial difficulty calibration
     features (sensory_sensitivity_score proxy, attention proxy).

  2. Student Performance Dataset (UCI ML Repository, Cortez & Silva 2008)
     https://archive.ics.uci.edu/dataset/320/student+performance
     Used for: engagement/performance forecasting features (study
     time, absences, prior grades -> analogous to session behavioral
     features here).

  3. OULAD - Open University Learning Analytics Dataset
     (Kuzilek, Hlosta & Zdrahal, 2017), https://analyse.kmi.open.ac.uk/open_dataset
     Used for: temporal engagement patterns / dropout modeling
     (early_warning.py builds on the patterns learned here).

Real-world format quirks handled here (learned from an actual run
against the live UCI/OULAD servers, not assumed):
    - The UCI ASD Screening zip contains a `.arff` file (Attribute-
      Relation File Format), not a CSV, alongside an unrelated .docx
      description file. This module downloads the zip, picks out the
      .arff member specifically, and parses ARFF with a small
      dependency-free parser (see _parse_arff below) rather than
      pulling in scipy solely for this.
    - The UCI Student Performance zip contains a NESTED zip
      (`student.zip`) plus a stray `.student.zip_old` artifact from
      UCI's own hosting. This module unwraps the outer zip, finds the
      inner zip, and reads `student-por.csv` out of that.
    - OULAD's download endpoint returns HTTP 403 for requests with no
      User-Agent header (the default one urllib/pandas sends is
      blocked) — this module downloads via `requests` with a normal
      browser-like User-Agent, then extracts `studentVle.csv` from the
      returned zip.

Network reality check:
    Every download function fails soft: on any network/parsing error
    it logs a clear warning and returns None, and callers (model.py)
    fall back to the deterministic synthetic dataset (ml/dataset.py)
    so the app always has a working model. Run
    `python -m app.ml.data_loader --refresh` on a machine with normal
    internet access to populate the real cache once; after that,
    cached CSVs under app/ml/data_cache/ are reused on every
    subsequent startup with no network calls at all.

Preprocessing:
    Each loader returns a pandas DataFrame already aligned to this
    app's internal feature schema (see ml/features.py FEATURE_ORDER)
    where a reasonable mapping exists; columns with no analogue are
    left as-is. This keeps the transformation deterministic and
    reproducible across runs (no randomness in imputation).
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger("memora.ml.data_loader")

_CACHE_DIR = Path(__file__).parent / "data_cache"

_ASD_SCREENING_URL = "https://archive.ics.uci.edu/static/public/426/autism+screening+adult.zip"
_STUDENT_PERFORMANCE_URL = "https://archive.ics.uci.edu/static/public/320/student+performance.zip"
_OULAD_URL = "https://analyse.kmi.open.ac.uk/open_dataset/download"

_ASD_CACHE = _CACHE_DIR / "asd_screening.csv"
_STUDENT_PERF_CACHE = _CACHE_DIR / "student_performance.csv"
_OULAD_CACHE = _CACHE_DIR / "oulad_studentVle.csv"

# A normal browser User-Agent. Some academic hosts (OULAD in
# particular) 403 the default urllib/requests User-Agent string.
_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _fetch_bytes(url: str) -> bytes:
    """Download raw bytes from a URL with a browser-like User-Agent. Raises on failure."""
    import requests

    response = requests.get(url, headers=_HTTP_HEADERS, timeout=60)
    response.raise_for_status()
    return response.content


def _parse_arff(text: str) -> pd.DataFrame:
    """
    Minimal ARFF (Attribute-Relation File Format) parser — enough for
    the UCI ASD Screening file's simple attribute types (nominal,
    integer, real, string), without pulling in scipy as a dependency
    for a single file.

    ARFF structure:
        @relation name
        @attribute colname {nominal,values} | integer | real | string
        ...
        @data
        value1,value2,...
        ...
    """
    columns: list[str] = []
    rows: list[list[str]] = []
    in_data_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue

        lowered = line.lower()
        if lowered.startswith("@attribute"):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                col_name = parts[1].strip("'\"")
                columns.append(col_name)
        elif lowered.startswith("@data"):
            in_data_section = True
        elif in_data_section:
            rows.append(next(csv_module_reader([line])))

    return pd.DataFrame(rows, columns=columns)


def csv_module_reader(lines: list[str]):
    """Thin wrapper around csv.reader so ARFF's comma-separated,
    possibly-quoted data rows are split correctly (values can contain
    quoted strings with embedded commas, e.g. relation/country names)."""
    import csv

    return csv.reader(lines)


def _extract_single_member(zip_bytes: bytes, *, suffix: str | None = None, exact_name: str | None = None) -> bytes:
    """
    Extract exactly one member from a zip's bytes, selecting either by
    filename suffix (e.g. ".arff") or an exact member name (e.g.
    "student-por.csv"). Raises ValueError if no match is found.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if exact_name is not None:
            matches = [n for n in names if n.endswith(exact_name)]
        else:
            matches = [n for n in names if suffix is not None and n.lower().endswith(suffix)]

        if not matches:
            raise ValueError(f"No member matching suffix={suffix!r} exact_name={exact_name!r} in zip; contents: {names}")

        return zf.read(matches[0])


def _cache_dataframe(df: pd.DataFrame, cache_path: Path) -> None:
    try:
        _ensure_cache_dir()
        df.to_csv(cache_path, index=False)
    except Exception as exc:  # pragma: no cover - disk issues are rare
        logger.warning("Downloaded dataset but failed to cache it at %s (%s).", cache_path, exc)


def load_asd_screening() -> pd.DataFrame | None:
    """
    UCI ASD Screening Adult dataset (~704 samples, 21 features:
    10 AQ-10 screening items + age/gender/ethnicity/jaundice/
    family-history/country/used-app-before/result/relation/class).

    The real download is a zip containing `Autism-Adult-Data.arff`
    (plus an unrelated .docx description file) — this pulls out and
    parses just the .arff member.

    Mapped here to a `sensory_sensitivity_proxy` (mean of the 10 AQ-10
    binary items, 0-1) and `attention_proxy` (the dataset's normalized
    `result` score), used to calibrate SensoryProfile defaults and
    initial difficulty placement for new students.
    """
    if _ASD_CACHE.exists():
        try:
            df = pd.read_csv(_ASD_CACHE)
            return _enrich_asd_screening(df)
        except Exception as exc:
            logger.warning("Cached ASD screening dataset unreadable (%s); re-downloading.", exc)

    try:
        zip_bytes = _fetch_bytes(_ASD_SCREENING_URL)
        arff_bytes = _extract_single_member(zip_bytes, suffix=".arff")
        df = _parse_arff(arff_bytes.decode("utf-8", errors="replace"))
    except Exception as exc:
        logger.warning(
            "Could not download/parse ASD screening dataset from %s (%s). "
            "Falling back to the synthetic dataset for this run.",
            _ASD_SCREENING_URL,
            exc,
        )
        return None

    _cache_dataframe(df, _ASD_CACHE)
    return _enrich_asd_screening(df)


def _enrich_asd_screening(df: pd.DataFrame) -> pd.DataFrame:
    aq_cols = [c for c in df.columns if c.lower().startswith("a") and c[1:].split("_")[0].isdigit()]
    if aq_cols:
        numeric_aq = df[aq_cols].apply(pd.to_numeric, errors="coerce")
        df["sensory_sensitivity_proxy"] = numeric_aq.mean(axis=1)
    if "result" in df.columns:
        numeric_result = pd.to_numeric(df["result"], errors="coerce")
        max_result = numeric_result.max() or 1
        df["attention_proxy"] = numeric_result / max_result
    return df


def load_student_performance() -> pd.DataFrame | None:
    """
    UCI Student Performance dataset (~649 samples for the "por"
    subject, 33 features: demographics, study time, absences,
    prior/final grades).

    The real download is a zip containing a NESTED zip (`student.zip`)
    plus a stray `.student.zip_old` file from UCI's own hosting — this
    unwraps both layers and reads `student-por.csv` specifically.

    Mapped to engagement-analogous features: `studytime` -> time_spent
    proxy, `absences` -> idle_time proxy, `failures` -> retry_count
    proxy, `G1`/`G2`/`G3` (period grades) -> rolling accuracy proxy.
    """
    if _STUDENT_PERF_CACHE.exists():
        try:
            df = pd.read_csv(_STUDENT_PERF_CACHE, sep=";")
            return _enrich_student_performance(df)
        except Exception as exc:
            logger.warning("Cached student performance dataset unreadable (%s); re-downloading.", exc)

    try:
        outer_zip_bytes = _fetch_bytes(_STUDENT_PERFORMANCE_URL)
        inner_zip_bytes = _extract_single_member(outer_zip_bytes, exact_name="student.zip")
        csv_bytes = _extract_single_member(inner_zip_bytes, exact_name="student-por.csv")
        df = pd.read_csv(io.BytesIO(csv_bytes), sep=";")
    except Exception as exc:
        logger.warning(
            "Could not download/parse student performance dataset from %s (%s). "
            "Falling back to the synthetic dataset for this run.",
            _STUDENT_PERFORMANCE_URL,
            exc,
        )
        return None

    _cache_dataframe(df, _STUDENT_PERF_CACHE)
    return _enrich_student_performance(df)


def _enrich_student_performance(df: pd.DataFrame) -> pd.DataFrame:
    if {"G1", "G2", "G3"}.issubset(df.columns):
        df["rolling_avg_accuracy_5_proxy"] = (df["G1"] + df["G2"] + df["G3"]) / (3 * 20.0)
    return df


def load_oulad_vle_interactions() -> pd.DataFrame | None:
    """
    OULAD studentVle.csv click-stream table (~10M+ rows in the full
    dataset; this loader is deliberately narrow and only pulls the
    single interaction table needed for temporal engagement /
    early-warning modeling, not the full multi-table dataset).

    OULAD's own download endpoint has proven unreliable (it 403'd a
    plain urllib/pandas request at first, then started returning its
    HTML landing page instead of the zip once the User-Agent was
    fixed — the dataset's download link on the official site appears
    to have moved or been retired). Given that, this loader supports
    THREE sources, tried in order:

      1. Our own already-processed cache (_OULAD_CACHE) — fastest path
         once any of the below has succeeded once.
      2. A manually-provided file dropped into app/ml/data_cache/ by
         the developer — the practical, reliable path in practice,
         since OULAD is also mirrored on Kaggle
         (search "Open University Learning Analytics Dataset") and
         other sources. Supports THREE forms, auto-detected:
           - app/ml/data_cache/studentVle.csv       (extracted already)
           - app/ml/data_cache/oulad_raw.zip         (the full OULAD zip,
             e.g. Kaggle's multi-file archive containing studentVle.csv
             alongside assessments.csv/courses.csv/etc.)
           - any other *.zip dropped in app/ml/data_cache/ containing
             a studentVle.csv member (in case the file isn't renamed).
      3. The live download URL (_OULAD_URL) — kept as a last resort in
         case the official endpoint becomes reachable again later.

    Mapped to: `sum_click` (per day) -> engagement intensity proxy,
    `date` (day offset from course start) -> temporal trend feature.
    """
    if _OULAD_CACHE.exists():
        try:
            return pd.read_csv(_OULAD_CACHE)
        except Exception as exc:
            logger.warning("Cached OULAD dataset unreadable (%s); re-checking other sources.", exc)

    manual_df = _load_oulad_from_manual_drop()
    if manual_df is not None:
        _cache_dataframe(manual_df, _OULAD_CACHE)
        return manual_df

    try:
        zip_bytes = _fetch_bytes(_OULAD_URL)

        # Diagnose BEFORE attempting extraction, rather than letting a
        # generic zipfile exception surface with no context.
        if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
            _ensure_cache_dir()
            debug_path = _CACHE_DIR / "oulad_debug_response.bin"
            debug_path.write_bytes(zip_bytes)

            preview = zip_bytes[:300].decode("utf-8", errors="replace")
            logger.warning(
                "OULAD download did not return a valid zip file (got %d "
                "bytes). The response has been saved to %s for inspection. "
                "First 300 bytes as text:\n%s\n"
                "The live OULAD download endpoint appears to be "
                "unreliable/moved — consider downloading the dataset "
                "manually (e.g. from Kaggle: search 'Open University "
                "Learning Analytics Dataset') and placing studentVle.csv "
                "or the full zip under app/ml/data_cache/ — see this "
                "function's docstring for the exact filenames supported.",
                len(zip_bytes),
                debug_path,
                preview,
            )
            raise ValueError("OULAD response was not a valid zip file — see warning above for details.")

        csv_bytes = _extract_single_member(zip_bytes, exact_name="studentVle.csv")
        df = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as exc:
        logger.warning(
            "OULAD download failed (%s); early-warning will use in-app "
            "session history instead (see ml/early_warning.py, which "
            "never depends on this dataset).",
            exc,
        )
        return None

    _cache_dataframe(df, _OULAD_CACHE)
    return df


def _load_oulad_from_manual_drop() -> pd.DataFrame | None:
    """
    Check app/ml/data_cache/ for a manually-provided OULAD source, in
    priority order: a bare studentVle.csv, then oulad_raw.zip
    (a suggested filename for a manually downloaded full OULAD zip),
    then any other *.zip present that happens to contain
    studentVle.csv as a member. Returns None if nothing is found —
    this is a normal, expected outcome, not an error.
    """
    _ensure_cache_dir()

    bare_csv = _CACHE_DIR / "studentVle.csv"
    if bare_csv.exists():
        try:
            logger.info("Using manually-provided OULAD file: %s", bare_csv)
            return pd.read_csv(bare_csv)
        except Exception as exc:
            logger.warning("Found %s but couldn't read it as CSV (%s); trying other sources.", bare_csv, exc)

    named_zip = _CACHE_DIR / "oulad_raw.zip"
    if named_zip.exists():
        try:
            logger.info("Using manually-provided OULAD zip: %s", named_zip)
            csv_bytes = _extract_single_member(named_zip.read_bytes(), exact_name="studentVle.csv")
            return pd.read_csv(io.BytesIO(csv_bytes))
        except Exception as exc:
            logger.warning("Found %s but couldn't extract studentVle.csv from it (%s); trying other sources.", named_zip, exc)

    for candidate_zip in _CACHE_DIR.glob("*.zip"):
        if candidate_zip.name == "oulad_raw.zip":
            continue  # already tried above
        try:
            csv_bytes = _extract_single_member(candidate_zip.read_bytes(), exact_name="studentVle.csv")
            logger.info("Using manually-provided OULAD zip: %s", candidate_zip)
            return pd.read_csv(io.BytesIO(csv_bytes))
        except Exception:
            continue  # not an OULAD zip, or doesn't contain studentVle.csv — skip silently

    return None


def refresh_all_caches() -> dict[str, bool]:
    """
    Force-refresh all three dataset caches. Intended to be run
    on-demand (`python -m app.ml.data_loader --refresh`) on a machine
    with normal internet access, not automatically on every app
    startup (startup should never block on/depend on external
    network calls).
    """
    results = {}
    for name, path, loader in (
        ("asd_screening", _ASD_CACHE, load_asd_screening),
        ("student_performance", _STUDENT_PERF_CACHE, load_student_performance),
        ("oulad_vle", _OULAD_CACHE, load_oulad_vle_interactions),
    ):
        if path.exists():
            path.unlink()
        results[name] = loader() is not None
    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if "--refresh" in sys.argv:
        outcome = refresh_all_caches()
        for name, ok in outcome.items():
            print(f"{name}: {'OK' if ok else 'FAILED (see warning above)'}")
    else:
        print("Usage: python -m app.ml.data_loader --refresh")
