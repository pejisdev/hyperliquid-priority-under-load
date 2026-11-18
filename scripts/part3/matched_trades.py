import csv, collections, sys
# matched_trades.py NAME DATE... : matched trades (maker quote + taker order tied to their signed orders) in the seconds above 40k tx/s of the given opens,
# pooled: who signed last, the result by gap (data/part3/head_start_buckets.csv), and takers by priority-fee lane. Reads run_open.sh's o.DATE.* and groups.tsv
# (see open_markouts.py) in the current directory. Markouts are capped at 25 bps per trade in the gap table, at 50 bps in the totals it prints.
csv.field_size_limit(1 << 30)
cap = lambda v: max(-25.0, min(25.0, v)); cap50 = lambda v: max(-50.0, min(50.0, v))
G = {}
for l in open('groups.tsv'):
    a, b = l.rstrip('\n').split('\t')[:2]; G[a[2:] if a.startswith('0x') else a] = b
def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))] if v else None
name, dates = sys.argv[1], sys.argv[2:]
R = []; LANE = {k: [[], 0.0] for k in ('nofee', '<8bps', '8bps+')}; FEE = collections.defaultdict(lambda: [0.0, 0.0, 0]); MK = [0.0, 0.0, 0.0, 0.0]; tot = 0.0; nsec = 0
BK = collections.Counter(); BKM = collections.Counter()
for d in dates:
    load = {}
    for r in csv.reader(open(f'o.{d}.load.tsv'), delimiter='\t'):
        try: load[int(r[0])] = int(r[1])
        except ValueError: pass
    place = collections.defaultdict(list)
    for c, bms, sms, kind, asset, buy, px in csv.reader(open(f'o.{d}.place.tsv'), delimiter='\t'): place[c[2:]].append((int(bms), int(sms), kind))
    tk = {r[0]: r[1] for r in csv.reader(open(f'o.{d}.takers.tsv'), delimiter='\t')}
    hype = float(open(f'o.{d}.hype').read()); pg = {r[0]: float(r[1]) for r in csv.reader(open(f'o.{d}.pg.tsv'), delimiter='\t')}
    def last(c, t):
        pl = place.get(c)
        if not pl: return None
        cand = [x for x in pl if x[0] <= t]
        return max(cand) if cand else None
    seen = set(); secs = set()
    for c, oid, user, coin, side, t, px, ntl, mk1, mk5, a1, bn, tid in csv.reader(open(f'o.{d}.fills.tsv'), delimiter='\t'):
        t, ntl = int(t), float(ntl); s = t // 1000
        if load.get(s, 0) < 40000: continue
        tot += ntl; secs.add(s); p1 = ntl * cap50(float(mk1)) / 1e4
        MK[0] += ntl; MK[1] += p1
        if G.get(user) == 'P': MK[2] += ntl; MK[3] += p1
        bps = pg.get(tid, 0.0) * hype / ntl * 1e4
        k = 'nofee' if tid not in pg else ('8bps+' if bps >= 7.5 else ('1-8bps' if bps >= 1 else '<1bps'))
        a = FEE[k]; a[0] += ntl; a[1] -= p1; a[2] += 1
        tc = tk.get(tid)
        q = last(tc, t) if tc and tc != '0' * 32 else None
        if not q or q[0] != t or not (50 <= q[0] - q[1] < 2000): continue
        tfl = q[0] - q[1]
        ln = '8bps+' if bps >= 7.5 else ('<8bps' if bps > 0 else 'nofee')
        LANE[ln][1] += ntl
        if (tc, t) not in seen: seen.add((tc, t)); LANE[ln][0].append(tfl)
        m = last(c, t) if c != '0' * 32 else None
        if not m or not m[2].endswith('_Alo'): continue
        mfl, age = m[0] - m[1], t - m[0]
        if not (50 <= mfl < 2000) or age >= 1000: continue
        gap = q[1] - m[1]
        R.append((ntl, float(mk1), mfl, tfl, age, gap))
        b = '<0' if gap < 0 else '0-100' if gap < 100 else '100-200' if gap < 200 else '200-300' if gap < 300 else '300-400' if gap < 400 else '400-600' if gap < 600 else '600+'
        BK[b] += ntl; BKM[b] += ntl * cap(float(mk1))
    nsec += len(secs); del place, tk, pg
    print('loaded', d, file=sys.stderr, flush=True)
v = sum(x[0] for x in R)
lo = [x for x in R if x[5] < 0]; hi = [x for x in R if x[5] >= 0]; sl = sum(x[0] for x in lo) / v
mk = lambda rs: sum(x[0] * cap(x[1]) for x in rs) / max(1.0, sum(x[0] for x in rs))
slow = sum(x[0] for x in R if x[2] > x[3]) / v; same = sum(x[0] for x in R if x[4] == 0) / v
print(f'== {name} ({" ".join(dates)}): seconds 40k+ {nsec}; maker $ {tot / 1e6:.0f}M; all makers {1e4 * MK[1] / MK[0]:+.2f} bps; main makers {1e4 * MK[3] / max(1.0, MK[2]):+.2f} bps on ${MK[2] / 1e6:.0f}M')
print(f'   young matched $ {v / 1e6:.0f}M ({100 * v / tot:.0f}%), n {len(R)}')
print(f'   maker quote flight p50 {pct([x[2] for x in R], .5)}  taker flight p50 {pct([x[3] for x in R], .5)}  age in book p25/p50/p75 {pct([x[4] for x in R], .25)}/{pct([x[4] for x in R], .5)}/{pct([x[4] for x in R], .75)}  gap p50 {pct([x[5] for x in R], .5)}')
print(f'   maker decided last {100 * sl:.0f}% of $ ({mk(lo):+.2f} bps) | taker decided last {100 * (1 - sl):.0f}% ({mk(hi):+.2f} bps) | all {mk(R):+.2f}')
print(f'   maker quote travelled longer than the taker order: {100 * slow:.0f}% of $; filled in the block it landed: {100 * same:.0f}%')
print('   gap buckets (share of matched $, markout): ' + '  '.join(f'{b} {BK[b] / v:.4f} {BKM[b] / BK[b]:+.2f}' for b in ('<0', '0-100', '100-200', '200-300', '300-400', '400-600', '600+') if BK[b]))
for k in ('nofee', '<8bps', '8bps+'):
    fl, ntl = LANE[k]
    if fl: print(f'   taker lane {k:6s}: matched taker orders {len(fl):7d}, flight p25/p50/p75 {pct(fl, .25)}/{pct(fl, .5)}/{pct(fl, .75)}, $ {ntl / 1e6:.0f}M')
for k in ('nofee', '<1bps', '1-8bps', '8bps+'):
    a = FEE[k]
    if a[0]: print(f'   fee {k:7s} ${a[0] / 1e6:8.1f}M  {100 * a[0] / tot:5.1f}% of taker volume  fills {a[2]:7d}  taker {1e4 * a[1] / a[0]:+.2f} bps (${a[1] / 1e3:+.0f}k)')
