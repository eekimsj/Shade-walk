import json, math, os, sys
d = os.path.dirname(os.path.abspath(__file__))
osm = json.load(open(os.path.join(d, 'bus_osm.json'), encoding='utf-8'))
LAT0, LON0 = 30.6120, -96.3425
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
xy = lambda g: (round((g['lon'] - LON0) * KX, 1), round((g['lat'] - LAT0) * KY, 1))
dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])

def stitch(ways):
    line, gaps = [], 0
    for w in ways:
        if not line: line = list(w); continue
        opts = [(dist(line[-1], w[0]), False, w), (dist(line[-1], w[-1]), True, w)]
        if len(line) and line is not None:
            # first way may need flipping to connect to the second
            if len(ways) > 1 and line is not None and len(line) == len(ways[0]) and line == list(ways[0]):
                opts += [(dist(line[0], w[0]), 'flip0', w), (dist(line[0], w[-1]), 'flip1', w)]
        dd, how, _ = min(opts, key=lambda o: o[0])
        if how == 'flip0': line.reverse(); seg = w
        elif how == 'flip1': line.reverse(); seg = w[::-1]
        else: seg = w[::-1] if how else w
        if dd > 30: gaps += 1
        line += seg[1:] if dd < 1 else seg
    return line, gaps

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

routes = []
for r in osm['elements']:
    t = r.get('tags', {})
    ways = [[xy(g) for g in m['geometry']] for m in r['members'] if m['type'] == 'way' and m.get('role', '') in ('', 'forward', 'backward') and m.get('geometry')]
    stops_raw = [(m.get('ref'), xy(m)) for m in r['members'] if m['type'] == 'node' and 'stop' in m.get('role', '') or (m['type'] == 'node' and 'platform' in m.get('role', ''))]
    if not ways: continue
    line, gaps = stitch(ways)
    total = sum(dist(line[i], line[i + 1]) for i in range(len(line) - 1))
    routes.append({'id': r['id'], 'ref': t.get('ref', ''), 'name': t.get('name', ''), 'from': t.get('from', ''), 'to': t.get('to', ''),
                   'ways': len(ways), 'gaps': gaps, 'km': round(total / 1000, 1), 'nstops': len(stops_raw), 'line': line, 'stops_raw': stops_raw})
for r in sorted(routes, key=lambda r: r['name']):
    print(r['id'], '|', r['ref'], '|', r['name'], '|', r['from'], '->', r['to'], '| ways', r['ways'], 'gaps', r['gaps'], '| km', r['km'], '| stops', r['nstops'])
json.dump(routes, open(os.path.join(d, 'bus_routes_raw.json'), 'w', encoding='utf-8'))

sp = os.path.join(d, 'bus_stops.json')
if os.path.exists(sp):
    names = {n['id']: n['tags'].get('name', '') for n in json.load(open(sp, encoding='utf-8'))['elements']}
    out = []
    for r in sorted(routes, key=lambda r: (r['name'] or r['ref'], r['from'])):
        if r['gaps'] > 1: continue
        line = []
        for p in r['line']:
            if not line or dist(line[-1], p) >= 3: line.append((round(p[0]), round(p[1])))
        # the relation lists stops in travel order: flip the stitched line if they mostly run backwards along it
        seq = [project(line, p)[0] for _, p in r['stops_raw']]
        fwd = sum(1 for a, b in zip(seq, seq[1:]) if b > a); back = sum(1 for a, b in zip(seq, seq[1:]) if b < a)
        if back > fwd: line.reverse()
        r['flipped'] = back > fwd
        stops = []
        for ref, p in r['stops_raw']:
            pos, off = project(line, p)
            if off < 60 and names.get(ref): stops.append((round(pos), names[ref]))
        stops.sort()
        ded = []
        for s in stops:
            if not ded or (ded[-1][1] != s[1] and s[0] - ded[-1][0] > 30): ded.append(s)
        loop = dist(line[0], line[-1]) < 150
        label = r['name'] or f"Route {r['ref']}"
        out.append({'name': label, 'ref': r['ref'], 'dir': 'Loop' if loop else f"{ded[0][1]} → {ded[-1][1]}", 'loop': loop,
                    'line': [c for p in line for c in p], 'stops': [[s[0], s[1]] for s in ded]})
    json.dump(out, open(os.path.join(d, 'bus.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print('kept', len(out), 'bytes', os.path.getsize(os.path.join(d, 'bus.json')))
    for o, r in zip(out, [r for r in sorted(routes, key=lambda r: (r['name'] or r['ref'], r['from'])) if r['gaps'] <= 1]):
        print(' ', o['name'], '|', o['dir'], '| flipped' if r.get('flipped') else '|', len(o['stops']), 'stops |', o['stops'][0][1], '...', o['stops'][-1][1])
