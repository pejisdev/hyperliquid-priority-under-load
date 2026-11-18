import csv, sys, glob, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib import font_manager as fm
# part3_figure_full.py DATA_DIR OUT : the full one-page version of part 3 (figure/hyperliquid-priority-part3-full.png) from the tables in data/part3:
# the three charts of part3_figure.py, six notes and the whole method. The texts carry figures measured outside these tables (Nov 14, matched trades of Nov 16-17,
# delays by load): they are in part3.md with their scripts. Font: Liberation Sans (the last check fails if another font makes a line too long).
DD, OUT = sys.argv[1:3]
MK, BK, AK, DK, GRP = (f'{DD}/{n}.csv' for n in ('maker_markouts_by_open', 'head_start_buckets', 'maker_markouts_after_nov13', 'order_delays_by_open', 'result_by_group'))
GK = None   # optional third bar of chart 3 (maker result by group on the opens after Nov 13), not drawn
for f in glob.glob('/usr/share/fonts/truetype/liberation/LiberationSans-*.ttf'): fm.fontManager.addfont(f)
plt.rcParams.update({'font.family': 'Liberation Sans', 'font.size': 10.5, 'axes.edgecolor': '#b5b5b5', 'axes.linewidth': 0.8, 'text.parse_math': False,
                     'xtick.color': '#555', 'ytick.color': '#555', 'axes.labelcolor': '#555', 'text.color': '#1a1a1a'})
OR, GR, BL, GN, DG = '#e8673a', '#a8a59c', '#2f74c9', '#20a67a', '#7d7a72'
INK, SUB, BG = '#1a1a1a', '#666', '#f4f4f2'
SPLIT, END = '2026-11-06', '2026-11-14'
mon = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
lab = lambda d: f'{int(d[8:])} {mon[int(d[5:7]) - 1]}'
neg = lambda s: s.replace('-', '−')

# ---------- data
M = {}
for r in [r for f in (MK, AK) for r in csv.DictReader(open(f))]:
    M[(r['date'], r['load_band'], r['makers'])] = dict(s=int(r['seconds']), v=float(r['notional_usd']), m1=float(r['markout_1s_bps']), a=float(r['abs_move_1s_bps']))
D = sorted({k[0] for k in M})
PRE, POST, AFTER = [d for d in D if d < SPLIT], [d for d in D if SPLIT <= d < END], [d for d in D if d >= END]
def agg(dates, band, g):
    ks = [(d, band, g) for d in dates if (d, band, g) in M]
    v = sum(M[k]['v'] for k in ks); w = sum(M[k]['v'] * M[k]['m1'] for k in ks)
    return dict(v=v, m1=w / v, s=sum(M[k]['s'] for k in ks))
THIN = {d for d in D if M[(d, '40k+', 'all')]['s'] < 60}
AG = {r['group']: float(r['maker_bps']) for r in csv.DictReader(open(GK))} if GK else None   # maker result by group over the opens after Nov 13
AFTER_LBL = 'Nov ' + ' and '.join(str(int(d[8:])) for d in AFTER)
L = {(r['date'], r['family']): int(r['median_ms']) for r in csv.DictReader(open(DK))}; HF = {r['date']: r['hardfork'] for r in csv.DictReader(open(DK))}
assert all((d, f) in L for d in D for f in ('batchmodify_alo', 'alo_order', 'ioc_nofee', 'ioc_8bps', 'cancel_fast')), [d for d in D if (d, 'alo_order') not in L]
B = list(csv.DictReader(open(BK)))
def taker_last(period):  # share of matched volume where the taker signed its order after the maker signed its price
    b = [(float(r['share_of_notional']), r['gap_bucket']) for r in B if r['period'] == period]
    return sum(s for s, g in b if g != '<0') / sum(s for s, _ in b)
tl0, tl1 = taker_last('before_nov06'), taker_last('since_nov06')
q40 = agg(POST, '40k+', 'all')
per_open = q40['s'] / 60 / len(POST)
raw = sum(M[(d, '40k+', 'all')]['v'] * M[(d, '40k+', 'all')]['m1'] / 1e4 for d in POST)
pos_pre = sum(1 for d in PRE if M[(d, '40k+', 'cancel_place')]['m1'] > 0); pos_post = sum(1 for d in POST if M[(d, '40k+', 'cancel_place')]['m1'] > 0)
aftb = [-M[(d, '40k+', 'all')]['m1'] for d in AFTER]   # all makers, bps lost, opens after Nov 13
aft = [M[(d, '40k+', 'all')]['v'] * M[(d, '40k+', 'all')]['m1'] / 1e7 for d in AFTER]   # all makers, $k, opens after Nov 13
assert len(AFTER) == 2 and all(-73 < x < 0 for x in aft), aft   # the worst open before Nov 6: -$73k
print('after', [(d, M[(d, '40k+', 'cancel_place')]['m1'], M[(d, '40k+', 'all')]['m1'], M[(d, '40k+', 'all')]['s']) for d in AFTER], '| main makers before', round(agg(PRE, '40k+', 'cancel_place')['m1'], 2))
print(f'taker last {tl0:.0%} -> {tl1:.0%} | raw {raw:.0f} | per open {per_open:.1f} min | pos {pos_pre}/{len(PRE)} {pos_post}/{len(POST)} | all {q40["m1"]:+.2f} bps on {q40["v"] / 1e9:.2f}B')
assert pos_post == 0 and len(POST) == 6 and round(100 * tl0) == 29 and round(100 * tl1) == 86 and round(-raw / 1e3 / len(POST)) == 75
def style(ax, grid='y'):
    for sp in ('top', 'right'): ax.spines[sp].set_visible(False)
    ax.grid(axis=grid, color='#ececec', lw=0.8); ax.set_axisbelow(True)

# ---------- texts
LEDE = [('Market makers are the accounts whose prices you trade against. When the market moves, they have to update those prices fast.', INK, 'normal'),
        ('In the busiest seconds of the US open, a maker’s new price reached the book in about 250 ms, a taker’s order in about 540 ms: a 290 ms head start.', SUB, 'normal'),
        (f'From Nov 6 to Nov 13 the maker’s price took about 520 ms: no head start, and the taker decided last in {100 * tl1:.0f}% of matched trades, up from {100 * tl0:.0f}%.', SUB, 'normal'),
        (f'In those six opens the main makers lost money in those seconds every time. Before, they earned at {pos_pre} opens out of {len(PRE)}.', INK, 'bold'),
        ('In the calm seconds of the same opens, nothing changed.', INK, 'bold'),
        ('Since Nov 14 part of the head start is back (240 ms on Nov 16, 180 on Nov 17). The main makers’ result is not back yet: +0.2 bps, then −0.9.', INK, 'bold')]
FOOT = ['Data: every HyperCore trade (fill) from a Femtos non-validator node in Tokyo, and Hyperliquid replica_cmds (public S3) for signing times and load. Perps incl. HIP-3.'] + textwrap.wrap(
    'Busiest seconds = above 40k transactions per second; calm = below 20k (makers: +0.3 bps before Nov 6, +0.4 from Nov 6 to Nov 13). Result = the price one second after the trade against the trade price, '
    'fees left out. Main makers = the 263 accounts that requote with cancel + new order. Order times = from signing an order to the block that holds it, medians over 46 opens '
    '(40 before Nov 6, 6 from Nov 6 to Nov 13); a taker order took about 540 ms with or without a priority fee, except in the top fee lane (8 bps or more); a cancel alone still took about 265 ms. '
    '“Decided” = signed the order; matched trades = 10 opens, the trades we could tie to both signed orders (9–29% of maker volume). '
    'Chart 3: every trade of 5 opens before Nov 6 and of the six from Nov 6 to Nov 13; $ next to a name = its maker volume from Nov 6 to Nov 13; Net before = its result per dollar traded before Nov 6, applied to the volume '
    'it traded from Nov 6 to Nov 13, so that column does not add up. '
    'Firms = addresses with a public tag, which can be wrong; linked groups = addresses we tie together on-chain; everyone else lost 1.0 bps of the volume they traded before Nov 6, 1.1 from Nov 6 to Nov 13. '
    'Takers did nothing wrong: they traded against prices that were in the book. '
    'Nov 14: a Saturday with no US open; in its evening sell-off (20:46–22:32 UTC, 336 seconds above 40k) a maker’s new price took 335 ms and a taker order 595 ms, '
    'main makers made +2.6 bps on $258M and the maker decided last in 69% of matched trades; the head start was already back that night, before the move to network version 113 (08:35 UTC). '
    'Nov 16 and Nov 17 opens: 259 and 152 seconds above 40k; a maker’s new price took 345 and 385 ms, a taker order 585 and 565 ms; main makers +0.2 bps on $129M and −0.9 bps on $42M, '
    'all makers −0.6 bps on $323M and −1.1 bps on $119M; the taker decided last in 62% and 78% of matched trades. '
    'At the same load a maker’s new price took 315–335 ms at 40–42.5k on those two opens (245 before Nov 6, 415 on Nov 12) and 435–465 ms at 47.5–52.5k (255 before Nov 6, 605–665 on Nov 12); '
    'over the two opens the main makers made +0.6 bps at 40–45k and lost 1.2 bps above 45k. '
    'Chart 1: ALO modify as in part 2; a new ALO order, the maker’s new price of the text above, moved the same way (345 and 385 ms on Nov 16 and Nov 17).', 198)

# ---------- layout, in inches from the top
TY = 0.45                                   # the title takes two lines
R3 = 1.07 + (len(LEDE) - 1) * 0.27 + 0.62   # chart 1 title (order delays), under the intro
RM = R3 + 4.3                               # chart 2 title (makers, open by open)
R4 = RM + 3.45                              # chart 3 title (by group)
AH = 5.3 if GK else 4.4                     # chart 3 height: three bars per group with AFTER_BY_GROUP, two without
# every note sits under chart 3, in one grid of three columns and two rows
X0 = 0.07
NOTES = [[('How big', f'Makers lost about ${-raw / 1e3:.0f}k in those seconds over six opens ({-q40["m1"]:.1f} bps on ${q40["v"] / 1e9:.1f}B), about {per_open:.0f} minutes per open. '
                     f'On Nov 16 and 17 they lost ${-aft[0]:.0f}k and ${-aft[1]:.0f}k on less volume: {aftb[0]:.1f} and {aftb[1]:.1f} bps.'),
          ('Who gained', 'Takers who pay the priority fee, an optional fee to arrive sooner: +6.1 bps per trade from Nov 6 to Nov 13, +3.2 before, on about as much volume. Before their fees.'),
          ('Who was worse off', 'Those who take least. Firm B and Firm D, who mostly make, ended below zero. The other main makers went from +$121k to +$17k on the same volume. '
                                'Everyone else lost about as much per dollar traded as before.')],
         [('Why it matters', 'Hyperliquid’s docs say the order priority is “designed to protect makers against toxic flow, so that end users see tight spreads and deep liquidity even during volatility.” '
                             'The 290 ms head start is that protection. For six opens it was gone, unannounced: the cost fell on those who only make, the gain went to those who take.'),
          ('Since Nov 14', 'A maker’s new price now takes longer as load rises: 315–335 ms at 40–42.5k transactions per second, 435–465 ms at 47.5–52.5k. '
                           'Before Nov 6 it took about 250 ms at any load. Over the Nov 16 and Nov 17 opens the main makers made +0.6 bps at 40–45k and lost 1.2 bps above 45k.'),
          ('What we don’t know', 'Whether it was intended. What changed on Nov 14: the head start came back that night, before the move to network version 113. '
                                  'Whether the rest will come back: on Nov 17 a maker’s new price still took 385 ms, not 250, '
                                  'and the taker decided last in 78% of matched trades. Other readings are welcome.')]]
NX = (X0, 0.375, 0.68)
NOTES = [[(h_, textwrap.wrap(t_, 48)) for h_, t_ in row] for row in NOTES]
NY = [R4 + 0.95 + AH + 0.85]                # heading of each row of notes
for row in NOTES: NY.append(NY[-1] + 0.27 + max(len(l_) for _, l_ in row) * 0.21 + 0.3)
FT = NY[-1] + 0.05; HC = FT + len(FOOT) * 0.17 + 0.82; H = HC + TY; X1 = 0.965
fig = plt.figure(figsize=(12.5, H), dpi=200)
y = lambda inch: 1 - (inch + TY) / H
def axes(top, height, left=X0, right=X1): return fig.add_axes([left, y(top + height), right - left, height / H])
def ttl(x, top, title, sub=None):
    fig.text(x, y(top), title, fontsize=14, fontweight='bold', color=INK)
    if sub: fig.text(x, y(top + 0.3), sub, fontsize=9.6, color=SUB)

fig.text(X0, 1 - 0.62 / H, 'Hyperliquid priority under load, part 3:', fontsize=23.5, fontweight='bold', color=INK)
fig.text(X0, 1 - 1.07 / H, 'what six opens without their head start cost makers', fontsize=23.5, fontweight='bold', color=INK)
for i, (t, c, w) in enumerate(LEDE): fig.text(X0, y(1.07 + i * 0.27), t, fontsize=12.3, color=c, fontweight=w)

# ---------- 1. order delays, open by open: the first chart of part 2, same series, same words, same marks, extended past Nov 12.
# Same opens and same x axis as chart 2.
xs = list(range(len(D))); i6 = D.index(SPLIT); XR_ = len(D) + 7.6
i10, i12, i16 = D.index('2026-11-10'), D.index('2026-11-12'), D.index(AFTER[0])
lastm = L[(D[-1], 'batchmodify_alo')]
ttl(X0, R3, '1. Modifies left the fast lane on Nov 6; since Nov 14 they are partly back',
    'Each point is one US open (weekdays): median time from signing to block during the seconds above 40k tx/s. ALO modify = batchModify with ALO orders.')
ax = axes(R3 + 0.6, 3.0)
ax.axvspan(i6 - 0.5, D.index(POST[-1]) + 0.5, color=BG, lw=0, zorder=0)
ax.axhspan(215, 285, xmin=0, xmax=(i6 + 0.1) / (XR_ + 0.6), color=BL, alpha=0.07, lw=0, zorder=0)
ax.axhspan(510, 575, color=GR, alpha=0.12, lw=0, zorder=0)
ax.text(1, 318, 'FAST LANE  •  cancels, ALO modifies and takers paying the 8 bps fee all land in ~250 ms', fontsize=9.5, color=BL, fontweight='bold', bbox=dict(facecolor='white', edgecolor='none', pad=1.5, alpha=0.9), zorder=4)
ax.text(1, 590, 'SLOW LANE  •  takers paying no fee wait ~300 ms longer, by design, so makers can get out of the way', fontsize=9.5, color='#777', fontweight='bold', bbox=dict(facecolor='white', edgecolor='none', pad=1.5, alpha=0.9), zorder=4)
SER = [('IOC, no fee', 'ioc_nofee', GR, 1.8), ('IOC, 8 bps', 'ioc_8bps', OR, 1.8), ('Fast cancel', 'cancel_fast', BL, 2.4), ('ALO modify', 'batchmodify_alo', GN, 3.0)]
ends = []
for name, fam, c, lw in SER:
    pts = [(x, L[(d, fam)]) for x, d in zip(xs, D) if not (fam == 'ioc_8bps' and d == '2026-11-02')]   # 8 bps IOC on Nov 2: too few at 40k+
    ax.plot([p_[0] for p_ in pts], [p_[1] for p_ in pts], color=c, lw=lw, marker='o', ms=2.6, zorder=3)
    ends.append([pts[-1][1], pts[-1][1], name, c if c != GR else '#777', name in ('ALO modify', 'Fast cancel')])
ends.sort()                                  # end labels: at least 46 ms apart
for a_, b_ in zip(ends, ends[1:]): b_[1] = max(b_[1], a_[1] + 46)
for v, yl, name, tc, bold in ends: ax.text(xs[-1] + 0.6, yl, f'{name}  {v} ms', va='center', fontsize=10, color=tc, fontweight='bold' if bold else 'normal')
for i in (i6, i10, i12, i16 - 0.5): ax.axvline(i, color='#999', ls=':', lw=1, zorder=1)
ax.text(i6 - 0.3, 845, 'Nov 6: the fast lane slows down', ha='right', va='top', fontsize=9.5, color=INK)
ax.text(i10 - 0.3, 185, 'Nov 9–10: cancels fixed', ha='right', va='top', fontsize=9.5, color=INK)
ax.text(i12 - 0.3, 778, 'Nov 12: v112', ha='right', va='top', fontsize=9.5, color=INK, zorder=4, bbox=dict(facecolor=BG, edgecolor='none', pad=1.5))
ax.text(i16 - 0.2, 845, 'Nov 14: v113', ha='left', va='top', fontsize=9.5, color=INK)
ax.annotate('Modifies out of the fast lane:\nmoving a quote was slower than a taker paying 8 bps', xy=(i10, L[(D[i10], 'batchmodify_alo')]), xytext=(i6 - 17, 690),
            fontsize=9.5, color=GN, fontweight='bold', arrowprops=dict(arrowstyle='->', color=GN, lw=1.2, connectionstyle='arc3,rad=-0.15'))
for i, d in enumerate(D):
    if i and HF[D[i - 1]] != HF[d]: ax.text(i, 40, 'v' + HF[d], ha='center', fontsize=8.5, color=SUB, zorder=4, bbox=dict(facecolor=BG if SPLIT <= d < END else 'white', edgecolor='none', pad=1.2))
ax.set_ylim(0, 860); ax.set_yticks([0, 200, 400, 600, 800]); ax.set_ylabel('Signing to block (ms), median')
tk = [i for i, d in enumerate(D) if d in ('2026-09-11', '2026-09-18', '2026-09-25', '2026-10-01', '2026-10-09', '2026-10-16', '2026-10-23', SPLIT, D[-1])]
ax.set_xticks(tk); ax.set_xticklabels([lab(D[i]) for i in tk]); ax.set_xlim(-0.6, XR_)
style(ax)

# ---------- 2. makers, open by open
ttl(X0, RM, '2. Makers earned in the busiest seconds until Nov 5, then lost six opens in a row',
    f'One point per US open, {len(D)} opens. Maker result one second after the trade, in bps (1 bp = $1 per $10,000 traded). Hollow points: under a minute of busiest seconds, noisy.')
ax = axes(RM + 0.6, 2.15)
ax.axvspan(i6 - 0.5, D.index(POST[-1]) + 0.5, color=BG, lw=0, zorder=0); ax.axhline(0, color='#999', lw=0.9, zorder=1)
for gname, c, lw, ms in (('other', GR, 1.8, 3.2), ('cancel_place', BL, 2.8, 4.2)):
    ys = [M[(d, '40k+', gname)]['m1'] for d in D]
    ax.plot(xs, ys, color=c, lw=lw, zorder=3 if gname != 'other' else 2)
    ax.scatter([x for x, d in zip(xs, D) if d not in THIN], [v for v, d in zip(ys, D) if d not in THIN], s=ms * 6, color=c, zorder=4, lw=0)
    ax.scatter([x for x, d in zip(xs, D) if d in THIN], [v for v, d in zip(ys, D) if d in THIN], s=ms * 6, facecolor='white', edgecolor=c, lw=1.2, zorder=4)
    ax.text(len(D) - 0.2, ys[-1] + (0.3 if gname == 'cancel_place' else -0.3), 'Main makers' if gname == 'cancel_place' else 'Other makers', color=c, fontsize=10.5, fontweight='bold', va='center')
ax.text(i6 - 0.25, 3.7, 'Nov 6 to Nov 13:\nno head start', fontsize=9.5, color=INK, va='top', fontweight='bold')
n5 = D.index('2026-11-05')
ax.annotate('Nov 5: the busiest open\nof the period, new prices\nstill at 250 ms', xy=(n5, M[('2026-11-05', '40k+', 'cancel_place')]['m1']), xytext=(n5 - 8.2, 2.5),
            fontsize=9.3, color=SUB, arrowprops=dict(arrowstyle='-', color='#aaa', lw=0.7))
ax.set_ylim(-6, 4); ax.set_yticks([-4, -2, 0, 2]); ax.set_yticklabels(['−4 bps', '−2 bps', '0', '+2 bps'])
tk = [i for i, d in enumerate(D) if d in ('2026-09-11', '2026-09-18', '2026-09-25', '2026-10-01', '2026-10-09', '2026-10-16', '2026-10-23', SPLIT, D[-1])]
ax.set_xticks(tk); ax.set_xticklabels([lab(D[i]) for i in tk]); ax.set_xlim(-0.6, XR_)
style(ax)

# ---------- 3. by group
ttl(X0, R4, '3. Every group did worse as maker. Those who take a lot made it back as takers, before fees',
    'Bars: result as maker one second after the trade, in bps. Dollars: 5 opens before Nov 6 ($3.5B traded) and the six from Nov 6 to Nov 13 ($2.3B); they add up to zero.'
    + (f' Blue: {AFTER_LBL}.' if AG else ''))
# data/part3/result_by_group.csv: group, addresses, maker volume Nov 6-13 ($M), maker bps before, maker bps Nov 6-13, Nov 6-13 in $k: as maker, as taker, net;
# net before in $k at the volume traded Nov 6-13 (by_group.py with CAP=1e9 on every fill of the 11 opens; tagged groups sorted by maker volume, then the rest split by maker style).
E = []
for r in csv.DictReader(open(GRP)):
    E.append((r['group'], int(r['addresses']), int(r['maker_volume_nov6_13_usd_m']), float(r['maker_bps_before_nov6']), float(r['maker_bps_nov6_13']), float(r['as_maker_usd_k']),
              float(r['as_taker_usd_k']), float(r['net_usd_k']), float(r['net_before_same_volume_usd_k']) if r['net_before_same_volume_usd_k'] else None))
assert abs(E[-1][5] * 1e3 - raw) < 500 and abs(E[-1][4] - q40['m1']) < 0.01, (E[-1], raw)   # chart 3 closes on the paper's total: same six opens, same fills, no cap
ax = axes(R4 + 0.95, AH, 0.215, 0.56); style(ax, 'x')
tr = ax.get_yaxis_transform(); k = lambda v: neg(f'{v:+.0f}k') if abs(v) >= 0.5 else '0'
NAME, C_ = -0.42, (1.29, 1.536, 1.783, 2.101)
for i, (n, na, vol, b0, b1, mk, tk_, net, net0) in enumerate(E):
    yy = len(E) - 1 - i - 0.25 * (i >= 7) - 0.25 * (i >= 9); h = 0.27 if AG else 0.34; bold = i == len(E) - 1
    y0, y1 = (yy + h, yy) if AG else (yy + h / 2, yy - h / 2)
    ax.barh(y0, b0, h, color=GR); ax.barh(y1, b1, h, color=OR)
    ax.text(b0 + (0.1 if b0 >= 0 else -0.1), y0, neg(f'{b0:+.1f}'), fontsize=8.8, color=DG, va='center', ha='left' if b0 >= 0 else 'right')
    ax.text(b1 - 0.1, y1, neg(f'{b1:+.1f}'), fontsize=9.2, color=OR, fontweight='bold', va='center', ha='right')
    if AG:
        b2 = AG[n]; ax.barh(yy - h, b2, h, color=BL)
        ax.text(b2 + (0.1 if b2 >= 0 else -0.1), yy - h, neg(f'{b2:+.1f}'), fontsize=8.8, color=BL, va='center', ha='left' if b2 >= 0 else 'right')
    ax.text(NAME, yy + 0.14, n, fontsize=10.8, fontweight='bold', color=INK, va='center', transform=tr, clip_on=False)
    ax.text(NAME, yy - 0.2, f'{na:,} address' + ('es' if na > 1 else '') + (f', ${vol / 1e3:.1f}B' if vol >= 1000 else f', ${vol}M'), fontsize=8.8, color=SUB, va='center', transform=tr, clip_on=False)
    ax.text(C_[0], yy, k(mk), fontsize=10.5, color=OR, va='center', ha='right', transform=tr, fontweight='bold' if bold else 'normal')
    ax.text(C_[1], yy, k(tk_), fontsize=10.5, color=BL if tk_ >= 0 else OR, va='center', ha='right', transform=tr, fontweight='bold' if bold else 'normal')
    ax.text(C_[2], yy, k(net), fontsize=11.5, fontweight='bold', color=INK if net >= 0 else OR, va='center', ha='right', transform=tr)
    if net0 is not None: ax.text(C_[3], yy, k(net0), fontsize=10, color=SUB, va='center', ha='right', transform=tr)
top = len(E) - 0.3
for x, t in zip(C_, ('As maker', 'As taker', 'Net', 'same volume')): ax.text(x, top, t, fontsize=9, color=SUB, ha='right', transform=tr)
ax.text(C_[3], top + 0.36, 'Net before,', fontsize=9, color=SUB, ha='right', transform=tr)
ax.text(C_[2], top + 0.36, 'Nov 6 to Nov 13, in dollars', fontsize=9, color=SUB, ha='right', transform=tr)
for yl_ in (2.375, 0.125): ax.plot([NAME, C_[3]], [yl_, yl_], color='#bbb', lw=0.8, transform=tr, clip_on=False)
ax.axvline(0, color='#999', lw=0.9)
ax.set_xlim(-7.3, 2.9); ax.set_ylim(-1.1, len(E) - 0.1); ax.set_yticks([])
ax.set_xticks([-6, -4, -2, 0, 2]); ax.set_xticklabels(['−6 bps', '−4 bps', '−2 bps', '0', '+2 bps'])
ax.legend(handles=[Patch(color=GR, label='As maker, before Nov 6'), Patch(color=OR, label='Nov 6 to Nov 13')] + ([Patch(color=BL, label=AFTER_LBL)] if AG else []),
          loc='lower left', bbox_to_anchor=(NAME - 0.012, 1.0), ncol=3, frameon=False, fontsize=9.6, handlelength=1.2, borderaxespad=0.1, columnspacing=1.2)
# "the gain went to those who take": what the table shows (the taker column). It does not show that the gain went to priority-fee payers.
for row, top_ in zip(NOTES, NY):
    for x_, (h_, lines) in zip(NX, row):
        fig.text(x_, y(top_), h_, fontsize=12, fontweight='bold', color=INK)
        for j, l_ in enumerate(lines): fig.text(x_, y(top_ + 0.27 + j * 0.21), l_, fontsize=10, color=INK)

fig.text(X0, y(FT), '\n'.join(FOOT), fontsize=8.6, color=SUB, linespacing=1.5, va='top')
fig.add_artist(plt.Line2D([X0, X1], [y(HC - 0.62), y(HC - 0.62)], color='#ccc', lw=0.8))
fig.text(X0, y(HC - 0.18), 'femtos.xyz', fontsize=30, fontweight='bold', color=INK)
fig.text(X1, y(HC - 0.26), 'Hyperliquid data: HyperCore, HyperEVM, Elysium', fontsize=11, color=SUB, ha='right')

# every text must stay inside the right margin
fig.canvas.draw(); rd = fig.canvas.get_renderer(); W = fig.get_figwidth() * fig.dpi
over = [(round(t.get_window_extent(rd).x1 / W, 3), t.get_text()[:60]) for t in fig.texts if t.get_window_extent(rd).x1 > X1 * W + 2]
assert not over, over
fig.savefig(OUT, facecolor='white')
print(OUT, f'{12.5 * 200:.0f}x{H * 200:.0f}')
