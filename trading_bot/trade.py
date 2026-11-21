"""Run one strategy for today: work out target holdings and rebalance.

Modes
  --paper (default)  simulated account stored in state/<strategy>.json; fills at
                     the latest close plus the cost assumption from config.py
  --kraken           crypto strategies only: reads your real Kraken balances and
                     sends orders with validate=true (Kraken checks, nothing is
                     placed). Add --live to actually place them.

Run it once a day (crypto) or once a month after the last trading day (ETFs),
for example from cron. ETF strategies print the orders to place by hand in your
broker, since UK retail ETF brokers rarely offer a simple order API.

Safety rails
  * Trades smaller than --min-trade (GBP) or within --band of target are skipped.
  * Kill switch: if account value falls --max-dd below its peak, everything is
    sold to cash and the strategy stops until you delete the "halted" flag.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import config
from bot import strategies as st
from bot.data import get_prices_gbp

STATE_DIR = Path(__file__).resolve().parent / "state"

STRATEGIES = {
    # name: (universe, function returning weights from prices)
    "crypto_ma200": (list(config.CRYPTO_UNIVERSE), lambda p: st.ma_trend(p, 200)),
    "crypto_ma50": (list(config.CRYPTO_UNIVERSE), lambda p: st.ma_trend(p, 50)),
    "etf_trend": (list(config.ETF_UNIVERSE), lambda p: st.trend_following(p, 252)),
    "etf_dual_momentum": (list(config.ETF_UNIVERSE), lambda p: st.dual_momentum(p, 252, 2)),
}


def load_state(name: str) -> dict:
    path = STATE_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"cash": config.STARTING_CAPITAL_GBP, "units": {}, "peak": config.STARTING_CAPITAL_GBP,
            "halted": False, "created": dt.date.today().isoformat()}


def save_state(name: str, s: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / f"{name}.json").write_text(json.dumps(s, indent=2))


def log_trades(name: str, rows: list[dict]) -> None:
    if not rows:
        return
    STATE_DIR.mkdir(exist_ok=True)
    path = STATE_DIR / f"{name}_trades.csv"
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        if new:
            w.writeheader()
        w.writerows(rows)


def plan_orders(value: float, holdings_gbp: dict, target_w: dict, min_trade: float, band: float):
    """Orders (ticker, GBP amount; + buy / - sell) to move holdings to target."""
    orders = []
    for t in sorted(set(holdings_gbp) | set(target_w)):
        want = value * target_w.get(t, 0.0)
        have = holdings_gbp.get(t, 0.0)
        diff = want - have
        if abs(diff) < min_trade:
            continue
        if want > 0 and have > 0 and abs(diff) / value < band:
            continue
        orders.append((t, diff))
    orders.sort(key=lambda o: o[1])  # sells first, to free cash
    return orders


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", choices=sorted(STRATEGIES))
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--paper", action="store_true", default=True)
    mode.add_argument("--kraken", action="store_true")
    ap.add_argument("--live", action="store_true", help="with --kraken: place real orders")
    ap.add_argument("--min-trade", type=float, default=10.0)
    ap.add_argument("--band", type=float, default=0.05, help="skip if within this fraction of target")
    ap.add_argument("--max-dd", type=float, default=0.35, help="kill-switch drawdown from peak")
    a = ap.parse_args(argv)

    universe, fn = STRATEGIES[a.strategy]
    prices = get_prices_gbp(universe, refresh=True)
    w = fn(prices)
    last = prices.index[-1]
    target = {t: float(x) for t, x in w.loc[last].items() if x > 1e-6}
    px = prices.loc[last].to_dict()
    print(f"{a.strategy}: data to {last.date()}  target weights: "
          + (", ".join(f"{t} {x:.0%}" for t, x in target.items()) or "100% cash"))

    if a.kraken:
        return run_kraken(a, universe, target)

    s = load_state(a.strategy)
    holdings = {t: u * px[t] for t, u in s["units"].items()}
    value = s["cash"] + sum(holdings.values())
    s["peak"] = max(s["peak"], value)
    dd = value / s["peak"] - 1
    print(f"paper account: £{value:,.2f}  (cash £{s['cash']:,.2f}, peak £{s['peak']:,.2f}, drawdown {dd:.1%})")

    if s["halted"]:
        print("HALTED by kill switch. Delete 'halted' in the state file to resume.")
        return 0
    if dd <= -a.max_dd:
        print(f"KILL SWITCH: drawdown {dd:.1%} beyond {a.max_dd:.0%}. Selling everything.")
        target = {}
        s["halted"] = True

    rows = []
    for t, amt in plan_orders(value, holdings, target, a.min_trade, a.band):
        c = config.cost_for(t)
        if amt > 0:  # never spend more cash than is there
            amt = min(amt, s["cash"] / (1 + c))
            if amt < a.min_trade:
                continue
        cost = abs(amt) * c
        units = amt / px[t]
        s["units"][t] = s["units"].get(t, 0.0) + units
        if abs(s["units"][t] * px[t]) < 0.01:
            s["units"].pop(t)
        s["cash"] -= amt + cost
        side = "BUY" if amt > 0 else "SELL"
        print(f"  {side:4} {t:8} £{abs(amt):9,.2f} @ £{px[t]:,.4f} (GBP-equivalent)  cost £{cost:.2f}")
        rows.append({"date": last.date().isoformat(), "ticker": t, "side": side,
                     "gbp": round(abs(amt), 2), "price": px[t], "cost": round(cost, 2)})
    if not rows:
        print("  no trades needed")
    log_trades(a.strategy, rows)
    save_state(a.strategy, s)
    return 0


def run_kraken(a, universe, target):
    from bot.kraken import CASH_ASSET, PAIRS, KrakenClient, ticker_prices

    if any(t not in PAIRS for t in universe):
        print("--kraken only supports the crypto strategies")
        return 2
    client = KrakenClient()
    bal = client.balances()
    live_px = ticker_prices([PAIRS[t][0] for t in universe])
    holdings = {t: bal.get(PAIRS[t][1], 0.0) * live_px[PAIRS[t][0]] for t in universe}
    cash = bal.get(CASH_ASSET, 0.0)
    value = cash + sum(holdings.values())
    print(f"Kraken account: £{value:,.2f} (cash £{cash:,.2f})")
    orders = plan_orders(value, holdings, target, a.min_trade, a.band)
    if not orders:
        print("  no trades needed")
    for t, amt in orders:
        pair = PAIRS[t][0]
        vol = abs(amt) / live_px[pair]
        side = "buy" if amt > 0 else "sell"
        res = client.market_order(pair, side, vol, live=a.live)
        tag = "PLACED" if a.live else "validated only (add --live to place)"
        print(f"  {side} {vol:.8f} {pair} (~£{abs(amt):,.2f}): {tag} -> {res.get('descr')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
