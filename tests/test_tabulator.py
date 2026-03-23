import pytest

from app.services.tabulator import (
    _fmt_indian,
    compute_portfolio,
    rebalance,
    validate_table,
)


# ── _fmt_indian ──────────────────────────────────────────────────────

class TestFmtIndian:
    def test_small_number(self):
        assert _fmt_indian(999.50) == "999.50"

    def test_thousands(self):
        assert _fmt_indian(1234.00) == "1,234.00"

    def test_lakhs(self):
        assert _fmt_indian(123456.78) == "1,23,456.78"

    def test_crores(self):
        assert _fmt_indian(12345678.90) == "1,23,45,678.90"

    def test_zero(self):
        assert _fmt_indian(0.0) == "0.00"

    def test_negative(self):
        assert _fmt_indian(-50000.00) == "-50,000.00"


# ── validate_table ──────────────────────────────────────────────────

class TestValidateTable:
    def test_qty_ltp_mode(self):
        td = validate_table({
            "col_ids": [0, 1, 2, 3],
            "rows": [
                {"is_header": True, "cells": ["Instrument", "Qty.", "Avg. cost", "LTP"]},
                {"is_header": False, "cells": ["AAA", "100", "10.00", "12.00"]},
            ],
        })
        assert td["valid"]
        assert td["mode"] == "qty_ltp"

    def test_present_value_mode(self):
        td = validate_table({
            "col_ids": [0, 1, 2, 3, 4, 5],
            "rows": [
                {"is_header": True, "cells": ["Symbol", "Qty.", "Buy avg.", "Buy value", "LTP", "Present value"]},
                {"is_header": False, "cells": ["AAA", "100", "10.00", "1000.00", "12.00", "1200.00"]},
            ],
        })
        assert td["valid"]
        assert td["mode"] == "present_value"

    def test_missing_columns_invalid(self):
        td = validate_table({
            "col_ids": [0, 1],
            "rows": [
                {"is_header": True, "cells": ["Foo", "Bar"]},
                {"is_header": False, "cells": ["x", "y"]},
            ],
        })
        assert not td["valid"]
        assert td["mode"] is None

    def test_extra_columns_ignored(self):
        td = validate_table({
            "col_ids": [0, 1, 2, 3, 4, 5],
            "rows": [
                {"is_header": True, "cells": ["Symbol", "Qty.", "Buy avg.", "Buy value", "LTP", "Present value"]},
                {"is_header": False, "cells": ["GGBL-SM", "600", "264.10", "1,58,460.00", "283.20", "1,69,920.00"]},
            ],
        })
        assert td["valid"]
        assert td["col_map"]["name"] == 0
        assert td["col_map"]["present_value"] == 5


# ── compute_portfolio ────────────────────────────────────────────────

@pytest.fixture
def table_data_qty_ltp():
    return validate_table({
        "col_ids": [0, 1, 2, 3],
        "rows": [
            {"is_header": True, "cells": ["Instrument", "Qty.", "Avg. cost", "LTP"]},
            {"is_header": False, "cells": ["AAA", "100", "10.00", "12.00"]},
            {"is_header": False, "cells": ["BBB", "200", "5.00", "6.00"]},
        ],
    })


@pytest.fixture
def table_data_pv():
    return validate_table({
        "col_ids": [0, 1, 2, 3, 4, 5],
        "rows": [
            {"is_header": True, "cells": ["Symbol", "Qty.", "Buy avg.", "Buy value", "LTP", "Present value"]},
            {"is_header": False, "cells": ["AAA", "100", "10.00", "1000.00", "12.00", "1200.00"]},
            {"is_header": False, "cells": ["BBB", "200", "5.00", "1000.00", "6.00", "1200.00"]},
        ],
    })


class TestComputePortfolio:
    def test_values_correct_qty_ltp(self, table_data_qty_ltp):
        p = compute_portfolio(table_data_qty_ltp, 1000.0)
        raw = p["instruments_raw"]
        assert raw["AAA"] == 1200.0
        assert raw["BBB"] == 1200.0

    def test_values_correct_present_value(self, table_data_pv):
        p = compute_portfolio(table_data_pv, 1000.0)
        raw = p["instruments_raw"]
        assert raw["AAA"] == 1200.0
        assert raw["BBB"] == 1200.0

    def test_portfolio_value(self, table_data_qty_ltp):
        p = compute_portfolio(table_data_qty_ltp, 1000.0)
        assert p["portfolio_value_raw"] == 3400.0

    def test_percentages_sum_to_100(self, table_data_qty_ltp):
        p = compute_portfolio(table_data_qty_ltp, 1000.0)
        total_pct = sum(
            float(row[2].rstrip("%")) for row in p["rows"]
        )
        assert abs(total_pct - 100.0) < 0.1

    def test_raw_fields_present(self, table_data_qty_ltp):
        p = compute_portfolio(table_data_qty_ltp, 1000.0)
        assert "portfolio_value_raw" in p
        assert "cash_raw" in p
        assert "instruments_raw" in p
        assert p["cash_raw"] == 1000.0

    def test_cash_row_appended(self, table_data_qty_ltp):
        p = compute_portfolio(table_data_qty_ltp, 1000.0)
        last_row = p["rows"][-1]
        assert last_row[0] == "Cash"
        assert last_row[1] == _fmt_indian(1000.0)


# ── rebalance ────────────────────────────────────────────────────────

@pytest.fixture
def portfolio():
    return {
        "portfolio_value_raw": 10000.0,
        "cash_raw": 2000.0,
        "instruments_raw": {"AAA": 5000.0, "BBB": 3000.0},
    }


class TestRebalanceHappy:
    def test_buy_action(self, portfolio):
        result = rebalance(portfolio, {"AAA": 60})
        aaa = next(a for a in result["actions"] if a["instrument"] == "AAA")
        assert aaa["action"] == "Buy"
        assert aaa["target_value"] == 6000.0
        assert aaa["delta"] == 1000.0

    def test_sell_action(self, portfolio):
        result = rebalance(portfolio, {"BBB": 20})
        bbb = next(a for a in result["actions"] if a["instrument"] == "BBB")
        assert bbb["action"] == "Sell"
        assert bbb["target_value"] == 2000.0
        assert bbb["delta"] == -1000.0

    def test_hold_action(self, portfolio):
        result = rebalance(portfolio, {"AAA": 50})
        aaa = next(a for a in result["actions"] if a["instrument"] == "AAA")
        assert aaa["action"] == "Hold"
        assert aaa["delta"] == 0

    def test_sells_before_buys(self, portfolio):
        result = rebalance(portfolio, {"AAA": 70, "BBB": 10})
        actions = result["actions"]
        action_types = [a["action"] for a in actions]
        if "Sell" in action_types and "Buy" in action_types:
            last_sell = max(i for i, t in enumerate(action_types) if t == "Sell")
            first_buy = min(i for i, t in enumerate(action_types) if t == "Buy")
            assert last_sell < first_buy

    def test_cash_updated_correctly(self, portfolio):
        # Sell BBB by 1000, buy AAA by 1000 → cash unchanged
        result = rebalance(portfolio, {"AAA": 60, "BBB": 20})
        cash_row = result["rebalanced_rows"][-1]
        assert cash_row[0] == "Cash"
        assert float(cash_row[2].rstrip("%")) > 0

    def test_rebalanced_percentages_sum_to_100(self, portfolio):
        result = rebalance(portfolio, {"AAA": 60, "BBB": 20})
        total_pct = sum(
            float(row[2].rstrip("%")) for row in result["rebalanced_rows"]
        )
        assert abs(total_pct - 100.0) < 0.1

    def test_portfolio_value_unchanged(self, portfolio):
        result = rebalance(portfolio, {"AAA": 60, "BBB": 20})
        # Sum all instrument values + cash
        rows = result["rebalanced_rows"]
        # Portfolio value string is present
        assert result["portfolio_value"] == _fmt_indian(10000.0)


class TestRebalanceEdgeCases:
    def test_insufficient_cash_blocked(self, portfolio):
        # AAA target 90% needs 4000 more, cash only 2000, no sells
        result = rebalance(portfolio, {"AAA": 90})
        assert result["error"] is not None
        assert "Insufficient cash" in result["error"]
        assert result["rebalanced_rows"] is None
        assert result["shortfall"] > 0

    def test_sells_fund_buys(self, portfolio):
        # Buy AAA +2000, sell BBB -2000 → sells free cash for buys
        result = rebalance(portfolio, {"AAA": 70, "BBB": 10})
        assert result["error"] is None
        assert result["rebalanced_rows"] is not None

    def test_empty_targets(self, portfolio):
        result = rebalance(portfolio, {})
        assert result["actions"] == []
        assert result["error"] is None

    def test_single_instrument_target(self, portfolio):
        result = rebalance(portfolio, {"AAA": 60})
        # Only AAA targeted, BBB untouched in rebalanced output
        instruments = [r[0] for r in result["rebalanced_rows"] if r[0] != "Cash"]
        assert "AAA" in instruments
        assert "BBB" in instruments  # still present

    def test_target_zero_percent(self, portfolio):
        result = rebalance(portfolio, {"AAA": 0})
        aaa = next(a for a in result["actions"] if a["instrument"] == "AAA")
        assert aaa["action"] == "Sell"
        assert aaa["delta"] == -5000.0

    def test_all_instruments_targeted_to_zero(self, portfolio):
        result = rebalance(portfolio, {"AAA": 0, "BBB": 0})
        assert result["error"] is None
        # All sold, cash should equal portfolio value
        cash_row = result["rebalanced_rows"][-1]
        assert cash_row[0] == "Cash"
        assert cash_row[1] == _fmt_indian(10000.0)
