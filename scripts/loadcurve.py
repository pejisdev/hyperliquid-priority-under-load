#!/usr/bin/env python3
# loadcurve.py LABEL file.hist.tsv.gz... : median signed->block per family and 2.5k tx/s load step, pooled over the files
import gzip, re, sys
from collections import defaultdict
FAM = [('cxl_f', r'^cancel(ByCloid)?_fast$'), ('cxl_nf', r'^cancel(ByCloid)?_nofast$'), ('ALO', r'^order_Alo(_fee)?(_x.*)?$'),
       ('bMod_A', r'^batchModify_Alo(_x.*)?$'), ('mod_A', r'^modify_Alo$'), ('mod_G', r'^modify_Gtc$'), ('bMod_G', r'^batchModify_Gtc(_x.*)?$'),
       ('IOC8', r'^order_Ioc_8bps\+$'), ('IOC0', r'^order_Ioc_nofee$'), ('IOClow', r'^order_Ioc_fee<8bps$'), ('GTC', r'^order_Gtc$'),
       ('FrontendMarket', r'^order_FrontendMarket$'), ('scheduleCancel', r'^scheduleCancel$')]
cache = {}
def fam(k):
    if k not in cache: cache[k] = next((l for l, rx in FAM if re.match(rx, k)), None)
    return cache[k]
H = defaultdict(lambda: defaultdict(int))
for f in sys.argv[2:]:
    for line in gzip.open(f, 'rt'):
        k, m, lk, b, c = line.rstrip('\n').split('\t')
        l = fam(k)
        if l: H[(l, int(lk))][int(b)] += int(c); H[(l, -1 if int(lk) < 40000 else 40000)][int(b)] += 0
        if l and int(lk) >= 40000: H[(l, 99999)][int(b)] += int(c)
for (l, lk), h in sorted(H.items()):
    n = sum(h.values())
    if not n: continue
    t, acc = (n + 1) // 2, 0
    for b in sorted(h):
        acc += h[b]
        if acc >= t: print(f'{sys.argv[1]}\t{l}\t{lk}\t{n}\t{b + 5}'); break
