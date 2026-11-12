# AIB World Vehicle Catalog — data attribution

## VehiclesDB
- File: `vehiclesdb-catalog.json`
- Upstream: https://github.com/vehiclesdb/vehiclesdb
- Snapshot: 2026.11.10
- License: CC BY 4.0
- Required visible credit: **Vehicle data by VehiclesDB** with a link to https://vehiclesdb.com
- Included kinds: car, truck, van, bus.
- This catalog is corroborated from official registers/type-approval catalogues in 18 countries. It is not a claim that every historical make/model ever manufactured is present. Missing records mean not yet catalogued.

## Open Tractor Data
- File: `tractor-brands.json`
- Upstream: https://github.com/tractordata-site/open-tractor-data
- License: CC BY 4.0
- Required attribution: **Source: TractorData.site — The Open Tractor Database** (https://tractordata.site)
- Included: farm-tractor manufacturer directory, recorded model counts and production-year ranges. The open file does not contain the full individual model-name list; AIB must not fabricate those names.

## Vehicle generations
- Upstream: https://github.com/gor3a/vehicle-makes-models
- Data license: ODbL 1.0 (see upstream LICENSE-DATA)
- Source basis: publicly available information compiled from autoevolution.com.
- Used lazily by manufacturer from `data/json/<make>.json`; actual generation names and year ranges are shown only when the source has a matching model.
- ODbL attribution and share-alike obligations apply to derivative database contents. This data source currently covers passenger-car makes/models/generations, not all construction/agricultural machinery.

## Heavy construction equipment
No complete, independently verified, openly licensed global make/model/generation dataset was identified for excavators, loaders, dozers, graders and related machinery in this update. Existing AIB curated options remain a partial fallback; they are not represented as exhaustive. Do not fill gaps with invented models or generic generation numbers.


## Heavy equipment manufacturer directory

Manufacturer names only were referenced from the public SpecCodex Excavators & Compaction directory: https://speccodex.com/grupa/bagger . This is not a redistributed model database and does not provide a complete historical model/generation list. Existing AIB model examples remain partial; missing model names are not fabricated.

## Tractor directory coverage

The updated `tractor-brands.json` contains all 334 manufacturer records in the upstream Open Tractor Data `data/brands.json` snapshot, including farm and lawn tractor categories. The source provides manufacturer-level model counts and year ranges, not the complete individual model-name records.
