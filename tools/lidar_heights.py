import json, math, os, io, base64
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

d = os.path.dirname(os.path.abspath(__file__))
LAT0, LON0 = 30.6120, -96.3425
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
R = 6378137.0
S, W_, N, E_ = 30.6035, -96.3530, 30.6240, -96.3325

pts = np.load(os.path.join(d, 'lidar_pts.npy'))
lon = np.degrees(pts[:, 0] / R); lat = np.degrees(np.arctan(np.sinh(pts[:, 1] / R)))
X = (lon - LON0) * KX; Y = (lat - LAT0) * KY; Z = pts[:, 2]; C = pts[:, 3].astype(int)

x0 = math.floor((W_ - LON0) * KX); x1 = math.ceil((E_ - LON0) * KX)
y0 = math.floor((S - LAT0) * KY); y1 = math.ceil((N - LAT0) * KY)
gw, gh = x1 - x0, y1 - y0
ci = np.clip((X - x0).astype(int), 0, gw - 1); cj = np.clip((y1 - Y).astype(int), 0, gh - 1)
flat = cj * gw + ci

# surface (all non-ground, non-noise) max, ground min
dsm = np.full(gw * gh, -1e9); m = (C == 1)
np.maximum.at(dsm, flat[m], Z[m])
dtm = np.full(gw * gh, 1e9); g = (C == 2)
np.minimum.at(dtm, flat[g], Z[g])
dsm = dsm.reshape(gh, gw); dtm = dtm.reshape(gh, gw)
# ground under roofs: nearest measured ground cell, then smoothed
has_g = dtm < 1e8
_, (ii, jj) = ndimage.distance_transform_edt(~has_g, return_indices=True)
dtm_f = ndimage.uniform_filter(dtm[ii, jj], 9)
# a cell with ground returns and no higher returns is ground-level
surf = np.where(dsm > -1e8, dsm, np.where(has_g, dtm, np.nan))

campus = json.load(open(os.path.join(d, 'campus.json'), encoding='utf-8'))
ids = Image.new('I', (gw, gh), 0); dr = ImageDraw.Draw(ids)
for k, b in enumerate(campus['b']):
    f = b[3]
    dr.polygon([(f[i] - x0, y1 - f[i + 1]) for i in range(0, len(f), 2)], fill=k + 1)
ids = np.array(ids)

hgt = surf - dtm_f
out = np.zeros((gh, gw), np.float32)
report = {}
lidar_n = 0
for k, b in enumerate(campus['b']):
    cells = ids == k + 1
    n = int(cells.sum())
    if n == 0: continue
    vals = hgt[cells]
    ok = np.isfinite(vals)
    med = float(np.nanmedian(vals)) if ok.sum() > max(4, n * 0.3) else float('nan')
    if not math.isnan(med) and med >= 2.5:
        v = np.where(ok, vals, med)
        v = np.clip(v, 0, 150)
        v[v < 2] = med if med < 6 else v[v < 2]   # keep courtyards/atria open on big buildings
        out[cells] = v
        b[0] = round(float(np.percentile(v, 90)), 1); b[1] = 0; lidar_n += 1
    else:
        out[cells] = b[0]  # built after 2018 or no returns: keep the estimate
        b[1] = 1
    if b[2]: report[b[2]] = (b[0], b[1], round(med, 1) if not math.isnan(med) else None)

print('buildings from lidar', lidar_n, 'of', len(campus['b']))
for nm in ['Rudder Tower', 'Rudder Theatre Complex', 'Eller Oceanography and Meteorology Building', 'Kyle Field', 'Sterling C. Evans Library',
           'Memorial Student Center', 'Zachry Engineering Education Complex', 'Academic Building', 'Reed Arena', 'Jack K. Williams Administration Building',
           'Student Recreation Center', 'Sbisa Dining Hall', 'Innovative Learning Classroom Building', 'Hullabaloo Residence Hall']:
    print(' ', nm, report.get(nm))

img = np.clip(np.round(out), 0, 255).astype(np.uint8)
buf = io.BytesIO(); Image.fromarray(img, 'L').save(buf, 'PNG', optimize=True)
campus['bh'] = {'x0': x0, 'y1': y1, 'res': 1, 'w': gw, 'h': gh, 'png': base64.b64encode(buf.getvalue()).decode()}
json.dump(campus, open(os.path.join(d, 'campus.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
Image.fromarray(np.clip(out * 4, 0, 255).astype(np.uint8)).save(os.path.join(d, 'bh_preview.png'))
print('height png bytes', len(buf.getvalue()))
