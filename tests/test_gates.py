import yaml

from transitcap.decide import gates
from transitcap.paths import CONFIG

PAP = yaml.safe_load((CONFIG / "pap.yaml").read_text())


def _inputs(lo, hi, p_material=0.8, failed=False):
    legal = {"n_available": 2}
    be = {"corridor_can_answer": True, "mde_log_points": 0.02,
          "breakeven_att_completed_corridor": 0.05, "best_instrument": "lid"}
    est = {"primary": {"estimate": (lo + hi) / 2, "lo": lo, "hi": hi, "se": 0.01}}
    fals = [{"test": "planted_effect", "passed": not failed}, {"test": "rezoning_split", "passed": None}]
    inst = {"p_material": p_material, "funding_ratio_median": 0.1,
            "bankability_q10_by_year": [0.0, 0.5]}
    rev = {"best_instrument": "lid", "instruments": {"lid": inst},
           "tornado": [{"input": "gap", "low": 0.08, "high": 0.2, "swing": 0.12}],
           "incidence": {"median_annual_share": 0.01, "max_annual_share": 0.03}}
    return legal, be, est, fals, rev


def test_positive_precise_estimate_proceeds():
    r = gates.evaluate(PAP, *_inputs(0.02, 0.06))
    assert r["decision_gate"] is None and r["decision"] == "proceed to due diligence"


def test_precise_zero_rejects_at_g2():
    r = gates.evaluate(PAP, *_inputs(-0.01, 0.01))
    assert r["decision_gate"] == "G2" and "precise zero" in r["decision"]


def test_wide_interval_sends_back_to_g1():
    r = gates.evaluate(PAP, *_inputs(-0.05, 0.08))
    assert r["decision_gate"] == "G2" and "return to G1" in r["decision"]


def test_blocked_test_does_not_fail_g3_but_failed_test_does():
    assert gates.evaluate(PAP, *_inputs(0.02, 0.06))["gates"][3]["passed"] is True
    r = gates.evaluate(PAP, *_inputs(0.02, 0.06, failed=True))
    assert r["decision_gate"] == "G3"


def test_gates_after_first_exit_are_not_decision_relevant():
    r = gates.evaluate(PAP, *_inputs(-0.01, 0.01))
    rel = {g["gate"]: g["decision_relevant"] for g in r["gates"]}
    assert rel["G2"] and not rel["G3"] and not rel["G4"]
