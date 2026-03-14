"""
Tests for instrument selection — strike resolution.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from modules.strategy.instrument_selection import select_entry_contract
from tests.fixtures.sample_universe import make_nifty_universe


def _strategy_cfg(**overrides):
    cfg = {
        "instrument_selection": {
            "underlying": "NIFTY",
            "expiry_choice": "current",
            "option_type": "CE",
            "strike_mode": "ATM",
            "strike_offset": 0,
            "quantity_mode": "lots",
            "lots": 1,
        },
        "order_execution": {},
    }
    cfg["instrument_selection"].update(overrides)
    return cfg


def test_atm_ce_nearest_strike():
    universe = make_nifty_universe(spot=22450.0)
    result = select_entry_contract(universe, _strategy_cfg(), spot_ltp=22450.0)
    assert result is not None
    assert result["contract"]["strike"] == 22450.0


def test_atm_rounds_to_nearest():
    universe = make_nifty_universe(spot=22430.0)
    result = select_entry_contract(universe, _strategy_cfg(), spot_ltp=22430.0)
    assert result is not None
    # 22430 is closer to 22450 than 22400
    assert result["contract"]["strike"] in (22400.0, 22450.0)


def test_otm_ce_offset_1():
    universe = make_nifty_universe()
    cfg = _strategy_cfg(strike_mode="OTM", strike_offset=1)
    result = select_entry_contract(universe, cfg, spot_ltp=22450.0)
    assert result is not None
    assert result["contract"]["strike"] == 22500.0


def test_otm_pe_offset_1():
    universe = make_nifty_universe()
    cfg = _strategy_cfg(option_type="PE", strike_mode="OTM", strike_offset=1)
    result = select_entry_contract(universe, cfg, spot_ltp=22450.0)
    assert result is not None
    assert result["contract"]["strike"] == 22400.0


def test_itm_ce_offset_1():
    universe = make_nifty_universe()
    cfg = _strategy_cfg(strike_mode="ITM", strike_offset=1)
    result = select_entry_contract(universe, cfg, spot_ltp=22450.0)
    assert result is not None
    assert result["contract"]["strike"] == 22400.0


def test_itm_pe_offset_1():
    universe = make_nifty_universe()
    cfg = _strategy_cfg(option_type="PE", strike_mode="ITM", strike_offset=1)
    result = select_entry_contract(universe, cfg, spot_ltp=22450.0)
    assert result is not None
    assert result["contract"]["strike"] == 22500.0


def test_offset_clamped():
    universe = make_nifty_universe()
    cfg = _strategy_cfg(strike_mode="OTM", strike_offset=99)
    result = select_entry_contract(universe, cfg, spot_ltp=22450.0)
    assert result is not None
    # Should clamp to highest available strike
    assert result["contract"]["strike"] == 22900.0


def test_no_contracts_returns_none():
    empty_universe = {"indices": {"NIFTY": {"underlying": "NIFTY", "options": {"CE": {}, "PE": {}}}}}
    result = select_entry_contract(empty_universe, _strategy_cfg(), spot_ltp=22450.0)
    assert result is None


def test_unknown_underlying_returns_none():
    universe = make_nifty_universe()
    cfg = _strategy_cfg(underlying="MIDCAP")
    result = select_entry_contract(universe, cfg, spot_ltp=22450.0)
    assert result is None
