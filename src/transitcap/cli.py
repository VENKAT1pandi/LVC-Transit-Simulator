"""Command line: `transitcap all` rebuilds every result from raw data in one command.

Order matters: power and break-even run before the plan is frozen; estimation refuses to run on
an unfrozen or edited plan.
"""

import argparse
import json
import time

from transitcap import config
from transitcap.paths import OUTPUTS, PROCESSED

STEPS = ["ingest", "build", "power", "freeze", "estimate", "falsify", "revenue", "decide", "report"]


def _legal() -> dict:
    import pandas as pd
    inst = pd.read_parquet(PROCESSED / "dim_lvc_instrument.parquet")
    avail = inst[inst.in_model == "yes"]
    return {"n_available": int(len(avail)), "instruments": avail.instrument_id.tolist(),
            "constraints": avail.key_limits.tolist()}


def run(step: str) -> None:
    t0 = time.time()
    if step == "ingest":
        from transitcap.ingest import buildings, osm, parcels
        parcels.fetch()
        if not (PROCESSED.parent / "interim" / "walk_edges.parquet").exists():
            osm.extract()
        if not (PROCESSED.parent / "interim" / "buildings.parquet").exists():
            buildings.extract()
    elif step == "build":
        from transitcap.build import tables
        tables.build_all()
    elif step == "power":
        from transitcap.estimate import run as est
        from transitcap.revenue import run as rev
        pap = config.load_pap()
        est.run_power(pap)
        base, _, _ = rev.planned_base(pap)
        rev.breakeven(pap, base)
    elif step == "freeze":
        print("plan sha256:", config.freeze())
    elif step == "estimate":
        from transitcap.estimate import run as est
        est.run_estimation(config.require_frozen())
    elif step == "falsify":
        from transitcap.estimate import run as est
        est.run_falsification(config.require_frozen())
    elif step == "revenue":
        from transitcap.revenue import run as rev
        rev.run_revenue(config.require_frozen())
    elif step == "decide":
        from transitcap.decide import gates
        pap = config.require_frozen()
        res = OUTPUTS / "results"
        load = lambda n: json.loads((res / n).read_text())  # noqa: E731
        out = gates.evaluate(pap, _legal(), load("breakeven.json"), load("estimates.json"),
                             load("falsification.json"), load("revenue.json"))
        (res / "gates.json").write_text(json.dumps(out, indent=2, default=float))
        print("decision:", out["decision"])
    elif step == "report":
        from transitcap.report import atlas, manifest, memo
        memo.write()
        atlas.write()
        manifest.write()
    print(f"[{step}] done in {time.time() - t0:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser(prog="transitcap")
    ap.add_argument("step", choices=STEPS + ["all"])
    a = ap.parse_args()
    for s in (STEPS if a.step == "all" else [a.step]):
        run(s)


if __name__ == "__main__":
    main()
