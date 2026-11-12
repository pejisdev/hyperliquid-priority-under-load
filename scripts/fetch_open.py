#!/usr/bin/env python3
# fetch_open.py YYYYMMDD [nfiles] : runs actlat over the replica_cmds files around the US cash open (09:30 New York) of that day,
# streamed from Hyperliquid's public S3 bucket (requester pays: your AWS credentials, through rclone env_auth).
# Starts one file before the open (calm reference), nfiles in all (the paper used 5, about an hour).
# Writes data/opens/<date>.hist.csv.gz, <date>.load.csv, <date>.out.csv, <date>.summary.csv, and the open's row in data/opens.csv.
# Needs: rclone, lz4, and actlat built (cargo build --release in actlat/).
import subprocess, sys, json, re, datetime, os, csv
from zoneinfo import ZoneInfo
R = ":s3,provider=AWS,env_auth=true,region=ap-northeast-1,requester_pays=true:hl-mainnet-node-data/replica_cmds"
D = sys.argv[1]; NF = int(sys.argv[2]) if len(sys.argv) > 2 else 5
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTLAT = os.path.join(ROOT, 'actlat', 'target', 'release', 'actlat')
os.makedirs(os.path.join(ROOT, 'data', 'opens'), exist_ok=True)
os.chdir(os.path.join(ROOT, 'data', 'opens'))
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True).stdout
d = datetime.date(int(D[:4]), int(D[4:6]), int(D[6:]))
T = datetime.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ZoneInfo('America/New_York')).astimezone(datetime.timezone.utc)
periods = [p.strip('/') for p in sh(f'rclone lsf "{R}/" 2>/dev/null').split()]
def probe(p, h):
    out = sh(f'rclone cat --count 12000000 "{R}/{p}/{D}/{h}.lz4" 2>/dev/null | lz4 -dc 2>/dev/null | head -c 20000000 | head -1')
    m = re.search(r'"time":"([0-9T:.-]+)"', out); hf = re.search(r'"hardfork":\{"version":(\d+)', out)
    if not m: return None, None
    return datetime.datetime.fromisoformat(m.group(1)[:26]).replace(tzinfo=datetime.timezone.utc), (hf.group(1) if hf else '?')
best = None
for p in reversed(periods):
    files = sorted(int(x[:-4]) for x in sh(f'rclone lsf "{R}/{p}/{D}/" 2>/dev/null').split() if x.endswith('.lz4'))
    if len(files) < 3: continue
    t0, _ = probe(p, files[0]); tn, _ = probe(p, files[-1])
    if not t0 or not tn or not (t0 <= T <= tn + datetime.timedelta(minutes=20)): continue
    k = round((T - t0) / (tn - t0) * (len(files) - 1)); k = max(0, min(k, len(files) - 1))
    for _ in range(6):
        tk, hf = probe(p, files[k])
        if tk is None: break
        if tk > T and k > 0: k -= 1; continue
        if k + 1 < len(files):
            tk1, _ = probe(p, files[k + 1])
            if tk1 and tk1 <= T: k += 1; continue
        break
    best = (p, files[max(0, k - 1):k - 1 + NF] if k > 0 else files[0:NF], tk, hf); break  # one file before the open (calm reference) + NF-1
if not best: print(f'{D} no file'); sys.exit()
p, hs, tk, hf = best
cmd = ' ; '.join(f'rclone cat "{R}/{p}/{D}/{h}.lz4" 2>/dev/null | lz4 -dc' for h in hs)
day = f'{D[:4]}-{D[4:6]}-{D[6:]}'
subprocess.run(f'( {cmd} ) | {ACTLAT} {day} > {day}.summary.csv && gzip -f {day}.hist.csv', shell=True, check=True)
# one row per open in data/opens.csv (replaced if the open was already there)
OPENS = os.path.join(ROOT, 'data', 'opens.csv')
HEAD = ['date', 's3_period', 'files', 'open_file_first_block_utc', 'us_open_utc', 'hardfork']
rows = [r for r in csv.DictReader(open(OPENS))] if os.path.exists(OPENS) else []
rows = [r for r in rows if r['date'] != day] + [dict(zip(HEAD, [day, p, ' '.join(map(str, hs)), tk.isoformat(), T.isoformat(), hf]))]
with open(OPENS, 'w', newline='') as f:
    w = csv.DictWriter(f, HEAD, lineterminator='\n'); w.writeheader(); w.writerows(sorted(rows, key=lambda r: r['date']))
print('done', day, p, ' '.join(map(str, hs)), f'hardfork {hf}')
