"""Capitalization atlas: one self-contained HTML dashboard, MapLibre GL, data inlined as GeoJSON.

- Corridor view: 300 m cells coloured by walk ring, by jobs reachable in a chosen year, or by the
  access gain since 1995; stations fill in as they open while the year slider moves.
- West Seattle view: every parcel within a 10-minute walk of the two planned stations, extruded in
  3D by its LID charge under the what-if settings; TIA parcels outlined; block groups coloured by
  the annual charge as a share of median household income.
- The what-if panel recomputes LID revenue in the browser with the constant from `twin.lid_constant`,
  so its totals equal the revenue model's at the plan's central parameter values.
The station list doubles as the table view and keyboard path.
"""

import io
import json
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd

from transitcap.config import load_pap
from transitcap.paths import OUTPUTS, PROCESSED, RAW
from transitcap.report import buildings, twin

RES = OUTPUTS / "results"
MAPLIBRE = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl"
TEST_NAMES = {"planted_effect": "Finds a planted price rise",
              "pretrend_bounds": "Near and far homes moved alike before the station",
              "placebo_stations": "Shows no rise around fake stations",
              "placebo_date": "Shows no rise at a fake date",
              "rezoning_split": "Rules out zoning changes",
              "composition": "Same kinds of homes sold before and after",
              "leave_one_station_out": "Holds up when any one station is left out"}


def no_estimate_reason(sid: str, status: str, pap: dict) -> str:
    if status != "open":
        return "No estimate"
    if sid in pap["treatment"]["excluded_stations"]:
        return "Not counted: buses already ran through this tunnel before the train"
    return "Too few home sales to measure on its own (counted in the overall result)"


def link_lines() -> dict:
    """Current Link alignments and their published colours from the GTFS feed, plus the planned
    West Seattle branch drawn station to station from SODO (its route is not final)."""
    with zipfile.ZipFile(RAW / "gtfs" / "st_40_gtfs.zip") as z:
        trips = pd.read_csv(io.BytesIO(z.read("trips.txt")), dtype=str)
        shapes = pd.read_csv(io.BytesIO(z.read("shapes.txt")), dtype={"shape_id": str})
        routes = pd.read_csv(io.BytesIO(z.read("routes.txt")), dtype=str).set_index("route_id")
    feats = []
    for rid, line in (("100479", "1 Line"), ("2LINE", "2 Line")):
        sid = trips[trips.route_id == rid].shape_id.value_counts().index[0]
        sh = shapes[shapes.shape_id == sid].sort_values("shape_pt_sequence")
        feats.append({"type": "Feature", "properties": {"line": line, "color": "#" + routes.at[rid, "route_color"]},
                      "geometry": {"type": "LineString",
                                   "coordinates": sh[["shape_pt_lon", "shape_pt_lat"]].round(5).values.tolist()}})
    st = pd.read_parquet(PROCESSED / "dim_station.parquet", columns=["station_id", "lon", "lat"]).set_index("station_id")
    feats.append({"type": "Feature", "properties": {"line": "West Seattle (planned)", "planned": 1},
                  "geometry": {"type": "LineString",
                               "coordinates": [[round(st.at[s, "lon"], 5), round(st.at[s, "lat"], 5)]
                                               for s in ("C15", "WS1", "WS2")]}})
    return {"type": "FeatureCollection", "features": feats}


def stations(pap: dict, rev: dict) -> dict:
    st = gpd.read_parquet(PROCESSED / "dim_station.parquet")
    est = pd.read_csv(RES / "station_estimates.csv")
    proj = {r["station_id"]: r for r in rev.get("station_projection", [])}
    st = st[st.county == "King"].merge(est, on="station_id", how="left")
    svc = twin.service_years().set_index("station_id")
    feats = []
    for r in st.itertuples():
        props = {"id": r.station_id, "name": r.station_name, "status": r.status, "segment": r.segment,
                 "open_year": int(svc.at[r.station_id, "service_year"]),
                 "fund_year": int(svc.at[r.station_id, "funding_year"]),
                 "opened": str(r.open_date.date()) if r.status == "open" else None}
        if r.status == "open" and np.isfinite(getattr(r, "att", np.nan)):
            props.update(kind="estimate", value=round(100 * np.expm1(r.att), 1),
                         lo=round(100 * np.expm1(r.lo), 1), hi=round(100 * np.expm1(r.hi), 1),
                         n=int(r.n_treated_sales), dose=round(r.dose, 2), cohort=int(r.cohort))
        elif r.status == "planned" and r.station_id in proj:
            q = proj[r.station_id]
            props.update(kind="projection", gain_p50=q["gain_p50"], gain_p10=q["gain_p10"],
                         gain_p90=q["gain_p90"], parcels=q["parcels"], dose=round(q["dose_mean"], 2))
        else:
            props.update(kind="none", reason=no_estimate_reason(r.station_id, r.status, pap))
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                      "properties": props})
    return {"type": "FeatureCollection", "features": feats}


def summary() -> dict:
    est = json.loads((RES / "estimates.json").read_text())
    fals = json.loads((RES / "falsification.json").read_text())
    rev = json.loads((RES / "revenue.json").read_text())
    gates = json.loads((RES / "gates.json").read_text())
    be = json.loads((RES / "breakeven.json").read_text())
    spec = {s["spec"]: s for s in est["spec_curve"]}
    lid = rev["instruments"]["lid"]
    pct = lambda v: round(100 * float(np.expm1(v)), 1)  # noqa: E731
    return {
        "primary": {k: pct(est["primary"][k]) for k in ("estimate", "lo", "hi")},
        "n_sales": est["n_sales"], "n_treated": est["n_treated_sales"],
        "lid": {k: lid[k] for k in ("pv_net_median", "funding_ratio_median", "p_material")},
        "tests": [{"name": TEST_NAMES.get(t["test"], t["test"]), "passed": t["passed"]} for t in fals],
        "gates": [{"gate": g["gate"], "question": g["question"], "passed": g["passed"], "outcome": g["outcome"]}
                  for g in gates["gates"]],
        "decision_gate": gates["decision_gate"],
        "elasticity": est["elasticity"],
        "eps_open": spec["cohort date = open"]["elasticity"],
        "eps_needed": be["elasticity_needed"]["lid"],
        "event_study": pd.read_csv(RES / "event_study_primary.csv").round(5).to_dict("records"),
        "burden": {"median": rev["incidence"]["median_annual_share"], "max": rev["incidence"]["max_annual_share"]},
        "tia": {"parcels": rev["tia_area_parcels"], "zone": rev["base"]["zone_parcels"],
                "gross": rev["instruments"]["tia"]["pv_gross_median"],
                "net": rev["instruments"]["tia"]["pv_net_median"]},
    }


def write() -> None:
    pap = load_pap()
    rev = json.loads((RES / "revenue.json").read_text())
    parcels, burden, lid = twin.west_seattle(pap)
    grid, years = twin.corridor_grid(pap)
    st = stations(pap, rev)
    data = {"stations": st, "lines": link_lines(), "grid": grid, "years": years,
            "parcels": parcels, "burden": burden, "lid": lid, "s": summary(),
            "bldg_bounds": buildings.write(grid, parcels, st)}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"), default=float))
    html = html.replace("__MAPLIBRE__", MAPLIBRE)
    out = OUTPUTS / "atlas"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html)


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Light Rail and Home Values</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cal+Sans&family=Geist+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="__MAPLIBRE__.css">
<script src="__MAPLIBRE__.js"></script>
<style>
:root{--surface:#fafafa;--panel:#ffffff;--frame:#f4f4f5;--ink:#171717;--ink2:#737373;--ink3:#a3a3a3;--rule:#e9e9eb;
 --s1:#6366f1;--s2:#f59e0b;--s3:#10b981;--neutral:#d4d4d8;
 --q1:#e0e7ff;--q2:#a5b4fc;--q3:#818cf8;--q4:#6366f1;--q5:#4338ca;
 --o1:#fef3c7;--o2:#fcd34d;--o3:#f59e0b;--o4:#d97706;--o5:#92400e;
 --bldg:#f4f4f5;--good:#10b981;--critical:#ef4444;--badge:#eef2ff;--badge-ink:#4f46e5;
 --f-head:"Cal Sans","Inter",system-ui,sans-serif;--f-body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;--f-mono:"Geist Mono",ui-monospace,"SFMono-Regular",Menlo,monospace;
 font:14px/1.5 var(--f-body);color:var(--ink)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--surface:#161616;--panel:#1b1b1b;--frame:#111111;--ink:#f5f5f5;
 --ink2:#a3a3a3;--ink3:#737373;--rule:rgb(255 255 255/.08);--s1:#818cf8;--s2:#fbbf24;--s3:#34d399;--neutral:#3f3f46;
 --q1:#312e81;--q2:#4338ca;--q3:#6366f1;--q4:#a5b4fc;--q5:#e0e7ff;
 --o1:#78350f;--o2:#b45309;--o3:#f59e0b;--o4:#fcd34d;--o5:#fef3c7;--bldg:#3f3f46;--badge:rgb(99 102 241/.16);--badge-ink:#a5b4fc;color-scheme:dark}}
:root[data-theme=dark]{--surface:#161616;--panel:#1b1b1b;--frame:#111111;--ink:#f5f5f5;--ink2:#a3a3a3;--ink3:#737373;--rule:rgb(255 255 255/.08);
 --s1:#818cf8;--s2:#fbbf24;--s3:#34d399;--neutral:#3f3f46;--q1:#312e81;--q2:#4338ca;--q3:#6366f1;--q4:#a5b4fc;--q5:#e0e7ff;
 --o1:#78350f;--o2:#b45309;--o3:#f59e0b;--o4:#fcd34d;--o5:#fef3c7;--bldg:#3f3f46;--badge:rgb(99 102 241/.16);--badge-ink:#a5b4fc;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);height:100vh;display:grid;grid-template-columns:minmax(320px,420px) 1fr;grid-template-rows:auto 1fr}
header{grid-column:1/-1;display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--rule);background:var(--panel)}
header h1{font-size:16px;margin:0;font-weight:650}
header .verdict{color:var(--ink2);font-size:13px;flex:1;min-width:240px}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.seg button{border:0;background:transparent;color:var(--ink);padding:6px 12px;font:inherit;font-size:13px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--ink);color:var(--surface)}
aside{background:var(--panel);border-right:1px solid var(--rule);overflow:auto;padding:16px}
section{margin-bottom:22px} h2{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink2);margin:0 0 10px;font-weight:600}
p{margin:0 0 10px} .muted{color:var(--ink2);font-size:12px}
.kpis{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.kpi{border:1px solid var(--rule);border-radius:8px;padding:10px}
.kpi .v{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.15}
.kpi .l{font-size:12px;color:var(--ink2)}
.gates{list-style:none;margin:0;padding:0}
.gates li{display:grid;grid-template-columns:28px 18px 1fr;gap:6px;padding:6px 0;border-bottom:1px solid var(--rule);font-size:13px}
.gates b{font-variant-numeric:tabular-nums}.gates .why{color:var(--ink2);font-size:12px;grid-column:3}
.ok{color:var(--good)} .no{color:var(--critical)} .na{color:var(--ink3)}
.gates li.stop{background:color-mix(in srgb,var(--critical) 8%,transparent)}
label.sl{display:block;font-size:13px;margin:10px 0 2px}
label.sl output{float:right;font-variant-numeric:tabular-nums;font-weight:600}
input[type=range]{width:100%;accent-color:var(--s2)}
.presets{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0 10px}
.presets button{font:inherit;font-size:12px;border:1px solid var(--rule);background:transparent;color:var(--ink);border-radius:6px;padding:3px 8px;cursor:pointer}
.result{border:1px solid var(--rule);border-radius:8px;padding:10px;margin-top:8px}
.result .big{font-size:20px;font-weight:650;font-variant-numeric:tabular-nums}
.meter{height:8px;background:var(--rule);border-radius:4px;position:relative;margin:8px 0 4px;overflow:visible}
.meter i{position:absolute;left:0;top:0;bottom:0;background:var(--s2);border-radius:4px}
.meter u{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink)}
svg text{fill:var(--ink2);font-size:11px;font-variant-numeric:tabular-nums}
.chart{width:100%;height:auto;display:block;touch-action:none}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;color:var(--ink2);font-size:12px;border-bottom:1px solid var(--rule);padding:4px}
td{padding:6px 4px;border-bottom:1px solid var(--rule);vertical-align:top}
tr[tabindex]{cursor:pointer} tr[tabindex]:hover td{background:color-mix(in srgb,var(--s1) 8%,transparent)}
tr[tabindex]:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
tr[aria-selected=true] td{background:color-mix(in srgb,var(--s1) 16%,transparent);font-weight:600}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
main{position:relative;min-height:0} #map{position:absolute;inset:0}
.card{position:absolute;background:color-mix(in srgb,var(--panel) 94%,transparent);border:1px solid var(--rule);border-radius:8px;padding:10px 12px;font-size:13px;box-shadow:0 1px 4px rgb(0 0 0/.12)}
#layers{top:10px;left:10px;max-width:270px} #layers fieldset{border:0;margin:0;padding:0} #layers legend{font-weight:600;margin-bottom:4px;padding:0}
#layers label{display:block;padding:2px 0;cursor:pointer} #layers summary{font-weight:600;cursor:pointer;margin-bottom:4px}
#legend{bottom:106px;right:10px;max-width:270px;max-height:calc(100% - 230px);overflow:auto}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-2px}
.ramp{display:flex;gap:2px;margin:4px 0}.ramp span{flex:1;height:10px}.ramp span:first-child{border-radius:3px 0 0 3px}.ramp span:last-child{border-radius:0 3px 3px 0}
.ramp-l{display:flex;justify-content:space-between;font-size:11px;color:var(--ink2);font-variant-numeric:tabular-nums}
#yearbar{left:10px;right:10px;bottom:30px;display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;padding:8px 12px} #cap-y{flex-basis:100%;min-height:1.4em}
#yearbar input{flex:1;accent-color:var(--s1)} #yearbar b{font-variant-numeric:tabular-nums;font-size:16px;min-width:3.2em}
#play{font:inherit;border:1px solid var(--rule);background:transparent;color:var(--ink);border-radius:6px;padding:4px 10px;cursor:pointer}
#tip{position:absolute;pointer-events:none;background:var(--panel);color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:8px 10px;font-size:12px;box-shadow:0 2px 8px rgb(0 0 0/.18);max-width:280px;z-index:5}
#tip b{font-weight:650}
.maplibregl-popup-content{background:var(--panel);color:var(--ink)}
aside,#story{grid-column:1;grid-row:2} main{grid-column:2;grid-row:2}
#story{display:none;background:var(--panel);border-right:1px solid var(--rule);overflow:auto;padding:24px 22px}
body.simple #story{display:flex;flex-direction:column} body.simple aside,body.simple #layers,body.simple #legend,body.simple .seg.views,body.simple #verdict{display:none}
body.simple:not(.show-year) #yearbar{display:none}
#story .stepno{font-size:12px;color:var(--ink2);letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px}
#story .dots{display:flex;gap:6px;margin-bottom:18px}#story .dots span{width:28px;height:4px;border-radius:2px;background:var(--rule)}#story .dots span.on{background:var(--s2)}
#story h2{font-size:24px;line-height:1.2;text-transform:none;letter-spacing:0;color:var(--ink);margin:0 0 14px;font-weight:700}
#story .big{font-size:40px;font-weight:750;line-height:1.05;margin:6px 0 4px;font-variant-numeric:tabular-nums}
#story .bigl{color:var(--ink2);font-size:14px;margin-bottom:18px}
#story p{font-size:16px;line-height:1.55;margin:0 0 14px}
#story .key{font-size:14px;margin:4px 0 14px}#story .key div{margin:4px 0}
#story .nav{margin-top:auto;padding-top:18px;display:flex;gap:10px}
#story .nav button{font:inherit;font-size:16px;padding:10px 18px;border-radius:8px;cursor:pointer;border:1px solid var(--rule);background:transparent;color:var(--ink)}
#story .nav button.primary{background:var(--ink);color:var(--surface);border-color:var(--ink);flex:1}
#story .nav button:disabled{opacity:.35;cursor:default}
#story .hint{font-size:14px;color:var(--ink2);background:color-mix(in srgb,var(--s1) 8%,transparent);border-radius:8px;padding:10px 12px;margin:0 0 14px}
.place{font:600 12px/1 system-ui,sans-serif;color:#0b0b0b;background:rgb(255 255 255/.92);border:1px solid #d6d4ce;border-radius:999px;padding:5px 9px;white-space:nowrap;box-shadow:0 1px 3px rgb(0 0 0/.15);pointer-events:none}
.place.new{background:#eb6834;color:#fff;border-color:#eb6834}
.aboutb{font:inherit;font-size:13px;border:1px solid var(--rule);background:var(--panel);color:var(--ink);border-radius:8px;padding:6px 12px;cursor:pointer}
.aboutb:hover{background:color-mix(in srgb,var(--ink) 6%,transparent)}
dialog#about{border:0;border-radius:12px;padding:0;width:min(860px,94vw);max-height:88vh;background:var(--panel);color:var(--ink);box-shadow:0 10px 40px rgb(0 0 0/.35)}
dialog#about::backdrop{background:rgb(0 0 0/.45)}
#about .ab-head{position:sticky;top:0;background:var(--panel);display:flex;align-items:center;gap:12px;padding:16px 22px;border-bottom:1px solid var(--rule)}
#about .ab-head h2{font-size:20px;text-transform:none;letter-spacing:0;color:var(--ink);margin:0;flex:1}
#about .ab-head button{font:inherit;font-size:14px;border:1px solid var(--rule);background:transparent;color:var(--ink);border-radius:8px;padding:6px 12px;cursor:pointer}
#about .ab-tabs{display:flex;gap:6px;padding:12px 22px 0}
#about .ab-tabs button{font:inherit;font-size:14px;border:0;border-bottom:3px solid transparent;background:transparent;color:var(--ink2);padding:8px 10px;cursor:pointer}
#about .ab-tabs button[aria-selected=true]{color:var(--ink);border-bottom-color:var(--s2);font-weight:600}
#about .ab-body{padding:16px 22px 22px;overflow:auto;max-height:calc(88vh - 120px)}
#about .ab-body p,#about .ab-body li{font-size:14px;line-height:1.55}
#about .ab-body h3{font-size:15px;margin:18px 0 6px}
#about .ab-table{width:100%;border-collapse:collapse;font-size:13px}
#about .ab-table th{text-align:left;color:var(--ink2);font-weight:600;padding:6px;border-bottom:1px solid var(--rule)}
#about .ab-table td{padding:8px 6px;border-bottom:1px solid var(--rule);vertical-align:top}
#about .ab-table td:first-child{font-weight:600;min-width:150px}
#about .src{color:var(--ink2);font-size:12px;word-break:break-word}
#about .tablewrap{overflow-x:auto}
.lineb{font:700 12px/1 system-ui,sans-serif;color:#fff;border-radius:6px;padding:5px 8px;box-shadow:0 1px 3px rgb(0 0 0/.25);pointer-events:none;border:2px solid #fff}
@media (max-width:760px){body{grid-template-columns:1fr;grid-template-rows:auto 62vh auto;height:auto}
 main{grid-row:2;grid-column:1;height:62vh} aside,#story{grid-row:3;border-right:0} #story h2{font-size:21px} #story .big{font-size:32px} #legend{display:none} #layers{max-width:180px;font-size:12px} #yearbar{bottom:52px}}
/* ---------- Bklit UI look: frames, cards, pills, Cal Sans headings, Geist Mono numbers ---------- */
h1,h2,h3,#story h2,#about .ab-head h2,.kpi .v,.result .big,#story .big{font-family:var(--f-head);letter-spacing:.005em}
header{padding:10px 20px;gap:14px;background:color-mix(in srgb,var(--surface) 85%,transparent);backdrop-filter:blur(8px)}
header h1{font-size:19px;font-weight:600}
.seg{background:var(--frame);border:1px solid var(--rule);border-radius:10px;padding:3px;gap:2px}
.seg button{border-radius:7px;padding:6px 12px;color:var(--ink2);font-weight:500;transition:background .15s,color .15s}
.seg button:hover{color:var(--ink)}
.seg button[aria-pressed=true]{background:var(--panel);color:var(--ink);box-shadow:0 1px 2px rgb(0 0 0/.08),0 0 0 1px var(--rule)}
.aboutb{border-radius:10px;font-weight:500;padding:7px 12px;box-shadow:0 1px 2px rgb(0 0 0/.05)}
aside,#story{background:var(--surface);border-right:1px solid var(--rule)}
aside{padding:18px}
section h2{font-family:var(--f-head);text-transform:none;letter-spacing:.005em;font-size:17px;color:var(--ink);font-weight:600;margin:0 0 4px}
section>h2+p.muted,section>h2+.muted{margin-bottom:12px}
.muted{color:var(--ink2)}
.kpis{background:var(--frame);border:1px solid var(--rule);border-radius:16px;padding:6px;gap:6px}
.kpi{background:var(--panel);border:1px solid var(--rule);border-radius:11px;padding:12px 14px;box-shadow:0 1px 2px rgb(0 0 0/.04)}
.kpi .v{font-size:26px;font-weight:600}
.gates li{border-bottom:1px dashed var(--rule)}
.gates li.stop{background:color-mix(in srgb,var(--critical) 7%,transparent);border-radius:8px}
.result{background:var(--panel);border-radius:14px;padding:14px;box-shadow:0 1px 2px rgb(0 0 0/.04)}
.result .big{font-size:24px;font-weight:600}
.meter{height:6px;border-radius:999px}.meter i{border-radius:999px;background:linear-gradient(90deg,var(--s2),color-mix(in srgb,var(--s2) 70%,var(--critical)))}
input[type=range]{accent-color:var(--ink)}
.presets button{border-radius:999px;padding:4px 11px;font-weight:500;background:var(--panel)}
.presets button:hover{background:var(--frame)}
.chart{background:var(--panel);border:1px solid var(--rule);border-radius:14px;margin-top:10px}
svg text{fill:var(--ink2);font-family:var(--f-mono);font-size:10px}
table{font-size:13px} th{font-weight:500}
.num,#year-o{font-variant-numeric:tabular-nums}
.kpi .v,#story .big,.result .big{font-variant-numeric:normal}
.result .unit{font-family:var(--f-body);font-size:13px;font-weight:400;color:var(--ink2);letter-spacing:0;margin-left:4px}
.card{background:color-mix(in srgb,var(--panel) 92%,transparent);backdrop-filter:blur(10px);border:1px solid var(--rule);border-radius:14px;box-shadow:0 8px 24px -12px rgb(0 0 0/.18),0 1px 2px rgb(0 0 0/.05)}
#layers summary{font-family:var(--f-head);font-size:14px}
#year-o{font-family:var(--f-mono);font-weight:500}
#play{border-radius:999px;width:32px;height:32px;padding:0;background:var(--ink);color:var(--surface);border:0}
#tip,#svgtip{border-radius:10px!important;box-shadow:0 10px 30px -10px rgb(0 0 0/.3)!important;border:1px solid var(--rule)!important}
/* story: a white card inside a soft frame */
#story{padding:16px}
#story>.frame{background:var(--frame);border:1px solid var(--rule);border-radius:18px;padding:6px;display:flex;flex-direction:column;flex:1;min-height:0}
#story .cardin{background:var(--panel);border:1px solid var(--rule);border-radius:13px;padding:22px 22px 18px;display:flex;flex-direction:column;flex:1;overflow:auto;box-shadow:0 1px 2px rgb(0 0 0/.04)}
#story .stepno{display:inline-flex;align-self:flex-start;text-transform:none;letter-spacing:0;font-size:12px;font-weight:500;color:var(--badge-ink);background:var(--badge);border-radius:999px;padding:3px 9px;margin-bottom:12px}
#story .dots span{height:3px;border-radius:999px;width:22px}
#story .dots span.on{background:var(--ink)}
#story h2{font-size:30px;font-weight:600;margin-bottom:4px}
#story .lede{color:var(--ink2);font-size:15px;margin:0 0 18px}
#story .bigbox{background:var(--frame);border:1px solid var(--rule);border-radius:12px;padding:14px 16px;margin-bottom:18px}
#story .big{font-size:40px;font-weight:600;margin:0}
#story .bigl{margin:2px 0 0;font-size:13.5px}
#story p{font-size:15px;color:var(--ink)}
#story .nav button{border-radius:10px;font-weight:500;font-size:15px}
#story .nav button.primary{background:var(--ink);color:var(--surface);border-color:var(--ink)}
#story .hint{background:var(--badge);color:var(--badge-ink);border-radius:10px}
.place{font-family:var(--f-body);font-weight:500;border-radius:999px;border-color:rgb(0 0 0/.08);box-shadow:0 4px 12px -6px rgb(0 0 0/.3)}
.place.new{background:#171717;border-color:#171717;color:#fff}
.lineb{border-radius:999px;font-family:var(--f-body);font-weight:600}
/* about dialog: tabs as a pill track */
dialog#about{border-radius:18px;border:1px solid var(--rule)}
#about .ab-head{border-bottom:1px solid var(--rule)}
#about .ab-head h2{font-size:22px;font-weight:600}
#about .ab-head button{border-radius:10px}
#about .ab-tabs{margin:14px 22px 0;padding:3px;gap:2px;background:var(--frame);border:1px solid var(--rule);border-radius:10px;display:inline-flex}
#about .ab-tabs button{border:0;border-radius:7px;padding:6px 12px;font-weight:500}
#about .ab-tabs button[aria-selected=true]{background:var(--panel);color:var(--ink);box-shadow:0 1px 2px rgb(0 0 0/.08),0 0 0 1px var(--rule)}
#about .ab-body h3{font-family:var(--f-head);font-weight:600}
#about .src{font-family:var(--f-mono);font-size:11px}
#about .tablewrap{border:1px solid var(--rule);border-radius:12px}
#about .ab-table th{background:var(--frame)}
.maplibregl-ctrl-group{border-radius:10px!important;box-shadow:0 1px 2px rgb(0 0 0/.08)!important}
</style></head><body class="simple">
<header>
 <div><h1>Light Rail and Home Values</h1></div>
 <div class="verdict" id="verdict"></div>
 <div class="seg" role="group" aria-label="How much detail">
  <button id="m-simple" aria-pressed="true">Simple view</button><button id="m-detail" aria-pressed="false">Detailed view</button>
 </div>
 <div class="seg views" role="group" aria-label="Map view">
  <button id="v-corr" aria-pressed="true">Whole region</button><button id="v-city" aria-pressed="false">Downtown in 3D</button><button id="v-ws" aria-pressed="false">West Seattle in 3D</button>
 </div>
 <button id="about-btn" class="aboutb" aria-haspopup="dialog">ⓘ About the data</button>
</header>
<section id="story" aria-live="polite"></section>
<aside aria-label="Results">
 <section><h2>The answer</h2><div class="kpis" id="kpis"></div></section>
 <section><h2>The checks, step by step</h2><ul class="gates" id="gates"></ul>
  <p class="muted" style="margin-top:8px">The checks stop at the first "no". Checks after that are shown only for information.</p></section>
 <section aria-labelledby="wi-h"><h2 id="wi-h">Try it yourself</h2>
  <p class="muted">What if West Seattle homeowners paid a share of the value the train adds to their homes? Move the sliders to see the result. (Main estimate, allowing for uncertainty: <span id="mcmed"></span>.)</p>
  <label class="sl" for="eps">How much more homes near the new stations are worth <output id="eps-o"></output></label>
  <input id="eps" type="range" min="0" max="0.15" step="0.001">
  <div class="presets"><button data-eps="est">Study result</button><button data-eps="open">Best-case reading</button><button data-eps="need">What's needed</button></div>
  <label class="sl" for="cap">Share of that extra value the city charges <output id="cap-o"></output></label>
  <input id="cap" type="range" min="0.3" max="0.6" step="0.01">
  <label class="sl" for="gap">Money still missing for the line <output id="gap-o"></output></label>
  <input id="gap" type="range" min="0.8" max="3.8" step="0.05">
  <div class="result" aria-live="polite">
   <div class="big" id="r-pv"></div><div class="muted" id="r-ratio"></div>
   <div class="meter" aria-hidden="true"><i id="r-bar"></i><u id="r-thr"></u></div>
   <div class="muted" id="r-need"></div><div class="muted" id="r-hh" style="margin-top:6px"></div>
  </div>
  <svg class="chart" id="curve" viewBox="0 0 380 170" role="img" aria-label="Share of the missing money raised, by home price rise"></svg>
 </section>
 <section><h2>Home prices near stations, year by year</h2>
  <p class="muted">Each dot compares homes a short walk from a new station with similar homes farther away. Above 0 means nearby homes did better. The line through each dot is the likely range. Year 0 is when money for the station was committed.</p>
  <svg class="chart" id="es" viewBox="0 0 380 190" role="img" aria-label="Home prices near stations, year by year"></svg></section>
 <section><h2>How reliable is the price result?</h2><p class="muted">The price result passed only some standard checks. Read it as "no clear rise", not "prices fell".</p><ul class="gates" id="tests"></ul></section>
 <section><h2>Stations</h2>
  <table><thead><tr><th scope="col">Station</th><th scope="col">Change in nearby home prices (likely range)</th></tr></thead><tbody id="rows"></tbody></table>
 </section>
 <section><h2>Good to know</h2>
  <ul class="muted" style="padding-left:18px;margin:0">
   <li>This is a prototype built only from public data.</li>
   <li>Buses are not included, so the train's benefit may look bigger than it really is.</li>
   <li>The "money still missing" is a range from news reports, not an official figure.</li>
   <li>The legal points need a lawyer to confirm. Sound Transit can't charge homeowners itself; the City of Seattle would have to.</li>
   <li>Data: King County home sales and property values, Sound Transit timetables, US Census jobs and income figures, OpenStreetMap. Buildings: Microsoft building footprints and OpenStreetMap.</li>
  </ul></section>
</aside>
<main>
 <div id="map" role="region" aria-label="Map"></div>
 <details class="card" id="layers" open><summary>Map options</summary><fieldset><legend>Colour the map by</legend>
  <label><input type="radio" name="theme" value="rings" checked> Walking distance to a station</label>
  <label><input type="radio" name="theme" value="jobs"> Jobs you can reach in 45 min</label>
  <label><input type="radio" name="theme" value="gain"> Growth in reachable jobs since 1995</label>
  <label><input type="radio" name="theme" value="burden"> Cost to West Seattle households</label>
  <label><input type="radio" name="theme" value="none"> Nothing</label></fieldset>
  <hr style="border:0;border-top:1px solid var(--rule);margin:6px 0">
  <label><input type="checkbox" id="c-3d" checked> 3D: taller = more jobs reachable</label>
  <label><input type="checkbox" id="c-bldg" checked> Real buildings in 3D (zoom in)</label>
  <label><input type="checkbox" id="c-parcels" checked> West Seattle homes: taller = bigger charge</label>
  <label><input type="checkbox" id="c-tia" checked> Outline the tax-sharing zone</label>
 </details>
 <div class="card" id="legend"></div>
 <div class="card" id="yearbar"><button id="play" aria-label="Play years">▶</button>
  <label for="year" class="muted">Train network in</label><input id="year" type="range"><b id="year-o"></b><div id="cap-y" class="muted" aria-live="polite"></div></div>
 <div id="tip" hidden></div>
</main>
<dialog id="about" aria-labelledby="ab-title">
 <div class="ab-head"><h2 id="ab-title">About the data</h2><button id="ab-close">Close</button></div>
 <div class="ab-tabs" role="tablist">
  <button role="tab" aria-selected="true" data-tab="ab-data">Datasets</button>
  <button role="tab" aria-selected="false" data-tab="ab-warn">Disclaimers</button>
  <button role="tab" aria-selected="false" data-tab="ab-method">Methodology</button>
  <button role="tab" aria-selected="false" data-tab="ab-credit">Credits</button>
 </div>
 <div class="ab-body">
  <section id="ab-data" role="tabpanel">
   <p>All data is public. Each dataset, its use and its publisher:</p>
   <div class="tablewrap"><table class="ab-table">
    <thead><tr><th scope="col">Dataset</th><th scope="col">Used for</th><th scope="col">Who publishes it · years</th></tr></thead>
    <tbody>
     <tr><td>Home sales</td><td>The 125,812 house sales used to check whether prices rose near new stations</td><td>King County Department of Assessments, "Real Property Sales" · 1995–2026<div class="src">info.kingcounty.gov/assessor/datadownload</div></td></tr>
     <tr><td>Property values and house details</td><td>Today's value of each West Seattle home, and house size, age and condition for the price comparison</td><td>King County Department of Assessments, "Value History", "Parcel", "Residential Building" · values to tax year 2027</td></tr>
     <tr><td>Property outlines</td><td>The shape of each West Seattle property in 3D</td><td>King County GIS, parcel map service<div class="src">gismaps.kingcounty.gov</div></td></tr>
     <tr><td>Train timetables</td><td>Where the stations and lines are, the line colours, and how long trips take</td><td>Sound Transit open timetable data (GTFS), Fall 2026 edition</td></tr>
     <tr><td>When each station was paid for and opened</td><td>The year slider and the funding and opening dates</td><td>Sound Transit news releases and Wikipedia station articles · see data/reference/sources.md</td></tr>
     <tr><td>Where jobs are</td><td>"Jobs you can reach in 45 minutes"</td><td>US Census Bureau, LEHD Origin-Destination Employment Statistics (LODES), 2019</td></tr>
     <tr><td>Census blocks</td><td>Placing jobs and households on the map</td><td>US Census Bureau, TIGER/Line 2020 blocks</td></tr>
     <tr><td>Household income and home ownership</td><td>"Cost to West Seattle households"</td><td>US Census Bureau, American Community Survey 5-year estimates, 2018–2022</td></tr>
     <tr><td>Streets and footpaths</td><td>Walking times to stations</td><td>OpenStreetMap, Washington extract from Geofabrik</td></tr>
     <tr><td>Buildings</td><td>The 3D buildings</td><td>Microsoft Global ML Building Footprints, and OpenStreetMap buildings</td></tr>
     <tr><td>Background map</td><td>Streets, place names and water</td><td>OpenStreetMap standard map tiles</td></tr>
     <tr><td>Laws</td><td>Whether the city could charge homeowners, and the limits</td><td>Revised Code of Washington 35.43, 39.114 and 81.112<div class="src">app.leg.wa.gov</div></td></tr>
     <tr><td>Money still missing</td><td>The $0.8–3.8 billion range</td><td>News reports on West Seattle line costs, 2026 (West Seattle Herald, My Ballard)</td></tr>
    </tbody></table></div>
  </section>
  <section id="ab-warn" role="tabpanel" hidden>
   <h3>Please read before relying on these numbers</h3>
   <ul>
    <li><b>This is a prototype.</b> It was built only from public data, not with Sound Transit or the City of Seattle. It is not official advice.</li>
    <li><b>The price result is not very reliable.</b> It passed only some reliability checks. Read it as "no clear rise", not "prices fell".</li>
    <li><b>Buses are not included.</b> Travel times use walking and trains only, so the train's benefit may look bigger than it really is.</li>
    <li><b>The "money still missing" figure is not official.</b> It is a range from news reports. A firm agency figure would replace it.</li>
    <li><b>Legal points need a lawyer.</b> Sound Transit cannot charge homeowners itself; the City of Seattle would have to.</li>
    <li><b>Building heights are partly estimated.</b> About 2% are measured. The rest come from the number of floors, Microsoft's computer estimate, or a standard 6 m.</li>
    <li><b>The 3D trains are an illustration.</b> They do not follow the real timetable. They are drawn wider than real so they are easy to see, and they move faster when you zoom out.</li>
    <li><b>The West Seattle line's route is not final.</b> The dashed line simply joins the planned stations.</li>
    <li><b>The year slider shows today's track.</b> It only lights up stations and areas as they open; the lines themselves are always drawn.</li>
    <li><b>Where people live is approximate.</b> Household figures are averages for each neighbourhood, not for individual homes.</li>
   </ul>
  </section>
  <section id="ab-method" role="tabpanel" hidden>
   <p>From raw data to answer, step by step. Technical names are in grey.</p>
   <ol>
    <li><b>Collect the facts.</b> Every house sale in King County from 1995 to 2026, the date each Link station was paid for and opened, and the street and footpath network.</li>
    <li><b>Measure walking distance.</b> Walking time from every property to the nearest station, along real streets at 80 metres a minute. Under 10 minutes is "close"; 20–40 minutes is the comparison group; homes in between are left out.<div class="src">Network walking time with Dijkstra's shortest paths on the OpenStreetMap network</div></li>
    <li><b>Measure how much the train helped.</b> Jobs reachable within 45 minutes by walking and train, each year. The jump when a station opens is the "access gain".<div class="src">Cumulative-opportunity accessibility from LODES 2019 jobs; buses not modelled</div></li>
    <li><b>Compare before and after.</b> Price changes of close homes against comparison homes, before and after each station was funded. House size, age, condition and neighbourhood are accounted for, so like is compared with like.<div class="src">Difference-in-differences with staggered timing (Callaway and Sant'Anna 2021), doubly robust, not-yet-treated controls; 999-draw cluster bootstrap</div></li>
    <li><b>Turn it into a rate.</b> Each station's price change divided by its access gain: how much more homes are worth per unit of better access.<div class="src">Price elasticity with respect to accessibility, weighted across stations</div></li>
    <li><b>Test the result.</b> Seven checks, such as planting a fake price rise to see if the method finds it, and fake stations and dates where no effect should appear. The result passed only some.<div class="src">Falsification suite: planted effect, pre-trend bounds, placebo stations, placebo date, composition, leave-one-station-out, rezoning split</div></li>
    <li><b>Apply it to West Seattle.</b> The access gain from the two new stations, the value each nearby home would gain, and what a charge of 30–60% of that gain would raise over 20 years, in today's dollars. Repeated 10,000 times with different assumptions.<div class="src">Local improvement district and tax increment area revenue models; Monte Carlo simulation</div></li>
    <li><b>Decide.</b> The answer goes through six yes/no checks, in order: legal, enough data, a clear price rise, reliable, enough money (5% of the gap), fair to households. It stops at the first "no".<div class="src">Decision gates G0–G5</div></li>
    <li><b>Rules written down first.</b> All choices were locked before the results were seen, so they could not be bent. The one later change is recorded with its reason.<div class="src">Pre-analysis plan with a SHA-256 lock (docs/pre_analysis_plan.md, docs/decisions/)</div></li>
   </ol>
  </section>
  <section id="ab-credit" role="tabpanel" hidden>
   <h3>Data</h3>
   <ul>
    <li>Map data and background map © OpenStreetMap contributors, available under the Open Database License (ODbL).</li>
    <li>Building footprints © Microsoft, Global ML Building Footprints, available under the Open Database License (ODbL).</li>
    <li>Property sales, values and outlines: King County Department of Assessments and King County GIS Center, public records.</li>
    <li>Train timetables: Sound Transit open data.</li>
    <li>Jobs, blocks, income and home ownership: US Census Bureau (public domain).</li>
    <li>Washington laws: Washington State Legislature.</li>
   </ul>
   <h3>Software</h3>
   <ul>
    <li>Map: MapLibre GL JS 4.7.1 (BSD licence).</li>
    <li>Analysis: Python with pandas, GeoPandas, Shapely, NumPy, SciPy, DuckDB and pyosmium.</li>
   </ul>
   <h3>Who made this</h3>
   <p><b>Prepared by Venkatesh T, Geospatial Expert.</b></p>
   <p>A TransitCap v3 prototype for the Seattle Link corridor. The full method, results and decision records are in the project folder: docs/decision_memo.md, docs/pre_analysis_plan.md and docs/decisions/.</p>
  </section>
 </div>
</dialog>
<script>
const D=__DATA__, S=D.s, L=D.lid, YEARS=D.years;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const $=id=>document.getElementById(id);
const pct=(v,d=1)=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(d)+'%';
const money=v=>{const a=Math.abs(v),s=v<0?'−':'';return a>=1e9?s+'$'+(a/1e9).toFixed(2)+'B':a>=1e6?s+'$'+(a/1e6).toFixed(a>=1e8?0:1)+'M':s+'$'+Math.round(a/1e3)+'k';};
const usd=v=>'$'+Math.round(v).toLocaleString('en-US');
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

// ---------- summary panel
const nPass=S.tests.filter(t=>t.passed===true).length, nRun=S.tests.filter(t=>t.passed!==null).length;
$('verdict').innerHTML=`<b>Answer: no.</b> Charging homeowners near the new West Seattle stations would raise less than ${Math.ceil(100*S.lid.funding_ratio_median)}% of the money needed, because past stations did not clearly make nearby homes worth more.`;
$('kpis').innerHTML=[
 [pct(S.primary.estimate),'Change in home prices near past new stations: no clear rise'],
 [money(S.lid.pv_net_median),'Money a homeowner charge would likely raise, in today\'s dollars'],
 [(100*S.lid.funding_ratio_median).toFixed(1)+'%','Share of the missing money that would cover'],
 [(100*S.lid.p_material).toFixed(1)+'%','Chance it covers even 5% of the missing money']]
 .map(([v,l])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');
const mark=p=>p===true?'<span class="ok" aria-label="yes">✓</span>':p===false?'<span class="no" aria-label="no">✕</span>':'<span class="na" aria-label="could not run">–</span>';
const GATE_TEXT={
 G0:['Is it legal?',p=>p?'Yes, but the City of Seattle would have to set it up, not Sound Transit.':'No legal way found.'],
 G1:['Is there enough data to tell?',p=>p?'Yes, enough home sales to spot a price rise big enough to matter.':'No, too few home sales.'],
 G2:['Did homes near new stations go up in value?',p=>p?'Yes.':'No clear rise. This is where the checks stop.'],
 G3:['Is the price result reliable?',p=>p?'Yes.':`Not very: it passed only ${nPass} of ${nRun} reliability checks.`],
 G4:['Would it raise enough money to matter?',p=>p?'Yes.':`No: about ${(100*S.lid.funding_ratio_median).toFixed(1)}% of the money needed (5% would count).`],
 G5:['Would it be fair to households?',p=>p?`Yes: a typical household would pay about ${(100*S.burden.median).toFixed(1)}% of its income a year.`:'No: the charge is too heavy for some households.']};
let after=false;
$('gates').innerHTML=S.gates.map((g,i)=>{const stop=g.gate===S.decision_gate,cls=stop?' class="stop"':'',t=GATE_TEXT[g.gate];
 const note=after?' (for information only)':''; if(stop)after=true;
 return `<li${cls}><b>${i+1}</b>${mark(g.passed)}<span>${t[0]}<div class="why">${t[1](g.passed)}${note}</div></span></li>`;}).join('');
$('tests').innerHTML=S.tests.map(t=>`<li><b></b>${mark(t.passed)}<span>${esc(t.name)}<div class="why">${t.passed===true?'Passed':t.passed===false?'Failed':'Could not run: no records of past zoning changes'}</div></span></li>`).join('');
$('mcmed').textContent=`${money(S.lid.pv_net_median)}, or ${(100*S.lid.funding_ratio_median).toFixed(1)}% of the money needed`;

// ---------- tiny SVG helpers
const NS='http://www.w3.org/2000/svg';
function el(tag,attrs,parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;}
const tip=$('tip');
function showTip(html,x,y){tip.innerHTML=html;tip.hidden=false;const r=tip.parentElement.getBoundingClientRect(),w=tip.offsetWidth,h=tip.offsetHeight;
 let lx=x-r.left+14,ly=y-r.top+14; if(lx+w>r.width-8)lx=x-r.left-w-14; if(ly+h>r.height-8)ly=y-r.top-h-14; tip.style.left=Math.max(4,lx)+'px';tip.style.top=Math.max(4,ly)+'px';}
const svgTip=document.createElement('div');svgTip.id='svgtip';svgTip.style.cssText='position:fixed;pointer-events:none;background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:6px 8px;font-size:12px;box-shadow:0 2px 8px rgb(0 0 0/.18);z-index:9';svgTip.hidden=true;document.body.appendChild(svgTip);
function sTip(html,e){svgTip.innerHTML=html;svgTip.hidden=false;const w=svgTip.offsetWidth;svgTip.style.left=Math.min(e.clientX+12,innerWidth-w-8)+'px';svgTip.style.top=(e.clientY+12)+'px';}

// ---------- event study chart
(function(){const svg=$('es'),W=380,H=190,m={l:40,r:10,t:10,b:28},rows=S.event_study.map(r=>({e:r.e,v:100*Math.expm1(r.att),lo:100*Math.expm1(r.lo),hi:100*Math.expm1(r.hi),n:r.n_treated}));
 const xs=rows.map(r=>r.e),x0=Math.min(...xs)-0.5,x1=Math.max(...xs)+0.5,lo=Math.min(...rows.map(r=>r.lo),-1),hi=Math.max(...rows.map(r=>r.hi),1);
 const X=e=>m.l+(e-x0)/(x1-x0)*(W-m.l-m.r),Y=v=>m.t+(hi-v)/(hi-lo)*(H-m.t-m.b);
 const step=hi-lo>30?10:5;for(let v=Math.ceil(lo/step)*step;v<=hi;v+=step){el('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:v===0?css('--ink3'):css('--rule'),'stroke-width':1,'stroke-dasharray':v===0?'':'3 4'},svg);el('text',{x:m.l-6,y:Y(v)+4,'text-anchor':'end'},svg).textContent=(v>0?'+':'')+v+'%';}
 el('line',{x1:X(-0.5),x2:X(-0.5),y1:m.t,y2:H-m.b,stroke:css('--ink3'),'stroke-dasharray':'3 3'},svg);
 el('text',{x:X(-0.5)+4,y:m.t+10},svg).textContent='money committed';
 for(let e=Math.ceil(x0);e<=x1;e+=2)el('text',{x:X(e),y:H-m.b+14,'text-anchor':'middle'},svg).textContent=e;
 el('text',{x:(m.l+W-m.r)/2,y:H-2,'text-anchor':'middle'},svg).textContent='years after money for the station was committed';
 rows.forEach(r=>{const c=r.e<0?css('--ink3'):css('--s1');
  el('line',{x1:X(r.e),x2:X(r.e),y1:Y(r.lo),y2:Y(r.hi),stroke:c,'stroke-width':2,'stroke-linecap':'round'},svg);
  el('circle',{cx:X(r.e),cy:Y(r.v),r:4,fill:c,stroke:css('--panel'),'stroke-width':2},svg);
  const hit=el('rect',{x:X(r.e)-8,y:m.t,width:16,height:H-m.t-m.b,fill:'transparent'},svg);
  hit.addEventListener('pointermove',ev=>sTip(`<b>Year ${r.e}</b><br>Nearby homes: ${pct(r.v)} compared with homes farther away<br>Likely between ${pct(r.lo)} and ${pct(r.hi)}<br><span class="muted">From ${r.n.toLocaleString()} home sales near stations</span>`,ev));
  hit.addEventListener('pointerleave',()=>svgTip.hidden=true);});})();

// ---------- what-if model (same formulas as revenue/model.py at central values)
const P=D.parcels.features, af=L.rate/(1-Math.pow(1+L.rate,-L.payment_years));
const income={}; D.burden.features.forEach(f=>income[f.properties.bg]=f.properties.median_hh_income);
function gainTotal(eps){let B=0;for(const f of P){const p=f.properties;if(p.sf)B+=p.mv*Math.expm1(eps*p.dose);}return B;}
const pvOf=(eps,cap)=>L.K*cap*Math.max(gainTotal(eps),0);
const SF=P.filter(f=>f.properties.sf),DOSE=SF.reduce((a,f)=>a+f.properties.dose,0)/SF.length;
const rise=e=>100*Math.expm1(e*DOSE);  // price rise for a typical West Seattle home at this elasticity
const epsFor=r=>Math.log(1+r/100)/DOSE;
function breakEven(cap,gap){const tgt=L.threshold*gap;if(pvOf(1,cap)<tgt)return null;let a=0,b=1;for(let i=0;i<50;i++){const m=(a+b)/2;pvOf(m,cap)<tgt?a=m:b=m;}return b;}
const st={eps:S.elasticity.elasticity,cap:L.capture_median,gap:L.gap_median};
$('eps').value=st.eps;$('cap').value=st.cap;$('gap').value=st.gap/1e9;
const presets={est:S.elasticity.elasticity,open:S.eps_open,need:null};
document.querySelectorAll('.presets button').forEach(b=>b.onclick=()=>{let v=presets[b.dataset.eps];if(v===null)v=breakEven(st.cap,st.gap);if(v===null)return;st.eps=v;$('eps').value=v;update();});
['eps','cap','gap'].forEach(id=>$(id).addEventListener('input',()=>{st.eps=+$('eps').value;st.cap=+$('cap').value;st.gap=1e9*+$('gap').value;update();}));
let bgShare={};
function update(){
 $('eps-o').textContent=pct(rise(st.eps));$('cap-o').textContent=Math.round(100*st.cap)+'%';$('gap-o').textContent=money(st.gap);
 let B=0;const agg={};
 for(const f of P){const p=f.properties,g=p.mv*Math.expm1(st.eps*p.dose);p.gain=g;
  p.charge=p.sf?Math.max(g,0)*st.cap*(1+L.eta):0;p.annual=p.charge*af;
  if(p.sf){B+=g;const a=agg[p.bg]||(agg[p.bg]={n:0,s:0});a.n++;a.s+=p.annual;}}
 bgShare={};for(const k in agg)bgShare[k]=income[k]?agg[k].s/agg[k].n/income[k]:null;
 D.burden.features.forEach(f=>{const a=agg[f.properties.bg];f.properties.share=bgShare[f.properties.bg]??-1;f.properties.annual=a?a.s/a.n:0;});
 const pv=L.K*st.cap*Math.max(B,0),ratio=pv/st.gap,be=breakEven(st.cap,st.gap);
 $('r-pv').innerHTML=money(pv)+'<span class="unit">raised, in today\'s dollars</span>';
 $('r-ratio').textContent=`That covers ${(100*ratio).toFixed(1)}% of the ${money(st.gap)} still missing. It would need to cover ${(100*L.threshold).toFixed(0)}% to be worth doing (black mark).`;
 const scale=Math.max(0.15,ratio*1.1);$('r-bar').style.width=Math.min(100,100*ratio/scale)+'%';$('r-thr').style.left=(100*L.threshold/scale)+'%';
 $('r-need').textContent=be===null?'Even a huge price rise would not reach 5% with these settings.':`To reach 5%, nearby homes would need to rise about ${pct(rise(be),0)}. The study found about ${pct(rise(S.elasticity.elasticity),0)} (likely ${pct(rise(S.elasticity.lo),0)} to ${pct(rise(S.elasticity.hi),0)}).`;
 const shares=Object.values(bgShare).filter(v=>v!==null).sort((a,b)=>a-b),med=shares.length?shares[Math.floor(shares.length/2)]:0,mx=shares.length?shares[shares.length-1]:0;
 const charges=P.filter(f=>f.properties.sf).map(f=>f.properties.charge).sort((a,b)=>a-b),mc=charges[Math.floor(charges.length/2)]||0;
 $('r-hh').textContent=`A typical homeowner would pay ${usd(mc)} in total, or about ${usd(mc*af)} a year for ${L.payment_years} years. That is ${(100*med).toFixed(1)}% of a typical household's income (${(100*mx).toFixed(1)}% in the hardest-hit neighbourhood). Over 5% is too much.`;
 drawCurve(ratio,be);
 if(map.getSource('parcels')){map.getSource('parcels').setData(D.parcels);map.getSource('burden').setData(D.burden);}
}
let curveX=null;
function drawCurve(ratio,be){const svg=$('curve');svg.innerHTML='';const W=380,H=170,m={l:40,r:10,t:10,b:28},emax=0.15,N=60;
 const pts=[];for(let i=0;i<=N;i++){const e=emax*i/N;pts.push([e,100*pvOf(e,st.cap)/st.gap]);}
 const ymax=Math.max(10,Math.ceil(Math.max(...pts.map(p=>p[1]))/5)*5);
 const X=e=>m.l+e/emax*(W-m.l-m.r),Y=v=>m.t+(ymax-v)/ymax*(H-m.t-m.b);curveX=X;
 const stp=ymax>40?20:ymax>20?10:5;for(let v=0;v<=ymax;v+=stp){el('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:css('--rule'),'stroke-dasharray':'3 4'},svg);el('text',{x:m.l-6,y:Y(v)+4,'text-anchor':'end'},svg).textContent=v+'%';}
 for(let r=0;r<=rise(emax)+1e-9;r+=10)el('text',{x:X(epsFor(r)),y:H-m.b+14,'text-anchor':'middle'},svg).textContent='+'+r+'%';
 el('text',{x:(m.l+W-m.r)/2,y:H-2,'text-anchor':'middle'},svg).textContent='how much more homes near the new stations are worth';
 el('rect',{x:X(S.elasticity.lo),y:m.t,width:X(S.elasticity.hi)-X(S.elasticity.lo),height:H-m.t-m.b,fill:css('--s1'),opacity:.12},svg);
 el('line',{x1:m.l,x2:W-m.r,y1:Y(100*L.threshold),y2:Y(100*L.threshold),stroke:css('--critical'),'stroke-dasharray':'4 3','stroke-width':1.5},svg);
 el('text',{x:W-m.r,y:Y(100*L.threshold)-4,'text-anchor':'end'},svg).textContent='worth doing: 5%';
 const gd=el('defs',{},svg),lg=el('linearGradient',{id:'cg',x1:0,y1:0,x2:0,y2:1},gd);
 el('stop',{offset:'0%','stop-color':css('--s1'),'stop-opacity':.28},lg);el('stop',{offset:'100%','stop-color':css('--s1'),'stop-opacity':0},lg);
 const line='M'+pts.map(p=>X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1)).join('L');
 el('path',{d:line+`L${X(pts[pts.length-1][0])},${Y(0)}L${X(0)},${Y(0)}Z`,fill:'url(#cg)'},svg);
 el('path',{d:line,fill:'none',stroke:css('--s1'),'stroke-width':2,'stroke-linejoin':'round'},svg);
 [[S.elasticity.elasticity,'study result'],[S.eps_open,'best case']].forEach(([e,t],i)=>{el('line',{x1:X(e),x2:X(e),y1:m.t+12*i+12,y2:H-m.b,stroke:css('--ink3'),'stroke-width':1},svg);el('text',{x:X(e)+3,y:m.t+12*i+10},svg).textContent=t;});
 el('circle',{cx:X(st.eps),cy:Y(100*ratio),r:5,fill:css('--s1'),stroke:css('--panel'),'stroke-width':2},svg);
 const hit=el('rect',{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:'transparent'},svg),cross=el('line',{y1:m.t,y2:H-m.b,stroke:css('--ink2'),visibility:'hidden'},svg);
 hit.addEventListener('pointermove',ev=>{const r=svg.getBoundingClientRect(),e=Math.max(0,Math.min(emax,((ev.clientX-r.left)*W/r.width-m.l)/(W-m.l-m.r)*emax));
  cross.setAttribute('x1',X(e));cross.setAttribute('x2',X(e));cross.setAttribute('visibility','visible');
  const pv=pvOf(e,st.cap);sTip(`If homes are worth <b>${pct(rise(e))}</b> more<br>${money(pv)} raised, ${(100*pv/st.gap).toFixed(1)}% of the money missing`,ev);});
 hit.addEventListener('pointerleave',()=>{svgTip.hidden=true;cross.setAttribute('visibility','hidden');});
 hit.addEventListener('click',ev=>{const r=svg.getBoundingClientRect();st.eps=Math.round(1000*Math.max(0,Math.min(emax,((ev.clientX-r.left)*W/r.width-m.l)/(W-m.l-m.r)*emax)))/1000;$('eps').value=st.eps;update();});}

// ---------- map
const map=new maplibregl.Map({container:'map',center:[-122.24,47.53],zoom:9.9,minZoom:9,pitch:45,bearing:-10,maxPitch:70,attributionControl:{compact:true},
 style:{version:8,sources:{base:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,maxzoom:19,
 attribution:'© OpenStreetMap contributors · Buildings © Microsoft · King County · Sound Transit · US Census'}},layers:[{id:'bg',type:'background',paint:{'background-color':css('--surface')}},
 {id:'base',type:'raster',source:'base',paint:{'raster-saturation':-0.55,'raster-opacity':0.85}}]}});
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'top-right');
map.addControl(new maplibregl.ScaleControl({unit:'metric'}),'top-right');

// year state
const yr=$('year');yr.min=YEARS[0];yr.max=YEARS[YEARS.length-1];yr.step=1;yr.value=yr.max;
let year=+yr.value;
const jobs2026=D.grid.features.map(f=>f.properties.jobs[f.properties.jobs.length-1]).sort((a,b)=>a-b);  // before the per-year flattening below
const q=p=>jobs2026[Math.floor(p*(jobs2026.length-1))];
const roundNice=v=>{const m=Math.pow(10,Math.floor(Math.log10(Math.max(v,1))));return Math.round(v/m)*m;};
const JSTOPS=[0.2,0.4,0.6,0.8].map(p=>roundNice(q(p)));
const GSTOPS=[0.05,0.25,0.5,1,2], BSTOPS=[0.005,0.01,0.02,0.05];
// Year changes only swap paint expressions that read the per-year properties already on each
// cell (j1995…, g1995…); the GeoJSON is never re-sent, so the map keeps up with the slider.
D.grid.features.forEach(f=>{const p=f.properties,a=p.jobs[0];YEARS.forEach((y,i)=>{const v=p.jobs[i];p['j'+y]=v;p['g'+y]=a>0?+Math.log(v/a).toFixed(3):(v>0?3:0);});delete p.jobs;});
let pending=false;
function setYear(y){year=y;$('year-o').textContent=y;caption(y);if(theme!=='burden'&&theme!=='none')legend();
 if(!pending){pending=true;requestAnimationFrame(()=>{pending=false;yearPaint();});}}
function ringColour(y){const lit=(k)=>Object.entries(RING).flatMap(([r,[c]])=>[r,k?css(c):tint(css(c))]);
 return ['case',['<=',['get','open'],y],['match',['get','ring'],...lit(true),css('--neutral')],['<=',['get','fund'],y],['match',['get','ring'],...lit(false),css('--neutral')],css('--neutral')];}
function yearPaint(){if(!map.getLayer('grid'))return;const y=year;
 if(theme==='rings')map.setPaintProperty('grid','fill-extrusion-color',ringColour(y));
 if(theme==='jobs')map.setPaintProperty('grid','fill-extrusion-color',stepExpr('j'+y,JSTOPS,qr));
 if(theme==='gain')map.setPaintProperty('grid','fill-extrusion-color',stepExpr('g'+y,GSTOPS,qr,css('--rule')));
 map.setPaintProperty('grid','fill-extrusion-height',gridHeight());
 const simple=document.body.classList.contains('simple');
 map.setPaintProperty('st','circle-color',['case',['<=',['get','open_year'],y],simple?'#ffffff':['match',['get','kind'],'estimate',css('--s1'),'projection',css('--s2'),css('--ink2')],['<=',['get','fund_year'],y],css('--ink3'),css('--panel')]);
 map.setPaintProperty('st','circle-stroke-color',simple?['case',['==',['get','kind'],'projection'],css('--s2'),['<=',['get','open_year'],y],'#1f1f1d','#a8a7a1']:['match',['get','kind'],'estimate',css('--s1'),'projection',css('--s2'),css('--ink2')]);}
yr.addEventListener('input',()=>setYear(+yr.value));
let timer=null;const stop=()=>{clearTimeout(timer);timer=null;$('play').textContent='▶';};
$('play').onclick=()=>{if(timer)return stop();if(year>=YEARS[YEARS.length-1]){yr.value=YEARS[0];setYear(YEARS[0]);}$('play').textContent='❚❚';
 const tick=()=>{if(year>=YEARS[YEARS.length-1])return stop();yr.value=year+1;setYear(year+1);timer=setTimeout(tick,EVENTS[year]?1600:450);};timer=setTimeout(tick,450);};

function tint(hex){const n=parseInt(hex.slice(1),16),b=parseInt(css('--surface').slice(1),16),m=(s)=>Math.round(((n>>s)&255)*0.4+((b>>s)&255)*0.6);return '#'+((1<<24)|(m(16)<<16)|(m(8)<<8)|m(0)).toString(16).slice(1);}
const EVENTS={};D.stations.features.forEach(f=>{const p=f.properties;[['fund_year','funded'],['open_year','in service']].forEach(([k,w])=>{const y=p[k];if(y<9999)((EVENTS[y]||(EVENTS[y]={}))[w]||(EVENTS[y][w]=[])).push(p.name.replace(' (planned)',''));});});
const dl=document.createElement('datalist');dl.id='ticks';Object.keys(EVENTS).filter(y=>y>=YEARS[0]&&y<=YEARS[YEARS.length-1]).forEach(y=>{const o=document.createElement('option');o.value=y;dl.appendChild(o);});document.body.appendChild(dl);yr.setAttribute('list','ticks');
function caption(y){const e=EVENTS[y],next=Object.keys(EVENTS).map(Number).filter(v=>v>y&&v<=YEARS[YEARS.length-1])[0];
 const list=(w)=>e&&e[w]?`<b>${w==='funded'?'Money committed':'Trains start running'}:</b> ${e[w].length>3?e[w].length+' stations ('+e[w].slice(0,2).join(', ')+'…)':e[w].join(', ')}`:'';
 $('cap-y').innerHTML=e?[list('in service'),list('funded')].filter(Boolean).join(' · '):`Nothing changed in ${y}.${next?' Next change: '+next+'.':''}`;}
const RING={treated:['--s1','Under 10 min walk'],spillover:['--s2','10–20 min walk'],control:['--s3','20–40 min walk (used for comparison)'],planned_area:['--neutral','West Seattle (line not built yet)']};
const qr=['--q1','--q2','--q3','--q4','--q5'],orr=['--o1','--o2','--o3','--o4','--o5'];
const stepExpr=(prop,stops,ramp,below)=>['step',['get',prop],below??css(ramp[0]),...stops.flatMap((s,i)=>[s,css(ramp[i+(below?0:1)])])];
const fmtJobs=v=>v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?Math.round(v/1e3)+'k':String(v);
let theme='rings';
function legend(){const g=$('legend');let h='';
 if(theme==='rings')h='<b>Walking distance to the nearest station, '+year+'</b>'+[RING.treated,RING.spillover,RING.control].map(([c,t])=>`<div><span class="sw" style="background:${tint(css(c))}"></span><span class="sw" style="background:${css(c)}"></span>${t}</div>`).join('')+`<div><span class="sw" style="background:${css('--neutral')}"></span>No station planned or paid for yet</div><div class="muted">Pale: money committed, station being built. Full colour: trains running. West Seattle opens in 2035.</div>`;
 if(theme==='jobs')h=`<b>Jobs you can reach in 45 minutes, ${year}</b><div class="muted">By walking and train. Buses not included.</div><div class="ramp">${qr.map(c=>`<span style="background:${css(c)}"></span>`).join('')}</div><div class="ramp-l"><span>&lt;${fmtJobs(JSTOPS[0])}</span><span>${fmtJobs(JSTOPS[1])}</span><span>${fmtJobs(JSTOPS[2])}</span><span>&gt;${fmtJobs(JSTOPS[3])}</span></div>`;
 if(theme==='gain')h=`<b>Growth in jobs you can reach, 1995 to ${year}</b><div class="ramp">${qr.map(c=>`<span style="background:${css(c)}"></span>`).join('')}</div><div class="ramp-l"><span>+5%</span><span>+30%</span><span>+65%</span><span>×2.7</span><span>×7+</span></div><div class="muted">Grey: little or no change.</div>`;
 if(theme==='burden')h=`<b>Yearly charge as a share of household income</b><div class="muted">By neighbourhood, using the "Try it yourself" settings.</div><div class="ramp">${qr.map(c=>`<span style="background:${css(c)}"></span>`).join('')}</div><div class="ramp-l"><span>&lt;0.5%</span><span>1%</span><span>2%</span><span>5%+</span></div><div class="muted">More than 5% counts as too much.</div>`;
 if($('c-3d').checked&&theme!=='burden'&&theme!=='none')h+=`<div class="muted" style="margin-top:6px">Taller = more jobs reachable in ${year}. Flattens as you zoom in.</div>`;
 if($('c-bldg').checked)h+=`<div class="muted" style="margin-top:6px">Zoom in to see real buildings in 3D. Heights are real where known, estimated elsewhere.</div>`;
 if($('c-parcels').checked)h+=`<div style="margin-top:8px"><b>West Seattle homes: what each would be charged</b><div class="ramp">${orr.map(c=>`<span style="background:${css(c)}"></span>`).join('')}</div><div class="ramp-l"><span>$0</span><span>$5k</span><span>$15k</span><span>$40k+</span></div><div class="muted">Taller = bigger charge. Grey = not a house, not charged. Zoom in to see them.</div></div>`;
 if($('c-tia').checked)h+=`<div style="margin-top:6px"><span class="sw" style="background:transparent;border:2px solid ${css('--ink')}"></span>Tax-sharing zone: the law limits its size, so only ${S.tia.parcels.toLocaleString()} of ${S.tia.zone.toLocaleString()} nearby properties fit</div>`;
 g.innerHTML=h||'<span class="muted">Nothing shown</span>';g.hidden=!h;}
function applyTheme(){
 const vis=(id,on)=>map.getLayer(id)&&map.setLayoutProperty(id,'visibility',on?'visible':'none');
 vis('grid',['rings','jobs','gain'].includes(theme));vis('burden',theme==='burden');vis('burden-line',theme==='burden');
 yearPaint();
 vis('parcels',$('c-parcels').checked);vis('tia',$('c-tia').checked);vis('bldg',$('c-bldg').checked);
 if(map.getLayer('bldg'))map.setFilter('bldg',$('c-parcels').checked?['!=',['get','ws'],1]:null);legend();}
document.querySelectorAll('input[name=theme]').forEach(r=>r.addEventListener('change',()=>{theme=r.value;applyTheme();}));
['c-parcels','c-tia','c-bldg'].forEach(id=>$(id).addEventListener('change',applyTheme));
$('c-3d').addEventListener('change',()=>{applyTheme();if(map.getZoom()<12.5)map.easeTo({pitch:$('c-3d').checked?45:0,duration:800});});
// Blocks shrink to flat between zoom 11 and 12.5 so real buildings take over. Done in code
// because MapLibre evaluates zoom-and-data height rules per tile, not smoothly.
const gridFactor=()=>$('c-3d').checked?Math.round(20*Math.min(1,Math.max(0,(12.5-map.getZoom())/1.5)))/20:0;
let lastFactor=null;
function gridHeight(){lastFactor=gridFactor();return lastFactor?['*',['get','j'+year],lastFactor/100]:0;}
map.on('zoom',()=>{if(gridFactor()!==lastFactor&&map.getLayer('grid'))map.setPaintProperty('grid','fill-extrusion-height',gridHeight());});

map.once('style.load',()=>{  // not 'load': data must show even if basemap tiles are slow or fail
 setYear(year);
 map.addSource('grid',{type:'geojson',data:D.grid});
 map.addSource('burden',{type:'geojson',data:D.burden});
 map.addSource('lines',{type:'geojson',data:D.lines});
 map.addSource('parcels',{type:'geojson',data:D.parcels});
 map.addSource('st',{type:'geojson',data:D.stations});
 map.addLayer({id:'grid',type:'fill-extrusion',source:'grid',paint:{'fill-extrusion-opacity':0.82,'fill-extrusion-height':0}});
 map.addLayer({id:'burden',type:'fill',source:'burden',layout:{visibility:'none'},paint:{'fill-opacity':0.7,'fill-color':['case',['<',['get','share'],0],css('--neutral'),stepExpr('share',BSTOPS,qr)]}});
 map.addLayer({id:'burden-line',type:'line',source:'burden',layout:{visibility:'none'},paint:{'line-color':css('--panel'),'line-width':1.5}});
 map.addSource('bldg',{type:'vector',tiles:[location.href.replace(/[#?].*$/,'').replace(/[^/]*$/,'')+'buildings/{z}/{x}/{y}.pbf'],minzoom:12,maxzoom:14,bounds:D.bldg_bounds});
 map.addLayer({id:'bldg',type:'fill-extrusion',source:'bldg','source-layer':'b',minzoom:12,paint:{'fill-extrusion-color':css('--bldg'),
  'fill-extrusion-height':['interpolate',['linear'],['zoom'],12,0,13,['get','h']],'fill-extrusion-base':['interpolate',['linear'],['zoom'],12,0,13,['get','b']],'fill-extrusion-opacity':0.95}});
 const lw=(a,b)=>['interpolate',['linear'],['zoom'],9,a,13,b,16,a];  // thinner again close up so the 3D trains stand out
 // the two lines share track north of downtown: draw them side by side, like a subway map
 const off=['interpolate',['linear'],['zoom'],9,['match',['get','line'],'2 Line',2,'1 Line',-2,0],12,['match',['get','line'],'2 Line',3,'1 Line',-3,0],13.5,0];
 map.addLayer({id:'lines-case',type:'line',source:'lines',filter:['!',['has','planned']],layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#ffffff','line-width':lw(7,14),'line-offset':off}});
 map.addLayer({id:'lines',type:'line',source:'lines',filter:['!',['has','planned']],layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['get','color'],'line-width':lw(3,6),'line-offset':off}});
 map.addLayer({id:'planned-case',type:'line',source:'lines',filter:['has','planned'],layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':'#ffffff','line-width':lw(7,14)}});
 map.addLayer({id:'planned',type:'line',source:'lines',filter:['has','planned'],layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':css('--s2'),'line-width':lw(4,8),'line-dasharray':[1.2,1]}});
 map.addSource('trains',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
 map.addLayer({id:'parcels',type:'fill-extrusion',source:'parcels',minzoom:12,paint:{
  'fill-extrusion-color':['case',['==',['get','sf'],0],css('--neutral'),['interpolate',['linear'],['get','charge'],0,css('--o1'),5000,css('--o2'),15000,css('--o3'),40000,css('--o4'),100000,css('--o5')]],
  'fill-extrusion-height':['case',['==',['get','sf'],0],1,['+',3,['/',['get','charge'],400]]],'fill-extrusion-opacity':0.88}});
 map.addLayer({id:'tia',type:'line',source:'parcels',minzoom:12,filter:['==',['get','tia'],1],paint:{'line-color':css('--ink'),'line-width':1.2}});
 map.addLayer({id:'trains',type:'circle',source:'trains',maxzoom:13.5,filter:['==',['geometry-type'],'Point'],paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,4,13.5,7],'circle-color':['get','color'],'circle-stroke-color':'#ffffff','circle-stroke-width':2}});
 // Link trains are mostly white with a band in the line's colour: draw the band, then the white body above it
 map.addLayer({id:'trains3d',type:'fill-extrusion',source:'trains',minzoom:13.5,filter:['==',['geometry-type'],'Polygon'],paint:{'fill-extrusion-color':['get','color'],'fill-extrusion-base':0.5,'fill-extrusion-height':1.9,'fill-extrusion-opacity':1}});
 map.addLayer({id:'trains3d-top',type:'fill-extrusion',source:'trains',minzoom:13.5,filter:['==',['geometry-type'],'Polygon'],paint:{'fill-extrusion-color':'#f7f7f4','fill-extrusion-base':1.9,'fill-extrusion-height':4.4,'fill-extrusion-opacity':1}});
 map.addLayer({id:'st',type:'circle',source:'st',paint:{'circle-radius':['interpolate',['linear'],['zoom'],9,4.5,14,10],
  'circle-stroke-color':['match',['get','kind'],'estimate',css('--s1'),'projection',css('--s2'),css('--ink2')],'circle-stroke-width':['interpolate',['linear'],['zoom'],9,2,14,3]}});
 startTrains();
 setYear(year);update();applyTheme();
 if(document.body.classList.contains('simple'))setup(STEPS[step].set);  // the moving trains keep the map from ever going idle, so apply the story step here
 // hover
 const hoverable=['st','parcels','burden','grid'];
 map.on('mousemove',e=>{const f=map.queryRenderedFeatures(e.point,{layers:hoverable.filter(l=>map.getLayer(l)&&map.getLayoutProperty(l,'visibility')!=='none')})[0];
  map.getCanvas().style.cursor=f?'pointer':'';if(!f){tip.hidden=true;return;}const p=f.properties,o=e.originalEvent;
  if(f.layer.id==='st')showTip(stationHtml(p),o.clientX,o.clientY);
  else if(f.layer.id==='parcels'){const q=P.find(x=>x.properties.pin===p.pin)?.properties||p;
   showTip(`<b>Property near ${q.st==='WS1'?'Delridge':'Alaska Junction'} station</b><br>${Math.round(q.walk)} min walk · value today ${usd(q.av)}`+
    (q.sf?`<br>Extra value from the train: ${usd(q.gain)}<br>Charge: ${usd(q.charge)} in total, or ${usd(q.annual)} a year`:'<br><span class="muted">Not a house, so not charged here</span>')+(q.tia?'<br>Inside the tax-sharing zone':''),o.clientX,o.clientY);}
  else if(f.layer.id==='burden')showTip(`<b>Neighbourhood</b><br>Typical household income ${usd(p.median_hh_income)}<br>Typical yearly charge ${usd(p.annual)}<br>That is ${p.share<0?'n/a':(100*p.share).toFixed(1)+'%'} of income<br><span class="muted">${Math.round(100*p.owner_share)}% of homes are lived in by their owners</span>`,o.clientX,o.clientY);
  else {const ring=RING[p.ring]?.[1]||p.ring,g=+p['g'+year],status=p.open<=year?'Trains running':p.fund<=year?'Station being built':'No station yet';
   showTip(`<b>${ring}</b> · ${status}<br>${p.n} properties in this square<br>Jobs you can reach in 45 min (${year}): ${(+p['j'+year]).toLocaleString()}<br>${g>=3?'Many times more than in 1995':g<0.05?'About the same as in 1995':'×'+Math.exp(g).toFixed(1)+' compared with 1995'}`,o.clientX,o.clientY);}});
 map.on('mouseout',()=>tip.hidden=true);
 map.on('click','st',e=>select(e.features[0].properties.id,false));});

function stationHtml(p){
 if(p.kind==='estimate')return `<b>${p.name}</b> · trains since ${p.opened.slice(0,4)}<br>Nearby home prices: ${pct(p.value)}<br>Likely between ${pct(p.lo)} and ${pct(p.hi)}<br><span class="muted">From ${p.n.toLocaleString()} home sales nearby</span>`;
 if(p.kind==='projection')return `<b>${p.name}</b> · opens 2035<br>Expected extra value of nearby homes: ${money(p.gain_p50)}<br>Could be anywhere from ${money(p.gain_p10)} to ${money(p.gain_p90)}<br><span class="muted">${p.parcels.toLocaleString()} houses within a 10-minute walk</span>`;
 return `<b>${p.name}</b>${p.opened?' · trains since '+p.opened.slice(0,4):''}<br><span class="muted">${p.reason}</span>`;}
function rowLabel(p){
 if(p.kind==='estimate')return `<span class="num">${pct(p.value)}</span> <span class="muted num">(${pct(p.lo)} to ${pct(p.hi)})</span>`;
 if(p.kind==='projection')return `Expected extra home value <span class="num">${money(p.gain_p50)}</span> <span class="muted num">(${money(p.gain_p10)} to ${money(p.gain_p90)})</span>`;
 return `<span class="muted">${p.reason}</span>`;}
let pop=null;
function select(id,fly){const f=D.stations.features.find(x=>x.properties.id===id);if(!f)return;
 document.querySelectorAll('#rows tr').forEach(r=>r.setAttribute('aria-selected',r.dataset.id===id));
 if(pop)pop.remove();pop=new maplibregl.Popup({closeOnClick:true}).setLngLat(f.geometry.coordinates).setHTML(stationHtml(f.properties)).addTo(map);
 if(fly)map.easeTo({center:f.geometry.coordinates,zoom:Math.max(map.getZoom(),13)});}
const order={estimate:0,projection:1,none:2};
D.stations.features.slice().sort((a,b)=>order[a.properties.kind]-order[b.properties.kind]||a.properties.name.localeCompare(b.properties.name)).forEach(f=>{
 const p=f.properties,tr=document.createElement('tr');tr.dataset.id=p.id;tr.tabIndex=0;tr.innerHTML=`<td>${esc(p.name)}</td><td>${rowLabel(p)}</td>`;
 tr.onclick=()=>select(p.id,true);tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(p.id,true);}};$('rows').appendChild(tr);});

// views
function view(v){['corr','city','ws'].forEach(k=>$('v-'+k).setAttribute('aria-pressed',v===k));
 if(v==='city'){map.easeTo({center:[-122.333,47.603],zoom:14.6,pitch:60,bearing:-30,duration:1600});return;}
 if(v==='ws'){map.easeTo({center:[-122.374,47.5625],zoom:14.1,pitch:55,bearing:-25,duration:1600});}
 else map.easeTo({center:[-122.24,47.53],zoom:9.9,pitch:$('c-3d').checked?45:0,bearing:-10,duration:1200});}
$('v-corr').onclick=()=>view('corr');$('v-city').onclick=()=>view('city');$('v-ws').onclick=()=>view('ws');
$('year-o').textContent=year;update();
if(innerWidth<760)$('layers').open=false;

// ---------- place names, shown in both views
[['Downtown Seattle',-122.335,47.607],['University of Washington',-122.304,47.656],['Northgate',-122.328,47.703],['Lynnwood',-122.296,47.815],
 ['Bellevue',-122.196,47.612],['Redmond',-122.125,47.672],['Rainier Valley',-122.287,47.548],['Sea-Tac Airport',-122.300,47.444],['Federal Way',-122.313,47.316]]
 .forEach(([t,x,y])=>{const e=document.createElement('div');e.className='place';e.textContent=t;new maplibregl.Marker({element:e,anchor:'left',offset:[10,0]}).setLngLat([x,y]).addTo(map);});
(()=>{const e=document.createElement('div');e.className='place new';e.textContent='West Seattle · new line 2035';new maplibregl.Marker({element:e,anchor:'top',offset:[0,12]}).setLngLat([-122.372,47.563]).addTo(map);})();

// ---------- trains: dots that run back and forth along each line (skipped if the viewer prefers less motion)
function startTrains(){
 // Distances in metres along each line (equirectangular is accurate to well under 1% at this scale).
 const M=111320,K=Math.cos(47.6*Math.PI/180);
 const lines=D.lines.features.filter(f=>!f.properties.planned).map(f=>{const c=f.geometry.coordinates;let d=[0];
  for(let i=1;i<c.length;i++)d.push(d[i-1]+Math.hypot((c[i][0]-c[i-1][0])*M*K,(c[i][1]-c[i-1][1])*M));return {c,d,len:d[d.length-1],color:f.properties.color};});
 const at=(l,t)=>{t=Math.max(0,Math.min(l.len,t));let a=0,b=l.d.length-1;while(b-a>1){const m=(a+b)>>1;l.d[m]<t?a=m:b=m;}
  const f=(t-l.d[a])/((l.d[b]-l.d[a])||1);return [l.c[a][0]+(l.c[b][0]-l.c[a][0])*f,l.c[a][1]+(l.c[b][1]-l.c[a][1])*f];};
 // A Link train: 4 cars, each 29 m long and about 4 m tall; drawn 6 m wide (real: 2.7 m) so it reads on screen.
 const SPACING=4000,CARS=4,CAR=29,GAP=1.5,W=6,THREE_D=13.5;
 // Speed follows the zoom: about real speed (25 m/s, 90 km/h) close up, faster when zoomed out so the motion still shows.
 const speed=()=>Math.min(600,25*Math.pow(2,Math.max(0,15-map.getZoom())*0.9));
 let dist=0,prev=null;
 const still=matchMedia('(prefers-reduced-motion: reduce)').matches;let last=0;
 function car(l,front,back){const a=at(l,back),b=at(l,front),dx=(b[0]-a[0])*M*K,dy=(b[1]-a[1])*M,len=Math.hypot(dx,dy)||1;
  const ox=-dy/len*W/2/(M*K),oy=dx/len*W/2/M;
  return [[a[0]+ox,a[1]+oy],[b[0]+ox,b[1]+oy],[b[0]-ox,b[1]-oy],[a[0]-ox,a[1]-oy],[a[0]+ox,a[1]+oy]];}
 function frame(ts){
  if(prev!==null&&!still)dist+=Math.min(0.2,(ts-prev)/1000)*speed();prev=ts;
  if(ts-last>50&&map.getSource('trains')){last=ts;const close=map.getZoom()>=THREE_D,feats=[];
   lines.forEach(l=>{const n=Math.max(2,Math.round(2*l.len/SPACING));
    for(let i=0;i<n;i++){const pos=(dist+i*2*l.len/n)%(2*l.len),dir=pos<l.len?1:-1,s=pos<l.len?pos:2*l.len-pos;
     if(!close){feats.push({type:'Feature',properties:{color:l.color},geometry:{type:'Point',coordinates:at(l,s)}});continue;}
     for(let k=0;k<CARS;k++){const front=s-dir*k*(CAR+GAP),back=front-dir*CAR;
      feats.push({type:'Feature',properties:{color:l.color},geometry:{type:'Polygon',coordinates:[car(l,front,back)]}});}}});
   map.getSource('trains').setData({type:'FeatureCollection',features:feats});}
  if(!still)requestAnimationFrame(frame);}
 requestAnimationFrame(frame);}
D.lines.features.forEach(f=>{const p=f.properties,c=f.geometry.coordinates,pick={'1 Line':[-122.29,47.47],'2 Line':[-122.232,47.589]}[p.line];if(!pick)return;
 let best=c[0],bd=1e9;c.forEach(q=>{const dd=Math.hypot(q[0]-pick[0],q[1]-pick[1]);if(dd<bd){bd=dd;best=q;}});
 const e=document.createElement('div');e.className='lineb';e.style.background=p.color;e.textContent=p.line;new maplibregl.Marker({element:e,anchor:'right',offset:[-12,0]}).setLngLat(best).addTo(map);});

// ---------- simple view: a five-step story
const homes=P.filter(f=>f.properties.sf).length;
function setup(o){
 const r=document.querySelector(`input[name=theme][value=${o.theme}]`);if(r){r.checked=true;theme=o.theme;}
 $('c-3d').checked=!!o.blocks;$('c-bldg').checked=!!o.bldg;$('c-parcels').checked=!!o.parcels;$('c-tia').checked=false;
 if(o.year){yr.value=o.year;setYear(o.year);} applyTheme();
 document.body.classList.toggle('show-year',!!o.year&&!!o.yearbar);
 map.easeTo({...o.cam,duration:1600});}
const SW=(c)=>`<span class="sw" style="background:${css(c)}"></span>`;
const STEPS=[
 {t:'Where is this?',lede:'The train line, and the gap in the money.',big:money(L.gap_median),bigl:'still missing to build the West Seattle line (middle of a $0.8–3.8 billion range)',
  html:`<p>Seattle's light rail runs on two lines: the <b style="color:#28813F">green 1 Line</b> and the <b style="color:#007CAD">blue 2 Line</b>. The moving dots are trains. A <b>West Seattle</b> branch (dashed orange) is planned for 2035, but the money is short.</p><p>One idea: homeowners near the new stations pay a share, since a nearby station may raise their home's value.</p>`,
  set:{theme:'none',cam:{center:[-122.27,47.56],zoom:9.7,pitch:0,bearing:0}}},
 {t:'What was checked',lede:'Homes near new stations against homes farther away.',big:S.n_sales.toLocaleString(),bigl:'home sales from 1995 to 2026',
  html:`<p>Seattle has opened many stations since 2009. Did homes <b>close to a new station</b> gain more value than similar homes <b>farther away</b>?</p>
   <div class="key"><div>${SW('--s1')}Close: under 10 minutes' walk</div><div>${SW('--s2')}In between: 10–20 minutes</div><div>${SW('--s3')}Farther away: 20–40 minutes' walk</div><div>${SW('--neutral')}No station yet</div><div class="muted">Pale colours: station paid for and being built. White station circles: trains running.</div></div>
   <div class="hint">Press ▶ at the bottom of the map to watch the stations open year by year.</div>`,
  set:{theme:'rings',year:YEARS[0],yearbar:true,cam:{center:[-122.25,47.55],zoom:9.9,pitch:0,bearing:0}}},
 {t:'The result',lede:'No clear rise in home prices near new stations.',big:pct(S.primary.estimate),bigl:'change in the price of homes close to new stations, compared with homes farther away',
  html:`<p><b>Homes near new stations did not gain value.</b> If anything, they sold for slightly less than similar homes farther away.</p><p>The result passed only ${nPass} of ${nRun} checks, so the safe reading is <b>no clear rise</b>.</p><p class="muted" style="font-size:14px">The map shows today's network: blue areas are close to a station, green areas are the farther-away homes they were compared with.</p>`,
  set:{theme:'rings',year:YEARS[YEARS.length-1],cam:{center:[-122.25,47.55],zoom:9.9,pitch:0,bearing:0}}},
 {t:'What it would raise in West Seattle',lede:'A charge on nearby homes, added up.',big:money(S.lid.pv_net_median),bigl:`about ${(100*S.lid.funding_ratio_median).toFixed(1)}% of the money missing. It would need at least 5% to be worth doing.`,
  html:`<p>Each block on the map is one of the <b>${homes.toLocaleString()} homes</b> within a 10-minute walk of the two new stations. Taller blocks would pay more.</p><p>Added together, the charge raises very little, because the homes are not expected to gain much value.</p>`,
  set:{theme:'none',cam:{center:[-122.374,47.5625],zoom:14.1,pitch:55,bearing:-25},parcels:true,bldg:true}},
 {t:'Recommendation',lede:'Look for other money.',big:'No',bigl:"don't count on charging homeowners to pay for the West Seattle line",
  html:`<p>It would raise under 1% of the money needed, and past stations did not clearly raise nearby home values. Look for other funding.</p>
   <p class="muted" style="font-size:13px">Note: a prototype built from public data. Buses are not included. The missing-money figure comes from news reports. Legal points need a lawyer to confirm.</p>`,
  set:{theme:'none',cam:{center:[-122.30,47.58],zoom:10.6,pitch:0,bearing:0}}}];
let step=0;
function showStep(i){step=i;const k=STEPS[i];
 $('story').innerHTML=`<div class="frame"><div class="cardin"><div class="stepno">Step ${i+1} of ${STEPS.length}</div><div class="dots">${STEPS.map((_,j)=>`<span class="${j<=i?'on':''}"></span>`).join('')}</div>
  <h2>${k.t}</h2><p class="lede">${k.lede}</p><div class="bigbox"><div class="big">${k.big}</div><div class="bigl muted">${k.bigl}</div></div>${k.html}
  <div class="nav"><button id="s-back" ${i?'':'disabled'}>Back</button>${i<STEPS.length-1?'<button class="primary" id="s-next">Next</button>':'<button class="primary" id="s-detail">See the details</button>'}</div></div></div>`;
 $('s-back').onclick=()=>showStep(step-1); if($('s-next'))$('s-next').onclick=()=>showStep(step+1); if($('s-detail'))$('s-detail').onclick=()=>mode('detail');
 if(map.getLayer('grid'))setup(k.set);}
function mode(m){document.body.classList.toggle('simple',m==='simple');yearPaint();$('m-simple').setAttribute('aria-pressed',m==='simple');$('m-detail').setAttribute('aria-pressed',m!=='simple');
 if(m==='simple')showStep(step);else{document.body.classList.remove('show-year');theme='rings';document.querySelector('input[name=theme][value=rings]').checked=true;$('c-3d').checked=true;$('c-bldg').checked=true;$('c-parcels').checked=true;view('corr');applyTheme();}
 setTimeout(()=>map.resize(),0);}
const about=$('about');
$('about-btn').onclick=()=>about.showModal();$('ab-close').onclick=()=>about.close();
about.addEventListener('click',e=>{if(e.target===about)about.close();});
about.querySelectorAll('[role=tab]').forEach(t=>t.onclick=()=>{about.querySelectorAll('[role=tab]').forEach(x=>{const on=x===t;x.setAttribute('aria-selected',on);$(x.dataset.tab).hidden=!on;});});
$('m-simple').onclick=()=>mode('simple');$('m-detail').onclick=()=>mode('detail');
showStep(0);
</script></body></html>
"""
