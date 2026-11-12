import re, math, collections, csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
# part2.py : the paper's figure, from the tables in data/ (make_tables.py). Writes figure/hyperliquid-priority-part2.png
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = os.path.join(ROOT, 'data') + '/'
import glob as _g
from matplotlib import font_manager as _fm
for _f in _g.glob('/usr/share/fonts/truetype/liberation/LiberationSans-*.ttf'): _fm.fontManager.addfont(_f)
plt.rcParams.update({'font.family': 'Liberation Sans', 'font.size': 10.5, 'axes.edgecolor': '#b5b5b5', 'axes.linewidth': 0.8,
                     'xtick.color': '#555', 'ytick.color': '#555', 'axes.labelcolor': '#555', 'text.color': '#1a1a1a'})
OR, GR, BL, GN, DG = '#e8673a', '#a8a59c', '#2f74c9', '#20a67a', '#7d7a72'
INK, SUB = '#1a1a1a', '#666'

# ---------- data
# signed-before shares of losing fast cancels (from fills, see README "Cancels"; not rebuilt by make_tables.sh), n = losing cancels with both clocks reliable
SB = {  # window -> ioc -> [(n, pct) per band <20k, 20-30k, 30-40k, 40k+]
 'Nov 8-9':  {'ioc8': [(101,12.9),(257,28.0),(1211,30.2),(1528,30.5)], 'ioc0': [(10246,1.7),(19225,1.4),(27144,9.7),(15138,16.6)]},
 'Nov 10':   {'ioc8': [(62,27.4),(156,21.2),(363,12.7),(1631,13.4)],  'ioc0': [(7677,0.6),(19498,0.7),(22310,0.8),(24164,2.2)]},
 'Nov 11':   {'ioc8': [(62,27.4),(160,11.9),(329,5.8),(476,3.8)],     'ioc0': [(6483,1.2),(10216,1.2),(7890,0.6),(3659,0.5)]},
 'Nov 12':   {'ioc8': [(51,45.1),(143,24.5),(470,8.5),(882,4.1)],     'ioc0': [(2223,1.0),(7478,0.6),(9091,0.5),(6100,0.4)]},
}
def wilson(n, p, z=1.96):
    p = p / 100; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)
# every open, 40k+ band: (date, hardfork, fast cancel, ALO order, modify ALO, IOC 8 bps, IOC no fee, batchModify ALO)
BO = collections.defaultdict(dict); HF = {}
for r in csv.DictReader(open(H + 'latency_by_open.csv')):
    if r['load_band'] == '40k+': BO[r['date']][r['family']] = int(r['median_ms']); HF[r['date']] = int(r['hardfork'])
T = [(d.replace('-', ''), HF[d], *(v[f] for f in ('cancel_fast', 'alo_order', 'modify_alo', 'ioc_8bps', 'ioc_nofee', 'batchmodify_alo')))
     for d, v in BO.items()]
THIN = {'20261030', '20261102', '20261103'}  # under 4% of the window's seconds above 40k tx/s
mon = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
lab = lambda d: f'{int(d[6:])} {mon[int(d[4:6]) - 1]}'
# load curves
K40 = {(r['period'], r['family']): int(r['median_ms']) for r in csv.DictReader(open(H + 'latency_40k_by_period.csv'))}

# ---------- figure
fig = plt.figure(figsize=(12.5, 13.4), dpi=200)
gs = GridSpec(3, 2, figure=fig, left=0.07, right=0.97, top=0.85, bottom=0.2, hspace=0.55, wspace=0.27, height_ratios=[1.5, 1.05, 1.05])
fig.text(0.07, 0.958, 'Hyperliquid priority under load, part 2: modifies', fontsize=24, fontweight='bold', color=INK)
fig.text(0.07, 0.929, 'Cancels were fixed on Nov 9\u201310. Under load, modifies still take about twice as long as before Nov 6, v112 included.', fontsize=13.5, color=SUB)
fig.text(0.07, 0.910, 'Measured on our own node: every block (replica_cmds), every validator bundle as it arrives (mempool_txs), down to the account.', fontsize=13.5, color=SUB)

# panel 1: moving a quote on Nov 12, 40k+
ax = fig.add_subplot(gs[1, 0])
rows = [('batchModify, ALO', 505, 505), ('modify, ALO', 575, 575), ('fast cancel + new ALO order', 255, 495)]
for k, (name, off, on) in enumerate(rows):
    y = len(rows) - 1 - k
    ax.barh(y, off, height=0.42, color='#d6d3cb', lw=0)
    if on > off: ax.barh(y, on - off, left=off, height=0.42, color='white', edgecolor='#bbb', hatch='////', lw=0.6)
    ax.plot([off], [y], marker='|', ms=18, mew=2.5, color=BL if on > off else GN)
    ax.plot([on], [y], marker='o', ms=9, color=GN)
    ax.text(2, y + 0.33, name, ha='left', va='bottom', fontsize=10.5, color=INK)
    lab_txt = f'off {off}, new quote {on} ms' if on > off else f'{on} ms'
    ax.text(on + 14, y, lab_txt, va='center', fontsize=9.8, color=INK, fontweight='bold')
ax.set_xlim(0, 800); ax.set_ylim(-0.45, 2.75); ax.set_yticks([])
ax.set_xlabel('Signing to block, median (ms)')
for sp in ('top', 'right', 'left'): ax.spines[sp].set_visible(False)
ax.grid(axis='x', color='#ececec', lw=0.8); ax.set_axisbelow(True)
ax.set_title('Moving a quote on Nov 12', loc='left', fontsize=13, fontweight='bold', pad=24)
ax.text(0, 1.04, 'Above 40k tx/s. Grey: old quote still on the book. Hatched: no quote. Before Nov 6, all three: ~255 ms.', transform=ax.transAxes, fontsize=9.5, color=SUB)

# panel 2: 45 opens, 40k+
ax = fig.add_subplot(gs[0, :])
xs = list(range(len(T))); D = [t[0] for t in T]
i6, i10, i12 = D.index('20261106'), D.index('20261110'), D.index('20261112')
ax.axvspan(i6 - 0.5, len(T) - 0.5, color='#f4f4f2', lw=0, zorder=0)
ax.axhspan(215, 285, xmin=0, xmax=(i6 + 0.5) / (len(T) + 7), color=BL, alpha=0.07, lw=0, zorder=0)
ax.axhspan(510, 575, color=GR, alpha=0.12, lw=0, zorder=0)
ax.text(1, 318, 'FAST LANE  •  cancels, ALO modifies and takers paying the 8 bps fee all land in ~250 ms', fontsize=9.5, color=BL, fontweight='bold', bbox=dict(facecolor='white', edgecolor='none', pad=1.5, alpha=0.9), zorder=4)
ax.text(1, 590, 'SLOW LANE  •  takers paying no fee wait ~300 ms longer, by design, so makers can get out of the way', fontsize=9.5, color='#777', fontweight='bold', bbox=dict(facecolor='white', edgecolor='none', pad=1.5, alpha=0.9), zorder=4)
series = [('IOC, no fee', 6, GR, '-', 1.8), ('IOC, 8 bps', 5, OR, '-', 1.8), ('Fast cancel', 2, BL, '-', 2.4), ('ALO modify', 7, GN, '-', 3.0)]
for name, k, c, ls, lw in series:
    pts = [(x, t[k]) for x, t in zip(xs, T) if not (k == 5 and t[0] == '20261102')]  # 8 bps IOC on Nov 2: too few at 40k+
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, ls=ls, lw=lw, marker='o', ms=2.6, zorder=3)
    y = pts[-1][1]
    ax.text(xs[-1] + 0.5, y + {'IOC, no fee': 12, 'ALO modify': -12}.get(name, 0), f'{name}  {y} ms', va='center', fontsize=10, color=c if c != GR else '#777', fontweight='bold' if name in ('ALO modify', 'Fast cancel') else 'normal')
for i in (i6, i10, i12): ax.axvline(i, color='#999', ls=':', lw=1, zorder=1)
ax.text(i6 - 0.3, 845, 'Nov 6: the fast lane slows down', ha='right', va='top', fontsize=9.5, color=INK)
ax.text(i10 - 0.3, 185, 'Nov 9–10: cancels fixed', ha='right', va='top', fontsize=9.5, color=INK)
ax.text(i12 + 0.3, 845, 'Nov 12: v112', ha='left', va='top', fontsize=9.5, color=INK)
ax.annotate('Modifies stay out of the fast lane:\nmoving a quote is now slower than a taker paying 8 bps', xy=(i10, T[i10][7]), xytext=(i6 - 17, 690),
            fontsize=9.5, color=GN, fontweight='bold', arrowprops=dict(arrowstyle='->', color=GN, lw=1.2, connectionstyle='arc3,rad=-0.15'))
for i, t in enumerate(T):
    if i > 0 and T[i - 1][1] != t[1]:
        ax.text(i, 40, f'v{t[1]}', ha='center', fontsize=8.5, color=SUB, zorder=4, bbox=dict(facecolor='#f4f4f2' if i >= i6 else 'white', edgecolor='none', pad=1.2))
ticks = [i for i, t in enumerate(T) if i % 5 == 0 or i == len(T) - 1]
ax.set_xticks(ticks); ax.set_xticklabels([lab(T[i][0]) for i in ticks], fontsize=9.5)
ax.set_xlim(-0.5, len(T) + 7); ax.set_ylim(0, 860); ax.set_yticks([0, 200, 400, 600, 800])
ax.set_ylabel('Signing to block (ms), median')
ax.grid(axis='y', color='#ececec', lw=0.8); ax.set_axisbelow(True)
for sp in ('top', 'right'): ax.spines[sp].set_visible(False)
ax.set_title('Modifies left the fast lane on Nov 6 and are still out after v112', loc='left', fontsize=14, fontweight='bold', pad=24)
ax.text(0, 1.02, 'Each point is one US open (weekdays): median time from signing to block during the seconds above 40k tx/s. ALO modify = batchModify with ALO orders.', transform=ax.transAxes, fontsize=9.5, color=SUB)

# panel 3: latency vs load, two panels side by side (5k tx/s bins)
LC5 = collections.defaultdict(dict)
for r in csv.DictReader(open(H + 'load_curve_5000.csv')):
    LC5[(r['period'], r['family'])][int(r['load_from'])] = (int(r['n']), int(r['median_ms']))
sub = gs[2, 0].subgridspec(1, 2, wspace=0.08)
LSTY = [('ioc_nofee', GR, 2, 0.9, 'o', 4), ('batchmodify_alo', GN, 2, 0.75, 's', 5), ('cancel_fast', BL, 2, 0.75, 'o', 5), ('ioc_8bps', OR, 2, 0.75, 'D', 4.5)]
for j, (per, title, nmin) in enumerate([('sep11-nov05', 'Sep 11–Nov 5', 5000), ('nov12', 'Nov 12 (v112)', 1500)]):
    ax = fig.add_subplot(sub[0, j])
    # same width, see-through, one marker shape each: the three overlapping lines all stay visible
    for fam, c, lw, a, mk, ms in LSTY:
        pts = sorted((lk, med) for lk, (n, med) in LC5[(per, fam)].items() if 5000 <= lk <= 50000 and n >= nmin)
        ax.plot([p[0] / 1000 + 2.5 for p in pts], [p[1] for p in pts], color=c, lw=lw, alpha=a, marker=mk, ms=ms, mec='white', mew=0.7)
    ax.set_xlim(5, 55); ax.set_ylim(0, 800); ax.set_xticks([10, 20, 30, 40, 50])
    ax.axvspan(40, 55, color='#f4f4f2', lw=0, zorder=0)
    ax.grid(axis='y', color='#ececec', lw=0.8); ax.set_axisbelow(True)
    for sp in ('top', 'right'): ax.spines[sp].set_visible(False)
    ax.text(0.03, 0.97, title, transform=ax.transAxes, fontsize=11, fontweight='bold', va='top', color=INK)
    if j == 0:
        sub_x0 = ax.get_position().x0
        ax.set_ylabel('Signing to block (ms), median')
        ax.set_title('Latency by chain load', loc='left', fontsize=13, fontweight='bold', pad=10)
        h = [matplotlib.lines.Line2D([], [], color=c, lw=lw, alpha=a, marker=mk, ms=ms, mec='white', mew=0.7) for _, c, lw, a, mk, ms in LSTY]
        ax.legend(h, ['IOC, no fee', 'ALO modify', 'Fast cancel', 'IOC, 8 bps'], frameon=False, fontsize=8.8, loc='lower left', ncol=2, columnspacing=1, handlelength=1.5, bbox_to_anchor=(0.0, 0.37))
        ax.text(7, 120, 'cancels, modifies and 8 bps IOC: one line', fontsize=8.8, color=SUB)
    else:
        ax.set_yticklabels([])
    ax.text(47.5, 770, '40k+', ha='center', va='top', fontsize=8.5, color=SUB)
    pos = ax.get_position()
fig.text((sub_x0 + pos.x1) / 2, pos.y0 - 0.032, 'Chain transactions per second (thousands)', ha='center', fontsize=10.5, color=INK)

# panel 4: every action, before vs Nov 12 (40k+)
ax = fig.add_subplot(gs[1, 1])
rows = [('batchModify, ALO', 'batchmodify_alo', GN), ('modify, ALO', 'modify_alo', GN), ('ALO order', 'alo_order_any', GN), ('IOC, 8+ bps', 'ioc_8bps', OR), ('Fast cancel', 'cancel_fast', BL),
        ('IOC, under 8 bps', 'ioc_under_8bps', GR), ('IOC, no fee', 'ioc_nofee', GR), ('GTC order', 'gtc_order', GR), ('Cancel, no flag', 'cancel_nofast', GR), ('batchModify, GTC', 'batchmodify_gtc', GR), ('scheduleCancel', 'schedule_cancel', GR)]
for i, (name, fam, c) in enumerate(rows):
    b = K40[('sep11-nov05', fam)]; a = K40[('nov12', fam)]
    y = len(rows) - 1 - i
    ax.plot([b, a], [y, y], color=c, lw=2.2, alpha=0.8 if c != GR else 0.6, solid_capstyle='round')
    ax.scatter([b], [y], s=26, facecolor='white', edgecolor=c if c != GR else '#888', lw=1.4, zorder=3)
    ax.scatter([a], [y], s=30, color=c if c != GR else '#888', zorder=3)
    ax.text(max(a, b) + 14, y, f'{b} \u2192 {a}', va='center', fontsize=8.8, color=INK if c in (GN, BL, OR) else '#666')
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=9.5)
ax.set_xlim(0, 820); ax.set_xlabel('Signing to block above 40k tx/s (ms), median: Sep 11\u2013Nov 5 (open dot) \u2192 Nov 12 (filled)', fontsize=9)
ax.grid(axis='x', color='#ececec', lw=0.8); ax.set_axisbelow(True)
for s in ('top', 'right'): ax.spines[s].set_visible(False)
ax.set_title('What moved: modifies and ALO orders', loc='left', fontsize=13, fontweight='bold', pad=24)

# panel 5: calm vs load table-like: share by band? -> where it waits (mempool)
ax = fig.add_subplot(gs[2, 1]); ax.axis('off')
ax.set_title('What else we found', loc='left', fontsize=13, fontweight='bold', pad=10)
notes = [
 ('Same accounts, two speeds.', 'Nov 12: 81 of 94 accounts had modifies at 400+ ms, own fast cancels under 300 ms.'),
 ('Cancels were fixed on Nov 9\u201310.', 'Losing cancels signed before an 8 bps IOC: 30% (Nov 8\u20139), 4% (Nov 12).'),
 ('Nothing changed on a calm network.', 'Below 20k tx/s, cancels and modifies land in ~205\u2013215 ms, every day.'),
 ('Nov 6 was not load, nor an upgrade.', 'Nov 5 was busier and ran at ~250 ms. v110 from Oct 31, v111 on Nov 7.'),
 ('The delay is before the block is built.', 'Validator bundles reach our node within \u00b140 ms of their block, for every action.'),
]
for i, (h, t) in enumerate(notes):
    cx, cy = 0.0, 0.95 - i * 0.2
    ax.text(cx, cy, h, fontsize=11, fontweight='bold', color=INK, transform=ax.transAxes, va='top')
    import textwrap
    ax.text(cx, cy - 0.075, '\n'.join(textwrap.wrap(t, 95)), fontsize=9.6, color='#444', transform=ax.transAxes, va='top', linespacing=1.35)

foot = ('Data: Hyperliquid replica_cmds (S3) and a Femtos non-validator node in Tokyo (replica_cmds, fills, order statuses, mempool_txs). '
        'Latency = block time minus the action\u2019s nonce (its signing time), medians in 10 ms bins; load = actions in the block\u2019s second. '
        'US cash open, ~09:20\u201310:20 New York, 44 weekdays Sep 11\u2013Nov 11 plus Nov 12. Cancel note: losing cancels whose order an IOC had already filled, at 40k+; '
        'windows Nov 8\u20139 (part 1\u2019s files), Nov 10 13:27\u201316:02, Nov 11 14:19\u201316:06, Nov 12 14:06\u201315:06 UTC.')
fig.add_artist(plt.Line2D([0.07, 0.97], [0.07, 0.07], color='#d9d9d9', lw=1))
fig.text(0.07, 0.034, 'femtos.xyz', fontsize=34, fontweight='bold', color=INK, va='center')
fig.text(0.97, 0.034, 'Hyperliquid data: HyperCore, HyperEVM, Elysium', fontsize=12, color=SUB, va='center', ha='right')
import textwrap
fig.text(0.07, 0.14, '\n'.join(textwrap.wrap(foot, 210)), fontsize=8.4, color='#666', va='top', linespacing=1.45)
fig.savefig(os.path.join(ROOT, 'figure', 'hyperliquid-priority-part2.png'), facecolor='white')
print('ok')
