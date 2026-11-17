# ADR-0001: Seattle Link, King County assessor data, single-family sales

Status: accepted, 15 Nov 2026. Owner: project analyst (@Venkatesh).

## Decision

The completed corridor is Sound Transit Link light rail inside King County. The transfer target is the West Seattle Link Extension, with Delridge and Alaska Junction stations planned for 2035. The outcome is the log price of arm's-length single-family sales from the King County Assessor's sales extract, 1995–2026.

## Why

- The spec's default is Seattle. The user chose it, with a fallback to another city if the data proved incomplete. It did not need the fallback: parcel sales, assessed land and improvement values by year, parcel polygons and building characteristics are all open.
- Link has 11 opening cohorts in King County between 2009 and 2026, so staggered timing is real.
- Single-family sales come with building records (size, age, grade). Condominium sales would need the separate condo extracts, and their land split is unclear (the spec flags this). They are phase 2.

## Consequences

- Mountlake Terrace and Lynnwood City Center are in Snohomish County. They stay in the network for travel times, but no parcels near them are analysed.
- Building characteristics are the current snapshot. Sales of homes built or renovated after the sale date are dropped, because their recorded characteristics describe a different house.
- The parcel-use filter uses the current present-use code. A parcel that was single-family when sold and has since been redeveloped is excluded. This trims the sample; it does not bias it toward stations by design, but redevelopment is more common near stations. The composition check tests for this.
