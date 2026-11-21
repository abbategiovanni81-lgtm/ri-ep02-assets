"""Backtest every strategy on real data, after costs, and print an honest report.

    python run_backtests.py            # uses cached data if < 12h old
    python run_backtests.py --refresh  # re-download

For each strategy it prints: full-period stats, first-half vs second-half
stats (a strategy that only worked in one half is probably luck or overfit),
and full-period stats at double the assumed costs.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

import config
from bot import backtest as bt
from bot import strategies as st
from bot.data import get_prices_gbp


def costs(cols, mult=1.0):
    return {c: config.cost_for(c) * mult for c in cols}


def build(refresh: bool):
    etf = get_prices_gbp(list(config.ETF_UNIVERSE), refresh)
    cry = get_prices_gbp(list(config.CRYPTO_UNIVERSE), refresh)
    rev = get_prices_gbp([config.REVERSION_ASSET], refresh)

    # Signals are computed on the full history; the test period starts once at
    # least 5 of the 8 ETFs have a year of prices, so every strategy and
    # benchmark is measured over the same dates.
    have5 = etf.notna().sum(axis=1) >= 5
    start = etf.index[have5.values.argmax() + 252]

    def cut(w):
        return w.loc[w.index >= start]

    etf_bt = cut(etf)
    tests = []  # (name, prices, weights)

    # Benchmarks
    tests.append(("BENCH world equity ETF (IWDA) buy & hold", etf_bt,
                  cut(st.buy_and_hold(etf, {"IWDA.L": 1.0}))))
    eq_w = {c: 1 / etf.shape[1] for c in etf.columns}
    tests.append(("BENCH equal-weight 8 ETFs (rebalancing cost not modelled)", etf_bt,
                  cut(st.buy_and_hold(etf, eq_w))))

    # 1. Multi-asset trend following
    for lb in (126, 252):
        tests.append((f"Trend following ETFs, {lb}d lookback, 10% vol target", etf_bt,
                      cut(st.trend_following(etf, lookback_days=lb))))
    # 2. Dual momentum rotation
    for lb in (126, 252):
        tests.append((f"Dual momentum ETFs, top 2, {lb}d lookback", etf_bt,
                      cut(st.dual_momentum(etf, lookback_days=lb, top_n=2))))

    # 3. Crypto trend (spot only, long or cash)
    cry = cry.dropna(how="all")
    tests.append(("BENCH BTC buy & hold", cry, st.buy_and_hold(cry, {"BTC-GBP": 1.0})))
    for ma in (50, 100, 200):
        tests.append((f"Crypto MA trend BTC+ETH, {ma}d MA", cry, st.ma_trend(cry, ma)))

    # 4. Short-term mean reversion on the S&P 500 ETF
    rev = rev.dropna()
    tests.append(("BENCH S&P 500 ETF (CSPX) buy & hold", rev,
                  st.buy_and_hold(rev, {config.REVERSION_ASSET: 1.0})))
    for e in (5, 10):
        tests.append((f"Mean reversion CSPX, RSI2<{e}, exit >5d MA", rev,
                      st.short_term_reversion(rev, config.REVERSION_ASSET, entry_rsi=e)))
    return tests


def fmt(s: dict) -> str:
    if not s:
        return "n/a"
    t = s.get("turnover_per_year", float("nan"))
    return (f"{s['start']}..{s['end']} CAGR {s['CAGR']:+6.1%}  vol {s['vol']:5.1%}  "
            f"Sharpe {s['sharpe']:5.2f}  maxDD {s['max_dd']:6.1%}  "
            f"worst yr {s['worst_year']:+6.1%}  turnover/yr {t:5.1f}x")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--csv", default="backtest_results.csv")
    a = ap.parse_args(argv)

    rows = []
    for name, px, w in build(a.refresh):
        r1 = bt.run(name, px, w, costs(px.columns))
        r2 = bt.run(name, px, w, costs(px.columns, 2.0))
        s1, s2 = r1.stats(), r2.stats()
        h1, h2 = bt.split_halves(r1)
        print(f"\n{name}")
        print(f"  full        : {fmt(s1)}")
        print(f"  1st half    : {fmt(h1)}")
        print(f"  2nd half    : {fmt(h2)}")
        print(f"  2x costs    : {fmt(s2)}")
        print(f"  £{config.STARTING_CAPITAL_GBP:,.0f} -> £{config.STARTING_CAPITAL_GBP * r1.equity.iloc[-1]:,.0f}")
        rows.append({"strategy": name, **{f"full_{k}": v for k, v in s1.items()},
                     **{f"h1_{k}": v for k, v in h1.items()},
                     **{f"h2_{k}": v for k, v in h2.items()},
                     **{f"x2cost_{k}": v for k, v in s2.items()}})
    pd.DataFrame(rows).to_csv(a.csv, index=False)
    print(f"\nSaved {a.csv}")


if __name__ == "__main__":
    sys.exit(main())
