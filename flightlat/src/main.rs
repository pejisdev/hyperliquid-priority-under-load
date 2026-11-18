// flightlat: for every order (order, modify, batchModify) in a replica_cmds stream whose client order id (cloid) is in CLOIDS,
// the signing time (nonce) and the block it landed in. Also the chain load per second. Used to join fills, by cloid, to the
// signed order behind each side: the maker's quote and the taker's order.
// usage: lz4 -dc FILES | flightlat CLOIDS OUT      CLOIDS = one 0x-hex cloid per line
// writes OUT.place.tsv: cloid_hex  block_ms  sign_ms  kind  asset  is_buy  px     and OUT.load.tsv: unix_second  actions
use serde::Deserialize;
use serde_json::value::RawValue;
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::io::{BufRead, BufReader, Write};

#[derive(Deserialize)]
struct Line<'a> { #[serde(borrow)] abci_block: Block<'a> }
#[derive(Deserialize)]
struct Block<'a> { time: &'a str, #[serde(borrow)] signed_action_bundles: Vec<(serde::de::IgnoredAny, Bundle<'a>)> }
#[derive(Deserialize)]
struct Bundle<'a> { #[serde(borrow)] signed_actions: Vec<SA<'a>> }
#[derive(Deserialize)]
struct SA<'a> { #[serde(borrow)] action: &'a RawValue, nonce: u64 }
#[derive(Deserialize)]
struct Head { #[serde(rename = "type")] t: String, orders: Option<Vec<Value>>, grouping: Option<Value>,
    order: Option<Value>, modifies: Option<Vec<Value>> }

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
fn cl(v: Option<&Value>) -> Option<u128> { u128::from_str_radix(v?.as_str()?.strip_prefix("0x")?, 16).ok() }
fn tif(o: &Value) -> &str { let t = o.get("t"); if let Some(x) = t.and_then(|t| t.get("limit")).and_then(|l| l.get("tif")).and_then(|x| x.as_str()) { x } else if t.and_then(|t| t.get("trigger")).is_some() { "trigger" } else { "?" } }

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let (cf, out) = (&a[1], &a[2]);
    let want: HashSet<u128> = BufReader::new(std::fs::File::open(cf).unwrap()).lines()
        .filter_map(|l| cl(Some(&Value::String(l.unwrap().trim().to_string())))).collect();
    eprintln!("cloids wanted: {}", want.len());
    let mut fo = std::io::BufWriter::new(std::fs::File::create(format!("{out}.place.tsv")).unwrap());
    let mut tx: HashMap<i64, u64> = HashMap::new();
    let (mut nblk, mut nplace, mut nalo) = (0u64, 0u64, 0u64);
    let stdin = std::io::stdin();
    let mut rd = BufReader::with_capacity(1 << 24, stdin.lock());
    let mut buf = String::new();
    loop {
        buf.clear();
        if rd.read_line(&mut buf).unwrap() == 0 { break; }
        let l: Line = match serde_json::from_str(buf.trim_end()) { Ok(l) => l, Err(_) => continue };
        let bms = parse_time_ms(l.abci_block.time); let sec = bms.div_euclid(1000); nblk += 1;
        for (_, b) in l.abci_block.signed_action_bundles {
            for sa in b.signed_actions {
                *tx.entry(sec).or_default() += 1;
                let raw = sa.action.get();
                if !(raw.contains("\"c\":\"0x")) { continue; }
                let h: Head = match serde_json::from_str(raw) { Ok(h) => h, Err(_) => continue };
                let mut emit = |o: &Value, kind: &str| {
                    let tf = tif(o); if tf == "Alo" { nalo += 1; }
                    let Some(c) = cl(o.get("c")) else { return };
                    if !want.contains(&c) { return; }
                    nplace += 1;
                    let px = o.get("p").and_then(|x| x.as_str()).unwrap_or("");
                    let buy = o.get("b").and_then(|x| x.as_bool()).unwrap_or(false) as u8;
                    let asset = o.get("a").and_then(|x| x.as_u64()).unwrap_or(u64::MAX);
                    writeln!(fo, "0x{:032x}\t{}\t{}\t{}_{}\t{}\t{}\t{}", c, bms, sa.nonce, kind, tf, asset, buy, px).unwrap();
                };
                match h.t.as_str() {
                    "order" => {
                        let p = h.grouping.as_ref().and_then(|g| g.get("p")).and_then(|p| p.as_u64()).unwrap_or(0);
                        let k = if p > 0 { "order_fee" } else { "order" };
                        for o in h.orders.as_deref().unwrap_or(&[]) { emit(o, k); }
                    }
                    "modify" => { if let Some(o) = h.order.as_ref() { emit(o, "modify"); } }
                    "batchModify" => { for m in h.modifies.as_deref().unwrap_or(&[]) { if let Some(o) = m.get("order") { emit(o, "batchModify"); } } }
                    _ => {}
                }
            }
        }
        if nblk % 20000 == 0 { eprintln!("blocks {nblk} alo {nalo} placed {nplace}"); }
    }
    fo.flush().unwrap();
    let mut fl = std::io::BufWriter::new(std::fs::File::create(format!("{out}.load.tsv")).unwrap());
    let mut v: Vec<_> = tx.into_iter().collect(); v.sort();
    for (s, n) in v { writeln!(fl, "{s}\t{n}").unwrap(); }
    eprintln!("done blocks {nblk} alo {nalo} placed {nplace}");
}
