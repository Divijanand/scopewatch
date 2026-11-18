# Map calibration

## Coordinate spaces

| Space | Meaning | Where |
|---|---|---|
| `native_world` | GRID game units (cm), +y up; `z` only in the ability supplement | Stored unchanged in every table |
| `display_pixel` | Pixel on one specific outline image version | Computed on the fly; never stored over native values |
| `normalized_display` | `display_pixel / (width, height)` | Not needed yet |

## Transform

Each map has `config/maps/<map>-<version>.json` with a 2D affine `world_to_pixel` (`px = a·x + b·y + c`, `py = d·x + e·y + f`). The UI reads it from there and never recomputes it.

**Minimaps (current, version `minimap-va-<sha1 of the source image>`).** The calibration comes from valorant-api.com:

```
px = 1024 · (y · xMultiplier + xScalarToAdd) − crop_x
py = 1024 · (x · yMultiplier + yScalarToAdd) − crop_y
```

The axes are swapped: image x comes from game **y**. That's why the old outline, which put game x on the horizontal, looked rotated 90° from the in-game map.

**Outlines (fallback, version `outline-v1-b<bounds hash>`).** These are drawn on GRID's own bounds, so the transform is exact by construction.

`engine.spatial.fit_affine` (least squares, with residuals per landmark) is there for any image that has no published calibration.

## What is validated, and how

Every displayed image plus its transform is checked end to end against landmarks that never went into either:

- **Spike plant positions** (from objectives), and
- **Spawn positions at buy-phase start** (up to 20,000 sampled per map).

A landmark passes if it lands on floor (alpha > 0) within 4 px. A map is `validated` when at least 97% of both landmark sets pass, and `needs_review` otherwise. As a control, the same plants with the axes *not* swapped land on the floor 0–72% of the time.

## Results (2026-11-18, minimaps, parser 2.0.1)

| Map | Plants on floor | Spawns on floor | Status |
|---|---|---|---|
| bind | 98.46% | 99.2% | validated |
| all 12 others (abyss, ascent, breeze, corrode, fracture, haven, icebox, lotus, pearl, split, summit, sunset) | 100% | 100% | validated |

With the drawn outline, Summit failed (43.8% / 66.7%); it now passes. Exact counts are in each config file. Re-run with `python -m engine.maps`.

## Known limits

- **2D projection.** Elevated areas and the floor beneath them overlap. Only the supplement has `z`.
- **One image per map.** The minimap is the current layout. Games played before a layout change are drawn on the new layout; the landmark check would catch large shifts.
- **Minimap transparency.** Some boxes and objects are transparent on the minimap, so a kill line can cross a "hole" that is really a low box.
- **What landmarks prove.** A landmark on the floor shows the outline and transform agree with the data. It doesn't prove a sightline or that an area is reachable.
