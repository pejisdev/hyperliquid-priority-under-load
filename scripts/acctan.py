# per-account check, 40k+ seconds: same accounts, fast cancel vs ALO order / batchModify ALO
import collections, sys
P = sys.argv[1] if len(sys.argv) > 1 else 'acct12'
R = collections.defaultdict(dict)  # user -> kind -> (n, p50)
for l in open(P + '.tsv'):
    u, k, b, n, p25, p50, p75 = l.split('\t')
    if b != '40k+': continue
    R[u][k] = (int(n), int(p50))
print('coverage at 40k+ (kind, total, resolved %):')
for l in sorted(open(P + '.cover.tsv'), key=lambda x: -int(x.split('\t')[2])):
    k, b, t, r = l.split('\t')
    if b == '40k+' and int(t) > 20000: print(f'  {k:28s} {int(t):9d} {100*int(r)/int(t):5.1f} %')
def canc(d):
    c = [d[k] for k in ('cancel_fast', 'cancelByCloid_fast') if k in d]
    return max(c) if c else None
for ak in ('order_Alo', 'order_Alo_fee', 'batchModify_Alo'):
    tot = sum(d[ak][0] for d in R.values() if ak in d)
    users = sorted(((d[ak][0], d[ak][1], canc(d), u) for u, d in R.items() if ak in d), reverse=True)
    print(f'\n== {ak}: {len(users)} accounts, {tot} actions resolved at 40k+')
    top = [x[0] for x in users]
    print('  volume share top1/5/10/25: ' + ' / '.join(f'{100*sum(top[:k])/tot:.0f} %' for k in (1, 5, 10, 25)))
    w_slow = sum(n for n, p, c, u in users if p >= 400)
    print(f'  share of {ak} volume from accounts whose median is >= 400 ms: {100*w_slow/tot:.0f} %')
    both = [(n, p, c[1], c[0]) for n, p, c, u in users if c and n >= 30 and c[0] >= 30]
    vb = sum(x[0] for x in both)
    print(f'  accounts with >=30 of both {ak} and fast cancels: {len(both)}, {100*vb/tot:.0f} % of {ak} volume')
    pat = [x for x in both if x[1] >= 400 and x[2] <= 300]
    print(f'    of which {ak} median >= 400 AND own fast-cancel median <= 300: {len(pat)} accounts, {100*sum(x[0] for x in pat)/max(vb,1):.0f} % of that volume')
    d = sorted(x[1] - x[2] for x in both)
    if d: print(f'    per-account gap ({ak} median - own cancel median), ms: p10 {d[len(d)//10]}  p50 {d[len(d)//2]}  p90 {d[9*len(d)//10]}')
    print('    top 12 by volume (n, median, own cancel median, cancel n):')
    for n, p, c, u in users[:12]: print(f'      {n:7d} {p:5d} {c[1] if c else "-":>5} {c[0] if c else "-":>7}  {u[:10]}')
    small = [p for n, p, c, u in users if 30 <= n < 1000]
    small.sort()
    if small: print(f'  small accounts (30-999 actions): {len(small)}, median of their medians {small[len(small)//2]} ms')
