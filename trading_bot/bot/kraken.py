"""Minimal Kraken spot REST client (public prices, balances, market orders).

Orders are sent with validate=true unless the caller passes live=True, so by
default Kraken checks the order and returns a description without placing it.
API keys are read from the environment: KRAKEN_API_KEY and KRAKEN_API_SECRET.
Create a key with only "Query funds" and "Create & modify orders" permissions,
and never "Withdraw funds".
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import urllib.parse

import requests

API = "https://api.kraken.com"

# Yahoo ticker -> (Kraken order pair, Kraken balance asset code)
PAIRS = {
    "BTC-GBP": ("XBTGBP", "XXBT"),
    "ETH-GBP": ("ETHGBP", "XETH"),
}
CASH_ASSET = "ZGBP"


class KrakenError(RuntimeError):
    pass


def _check(j: dict) -> dict:
    if j.get("error"):
        raise KrakenError("; ".join(j["error"]))
    return j["result"]


def ticker_prices(pairs: list[str]) -> dict[str, float]:
    """Last trade price per Kraken pair name."""
    out = {}
    for p in pairs:  # one pair per call: Kraken renames keys (XBTGBP -> XXBTZGBP)
        r = requests.get(f"{API}/0/public/Ticker", params={"pair": p}, timeout=20)
        (only,) = _check(r.json()).values()
        out[p] = float(only["c"][0])
    return out


class KrakenClient:
    def __init__(self, key: str | None = None, secret: str | None = None):
        self.key = key or os.environ.get("KRAKEN_API_KEY")
        self.secret = secret or os.environ.get("KRAKEN_API_SECRET")
        if not self.key or not self.secret:
            raise KrakenError("set KRAKEN_API_KEY and KRAKEN_API_SECRET")

    def _private(self, method: str, data: dict | None = None) -> dict:
        path = f"/0/private/{method}"
        data = dict(data or {})
        data["nonce"] = str(int(time.time() * 1000))
        post = urllib.parse.urlencode(data)
        sha = hashlib.sha256((data["nonce"] + post).encode()).digest()
        sig = hmac.new(base64.b64decode(self.secret), path.encode() + sha, hashlib.sha512)
        headers = {"API-Key": self.key, "API-Sign": base64.b64encode(sig.digest()).decode()}
        r = requests.post(API + path, data=data, headers=headers, timeout=30)
        return _check(r.json())

    def balances(self) -> dict[str, float]:
        return {k: float(v) for k, v in self._private("Balance").items()}

    def market_order(self, pair: str, side: str, volume: float, live: bool = False) -> dict:
        if side not in ("buy", "sell"):
            raise ValueError(side)
        data = {"pair": pair, "type": side, "ordertype": "market",
                "volume": f"{volume:.8f}"}
        if not live:
            data["validate"] = "true"
        return self._private("AddOrder", data)
