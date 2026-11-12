// actlat: signed->block latency (block time - nonce) of every action kind, by chain load (actions/s of the block's second)
// stdin: replica_cmds lines. stdout: kind  bucket  n  p25  p50  p75  p90  (ms, latencies kept in -50..5000)
// actlat OUT (v2): also writes the raw material, so any later question is a query, not a re-download:
//   OUT.hist.tsv  kind  minute(unix/60)  load_k(actions/s of the second, floor to 2.5k)  bin_ms(10 ms bins, -50..5000)  count
//   OUT.load.tsv  second(unix)  actions  blocks
//   OUT.out.tsv   kind  minute  below(-50)  above(5000)  (latencies outside the histogram)
use serde::Deserialize;
use serde_json::value::RawValue;
use serde_json::Value;
use std::collections::{BTreeMap, HashMap};
use std::io::{BufRead, BufReader};

#[derive(Deserialize)]
struct Line<'a> { #[serde(borrow)] abci_block: Block<'a> }
#[derive(Deserialize)]
struct Block<'a> { time: &'a str, #[serde(borrow)] signed_action_bundles: Vec<(serde::de::IgnoredAny, Bundle<'a>)> }
#[derive(Deserialize)]
struct Bundle<'a> { #[serde(borrow)] signed_actions: Vec<SA<'a>> }
#[derive(Deserialize)]
struct SA<'a> { #[serde(borrow)] action: &'a RawValue, nonce: u64 }
#[derive(Deserialize)]
struct Head { #[serde(rename = "type")] t: String, orders: Option<Vec<Value>>, grouping: Option<Value>, f: Option<bool>, order: Option<Value>, modifies: Option<Vec<Value>> }

fn parse_time_ms(s: &str) -> i64 {
    // 2026-11-11T14:31:32.201642769
    let (d, t) = s.split_at(10);
    let y: i64 = d[0..4].parse().unwrap(); let m: i64 = d[5..7].parse().unwrap(); let dd: i64 = d[8..10].parse().unwrap();
    let t = &t[1..];
    let hh: i64 = t[0..2].parse().unwrap(); let mm: i64 = t[3..5].parse().unwrap(); let ss: i64 = t[6..8].parse().unwrap();
    let frac = if t.len() > 9 { &t[9..] } else { "" };
    let ms: i64 = if frac.len() >= 3 { frac[..3].parse().unwrap() } else { 0 };
    let (yy, mo) = if m <= 2 { (y - 1, m + 9) } else { (y, m - 3) };
    let era = yy.div_euclid(400); let yoe = yy - era * 400;
    let doy = (153 * mo + 2) / 5 + dd - 1; let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146097 + doe - 719468;
    ((days * 24 + hh) * 60 + mm) * 60_000 + ss * 1000 + ms
}

fn kind(h: &Head) -> String {
    match h.t.as_str() {
        "order" => {
            let ords = h.orders.as_deref().unwrap_or(&[]);
            let g = h.grouping.as_ref();
            let p = g.and_then(|g| g.get("p")).and_then(|p| p.as_u64()).unwrap_or(0);
            let gs = g.and_then(|g| g.as_str()).unwrap_or("");
            let mut tifs: Vec<String> = ords.iter().map(|o| {
                let t = o.get("t");
                if let Some(l) = t.and_then(|t| t.get("limit")) { l.get("tif").and_then(|x| x.as_str()).unwrap_or("?").to_string() }
                else if let Some(tr) = t.and_then(|t| t.get("trigger")) {
                    format!("trigger_{}_{}", tr.get("tpsl").and_then(|x| x.as_str()).unwrap_or("?"),
                        if tr.get("isMarket").and_then(|x| x.as_bool()).unwrap_or(false) { "mkt" } else { "lmt" })
                } else { "?".into() }
            }).collect();
            tifs.sort(); tifs.dedup();
            let base = if tifs.len() == 1 { tifs[0].clone() } else if tifs.is_empty() { "empty".into() } else { "mixed".into() };
            let base = if base == "Ioc" { if p >= 80000 { "Ioc_8bps+".to_string() } else if p > 0 { "Ioc_fee<8bps".into() } else { "Ioc_nofee".into() } } else { base };
            let base = if base == "Gtc" || base == "Alo" { if p > 0 { format!("{base}_fee") } else { base } } else { base };
            let base = if base == "Alo" || base == "Alo_fee" { format!("{base}{}", nb(ords.len())) } else { base };
            if gs == "normalTpsl" || gs == "positionTpsl" { format!("order_{gs}") } else { format!("order_{base}") }
        }
        "cancel" | "cancelByCloid" => format!("{}_{}", h.t, match h.f { Some(true) => "fast", _ => "nofast" }),
        // modify / batchModify split by the tif of the new order(s): Alo (non-executable) vs Gtc/Ioc (executable)
        "modify" => format!("modify_{}", tif_set(h.order.iter().collect())),
        "batchModify" => { let m = h.modifies.as_deref().unwrap_or(&[]);
            format!("batchModify_{}{}", tif_set(m.iter().filter_map(|m| m.get("order")).collect()), nb(m.len())) }
        t => t.to_string(),
    }
}

fn nb(n: usize) -> &'static str { if n <= 1 { "" } else if n <= 10 { "_x2-10" } else { "_x11+" } }

fn tif_set(ords: Vec<&Value>) -> String {
    let mut tifs: Vec<String> = ords.iter().map(|o| {
        let t = o.get("t");
        if let Some(l) = t.and_then(|t| t.get("limit")) { l.get("tif").and_then(|x| x.as_str()).unwrap_or("?").to_string() }
        else if t.and_then(|t| t.get("trigger")).is_some() { "trigger".into() } else { "?".into() }
    }).collect();
    tifs.sort(); tifs.dedup();
    if tifs.len() == 1 { tifs.remove(0) } else if tifs.is_empty() { "empty".into() } else { "mixed".into() }
}

fn main() {
    use std::io::Write;
    let out = std::env::args().nth(1);
    // (sec, kind) -> histogram 10 ms bins; sec -> actions, blocks; (kind, minute) -> (below, above)
    let mut hist: HashMap<(i64, String), Vec<u32>> = HashMap::new();
    let mut tx: BTreeMap<i64, u64> = BTreeMap::new();
    let mut blocks: BTreeMap<i64, u64> = BTreeMap::new();
    let mut outl: BTreeMap<(String, i64), (u64, u64)> = BTreeMap::new();
    let stdin = std::io::stdin();
    let mut rd = BufReader::with_capacity(1 << 24, stdin.lock());
    let mut buf = String::new();
    loop {
        buf.clear();
        if rd.read_line(&mut buf).unwrap() == 0 { break; }
        let l: Line = match serde_json::from_str(buf.trim_end()) { Ok(l) => l, Err(_) => continue };
        let bms = parse_time_ms(l.abci_block.time);
        let sec = bms.div_euclid(1000);
        *blocks.entry(sec).or_default() += 1;
        for (_, b) in l.abci_block.signed_action_bundles {
            for sa in b.signed_actions {
                *tx.entry(sec).or_default() += 1;
                let h: Head = match serde_json::from_str(sa.action.get()) { Ok(h) => h, Err(_) => continue };
                let lat = bms - sa.nonce as i64;
                let k = kind(&h);
                if !(-50..=5000).contains(&lat) {
                    let e = outl.entry((k, sec.div_euclid(60))).or_default();
                    if lat < -50 { e.0 += 1 } else { e.1 += 1 }
                    continue;
                }
                let bin = ((lat + 50) / 10) as usize;
                hist.entry((sec, k)).or_insert_with(|| vec![0; 506])[bin] += 1;
            }
        }
    }
    if let Some(o) = &out {
        let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{o}.load.tsv")).unwrap());
        for (s, n) in &tx { writeln!(f, "{s}\t{n}\t{}", blocks.get(s).unwrap_or(&0)).unwrap(); }
        let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{o}.out.tsv")).unwrap());
        for ((k, m), (a, b)) in &outl { writeln!(f, "{k}\t{m}\t{a}\t{b}").unwrap(); }
        // (kind, minute, load_k) -> bins
        let mut fine: BTreeMap<(String, i64, u64), Vec<u64>> = BTreeMap::new();
        for ((sec, k), h) in &hist {
            let lk = tx.get(sec).unwrap_or(&0) / 2500 * 2500;
            let a = fine.entry((k.clone(), sec.div_euclid(60), lk)).or_insert_with(|| vec![0; 506]);
            for (i, c) in h.iter().enumerate() { a[i] += *c as u64; }
        }
        let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{o}.hist.tsv")).unwrap());
        for ((k, m, lk), a) in &fine {
            for (i, c) in a.iter().enumerate() { if *c > 0 { writeln!(f, "{k}\t{m}\t{lk}\t{}\t{c}", i as i64 * 10 - 50).unwrap(); } }
        }
    }
    let bk = |v: u64| if v < 20000 { "<20k" } else if v < 30000 { "20-30k" } else if v < 40000 { "30-40k" } else { "40k+" };
    let mut agg: BTreeMap<(String, &str), Vec<u64>> = BTreeMap::new();
    for ((sec, k), h) in hist {
        let b = bk(*tx.get(&sec).unwrap_or(&0));
        let a = agg.entry((k.clone(), b)).or_insert_with(|| vec![0; 506]);
        for (i, c) in h.iter().enumerate() { a[i] += *c as u64; }
        let a = agg.entry((k, "all")).or_insert_with(|| vec![0; 506]);
        for (i, c) in h.iter().enumerate() { a[i] += *c as u64; }
    }
    for ((k, b), a) in agg {
        let n: u64 = a.iter().sum();
        let q = |f: f64| { let t = (n as f64 * f).ceil() as u64; let mut acc = 0; for (i, c) in a.iter().enumerate() { acc += c; if acc >= t.max(1) { return i as i64 * 10 - 45; } } 0 };
        println!("{k}\t{b}\t{n}\t{}\t{}\t{}\t{}", q(0.25), q(0.5), q(0.75), q(0.9));
    }
}
