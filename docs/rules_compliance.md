# Repository rules compliance registry

Audit date: 15 November 2026  
Release: TransitCap v3 prototype 0.1.0 (Seattle Link, plan v2)

This registry records, for each supplied rule, whether the prototype in this repository meets it and where the evidence is. A rule is marked Verified only when the evidence is in the repository and was checked in this release. The prototype is a research build on open data. It is not a deployed service, a legal determination or a valuation.

## **1. Status definitions**

- **Verified.** Implemented and checked in the current release.
- **Partial.** Useful coverage exists, but the rule is not fully satisfied.
- **Deferred.** Required for a later production phase or external authorization.
- **Not applicable.** The current product does not contain the relevant capability.
- **Blocked.** Evidence or an accountable owner is unavailable.

## **2. Coverage**

Integrity check (generated): 343 rule rows, 343 unique IDs, no duplicates, every ID assessed.

| Prefix | Family | Rules | Verified | Partial | Deferred | Not applicable | Blocked |
|---|---|---:|---:|---:|---:|---:|---:|
| AS | Anti-Slop | 20 | 17 | 3 | 0 | 0 | 0 |
| FE | Frontend | 20 | 17 | 3 | 0 | 0 | 0 |
| WG | WebGIS | 20 | 14 | 4 | 0 | 2 | 0 |
| SQL | Spatial SQL | 20 | 11 | 5 | 0 | 4 | 0 |
| WGUI | WebGIS UI | 50 | 38 | 8 | 2 | 2 | 0 |
| DOC | Business documents | 60 | 54 | 2 | 1 | 3 | 0 |
| REPO | Production repository | 53 | 29 | 7 | 8 | 9 | 0 |
| DS | Data science | 50 | 35 | 6 | 0 | 9 | 0 |
| GEO | Geospatial | 50 | 33 | 5 | 0 | 12 | 0 |
|  | **Total** | **343** | **248** | **43** | **11** | **41** | **0** |

## **3. Anti-Slop rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| AS-01 | Start from a real brief | Verified | Built from the supplied spec; corridor, data and stack choices confirmed by the user before work began (ADR-0001). | None. |
| AS-02 | Make the first draft answer a question | Verified | Decision memo opens with the decision and the gate it rests on (`docs/decision_memo.md`). | None. |
| AS-03 | Use evidence before adjectives | Verified | Every memo claim carries a number from `outputs/results/*.json` and a gate tag. | None. |
| AS-04 | Ban unsupported claims | Verified | Legal claims cite RCW sections read on 15 Nov 2026; unverified dates are flagged PROXY in `station_milestones.csv`. | Counsel review of the legal memo. |
| AS-05 | Prefer specifics to templates | Verified | Memo names stations, statutes, dollar amounts and sale counts. | None. |
| AS-06 | Cut filler before polish | Verified | Memo is generated from results with no boilerplate sections; ADRs are one page each. | None. |
| AS-07 | Write for a human reader | Verified | Memos written for the agency finance team in plain sentences. | None. |
| AS-08 | Avoid borrowed authority | Verified | Authority comes from cited statute text and data, not from named institutions. | None. |
| AS-09 | Keep claims proportional | Verified | Memo states the estimate is not credible as an effect and limits conclusions to what the gates support. | None. |
| AS-10 | Show uncertainty honestly | Verified | Intervals on every estimate; Monte Carlo bands; specification curve; limits section in the memo. | None. |
| AS-11 | Make every visual earn its place | Verified | Four figures, each answering one question in the memo (`outputs/figures/`). | None. |
| AS-12 | Design for actual content | Verified | Atlas and figures built against the real results; station list sized for 41 stations. | None. |
| AS-13 | Use restraint as a feature | Verified | Atlas has one map, one list, one legend; no decorative elements. | None. |
| AS-14 | Respect accessibility | Partial | Atlas has a keyboard-operable station list doubling as a table view, focus styles, ARIA labels, light/dark tokens. No screen-reader test was run. | Test with a screen reader and axe. |
| AS-15 | Build unhappy paths | Partial | Contracts reject bad tables (`build/schemas.py`); unsnappable parcels get NaN, not a guess; the frozen-plan check raises. Atlas data layers load on style.load, so stations show even when basemap tiles fail; there is no visible message when they do. | Add a visible tile-failure notice. |
| AS-16 | Make every control functional | Verified | Every atlas control (list row, map point, zoom) does something; no dead controls. | None. |
| AS-17 | Keep comments informative | Verified | Comments explain why (e.g. infill rule in `build/rail.py`, IF caveat in `estimate/csdid.py`). | None. |
| AS-18 | Verify before delivery | Verified | 13 unit tests pass; `make all` rebuilt every result from raw data (`outputs/logs/make_all.log`); the atlas was rendered in headless Chrome at 1400 px and 420 px and inspected, which found and fixed three defects (basemap key, mislabelled stations, overclaiming headline). | None. |
| AS-19 | Review for sameness | Partial | Memo and atlas copy written for this corridor; no independent review for sameness. | Peer review of memo wording. |
| AS-20 | Preserve the creator's point of view | Verified | Spec's verdicts kept (frozen primary spec, gates, materiality); deviations recorded, not silently replaced. | None. |

## **4. Frontend rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| FE-01 | Design the job, not the screen | Verified | Atlas built for one job: see where Link changed prices and what West Seattle could gain. | None. |
| FE-02 | One primary action per view | Verified | One primary action: select a station (list or map). | None. |
| FE-03 | Let content determine structure | Verified | Layout is list + map because the content is 41 stations with one number each. | None. |
| FE-04 | First screen answers what, why, next | Verified | Atlas heading asks the question; first paragraph gives the headline estimate and interval; key explains what to do next. | None. |
| FE-05 | Treat interface copy as design | Verified | Copy states sources, comparison group and how to read an interval that includes zero. | None. |
| FE-06 | Avoid interchangeable copy | Verified | Copy is specific to Link and King County sales. | None. |
| FE-07 | Use deliberate visual direction | Verified | Restrained grey basemap, two semantic colours (estimate, projection). | None. |
| FE-08 | Create hierarchy through contrast | Verified | Hierarchy by weight and ink tokens; secondary text muted. | None. |
| FE-09 | Use a limited type system | Verified | One system font stack; three sizes (18, 14, 12-13 px). | None. |
| FE-10 | Give color a job | Verified | Blue = estimate, orange = planned projection; colour never carries identity alone (labels in list). | None. |
| FE-11 | Define tokens before components | Verified | CSS custom properties defined first (`report/atlas.py` template). | None. |
| FE-12 | Build with spacing rhythm | Verified | 8 px spacing unit used throughout the atlas. | None. |
| FE-13 | Design interactive states | Verified | Hover, focus-visible and selected states on list rows; cursor change on map points. | None. |
| FE-14 | Make keyboard use first-class | Verified | List rows are focusable and respond to Enter/Space. | None. |
| FE-15 | Meet accessibility from the start | Partial | Semantic table, ARIA region labels, reference-palette colours. No WCAG audit run. | Run an automated and manual WCAG 2.2 AA check. |
| FE-16 | Make motion purposeful | Verified | Only motion is the map ease to the selected station. | None. |
| FE-17 | Optimize perceived performance | Partial | Data inlined so the list renders before tiles; no measurement taken. | Measure load on a throttled connection. |
| FE-18 | Design the incomplete product | Verified | Stations with no estimate say why (excluded or no projection). | None. |
| FE-19 | Use familiar patterns | Verified | Standard web-map pattern: list, map, popup, zoom control, scale bar. | None. |
| FE-20 | Test real devices and content | Partial | Rendered against real data at desktop and phone widths in headless Chrome; no physical-device test. | Test on a phone and a desktop browser. |

## **5. WebGIS rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| WG-01 | Start with the geographic question | Verified | Geographic question stated in the atlas heading. | None. |
| WG-02 | Make the map the primary workspace | Verified | Map takes the main area; list is a side panel. | None. |
| WG-03 | Provide a meaningful default view | Verified | Default view frames King County Link from Northgate to Federal Way. | None. |
| WG-04 | Preserve map context | Verified | Selecting a station keeps the map and list in view; popup does not navigate away. | None. |
| WG-05 | Use a restrained basemap | Verified | Desaturated CARTO light basemap. | None. |
| WG-06 | Use semantic symbology | Verified | Point colour by kind (estimate/projection/none); rings as light fill. | None. |
| WG-07 | Normalize choropleths | Not applicable | No choropleth: values are station-level effects, not area totals. | None. |
| WG-08 | Respect scale, projection, and precision | Verified | Distances in UTM 10N metres; display in Web Mercator only; values rounded to 0.1%. | None. |
| WG-09 | Make layer control understandable | Verified | Two layers (stations, rings), both explained in the key and footnote. | None. |
| WG-10 | Limit active layers | Verified | Two active layers. | None. |
| WG-11 | Use scale-dependent detail | Partial | Point radius scales with zoom; no generalisation of ring polygons by scale. | Simplify ring hulls at low zoom. |
| WG-12 | Make popups analytical | Verified | Popups give effect, interval, sale count, access gain, cohort and opening date. | None. |
| WG-13 | Keep selection consistent | Verified | Same station selected in list and map; selected row and point highlighted together. | None. |
| WG-14 | Design coherent filters | Not applicable | No filters: 41 stations fit in one list. | None. |
| WG-15 | Treat time explicitly | Verified | Each station shows its funding cohort and opening date; effects are post-period averages. | None. |
| WG-16 | Distinguish blank, zero, missing, and failed | Verified | Excluded stations labelled as such; intervals including zero explained; missing projection stated. | None. |
| WG-17 | Support touch and precise selection | Partial | Map points enlarge with zoom; list offers precise selection. Touch not tested. | Test touch targets on a phone. |
| WG-18 | Build for keyboard and screen readers | Partial | List is the keyboard/screen-reader path; map canvas itself is not accessible. | Screen-reader test. |
| WG-19 | Make exports and citations usable | Partial | Atlas footnote points to the manifest with hashes; no export button. | Add CSV download of station table. |
| WG-20 | Test real geospatial workloads | Verified | Run on 326,044 real parcels and 1.46 M-node walk graph. | None. |

## **6. Spatial SQL rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| SQL-01 | Inspect before querying | Verified | Assessor extracts profiled in DuckDB before cleaning (code distributions, year coverage; recorded in ADR-0001 and the plan). | None. |
| SQL-02 | Treat a location as geometry, not two numbers | Partial | Parcels stored as point geometry in GeoParquet; stations kept as lat/lon columns plus geometry in `dim_station`. | None needed for the prototype. |
| SQL-03 | Type geometry columns fully | Partial | GeoParquet carries CRS (EPSG:32610 parcels, EPSG:4326 stations); no database typmods because no spatial database is used. | Typed columns if PostGIS is adopted. |
| SQL-04 | Know the difference between geometry and geography | Verified | All measurement in projected UTM metres; no geography type needed. | None. |
| SQL-05 | Never measure in degrees | Verified | No distance in degrees anywhere; walk times from metric graph. | None. |
| SQL-06 | Do not use Web Mercator for measurement | Verified | Web Mercator used for display only (`paths.py`). | None. |
| SQL-07 | Keep one SRID per spatial predicate | Verified | All spatial operations in EPSG:32610. | None. |
| SQL-08 | Store an indexed projected copy for repeated analysis | Not applicable | No spatial database; projected copy is the stored copy. | None. |
| SQL-09 | Create spatial indexes on filtered and joined columns | Not applicable | Spatial queries use in-memory KD-trees (scipy) rather than database indexes. | None. |
| SQL-10 | Use index-friendly predicates | Not applicable | No spatial SQL predicates. | None. |
| SQL-11 | Use a two-stage filter-and-refine pattern | Verified | Parcel fetch filters by tile envelope, then exact walk-network distance refines rings. | None. |
| SQL-12 | Choose predicates deliberately | Verified | Envelope intersects for fetch; network distance for rings; nearest point for snapping. | None. |
| SQL-13 | Validate geometries at ingestion and after transformation | Verified | Invalid polygons repaired with buffer(0) and counted (503) in `build_log.json`. | None. |
| SQL-14 | Deduplicate before merging or aggregating | Verified | Parcels deduplicated by PIN across tiles; value history deduplicated to one row per parcel-year by latest change date; duplicate keys rejected by contracts. | None. |
| SQL-15 | Keep analysis and serving geometries separate | Verified | Analysis uses UTM points; atlas serves WGS84 hulls. | None. |
| SQL-16 | Subdivide very large polygons for joins | Not applicable | No large-polygon joins. | None. |
| SQL-17 | Push reductions into the database | Verified | Filtering and aggregation of 2.4 M sales and 3.4 GB value history done in DuckDB. | None. |
| SQL-18 | Bound exploratory queries | Partial | Parcel fetch bounded by station buffers; exploratory queries not formally bounded. | None. |
| SQL-19 | Validate results with independent checks | Partial | Walk times checked against straight-line distance on known station pairs; rail times against timetable. | Compare a sample of walk times with an independent router. |
| SQL-20 | Use the query plan and retain the SQL | Partial | SQL retained in `build/tables.py`; no query plans inspected. | Inspect DuckDB plans if build time matters. |

## **7. WebGIS UI rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| WGUI-01 | Make the map self-evident | Verified | Heading states what the map shows; key explains both colours. | None. |
| WGUI-02 | Use obvious labels | Verified | Labels use station names and plain terms ("price effect", "projected value gain"). | None. |
| WGUI-03 | Make the primary task obvious | Verified | Primary task (pick a station) is the list and the map. | None. |
| WGUI-04 | Reduce choices to what matters | Verified | No filters, toggles or basemap switcher. | None. |
| WGUI-05 | Use familiar navigation | Verified | Standard zoom control, scale bar, click-to-select. | None. |
| WGUI-06 | Make clickable things look clickable | Verified | Rows and points change cursor and highlight on hover. | None. |
| WGUI-07 | Keep the path short | Verified | One click from page to station detail. | None. |
| WGUI-08 | Test with real users | Deferred | No user testing. | Test with two finance-team readers. |
| WGUI-09 | Make errors recoverable | Partial | Nothing destructive to undo; selection replaceable. No tile-failure recovery message. | Add tile-failure notice. |
| WGUI-10 | Prioritize scanning | Verified | List sorted by kind then name; effect column aligned with tabular numerals. | None. |
| WGUI-11 | Design for the user’s mental model | Verified | Model: stations with a number and a range, as finance readers expect. | None. |
| WGUI-12 | Make affordances visible | Verified | Rows and points look selectable. | None. |
| WGUI-13 | Use signifiers, not assumptions | Verified | Key, footnote and popups explain each mark. | None. |
| WGUI-14 | Constrain dangerous actions | Not applicable | No dangerous actions. | None. |
| WGUI-15 | Give immediate feedback | Verified | Selection highlights row and point and opens popup immediately. | None. |
| WGUI-16 | Show system status | Partial | No loading indicator for basemap tiles. | Add a loading state. |
| WGUI-17 | Map errors to understandable causes | Partial | No error messages exist beyond the browser's. | Add tile-failure message. |
| WGUI-18 | Make the right action easy | Verified | Selecting a station is the only action and the easiest. | None. |
| WGUI-19 | Prevent mistakes before they happen | Verified | Intervals shown next to every estimate to stop over-reading. | None. |
| WGUI-20 | Treat confusion as a design problem | Deferred | No confusion testing. | User test. |
| WGUI-21 | Start with a feature, not a layout | Verified | Built from the station feature outward. | None. |
| WGUI-22 | Establish visual hierarchy | Verified | Heading, headline, list, map. | None. |
| WGUI-23 | Use consistent spacing | Verified | 8 px grid. | None. |
| WGUI-24 | Use a limited type scale | Verified | Three sizes. | None. |
| WGUI-25 | Use color sparingly and semantically | Verified | Two semantic colours. | None. |
| WGUI-26 | Use a restrained palette | Verified | Reference palette slots 1-2 plus neutrals. | None. |
| WGUI-27 | Make secondary information quieter | Verified | Secondary text in muted ink. | None. |
| WGUI-28 | Separate groups with space | Verified | Groups separated by space. | None. |
| WGUI-29 | Use borders sparingly | Verified | Only row rules and panel edge. | None. |
| WGUI-30 | Create depth intentionally | Verified | No shadows except MapLibre popup. | None. |
| WGUI-31 | Design empty states well | Verified | Stations without numbers state why. | None. |
| WGUI-32 | Avoid cramming detail | Verified | Popup carries detail; list shows one value and range. | None. |
| WGUI-33 | Make destructive actions less prominent | Not applicable | No destructive actions. | None. |
| WGUI-34 | Systematize components | Partial | One template; no shared component library. | None. |
| WGUI-35 | Start mobile-first | Partial | Layout stacks map over list below 700 px; checked at 420 px in headless Chrome, not on a device. | Device test. |
| WGUI-36 | Use established map patterns | Verified | Popups, zoom, scale, list-map linking. | None. |
| WGUI-37 | Make navigation predictable | Verified | Single page; no navigation. | None. |
| WGUI-38 | Use progressive disclosure | Verified | Detail on selection only. | None. |
| WGUI-39 | Support both browsing and searching | Partial | Browse by list or map; no search box (41 items). | Add search if more corridors are added. |
| WGUI-40 | Let users compare | Partial | Stations compared in one list; no side-by-side view. | None. |
| WGUI-41 | Keep related controls together | Verified | All controls in the side panel. | None. |
| WGUI-42 | Make selection persistent and visible | Verified | Selected station stays highlighted in list and map. | None. |
| WGUI-43 | Provide multiple representations | Verified | Map, list (table) and popup text. | None. |
| WGUI-44 | Use modals sparingly | Verified | No modals. | None. |
| WGUI-45 | Design for interruption | Partial | Selection not persisted across reloads. | Store selected station in the URL hash. |
| WGUI-46 | Respect cognitive limits | Verified | One number and one range per row. | None. |
| WGUI-47 | Use recognition over recall | Verified | Station names visible; no codes to remember. | None. |
| WGUI-48 | Make similar things look similar | Verified | All estimates styled alike; all projections alike. | None. |
| WGUI-49 | Make important differences distinct | Verified | Estimates and projections differ in colour and in units (% vs $). | None. |
| WGUI-50 | Design for completion and closure | Verified | Popup gives a complete answer per station. | None. |

## **8. Business-document rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| DOC-01 | Decide the one message before writing | Verified | Memo's one message is in its title and first paragraph. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-02 | Put the answer first | Verified | Decision first, reasons after. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-03 | Build a pyramid, not a chronology | Verified | Memo ordered decision → why → what would change it → gates → limits. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-04 | Use the SCQ opening | Verified | Legal memo and plan open with situation and question; memo states the answer first. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-05 | Limit top-level points | Verified | Six reasons under 'Why'. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-06 | Group like with like | Verified | Reasons grouped by gate. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-07 | Order groups logically | Verified | Ordered by gate, cheapest first. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-08 | Make headings carry meaning | Verified | Headings are statements (e.g. 'Legal screen: two instruments pass, with a sponsor problem'). (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-09 | Make every subordinate idea support its parent | Verified | Every bullet supports the decision and cites a gate. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-10 | Separate facts from conclusions | Verified | Results (numbers) separated from conclusions; ADR-0006 separates observations from changes. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-11 | Use a question-driven structure | Verified | Plan organised around the two questions in §1. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-12 | State the gap | Verified | Memo states the gap between needed and estimated elasticity. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-13 | Avoid orphan evidence | Verified | Every number in the memo is interpreted. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-14 | Use an executive summary for long documents | Verified | Memo is the executive summary; plan and ADRs hold depth. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-15 | Use appendices for depth | Verified | Results JSON, ADRs and plan are the appendices. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-16 | Respect the reader’s time | Verified | Memo fits two pages. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-17 | Write a six-word-or-fewer headline | Verified | Memo headline is six words or fewer. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-18 | Open with the most important sentence | Verified | First sentence is the decision. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-19 | Add “why it matters.” | Verified | Each reason says why it matters for funding. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-20 | Provide a “go deeper” path | Verified | 'Go deeper' line links plan, results, atlas and decisions. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-21 | Write for one person | Verified | Written for the finance team lead. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-22 | Aim for one memorable takeaway | Verified | One takeaway: do not plan on value capture for West Seattle on this evidence. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-23 | Cut before you decorate | Verified | No decoration in memos. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-24 | Use short, active sentences | Verified | Short sentences, active voice. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-25 | Use formatting to guide scanning | Verified | Bold lead-ins, tables for gates. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-26 | Keep slides short | Not applicable | No slides were produced. | None. |
| DOC-27 | Use visuals to advance the story | Verified | One figure in the memo, the event study, advances the argument. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-28 | End with a takeaway | Verified | Memo ends with what would change the decision. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-29 | Write like a human | Verified | Plain register throughout. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-30 | Choose clarity over cleverness | Verified | No wordplay. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-31 | Cut every nonessential word | Verified | Generated memo has no filler phrases. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-32 | Use strong nouns and verbs | Verified | Verbs such as 'falls short', 'caps', 'measures'. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-33 | Avoid clichés | Verified | No clichés. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-34 | Maintain one voice | Verified | One voice across memos and ADRs. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-35 | Use concrete detail | Verified | Station names, statute sections, sale counts. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-36 | Read it aloud | Deferred | Not read aloud. | Read the memo aloud before circulation. |
| DOC-37 | Remove hedging | Verified | Hedges limited to stated uncertainty. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-38 | Make transitions useful | Verified | Transitions carry logic (e.g. 'Even the most favourable reading'). (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-39 | Say what you mean | Verified | Decision stated plainly. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-40 | Name the decision | Verified | Decision named in the first line. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-41 | Name the owner | Verified | Owners named in ADRs and README. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-42 | Do not hide bad news | Verified | Memo leads with the negative result and states test failures. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-43 | Avoid buzzword stacking | Verified | No buzzwords. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-44 | Eliminate empty openings | Verified | No throat-clearing openings. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-45 | Make the ask impossible to miss | Verified | Ask: do not build the funding plan around value capture; supply the agency's funding gap. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-46 | Use evidence, not assertion | Verified | Every claim backed by a result file. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-47 | Use plain English | Verified | Plain English; technical terms explained in the plan. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-48 | Avoid acronym overload | Verified | Acronyms limited (LID, TIA) and spelled out at first use. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-49 | Avoid false precision | Verified | Percentages to one decimal; elasticities to three; intervals given. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-50 | Respect the audience’s intelligence | Verified | No over-explanation of basics in the memo. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-51 | Know your purpose | Verified | Purpose stated in plan §1. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-52 | Know your audience | Verified | Audience stated at the top of each memo. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-53 | Front-load the message | Verified | Message in title and first line. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-54 | Use a logical document design | Verified | Consistent structure across memos. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-55 | Proofread for accuracy | Partial | Numbers are generated from results, so they cannot drift; prose not proofread by a second person. | Second-person proofread. |
| DOC-56 | Open with a human stake | Not applicable | Decision memo for a finance team; a human-stake opening would add length without information. | None. |
| DOC-57 | Use a story arc | Not applicable | Not a narrative piece. | None. |
| DOC-58 | Use one vivid example | Partial | Central Link construction dip is the one concrete example, in ADR-0006 rather than the memo. | None. |
| DOC-59 | Make the audience the protagonist | Verified | Finance team addressed as the decision maker. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |
| DOC-60 | End with forward motion | Verified | Memo ends with the steps that could change the answer. (`docs/decision_memo.md`, `docs/legal_memo.md`). | None. |

## **9. Production-repository rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| REPO-01 | Start with the domain, not the framework | Verified | Package modules follow the domain chain: ingest → build → estimate → revenue → decide → report. | None. |
| REPO-02 | Establish a ubiquitous language | Verified | Spec terms used in code: cohort, ring, dose, ATT(g,t), elasticity, gate, funding ratio. | None. |
| REPO-03 | Define bounded contexts | Verified | Contexts: estimation, revenue, decision, reporting, each a subpackage. | None. |
| REPO-04 | Document context boundaries | Partial | Boundaries described in README pipeline table; no context map document. | None. |
| REPO-05 | Model entities and value objects deliberately | Partial | Value objects as dataclasses (`Sample`, `CellResult`, `Aggregate`, `Base`, `Gate`). | None. |
| REPO-06 | Keep aggregates small and consistent | Not applicable | No transactional aggregates in an analysis pipeline. | None. |
| REPO-07 | Protect domain invariants | Verified | Invariants enforced: table contracts, frozen-plan hash, overlap rule and net ≤ gross tested. | None. |
| REPO-08 | Keep domain logic independent of infrastructure | Verified | Estimator, revenue model and gates are pure functions with no I/O (`csdid.py`, `model.py`, `gates.py`). | None. |
| REPO-09 | Use repositories for persistence boundaries | Partial | Parquet tables are the persistence boundary; no repository abstraction. | None. |
| REPO-10 | Use domain events for meaningful business facts | Not applicable | No event-driven system. | None. |
| REPO-11 | Refactor the model as understanding improves | Verified | Model refined during the build; changes recorded (ADR-0006). | None. |
| REPO-12 | Distill the core domain | Verified | Core domain is `estimate/csdid.py` and `revenue/model.py`. | None. |
| REPO-13 | Separate business rules from delivery mechanisms | Verified | Business rules independent of CLI (`cli.py` only orchestrates). | None. |
| REPO-14 | Point dependencies inward | Verified | Core modules import only numpy/pandas; adapters (ingest) depend on them, not the reverse. | None. |
| REPO-15 | Use adapters at the boundaries | Verified | External sources wrapped in `ingest/` adapters. | None. |
| REPO-16 | Keep controllers thin | Verified | CLI steps are a few lines each. | None. |
| REPO-17 | Use application services for orchestration | Verified | `estimate/run.py` and `revenue/run.py` orchestrate. | None. |
| REPO-18 | Prevent framework lock-in | Verified | No framework; plain Python packages. | None. |
| REPO-19 | Make boundaries testable | Verified | Pure modules unit-tested (`tests/`). | None. |
| REPO-20 | Keep the dependency graph understandable | Verified | Acyclic module graph. | None. |
| REPO-21 | Optimize for change over time | Verified | Each step re-runnable; plan changes forced through `refreeze`. | None. |
| REPO-22 | Make the codebase readable | Verified | Ruff clean; docstrings on every module. | None. |
| REPO-23 | Establish a single source of truth | Verified | One plan file (`config/pap.yaml`) and one milestone table drive every step. | None. |
| REPO-24 | Use small, reviewable changes | Deferred | No commits made in this session: the user did not ask for a commit. | Commit in reviewable steps. |
| REPO-25 | Require code review | Deferred | No reviewer available. | Review before use. |
| REPO-26 | Automate style and quality checks | Partial | Ruff configured (`make lint`); not run in CI. | Add CI. |
| REPO-27 | Test behavior, not implementation details | Verified | Tests check behaviour (effect recovered, cap respected, gates route correctly). | None. |
| REPO-28 | Keep tests fast and reliable | Verified | 13 tests run in about 5 s. | None. |
| REPO-29 | Document ownership | Verified | Owners named in README and ADRs. | None. |
| REPO-30 | Make onboarding easy | Verified | README gives a three-command start. | None. |
| REPO-31 | Use semantic versioning where appropriate | Verified | Package version 0.1.0. | None. |
| REPO-32 | Deprecate deliberately | Not applicable | Nothing deprecated yet. | None. |
| REPO-33 | Record decisions | Verified | Six ADRs in `docs/decisions/`. | None. |
| REPO-34 | Treat generated code as code | Not applicable | No generated code. | None. |
| REPO-35 | Manage every artifact as a versioned asset | Partial | Outputs hashed in the manifest; not versioned in an artifact store. | Archive outputs per release. |
| REPO-36 | Never rely on unpinned external dependencies | Verified | Every dependency pinned to an exact version in `pyproject.toml` and `uv.lock`; atlas pins MapLibre 4.7.1. | None. |
| REPO-37 | Use a private artifact repository | Deferred | No private artifact repository. | Mirror dependencies for production. |
| REPO-38 | Make builds reproducible | Partial | Pinned dependencies and seeded randomness; raw data downloads are dated snapshots, not frozen URLs. | Archive the raw snapshot with its hashes. |
| REPO-39 | Promote immutable artifacts | Deferred | No release process. | Define release artifacts. |
| REPO-40 | Scan artifacts continuously | Deferred | No dependency scanning. | Add pip-audit. |
| REPO-41 | Retain provenance | Verified | Raw file hashes, source URLs and retrieval dates recorded (`outputs/manifest.json`, `data/reference/sources.md`). | None. |
| REPO-42 | Apply retention policies | Deferred | No retention policy. | Set one with the data owner. |
| REPO-43 | Control repository access | Deferred | Local repository only. | Set access when hosted. |
| REPO-44 | Make every commit a release candidate | Deferred | No CI. | Add CI. |
| REPO-45 | Keep the pipeline fast | Not applicable | No pipeline beyond `make all`. | None. |
| REPO-46 | Use the same artifact across environments | Not applicable | No deployment environments. | None. |
| REPO-47 | Automate deployment | Not applicable | Nothing deployed. | None. |
| REPO-48 | Make releases reversible | Not applicable | Nothing released. | None. |
| REPO-49 | Manage configuration and secrets separately | Verified | No secrets used; all configuration in `config/pap.yaml`. | None. |
| REPO-50 | Monitor after release | Not applicable | Nothing deployed. | None. |
| REPO-51 | Preserve source, context, and output | Verified | Raw data, plan, code and outputs all retained and hashed. | None. |
| REPO-52 | Use durable formats and checksums | Verified | Parquet, CSV, JSON, Markdown; SHA-256 checksums. | None. |
| REPO-53 | Plan for continuity | Partial | README and ADRs let another analyst continue; no handover plan. | None. |

## **10. Data-science rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| DS-01 | Start with the decision, not the algorithm | Verified | Starts from the materiality decision; break-even computed before estimation. | None. |
| DS-02 | Perform exploratory data analysis first | Verified | Sales, codes, rings and doses profiled before estimation (ADR-0001, ADR-0006). | None. |
| DS-03 | Understand how the data was generated | Verified | Assessor sale codes and valuation timing documented; registered sales only. | None. |
| DS-04 | Use random sampling when appropriate | Not applicable | Full population of recorded sales used, not a sample. | None. |
| DS-05 | Distinguish population from sample | Verified | Population is arm's-length single-family sales; generalisation limits stated. | None. |
| DS-06 | Report uncertainty | Verified | Wild cluster bootstrap intervals; Monte Carlo ranges. | None. |
| DS-07 | Use experiments for causal claims | Partial | Quasi-experimental staggered design; no randomisation possible. Placebos stand in. | None. |
| DS-08 | Avoid confusing correlation with causation | Verified | Memo states the estimate is not credible as a causal effect. | None. |
| DS-09 | Control for confounders | Verified | Hedonic covariates, submarket-matched controls, doubly robust adjustment. | None. |
| DS-10 | Choose the right statistical test | Verified | Estimator chosen for staggered timing (spec upgrade 5). | None. |
| DS-11 | Correct for multiple comparisons | Partial | Event-time intervals are pointwise; no simultaneous bands. | Add sup-t bands. |
| DS-12 | Use regression to estimate and explain | Verified | Regression used for adjustment and elasticity. | None. |
| DS-13 | Validate model assumptions | Partial | Planted-effect simulation checks coverage; no residual diagnostics reported. | Report residual checks. |
| DS-14 | Do not trust R2R^2R2 alone | Not applicable | No R² reported or used. | None. |
| DS-15 | Use unsupervised learning for exploration, not proof | Not applicable | No unsupervised learning. | None. |
| DS-16 | Make statistics understandable | Verified | Effects reported as percentages with intervals. | None. |
| DS-17 | Question the denominator | Verified | Funding ratio denominator stated and justified (ADR-0005). | None. |
| DS-18 | Beware misleading averages | Partial | Medians and percentiles reported; averages over event time are the spec's aggregation. | None. |
| DS-19 | Do not treat a correlation as destiny | Verified | Elasticity treated as uncertain with transfer error. | None. |
| DS-20 | Beware cherry-picked comparisons | Verified | All pre-registered alternates reported in the specification curve. | None. |
| DS-21 | Ask who benefits from the framing | Verified | Gross vs net TIA revenue separated (net-new rule). | None. |
| DS-22 | Distinguish risk from uncertainty | Verified | Parameter ranges (risk) separated from model uncertainty (specification curve). | None. |
| DS-23 | Communicate absolute and relative effects | Verified | Revenue in dollars and as share of the gap. | None. |
| DS-24 | Use reproducible workflows | Verified | One command rebuilds every result (`make all`), seeds fixed. | None. |
| DS-25 | Separate raw and processed data | Verified | `data/raw` untouched; interim and processed separate. | None. |
| DS-26 | Document every transformation | Verified | Every filter in the plan and `build/tables.py`; build log counts. | None. |
| DS-27 | Validate data early | Verified | Table contracts checked before write. | None. |
| DS-28 | Use tidy data principles | Verified | Ten tables at declared grains. | None. |
| DS-29 | Use vectorized operations | Verified | Vectorised numpy throughout. | None. |
| DS-30 | Use exploratory notebooks, production modules | Verified | No notebooks; production modules only. | None. |
| DS-31 | Version data and code together | Verified | Manifest hashes raw data and code together. | None. |
| DS-32 | Handle missingness deliberately | Verified | Missing covariates filled with medians (documented); unsnappable parcels excluded, not imputed. | None. |
| DS-33 | Profile data continuously | Partial | Profiles run during the build; not automated per run. | Add a data-profile report step. |
| DS-34 | Define the ML task precisely | Not applicable | No machine-learning task. | None. |
| DS-35 | Choose a metric aligned to the decision | Verified | Funding ratio is the decision metric. | None. |
| DS-36 | Split data before leakage occurs | Not applicable | No predictive model. | None. |
| DS-37 | Prevent target leakage | Verified | Power calculation uses only non-post-treatment sales. | None. |
| DS-38 | Start with a simple baseline | Not applicable | No ML baseline. | None. |
| DS-39 | Use cross-validation properly | Not applicable | No cross-validation. | None. |
| DS-40 | Tune only after establishing a baseline | Not applicable | No tuning. | None. |
| DS-41 | Interpret models in context | Verified | Estimates interpreted against construction timing and bus omission. | None. |
| DS-42 | Evaluate fairness and bias | Verified | Block-group incidence table (charge as share of income). | None. |
| DS-43 | Plan for model drift | Not applicable | No deployed model. | None. |
| DS-44 | Keep humans in the loop where consequences are high | Verified | Memo says the decision needs the finance team, counsel and a better design. | None. |
| DS-45 | Design for failure | Verified | Pipeline fails loudly on contract or frozen-plan violations. | None. |
| DS-46 | Separate ingestion, storage, and serving | Verified | Ingest, processed storage and report outputs separate. | None. |
| DS-47 | Make pipelines idempotent | Verified | Cached raw pages and deterministic builds make reruns idempotent. | None. |
| DS-48 | Use schemas and contracts | Verified | Schemas in `build/schemas.py`. | None. |
| DS-49 | Monitor data quality and pipeline health | Partial | Build log records counts; no monitoring. | None. |
| DS-50 | Lead with the “so what.” | Verified | Memo leads with what it means for the funding plan. | None. |

## **11. Geospatial rules**

| ID | Requirement | Status | Evidence | Next action |
|---|---|---|---|---|
| GEO-01 | Define the geographic question first | Verified | Question stated in plan §1. | None. |
| GEO-02 | Choose the right spatial data model | Verified | Parcels as points, network as graph, rings as hulls. | None. |
| GEO-03 | Match resolution to the question | Verified | Parcel-level rings; 200 m job cells; 100 m access origins. | None. |
| GEO-04 | Know your coordinate reference system | Verified | CRS fixed in `paths.py`. | None. |
| GEO-05 | Use an appropriate projection | Verified | UTM 10N for King County. | None. |
| GEO-06 | Reproject deliberately | Verified | Explicit pyproj transforms. | None. |
| GEO-07 | Validate geometries before analysis | Verified | Polygons validated and repaired. | None. |
| GEO-08 | Clean topology before overlay | Not applicable | No polygon overlay. | None. |
| GEO-09 | Use metadata | Verified | Sources, dates and precision in `data/reference/sources.md`. | None. |
| GEO-10 | Assess positional accuracy | Partial | Station coordinates from GTFS; planned stations from cross streets (flagged approximate). | Replace with Sound Transit alignment. |
| GEO-11 | Assess attribute accuracy | Partial | Milestone precision recorded; PROXY dates flagged. | Verify proxy dates. |
| GEO-12 | Understand scale and generalization | Verified | Snap limit 150 m; 98.1% of nodes in the main component. | None. |
| GEO-13 | Use authoritative sources | Verified | County assessor, Sound Transit, Census, OSM. | None. |
| GEO-14 | Separate observation from interpretation | Verified | Observed network vs modelled access separated. | None. |
| GEO-15 | Version datasets and workflows | Verified | Manifest hashes. | None. |
| GEO-16 | Use GIS to support decisions, not merely to make maps | Verified | Map supports the materiality decision. | None. |
| GEO-17 | Combine layers only when they are compatible | Verified | All layers reprojected to UTM before joins. | None. |
| GEO-18 | Use geocoding carefully | Not applicable | No geocoding (parcels by PIN). | None. |
| GEO-19 | Use GPS/GNSS appropriately | Not applicable | No GNSS data. | None. |
| GEO-20 | Design field collection for real conditions | Not applicable | No field collection. | None. |
| GEO-21 | Maintain a single source of truth | Verified | Milestone table is the only station source. | None. |
| GEO-22 | Use spatial indexes | Verified | KD-trees for every nearest-neighbour search. | None. |
| GEO-23 | Design for interoperability | Verified | GeoParquet and GeoJSON outputs. | None. |
| GEO-24 | Preserve attribute integrity | Verified | PINs kept as 10-character text. | None. |
| GEO-25 | Build repeatable workflows | Verified | One-command pipeline. | None. |
| GEO-26 | Treat spatial SQL as analysis, not just extraction | Partial | Analysis done in Python graph code rather than spatial SQL. | None. |
| GEO-27 | Inspect spatial tables first | Verified | Tables profiled before use. | None. |
| GEO-28 | Use spatial predicates intentionally | Verified | Predicates chosen per task (envelope, network distance, nearest). | None. |
| GEO-29 | Use `ST_DWithin` for proximity | Not applicable | No spatial database; network distance used instead of ST_DWithin. | None. |
| GEO-30 | Do not measure in degrees | Verified | No degree measurements. | None. |
| GEO-31 | Keep spatial predicates CRS-consistent | Verified | All operations in one CRS. | None. |
| GEO-32 | Use a two-stage filter-and-refine pattern | Verified | Tile filter, then network refine. | None. |
| GEO-33 | Deduplicate before aggregation | Verified | PIN deduplication before aggregation. | None. |
| GEO-34 | Validate query results independently | Partial | Rail times checked against timetable; walk times against straight-line; no independent router check. | Cross-check with a router. |
| GEO-35 | Use query plans | Not applicable | No spatial SQL. | None. |
| GEO-36 | Use Python for reproducible geoprocessing | Verified | All geoprocessing in Python. | None. |
| GEO-37 | Keep functions small and testable | Verified | Small functions with tests for gates and revenue rules. | None. |
| GEO-38 | Test spatial logic with known cases | Partial | Spatial logic tested on known station pairs interactively, not in the test suite. | Add walk/rail tests with known pairs. |
| GEO-39 | Handle large data efficiently | Verified | 1.66 M segments handled with sparse graphs and chunked Dijkstra. | None. |
| GEO-40 | Avoid silent coordinate errors | Verified | Snap distances checked; unsnappable parcels set to NaN. | None. |
| GEO-41 | Preserve raw data | Verified | Raw data untouched. | None. |
| GEO-42 | Log processing lineage | Verified | Build log and manifest. | None. |
| GEO-43 | Understand the sensor before interpreting imagery | Not applicable | No imagery. | None. |
| GEO-44 | Apply atmospheric and radiometric correction when needed | Not applicable | No imagery. | None. |
| GEO-45 | Use ground truth | Not applicable | No remote sensing classification. | None. |
| GEO-46 | Quantify accuracy | Verified | Uncertainty quantified for every estimate. | None. |
| GEO-47 | Use change detection carefully | Not applicable | No change detection from imagery. | None. |
| GEO-48 | Use GeoAI as a tool, not an oracle | Not applicable | No GeoAI. | None. |
| GEO-49 | Document model provenance | Not applicable | No model artefacts beyond the estimator, documented in ADR-0003. | None. |
| GEO-50 | Design maps for comprehension, not decoration | Verified | Atlas designed for comprehension. | None. |

## **12. Release boundary**

The repository contains a research prototype. Its primary estimate fails four of the six runnable falsification tests, and the seventh (rezoning split) is blocked (see `docs/decision_memo.md`). It must not be described as a validated valuation model, a legal determination, a deployed service, or evidence that Link changed property values. Rules marked Deferred need a production phase, a reviewer, users or counsel that this build did not have.
