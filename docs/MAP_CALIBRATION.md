# Map calibration

## Coordinate spaces

| Space | Meaning | Where |
|---|---|---|
| `native_world` | GRID game units (cm), +y up; `z` only in the ability supplement | Stored unchanged in every table |
| `display_pixel` | Pixel on one specific outline image version | Computed on the fly; never stored over native values |
| `normalized_display` | `display_pixel / (width, height)` | Not needed yet |

## Transform

Each map has `config/maps/<map>-<version>.json` with a 2D affine `world_to_pixel` (`px = a·x + b·y + c`, `py = d·x + e·y + f`). The version is `outline-v1-b<hash of the map's GRID bounds>`.

The outline is drawn on a grid laid over GRID's own map bounds, so the transform is exact by construction: scale, y-flip and offset, with no fitting and no axis-swap risk. The UI reads the transform from this config rather than recomputing it.

`engine.spatial.fit_affine` (least squares, residuals per landmark) exists for any future third-party image. Unit tests cover rotation recovery, holdout error and rejection of collinear landmarks.

## What is validated, and how

The real risk with a data-drawn outline is the outline itself: missing floor, the wrong map version, a mis-flipped axis. So the **displayed image plus its transform** is checked end to end against landmarks that were **never used to draw it**:

- **Spike plant positions** (from objectives), and
- **Spawn positions at buy-phase start** (up to 20,000 sampled per map).

A landmark passes if it lands on drawn floor within 4 px (about 0.7 m). A map is `validated` when at least 97% of both landmark sets pass, and `needs_review` otherwise.

## Results (2026-11-17, parser 2.0.1)

| Map | Plants on floor | Spawns on floor | Status |
|---|---|---|---|
| abyss | 100% | 100% | validated |
| ascent | 100% | 99.94% | validated |
| bind | 98.57% | 98.75% | validated |
| breeze | 100% | 100% | validated |
| corrode | 100% | 100% | validated |
| fracture | 100% | 100% | validated |
| haven | 100% | 100% | validated |
| icebox | 100% | 100% | validated |
| lotus | 100% | 100% | validated |
| pearl | 100% | 99.94% | validated |
| split | 100% | 99.96% | validated |
| summit | 43.75% | 66.67% | **needs_review**: only 3 maps in the corpus; the UI shows a warning |
| sunset | 100% | 100% | validated |

Exact counts are in each config file. Re-run with `python -m engine.maps`.

## Known limits

- **2D projection.** Elevated areas and the floor beneath them overlap. Only the supplement has `z`.
- **Map versions are pooled.** All versions in the corpus that share GRID's bounds are pooled into one outline. A layout change between patches would blur, not split. Splitting by patch needs enough games per version.
- **What landmarks prove.** A landmark on the floor shows the outline and transform agree with the data. It doesn't prove a sightline or that an area is reachable.
