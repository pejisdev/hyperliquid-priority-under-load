#!/usr/bin/env python3
"""compare.py MINE OURS : compares the histograms you rebuilt (fetch_open.py, default out/) with the published ones (data/).

For every open in MINE/opens.csv: rows of the histogram (kind, minute, load bucket, 10 ms bin, count) identical or not,
then the medians of the main families at 40k+ tx/s on both sides.
"""
import csv, gzip, os, re, sys

MAIN = [('fast cancel', r'^cancel(ByCloid)?_fast$'), ('ALO order', r'^order_Alo(_x.*)?$'), ('batchModify ALO', r'^batchModify_Alo(_x.*)?$'),
        ('modify ALO', r'^modify_Alo$'), ('IOC 8 bps', r'^order_Ioc_8bps\+$'), ('IOC no fee', r'^order_Ioc_nofee$')]

def load(d, day):
    h = {}
    with gzip.open(os.path.join(d, 'opens', f'{day}.hist.csv.gz'), 'rt') as f:
        next(f)
        for line in f:
            k, m, lk, b, c = line.rstrip('\n').split(',')
            h[(k, int(m), int(lk), int(b))] = int(c)
    return h

def med40(h, rx):
    acc = {}
    for (k, m, lk, b), c in h.items():
        if lk >= 40000 and re.match(rx, k): acc[b] = acc.get(b, 0) + c
    n = sum(acc.values())
    if not n: return '-', 0
    t, s = (n + 1) // 2, 0
    for b in sorted(acc):
        s += acc[b]
        if s >= t: return b + 5, n

mine = sys.argv[1] if len(sys.argv) > 1 else 'out'
ours = sys.argv[2] if len(sys.argv) > 2 else 'data'
for r in csv.DictReader(open(os.path.join(mine, 'opens.csv'))):
    day = r['date']
    if not os.path.exists(os.path.join(ours, 'opens', f'{day}.hist.csv.gz')): print(f'{day}: not in {ours}'); continue
    a, b = load(mine, day), load(ours, day)
    same = sum(1 for k, v in a.items() if b.get(k) == v)
    diff = len(set(a) | set(b)) - same
    print(f'{day}: {len(a):,} rows yours, {len(b):,} ours, {same:,} identical, {diff:,} different'
          + ('  -> identical' if diff == 0 else '  (different files? compare opens.csv, or use --like)'))
    print(f'  {"median at 40k+ tx/s, ms":26} {"yours":>12} {"ours":>12}')
    for name, rx in MAIN:
        (ma, na), (mb, nb) = med40(a, rx), med40(b, rx)
        print(f'  {name:26} {str(ma):>5} n={na:<10,} {str(mb):>5} n={nb:<10,}')
