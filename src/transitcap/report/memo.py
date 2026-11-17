"""Decision memo (about 2 pages), generated from outputs/results. Every claim cites its gate."""

import json

import numpy as np

from transitcap.paths import DOCS, OUTPUTS
from transitcap.report import figures

RES = OUTPUTS / "results"


def pct(x: float) -> str:
    """Log points to a signed percentage change."""
    return f"{100 * np.expm1(x):+.1f}%"


def share(x: float) -> str:
    return f"{100 * x:.1f}%"


def usd(x: float) -> str:
    return f"${x / 1e9:.2f} billion" if abs(x) >= 1e9 else f"${x / 1e6:.0f} million"


def write() -> None:
    figures.write_all()
    load = lambda n: json.loads((RES / n).read_text())  # noqa: E731
    g, est, fals, rev, be = (load("gates.json"), load("estimates.json"), load("falsification.json"),
                             load("revenue.json"), load("breakeven.json"))
    gates = {x["gate"]: x for x in g["gates"]}
    p, el, sp = est["primary"], est["elasticity"], est["spillover"]
    lid, tia = rev["instruments"]["lid"], rev["instruments"]["tia"]
    ft = {t["test"]: t for t in fals}
    sc = {x["spec"]: x for x in est["spec_curve"]}
    opened = sc["cohort date = open"]
    need = be["elasticity_needed"]["lid"]
    failed = gates["G3"]["evidence"]["failed"]
    passed = [t["test"].replace("_", " ") for t in fals if t["passed"] is True]
    material = lid["p_material"] >= 0.5
    best_el = max(el["hi"], opened["elasticity"] or -1)

    L: list[str] = []
    A = L.append
    A("# West Seattle value capture: " + ("material" if material else "not material") + "\n")
    A("Decision memo · 15 November 2026 · For: Sound Transit finance team · Prototype on open data; "
      "read the limits before relying on it.\n")

    A("## Decision\n")
    lead = ("Do not build the West Seattle funding plan around value capture on this evidence."
            if not material else "Value capture may be material; proceed to due diligence.")
    A(f"{lead} The pre-registered protocol stops at gate {g['decision_gate']}: {g['decision']}. "
      f"Every specification that yields an elasticity puts it below the {need:.3f} a local "
      f"improvement district needs to raise 5% of the funding gap; the highest point estimate or upper "
      f"bound is {best_el:.3f}. "
      f"The estimate behind the stop also fails {len(failed)} of the falsification tests, so read it "
      f"as \"no credible positive effect found\", not as proof that Link lowered prices.\n")

    A("## Why\n")
    A(f"- **No detectable price gain after funding was committed** [G2]. Homes within a 10-minute walk "
      f"of a new station sold for {pct(p['estimate'])} relative to homes 20–40 minutes away "
      f"(95% interval {pct(p['lo'])} to {pct(p['hi'])}; {est['n_treated_sales']:,} treated of "
      f"{est['n_sales']:,} sales; {est['n_clusters']} station clusters). The 10–20 minute ring moved "
      f"{pct(sp['estimate'])} ({pct(sp['lo'])} to {pct(sp['hi'])}).")
    A(f"- **The estimate is fragile** [G3]. Failed: {', '.join(t.replace('_', ' ') for t in failed) or 'none'}. "
      f"Passed: {', '.join(passed)}. Blocked: rezoning split (no zoning history). The planted-effect "
      f"interval covered the truth in {share(ft['planted_effect']['coverage'])} of runs (90% needed), so "
      f"the intervals here are too narrow. Pre-period coefficients move by up to "
      f"{100 * ft['pretrend_bounds']['max_pre_step']:.1f} points a year, so one base year can shift the "
      f"whole estimate.")
    A(f"- **The answer depends on which date counts as treatment** [G2]. Dated from announcement: "
      f"{pct(sc['cohort date = announce']['estimate'])}. Dated from opening: {pct(opened['estimate'])} "
      f"({pct(opened['lo'])} to {pct(opened['hi'])}). Central Link's surface construction ran between "
      f"funding and opening, which fits a dip followed by recovery.")
    A(f"- **Even the most favourable reading falls short** [G1, G4]. Elasticity: {el['elasticity']:.3f} "
      f"(95% interval {el['lo']:.3f} to {el['hi']:.3f}, from {el['k_stations']} stations); opening-dated "
      f"{opened['elasticity']:.3f}; needed {need:.3f}.")
    A(f"- **Revenue would be small** [G4]. Median present value of net LID revenue is "
      f"{usd(lid['pv_net_median'])}, {share(lid['funding_ratio_median'])} of the gap (80% range "
      f"{share(lid['funding_ratio_p10'])} to {share(lid['funding_ratio_p90'])}). Probability of reaching "
      f"5%: {share(lid['p_material'])}. LID payments start after the gain is realized, so in years 1–10 "
      f"they cover {share(max(lid['bankability_q10_by_year']))} of debt service at the 10th percentile.")
    A(f"- **The tax increment area is capped by law** [G0, G4]. RCW 39.114's $200 million limit per area "
      f"admits {rev['tia_area_parcels']:,} of the {rev['base']['zone_parcels']:,} parcels within a 10-minute "
      f"walk of the two stations. Its gross take would be {usd(tia['pv_gross_median'])} in present value; "
      f"{usd(tia['pv_net_median'])} of that is caused by the line. The rest is ordinary growth diverted "
      f"from schools, the county and other taxing districts.\n")

    A("![Effect on sale prices by year since funding commitment](../outputs/figures/event_study.png)\n")

    A("## What would change this conclusion\n")
    A(f"- **A stronger design showing an elasticity above {need:.3f}** [G1, G2]: archived timetables with "
      f"buses (the current dose omits them), condominium sales, and an averaged base period.")
    gap = next(t for t in rev["tornado"] if t["input"] == "gap")
    gap_needed = lid["pv_net_median"] / be["threshold"]
    A(f"- **A much smaller funding gap** [G4]. At the median LID revenue, the gap would have to be "
      f"below {usd(gap_needed)} for the ratio to reach 5%. Across the reported range ($0.8–3.8 billion) "
      f"the ratio runs only from {share(min(gap['low'], gap['high']))} to "
      f"{share(max(gap['low'], gap['high']))}, so a firm agency figure inside that range would not change "
      f"the answer.")
    A("- **A legal change** [G0]: Sound Transit gaining LID powers, or a higher TIA cap.\n")

    A("## Gates\n")
    A("| Gate | Question | Result |")
    A("|---|---|---|")
    for k in ("G0", "G1", "G2", "G3", "G4", "G5"):
        x = gates[k]
        tag = {True: "pass", False: "fail", None: "blocked"}[x["passed"]]
        note = "" if x["decision_relevant"] else " (after the stop; for information)"
        out = x["outcome"].replace("_", " ")
        A(f"| {k} | {x['question']} | {out if out.startswith(('pass', 'exit', 'redesign')) else tag + ': ' + out}{note} |")
    A("")

    A("## Limits\n")
    A("- Buses are not modelled, so the access gain is overstated (ADR-0002).")
    A(f"- Four of nine funding cohorts have enough sales a year to enter; the elasticity rests on "
      f"{el['k_stations']} stations (ADR-0006).")
    A("- Plan v2 added submarket terms after the planted-effect test exposed a bias; the v1 results are "
      "kept for comparison (ADR-0007).")
    A("- The funding gap is a reported range of $0.8–3.8 billion, not an agency figure (ADR-0005).")
    ls = rev["land_split"]
    A(f"- Land share of single-family value near the planned stations: {share(ls['assessor_median_land_share_sf'])} "
      f"by the assessor's split, {share(ls['vacant_sales_median_land_share_sf'])} from vacant-lot sales. The "
      f"second is implausibly low (vacant lots that sell are often steep or unbuildable), so the land-effect "
      f"percentages use the assessor's split. The dollar base does not depend on it: the whole gain is land.")
    A("- Legal points need counsel ([legal memo](legal_memo.md)).\n")
    A("**Ask:** send the agency's West Seattle funding-gap figure, and decide whether to fund the "
      "phase-2 design (archived timetables with buses, condominium sales) before value capture is "
      "reconsidered.\n")
    A("Go deeper: [pre-analysis plan](pre_analysis_plan.md) · `outputs/results/` · "
      "`outputs/atlas/index.html` · `docs/decisions/`.")
    (DOCS / "decision_memo.md").write_text("\n".join(L) + "\n")
