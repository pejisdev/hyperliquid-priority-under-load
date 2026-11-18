#!/bin/bash
# run_open.sh DATE PERIOD B0 : one US open, for the other scripts of scripts/part3.
#   DATE   2026-11-12            PERIOD  S3 period folder        B0  first block of the open window (data/opens.csv; data/part3/opens_since_nov13.csv)
# Needs: a ClickHouse with HyperCore fills (table hypercore_fills, below), rclone + lz4 + AWS credentials for Hyperliquid's
# requester-pays bucket, and flightlat built (cd flightlat && cargo build --release).
# hypercore_fills: one row per fill side, from a node's node_fills_by_block (also in Hyperliquid's public bucket):
#   block_number, block_time DateTime64(3), coin, side ('B'/'A'), px, sz, oid, cloid FixedString(16), user, tid, crossed (1 = taker side),
#   priority_gas (the priority fee of a taker fill, in HYPE)
# Writes o.DATE.fills.tsv (maker fills + 1 s / 5 s markouts), o.DATE.takers.tsv, o.DATE.pg.tsv and o.DATE.hype (priority fee per taker fill, HYPE price),
# o.DATE.cloids, then o.DATE.place.tsv and o.DATE.load.tsv.
set -e; D=$1; P=$2; B0=$3; B1=$((B0 + 50000)); O=o.$D
CH=${CH:-clickhouse-client}
FLIGHTLAT=${FLIGHTLAT:-flightlat/target/release/flightlat}
$CH --join_algorithm=full_sorting_merge > $O.fills.tsv <<SQL
WITH m AS (SELECT block_time t, coin, side, toFloat64(px) p, toFloat64(sz) z, oid, cloid, user, block_number bn, tid FROM hypercore_fills
           WHERE block_number >= $B0 AND block_number < $B1 AND crossed = 0 AND coin NOT LIKE '#%' AND coin NOT LIKE '@%'),
     tr AS (SELECT coin, block_time t, toFloat64(px) p FROM hypercore_fills WHERE block_number >= $B0 AND block_number < $B1 + 300 AND crossed = 1 AND coin NOT LIKE '#%' AND coin NOT LIKE '@%')
SELECT lower(hex(m.cloid)), m.oid, lower(hex(m.user)), m.coin, m.side, toUnixTimestamp64Milli(m.t), m.p, m.p * m.z,
       if(m.side = 'B', 1, -1) * (a.p - m.p) / m.p * 1e4, if(m.side = 'B', 1, -1) * (b.p - m.p) / m.p * 1e4, abs(a.p - m.p) / m.p * 1e4, m.bn, m.tid
FROM (SELECT *, t + INTERVAL 1 SECOND t1, t + INTERVAL 5 SECOND t5 FROM m) m
ASOF LEFT JOIN tr a ON m.coin = a.coin AND a.t <= m.t1
ASOF LEFT JOIN tr b ON m.coin = b.coin AND b.t <= m.t5
FORMAT TSV
SQL
$CH > $O.takers.tsv <<SQL
SELECT tid, lower(hex(cloid)), lower(hex(user)) FROM hypercore_fills WHERE block_number >= $B0 AND block_number < $B1 AND crossed = 1 AND coin NOT LIKE '#%' AND coin NOT LIKE '@%' FORMAT TSV
SQL
$CH > $O.pg.tsv <<SQL
SELECT tid, toFloat64(priority_gas), lower(hex(user)) FROM hypercore_fills WHERE block_number >= $B0 AND block_number < $B1 AND crossed = 1 AND priority_gas > 0 AND coin NOT LIKE '#%' AND coin NOT LIKE '@%' FORMAT TSV
SQL
$CH > $O.hype <<SQL
SELECT avg(toFloat64(px)) FROM hypercore_fills WHERE block_number >= $B0 AND block_number < $B1 AND coin = 'HYPE' FORMAT TSV
SQL
( awk -F'\t' '$1 != "00000000000000000000000000000000" {print "0x"$1}' $O.fills.tsv; awk -F'\t' '$2 != "00000000000000000000000000000000" {print "0x"$2}' $O.takers.tsv ) | sort -u > $O.cloids
echo "fills $(wc -l < $O.fills.tsv) cloids $(wc -l < $O.cloids)"
BUCKET=":s3,provider=AWS,env_auth=true,region=ap-northeast-1,requester_pays=true:hl-mainnet-node-data/replica_cmds"
# the file before the window too: a quote can be placed up to ~10k blocks before it is hit
FILES="$((B0 - 10000)) $B0 $((B0 + 10000)) $((B0 + 20000)) $((B0 + 30000)) $((B0 + 40000))"
( for h in $FILES; do rclone cat -q "$BUCKET/$P/${D//-/}/$h.lz4" | lz4 -dc; done ) | $FLIGHTLAT $O.cloids $O
echo DONE $D
