# ADR-0002: Accessibility from the current timetable, walk and rail only

Status: accepted, 15 Nov 2026. Owner: project analyst.

## Decision

The treatment dose is the change in log jobs reachable within 45 minutes by walking plus Link, measured at the opening of the parcel's station. Jobs are LODES 8 (2019) at census-block points. Walking uses the OpenStreetMap street graph. Rail times come from Sound Transit's current GTFS feed (`SC-Fall-2026.6`), and each historical network is rebuilt by removing stations that had not yet opened.

## Deviations from the spec

| Spec | This build | Effect |
|---|---|---|
| R5 multimodal routing | Own walk + rail model (`build/access.py`) | No R5 or Java dependency; simpler to audit |
| Archived before and after timetables | Current timetable, masked by opening date | Historical headways and run times are not reproduced |
| Accessibility by transit | Buses not modelled | **The dose overstates the access gain** wherever good bus service existed before the station. Elasticities are per unit of rail-and-walk access, not total transit access |
| Year-specific jobs | Jobs fixed at 2019 | The dose isolates the network change; jobs moving because of the station do not enter it |

## Why

Openly archived GTFS for King County Metro and Sound Transit does not reach back to 2009. Getting R5 to run and checking it against these sources is more than the time budget allows. A transparent model with known biases beats an opaque one that cannot be checked.

## Consequences

- The transfer step multiplies the elasticity by the planned line's dose, which is computed the same way. The bus bias then partly cancels, because both sides omit buses.
- An R5 run with archived feeds is the first phase-2 upgrade.
