"""Strategies. Each returns target weights (0..1, summing to <= 1) per date.

Weights are decided using data up to and including that date's close only.
The backtester applies them from the following day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _month_ends(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby([index.year, index.month]).last().values)


def buy_and_hold(prices: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for k, v in weights.items():
        w[k] = v
    # only hold an asset once it has a price
    return w.where(prices.notna(), 0.0)


def trend_following(prices: pd.DataFrame, lookback_days: int = 252,
                    vol_days: int = 63, target_vol: float = 0.10) -> pd.DataFrame:
    """Time-series momentum, long-only, rebalanced monthly.

    Hold each asset whose trailing `lookback_days` return is positive, sized by
    inverse volatility so each holding carries similar risk. The whole basket
    is then scaled so its estimated volatility (from the trailing covariance)
    is `target_vol`, never above 100% invested. Each asset's slot is a fixed
    share of the universe, so assets in a downtrend leave their share in cash.
    """
    rets = prices.pct_change()
    mom = prices / prices.shift(lookback_days) - 1
    vol = rets.rolling(vol_days).std() * np.sqrt(252)
    w = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    for d in _month_ends(prices.index):
        m, v = mom.loc[d], vol.loc[d]
        live = v.notna() & (v > 0) & m.notna()
        ok = live & (m > 0)
        row = pd.Series(0.0, index=prices.columns)
        if ok.any():
            inv = 1.0 / v[live]
            slots = inv / inv.sum()            # risk-parity share of the live universe
            raw = slots[ok[live]]              # downtrend slots stay in cash
            window = rets.loc[:d, raw.index].tail(vol_days)
            cov = window.cov().values * 252
            port_vol = float(np.sqrt(raw.values @ cov @ raw.values))
            scale = target_vol / port_vol if port_vol > 0 else 0.0
            raw = raw * scale
            if raw.sum() > 1.0:
                raw /= raw.sum()
            row[raw.index] = raw
        w.loc[d] = row
    return w.ffill().fillna(0.0)


def dual_momentum(prices: pd.DataFrame, lookback_days: int = 252, top_n: int = 2) -> pd.DataFrame:
    """Relative + absolute momentum, rebalanced monthly.

    Rank assets by trailing return, hold the top `top_n` equally, but only
    those whose own trailing return is positive; the rest of the money is cash.
    """
    mom = prices / prices.shift(lookback_days) - 1
    w = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    for d in _month_ends(prices.index):
        m = mom.loc[d].dropna()
        row = pd.Series(0.0, index=prices.columns)
        if len(m):
            best = m.sort_values(ascending=False).head(top_n)
            best = best[best > 0]
            row[best.index] = 1.0 / top_n
        w.loc[d] = row
    return w.ffill().fillna(0.0)


def ma_trend(prices: pd.DataFrame, ma_days: int = 100) -> pd.DataFrame:
    """Hold an equal slice of each asset while its close is above its moving average."""
    ma = prices.rolling(ma_days).mean()
    on = (prices > ma) & ma.notna()
    n_live = ma.notna().sum(axis=1).replace(0, np.nan)   # assets with enough history
    return on.astype(float).div(n_live, axis=0).fillna(0.0)


def rsi(series: pd.Series, n: int = 2) -> pd.Series:
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def short_term_reversion(prices: pd.DataFrame, asset: str, entry_rsi: float = 10,
                         exit_ma: int = 5, trend_ma: int = 200) -> pd.DataFrame:
    """Buy sharp short-term dips in an uptrend; sell on the bounce.

    Enter when 2-day RSI < entry_rsi and price > its trend_ma-day average.
    Exit when price closes above its exit_ma-day average.
    """
    p = prices[asset]
    r = rsi(p, 2)
    trend = p > p.rolling(trend_ma).mean()
    exit_sig = p > p.rolling(exit_ma).mean()
    pos = np.zeros(len(p))
    holding = False
    for i in range(len(p)):
        if not holding and trend.iloc[i] and r.iloc[i] < entry_rsi:
            holding = True
        elif holding and exit_sig.iloc[i]:
            holding = False
        pos[i] = 1.0 if holding else 0.0
    w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    w[asset] = pos
    return w
