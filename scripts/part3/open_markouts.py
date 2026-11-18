import csv, collections, sys
# open_markouts.py DATE FILLS LOAD [GROUPS] : rows of data/part3/maker_markouts_by_open.csv for one open, from run_open.sh's fills (o.DATE.fills.tsv: 1 s / 5 s markout
# per maker fill) and the load per second (o.DATE.load.tsv). GROUPS = your own file "address<TAB>group", one account per line: P = cancel + place (the main makers),
# M, X, Y = modifiers (X and Y: two large modifiers we kept apart in other tables), anything else or absent = other (rules in part3.md, Data and method). makers: all, cancel_place, modifiers, other.
csv.field_size_limit(1 << 30)
date, ff, lf = sys.argv[1:4]; gf = sys.argv[4] if len(sys.argv) > 4 else 'groups.tsv'
G = {}
for l in open(gf):
    a, b = l.rstrip('\n').split('\t')[:2]; G[a[2:] if a.startswith('0x') else a] = b
load = {}
for r in csv.reader(open(lf), delimiter='\t' if lf.endswith('.tsv') else ','):
    try: load[int(r[0])] = int(r[1])
    except ValueError: pass
band = lambda a: '<20k' if a < 20000 else '20-40k' if a < 40000 else '40k+'
A = collections.defaultdict(lambda: [set(), 0, 0.0, 0.0, 0.0, 0.0]); miss = 0
for c, oid, user, coin, side, t, px, ntl, mk1, mk5, a1, bn, tid in csv.reader(open(ff), delimiter='\t'):
    s = int(t) // 1000
    if s not in load: miss += 1; continue
    ntl = float(ntl); g = {'P': 'cancel_place', 'M': 'modifiers', 'X': 'modifiers', 'Y': 'modifiers'}.get(G.get(user), 'other')
    for k in ('all', g):
        x = A[(band(load[s]), k)]; x[0].add(s); x[1] += 1; x[2] += ntl; x[3] += ntl * float(mk1); x[4] += ntl * float(mk5); x[5] += ntl * float(a1)
print(f'# {date}: load seconds {len(load)}, 40k+ {sum(1 for a in load.values() if a >= 40000)}, max {max(load.values())}, fills outside {miss}', file=sys.stderr)
for b in ('20-40k', '40k+', '<20k'):
    for k in ('all', 'cancel_place', 'modifiers', 'other'):
        ss, n, v, w1, w5, a = A[(b, k)]
        if v: print(f'{date},{b},{k},{len(ss)},{n},{v:.0f},{round(w1 / v, 4)},{round(w5 / v, 4)},{round(a / v, 4)}')
