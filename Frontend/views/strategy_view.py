"""
strategy_view — Entry / Instrument / Exit config tabs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import customtkinter as ctk

_BG = "#1e2130"
_BG2 = "#252a3d"
_TAB_BG = "#1a1f32"
_FG = "#c9d1e0"
_MUTED = "#6b7280"
_INPUT_BG = "#1a1f32"
_INPUT_BORDER = "#3d4870"
_GREEN = "#22c55e"


class StrategyView(ctk.CTkFrame):
    def __init__(self, parent, source_dir: Path, **kwargs) -> None:
        super().__init__(parent, fg_color=_BG, **kwargs)
        self._path = source_dir / "strategy_config.json"
        self._cfg = _load(self._path, {})
        self._status = ctk.StringVar(value="")

        tabs = ctk.CTkTabview(self, fg_color=_BG2, segmented_button_fg_color=_TAB_BG,
                               segmented_button_selected_color="#2563eb",
                               segmented_button_selected_hover_color="#1d4ed8",
                               segmented_button_unselected_color=_TAB_BG,
                               segmented_button_unselected_hover_color="#252a3d",
                               text_color=_FG)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        for name in ("Entry", "Instrument", "Exit"):
            tabs.add(name)

        self._build_entry(tabs.tab("Entry"))
        self._build_instrument(tabs.tab("Instrument"))
        self._build_exit(tabs.tab("Exit"))

    def update_state(self, state) -> None:
        pass

    # ── Entry tab ────────────────────────────────────────────────────────────

    def _build_entry(self, parent) -> None:
        self._entry_vars: Dict[str, Any] = {}
        frame = _scroll(parent)
        entry = self._cfg.get("entry_conditions", {})

        _section(frame, "General")
        _dropdown(frame, "Timeframe (min)", "timeframe",
                  str(entry.get("timeframe_minutes", 3)), ["2", "3", "5"], self._entry_vars)

        _section(frame, "RSI")
        rsi = entry.get("rsi", {})
        _switch(frame, "Enable RSI", "rsi_on", bool(rsi.get("enabled", True)), self._entry_vars)
        _num(frame, "RSI Period", "rsi_period", rsi.get("period", 14), self._entry_vars)
        _dropdown(frame, "Operator", "rsi_op", str(rsi.get("operator", ">")), [">", "<"], self._entry_vars)
        _num(frame, "Threshold", "rsi_thr", rsi.get("threshold", 60.0), self._entry_vars)

        _section(frame, "Volume vs EMA")
        vol = entry.get("volume_vs_ema", {})
        _switch(frame, "Enable Volume Filter", "vol_on", bool(vol.get("enabled", True)), self._entry_vars)
        _num(frame, "EMA Period", "vol_ema", vol.get("ema_period", 20), self._entry_vars)

        _section(frame, "ADX (optional)")
        adx = entry.get("adx", {})
        _switch(frame, "Enable ADX", "adx_on", bool(adx.get("enabled", False)), self._entry_vars)
        _num(frame, "ADX Period", "adx_period", adx.get("period", 14), self._entry_vars)
        _num(frame, "Min ADX Threshold", "adx_thr", adx.get("min_threshold", 20.0), self._entry_vars)

        _save_btn(frame, self._save_entry, self._status)

    def _save_entry(self) -> None:
        v = self._entry_vars
        e = self._cfg.setdefault("entry_conditions", {})
        e["timeframe_minutes"] = _iv(v, "timeframe", 3)
        e.setdefault("rsi", {})
        e["rsi"]["enabled"] = _bv(v, "rsi_on")
        e["rsi"]["period"] = _iv(v, "rsi_period", 14)
        e["rsi"]["operator"] = _sv(v, "rsi_op")
        e["rsi"]["threshold"] = _fv(v, "rsi_thr", 60.0)
        e.setdefault("volume_vs_ema", {})
        e["volume_vs_ema"]["enabled"] = _bv(v, "vol_on")
        e["volume_vs_ema"]["ema_period"] = _iv(v, "vol_ema", 20)
        e.setdefault("adx", {})
        e["adx"]["enabled"] = _bv(v, "adx_on")
        e["adx"]["period"] = _iv(v, "adx_period", 14)
        e["adx"]["min_threshold"] = _fv(v, "adx_thr", 20.0)
        _save(self._path, self._cfg)
        self._status.set("Entry config saved ✓")

    # ── Instrument tab ───────────────────────────────────────────────────────

    def _build_instrument(self, parent) -> None:
        self._ins_vars: Dict[str, Any] = {}
        frame = _scroll(parent)
        ins = self._cfg.get("instrument_selection", {})

        _section(frame, "Contract Selection")
        _dropdown(frame, "Underlying", "underlying",
                  str(ins.get("underlying", "NIFTY")), ["NIFTY", "BANKNIFTY"], self._ins_vars)
        _dropdown(frame, "Expiry", "expiry",
                  str(ins.get("expiry_choice", "current")), ["current", "next"], self._ins_vars)
        _dropdown(frame, "Option Type", "opt_type",
                  str(ins.get("option_type", "CE")), ["CE", "PE"], self._ins_vars)
        _dropdown(frame, "Strike Mode", "strike_mode",
                  str(ins.get("strike_mode", "ATM")), ["ATM", "ITM", "OTM"], self._ins_vars)
        _num(frame, "Strike Offset", "strike_offset", ins.get("strike_offset", 0), self._ins_vars)

        _section(frame, "Quantity")
        _dropdown(frame, "Quantity Mode", "qty_mode",
                  str(ins.get("quantity_mode", "lots")), ["lots", "qty"], self._ins_vars)
        _num(frame, "Lots", "lots", ins.get("lots", 1), self._ins_vars)

        _section(frame, "Order Execution")
        order = self._cfg.get("order_execution", {})
        _dropdown(frame, "Order Type", "order_type",
                  str(order.get("order_type", "LIMIT")), ["LIMIT", "MARKET", "SL", "SL-M"], self._ins_vars)
        _dropdown(frame, "Product", "product",
                  str(order.get("product", "D")), ["D", "I", "CO", "OCO"], self._ins_vars)
        _num(frame, "Tick Size", "tick_size", order.get("tick_size", 0.05), self._ins_vars)

        _save_btn(frame, self._save_instrument, self._status)

    def _save_instrument(self) -> None:
        v = self._ins_vars
        ins = self._cfg.setdefault("instrument_selection", {})
        ins["underlying"] = _sv(v, "underlying").upper()
        ins["expiry_choice"] = _sv(v, "expiry")
        ins["option_type"] = _sv(v, "opt_type").upper()
        ins["strike_mode"] = _sv(v, "strike_mode").upper()
        ins["strike_offset"] = _iv(v, "strike_offset", 0)
        ins["quantity_mode"] = _sv(v, "qty_mode")
        ins["lots"] = max(1, _iv(v, "lots", 1))
        order = self._cfg.setdefault("order_execution", {})
        order["order_type"] = _sv(v, "order_type")
        order["product"] = _sv(v, "product")
        order["tick_size"] = _fv(v, "tick_size", 0.05)
        _save(self._path, self._cfg)
        self._status.set("Instrument config saved ✓")

    # ── Exit tab ─────────────────────────────────────────────────────────────

    def _build_exit(self, parent) -> None:
        self._exit_vars: Dict[str, Any] = {}
        frame = _scroll(parent)
        exits = self._cfg.get("exit_conditions", {})
        mod = self._cfg.get("order_modify", {})
        pos = self._cfg.get("position_management", {})

        _section(frame, "Stop-Loss")
        sl = exits.get("stoploss", {})
        _switch(frame, "Enable SL", "sl_on", bool(sl.get("enabled", True)), self._exit_vars)
        _dropdown(frame, "SL Type", "sl_type", str(sl.get("type", "percent")),
                  ["percent", "points", "fixed_price"], self._exit_vars)
        _num(frame, "SL Value", "sl_val", sl.get("value", 30.0), self._exit_vars)
        _dropdown(frame, "SL Order Type", "sl_order",
                  str(sl.get("order_type", "SL-M")), ["SL-M", "MARKET", "LIMIT"], self._exit_vars)

        _section(frame, "Target")
        tgt = exits.get("target", {})
        _switch(frame, "Enable Target", "tgt_on", bool(tgt.get("enabled", False)), self._exit_vars)
        _dropdown(frame, "Target Type", "tgt_type", str(tgt.get("type", "percent")),
                  ["percent", "points"], self._exit_vars)
        _num(frame, "Target Value", "tgt_val", tgt.get("value", 50.0), self._exit_vars)

        _section(frame, "Trailing Stop-Loss")
        trail = exits.get("trailing_sl", {})
        _switch(frame, "Enable Trailing SL", "trail_on", bool(trail.get("enabled", False)), self._exit_vars)
        _num(frame, "Activate at % Profit", "trail_act", trail.get("activate_at_percent", 20.0), self._exit_vars)
        _num(frame, "Trail by %", "trail_by", trail.get("trail_by_percent", 10.0), self._exit_vars)

        _section(frame, "Time-based Exit")
        te = exits.get("time_based_exit", {})
        _switch(frame, "Enable Time Exit", "te_on", bool(te.get("enabled", False)), self._exit_vars)
        _text(frame, "Exit At Time", "te_time", te.get("exit_at_time", "15:15:00"), self._exit_vars)

        _section(frame, "Order Modify")
        _switch(frame, "Modify on Re-entry Signal", "mod_reentry",
                bool(mod.get("modify_on_reentry_signal", True)), self._exit_vars)
        _num(frame, "Modify Cooldown (s)", "mod_cooldown", mod.get("modify_cooldown_seconds", 10), self._exit_vars)
        _switch(frame, "Only Improve Price", "mod_improve",
                bool(mod.get("only_improve_price", True)), self._exit_vars)

        _section(frame, "Position Management")
        _num(frame, "Re-entry Wait (s)", "reentry_wait", pos.get("reentry_wait_seconds_after_close", 30), self._exit_vars)
        _switch(frame, "Manual Exit Detection", "manual_exit_det",
                bool(pos.get("manual_exit_detection_enabled", True)), self._exit_vars)

        _save_btn(frame, self._save_exit, self._status)

    def _save_exit(self) -> None:
        v = self._exit_vars
        exits = self._cfg.setdefault("exit_conditions", {})
        exits.setdefault("stoploss", {})
        exits["stoploss"]["enabled"] = _bv(v, "sl_on")
        exits["stoploss"]["type"] = _sv(v, "sl_type")
        exits["stoploss"]["value"] = _fv(v, "sl_val", 30.0)
        exits["stoploss"]["order_type"] = _sv(v, "sl_order")
        exits.setdefault("target", {})
        exits["target"]["enabled"] = _bv(v, "tgt_on")
        exits["target"]["type"] = _sv(v, "tgt_type")
        exits["target"]["value"] = _fv(v, "tgt_val", 50.0)
        exits.setdefault("trailing_sl", {})
        exits["trailing_sl"]["enabled"] = _bv(v, "trail_on")
        exits["trailing_sl"]["activate_at_percent"] = _fv(v, "trail_act", 20.0)
        exits["trailing_sl"]["trail_by_percent"] = _fv(v, "trail_by", 10.0)
        exits.setdefault("time_based_exit", {})
        exits["time_based_exit"]["enabled"] = _bv(v, "te_on")
        exits["time_based_exit"]["exit_at_time"] = _sv(v, "te_time")
        mod = self._cfg.setdefault("order_modify", {})
        mod["modify_on_reentry_signal"] = _bv(v, "mod_reentry")
        mod["modify_cooldown_seconds"] = _iv(v, "mod_cooldown", 10)
        mod["only_improve_price"] = _bv(v, "mod_improve")
        pos = self._cfg.setdefault("position_management", {})
        pos["reentry_wait_seconds_after_close"] = _iv(v, "reentry_wait", 30)
        pos["manual_exit_detection_enabled"] = _bv(v, "manual_exit_det")
        _save(self._path, self._cfg)
        self._status.set("Exit config saved ✓")


# ── shared helpers ────────────────────────────────────────────────────────────

def _scroll(parent) -> ctk.CTkScrollableFrame:
    frame = ctk.CTkScrollableFrame(parent, fg_color=_BG, scrollbar_button_color=_BG2,
                                    scrollbar_button_hover_color="#3d4870")
    frame.pack(fill="both", expand=True, padx=4, pady=4)
    return frame


def _section(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, font=("Segoe UI", 15, "bold"),
                 text_color="#e2e8f0").pack(anchor="w", padx=16, pady=(16, 6))


def _row(parent) -> ctk.CTkFrame:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=3)
    return row


def _text(parent, label, key, default, store) -> None:
    row = _row(parent)
    ctk.CTkLabel(row, text=label, width=210, anchor="w", font=("Segoe UI", 13),
                 text_color=_FG).pack(side="left")
    var = ctk.StringVar(value=str(default))
    store[key] = var
    ctk.CTkEntry(row, textvariable=var, width=180, fg_color=_INPUT_BG, text_color=_FG,
                  border_color=_INPUT_BORDER, height=30).pack(side="left", padx=8)


def _num(parent, label, key, default, store) -> None:
    _text(parent, label, key, default, store)


def _switch(parent, label, key, default, store) -> None:
    row = _row(parent)
    ctk.CTkLabel(row, text=label, width=210, anchor="w", font=("Segoe UI", 13),
                 text_color=_FG).pack(side="left")
    var = ctk.BooleanVar(value=default)
    store[key] = var
    ctk.CTkSwitch(row, text="", variable=var, progress_color="#2563eb").pack(side="left", padx=8)


def _dropdown(parent, label, key, default, values, store) -> None:
    row = _row(parent)
    ctk.CTkLabel(row, text=label, width=210, anchor="w", font=("Segoe UI", 13),
                 text_color=_FG).pack(side="left")
    var = ctk.StringVar(value=default)
    store[key] = var
    ctk.CTkOptionMenu(row, values=values, variable=var, width=180,
                       fg_color=_INPUT_BG, button_color="#3d4870",
                       dropdown_fg_color="#1e2130", text_color=_FG).pack(side="left", padx=8)


def _save_btn(parent, cmd, status_var) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=16)
    ctk.CTkButton(row, text="Save", width=160, height=34, fg_color="#2563eb", hover_color="#1d4ed8",
                   font=("Segoe UI", 13, "bold"), command=cmd).pack(side="left")
    ctk.CTkLabel(row, textvariable=status_var, font=("Segoe UI", 12),
                 text_color="#22c55e").pack(side="left", padx=12)


def _sv(store, key, default="") -> str:
    v = store.get(key)
    return str(v.get()) if v else default


def _iv(store, key, default=0) -> int:
    try:
        return int(float(_sv(store, key, str(default))))
    except (ValueError, TypeError):
        return default


def _fv(store, key, default=0.0) -> float:
    try:
        return float(_sv(store, key, str(default)))
    except (ValueError, TypeError):
        return default


def _bv(store, key) -> bool:
    v = store.get(key)
    return bool(v.get()) if isinstance(v, ctk.BooleanVar) else False


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8-sig") as f:
            raw = f.read().strip()
            return json.loads(raw) if raw else default
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
