# ADR-0004: Gate contents reconstructed from the spec's text

Status: accepted, 15 Nov 2026. Owner: project analyst; to be confirmed by the spec author.

The spec embeds a diagram ("decision protocol · 6 gates, 5 exits") whose content was not in the supplied file. The gates are rebuilt from the build plan and the three rules stated under the diagram:

| Gate | Week | Question | Exit |
|---|---|---|---|
| G0 | 1 | Is an instrument legally available to a sponsor? | No instrument: stop |
| G1 | 2–3 | Is the minimum detectable effect at or below the break-even effect? | Stop, or move to another corridor |
| G2 | 5–7 | Is there a precise answer? | Precise zero: reject value capture. Wide interval: return to G1 |
| G3 | 5–7 | Does the estimate survive falsification? | Not credible |
| G4 | 10 | Is P(funding ratio ≥ 5%) at least 50%? | Not material |
| G5 | 11 | Does the instrument transfer with acceptable incidence? | Not an exit: redesign, return to G4 |

These thresholds are policy choices fixed in `config/pap.yaml` before estimation:

- the 50% probability bar at G4;
- the 5% median income-share limit at G5;
- the ±2% band that counts as a "precise zero" at G2.

The spec author should confirm or replace them before the memo is used for a decision.
