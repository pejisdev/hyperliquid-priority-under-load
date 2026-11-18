import csv, sys, collections, os
# by_group.py DIR LABELS GROUPS DATE... : (1) maker and taker result at 1 s per shown label, with the rest split by maker style;
# (2) taker result and order flight time by lane of the taker order (priority fee or not). Seconds above 40k tx/s, before / since Nov 6.
# DIR holds run_open.sh's o.DATE.*; LABELS = your own file "address<TAB>name<TAB>source" (addresses as in the fills, hex without 0x); GROUPS as in open_markouts.py.
# SHOW=name|name|... picks the labels that get their own row (the paper's firms and linked groups; their names and addresses are not published).
# CAP=1e9 for the paper's table (data/part3/result_by_group.csv): no cap on a trade's result.
csv.field_size_limit(1 << 30)
DIR, LF, GF, DATES = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
SHOW = set(os.environ.get('SHOW', '').split('|')) - {''}
L = {}
for a, n, c in csv.reader(open(LF), delimiter='\t'): L.setdefault(a, n)
G = {a[2:] if a.startswith('0x') else a: b for a, b in (l.split('\t') for l in open(GF).read().split('\n') if l)}
STY = {'P': 'rest: main makers (cancel + place)', 'M': 'rest: modifiers', 'X': 'rest: X', 'Y': 'rest: Y'}
def cat(u):
    n = L.get(u)
    if n in SHOW: return n
    return STY.get(G.get(u), 'rest: other')
CAPV = float(os.environ.get('CAP', 50))   # CAP=1e9: no cap, the definition of the paper's totals (data/part3/maker_markouts_by_open.csv)
cap = lambda v: max(-CAPV, min(CAPV, v))
def Z(): return {p: dict(mn=0.0, m1=0.0, tn=0.0, t1=0.0, ad=set()) for p in ('pre', 'post')}
E = collections.defaultdict(Z)
LN = {p: collections.defaultdict(lambda: dict(n=0.0, p=0.0, fl=[], by=collections.defaultdict(lambda: [0.0, 0.0]))) for p in ('pre', 'post')}
for D in DATES:
    per = 'pre' if D < '2026-11-06' else 'post'; p = f'{DIR}/o.{D}'
    place = collections.defaultdict(list)
    for c, bms, sms, kind, asset, buy, px in csv.reader(open(p + '.place.tsv'), delimiter='\t'): place[c[2:]].append((int(bms), int(sms), kind))
    load = {int(s): int(n) for s, n in csv.reader(open(p + '.load.tsv'), delimiter='\t')}
    tk = {r[0]: (r[1], r[2]) for r in csv.reader(open(p + '.takers.tsv'), delimiter='\t')}
    for c, oid, user, coin, side, t, px, ntl, mk1, mk5, a1, bn, tid in csv.reader(open(p + '.fills.tsv'), delimiter='\t'):
        t = int(t)
        if load.get(t // 1000, 0) < 40000: continue
        ntl = float(ntl); p1 = ntl * cap(float(mk1)) / 1e4
        e = E[cat(user)][per]; e['mn'] += ntl; e['m1'] += p1; e['ad'].add(user)
        tc = tk.get(tid)
        if not tc: continue
        tu = tc[1]; ct = cat(tu); e = E[ct][per]; e['tn'] += ntl; e['t1'] -= p1; e['ad'].add(tu)
        lane = 'unmatched'
        if tc[0] != '0' * 32:
            q = [x for x in place.get(tc[0], ()) if x[0] <= t]
            q = max(q) if q else None
            if q and q[0] == t:
                k = q[2]; lane = 'fee' if k.startswith('order_fee') else ('ioc' if k.endswith('_Ioc') else ('gtc' if k.endswith('_Gtc') else 'other'))
                x = LN[per][lane]
                if 50 <= q[0] - q[1] < 2000 and len(x['fl']) < 400000: x['fl'].append(q[0] - q[1])
                LN[per][lane]['by'][k][0] += ntl; LN[per][lane]['by'][k][1] -= p1
        x = LN[per][lane]; x['n'] += ntl; x['p'] -= p1
        x['by']['cat:' + ct][0] += ntl; x['by']['cat:' + ct][1] -= p1
    print('loaded', D, file=sys.stderr, flush=True)
print('## by category: cat, addrs, then pre/post maker ntl, maker pnl, taker ntl, taker pnl')
for n, v in sorted(E.items()):
    a, b = v['pre'], v['post']
    print('\t'.join([n, str(len(a['ad'] | b['ad']))] + [f'{x[k]:.0f}' for x in (a, b) for k in ('mn', 'm1', 'tn', 't1')]))
print('## taker lanes: period, lane, ntl, pnl, bps, median flight ms, n flights')
for per in ('pre', 'post'):
    for lane, x in sorted(LN[per].items()):
        fl = sorted(x['fl'])
        print('\t'.join([per, lane, f"{x['n']:.0f}", f"{x['p']:.0f}", f"{1e4 * x['p'] / x['n']:+.2f}", str(fl[len(fl) // 2]) if fl else '-', str(len(fl))]))
        for k, (n_, p_) in sorted(x['by'].items(), key=lambda kv: -kv[1][0])[:14]:
            print('\t\t' + '\t'.join([k, f'{n_:.0f}', f'{p_:.0f}', f'{1e4 * p_ / n_:+.2f}' if n_ else '-']))
