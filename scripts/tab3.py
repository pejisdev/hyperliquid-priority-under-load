#!/usr/bin/env python3
# tab3.py [dir] (default data/opens) : US-open chronology from actlat v2 raw histograms (a.<day>.hist.tsv.gz + meta.<day>.tsv)
# median signed->block (ms) per family and load band; n in brackets when < 300
import gzip, glob, os, re, sys
from collections import defaultdict
d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'opens')
FAM = [  # label, regex on the kind
    ('cxl_f', r'^cancel(ByCloid)?_fast$'), ('cxl_nf', r'^cancel(ByCloid)?_nofast$'),
    ('ALO', r'^order_Alo(_x.*)?$'), ('ALOfee', r'^order_Alo_fee(_x.*)?$'),
    ('bMod_A', r'^batchModify_Alo(_x.*)?$'), ('bMod_G', r'^batchModify_Gtc(_x.*)?$'),
    ('mod_A', r'^modify_Alo$'), ('mod_G', r'^modify_Gtc$'),
    ('IOC8', r'^order_Ioc_8bps\+$'), ('IOC0', r'^order_Ioc_nofee$'), ('GTC', r'^order_Gtc$'),
]
BANDS = [('<20k', 0, 20000), ('30-40k', 30000, 40000), ('40k+', 40000, 10**9)]
def med(h):
    n = sum(h.values())
    if not n: return '-', 0
    t, acc = (n + 1) // 2, 0
    for b in sorted(h):
        acc += h[b]
        if acc >= t: return b + 5, n
for f in sorted(glob.glob(f'{d}/a.*.hist.tsv.gz')):
    day = re.search(r'a\.(\d{8})', f).group(1)
    mf = f'{d}/meta.{day}.tsv'
    hf = open(mf).read().split('\t')[-1].strip() if os.path.exists(mf) else '?'
    H = defaultdict(lambda: defaultdict(int))
    for line in gzip.open(f, 'rt'):
        k, m, lk, b, c = line.rstrip('\n').split('\t')
        lk, b, c = int(lk), int(b), int(c)
        for lab, rx in FAM:
            if re.match(rx, k):
                for bl, lo, hi in BANDS:
                    if lo <= lk < hi: H[(lab, bl)][b] += c
    cells = []
    for bl, _, _ in BANDS:
        row = []
        for lab, _ in FAM:
            v, n = med(H[(lab, bl)])
            row.append(f'{v}' + (f'({n})' if 0 < n < 300 else ''))
        cells.append(' '.join(f'{x:>5}' for x in row))
    print(f'{day} {hf:6} | ' + ' | '.join(cells))
print('cols per band: ' + ' '.join(l for l, _ in FAM) + '   bands: ' + ' | '.join(b for b, _, _ in BANDS))
