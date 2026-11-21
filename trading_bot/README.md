# Trading bot (UK, small account)

A backtester, paper trader and Kraken spot connector for a UK account starting at £1,000.
It holds positions or cash: no leverage, no shorting, no derivatives.

**Not financial advice.** Past backtest results do not predict future returns. Run it on
paper before risking money.

## Setup

```bash
cd trading_bot
pip install -r requirements.txt
python -m unittest discover -s tests   # 6 tests: no look-ahead, costs, order planning
python run_backtests.py                # downloads data, prints the report below
```

## Results (data to 19–21 Nov 2026, in GBP, after assumed costs)

Each strategy is tested at several standard settings, and every setting is shown so
the best one is not cherry-picked. "Sharpe 1st / 2nd half" splits the period in two:
a strategy that only worked in one half is less trustworthy.

| Strategy | Period | CAGR | Sharpe | Max drawdown | Sharpe 1st / 2nd half | CAGR at 2× costs |
|---|---|---|---|---|---|---|
| BENCH world equity ETF (IWDA) buy & hold | 2013–2026 | +11.9% | 0.76 | -26% | 0.85 / 0.70 | +11.9% |
| BENCH equal-weight 8 ETFs | 2013–2026 | +5.6% | 0.65 | -18% | 0.80 / 0.56 | +5.5% |
| Trend following ETFs, 126d | 2013–2026 | +4.5% | 0.55 | -18% | 0.64 / 0.46 | +3.6% |
| Trend following ETFs, 252d | 2013–2026 | +5.5% | 0.66 | -15% | 0.51 / 0.80 | +4.9% |
| Dual momentum ETFs, top 2, 126d | 2013–2026 | +4.0% | 0.35 | -31% | 0.40 / 0.31 | +2.5% |
| Dual momentum ETFs, top 2, 252d | 2013–2026 | +7.9% | 0.64 | -17% | 0.43 / 0.85 | +7.2% |
| BENCH BTC buy & hold | 2014–2026 | +51.4% | 0.96 | -82% | 1.14 / 0.75 | +51.4% |
| Crypto MA trend BTC+ETH, 50d | 2014–2026 | +60.9% | 1.22 | -59% | 1.39 / 1.04 | +45.4% |
| Crypto MA trend BTC+ETH, 100d | 2014–2026 | +47.0% | 1.01 | -68% | 1.12 / 0.89 | +37.8% |
| Crypto MA trend BTC+ETH, 200d | 2014–2026 | +59.5% | 1.16 | -71% | 1.29 / 1.00 | +54.8% |
| BENCH S&P 500 ETF (CSPX) buy & hold | 2010–2026 | +15.2% | 0.93 | -26% | 1.07 / 0.82 | +15.1% |
| Mean reversion CSPX, RSI2<5 | 2010–2026 | +0.3% | 0.09 | -15% | -0.33 / 0.49 | -1.5% |
| Mean reversion CSPX, RSI2<10 | 2010–2026 | +1.0% | 0.19 | -12% | -0.06 / 0.42 | -3.1% |

What the numbers show:

- **No ETF strategy beat simply holding a world equity ETF on return.** Trend
  following and dual momentum gave smaller drawdowns, but over this period they made
  less money than IWDA and had a lower Sharpe ratio.
- **Crypto trend (hold BTC/ETH above their moving average, else cash)** had a higher
  Sharpe ratio than holding Bitcoin in both halves, at all three settings, and cut
  the worst drawdown from -82% to -59%…-71%. A drawdown of that size is still a
  likely outcome. The early years (2014–2017) were enormous gains from a tiny base,
  and those years drive the CAGR; the second half (2020–2026) gave +34% to +42% a
  year. Nothing says the next decade looks like either.
- **Short-term mean reversion (the "quick trade" idea) failed.** Once realistic costs
  are included it made roughly nothing, and lost money at 2× costs.

## Running it

```bash
python trade.py crypto_ma200            # paper account, state in state/crypto_ma200.json
python trade.py etf_dual_momentum       # paper; also prints the orders to place by hand
python trade.py crypto_ma200 --kraken           # real balances, orders only validated by Kraken
python trade.py crypto_ma200 --kraken --live    # places real market orders
```

Strategies: `crypto_ma200`, `crypto_ma50`, `etf_trend`, `etf_dual_momentum`.
Run crypto once a day and ETFs once a month after the last trading day, for example
from cron: `5 0 * * * cd /path/trading_bot && python trade.py crypto_ma200 >> bot.log`.

Safety rails in `trade.py`:
- Trades below £10 (`--min-trade`) or within 5% of target (`--band`) are skipped.
- Kill switch: if the account falls 35% from its peak (`--max-dd`) it sells to cash
  and halts until you clear the `halted` flag in the state file.
- Kraken orders are sent with `validate=true` unless you pass `--live`.

For Kraken, create an API key with only **Query funds** and **Create & modify orders**
permissions (never Withdraw), then `export KRAKEN_API_KEY=... KRAKEN_API_SECRET=...`.
The order and balance code is written to Kraken's documented signing scheme but has
not been run against a real account in this session (no keys were available).
Check it with the validate-only mode first.

## Assumptions and limits

- **Costs are assumptions, not quotes** (`config.py`): 0.10% per side for GBP ETFs,
  0.25% for USD-quoted ETFs (spread + FX fee), 0.50% for crypto. Set them to your
  broker's real fees. Every result is also shown at 2× costs.
- Data comes from Yahoo Finance (adjusted closes), converted to GBP with GBPUSD.
  Free data can contain errors, especially for early crypto prices.
- Orders fill at the close. In reality you trade the next day at a different price.
- The ETF universe has only 8 funds, and history starts in 2013, so it covers one
  long bull market and only a few sharp sell-offs (2020, 2022).
- UK tax: gains outside an ISA or SIPP may be subject to Capital Gains Tax, and
  frequent trading creates many disposals to record. Crypto cannot be held in an ISA.

## Layout

```
config.py          universes and cost assumptions
run_backtests.py   full report
trade.py           daily/monthly runner: paper or Kraken
bot/data.py        Yahoo download, GBP conversion, cache
bot/backtest.py    backtester (next-day execution, costs, stats)
bot/strategies.py  trend following, dual momentum, MA trend, mean reversion
bot/kraken.py      Kraken REST client
tests/             unit tests
```
