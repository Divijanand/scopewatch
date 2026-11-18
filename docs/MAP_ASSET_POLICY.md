# Map asset policy

## Decision

Scopewatch shows the **in-game minimaps**, using the world→minimap calibration from valorant-api.com (`engine/minimaps.py`), recoloured to the Scopewatch palette (D-009). The **original outline drawn from GRID positions** (`engine/maps.py`) is the fallback for any map without a minimap.

The minimaps are Riot Games artwork, used under Riot's fan-content policy ("Legal Jibber Jabber"). They're fetched into git-ignored `cache/` with `python -m engine.minimaps` and are never committed or redistributed. They're labelled unofficial.

The original policy (outlines only) was reversed on 2026-11-18. Analysts couldn't read the drawn outline, which was also rotated 90° from the in-game minimap.

## Sources checked (2026-11-17), in the priority order of the map-data spec

| # | Source | What we found | Used? |
|---|---|---|---|
| 1 | Riot Public Content Catalog, `PublicContentCatalog-release-08.09.zip` (valorant.dyn.riotcdn.net) | Official. HTTP HEAD: 509,672,170 bytes, last modified 2024-05-14. That predates Abyss (June 2024), Corrode and Summit, 3 of the 13 maps in the corpus, and Riot notes the catalog lags patches. | No. Not downloaded: stale for this corpus and 510 MB. |
| 2 | playvalorant.com media | Content-creator media; app-asset use not established | No |
| 3 | valorant-api.com `/v1/maps` (unofficial community API) | Minimap URLs plus per-map world→image multipliers for all 13 maps | **Yes, since 2026-11-18.** Images plus calibration; every map is checked against independent landmarks (MAP_CALIBRATION.md) |
| 4 | Original schematic | Drawn from the union of observed positions; walls are areas no player was ever recorded in | Fallback only |

## Rules

- No scraping of image search, wikis, VOD screenshots or tactics sites for production assets.
- If a third-party image is ever added, it gets its own `config/maps/<map>-<version>.json` with source URL, retrieval date, checksum, terms status and a landmark calibration (`engine.spatial.fit_affine`, holdout residuals). It's labelled unofficial when it is.
- Generated outlines are derived from licensed data, so the PNGs live in git-ignored `cache/`. Only transforms and aggregate calibration statistics are committed (`config/maps/`).
- Callout names and zone polygons aren't used yet. If added, they'll be versioned polygons with author and source, labelled as ours or community-provided, never "official".
