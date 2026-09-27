"""Off-campus shade for bus routes.
Builds 2 m obstacle grids over a 150 m corridor around every Aggie Spirit route:
  trees     = Meta/WRI CHM v2 canopy height (crown occupies 35-100 % of height)
  buildings = USGS 3DEP lidar surface minus ground where there is no tree canopy, plus OSM footprints with estimated heights
Then, for every route sample point off campus, precomputes whether the point is shaded for a grid of sun positions.
Stages: 'lidar' (download + DSM/DTM), 'grids' (CHM + obstacles), 'masks' (ray casting + outputs)."""
import json, math, os, sys, io, base64, urllib.request, concurrent.futures as cf
import numpy as np
from scipy import ndimage

d = os.path.dirname(os.path.abspath(__file__))
LAT0, LON0 = 30.6120, -96.3425
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
R = 6378137.0
S_, W_, N_, E_ = 30.5669, -96.4883, 30.6683, -96.2959
RES = 2.0
X0 = math.floor((W_ - LON0) * KX); X1 = math.ceil((E_ - LON0) * KX)
Y0 = math.floor((S_ - LAT0) * KY); Y1 = math.ceil((N_ - LAT0) * KY)
GW, GH = int((X1 - X0) / RES), int((Y1 - Y0) / RES)
bus = json.load(open(os.path.join(d, 'bus.json'), encoding='utf-8'))
campus_bh = json.load(open(os.path.join(d, 'campus.json'), encoding='utf-8'))['bh']
CX0, CY1 = campus_bh['x0'], campus_bh['y1']; CX1, CY0 = CX0 + campus_bh['w'], CY1 - campus_bh['h']
stage = sys.argv[1]

def corridor_mask(buf=150):
    m = np.zeros((GH // 5 + 1, GW // 5 + 1), bool)  # 10 m cells
    for r in bus:
        L = r['line']
        for i in range(0, len(L) - 2, 2):
            a, b = (L[i], L[i + 1]), (L[i + 2], L[i + 3]); n = max(1, int(math.dist(a, b) / 5))
            for k in range(n + 1):
                x = a[0] + (b[0] - a[0]) * k / n; y = a[1] + (b[1] - a[1]) * k / n
                m[int((Y1 - y) / 10), int((x - X0) / 10)] = True
    m = ndimage.binary_dilation(m, iterations=int(buf / 10))
    return m

if stage == 'lidar':
    import laspy
    BASE = 'https://s3-us-west-2.amazonaws.com/usgs-lidar-public/USGS_LPC_TX_RedRiver_3Area_B2_2018_LAS_2019/'
    def get(url):
        for _ in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'AggieShadeMVP/0.1'}), timeout=90) as r: return r.read()
            except Exception as e: err = e
        raise err
    cm = corridor_mask(170)
    ept = json.loads(get(BASE + 'ept.json')); bx0, by0, _, bx1, _, _ = ept['bounds']; cube = bx1 - bx0
    merc = lambda lon, lat: (math.radians(lon) * R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R)
    def node_hits(D, X, Y):
        s = cube / 2 ** D; mx0, my0 = bx0 + X * s, by0 + Y * s
        lon0 = math.degrees(mx0 / R); lon1 = math.degrees((mx0 + s) / R)
        lat0 = math.degrees(math.atan(math.sinh(my0 / R))); lat1 = math.degrees(math.atan(math.sinh((my0 + s) / R)))
        x0 = (lon0 - LON0) * KX; x1 = (lon1 - LON0) * KX; y0 = (lat0 - LAT0) * KY; y1 = (lat1 - LAT0) * KY
        c0 = max(0, int((x0 - X0) / 10)); c1 = min(cm.shape[1] - 1, int((x1 - X0) / 10))
        r0 = max(0, int((Y1 - y1) / 10)); r1 = min(cm.shape[0] - 1, int((Y1 - y0) / 10))
        return c0 <= c1 and r0 <= r1 and cm[r0:r1 + 1, c0:c1 + 1].any()
    nodes, pending = [], ['0-0-0-0']
    while pending:
        root = pending.pop(); h = json.loads(get(BASE + 'ept-hierarchy/' + root + '.json'))
        for key, cnt in h.items():
            D, X, Y, Z = map(int, key.split('-'))
            if D > 9 or not node_hits(D, X, Y): continue
            if cnt == -1:
                if key != root: pending.append(key)
            elif cnt > 0: nodes.append(key)
    print('nodes', len(nodes), flush=True)
    dsm = np.full(GW * GH, -1e4, np.float32); dtm = np.full((GH // 2) * (GW // 2), 1e4, np.float32)
    def fetch(key):
        las = laspy.read(io.BytesIO(get(BASE + 'ept-data/' + key + '.laz')))
        lon = np.degrees(np.asarray(las.x) / R); lat = np.degrees(np.arctan(np.sinh(np.asarray(las.y) / R)))
        x = (lon - LON0) * KX; y = (lat - LAT0) * KY
        return x, y, np.asarray(las.z, np.float32), np.asarray(las.classification)
    done = 0
    with cf.ThreadPoolExecutor(16) as ex:
        for x, y, z, c in ex.map(fetch, nodes):
            ci = ((x - X0) / RES).astype(np.int64); cj = ((Y1 - y) / RES).astype(np.int64)
            ok = (ci >= 0) & (ci < GW) & (cj >= 0) & (cj < GH)
            m = ok & (c == 1); np.maximum.at(dsm, cj[m] * GW + ci[m], z[m])
            g = ok & (c == 2); np.minimum.at(dtm, (cj[g] // 2) * (GW // 2) + np.minimum(ci[g] // 2, GW // 2 - 1), z[g])
            done += 1
            if done % 200 == 0: print('fetched', done, flush=True)
    np.save(os.path.join(d, 'c_dsm.npy'), dsm.reshape(GH, GW)); np.save(os.path.join(d, 'c_dtm4.npy'), dtm.reshape(GH // 2, GW // 2))
    print('dsm cells with returns', int((dsm > -1e3).sum()), 'dtm cells', int((dtm < 1e3).sum()))

elif stage == 'grids':
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    from PIL import Image, ImageDraw
    cm = np.repeat(np.repeat(corridor_mask(150), 5, 0), 5, 1)[:GH, :GW]
    # canopy: reproject CHM tiles into our local equirectangular grid (max resampling)
    lat_ts = math.degrees(math.acos(KX / KY)); Rloc = KY * 180 / math.pi
    dst_crs = f'+proj=eqc +R={Rloc} +lat_ts={lat_ts} +lat_0={LAT0} +lon_0={LON0} +x_0=0 +y_0=0 +units=m +no_defs'
    dst_tf = from_origin(X0, Y1, RES, RES)
    chm = np.zeros((GH, GW), np.uint8)
    def qk(lat, lon, z=10):
        n = 2 ** z; x = int((lon + 180) / 360 * n); y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
        return ''.join(str((1 if x & (1 << (i - 1)) else 0) + (2 if y & (1 << (i - 1)) else 0)) for i in range(z, 0, -1))
    keys = {qk(la, lo) for la in (S_, N_) for lo in (W_, E_)}
    print('chm tiles', keys, flush=True)
    os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'
    for k in keys:
        with rasterio.open(f'/vsicurl/https://dataforgood-fb-data.s3.amazonaws.com/forests/v2/global/dinov3_global_chm_v2_ml3/chm/{k}.tif') as src:
            tmp = np.zeros((GH, GW), np.uint8)
            reproject(rasterio.band(src, 1), tmp, dst_transform=dst_tf, dst_crs=dst_crs, resampling=Resampling.max)
            chm = np.maximum(chm, tmp)
    chm[chm < 3] = 0; chm[~cm] = 0
    # buildings from lidar: surface minus ground, where there is no canopy
    dsm = np.load(os.path.join(d, 'c_dsm.npy')); dtm4 = np.load(os.path.join(d, 'c_dtm4.npy'))
    has = dtm4 < 1e3
    _, (ii, jj) = ndimage.distance_transform_edt(~has, return_indices=True)
    dtm4 = ndimage.uniform_filter(dtm4[ii, jj], 5)
    dtm = np.repeat(np.repeat(dtm4, 2, 0), 2, 1)
    dtm = np.pad(dtm, ((0, GH - dtm.shape[0]), (0, GW - dtm.shape[1])), mode='edge')
    # the corridor lidar is sparse (~1 return per 2 m cell): fill empty cells from their 3x3 neighbourhood
    dsm = np.where(dsm > -1e3, dsm, ndimage.maximum_filter(dsm, size=3))
    seen = dsm > -1e3
    nd = np.where(seen, dsm - dtm, 0).astype(np.float32)
    treeish = ndimage.binary_dilation(chm > 0, iterations=1)
    bmask = (nd >= 2.5) & ~treeish & cm
    bmask = ndimage.binary_opening(bmask, structure=np.ones((2, 2)))  # drop power lines, poles, cars
    lab, n = ndimage.label(bmask); sizes = ndimage.sum(bmask, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool); keep[1:] = sizes >= 6  # at least ~24 m2
    bmask = keep[lab]
    # fill cells inside a structure that had no lidar return with the structure's median height
    bh = np.where(bmask, np.clip(nd, 0, 80), 0)
    # OSM footprints with estimated heights (covers buildings newer than the 2018 lidar)
    osm = json.load(open(os.path.join(d, 'city_buildings.json'), encoding='utf-8'))['elements']
    img = Image.new('L', (GW, GH), 0); dr = ImageDraw.Draw(img)
    def est(t):
        try: return float(str(t.get('height', '')).split()[0])
        except (ValueError, IndexError): pass
        try: return float(t['building:levels']) * 3.5 + 1
        except (KeyError, ValueError): pass
        return {'house': 6.5, 'detached': 6.5, 'residential': 7, 'apartments': 10, 'dormitory': 12, 'commercial': 7, 'retail': 6,
                'garage': 3.5, 'shed': 3, 'roof': 5, 'church': 10, 'school': 8, 'university': 12, 'office': 10}.get(t.get('building'), 6)
    for e in osm:
        geom = e.get('geometry') or next((m['geometry'] for m in e.get('members', []) if m.get('role') == 'outer' and m.get('geometry')), None)
        if not geom or len(geom) < 3: continue
        pts = [(((g['lon'] - LON0) * KX - X0) / RES, (Y1 - (g['lat'] - LAT0) * KY) / RES) for g in geom]
        dr.polygon(pts, fill=int(min(80, round(est(e.get('tags', {}))))))
    osm_h = np.array(img)
    # OSM building where the lidar clearly saw open ground: built after 2018. Needs most of the footprint observed.
    lab_o, no = ndimage.label(osm_h > 0)
    obs = ndimage.mean(seen & (nd < 2.5) & (chm == 0), lab_o, range(1, no + 1))
    new_fp = np.zeros(no + 1, bool); new_fp[1:] = np.asarray(obs) > 0.8
    newer = new_fp[lab_o] & (bh == 0)
    bh = np.where(newer & cm, osm_h, bh)
    bh = np.round(bh).astype(np.uint8)
    np.save(os.path.join(d, 'c_bh.npy'), bh); np.save(os.path.join(d, 'c_chm.npy'), chm)
    oc = ~((np.arange(GW)[None, :] * RES + X0 >= CX0) & (np.arange(GW)[None, :] * RES + X0 <= CX1) & ((Y1 - np.arange(GH)[:, None] * RES) >= CY0) & ((Y1 - np.arange(GH)[:, None] * RES) <= CY1))
    print('corridor km2', round(cm.sum() * 4 / 1e6, 1), '| off-campus corridor: tree cover', round(float((chm > 0)[cm & oc].mean()), 3),
          'building cover', round(float((bh > 0)[cm & oc].mean()), 3), 'newer-than-lidar cells', int(newer.sum()))
    Image.fromarray(np.dstack([np.clip(bh * 6, 0, 255), np.clip(chm.astype(np.int32) * 10, 0, 255), np.zeros_like(bh)]).astype(np.uint8)).resize((GW // 4, GH // 4)).save(os.path.join(d, 'corridor_preview.png'))

elif stage == 'masks':
    from PIL import Image
    bh = np.load(os.path.join(d, 'c_bh.npy')); chm = np.load(os.path.join(d, 'c_chm.npy'))
    AZ = np.arange(0, 360, 15); ALT = np.array([5, 15, 25, 35, 45, 55, 65, 78])
    # sample points every 12 m along each route (index k covers distance k*12 .. k*12+12); campus points are handled exactly in the app
    pts, key2id, route_idx = [], {}, []
    for r in bus:
        L = r['line']; cum = [0.0]
        for i in range(0, len(L) - 2, 2): cum.append(cum[-1] + math.dist((L[i], L[i + 1]), (L[i + 2], L[i + 3])))
        idx, seg = [], 0
        for k in range(int(cum[-1] // 12) + 1):
            s = min(cum[-1], k * 12 + 6)
            while seg < len(cum) - 2 and cum[seg + 1] < s: seg += 1
            t = (s - cum[seg]) / max(1e-9, cum[seg + 1] - cum[seg])
            x = L[2 * seg] + (L[2 * seg + 2] - L[2 * seg]) * t; y = L[2 * seg + 1] + (L[2 * seg + 3] - L[2 * seg + 1]) * t
            if CX0 <= x <= CX1 and CY0 <= y <= CY1: idx.append(0); continue  # 0 = on campus, use exact model
            q = (round(x / 6), round(y / 6))
            if q not in key2id: key2id[q] = len(pts) + 1; pts.append((x, y))
            idx.append(key2id[q])
        route_idx.append(idx)
    P = np.array(pts); n = len(P)
    print('route samples', sum(map(len, route_idx)), 'unique off-campus points', n, flush=True)
    bbits = np.zeros((n, len(AZ) * len(ALT)), bool); tbits = np.zeros_like(bbits)
    for ai, az in enumerate(AZ):
        dx, dy = math.sin(math.radians(az)), math.cos(math.radians(az))
        for li, alt in enumerate(ALT):
            tn = math.tan(math.radians(alt)); maxS = min(150, 60 / tn); col = ai * len(ALT) + li
            bhit = np.zeros(n, bool); thit = np.zeros(n, bool)
            for s in np.arange(1.0, maxS + 1e-6, min(2.0, 1.5 / tn)):
                gx = ((P[:, 0] + dx * s - X0) / RES).astype(np.int64); gy = ((Y1 - (P[:, 1] + dy * s)) / RES).astype(np.int64)
                ok = (gx >= 0) & (gx < GW) & (gy >= 0) & (gy < GH)
                gx = np.where(ok, gx, 0); gy = np.where(ok, gy, 0); z = s * tn
                hb = bh[gy, gx]; hc = chm[gy, gx].astype(np.float32)
                bhit |= ok & (hb > z); thit |= ok & (hc > 0) & (z < hc) & (z > 0.35 * hc)
            bbits[:, col] = bhit; tbits[:, col] = thit
        print('az', az, flush=True)
    packed = np.concatenate([np.packbits(bbits, axis=1), np.packbits(tbits, axis=1)], axis=1)  # 24 + 24 bytes per point
    per_row = 25; rows = math.ceil(n / per_row)
    img = np.zeros((rows, per_row * packed.shape[1]), np.uint8); img.reshape(-1)[:packed.size] = packed.reshape(-1)
    buf = io.BytesIO(); Image.fromarray(img, 'L').save(buf, 'PNG', optimize=True)
    # display layers off campus at 8 m: R = buildings, G = canopy (corridor only)
    b8 = bh.reshape(GH // 4, 4, GW // 4, 4).max((1, 3)) if GH % 4 == 0 and GW % 4 == 0 else bh[:GH // 4 * 4, :GW // 4 * 4].reshape(GH // 4, 4, GW // 4, 4).max((1, 3))
    c8 = chm[:GH // 4 * 4, :GW // 4 * 4].reshape(GH // 4, 4, GW // 4, 4).max((1, 3))
    xs8 = X0 + (np.arange(b8.shape[1]) + .5) * 8; ys8 = Y1 - (np.arange(b8.shape[0]) + .5) * 8
    oncampus = ((xs8[None, :] >= CX0) & (xs8[None, :] <= CX1)) & ((ys8[:, None] >= CY0) & (ys8[:, None] <= CY1))
    disp = np.dstack([(b8 > 0) * 255, (c8 > 0) * 255, np.zeros_like(b8)]).astype(np.uint8)
    disp[oncampus] = 0
    dbuf = io.BytesIO(); Image.fromarray(disp, 'RGB').save(dbuf, 'PNG', optimize=True)
    out = {'x0': X0, 'y1': Y1, 'az': AZ.tolist(), 'alt': ALT.tolist(), 'bytes': int(packed.shape[1]), 'perRow': per_row, 'n': n,
           'png': base64.b64encode(buf.getvalue()).decode(), 'routes': [','.join(map(str, ix)) for ix in route_idx],
           'disp': {'x0': X0, 'y1': Y1, 'res': 8, 'w': disp.shape[1], 'h': disp.shape[0], 'png': base64.b64encode(dbuf.getvalue()).decode()}}
    json.dump(out, open(os.path.join(d, 'offcampus.json'), 'w'), separators=(',', ':'))
    sh = (bbits | tbits)
    print('mask png', len(buf.getvalue()), 'display png', len(dbuf.getvalue()), 'json', os.path.getsize(os.path.join(d, 'offcampus.json')))
    print('shaded share at alt 55: buildings', round(float(bbits[:, 5::len(ALT)].mean()), 3), 'trees', round(float(tbits[:, 5::len(ALT)].mean()), 3), '| at alt 25:', round(float(sh[:, 2::len(ALT)].mean()), 3))
