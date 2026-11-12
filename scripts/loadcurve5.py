#!/usr/bin/env python3
# loadcurve5.py LABEL file.hist.tsv.gz... : median signed->block per family and 5k tx/s load step (99999 = all 40k+), pooled
import gzip, re, sys
from collections import defaultdict
FAM = [('cxl_f', r'^cancel(ByCloid)?_fast$'), ('ALO', r'^order_Alo(_fee)?(_x.*)?$'), ('IOC8', r'^order_Ioc_8bps\+$'), ('IOC0', r'^order_Ioc_nofee$'), ('bMod_A', r'^batchModify_Alo(_x.*)?$'), ('mod_A', r'^modify_Alo$')]
cache = {}
def fam(k):
    if k not in cache: cache[k] = next((l for l, rx in FAM if re.match(rx, k)), None)
    return cache[k]
H = defaultdict(lambda: defaultdict(int))
for f in sys.argv[2:]:
    for line in gzip.open(f, 'rt'):
        k, m, lk, b, c = line.rstrip('\n').split('\t')
        l = fam(k)
        if not l: continue
        lk = int(lk); H[(l, lk // 5000 * 5000)][int(b)] += int(c)
for (l, lk), h in sorted(H.items()):
    n = sum(h.values()); t, acc = (n + 1) // 2, 0
    for b in sorted(h):
        acc += h[b]
        if acc >= t: print(f'{sys.argv[1]}\t{l}\t{lk}\t{n}\t{b + 5}'); break
