import numpy as np
import pytest

from engine.spatial import Affine, bounds_transform, fit_affine, on_image

T = bounds_transform(-1000, -2000, 3000, 2000, width=800, height=800)  # 5 cm per pixel


def test_corners_and_axis_flip():
    # world +y is up; screen rows grow downward
    assert T.apply(-1000, 2000) == (0.0, 0.0)          # top-left
    assert T.apply(3000, -2000) == (800.0, 800.0)      # bottom-right
    px_low, py_low = T.apply(0, -1000)
    px_high, py_high = T.apply(0, 1000)
    assert px_low == px_high and py_high < py_low       # higher world y = higher on screen


def test_roundtrip_preserves_native_coordinates():
    x, y = 1234.5, -567.25
    px, py = T.apply(x, y)
    assert np.allclose(T.inverse(px, py), (x, y))


def test_missing_geometry_never_becomes_zero():
    assert T.apply(None, 5.0) == (None, None)
    assert not on_image(None, None, 800, 800)


def test_out_of_bounds_detected():
    assert on_image(*T.apply(0, 0), 800, 800)
    assert not on_image(*T.apply(5000, 0), 800, 800)   # east of the image
    assert not on_image(*T.apply(0, 9000), 800, 800)   # north of the image


def test_fit_recovers_rotation_and_reports_residuals():
    # a rotated, scaled, shifted image (e.g. a third-party minimap)
    th = np.deg2rad(90)
    true = Affine(np.cos(th) * 0.1, -np.sin(th) * 0.1, 400, np.sin(th) * 0.1, np.cos(th) * 0.1, 300)
    world = [(0, 0), (1000, 0), (0, 1000), (1000, 1000), (-500, 300)]
    pix = [true.apply(*w) for w in world]
    fit, res = fit_affine(world[:4], pix[:4])
    hold = np.hypot(*(np.array(fit.apply(*world[4])) - np.array(pix[4])))
    assert res.max() < 1e-6 and hold < 1e-6


def test_fit_rejects_collinear_landmarks():
    with pytest.raises(ValueError):
        fit_affine([(0, 0), (1, 1), (2, 2)], [(0, 0), (1, 1), (2, 2)])


def test_minimap_transform_swaps_axes(tmp_path, monkeypatch):
    """valorant-api calibration: image x comes from game y, image y from game x."""
    import json
    import numpy as np
    from PIL import Image
    from engine import minimaps

    img = np.zeros((1024, 1024, 4), np.uint8)
    img[100:900, 50:950] = (118, 118, 118, 255)
    Image.fromarray(img, "RGBA").save(tmp_path / "testmap.png")
    m = dict(displayName="Testmap", displayIcon="x", mapUrl="/Game/Maps/T", uuid="u",
             xMultiplier=7e-05, yMultiplier=-7e-05, xScalarToAdd=0.5, yScalarToAdd=0.6)
    (tmp_path / "valorant-api-maps.json").write_text(json.dumps({"data": [m]}))
    monkeypatch.setattr(minimaps, "SRC_DIR", tmp_path)
    monkeypatch.setattr(minimaps, "INDEX", tmp_path / "valorant-api-maps.json")

    im, t, asset = minimaps.build("testmap")
    x0, y0 = asset["crop"][:2]
    px, py = t.apply(1000.0, 2000.0)
    assert px == pytest.approx(1024 * (2000.0 * 7e-05 + 0.5) - x0)
    assert py == pytest.approx(1024 * (1000.0 * -7e-05 + 0.6) - y0)
    assert asset["third_party"] and not asset["official"]
    assert np.asarray(im)[0, 0, 3] == 0  # out-of-bounds stays transparent
