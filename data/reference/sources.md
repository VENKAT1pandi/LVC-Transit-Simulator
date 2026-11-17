# Reference sources for `station_milestones.csv`

Each milestone row cites one or more codes below. All were retrieved on 15 November 2026.

| Code | Source | Used for |
|---|---|---|
| W1 | Wikipedia, "List of Link light rail stations" (current stations table) | Opening dates of every station |
| W2 | Wikipedia, "1 Line (Sound Transit)" | Sound Move vote 5 Nov 1996; $500M federal grant agreement Oct 2003; SoDo groundbreaking 8 Nov 2003; Pinehurst funded in ST3 |
| W3 | Wikipedia, "University Link extension"; Sound Transit press release 15 Jan 2009 | FTA $830M share (Jan 2009); groundbreaking 6 Mar 2009 |
| W4 | Wikipedia, "Northgate Link extension" | ST2 approval 2008; construction began 2012 |
| W5 | Sound Transit news release "S. 200th Link extension groundbreaking, 04/26/13" | Angle Lake groundbreaking; 2011 TIGER-backed acceleration |
| W6 | Wikipedia, "2 Line (Sound Transit)" | ST2 Nov 2008; 2015 budget; Bellevue tunnel groundbreaking 22 Apr 2016; Downtown Redmond construction Oct 2019, TIFIA 2021 |
| W7 | Sound Transit news release (28 Dec 2018): FTA executed $1.17B FFGA on 19 Dec 2018; FHWA project profile: Lynnwood Link groundbreaking 3 Sep 2019 | Lynnwood Link funding and construction |
| W8 | Sound Transit Platform blog "Breaking ground on the Federal Way Link Extension" (16 Jul 2020); Sound Transit Agency Progress Report Jan 2020 (FFGA signing ceremony) | Federal Way Link |
| W9 | Wikipedia, "West Seattle Link Extension" | Planned stations, 2035 opening, ~$7B cost, ROD Apr 2025, Avalon removed May 2026 |
| W10 | OpenStreetMap via Overpass API: intersection nodes Delridge Way SW × SW Genesee St and California Ave SW × SW Alaska St | Planned station coordinates (approximate; the source names cross streets only) |

The ST2 vote date (4 Nov 2008) and ST3 vote date (8 Nov 2016) are the US general election days of those years; the sources above give the month only.

Coordinates for open stations are the mean of platform coordinates per parent station in Sound Transit GTFS feed `SC-Fall-2026.6` (`data/raw/gtfs/st_40_gtfs.zip`).

Rows marked `PROXY` in `funding_basis` use a substitute date because the true funding-commitment date could not be verified. The pre-analysis plan treats them as lower-quality cohort dates.
