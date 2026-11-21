"""Daily price data from Yahoo Finance's public chart endpoint, cached on disk.

All prices are returned in GBP so that returns are what a UK account sees.
USD-quoted instruments are converted with the GBPUSD=X rate; GBp (pence)
quotes are divided by 100.
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"
_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _download(ticker: str) -> tuple[pd.Series, str]:
    params = {
        "period1": 0,
        "period2": int(time.time()),
        "interval": "1d",
        "events": "div,split",
    }
    last_err = None
    for attempt in range(4):
        try:
            r = requests.get(_URL.format(ticker=ticker), params=params,
                             headers=_HEADERS, timeout=30)
            r.raise_for_status()
            chart = r.json()["chart"]
            if chart["result"] is None:
                raise ValueError(f"{ticker}: {chart['error']}")
            res = chart["result"][0]
            idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
            ind = res["indicators"]
            if "adjclose" in ind:
                px = ind["adjclose"][0]["adjclose"]
            else:
                px = ind["quote"][0]["close"]
            s = pd.Series(px, index=idx, name=ticker, dtype="float64")
            s = s[~s.index.duplicated(keep="last")].dropna()
            s = s[s > 0]
            return s, res["meta"].get("currency", "")
        except Exception as e:  # network hiccup: back off and retry
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"download failed for {ticker}: {last_err}")


def get_series(ticker: str, refresh: bool = False,
               max_age_hours: float = 12) -> tuple[pd.Series, str]:
    """Price series for one ticker in its own currency (GBp converted to GBP)."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{ticker.replace('^', '_').replace('=', '_')}.csv"
    if path.exists() and not refresh:
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if age_h < max_age_hours:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            return df["price"].rename(ticker), df["currency"].iloc[0]
    s, ccy = _download(ticker)
    if ccy == "GBp":
        s = s / 100.0
        ccy = "GBP"
    pd.DataFrame({"price": s, "currency": ccy}).to_csv(path)
    return s, ccy


def get_prices_gbp(tickers: list[str], refresh: bool = False) -> pd.DataFrame:
    """Close prices in GBP, one column per ticker, on the union of trading days.

    Gaps (holidays, different exchange calendars) are forward-filled so a
    missing day counts as a zero return, never as a jump.
    """
    fx = None
    cols = {}
    for t in tickers:
        s, ccy = get_series(t, refresh=refresh)
        if ccy == "USD":
            if fx is None:
                fx, _ = get_series("GBPUSD=X", refresh=refresh)  # USD per GBP
            f = fx.reindex(s.index.union(fx.index)).ffill().reindex(s.index)
            s = (s / f).dropna()
        elif ccy not in ("GBP",):
            raise ValueError(f"{t}: unsupported currency {ccy}")
        cols[t] = s
    df = pd.DataFrame(cols).sort_index()
    return df.ffill()


def today() -> dt.date:
    return dt.date.today()
