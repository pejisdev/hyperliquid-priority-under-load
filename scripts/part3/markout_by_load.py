import csv, sys, collections
# markout_by_load.py GROUPS NAME=DATE,DATE... : maker result at 1 s (bps, no cap) by load bin of the fill's second, for the main makers (group P of GROUPS, see open_markouts.py) and for all makers.
# Reads run_open.sh's o.DATE.fills.tsv and o.DATE.load.tsv in the current directory. Example: markout_by_load.py groups.tsv nov16-17=2026-11-16,2026-11-17
csv.field_size_limit(1 << 30)
G = {a[2:] if a.startswith('0x') else a: b for a, b in (l.split('\t') for l in open(sys.argv[1]).read().split('\n') if l)}
BINS = [(0, 20000, '<20k'), (20000, 30000, '20-30k'), (30000, 40000, '30-40k'), (40000, 45000, '40-45k'), (45000, 50000, '45-50k'), (50000, 10**9, '50k+')]
for spec in sys.argv[2:]:
    name, dates = spec.split('='); A = collections.defaultdict(lambda: [0.0, 0.0, 0]); S = collections.Counter()
    for D in dates.split(','):
        load = {int(s): int(n) for s, n in csv.reader(open(f'o.{D}.load.tsv'), delimiter='\t')}
        for n in load.values(): S[next(b for lo, hi, b in BINS if lo <= n < hi)] += 1
        for c, oid, user, coin, side, t, px, ntl, mk1, mk5, a1, bn, tid in csv.reader(open(f'o.{D}.fills.tsv'), delimiter='\t'):
            b = next(b for lo, hi, b in BINS if lo <= load.get(int(t) // 1000, 0) < hi); ntl = float(ntl)
            for g in ('all', 'main' if G.get(user) == 'P' else None):
                if g: x = A[(g, b)]; x[0] += ntl; x[1] += ntl * float(mk1) / 1e4; x[2] += 1
    print(f'== {name}')
    for lo, hi, b in BINS:
        print(f'   {b:7s} seconds {S[b]:5d} | ' + ' | '.join(f'{g} {1e4 * A[(g, b)][1] / A[(g, b)][0]:+.2f} bps on ${A[(g, b)][0] / 1e6:.0f}M (${A[(g, b)][1] / 1e3:+.0f}k)' if A[(g, b)][0] else f'{g} -' for g in ('main', 'all')))
