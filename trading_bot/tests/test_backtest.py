import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import backtest as bt  # noqa: E402
from bot import strategies as st  # noqa: E402
from trade import plan_orders  # noqa: E402


def prices(vals):
    idx = pd.date_range("2020-01-01", periods=len(vals), freq="D")
    return pd.DataFrame({"A": vals}, index=idx, dtype=float)


class BacktestTests(unittest.TestCase):
    def test_no_lookahead(self):
        # A weight set at day 1's close must not earn day 1's return.
        p = prices([100, 200, 200])
        w = pd.DataFrame({"A": [0.0, 1.0, 1.0]}, index=p.index)
        r = bt.run("t", p, w, 0.0)
        self.assertAlmostEqual(r.equity.iloc[-1], 1.0)

    def test_return_earned_next_day(self):
        p = prices([100, 100, 110])
        w = pd.DataFrame({"A": [0.0, 1.0, 1.0]}, index=p.index)
        r = bt.run("t", p, w, 0.0)
        self.assertAlmostEqual(r.equity.iloc[-1], 1.10)

    def test_costs_charged_on_turnover(self):
        p = prices([100, 100, 100, 100])
        w = pd.DataFrame({"A": [1.0, 0.0, 1.0, 1.0]}, index=p.index)
        r = bt.run("t", p, w, 0.01)
        # three trades of 100% each at 1% -> 0.99^3
        self.assertAlmostEqual(r.equity.iloc[-1], 0.99 ** 3)

    def test_rejects_leverage(self):
        p = prices([100, 101])
        w = pd.DataFrame({"A": [1.5, 1.5]}, index=p.index)
        with self.assertRaises(ValueError):
            bt.run("t", p, w, 0.0)

    def test_ma_trend_uses_only_past(self):
        p = prices(list(np.linspace(100, 200, 50)))
        w1 = st.ma_trend(p, 10)
        w2 = st.ma_trend(p.iloc[:30], 10)
        pd.testing.assert_frame_equal(w1.iloc[:30], w2)

    def test_plan_orders_sells_first_and_skips_small(self):
        orders = plan_orders(1000, {"A": 600, "B": 0}, {"B": 0.6}, min_trade=10, band=0.05)
        self.assertEqual([o[0] for o in orders], ["A", "B"])
        self.assertAlmostEqual(orders[0][1], -600)
        self.assertEqual(plan_orders(1000, {"A": 595}, {"A": 0.6}, 10, 0.05), [])


if __name__ == "__main__":
    unittest.main()
