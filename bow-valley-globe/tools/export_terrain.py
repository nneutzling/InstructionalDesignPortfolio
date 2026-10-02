"""Cut one elevation tile per peak from NRCan's Canadian Digital Elevation Model and embed them in ../index.html.

    pip install rasterio scipy pyproj numpy pysheds scikit-image
    python export_terrain.py

Reads only the Bow Valley window of the national CDEM (a cloud-optimised GeoTIFF), reprojects it to
UTM 11N at 20 m, then samples a square grid around each summit, turned so the viewer looks at the peak
from its best-known side. Rows run from the far side to the viewer's side; values are metres above sea level.

Water is traced from the same elevation data:
  - lakes: the CDEM stores water surfaces as perfectly flat patches, so flat areas over 0.06 km2 are water,
    except flat terraces at 20 m contour heights, which are an artefact of how the CDEM was made;
  - streams: cells draining more than 15 km2 (D8 flow accumulation);
  - the Bow River: the lowest-cost path along the valley floor from the west edge of the window to the east.
Each tile gets a water bitmask, plus the points where the Bow crosses into and out of it (upstream first),
which the page uses to join the tiles with one river around the globe.

Source: Canadian Digital Elevation Model, Natural Resources Canada, Open Government Licence - Canada.
"""
import base64, json, pathlib, re

import numpy as np
if not hasattr(np, "in1d"):  # pysheds still calls the old name
    np.in1d = np.isin
import pyproj
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from scipy import ndimage
from scipy.ndimage import map_coordinates
from skimage.draw import line as draw_line
from skimage.graph import route_through_array

CDEM = "/vsicurl/https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com/store/elevation/cdem-cdsm/cdem/cdem-canada-dem.tif"
BOX = (-116.05, 50.98, -115.02, 51.36)  # lon/lat: Lac des Arcs to Lake Louise
RES = 20      # metres per cell after reprojection
SIZE = 192    # grid points per tile side (about 30–40 m spacing; the CDEM itself is ~20 m)

# id: (approx lon, lat; summit search radius m; tile width m; bearing from peak toward viewer, deg;
#      tile centre shift in m to the viewer's right / toward the viewer)
PEAKS = {
# Tiles are pushed toward the viewer so the Bow River runs through the foreground where it is close enough
    # (the Three Sisters stand 7-8 km from it, so there the river passes in front of the tile on the globe).
    "yamnuska": (-115.1222, 51.1186, 700, 7500, 165, (-500, 1600)),     # cliff seen from Highway 1A to the south
    "sisters":  (-115.3345, 51.0247, 2500, 8500, 330, (0, 2600)),       # from Canmore
    "rundle":   (-115.4987, 51.1197, 2500, 8000, 315, (-1000, 1500)),   # from Vermilion Lakes
    "cascade":  (-115.5664, 51.2236, 1500, 9000, 185, (0, 2700)),       # from Banff Avenue
    "castle":   (-115.9256, 51.2958, 700, 8000, 225, (-800, 1200)),     # from the Trans-Canada Highway
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


def trace_water(dem, x0, y0):
    """Return (water mask, Bow River path as (row, col) cells), both on the 20 m UTM grid.

    The Bow is traced first, as the lowest-cost path along the valley floor. It is then burned into the
    terrain and flat ground is tilted very slightly toward it, so the drainage network has no undecided
    flats and every stream runs on until it meets the Bow.
    """
    dem = dem.astype(np.float64)
    gy, gx = np.gradient(dem)
    lab, n = ndimage.label((np.abs(gx) < 1e-3) & (np.abs(gy) < 1e-3))
    keep = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        area = (lab[sl] == k).sum() * RES * RES
        level = dem[sl][lab[sl] == k].mean()
        # The CDEM was built from 20 m contours and leaves flat terraces at contour heights on gentle valley
        # floors. Real lake surfaces rarely sit on a contour value, so skip flats there unless they are big.
        on_contour = abs(level - round(level / 20) * 20) < 1.2
        if area > 60000 and (not on_contour or area > 10e6):
            keep.append(k)
    lakes = np.isin(lab, keep)
    lakes = ndimage.binary_closing(ndimage.binary_dilation(lakes, iterations=1), iterations=2)

    H, W = dem.shape
    start = min([(r, 0) for r in range(200, 1000)] + [(0, c) for c in range(800)], key=lambda p: dem[p])
    end = min([(r, W - 2) for r in range(600, 1800)], key=lambda p: dem[p])
    cost = np.exp((dem - 1250) / 35.0)
    cost[lakes] *= 0.5
    path = np.array(route_through_array(cost, start, end, fully_connected=True, geometric=True)[0])
    # Across flat valley floors the cheapest path runs in straight lines; smooth it into a river's curves.
    smooth_path = np.c_[ndimage.gaussian_filter1d(path[:, 0].astype(float), 10, mode="nearest"),
                        ndimage.gaussian_filter1d(path[:, 1].astype(float), 10, mode="nearest")]
    path = np.unique(np.round(smooth_path).astype(int), axis=0, return_index=True)
    path = np.round(smooth_path).astype(int)[np.sort(path[1])]
    on_bow = np.zeros(dem.shape, bool)
    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        rr, cc = draw_line(r0, c0, r1, c1)
        on_bow[rr, cc] = True

    # Burn the Bow in, always running downhill, and tilt everything else a hair toward it.
    burned = dem + ndimage.distance_transform_edt(~on_bow) * 0.002
    level = np.minimum.accumulate(dem[path[:, 0], path[:, 1]]) - 5 - np.arange(len(path)) * 1e-3
    burned[path[:, 0], path[:, 1]] = level

    vf = ViewFinder(affine=from_origin(x0, y0, RES, RES), shape=dem.shape, crs=pyproj.Proj("EPSG:32611"), nodata=np.nan)
    grid = Grid(viewfinder=vf)
    filled = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(burned, viewfinder=vf))))
    fdir = grid.flowdir(filled)
    acc = np.asarray(grid.accumulation(fdir))
    undecided = int((np.asarray(fdir) < 1).sum())
    streams = ndimage.binary_dilation(acc * RES * RES > 15e6, iterations=1)

    bow = ndimage.binary_dilation(on_bow, iterations=3)   # about 140 m wide, to match the ribbon on the globe
    water = lakes | streams | bow

    # Anything that still stops short (a stream ending in a leftover flat, a pond beside the river) is joined
    # to the nearest larger water along the lowest ground. Ponds more than 1.5 km from other water stay put.
    lab, n = ndimage.label(water, structure=np.ones((3, 3)))
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    main = lab == (np.argmax(sizes) + 1)
    joined = 0
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        part = lab[sl] == k
        if main[sl][part].any():
            continue
        cells = np.argwhere(lab == k)
        low = cells[np.argmin(dem[cells[:, 0], cells[:, 1]])]          # its outlet end
        is_stream = streams[cells[:, 0], cells[:, 1]].mean() > 0.5
        win = 120                                                      # search within 2.4 km
        r0, c0 = max(0, low[0] - win), max(0, low[1] - win)
        sub_main = main[r0:low[0] + win, c0:low[1] + win]
        if not sub_main.any():
            continue
        d, (ir, ic) = ndimage.distance_transform_edt(~sub_main, return_indices=True)
        lr, lc = low[0] - r0, low[1] - c0
        if not is_stream and d[lr, lc] * RES > 1500:
            continue
        target = (ir[lr, lc], ic[lr, lc])
        sub_cost = 1 + np.maximum(0, dem[r0:low[0] + win, c0:low[1] + win] - dem[low[0], low[1]])
        link = np.array(route_through_array(sub_cost, (lr, lc), target, fully_connected=True, geometric=True)[0])
        mask = np.zeros_like(sub_main)
        mask[link[:, 0], link[:, 1]] = True
        water[r0:low[0] + win, c0:low[1] + win] |= ndimage.binary_dilation(mask, iterations=1)
        joined += 1
    print(f"drainage: {undecided} cells without a flow direction; joined {joined} loose streams and ponds")
    return water, path


def main():
    dem, x0, y0 = load_dem()
    water, bow_path = trace_water(dem, x0, y0)
    bow_xy = np.c_[x0 + bow_path[:, 1] * RES, y0 - bow_path[:, 0] * RES]   # upstream (west) first
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
        rows, cols = (y0 - ny) / RES, (ex - x0) / RES
        h = map_coordinates(dem, [rows, cols], order=1)
        # A tile cell is ~40 m across, two DEM cells: count it wet if any water touches its footprint,
        # so narrow streams stay continuous instead of breaking into dashes.
        wet = map_coordinates(ndimage.maximum_filter(water.astype(np.uint8), size=3), [rows, cols], order=0).astype(bool)
        # Where the Bow enters and leaves the tile, in tile units (-0.5..0.5), at 0.9 of the tile radius.
        rel = bow_xy - [cx, cy]
        uv = np.c_[rel @ right, rel @ toward] / L
        inside = np.where(np.hypot(*uv.T) < 0.45)[0]
        bow = [uv[inside[0]].round(4).tolist(), uv[inside[-1]].round(4).tolist()] if len(inside) else None
        out[key] = dict(size=SIZE, extent=L, base=round(float(np.percentile(h, 3))), bearing=bearing, bow=bow,
                        h=base64.b64encode(np.clip(np.round(h), 0, 65535).astype("<u2").tobytes()).decode(),
                        water=base64.b64encode(np.packbits(wet.ravel(), bitorder="little").tobytes()).decode())
        print(f"{key}: DEM summit {sub[rr, cc]:.0f} m, valley {out[key]['base']} m, water {wet.mean():.1%}, Bow {bow}")

    page = pathlib.Path(__file__).resolve().parent.parent / "index.html"
    html = page.read_text()
    html, count = re.subn(r"const TERRAIN = .*?; // @terrain", lambda _: "const TERRAIN = " + json.dumps(out, separators=(",", ":")) + "; // @terrain", html, count=1, flags=re.S)
    assert count == 1, "TERRAIN marker not found in index.html"
    page.write_text(html)


if __name__ == "__main__":
    main()
