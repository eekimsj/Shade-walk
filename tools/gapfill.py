"""Rebuild every Aggie Spirit route from OSM, filling gaps in the route relations by routing on the OSM road network.
Stage 1 (no args): stitch + report gaps, write gap bboxes.  Stage 2 ('fill'): needs roads.json, fills gaps, validates, writes bus.json."""
import json, math, os, sys, heapq, collections
d = os.path.dirname(os.path.abspath(__file__))
LAT0, LON0 = 30.6120, -96.3425
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
xy = lambda lat, lon: ((lon - LON0) * KX, (lat - LAT0) * KY)
ll = lambda p: (LAT0 + p[1] / KY, LON0 + p[0] / KX)
dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
NUM = {'Bonfire': '01', 'Yell Practice': '03', "Gig Em": '04', "Gig 'Em": '04', 'Bush School': '05', '12th Man': '06', 'Airport': '07',
       'Howdy': '08', 'Reveille': '12', 'Old Army': '15', 'Excel': '22', 'Rudder': '26', 'Ring Dance': '27', 'Elephant Walk': '31',
       'Fish Camp': '34', 'Hullabaloo': '35', 'Matthew Gaines': '36', 'Century Tree': '40', 'RELLIS': '47/48'}
NIGHT = {'01-04': "Bonfire & Gig 'Em (night)", '03-05': 'Yell Practice & Bush School (night)'}

osm = json.load(open(os.path.join(d, 'bus_osm.json'), encoding='utf-8'))
stopnames = {n['id']: n['tags'].get('name', '') for n in json.load(open(os.path.join(d, 'bus_stops.json'), encoding='utf-8'))['elements']}

def orient(ways):
    """Orient each way using its neighbours; closed ways (roundabouts) are cut between entry and exit."""
    out = []
    n = len(ways)
    for i, w in enumerate(ways):
        closed = len(w) > 3 and dist(w[0], w[-1]) < 0.5
        prev_end = out[-1][-1] if out else None
        nxt = ways[i + 1] if i + 1 < n else None
        if closed:
            ring = w[:-1]
            ent = min(range(len(ring)), key=lambda k: dist(ring[k], prev_end)) if prev_end else 0
            if nxt:
                ends = [nxt[0], nxt[-1]] if not (len(nxt) > 3 and dist(nxt[0], nxt[-1]) < 0.5) else nxt
                ex = min(range(len(ring)), key=lambda k: min(dist(ring[k], e) for e in ends))
            else:
                ex = ent
            seg, k = [ring[ent]], ent
            while k != ex:  # follow the mapped direction (roundabouts are one-way in mapped order)
                k = (k + 1) % len(ring); seg.append(ring[k])
            out.append(seg); continue
        fwd = None
        if nxt:
            ends = [nxt[0], nxt[-1]]
            if min(dist(w[-1], e) for e in ends) < 0.5: fwd = True
            elif min(dist(w[0], e) for e in ends) < 0.5: fwd = False
            elif len(nxt) > 3 and dist(nxt[0], nxt[-1]) < 0.5:  # next is a roundabout: whichever end touches it
                dE = min(dist(w[-1], q) for q in nxt); dS = min(dist(w[0], q) for q in nxt)
                if min(dE, dS) < 0.5: fwd = dE <= dS
        if fwd is None and prev_end:
            fwd = dist(w[0], prev_end) <= dist(w[-1], prev_end)
        if fwd is None: fwd = True
        out.append(list(w) if fwd else list(w[::-1]))
    return out

routes = []
for r in osm['elements']:
    t = r.get('tags', {})
    ways = [[xy(g['lat'], g['lon']) for g in m['geometry']] for m in r['members']
            if m['type'] == 'way' and m.get('role', '') in ('', 'forward', 'backward') and m.get('geometry')]
    stops = [(m['ref'], xy(m['lat'], m['lon'])) for m in r['members'] if m['type'] == 'node' and ('stop' in m.get('role', '') or 'platform' in m.get('role', ''))]
    if not ways: continue
    # Misplaced members: a run of 1–6 ways that jumps away and back. Remove the run when the ways on either side
    # meet without it, then re-insert it at any gap whose two sides it bridges.
    def touch(a, b): return min(dist(p, q) for p in (a[0], a[-1]) for q in (b[0], b[-1])) < 1.0
    moved = 0
    for _ in range(20):
        pcs = orient(ways)
        gap_after = [dist(pcs[i][-1], pcs[i + 1][0]) > 1.0 for i in range(len(pcs) - 1)]
        done = False
        for i in range(1, len(ways)):
            if not gap_after[i - 1]: continue
            for k in range(1, 7):
                j = i + k
                if j >= len(ways) or not gap_after[j - 1]: continue
                if touch(ways[i - 1], ways[j]):
                    run = ways[i:j]; del ways[i:j]
                    pcs2 = orient(ways)
                    for g in range(len(pcs2) - 1):  # re-insert where the run bridges a gap
                        if dist(pcs2[g][-1], pcs2[g + 1][0]) > 1.0 and touch(ways[g], run[0]) and touch(run[-1], ways[g + 1]):
                            ways[g + 1:g + 1] = run; break
                        if dist(pcs2[g][-1], pcs2[g + 1][0]) > 1.0 and touch(ways[g], run[-1]) and touch(run[0], ways[g + 1]):
                            ways[g + 1:g + 1] = run[::-1]; break
                    moved += 1; done = True; break
            if done: break
        if not done: break
    pieces = orient(ways)
    line, gaps = list(pieces[0]), []
    for p in pieces[1:]:
        g = dist(line[-1], p[0])
        if g > 1.0: gaps.append({'at': len(line), 'a': line[-1], 'b': p[0], 'm': g})
        line += p if g > 1.0 else p[1:]
    name = t.get('name') or NIGHT.get(t.get('ref', ''), f"Route {t.get('ref', '')}")
    routes.append({'id': r['id'], 'ref': t.get('ref', ''), 'name': name, 'line': line, 'gaps': gaps, 'stops': stops, 'moved': moved})

if len(sys.argv) < 2:
    boxes = []
    for r in sorted(routes, key=lambda r: r['name']):
        big = [round(g['m']) for g in r['gaps']]
        print(f"{r['id']} {r['name']:<40} moved {r['moved']} gaps {len(big):>2} {big}")
        for g in r['gaps']:
            m = max(600, g['m'] * 0.8)
            (la1, lo1), (la2, lo2) = ll((min(g['a'][0], g['b'][0]) - m, min(g['a'][1], g['b'][1]) - m)), ll((max(g['a'][0], g['b'][0]) + m, max(g['a'][1], g['b'][1]) + m))
            boxes.append([round(la1, 5), round(lo1, 5), round(la2, 5), round(lo2, 5)])
    json.dump(boxes, open(os.path.join(d, 'gap_boxes.json'), 'w'))
    print('total gaps', sum(len(r['gaps']) for r in routes), 'boxes', len(boxes))
    sys.exit()

# ---------- stage 2: fill ----------
roads = json.load(open(os.path.join(d, 'roads.json'), encoding='utf-8'))
DRIVE = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link',
         'unclassified', 'residential', 'service', 'living_street', 'busway', 'road'}
coord, adj = {}, collections.defaultdict(list)
for w in roads['elements']:
    if w['type'] != 'way': continue
    t = w.get('tags', {})
    if t.get('highway') not in DRIVE: continue
    ow = t.get('oneway'); ow = '-1' if ow == '-1' else ('yes' if ow in ('yes', 'true', '1') or t.get('junction') in ('roundabout', 'circular') else 'no')
    if t.get('oneway:bus') == 'no' or t.get('busway') == 'opposite_lane': ow = 'no'
    for i, nid in enumerate(w['nodes']): coord[nid] = xy(w['geometry'][i]['lat'], w['geometry'][i]['lon'])
    for a, b in zip(w['nodes'], w['nodes'][1:]):
        L = dist(coord[a], coord[b])
        if ow in ('yes', 'no'): adj[a].append((b, L))
        if ow in ('-1', 'no'): adj[b].append((a, L))
ids = list(coord)
def nearest(p):
    return min(ids, key=lambda n: (coord[n][0] - p[0]) ** 2 + (coord[n][1] - p[1]) ** 2)
def shortest(a, b):
    dd, prev, h = {a: 0}, {}, [(0, a)]
    while h:
        c, u = heapq.heappop(h)
        if u == b: break
        if c > dd.get(u, 1e18): continue
        for v, L in adj[u]:
            if c + L < dd.get(v, 1e18): dd[v] = c + L; prev[v] = u; heapq.heappush(h, (c + L, v))
    if b not in dd: return None, None
    path, u = [b], b
    while u != a: u = prev[u]; path.append(u)
    return [coord[n] for n in path[::-1]], dd[b]

# reference layers: where buses actually drive (City of College Station 2023 + TAMU GIS 2026)
ref_pts = []
for f in ('ref_city.json', 'ref_tamu.json'):
    for feat in json.load(open(os.path.join(d, f)))['features']:
        for path in feat['geometry']['paths']:
            for i in range(len(path) - 1):
                (x1, y1), (x2, y2) = xy(path[i][1], path[i][0]), xy(path[i + 1][1], path[i + 1][0])
                n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 10))
                for k in range(n + 1): ref_pts.append((x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n))
grid = collections.defaultdict(list)
for p in ref_pts: grid[(int(p[0] // 50), int(p[1] // 50))].append(p)
def near_ref(p, tol=30):
    gx, gy = int(p[0] // 50), int(p[1] // 50)
    return any(dist(p, q) < tol for i in (-1, 0, 1) for j in (-1, 0, 1) for q in grid.get((gx + i, gy + j), ()))

def project(line, p):
    best, acc, bestpos = 1e18, 0, 0
    for i in range(len(line) - 1):
        a, b = line[i], line[i + 1]; L = dist(a, b)
        t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L / L))
        q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        dd = dist(p, q)
        if dd < best: best, bestpos = dd, acc + t * L
        acc += L
    return bestpos, best

out, report = [], []
for r in sorted(routes, key=lambda r: (NUM.get(r['name'], r['ref'] or '99'), r['name'])):
    line, filled, filled_m, checked, onref, failed = r['line'], [], 0, 0, 0, 0
    for g in reversed(r['gaps']):  # reversed so earlier indices stay valid
        path, L = shortest(nearest(g['a']), nearest(g['b']))
        if path is None or L > max(4 * g['m'], g['m'] + 1500):
            failed += 1; continue
        line[g['at']:g['at']] = path
        filled_m += L
        for i in range(len(path) - 1):
            n = max(1, int(dist(path[i], path[i + 1]) / 10))
            for k in range(n):
                p = (path[i][0] + (path[i + 1][0] - path[i][0]) * k / n, path[i][1] + (path[i + 1][1] - path[i][1]) * k / n)
                checked += 1; onref += near_ref(p)
    clean = []
    for p in line:
        if not clean or dist(clean[-1], p) >= 3: clean.append((round(p[0]), round(p[1])))
    # stop order must follow travel direction
    seq = [project(clean, p)[0] for _, p in r['stops']]
    if sum(b < a for a, b in zip(seq, seq[1:])) > sum(b > a for a, b in zip(seq, seq[1:])): clean.reverse()
    st = []
    for ref, p in r['stops']:
        pos, off = project(clean, p)
        if off < 60 and stopnames.get(ref): st.append((round(pos), stopnames[ref]))
    st.sort(); ded = []
    for s in st:
        if not ded or (ded[-1][1] != s[1] and s[0] - ded[-1][0] > 30): ded.append(s)
    total = sum(dist(clean[i], clean[i + 1]) for i in range(len(clean) - 1))
    # residual jumps after filling (should be none)
    jumps = sum(1 for i in range(len(clean) - 1) if dist(clean[i], clean[i + 1]) > 80)
    loop = dist(clean[0], clean[-1]) < 150
    num = NUM.get(r['name'], r['ref'] if r['ref'] in NIGHT else '')
    report.append((num, r['name'], ded[0][1] if ded else '', ded[-1][1] if ded else '', len(r['gaps']), failed, round(filled_m), round(100 * onref / checked) if checked else None, jumps, round(total / 1000, 1), len(ded)))
    if failed or len(ded) < 2: continue
    out.append({'name': r['name'], 'num': num, 'ref': r['ref'], 'dir': 'Loop' if loop else f"{ded[0][1]} → {ded[-1][1]}", 'loop': loop,
                'filled': round(filled_m), 'line': [c for p in clean for c in p], 'stops': [[s[0], s[1]] for s in ded]})

print(f"{'num':<6}{'route':<38}{'gaps':>5}{'fail':>5}{'filled m':>9}{'on bus roads':>13}{'jumps':>6}{'km':>6}{'stops':>6}  first -> last")
for rp in report:
    print(f"{rp[0]:<6}{rp[1][:37]:<38}{rp[4]:>5}{rp[5]:>5}{rp[6]:>9}{(str(rp[7]) + '%') if rp[7] is not None else '-':>13}{rp[8]:>6}{rp[9]:>6}{rp[10]:>6}  {rp[2]} -> {rp[3]}")
json.dump(out, open(os.path.join(d, 'bus.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print('kept', len(out), 'of', len(routes), 'bytes', os.path.getsize(os.path.join(d, 'bus.json')))
