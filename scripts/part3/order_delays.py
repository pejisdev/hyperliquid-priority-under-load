import gzip, re, sys, collections
# order_delays.py DATE HARDFORK HIST : the rows of data/part3/order_delays_by_open.csv for one more open, seconds above 40k tx/s only, from actlat's histogram
# (<date>.hist.csv or .csv.gz, as in data/opens). Same families and same median on 10 ms bins as scripts/make_tables.py. Output: date,hardfork,load_band,family,n,median_ms
FAMILIES = [('cancel_fast', r'^cancel(ByCloid)?_fast$'), ('cancel_nofast', r'^cancel(ByCloid)?_nofast$'), ('alo_order', r'^order_Alo(_x.*)?$'), ('alo_order_fee', r'^order_Alo_fee(_x.*)?$'),
            ('batchmodify_alo', r'^batchModify_Alo(_x.*)?$'), ('batchmodify_gtc', r'^batchModify_Gtc(_x.*)?$'), ('modify_alo', r'^modify_Alo$'), ('modify_gtc', r'^modify_Gtc$'),
            ('ioc_8bps', r'^order_Ioc_8bps\+$'), ('ioc_nofee', r'^order_Ioc_nofee$'), ('gtc_order', r'^order_Gtc$')]
DATE, HF, HIST = sys.argv[1:4]
H = collections.defaultdict(lambda: collections.defaultdict(int)); fam_of = {}
f = gzip.open(HIST, 'rt') if HIST.endswith('.gz') else open(HIST); next(f)
for line in f:
    kind, _, lk, b, c = line.rstrip('\n').split(',')
    if int(lk) < 40000: continue
    if kind not in fam_of: fam_of[kind] = [fam for fam, rx in FAMILIES if re.match(rx, kind)]
    for fam in fam_of[kind]: H[fam][int(b)] += int(c)
for fam, _ in FAMILIES:
    h = H[fam]; n = sum(h.values())
    if not n: continue
    t, acc = (n + 1) // 2, 0
    for b in sorted(h):
        acc += h[b]
        if acc >= t: print(f'{DATE},{HF},40k+,{fam},{n},{b + 5}'); break
