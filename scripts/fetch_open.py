#!/usr/bin/env python3
"""fetch_open.py DATE [--out DIR] [--files N] [--like DATA_DIR]

Rebuilds the histogram of one US cash open (09:30 New York) from Hyperliquid's public S3 bucket:
streams the replica_cmds files around the open (rclone + lz4), pipes them into actlat, and writes
  DIR/opens/<date>.hist.csv.gz   kind,unix_minute,load_bucket,latency_ms,count
  DIR/opens/<date>.load.csv      unix_second,actions,blocks
  DIR/opens/<date>.out.csv       latencies outside -50..5000 ms
  DIR/opens/<date>.summary.csv   quantiles per kind and load band
  DIR/opens.csv                  the open's row (period folder, files read, hardfork)
DIR defaults to out/, so the published data/ is never overwritten.

--like data   read exactly the files listed for that date in data/opens.csv (to compare with ours, compare.py)
--files N     otherwise: one file before the open plus N-1 after (default 5, about an hour)

The bucket is requester pays: rclone uses your AWS credentials (environment variables, or ~/.aws) and your
account pays the transfer. Needs rclone, lz4 and actlat built: (cd actlat && cargo build --release).
"""
import argparse, csv, datetime, os, re, subprocess, sys
from zoneinfo import ZoneInfo

BUCKET = ":s3,provider=AWS,env_auth=true,region=ap-northeast-1,requester_pays=true:hl-mainnet-node-data/replica_cmds"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTLAT = os.path.join(ROOT, 'actlat', 'target', 'release', 'actlat')
HEAD = ['date', 's3_period', 'files', 'open_file_first_block_utc', 'us_open_utc', 'hardfork']

ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
ap.add_argument('date', help='YYYY-MM-DD or YYYYMMDD')
ap.add_argument('--out', default=os.path.join(ROOT, 'out'))
ap.add_argument('--files', type=int, default=5)
ap.add_argument('--like', metavar='DATA_DIR', help='read the files that DATA_DIR/opens.csv lists for this date')
a = ap.parse_args()
D = a.date.replace('-', ''); day = f'{D[:4]}-{D[4:6]}-{D[6:]}'
out = os.path.abspath(a.out); os.makedirs(os.path.join(out, 'opens'), exist_ok=True)
if not os.access(ACTLAT, os.X_OK): sys.exit(f'actlat not built: (cd {os.path.join(ROOT, "actlat")} && cargo build --release)')

def run(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True)
    return r.stdout, r.stderr

def ls(path, must=False):
    o, e = run(f'rclone lsf -q "{BUCKET}/{path}"')
    if must and not o: sys.exit(f'rclone could not list replica_cmds/{path}:\n{e.strip()}\n(AWS credentials set? the bucket is requester pays)')
    return o.split()

def probe(p, h):
    """time and hardfork of the first block of a file, from its first ~12 MB"""
    o, _ = run(f'rclone cat -q --count 12000000 "{BUCKET}/{p}/{D}/{h}.lz4" 2>/dev/null | lz4 -dc 2>/dev/null | head -c 20000000 | head -1')
    m = re.search(r'"time":"([0-9T:.-]+)"', o); hf = re.search(r'"hardfork":\{"version":(\d+)', o)
    if not m: return None, '?'
    return datetime.datetime.fromisoformat(m.group(1)[:26]).replace(tzinfo=datetime.timezone.utc), (hf.group(1) if hf else '?')

d = datetime.date(int(D[:4]), int(D[4:6]), int(D[6:]))
T = datetime.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ZoneInfo('America/New_York')).astimezone(datetime.timezone.utc)

if a.like:
    row = next((r for r in csv.DictReader(open(os.path.join(a.like, 'opens.csv'))) if r['date'] == day), None)
    if not row: sys.exit(f'{day} is not in {a.like}/opens.csv')
    p, hs = row['s3_period'], [int(x) for x in row['files'].split()]
    tk, hf = probe(p, hs[1] if len(hs) > 1 else hs[0])
else:
    best = None
    for p in reversed([x.strip('/') for x in ls('', must=True)]):          # period folders, newest first
        files = sorted(int(x[:-4]) for x in ls(f'{p}/{D}/') if x.endswith('.lz4'))
        if len(files) < 3: continue
        t0, _ = probe(p, files[0]); tn, _ = probe(p, files[-1])
        if not t0 or not tn or not (t0 <= T <= tn + datetime.timedelta(minutes=20)): continue
        k = max(0, min(round((T - t0) / (tn - t0) * (len(files) - 1)), len(files) - 1))
        for _ in range(6):                                           # the file whose first block is the last one before 09:30
            tk, hf = probe(p, files[k])
            if tk is None: break
            if tk > T and k > 0: k -= 1; continue
            if k + 1 < len(files):
                tk1, _ = probe(p, files[k + 1])
                if tk1 and tk1 <= T: k += 1; continue
            break
        best = (p, files[max(0, k - 1):max(0, k - 1) + a.files], tk, hf); break
    if not best: sys.exit(f'no replica_cmds files cover {day} 09:30 New York')
    p, hs, tk, hf = best

print(f'{day}: period {p}, files {" ".join(map(str, hs))}, hardfork {hf}', flush=True)
os.chdir(os.path.join(out, 'opens'))
cat = ' ; '.join(f'rclone cat -q "{BUCKET}/{p}/{D}/{h}.lz4" | lz4 -dc' for h in hs)
subprocess.run(f'( {cat} ) | "{ACTLAT}" {day} > {day}.summary.csv && gzip -f {day}.hist.csv', shell=True, check=True)

opens = os.path.join(out, 'opens.csv')
rows = [r for r in csv.DictReader(open(opens))] if os.path.exists(opens) else []
rows = [r for r in rows if r['date'] != day] + [dict(zip(HEAD, [day, p, ' '.join(map(str, hs)), tk.isoformat() if tk else '', T.isoformat(), hf]))]
with open(opens, 'w', newline='') as f:
    w = csv.DictWriter(f, HEAD, lineterminator='\n'); w.writeheader(); w.writerows(sorted(rows, key=lambda r: r['date']))
print(f'done: {os.path.join(out, "opens", day + ".hist.csv.gz")}')
