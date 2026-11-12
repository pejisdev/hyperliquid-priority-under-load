# Hyperliquid priority under load, part 2: modifies

FrothyBeverage × Femtos (femtos.xyz) · Nov 12, 2026

![Hyperliquid priority under load, part 2](figure/hyperliquid-priority-part2.png)

## TL;DR

Hyperliquid fixed cancel priority on Nov 9-10, and the team deserves credit for how fast it happened. What is still open is modifies: under load, moving a quote takes about twice as long as it did before Nov 6.

- **Modifies: still about 2× slower under load.** From Sep 11 to Nov 5, cancels and modifies carrying ALO orders shared one lane at \~245-335 ms, even at 40k+ tx/s. Since Nov 6 those modifies have taken 425-675 ms at that load (batchModify 505 ms on Nov 12), and new ALO orders moved with them.
- **Cancels: fixed.** Losing fast cancels signed before the 8 bps IOC that filled them went from 30.6 % (Nov 8-9) to 1.4 % (Nov 11) at 40k+ tx/s, and fast cancels land in \~245 ms again.
- **Only under load.** On a calm network (below 20k tx/s) cancels, ALO orders and ALO modifies still land in \~205-285 ms, which is why day-to-day monitoring looks fine.
- **Nov 12 upgrade (v112), a weekday release five days after v111:** ALO is 20-40 ms faster at 40k+ tx/s, still about twice its old level (ALO order 495 ms, fast cancel 255).
- **Same accounts, two speeds.** In the busiest 20 minutes of Nov 12, the accounts behind about 80 % of ALO orders saw them take 400 ms or more while their own fast cancels landed in 300 ms or less. The causes Hyperliquid named on Nov 11 (missing `fast` flag, non-Standard abstraction, recent non-trading actions) fit our cancel data, but they slow a whole account, cancels included. Under load, cancel + place now pulls a quote 250 ms sooner than a modify, at twice the transactions.

## Background

On Nov 10, FrothyBeverage published "Hyperliquid cancel priority under load". At 40k+ tx/s on Nov 8-9, 31 % of the failed cancels had been signed before the 8 bps priority-fee IOC that filled the order. Hyperliquid documents the opposite: cancels go ahead of every immediately executable order.

Femtos reproduced the numbers on the same 14 `replica_cmds` files (30.5 %, the same 19 bursts). Hyperliquid answered on Nov 11 with three causes that deprioritize an action: no `fast` flag on the cancel, an account abstraction other than Standard, and a non-trading action still in flight. The mempool section of the latency docs now lists these rules, and Hyperliquid confirmed on Nov 10 that they were live.

FrothyBeverage then asked whether modifies had been hit by the same regression. Femtos pulled the data to answer it. This piece follows up on both: did the cancel fix hold, and what happened to modifies?

## Data and method

Everything below comes from public chain data, read passively. Nothing was tested on mainnet.

| Source | What it gives | Coverage |
| --- | --- | --- |
| `replica_cmds` (Hyperliquid's S3, and a Femtos non-validator node) | every signed action, its nonce, the block it landed in | 44 weekday US opens, Sep 11 to Nov 11, plus Nov 12 |
| fills (`node_fills_by_block`, Hyperliquid's S3, loaded in a Femtos database) | maker fill joined to its taker, priority fee paid | same windows |
| `mempool_txs` of the Femtos node | validator bundles, as received before any block | from Nov 11 (archived hourly since) |

- **Latency** = block time minus the action's nonce, which signers set to their clock in ms. Medians, 10 ms bins; client clock skew moves single values, not a median over hundreds of thousands of actions.
- **Load** = signed actions in the block's second. Bands: below 20k, 30-40k and 40k+ tx/s.
- **Window** = from about 10 minutes before the US cash open (09:30 New York) to about 50 minutes after.
- **Kinds** split by what the docs treat differently: fast vs non-fast cancels, ALO vs GTC vs IOC (by priority fee), and `modify` / `batchModify` by the time-in-force of the new order. A GTC modify is executable, so it belongs to the slow lane by design; only ALO modifies are compared with cancels.

## Two months of US opens: one lane until Nov 5

For 39 straight opens, through six hardfork versions, fast cancels, ALO orders and ALO modifies landed together at \~245-300 ms, even at 40k+ tx/s. On Friday Nov 6 all three slowed at once. The Nov 9-10 fix brought cancels back; the ALO side stayed at about twice its old level, and the Nov 12 upgrade (v112) left it there.

![Signed to block, median at 40k+ tx/s, every weekday US open](figure/hyperliquid-priority-part2.png)

Nov 5 was the busiest open of the period (54 % of its seconds above 40k tx/s) and still ran at \~250 ms, so load alone does not explain Nov 6. Nov 6 brought no hardfork either: v110 had run since Saturday Oct 31, and v111 came on Saturday Nov 7.

## Modifies: about 2× slower under load

Until Nov 5, a modify or batchModify carrying ALO orders landed with cancels, even at 40k+ tx/s, and so did new ALO orders, which the docs say land "with similar end-to-end latency as cancels". On a calm network they still do. Under load, since Nov 6, they don't, and the cancel fix did not change that.

Median signed→block, ms:

| Action | Nov 11, below 20k tx/s | Nov 11, 30-40k | Nov 11, 40k+ | 40k+, Sep 11 to Nov 5 (39 opens) |
| --- | --- | --- | --- | --- |
| Fast cancel | 205 | 235 | 245 | 235-265 |
| ALO order | 205 | 335 | 515 | 245-265 |
| ALO order with priority fee | 205 | 325 | 515 | 245-275 |
| batchModify, ALO | 215 | 345 | 535 | 245-275 |
| modify, ALO | 245 | 395 | 595 | 255-335 |
| IOC, 8 bps priority fee | 255 | 275 | 345 | 245-305 |
| modify, GTC | 605 | 585 | 625 | 565-785 |
| batchModify, GTC | 525 | 545 | 575 | 555-595 |

- At 40k+ tx/s the median IOC paying 8 bps (345 ms) now takes less time from signature to block than the median ALO order (515 ms). The docs describe the reverse: cancels and ALO orders sent at time t "will almost always execute before IOC and GTC orders sent at time t".
- The priority fee on an ALO buys queue position after execution, not mempool priority, as documented. It doesn't change this delay.
- 98.5 % of batchModify actions carry ALO orders. Single `modify` was always 20-60 ms slower than batchModify, before and after.
- GTC modifies never moved: they are executable and sit in the slow lane by design.

### Modify, or cancel and place?

Under load, cancel + place takes a stale quote off the book about 250 ms sooner than a modify. The new quote lands no sooner, and it costs two actions instead of one.

| Moving a quote, 40k+ tx/s, Nov 12 (ms, median) | Old quote off the book | New quote on the book | Actions |
| --- | --- | --- | --- |
| batchModify, ALO | 505 | 505 | 1 |
| modify, ALO | 575 | 575 | 1 |
| fast cancel, then a new ALO order | 255 | 485-505 | 2 |

- Batch size changes nothing: batchModify ALO lands in 505 ms alone or with 2-10 modifies (495 with 11+), and new ALO orders in 485 alone, 505 in 2-10.
- A single `modify` is 70 ms slower than a `batchModify` of one. Switching to batchModify is the free gain.
- Below 20k tx/s everything lands in 205-215 ms, so cancel + place only pays during spikes. A middle path: cancel first only when the move is against the resting quote and the chain is busy.
- The cost is rate limits and block space. A batch counts as one request per IP but as one per order or cancel for the address limit. Cancels get extra room (min(limit + 100k, 2 × limit)), but during high congestion each address is limited to its previous day's maker share of block space (twice that share in our Oct 8 copy of the page), at a constant cost per signature, so cancel + place spends twice as much.

For the exchange: as long as an ALO modify is slower than a cancel, makers who switch to cancel + place add transactions exactly when the chain is busiest.

## The Nov 12 upgrade (v112)

Hyperliquid shipped v112 on Thursday Nov 12 at 10:43 UTC; the chain paused 57.6 s. Every network upgrade since at least late May had landed on a Saturday or Sunday morning, and v111 was only five days old. The public docs show no change that would explain it.

At today's US open (14:06-15:06 UTC, 425 seconds at 40k+ tx/s), v112 did not bring the ALO lane back. It is 20-40 ms faster than on Nov 11 and still about twice its pre-Nov 6 level.

| Median signed→block, 40k+ tx/s | Sep 11 to Nov 5 | Nov 11 (v111) | Nov 12 (v112) |
| --- | --- | --- | --- |
| Fast cancel | 235-265 | 245 | 255 |
| ALO order | 245-265 | 515 | 495 |
| batchModify, ALO | 245-275 | 535 | 505 |
| modify, ALO | 255-335 | 595 | 575 |
| IOC, 8 bps priority fee | 245-305 | 345 | 325 |

At 30-40k tx/s the gap is smaller (ALO 295 ms against 235 for fast cancels, 335 on Nov 11). On a calm network nothing changed: ALO 205, fast cancel 205.

So the timeline stands as: regression on Nov 6, cancels fixed on Nov 9-10, ALO orders and ALO modifies still slow under load after v112.

## What Hyperliquid's Nov 11 statement covers

Hyperliquid's statement explains the cancel losses users can fix themselves. The ALO step looks different: it hits the same accounts whose cancels are fast.

On Nov 11, in its API announcements channel, Hyperliquid wrote that during a recent congestion period 1 % of cancels were sent without the `fast` flag, 1 % were delayed because the account did not use Standard abstraction, and 0.5 % were delayed by recent non-trading actions: "unrelated to network congestion" and "fixed by simple adjustments by the user". Cancel prioritization "has functioned as designed for the vast majority of the past week", and optimizations for stress periods are under way, some already live.

On cancels the data agrees: 1.27-1.80 % of cancels lacked `fast` in our windows, and fast cancels are back at 245-255 ms. On ALO orders and ALO modifies, four things point away from those user-side causes:

- **Same accounts, two speeds.** In the busiest 20 minutes of Nov 12 (14:30-14:50 UTC, seconds above 40k tx/s), 418 accounts sent at least 30 ALO orders and 30 fast cancels; they carry 98 % of ALO orders. For 320 of them (84 % of their ALO orders), the ALO median is 400 ms or more while their own fast cancels land in 300 ms or less. The median gap per account is 241 ms. The rules Hyperliquid named slow every action of an account, cancels included, so they do not fit this pattern.
- **Broad, not a few accounts.** 86 % of ALO orders come from accounts whose own median is 400 ms or more, and accounts with 30-999 ALO orders sit at 534 ms. For batchModify ALO, 81 of the 94 accounts that also cancel show the same pattern (97 % of their modifies).
- **Timing.** Hyperliquid announced on Oct 26 that these rules would activate with the next upgrade, delayed them by one more upgrade on Oct 28, and wrote on Nov 10 that they "went live in this network upgrade": v111, Saturday Nov 7, the day after the Nov 6 step.
- **Size.** Each cause touches 0.5-1 % of cancels. Moving the median of all ALO orders by \~240 ms takes far more than that.

Two things we cannot rule out from outside. First, a documented rule that slows orders but not cancels, such as the congestion limit on each address's share of block space (now its previous day's maker share, twice that share in our Oct 8 copy of the page). Second, time spent on the client between signing and sending, which signed→block includes; that would take hundreds of independent makers holding ALO orders, and not cancels, from the same day. So we report the step as an observation and ask Hyperliquid below.

Accounts come from the node's order statuses, which give the user behind each order id and client order id. At 40k+ tx/s, 86 % of ALO orders and 81-100 % of fast cancels were matched to an account.

## Inside the pipeline: validator bundles

A non-validator node writes `mempool_txs`: what it receives before any block. It turns out to be validator bundles, not user transactions, and it shows that the queueing happens before broadcast, not inside blocks.

Nov 11 US open, 14:19-16:06 UTC:

- 99.7 % of actions arrived through one broadcaster address, in one bundle per block.
- Bundle arrival order matched block order exactly (zero inversions). Once a bundle is broadcast, nothing reorders it.

Nov 12 US open on v112, 14:06-15:06 UTC (102 million actions, all 100 % matched to a bundle):

- Bundles reach the Femtos node within about ±40 ms of their block's time, for every kind of action. So the extra 250-300 ms a modify or a new ALO order waits under load comes before its bundle is broadcast: on the client, at the API, or in the validators' queue. This data cannot tell them apart.

## Cancels: fixed on Hyperliquid's side

The failure the first report described is gone, and it did not come from makers adding the fast flag.

| Window (40k+ tx/s) | Losing fast cancels signed before the 8 bps IOC | Fast cancel, median signed→block | Cancels sent without `fast` |
| --- | --- | --- | --- |
| Nov 8-9 (the report's windows) | 30.6 % (n = 1,528) | 395 ms | 1.80 % |
| Nov 10 | 12.9 % | 265 ms | 1.48 % |
| Nov 11 | 1.4 % | 245 ms | 1.27 % |

- Only 1.5 % of the Nov 8-9 "signed before" cancels lacked the `fast` flag, and the share of cancels sent without it barely moved. The fix came from the network, not from users adding the flag.
- The hardfork stayed at v111 across all three windows: the fix shipped without a version bump.

## What it means for makers and takers

Under load, a maker can pull quotes fast but cannot put them back fast. Depth disappears at cancel speed (\~245 ms) and comes back at ALO speed (\~515-675 ms), so books thin out during spikes and refill slowly.

- **Pulling works.** A fast cancel (245 ms) beats an IOC paying 8 bps (345 ms) sent at the same time.
- **Re-quoting or moving doesn't.** An ALO order or ALO modify (515-675 ms) loses to that IOC, and to the next one.

## Questions for the Hyperliquid team

1. What changed on Nov 6? No post in the API announcements channel between Oct 30 and Nov 7 covers it. There was no hardfork (v110 since Saturday Oct 31, v111 on Saturday Nov 7) and no new non-validator binary. Nov 5 was the busiest open of the two months and still ran at \~250 ms across the board.
2. Was the Nov 9-10 fix scoped to fast cancels on purpose? Is a fast lane planned for ALO orders and ALO modifies, as the docs describe? Until then, a maker who switches from modify to cancel + place doubles its transactions during spikes.
3. Did v112 touch mempool prioritization? And when did the congestion limit go from twice the previous day's maker share of block space to once that share? Can that limit, or another rule, slow an account's ALO orders under congestion while its cancels stay fast?
4. The `fast` flag description on the exchange endpoint page still says it "has no other effect", while the latency page makes mempool priority depend on it. Which page is current?

## Limits

- Latency uses the signer's clock (the nonce). A median over hundreds of thousands of actions is robust to skew; a single action is not.
- Signed→block starts at the signature. Time on the client before sending, the hop to the API and the validators' queue all count, and this data cannot separate them.
- One window a day, around the US open. The 40k+ band is thin on some days (Oct 30, Nov 2-3): read the 30-40k band there.
- `mempool_txs` exists only from Nov 11, so nothing before can be split into before and after broadcast. On Nov 12 the Femtos node wrote no bundles from 10:43 to 12:07 UTC, while it streamed blocks from an upstream peer that did not forward them; the US open is covered.

## Appendix: reproduce it

Everything the figure and the latency tables show is rebuilt from Hyperliquid's public `replica_cmds` with the code in this repository. See [Reproduce](#reproduce) below.

- `replica_cmds`: `s3://hl-mainnet-node-data/replica_cmds/<period>/<date>/<height>.lz4` (requester pays). Each period folder starts when Hyperliquid's writing node starts.
- Latency per action: block time minus nonce, every signed action of every bundle, grouped by kind and by the actions counted in the block's second.
- The raw histograms of all 45 opens are in `data/opens/` (kind × minute × load in 2.5k tx/s steps × 10 ms bins, plus load per second), so the tables can be checked without downloading anything.

---

## Reproduce

```
.
├── actlat/            Rust: signed→block latency of every action in replica_cmds, by kind and chain load
├── acctlat/           Rust: the same per account (needs a node's order statuses, see below)
├── scripts/
│   ├── fetch_open.py   streams the replica_cmds files around one US open from Hyperliquid's S3 into actlat
│   ├── make_tables.sh  rebuilds every table the figure reads from data/opens (no download)
│   ├── tab3.py         median per action family and load band, one line per open → data/tab44.txt
│   ├── loadcurve.py    median per family and 2.5k tx/s load step → data/lc.tsv
│   ├── loadcurve5.py   the same in 5k steps → data/lc5_*.tsv
│   ├── part2.py        the figure → figure/hyperliquid-priority-part2.png
│   └── acctan.py       per-account summary of acctlat's output
├── data/
│   ├── opens/          raw histograms of 45 US opens (Sep 11 to Nov 12, 2026), ~150 MB
│   └── *.tsv, tab44.txt
└── figure/
```

**1. Check the numbers from the histograms (no download)**

```sh
python3 -m pip install matplotlib
scripts/make_tables.sh          # ~10 min, pure Python
python3 scripts/part2.py        # redraws the figure from the rebuilt tables
```

`make_tables.sh` on the histograms in `data/opens/` gives back the committed tables byte for byte, and `part2.py` draws the same figure pixel for pixel.

**2. Rebuild a histogram from Hyperliquid's public data**

```sh
(cd actlat && cargo build --release)
# rclone and lz4 installed; AWS credentials in the environment (the bucket is requester pays)
python3 scripts/fetch_open.py 20261105      # one file before the 09:30 New York open + 4 after
```

One open is 5 files of 1.2 to 2 GB (lz4). From AWS Tokyo (ap-northeast-1) only the request fees apply; from outside AWS, data transfer is about $0.09-0.11 per GB, so roughly $1 per open.

What `actlat` does, in one line: for every signed action of every bundle, `latency = block time - nonce` (the nonce is the signer's clock in ms), histogrammed in 10 ms bins by action kind and by the number of actions in the block's second. Kinds split what the docs treat differently: `cancel` / `cancelByCloid` with or without `fast`, ALO / GTC / IOC (IOC by priority fee: none, under 8 bps, 8 bps and more), `modify` / `batchModify` by the time-in-force of the new order(s) and by batch size.

The Nov 12 open was read from the Femtos node's own `replica_cmds` (the same files later land in the public bucket, period `2026-11-12T10:43:59Z`).

**3. What this repository does not rebuild**

- **Per account** ("same accounts, two speeds"): `replica_cmds` carries no user per action. `acctlat` gets it from `node_order_statuses_by_block` (user per order id and client order id), which only a node writes; it is not in the public bucket. Run a non-validator node with order statuses on, then `acctlat T0 T1 OUT STATUS_FILE... -- REPLICA_FILE...`.
- **Cancels** (losing fast cancels signed before the IOC that filled them): built from maker fills joined to their taker in `node_fills_by_block` (public), with each cancel's signing time from `replica_cmds`. The shares are hard-coded at the top of `part2.py`.
- **Validator bundles**: `mempool_txs` is written by a node and kept for two hours; Femtos archives it since Nov 11. It supports the "the delay is before the block is built" note, not a headline number.

---

Data and code by [femtos.xyz](https://femtos.xyz), Hyperliquid data: HyperCore, HyperEVM, Elysium. Research with FrothyBeverage.
