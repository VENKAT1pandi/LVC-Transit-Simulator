"""Filesystem layout. Raw data is never modified; every later stage writes to its own folder."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
REFERENCE = ROOT / "data" / "reference"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
CONFIG = ROOT / "config"
DOCS = ROOT / "docs"

# Metric CRS for every distance and area: UTM zone 10N (metres). Web Mercator is display-only.
CRS_METRIC = "EPSG:32610"
CRS_GEO = "EPSG:4326"

for _p in (INTERIM, PROCESSED, OUTPUTS):
    _p.mkdir(parents=True, exist_ok=True)
