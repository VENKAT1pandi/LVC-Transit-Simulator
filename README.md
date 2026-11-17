# TransitCap v3 prototype: Seattle Link

**Live dashboard:** https://venkat1pandi.github.io/LVC-Transit-Simulator/

This repository estimates how much Seattle's Link light rail raised nearby home values. It then asks whether a Washington value-capture instrument, applied to the planned West Seattle line, could raise enough to matter to its funding gap.

It implements [`docs/TransitCap v3 Prototype Specification.md`](docs/TransitCap%20v3%20Prototype%20Specification.md) on real open data.

- Results: [`docs/decision_memo.md`](docs/decision_memo.md)
- Rule-by-rule status: [`docs/rules_compliance.md`](docs/rules_compliance.md)
- Interactive map dashboard: open [`outputs/atlas/index.html`](outputs/atlas/index.html) in a browser (needs internet for the map library and basemap). It shows:
  - the study rings, jobs reachable and the access gain for each year since 1995;
  - every West Seattle parcel in 3D, sized by its LID charge, with the TIA parcels outlined;
  - household burden by block group;
  - a what-if panel (elasticity, share of the gain assessed, funding gap) that recomputes revenue with the model's own formula.
  - real buildings in 3D as you zoom in: Microsoft Global ML Building Footprints plus OpenStreetMap buildings and building parts.
    - Heights come from OSM `height` where mapped (12,283), then storeys × 3.2 m (14,120), then Microsoft's estimate, then a 6 m default.
    - `transitcap ingest` downloads the four Microsoft tiles (about 150 MB) into `data/raw/ms_buildings/`.
    - The page loads its building tiles from `outputs/atlas/buildings/`, so serve the folder (`python3 -m http.server` in `outputs/atlas/`) rather than opening the file directly.

> The repository folder is named "Chennai", but the corridor is Seattle. The spec flags Indian registered prices as unreliable, and the user chose the spec's default (ADR-0001).

## Rebuild everything

```bash
uv sync               # Python 3.12, pinned dependencies (pyproject.toml + uv.lock)
make all              # ingest → build → power → freeze → estimate → falsify → revenue → decide → report
make test             # unit tests (estimator, revenue rules, gates)
```

`make all` took 40 minutes to 4 hours on an 8-core, 7 GB machine; the placebo-station test dominates and slows sharply under memory pressure (ADR-0006). It needs about 3.5 GB of RAM, about 8 GB of disk (the unzipped value history is 3.4 GB), and network access on the first run. First, download the raw files listed in [`data/reference/sources.md`](data/reference/sources.md) into `data/raw/`:

- the assessor zips;
- LODES WAC files;
- the TIGER 2020 Washington blocks;
- the ACS B19013 and B25003 summary files;
- Sound Transit GTFS;
- Geofabrik Washington.

`transitcap ingest` then fetches parcel polygons and extracts the walk network. Assessor zips must be unzipped into `data/interim/kc_assessor/`.

## Pipeline

| Step | Module | Output |
|---|---|---|
| ingest | `ingest/parcels.py`, `ingest/osm.py` | Cached raw parcel pages; walk edges |
| build | `build/tables.py` | The ten tables in `data/processed/*.parquet` |
| power | `estimate/power.py`, `revenue/run.py` | Minimum detectable effect and break-even effect (gate G1) |
| freeze | `config.py` | `config/pap.lock`; later steps refuse to run if `pap.yaml` changes |
| estimate | `estimate/csdid.py`, `estimate/run.py` | Event study, spillover, station effects, elasticity, specification curve |
| falsify | `estimate/falsify.py` | Seven-test suite |
| revenue | `revenue/` | Land split, assessment bridge, Monte Carlo, tornado, incidence |
| decide | `decide/gates.py` | `outputs/results/gates.json` |
| report | `report/` | Figures, decision memo, interactive atlas (`outputs/atlas/index.html`), manifest with hashes |

## Where the build departs from the spec

Each departure has a decision record in [`docs/decisions/`](docs/decisions/):

- No R5 and no archived GTFS. Accessibility is walk plus Link from the current timetable, and buses are not modelled (ADR-0002).
- The estimators are written in Python, not the R packages the spec names, with three known differences (ADR-0003).
- The gate diagram was missing from the spec, so the gates are reconstructed from its text (ADR-0004).
- The funding gap is a reported range, not an agency figure (ADR-0005).

## Ownership

The author owns the code and the plan. Legal conclusions need counsel. The funding gap needs the agency finance team.
