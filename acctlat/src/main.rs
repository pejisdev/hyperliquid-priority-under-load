// acctlat: signed->block latency per ACCOUNT and action kind, by chain load, over a time window.
// The account comes from node_order_statuses_by_block (user per oid and per cloid), joined to replica_cmds actions:
//   order / batchModify / modify -> cloid of the (first) order, else the modified oid; cancelByCloid -> cloid; cancel -> oid.
// usage: acctlat T0 T1 OUT STATUS_FILE... -- REPLICA_FILE...      (T0/T1 = "2026-11-12T14:30:00", block time UTC)
// writes OUT.csv: user,kind,load_band,n,p25_ms,p50_ms,p75_ms   and OUT.cover.csv: kind,load_band,total,resolved
use serde::Deserialize;
use serde_json::value::RawValue;
use serde_json::Value;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};

#[derive(Deserialize)]
struct SLine<'a> { #[serde(borrow)] block_time: &'a str, #[serde(borrow)] events: Vec<Ev<'a>> }
#[derive(Deserialize)]
struct Ev<'a> { #[serde(borrow)] user: &'a str, #[serde(borrow)] order: Ord<'a> }
#[derive(Deserialize)]
struct Ord<'a> { oid: u64, #[serde(borrow)] cloid: Option<&'a str> }

#[derive(Deserialize)]
struct Line<'a> { #[serde(borrow)] abci_block: Block<'a> }
#[derive(Deserialize)]
struct Block<'a> { time: &'a str, #[serde(borrow)] signed_action_bundles: Vec<(serde::de::IgnoredAny, Bundle<'a>)> }
#[derive(Deserialize)]
struct Bundle<'a> { #[serde(borrow)] signed_actions: Vec<SA<'a>> }
#[derive(Deserialize)]
struct SA<'a> { #[serde(borrow)] action: &'a RawValue, nonce: u64 }
#[derive(Deserialize)]
struct Head { #[serde(rename = "type")] t: String, orders: Option<Vec<Value>>, grouping: Option<Value>, f: Option<bool>,
    order: Option<Value>, modifies: Option<Vec<Value>>, cancels: Option<Vec<Value>>, oid: Option<Value> }

fn parse_time_ms(s: &str) -> i64 {
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

fn tif_of(o: &Value) -> String {
    let t = o.get("t");
    if let Some(l) = t.and_then(|t| t.get("limit")) { l.get("tif").and_then(|x| x.as_str()).unwrap_or("?").to_string() }
    else if t.and_then(|t| t.get("trigger")).is_some() { "trigger".into() } else { "?".into() }
}
fn tif_set(ords: Vec<&Value>) -> String {
    let mut v: Vec<String> = ords.iter().map(|o| tif_of(o)).collect();
    v.sort(); v.dedup();
    if v.len() == 1 { v.remove(0) } else if v.is_empty() { "empty".into() } else { "mixed".into() }
}
// same kinds as actlat, without the batch-size suffix
fn kind(h: &Head) -> String {
    match h.t.as_str() {
        "order" => {
            let ords = h.orders.as_deref().unwrap_or(&[]);
            let g = h.grouping.as_ref();
            let p = g.and_then(|g| g.get("p")).and_then(|p| p.as_u64()).unwrap_or(0);
            let gs = g.and_then(|g| g.as_str()).unwrap_or("");
            if gs == "normalTpsl" || gs == "positionTpsl" { return format!("order_{gs}"); }
            let base = tif_set(ords.iter().collect());
            let base = if base == "Ioc" { if p >= 80000 { "Ioc_8bps+".to_string() } else if p > 0 { "Ioc_fee<8bps".into() } else { "Ioc_nofee".into() } } else { base };
            let base = if (base == "Gtc" || base == "Alo") && p > 0 { format!("{base}_fee") } else { base };
            format!("order_{base}")
        }
        "cancel" | "cancelByCloid" => format!("{}_{}", h.t, match h.f { Some(true) => "fast", _ => "nofast" }),
        "modify" => format!("modify_{}", tif_set(h.order.iter().collect())),
        "batchModify" => format!("batchModify_{}", tif_set(h.modifies.as_deref().unwrap_or(&[]).iter().filter_map(|m| m.get("order")).collect())),
        t => t.to_string(),
    }
}

fn cl(v: Option<&Value>) -> Option<u128> {
    let s = v?.as_str()?;
    u128::from_str_radix(s.strip_prefix("0x")?, 16).ok()
}
struct Maps { by_oid: HashMap<u64, u32>, by_cloid: HashMap<u128, u32> }
fn oid_or_cloid(m: &Maps, v: Option<&Value>) -> Option<u32> {
    let v = v?;
    if let Some(o) = v.as_u64() { return m.by_oid.get(&o).copied(); }
    cl(Some(v)).and_then(|c| m.by_cloid.get(&c).copied())
}
fn resolve(h: &Head, m: &Maps) -> Option<u32> {
    let order_cloid = |o: Option<&Value>| cl(o.and_then(|o| o.get("c"))).and_then(|c| m.by_cloid.get(&c).copied());
    match h.t.as_str() {
        "order" => order_cloid(h.orders.as_ref().and_then(|v| v.first())),
        "cancelByCloid" => cl(h.cancels.as_ref().and_then(|v| v.first()).and_then(|c| c.get("cloid"))).and_then(|c| m.by_cloid.get(&c).copied()),
        "cancel" => h.cancels.as_ref().and_then(|v| v.first()).and_then(|c| c.get("o")).and_then(|o| o.as_u64()).and_then(|o| m.by_oid.get(&o).copied()),
        "modify" => order_cloid(h.order.as_ref()).or_else(|| oid_or_cloid(m, h.oid.as_ref())),
        "batchModify" => { let f = h.modifies.as_ref().and_then(|v| v.first());
            order_cloid(f.and_then(|x| x.get("order"))).or_else(|| oid_or_cloid(m, f.and_then(|x| x.get("oid")))) }
        _ => None,
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (t0, t1, out) = (a[1].clone(), a[2].clone(), a[3].clone());
    let sep = a.iter().position(|x| x == "--").expect("--");
    let sfiles = &a[4..sep]; let rfiles = &a[sep + 1..];
    let in_win = |t: &str| t.len() >= 19 && &t[..19] >= t0.as_str() && &t[..19] < t1.as_str();
    let mut users: HashMap<String, u32> = HashMap::new(); let mut names: Vec<String> = vec![];
    let mut m = Maps { by_oid: HashMap::new(), by_cloid: HashMap::new() };
    let mut buf = String::new();
    // statuses: also 60 s before the window, so cancels of orders placed just before it resolve
    let pre = { let ms = parse_time_ms(&format!("{t0}.000")) - 60_000; ms };
    for f in sfiles {
        let mut rd = BufReader::with_capacity(1 << 24, std::fs::File::open(f).unwrap());
        loop {
            buf.clear();
            if rd.read_line(&mut buf).unwrap() == 0 { break; }
            let head = &buf[..buf.len().min(120)];
            let Some(i) = head.find("\"block_time\":\"") else { continue };
            let bt = &head[i + 14..(i + 14 + 19).min(head.len())];
            if bt.len() < 19 || bt >= t1.as_str() { if bt >= t1.as_str() { break } else { continue } }
            if parse_time_ms(&format!("{bt}.000")) < pre { continue; }
            let l: SLine = match serde_json::from_str(buf.trim_end()) { Ok(l) => l, Err(_) => continue };
            let _ = l.block_time;
            for e in l.events {
                let n = names.len() as u32;
                let u = *users.entry(e.user.to_string()).or_insert_with(|| { names.push(e.user.to_string()); n });
                m.by_oid.insert(e.order.oid, u);
                if let Some(c) = cl(e.order.cloid.map(|s| Value::String(s.to_string())).as_ref()) { m.by_cloid.insert(c, u); }
            }
        }
        eprintln!("statuses {f}: users {} oids {} cloids {}", names.len(), m.by_oid.len(), m.by_cloid.len());
    }
    let mut kinds: HashMap<String, u16> = HashMap::new(); let mut knames: Vec<String> = vec![];
    let mut tx: HashMap<i64, u64> = HashMap::new();
    // samples: (user or u32::MAX, kind, sec, lat)
    let mut samples: Vec<(u32, u16, i64, i16)> = Vec::new();
    for f in rfiles {
        let mut rd = BufReader::with_capacity(1 << 24, std::fs::File::open(f).unwrap());
        loop {
            buf.clear();
            if rd.read_line(&mut buf).unwrap() == 0 { break; }
            let head = &buf[..buf.len().min(80)];
            let Some(i) = head.find("\"time\":\"") else { continue };
            let bt = &head[i + 8..(i + 8 + 19).min(head.len())];
            if !in_win(bt) { if bt >= t1.as_str() { break } else { continue } }
            let l: Line = match serde_json::from_str(buf.trim_end()) { Ok(l) => l, Err(_) => continue };
            let bms = parse_time_ms(l.abci_block.time); let sec = bms.div_euclid(1000);
            for (_, b) in l.abci_block.signed_action_bundles {
                for sa in b.signed_actions {
                    *tx.entry(sec).or_default() += 1;
                    let h: Head = match serde_json::from_str(sa.action.get()) { Ok(h) => h, Err(_) => continue };
                    let k = kind(&h);
                    if !(k.starts_with("cancel") || k.starts_with("order_Alo") || k.starts_with("order_Ioc") || k.contains("odify")) { continue; }
                    let lat = bms - sa.nonce as i64;
                    if !(-50..=5000).contains(&lat) { continue; }
                    let n = knames.len() as u16;
                    let ki = *kinds.entry(k.clone()).or_insert_with(|| { knames.push(k); n });
                    let u = resolve(&h, &m).unwrap_or(u32::MAX);
                    samples.push((u, ki, sec, lat as i16));
                }
            }
        }
        eprintln!("replica {f}: samples {}", samples.len());
    }
    let band = |s: i64| { let v = *tx.get(&s).unwrap_or(&0); if v < 20000 { "<20k" } else if v < 30000 { "20-30k" } else if v < 40000 { "30-40k" } else { "40k+" } };
    let mut agg: HashMap<(u32, u16, &str), Vec<i16>> = HashMap::new();
    let mut cover: HashMap<(u16, &str), (u64, u64)> = HashMap::new();
    for (u, k, s, lat) in samples {
        let b = band(s);
        let c = cover.entry((k, b)).or_default(); c.0 += 1;
        if u != u32::MAX { c.1 += 1; agg.entry((u, k, b)).or_default().push(lat); }
    }
    let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{out}.csv")).unwrap());
    writeln!(f, "user,kind,load_band,n,p25_ms,p50_ms,p75_ms").unwrap();
    for ((u, k, b), mut v) in agg {
        if v.len() < 5 { continue; }
        v.sort_unstable();
        let q = |p: f64| v[((v.len() - 1) as f64 * p).round() as usize];
        writeln!(f, "{},{},{},{},{},{},{}", names[u as usize], knames[k as usize], b, v.len(), q(0.25), q(0.5), q(0.75)).unwrap();
    }
    let mut f = std::io::BufWriter::new(std::fs::File::create(format!("{out}.cover.csv")).unwrap());
    writeln!(f, "kind,load_band,total,resolved").unwrap();
    for ((k, b), (t, r)) in cover { writeln!(f, "{},{},{},{}", knames[k as usize], b, t, r).unwrap(); }
    eprintln!("done");
}
