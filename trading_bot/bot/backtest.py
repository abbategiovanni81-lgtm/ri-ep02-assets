"""Daily backtester with transaction costs and no look-ahead.

A strategy produces target weights dated at a close. Those weights earn the
*next* day's return (`weights.shift(1)`), so a signal computed from today's
close can never trade at today's close. Every change in weight pays
`cost_per_side` on the traded fraction of the portfolio.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Result:
    name: str
    equity: pd.Series        # growth of 1.0
    daily: pd.Series         # net daily returns
    weights: pd.DataFrame
    turnover: pd.Series      # traded fraction of equity per day
    costs: pd.Series         # cost as a fraction of equity per day

    def stats(self, periods_per_year: float | None = None) -> dict:
        return performance(self.daily, self.turnover, periods_per_year)


def run(name: str, prices: pd.DataFrame, weights: pd.DataFrame,
        cost_per_side: float | dict[str, float]) -> Result:
    prices = prices.sort_index()
    weights = weights.reindex(prices.index).ffill().fillna(0.0)
    weights = weights.reindex(columns=prices.columns, fill_value=0.0)
    if (weights.sum(axis=1) > 1.0 + 1e-9).any():
        raise ValueError(f"{name}: weights exceed 100% (no leverage allowed)")
    if (weights < -1e-12).any().any():
        raise ValueError(f"{name}: negative weights (no shorting allowed)")

    rets = prices.pct_change().fillna(0.0)
    held = weights.shift(1).fillna(0.0)          # position held during day t
    gross = (held * rets).sum(axis=1)

    if isinstance(cost_per_side, dict):
        c = pd.Series(cost_per_side).reindex(prices.columns).fillna(0.0)
    else:
        c = pd.Series(float(cost_per_side), index=prices.columns)
    trades = weights.diff().abs()
    trades.iloc[0] = weights.iloc[0].abs()
    cost = (trades * c).sum(axis=1).shift(1).fillna(0.0)  # paid when executed (next day)
    turnover = trades.sum(axis=1).shift(1).fillna(0.0)

    net = gross - cost
    equity = (1.0 + net).cumprod()
    return Result(name, equity, net, weights, turnover, cost)


def performance(daily: pd.Series, turnover: pd.Series | None = None,
                periods_per_year: float | None = None) -> dict:
    daily = daily.dropna()
    if len(daily) < 2:
        return {}
    if periods_per_year is None:
        days = (daily.index[-1] - daily.index[0]).days
        periods_per_year = len(daily) / max(days / 365.25, 1e-9)
    years = len(daily) / periods_per_year
    eq = (1 + daily).cumprod()
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = daily.std() * np.sqrt(periods_per_year)
    sharpe = daily.mean() / daily.std() * np.sqrt(periods_per_year) if daily.std() > 0 else np.nan
    dd = eq / eq.cummax() - 1
    out = {
        "start": daily.index[0].date().isoformat(),
        "end": daily.index[-1].date().isoformat(),
        "years": round(years, 1),
        "CAGR": cagr,
        "vol": vol,
        "sharpe": sharpe,
        "max_dd": dd.min(),
        "worst_year": daily.groupby(daily.index.year).apply(lambda r: (1 + r).prod() - 1).min(),
    }
    if turnover is not None:
        out["turnover_per_year"] = turnover.sum() / years if years > 0 else np.nan
    return out


def split_halves(res: Result) -> tuple[dict, dict]:
    """Stats for the first and second half of the period, to check stability."""
    n = len(res.daily)
    a, b = res.daily.iloc[: n // 2], res.daily.iloc[n // 2:]
    ta, tb = res.turnover.iloc[: n // 2], res.turnover.iloc[n // 2:]
    return performance(a, ta), performance(b, tb)
