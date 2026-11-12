#!/usr/bin/env python3
"""make_tables.py [DATA_DIR] : every table the figure reads, from the raw histograms in DATA_DIR/opens (default data/; one pass, no download).

Inputs : data/opens/<date>.hist.csv.gz (actlat output, gzipped) and data/opens.csv
Outputs: data/latency_by_open.csv       date,hardfork,load_band,family,n,median_ms
         data/latency_40k_by_period.csv period,family,n,median_ms
         data/load_curve_2500.csv       period,family,load_from,n,median_ms
         data/load_curve_5000.csv       period,family,load_from,n,median_ms
Medians are taken on 10 ms bins and reported as the bin's middle (lower edge + 5).
"""
import csv, gzip, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data')

# family -> regex on actlat's kind. alo_order and alo_order_fee are split by priority fee; alo_order_any pools both.
FAMILIES = [
    ('cancel_fast', r'^cancel(ByCloid)?_fast$'), ('cancel_nofast', r'^cancel(ByCloid)?_nofast$'),
    ('alo_order', r'^order_Alo(_x.*)?$'), ('alo_order_fee', r'^order_Alo_fee(_x.*)?$'), ('alo_order_any', r'^order_Alo(_fee)?(_x.*)?$'),
    ('batchmodify_alo', r'^batchModify_Alo(_x.*)?$'), ('modify_alo', r'^modify_Alo$'),
    ('batchmodify_gtc', r'^batchModify_Gtc(_x.*)?$'), ('modify_gtc', r'^modify_Gtc$'),
    ('ioc_8bps', r'^order_Ioc_8bps\+$'), ('ioc_under_8bps', r'^order_Ioc_fee<8bps$'), ('ioc_nofee', r'^order_Ioc_nofee$'),
    ('gtc_order', r'^order_Gtc$'), ('frontend_market', r'^order_FrontendMarket$'), ('schedule_cancel', r'^scheduleCancel$'),
]
BY_OPEN = ['cancel_fast', 'cancel_nofast', 'alo_order', 'alo_order_fee', 'batchmodify_alo', 'batchmodify_gtc',
           'modify_alo', 'modify_gtc', 'ioc_8bps', 'ioc_nofee', 'gtc_order']
CURVES = [f for f, _ in FAMILIES if f not in ('alo_order', 'alo_order_fee')]
BANDS = [('<20k', 0, 20000), ('30-40k', 30000, 40000), ('40k+', 40000, 10**9)]

def period(date):
    return 'sep11-nov05' if date <= '2026-11-05' else {'2026-11-06': 'nov06', '2026-11-11': 'nov11', '2026-11-12': 'nov12'}.get(date)

def median(h):
    n = sum(h.values())
    t, acc = (n + 1) // 2, 0
    for b in sorted(h):
        acc += h[b]
        if acc >= t: return n, b + 5

opens = list(csv.DictReader(open(os.path.join(DATA, 'opens.csv'))))
fam_of = {}
by_open, k40, c25, c50 = (defaultdict(lambda: defaultdict(int)) for _ in range(4))
for o in opens:
    date, per = o['date'], period(o['date'])
    with gzip.open(os.path.join(DATA, 'opens', f'{date}.hist.csv.gz'), 'rt') as f:
        next(f)
        for line in f:
            kind, _, lk, b, c = line.rstrip('\n').split(',')
            if kind not in fam_of: fam_of[kind] = [fam for fam, rx in FAMILIES if re.match(rx, kind)]
            fams = fam_of[kind]
            if not fams: continue
            lk, b, c = int(lk), int(b), int(c)
            band = next((name for name, lo, hi in BANDS if lo <= lk < hi), None)
            for fam in fams:
                if band and fam in BY_OPEN: by_open[(date, band, fam)][b] += c
                if per and fam in CURVES:
                    c25[(per, fam, lk)][b] += c
                    c50[(per, fam, lk // 5000 * 5000)][b] += c
                    if lk >= 40000: k40[(per, fam)][b] += c

def write(name, header, rows):
    with open(os.path.join(DATA, name), 'w', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(header); w.writerows(rows)

order = {d['date']: i for i, d in enumerate(opens)}
hf = {d['date']: d['hardfork'] for d in opens}
bi = {b: i for i, (b, _, _) in enumerate(BANDS)}; fi = {f: i for i, f in enumerate(BY_OPEN)}
write('latency_by_open.csv', ['date', 'hardfork', 'load_band', 'family', 'n', 'median_ms'],
      [(d, hf[d], b, fam, *median(h)) for (d, b, fam), h in sorted(by_open.items(), key=lambda x: (order[x[0][0]], bi[x[0][1]], fi[x[0][2]]))])
PER = ['sep11-nov05', 'nov06', 'nov11', 'nov12']; ci = {f: i for i, f in enumerate(CURVES)}
key = lambda x: (PER.index(x[0][0]), ci[x[0][1]]) + tuple(x[0][2:])
write('latency_40k_by_period.csv', ['period', 'family', 'n', 'median_ms'], [(p, fam, *median(h)) for (p, fam), h in sorted(k40.items(), key=key)])
for name, t in (('load_curve_2500.csv', c25), ('load_curve_5000.csv', c50)):
    write(name, ['period', 'family', 'load_from', 'n', 'median_ms'], [(p, fam, lk, *median(h)) for (p, fam, lk), h in sorted(t.items(), key=key)])
print(f'tables written in {DATA}/')
