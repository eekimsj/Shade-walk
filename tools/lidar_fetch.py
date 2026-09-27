import json, math, os, sys, io, urllib.request, concurrent.futures as cf
import numpy as np, laspy

d = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://s3-us-west-2.amazonaws.com/usgs-lidar-public/USGS_LPC_TX_RedRiver_3Area_B2_2018_LAS_2019/'
MAXD = int(sys.argv[1]) if len(sys.argv) > 1 else 10
R = 6378137.0
def merc(lon, lat): return (math.radians(lon) * R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R)
S, W_, N, E_ = 30.6035, -96.3530, 30.6240, -96.3325
qx0, qy0 = merc(W_, S); qx1, qy1 = merc(E_, N)

def get(url):
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'AggieShadeMVP/0.1'}), timeout=60) as r:
                return r.read()
        except Exception as e:
            err = e
    raise err

ept = json.loads(get(BASE + 'ept.json'))
bx0, by0, bz0, bx1, by1, bz1 = ept['bounds']
cube = bx1 - bx0

def nb(D, X, Y):
    s = cube / 2 ** D
    return bx0 + X * s, by0 + Y * s, bx0 + (X + 1) * s, by0 + (Y + 1) * s
def hits(D, X, Y):
    x0, y0, x1, y1 = nb(D, X, Y)
    return x0 < qx1 and x1 > qx0 and y0 < qy1 and y1 > qy0

# walk hierarchy (subtrees flagged with -1)
nodes, pending = [], ['0-0-0-0']
while pending:
    root = pending.pop()
    h = json.loads(get(BASE + 'ept-hierarchy/' + root + '.json'))
    for key, cnt in h.items():
        D, X, Y, Z = map(int, key.split('-'))
        if D > MAXD or not hits(D, X, Y): continue
        if cnt == -1:
            if key != root: pending.append(key)
        elif cnt > 0:
            nodes.append(key)
print('nodes', len(nodes), 'by depth', {k: sum(1 for n in nodes if n.startswith(f'{k}-')) for k in range(MAXD + 1)})

def fetch(key):
    las = laspy.read(io.BytesIO(get(BASE + 'ept-data/' + key + '.laz')))
    x, y = np.asarray(las.x), np.asarray(las.y)
    m = (x >= qx0) & (x <= qx1) & (y >= qy0) & (y <= qy1)
    return np.stack([x[m], y[m], np.asarray(las.z)[m], np.asarray(las.classification)[m].astype(np.float64)], 1)

parts = []
with cf.ThreadPoolExecutor(16) as ex:
    for i, arr in enumerate(ex.map(fetch, nodes)):
        parts.append(arr)
        if i % 100 == 0: print('fetched', i, flush=True)
pts = np.concatenate(parts)
np.save(os.path.join(d, 'lidar_pts.npy'), pts.astype(np.float64))
area = (qx1 - qx0) * (qy1 - qy0) * math.cos(math.radians(30.61)) ** 2
cls, cnt = np.unique(pts[:, 3].astype(int), return_counts=True)
print('points', len(pts), 'per m2', round(len(pts) / area, 2), 'classes', dict(zip(cls.tolist(), cnt.tolist())))
