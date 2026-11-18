"""Coordinate spaces and transforms.

Three spaces, never mixed:
  native_world        GRID game units (cm), x/y (+ z where the supplement has it). Never overwritten.
  display_pixel       pixels on a specific map image version
  normalized_display  display_pixel / image size, in [0, 1] when on the image

A transform is a 2D affine map world -> pixel:
  px = a*x + b*y + c
  py = d*x + e*y + f
For Scopewatch's data-drawn outlines it is exact by construction (scale + y-flip + offset).
`fit_affine` exists for any future third-party image, which would need landmark calibration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Affine:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def apply(self, x, y):
        """World -> pixel. None in, None out (missing geometry never becomes 0,0)."""
        if x is None or y is None:
            return None, None
        return self.a * x + self.b * y + self.c, self.d * x + self.e * y + self.f

    def inverse(self, px, py):
        det = self.a * self.e - self.b * self.d
        if abs(det) < 1e-12:
            raise ValueError("transform is not invertible")
        x = (self.e * (px - self.c) - self.b * (py - self.f)) / det
        y = (-self.d * (px - self.c) + self.a * (py - self.f)) / det
        return x, y

    def to_dict(self):
        return asdict(self)


def bounds_transform(min_x, min_y, max_x, max_y, width, height) -> Affine:
    """World bounds -> image with +y up in the world and rows growing downward on screen."""
    sx = width / (max_x - min_x)
    sy = height / (max_y - min_y)
    return Affine(a=sx, b=0.0, c=-min_x * sx, d=0.0, e=-sy, f=max_y * sy)


def fit_affine(world_pts, pixel_pts) -> tuple[Affine, np.ndarray]:
    """Least-squares affine from >= 3 non-collinear landmarks. Returns (transform, residuals_px)."""
    w = np.asarray(world_pts, dtype=float)
    p = np.asarray(pixel_pts, dtype=float)
    if len(w) < 3:
        raise ValueError("need at least 3 landmarks")
    A = np.column_stack([w[:, 0], w[:, 1], np.ones(len(w))])
    if np.linalg.matrix_rank(A) < 3:
        raise ValueError("landmarks are collinear")
    (a, b, c), *_ = np.linalg.lstsq(A, p[:, 0], rcond=None)
    (d, e, f), *_ = np.linalg.lstsq(A, p[:, 1], rcond=None)
    t = Affine(*(float(v) for v in (a, b, c, d, e, f)))
    pred = np.column_stack(t.apply(w[:, 0], w[:, 1]))
    return t, np.hypot(*(pred - p).T)


def on_image(px, py, width, height) -> bool:
    return px is not None and 0 <= px < width and 0 <= py < height
