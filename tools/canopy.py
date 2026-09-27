import math, os, json, base64, io
import numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds, transform

d = os.path.dirname(os.path.abspath(__file__))
URL = '/vsicurl/https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/chm/0231301301.tif'
S, W_, N, E_ = 30.6035, -96.3530, 30.6240, -96.3325
LAT0, LON0 = 30.6120, -96.3425
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
RES = 2.0  # metres per canopy cell

os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
with rasterio.open(URL) as src:
    print('crs', src.crs, 'res', src.res, 'dtype', src.dtypes, 'nodata', src.nodata, 'size', src.width, src.height)
    b = transform_bounds('EPSG:4326', src.crs, W_ - .001, S - .001, E_ + .001, N + .001)
    win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
    arr = src.read(1, window=win).astype(np.float32)
    wt = src.window_transform(win)
    print('window', win, 'arr', arr.shape, 'min/max', float(arr.min()), float(arr.max()))

# local grid covering the bbox
x0 = math.floor((W_ - LON0) * KX); x1 = math.ceil((E_ - LON0) * KX)
y0 = math.floor((S - LAT0) * KY); y1 = math.ceil((N - LAT0) * KY)
gw = int((x1 - x0) / RES); gh = int((y1 - y0) / RES)
out = np.zeros((gh, gw), np.float32)
inv = ~wt
for sx, sy in ((.25, .25), (.75, .25), (.25, .75), (.75, .75)):
    xs = x0 + (np.arange(gw) + sx) * RES
    ys = y1 - (np.arange(gh) + sy) * RES
    X, Y = np.meshgrid(xs, ys)
    lon = LON0 + X / KX; lat = LAT0 + Y / KY
    px, py = transform('EPSG:4326', src.crs, lon.ravel(), lat.ravel())
    c, r = inv * (np.array(px), np.array(py))
    c = np.clip(c.astype(int), 0, arr.shape[1] - 1); r = np.clip(r.astype(int), 0, arr.shape[0] - 1)
    out = np.maximum(out, arr[r, c].reshape(gh, gw))

out[out < 3] = 0          # ignore shrubs / noise
out = np.clip(np.round(out), 0, 40).astype(np.uint8)
print('grid', gw, gh, 'canopy cells', int((out > 0).sum()), 'share', round(float((out > 0).mean()), 3), 'mean h', round(float(out[out > 0].mean()), 1))

from PIL import Image
buf = io.BytesIO(); Image.fromarray(out, 'L').save(buf, 'PNG', optimize=True)
meta = {'x0': x0, 'y1': y1, 'res': RES, 'w': gw, 'h': gh, 'png': base64.b64encode(buf.getvalue()).decode()}
json.dump(meta, open(os.path.join(d, 'canopy.json'), 'w'))
Image.fromarray((out.astype(np.float32) * 6).clip(0, 255).astype(np.uint8)).save(os.path.join(d, 'canopy_preview.png'))
print('png bytes', len(buf.getvalue()))
