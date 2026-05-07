#!/usr/bin/env python3
"""
🦞 小龙虾 — EVE 欧服矿物价格采集器 v5
- Janice: 收购/出售/均价
- ESI 订单簿: 真实收购/出售需求
- 日内 → intraday.json / 日级 → prices.json
用法: python3 scraper.py
"""

from __future__ import annotations
import json, os, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

REGION_ID, DATASOURCE = 10000002, "tranquility"
JANICE_RPC = "https://janice.e-351.com/api/rpc/v1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DAILY_FILE = os.path.join(DATA_DIR, "prices.json")
INTRADAY_FILE = os.path.join(DATA_DIR, "intraday.json")
RETAIN_DAYS = 8


MINERALS = {
    "Tritanium": 34, "Pyerite": 35, "Mexallon": 36, "Isogen": 37,
    "Nocxium": 38, "Zydrine": 39, "Megacyte": 40, "Morphite": 11399,
    "PLEX": 44992,
    "Skill Extractor": 40520,
    "Large Skill Injector": 45635,
}

QUERY_BATCHES = [
    ["Tritanium","Pyerite","Mexallon","Isogen","Nocxium","Zydrine","Megacyte","Morphite","PLEX"],
    ["Skill Extractor"],
    ["Large Skill Injector"],
]

UA = "EveMineralTracker/5.0"


# ========== Janice ==========

def fetch_janice_all() -> dict:
    id2name = {v: k for k, v in MINERALS.items()}
    out = {}
    for batch in QUERY_BATCHES:
        text = "\n".join(batch)
        items = _janice_query(text)
        if items:
            if len(batch) == 1:
                out[batch[0]] = {"buy": items[0]["buy"], "sell": items[0]["sell"], "avg": items[0]["avg"]}
            else:
                for it in items:
                    name = id2name.get(it["tid"])
                    if name:
                        out[name] = {"buy": it["buy"], "sell": it["sell"], "avg": it["avg"]}
        if batch != QUERY_BATCHES[-1]:
            time.sleep(0.5)
    return out


def _janice_query(text: str) -> list | None:
    payload = json.dumps({
        "method": "Appraisal.create",
        "params": {"marketId":2,"designation":"appraisal","pricing":"split",
                   "pricePercentage":100,"input":text,"comment":"","compactize":False},
        "id": 1,
    }).encode()
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(JANICE_RPC, data=payload, headers={
                "Content-Type":"application/json","Accept":"application/json","User-Agent":UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read()).get("result", {})
                items = []
                for it in result.get("items", []):
                    ip = it.get("immediatePrices", {})
                    try:
                        items.append({
                            "tid": it["itemType_eid"],
                            "buy": round(ip["buyPrice"], 2),
                            "sell": round(ip["sellPrice"], 2),
                            "avg": round(ip["splitPrice"], 2),
                        })
                    except (KeyError, TypeError): pass
                return items
        except Exception as e:
            if attempt < 3: time.sleep(2)
            else: print(f"  ⚠ Janice 失败: {e}", file=sys.stderr)
    return None


# ========== ESI 订单簿 → 真实需求 ==========

def fetch_esi_orders(type_id: int, order_type: str) -> list:
    """
    获取指定类型的所有相关订单 (买或卖)
    buy: 价格从高到低 → 读到低于 90%最高价 停止
    sell: 价格从低到高 → 读到高于 120%最低价 停止
    """
    all_orders = []
    page = 1
    while page <= 20:  # 安全上限
        url = (f"https://esi.evetech.net/latest/markets/{REGION_ID}/orders/"
               f"?datasource={DATASOURCE}&order_type={order_type}&type_id={type_id}&page={page}")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                batch = json.loads(resp.read())
        except Exception:
            break
        if not batch:
            break
        all_orders.extend(batch)

        if len(batch) < 1000:
            break  # 最后一页

        # 预先截止判定
        if all_orders:
            if order_type == "buy":
                max_price = all_orders[0]["price"]
                if batch[-1]["price"] < max_price * 0.85:
                    break
            else:
                min_price = all_orders[0]["price"]
                if batch[-1]["price"] > min_price * 1.25:
                    break

        page += 1
        time.sleep(0.15)

    if order_type == "buy":
        if not all_orders: return []
        max_p = all_orders[0]["price"]
        return [o for o in all_orders if o["price"] >= max_p * 0.9]
    else:
        if not all_orders: return []
        min_p = all_orders[0]["price"]
        return [o for o in all_orders if o["price"] <= min_p * 1.2]


def calc_demand(orders: list) -> dict:
    """从订单列表计算需求统计"""
    if not orders:
        return {"value": 0, "orders": 0, "volume": 0}
    return {
        "value":  sum(o["price"] * o["volume_remain"] for o in orders),
        "orders": len(orders),
        "volume": sum(o["volume_remain"] for o in orders),
    }


def fetch_esi_history_volume(type_id: int) -> int:
    """获取最近24小时成交量"""
    url = (f"https://esi.evetech.net/latest/markets/{REGION_ID}/history/"
           f"?datasource={DATASOURCE}&type_id={type_id}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data:
            return data[-1].get("volume", 0)
    except Exception:
        pass
    return 0


# ========== 数据持久化 ==========

def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for k in data:
        data[k].sort(key=lambda d: d.get("date") or d.get("dt") or "")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def upsert_daily(daily, janice, demands, today):
    n = 0
    for name in MINERALS:
        if name not in janice: continue
        j = janice[name]
        d = demands.get(name, {})
        entry = {
            "date": today,
            "buy": j["buy"], "sell": j["sell"], "avg": j["avg"],
            "buy_demand": d.get("buy_demand", {"value":0,"orders":0,"volume":0,"volume_24h":0}),
            "sell_demand": d.get("sell_demand", {"value":0,"orders":0,"volume":0,"volume_24h":0}),
        }
        if name not in daily: daily[name] = []
        match = [x for x in daily[name] if x["date"] == today]
        if match:
            match[0].update(entry)
        else:
            daily[name].append(entry)
            n += 1
    return n


def append_intraday(intra, janice, demands, now):
    n = 0
    for name in MINERALS:
        if name not in janice: continue
        j = janice[name]
        d = demands.get(name, {})
        if name not in intra: intra[name] = []
        intra[name].append({
            "dt": now,
            "buy": j["buy"], "sell": j["sell"], "avg": j["avg"],
            "buy_demand": d.get("buy_demand", {}),
            "sell_demand": d.get("sell_demand", {}),
        })
        n += 1
    return n


def prune_intraday(intra):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETAIN_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = 0
    for name in intra:
        before = len(intra[name])
        intra[name] = [d for d in intra[name] if d["dt"] >= cutoff]
        r += before - len(intra[name])
    return r


# ========== 主流程 ==========

def main():
    now = datetime.now(timezone.utc)
    now_s, today = now.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%d")
    print(f"🦞 小龙虾 v5 — {datetime.now().strftime('%Y-%m-%d %H:%M')} CST")
    print(f"📍 Jita 4-4 | {len(MINERALS)} 种商品\n")

    # 1. Janice 价格
    print("📡 [1/3] Janice 价格...")
    janice = fetch_janice_all()
    if not janice:
        print("   ⚠ 失败\n"); return

    # 2. 订单簿 → 真实需求
    print("\n📡 [2/3] ESI 订单簿 → 真实需求...")
    demands = {}
    for name, tid in MINERALS.items():
        if name not in janice:
            continue
        print(f"     {name:22s} ...", end=" ", flush=True)
        try:
            buy_orders = fetch_esi_orders(tid, "buy")
            sell_orders = fetch_esi_orders(tid, "sell")
            vol_24h = fetch_esi_history_volume(tid)
            bd = calc_demand(buy_orders)
            sd = calc_demand(sell_orders)
            bd["volume_24h"] = vol_24h
            sd["volume_24h"] = vol_24h
            demands[name] = {"buy_demand": bd, "sell_demand": sd}
            j = janice[name]
            print(f"✓ 收购:{bd['orders']}单/{format_isk(bd['value'])}ISK | 出售:{sd['orders']}单/{format_isk(sd['value'])}ISK")
        except Exception as e:
            print(f"✗ {e}")
        time.sleep(0.3)

    # 3. 保存
    print("\n📡 [3/3] 保存数据...")
    daily = load(DAILY_FILE)
    n_day = upsert_daily(daily, janice, demands, today)
    save(DAILY_FILE, daily)

    intra = load(INTRADAY_FILE)
    n_intra = append_intraday(intra, janice, demands, now_s)
    n_prune = prune_intraday(intra)
    save(INTRADAY_FILE, intra)
    print(f"   ✓ 日级 +{n_day} | 日内 +{n_intra} | 清理 {n_prune}")

    print(f"\n✅ 完成!")
    for n in MINERALS:
        d = daily.get(n, [])
        i = intra.get(n, [])
        print(f"   {n:22s}  日级:{len(d)}条  日内:{len(i)}条")


def format_isk(v):
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v/1_000:.2f}K"
    return f"{v:.2f}"


if __name__ == "__main__":
    main()
