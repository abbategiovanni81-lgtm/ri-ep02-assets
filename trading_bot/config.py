"""Universes and cost assumptions. Edit these to match your broker's actual fees.

COSTS ARE ASSUMPTIONS, not quotes from any broker. They are a per-side cost as a
fraction of the trade value (fee + half the bid/ask spread + FX conversion).
Check your broker's fee page and change them; run_backtests.py also reruns
everything at double these costs so you can see how sensitive each result is.
"""

# UK-listed UCITS ETFs (a UK retail account generally cannot buy US-listed ETFs
# such as SPY because they have no UK key information document).
ETF_UNIVERSE = {
    "IWDA.L": "iShares Core MSCI World (USD line)",
    "VUKE.L": "Vanguard FTSE 100",
    "EIMI.L": "iShares Core MSCI Emerging Markets (USD line)",
    "IGLT.L": "iShares Core UK Gilts",
    "IDTL.L": "iShares USD Treasury 20+yr (USD line)",
    "SGLN.L": "iShares Physical Gold",
    "IUKP.L": "iShares UK Property",
    "CMOD.L": "Invesco Bloomberg Commodity (USD line)",
}

CRYPTO_UNIVERSE = {
    "BTC-GBP": "Bitcoin",
    "ETH-GBP": "Ether",
}

# Instrument used for the short-term mean-reversion test (S&P 500 UCITS ETF).
REVERSION_ASSET = "CSPX.L"

# Per-side cost assumptions (fraction of trade value).
COST_GBP_ETF = 0.0010    # 0.10%: spread on liquid GBP-quoted ETFs
COST_USD_ETF = 0.0025    # 0.25%: spread + FX conversion fee on a GBP account
COST_CRYPTO = 0.0050     # 0.50%: exchange taker fee + spread on spot crypto

USD_QUOTED = {"IWDA.L", "EIMI.L", "IDTL.L", "CMOD.L", "CSPX.L"}


def cost_for(ticker: str) -> float:
    if ticker in CRYPTO_UNIVERSE:
        return COST_CRYPTO
    if ticker in USD_QUOTED:
        return COST_USD_ETF
    return COST_GBP_ETF


STARTING_CAPITAL_GBP = 1000.0
