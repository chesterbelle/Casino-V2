#!/usr/bin/env python3
"""
Simple log + demo JSON parser to extract order events, WS confirmations and fallback counts.
Heuristic-based: scans `logs/` for `main_*.log` files and `logs/demo_*.json` files.
Outputs a short summary with counts and latency stats.
"""
import json
import logging
import re
import statistics
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOGS_DIR = Path("logs")
TIME_FMT = "%Y-%m-%d %H:%M:%S,%f"

order_create_keywords = [
    r"create[_\s]?order",
    r"order created",
    r"order placement",
    r"order placed",
    r"new order",
    r"send order",
    r"creating order",
]
ws_confirm_keywords = [
    r"watch_orders",
    r"watch_my_trades",
    r"avgPrice",
    r"filled",
    r"fill",
    r"update order",
    r"order update",
]
fallback_keywords = [r"fetch_order", r"fetch order", r"fetchOrder", r"fallback to rest"]

# regexes to extract timestamps at line start
ts_regex = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
# order id patterns
order_id_patterns = [
    re.compile(r'"orderId"\s*[:=]\s*"?(?P<id>\w+)"?'),
    re.compile(r'"id"\s*[:=]\s*"?(?P<id>\w+)"?'),
    re.compile(r"orderId=?(?P<id>\w+)"),
    re.compile(r'clientOrderId"\s*:\s*"(?P<id>[^"]+)"'),
]


def extract_ts(line):
    m = ts_regex.search(line)
    if m:
        s = m.group("ts")
        try:
            return datetime.strptime(s, TIME_FMT)
        except Exception:
            return None
    return None


def find_order_id(text):
    for p in order_id_patterns:
        m = p.search(text)
        if m:
            return m.group("id")
    return None


def scan_log_file(p: Path):
    events = []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            ts = extract_ts(line)
            low = line.lower()
            kind = None
            if any(re.search(k, low) for k in order_create_keywords):
                kind = "create"
            elif any(re.search(k, low) for k in ws_confirm_keywords):
                kind = "ws_confirm"
            elif any(re.search(k, low) for k in fallback_keywords):
                kind = "rest_fallback"
            if kind:
                oid = find_order_id(line)
                events.append(
                    {
                        "file": str(p.name),
                        "line_no": i + 1,
                        "ts": ts,
                        "kind": kind,
                        "text": line.strip(),
                        "order_id": oid,
                    }
                )
    return events


def scan_demo_json(p: Path):
    data = {}
    try:
        with p.open("r", encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return data
    # heuristics: look for keys
    keys_of_interest = ["total_trades", "orders", "executions", "summary"]
    for k in keys_of_interest:
        if k in j:
            data[k] = j[k]
    # also try to find any 'orders' like structures
    if "orders" in j and isinstance(j["orders"], list):
        data["orders_count"] = len(j["orders"])
    return data


def main():
    logs = sorted(LOGS_DIR.glob("main_*.log"))
    demo_jsons = sorted(LOGS_DIR.glob("demo_*.json"))

    if not logs and not demo_jsons:
        logger.info("No main_*.log or demo_*.json files found in logs/.")
        return

    logger.info(f"Found {len(logs)} main_*.log, {len(demo_jsons)} demo_*.json")

    all_events = []
    for p in logs:
        ev = scan_log_file(p)
        if ev:
            all_events.extend(ev)
    # sort events by timestamp when present
    all_events_sorted = sorted(all_events, key=lambda e: e["ts"] or datetime.min)

    # build mapping by order_id
    by_id = {}
    create_events = []
    ws_events = []
    fallback_events = []
    for e in all_events_sorted:
        if e["kind"] == "create":
            create_events.append(e)
        elif e["kind"] == "ws_confirm":
            ws_events.append(e)
        elif e["kind"] == "rest_fallback":
            fallback_events.append(e)
        oid = e.get("order_id")
        if oid:
            by_id.setdefault(oid, []).append(e)

    # Attempt to link creates -> ws confirmation by order_id
    matched_latencies = []
    matched_count = 0
    ws_confirm_count = 0
    for oid, evs in by_id.items():
        creates = [x for x in evs if x["kind"] == "create" and x["ts"]]
        ws = [x for x in evs if x["kind"] == "ws_confirm" and x["ts"]]
        rest = [x for x in evs if x["kind"] == "rest_fallback" and x["ts"]]
        if creates and ws:
            # pair closest create -> earliest ws after create
            for c in creates:
                # find first ws ts >= c.ts
                ws_after = [w for w in ws if w["ts"] and c["ts"] and w["ts"] >= c["ts"]]
                if ws_after:
                    delta_ms = (ws_after[0]["ts"] - c["ts"]).total_seconds() * 1000.0
                    matched_latencies.append(delta_ms)
                    matched_count += 1
                    ws_confirm_count += 1
        elif creates and rest:
            # fallback case
            for c in creates:
                rest_after = [r for r in rest if r["ts"] and c["ts"] and r["ts"] >= c["ts"]]
                if rest_after:
                    delta_ms = (rest_after[0]["ts"] - c["ts"]).total_seconds() * 1000.0
                    matched_latencies.append(delta_ms)

    # Heuristic linking for events without order_id: sequential matching
    # take create_events without id and try to match next ws event after it
    creates_noid = [c for c in create_events if not c.get("order_id") and c["ts"]]
    ws_noid = [w for w in ws_events if not w.get("order_id") and w["ts"]]
    for c in creates_noid:
        ws_after = [w for w in ws_noid if w["ts"] >= c["ts"]]
        if ws_after:
            delta_ms = (ws_after[0]["ts"] - c["ts"]).total_seconds() * 1000.0
            matched_latencies.append(delta_ms)
            matched_count += 1
            ws_confirm_count += 1

    # Summary
    total_creates = len(create_events)
    total_ws = len(ws_events)
    total_fallback = len(fallback_events)

    logger.info("\nSummary Report")
    logger.info("--------------")
    logger.info(f"Total create-like events found: {total_creates}")
    logger.info(f"Total ws-confirm-like events found: {total_ws}")
    logger.info(f"Total REST fallback-like events found: {total_fallback}")
    logger.info(f"Linked confirmations (heuristic): {matched_count}")
    if matched_latencies:
        logger.info(
            f"Latency (ms) - mean: {statistics.mean(matched_latencies):.1f}, median: {statistics.median(matched_latencies):.1f}, min: {min(matched_latencies):.1f}, max: {max(matched_latencies):.1f}"
        )
    else:
        logger.info("No latency samples found.")

    # show samples
    logger.info("\nSample events (up to 10)")
    for e in all_events_sorted[:10]:
        ts = e["ts"].isoformat(sep=" ") if e["ts"] else "NO_TS"
        oid = e.get("order_id") or "-"
        logger.info(f"{ts} | {e['kind']} | order_id={oid} | {e['text']}")

    # Demo JSONs quick scan
    if demo_jsons:
        logger.info("\nDemo JSON scan:")
        for p in demo_jsons[-5:]:
            d = scan_demo_json(p)
            logger.info(f"{p.name}: keys_found={list(d.keys())}")


if __name__ == "__main__":
    main()
