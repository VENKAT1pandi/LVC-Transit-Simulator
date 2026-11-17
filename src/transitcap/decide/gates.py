"""Decision protocol: six gates ordered by cost (spec: Decision protocol).

The spec's diagram ("6 gates, 5 exits") was not included in the supplied document, so the gate
contents are reconstructed from its text and build plan (ADR-0004):

G0 Legal screen       exit: no legally available instrument and sponsor
G1 Data and power     exit: detectable effect larger than break-even -> stop or move corridor
G2 Primary estimate   exit: precise zero -> reject LVC; wide interval -> back to G1 (no answer)
G3 Falsification      exit: a falsification test fails -> estimate not credible
G4 Materiality        exit: probability of materiality below the pre-set level
G5 Transfer & design  failure loops back to G4 with a redesigned instrument (not an exit)
"""

from dataclasses import asdict, dataclass


@dataclass
class Gate:
    gate: str
    question: str
    passed: bool | None
    outcome: str
    evidence: dict


def evaluate(pap: dict, legal: dict, breakeven: dict, est: dict, fals: list[dict],
             rev: dict) -> dict:
    g = pap["gates"]
    gates: list[Gate] = []

    ok = legal["n_available"] > 0
    gates.append(Gate("G0", "Is a value-capture instrument legally available to a sponsor?", ok,
                      "pass" if ok else "exit: no legal instrument", legal))

    ok = bool(breakeven["corridor_can_answer"])
    gates.append(Gate("G1", "Can the corridor detect the break-even effect?", ok,
                      "pass" if ok else "exit: detectable effect exceeds break-even; stop or move corridor",
                      {"mde_log_points": breakeven["mde_log_points"],
                       "breakeven_att": breakeven["breakeven_att_completed_corridor"],
                       "best_instrument": breakeven["best_instrument"]}))

    p = est["primary"]
    hw = g["g2_precise_zero_halfwidth"]
    if p["lo"] > 0:
        ok, out = True, "pass: positive capitalization"
    elif -hw <= p["lo"] and p["hi"] <= hw:
        ok, out = False, "exit: precise zero; reject value capture on this evidence"
    elif p["hi"] < 0:
        ok, out = False, "exit: negative effect; reject value capture on this evidence"
    else:
        ok, out = False, "exit: interval too wide to answer; return to G1"
    gates.append(Gate("G2", "Is there a capitalization effect, and is the answer precise?", ok, out, p))

    failed = [t["test"] for t in fals if t.get("passed") is False]
    blocked = [t["test"] for t in fals if t.get("passed") is None]
    ok = not failed
    gates.append(Gate("G3", "Does the estimate survive the falsification suite?", ok,
                      "pass" if ok else f"exit: failed {', '.join(failed)}",
                      {"failed": failed, "blocked": blocked}))

    best = rev["best_instrument"]
    inst = rev["instruments"][best]
    ok = inst["p_material"] >= g["g4_min_probability_material"]
    top = rev["tornado"][0]
    thr = pap["materiality"]["threshold"]
    more_data = min(top["low"], top["high"]) < thr < max(top["low"], top["high"])
    flags = []
    if more_data:
        flags.append(f"collect more data on '{top['input']}': its range crosses the threshold")
    if inst["funding_ratio_median"] > g["g4_due_diligence_band"]:
        flags.append("above 30%: independent valuation, legal and governance due diligence required")
    gates.append(Gate("G4", "Is net revenue likely to be material to the funding plan?", ok,
                      "pass" if ok else "exit: not material", {"instrument": best, **inst,
                                                               "flags": flags}))

    bank = min(inst["bankability_q10_by_year"])
    inc = rev["incidence"]
    ok = inc["median_annual_share"] <= g["g5_max_median_income_share"]
    gates.append(Gate("G5", "Does the instrument transfer to the planned line with acceptable "
                            "incidence?", ok,
                      "pass" if ok else "redesign instrument and return to G4",
                      {"bankability_min_q10_ratio": bank, **inc}))

    decision = next((x for x in gates if x.passed is False), None)
    reached = []
    stop = False
    for x in gates:
        reached.append({**asdict(x), "decision_relevant": not stop})
        if x.passed is False and x.gate != "G5":
            stop = True
    return {"gates": reached,
            "decision_gate": decision.gate if decision else None,
            "decision": decision.outcome if decision else "proceed to due diligence"}
