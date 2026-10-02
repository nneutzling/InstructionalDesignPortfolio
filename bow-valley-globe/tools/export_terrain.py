"""Cut one elevation tile per peak from NRCan's Canadian Digital Elevation Model and embed them in ../index.html.

    pip install rasterio scipy pyproj numpy
    python export_terrain.py

Reads only the Bow Valley window of the national CDEM (a cloud-optimised GeoTIFF), reprojects it to
UTM 11N at 20 m, then samples a square grid around each summit, turned so the viewer looks at the peak
from its best-known side. Rows run from the far side to the viewer's side; values are metres above sea level.

Source: Canadian Digital Elevation Model, Natural Resources Canada, Open Government Licence - Canada.
"""
import base64, json, pathlib, re

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from scipy.ndimage import map_coordinates

CDEM = "/vsicurl/https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/elevation/cdem-cdsm/cdem/cdem-canada-dem.tif"
BOX = (-116.05, 50.98, -115.02, 51.36)  # lon/lat: Lac des Arcs to Lake Louise
RES = 20      # metres per cell after reprojection
SIZE = 192    # grid points per tile side (about 30–40 m spacing; the CDEM itself is ~20 m)

# id: (approx lon, lat; summit search radius m; tile width m; bearing from peak toward viewer, deg;
#      tile centre shift in m to the viewer's right / toward the viewer)
PEAKS = {
    "yamnuska": (-115.1222, 51.1186, 700, 6000, 165, (-500, 0)),   # cliff seen from Highway 1A to the south
    "sisters":  (-115.3345, 51.0247, 2500, 7000, 330, (0, 0)),     # from Canmore
    "rundle":   (-115.4987, 51.1197, 2500, 8000, 315, (0, 0)),     # from Vermilion Lakes
    "cascade":  (-115.5664, 51.2236, 1500, 7000, 185, (0, 0)),     # from Banff Avenue
    "castle":   (-115.9256, 51.2958, 700, 7500, 225, (-800, 0)),   # from the Trans-Canada Highway
}


def load_dem():
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(CDEM) as d:
            w = from_bounds(*transform_bounds("EPSG:4326", d.crs, *BOX), d.transform).round_offsets().round_lengths()
            a = d.read(1, window=w).astype(np.float32)
            a[a == d.nodata] = np.nan
            src_t, src_crs = d.window_transform(w), d.crs
    ub = transform_bounds("EPSG:4326", "EPSG:32611", *BOX)
    dst = np.full((int((ub[3] - ub[1]) / RES), int((ub[2] - ub[0]) / RES)), np.nan, np.float32)
    reproject(a, dst, src_transform=src_t, src_crs=src_crs, dst_transform=from_origin(ub[0], ub[3], RES, RES),
              dst_crs="EPSG:32611", resampling=Resampling.bilinear, src_nodata=np.nan, dst_nodata=np.nan)
    return np.nan_to_num(dst, nan=1300), ub[0], ub[3]


def main():
    dem, x0, y0 = load_dem()
    fw = Transformer.from_crs("EPSG:4326", "EPSG:32611", always_xy=True)
    out = {}
    for key, (lon, lat, search, L, bearing, (shift_r, shift_t)) in PEAKS.items():
        x, y = fw.transform(lon, lat)
        c, r, n = int((x - x0) / RES), int((y0 - y) / RES), int(search / RES)
        sub = dem[r - n:r + n, c - n:c + n]
        rr, cc = np.unravel_index(np.argmax(sub), sub.shape)
        sx, sy = x0 + (c - n + cc) * RES, y0 - (r - n + rr) * RES
        a = np.radians(bearing)
        toward, right = np.array([np.sin(a), np.cos(a)]), np.array([-np.cos(a), np.sin(a)])
        cx, cy = np.array([sx, sy]) + right * shift_r + toward * shift_t
        g = np.linspace(-L / 2, L / 2, SIZE)
        V, U = np.meshgrid(g, g, indexing="ij")
        ex, ny = cx + U * right[0] + V * toward[0], cy + U * right[1] + V * toward[1]
        h = map_coordinates(dem, [(y0 - ny) / RES, (ex - x0) / RES], order=1)
        out[key] = dict(size=SIZE, extent=L, base=round(float(np.percentile(h, 3))), bearing=bearing,
                        h=base64.b64encode(np.clip(np.round(h), 0, 65535).astype("<u2").tobytes()).decode())
        print(f"{key}: DEM summit {sub[rr, cc]:.0f} m, valley {out[key]['base']} m")

    page = pathlib.Path(__file__).resolve().parent.parent / "index.html"
    html = page.read_text()
    html, count = re.subn(r"const TERRAIN = .*?; // @terrain", lambda _: "const TERRAIN = " + json.dumps(out, separators=(",", ":")) + "; // @terrain", html, count=1, flags=re.S)
    assert count == 1, "TERRAIN marker not found in index.html"
    page.write_text(html)


if __name__ == "__main__":
    main()
