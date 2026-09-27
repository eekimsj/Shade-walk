import json, math, re, collections, sys, os
d = os.path.dirname(os.path.abspath(__file__))
osm = json.load(open(os.path.join(d, 'osm2.json'), encoding='utf-8'))
LAT0, LON0 = 30.6120, -96.3425
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 110574.0
def xy(lat, lon):
    return (round((lon - LON0) * KX, 1), round((lat - LAT0) * KY, 1))

def num(s):
    if s is None: return None
    m = re.match(r'\s*([0-9.]+)', s)
    return float(m.group(1)) if m else None

buildings, names = [], []
trees = []
adj_nodes = {}
edges = set()
walk_ok = re.compile(r'footway|path|pedestrian|steps|living_street|residential|service|tertiary|secondary|unclassified|cycleway')
for el in osm['elements']:
    t = el.get('tags', {})
    if el['type'] == 'node' and t.get('natural') == 'tree':
        trees.append(xy(el['lat'], el['lon']))
    elif 'building' in t and ('geometry' in el or el['type'] == 'relation'):
        if el['type'] == 'relation':
            segs = [[xy(g['lat'], g['lon']) for g in m.get('geometry', [])] for m in el.get('members', []) if m.get('role') == 'outer' and m.get('geometry')]
            # stitch outer segments into one ring
            ring = segs.pop(0) if segs else []
            while segs:
                for i, s in enumerate(segs):
                    if s[0] == ring[-1]: ring += s[1:]; break
                    if s[-1] == ring[-1]: ring += s[::-1][1:]; break
                else:
                    break
                segs.pop(i)
            pts = ring
        else:
            pts = [xy(g['lat'], g['lon']) for g in el['geometry']]
        if len(pts) > 1 and pts[0] == pts[-1]: pts = pts[:-1]
        clean = []
        for p in pts:
            if not clean or abs(p[0]-clean[-1][0]) + abs(p[1]-clean[-1][1]) > 0.8: clean.append(p)
        if len(clean) < 3: continue
        h = num(t.get('height'))
        if h is None:
            lv = num(t.get('building:levels'))
            if lv: h = lv * 3.8 + 1.5
        est = h is None
        if h is None:
            bt = t.get('building')
            h = {'house': 7, 'garage': 4, 'shed': 3, 'roof': 5, 'parking': 12, 'stadium': 40}.get(bt, 12)
        name = t.get('name', '')
        KNOWN = {'Rudder Tower': 56, 'Eller Oceanography and Meteorology Building': 60, 'Kyle Field': 55,
                 'Sterling C. Evans Library': 26, 'Reed Arena': 30, 'Memorial Student Center': 18,
                 'Zachry Engineering Education Complex': 22, 'Academic Building': 30,
                 'Jack K. Williams Administration Building': 20, 'Student Recreation Center': 16}
        if est and name in KNOWN: h = KNOWN[name]
        flat = [c for p in clean for c in p]
        buildings.append([round(h, 1), 1 if est else 0, name, flat])
    elif el['type'] == 'way' and 'highway' in t and 'geometry' in el:
        hw = t['highway']
        if not walk_ok.search(hw): continue
        if t.get('foot') == 'no' or t.get('access') in ('private', 'no'): continue
        ids = el['nodes']
        for i, nid in enumerate(ids):
            adj_nodes[nid] = xy(el['geometry'][i]['lat'], el['geometry'][i]['lon'])
        for a, b in zip(ids, ids[1:]):
            if a != b: edges.add((min(a, b), max(a, b)))

# largest connected component
adj = collections.defaultdict(list)
for a, b in edges:
    adj[a].append(b); adj[b].append(a)
seen, best = set(), []
for s in adj:
    if s in seen: continue
    comp, st = [], [s]; seen.add(s)
    while st:
        u = st.pop(); comp.append(u)
        for v in adj[u]:
            if v not in seen: seen.add(v); st.append(v)
    if len(comp) > len(best): best = comp
keep = set(best)
idx = {nid: i for i, nid in enumerate(best)}
nodes = [c for nid in best for c in adj_nodes[nid]]
E = [c for a, b in edges if a in keep for c in (idx[a], idx[b])]

canopy = json.load(open(os.path.join(d, 'canopy.json')))
out = {'origin': [LAT0, LON0], 'b': buildings, 'n': nodes, 'e': E, 'c': canopy}
s = json.dumps(out, separators=(',', ':'), ensure_ascii=False)
open(os.path.join(d, 'campus.json'), 'w', encoding='utf-8').write(s)
print('buildings', len(buildings), 'est', sum(b[1] for b in buildings), 'trees', len(trees), 'nodes', len(best), 'edges', len(E)//2, 'bytes', len(s))
named = sorted(set(b[2] for b in buildings if b[2]))
print(len(named))
print(' | '.join(named))
