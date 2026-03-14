"""
config_view — strategy, system, and credentials config editor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import customtkinter as ctk


class ConfigView(ctk.CTkFrame):
    def __init__(self, parent, source_dir: Path, **kwargs) -> None:
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.source_dir = source_dir
        self.strategy_path = source_dir / "strategy_config.json"
        self.system_path = source_dir / "system_config.json"
        self.credentials_path = source_dir / "credentials.json"

        self._status = ctk.StringVar(value="")
        self._strategy_vars: Dict[str, Any] = {}
        self._system_vars: Dict[str, Any] = {}
        self._cred_vars: Dict[str, ctk.StringVar] = {}

        self.strategy_cfg = self._load(self.strategy_path, {})
        self.system_cfg = self._load(self.system_path, {})
        self.credentials_cfg = self._load(self.credentials_path, {"upstox": {}})

        tabs = ctk.CTkTabview(self, fg_color="#eef3ff")
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        for name in ("Credentials", "Strategy", "System"):
            tabs.add(name)

        self._build_credentials_tab(tabs.tab("Credentials"))
        self._build_strategy_tab(tabs.tab("Strategy"))
        self._build_system_tab(tabs.tab("System"))

        ctk.CTkLabel(self, textvariable=self._status, text_color="#1f4778", font=("Segoe UI", 12)).pack(
            anchor="w", padx=12, pady=(0, 8)
        )

    def update_state(self, state) -> None:
        pass  # config view doesn't need live state

    # --- Credentials ---

    def _build_credentials_tab(self, parent) -> None:
        frame = ctk.CTkScrollableFrame(parent, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._section_label(frame, "Upstox Credentials")
        up = self.credentials_cfg.get("upstox", {})
        for key, label in [
            ("api_key", "API Key"), ("api_secret", "API Secret"), ("redirect_uri", "Redirect URI"),
            ("totp_key", "TOTP Key"), ("mobile_no", "Mobile Number"), ("pin", "PIN"),
        ]:
            var = ctk.StringVar(value=str(up.get(key, "")))
            self._cred_vars[key] = var
            self._entry_row(frame, label, var, secret=key in {"api_secret", "totp_key", "pin"})

        ctk.CTkButton(frame, text="Save Credentials", command=self._save_credentials,
                       fg_color="#2d6cdf", hover_color="#2258b8").pack(anchor="e", padx=8, pady=12)

    def _save_credentials(self) -> None:
        self.credentials_cfg.setdefault("upstox", {})
        for key, var in self._cred_vars.items():
            self.credentials_cfg["upstox"][key] = var.get().strip()
        self._save(self.credentials_path, self.credentials_cfg)
        self._status.set("Credentials saved")

    # --- Strategy ---

    def _build_strategy_tab(self, parent) -> None:
        frame = ctk.CTkScrollableFrame(parent, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Entry conditions
        self._section_label(frame, "Entry Conditions")
        entry = self.strategy_cfg.get("entry_conditions", {})
        self._dropdown_row(frame, "Timeframe (min)", "timeframe_minutes",
                           str(entry.get("timeframe_minutes", 3)), ["2", "3", "5"])
        self._switch_row(frame, "Enable RSI", "rsi_enabled", bool(entry.get("rsi", {}).get("enabled", True)))
        self._num_row(frame, "RSI Period", "rsi_period", entry.get("rsi", {}).get("period", 14))
        self._num_row(frame, "RSI Threshold", "rsi_threshold", entry.get("rsi", {}).get("threshold", 60.0))
        self._switch_row(frame, "Enable Volume > EMA", "vol_enabled",
                         bool(entry.get("volume_vs_ema", {}).get("enabled", True)))
        self._num_row(frame, "Volume EMA Period", "vol_ema_period",
                      entry.get("volume_vs_ema", {}).get("ema_period", 20))
        self._switch_row(frame, "Enable MACD", "macd_enabled", bool(entry.get("macd", {}).get("enabled", False)))
        self._num_row(frame, "MACD Fast", "macd_fast", entry.get("macd", {}).get("fast_period", 12))
        self._num_row(frame, "MACD Slow", "macd_slow", entry.get("macd", {}).get("slow_period", 26))
        self._num_row(frame, "MACD Signal", "macd_signal", entry.get("macd", {}).get("signal_period", 9))
        self._switch_row(frame, "Enable ADX", "adx_enabled", bool(entry.get("adx", {}).get("enabled", False)))
        self._num_row(frame, "ADX Period", "adx_period", entry.get("adx", {}).get("period", 14))
        self._num_row(frame, "ADX Threshold", "adx_threshold", entry.get("adx", {}).get("min_threshold", 20.0))

        # Instrument selection
        self._section_label(frame, "Instrument Selection")
        ins = self.strategy_cfg.get("instrument_selection", {})
        self._dropdown_row(frame, "Underlying", "underlying",
                           str(ins.get("underlying", "NIFTY")), ["NIFTY", "BANKNIFTY"])
        self._dropdown_row(frame, "Expiry Choice", "expiry_choice",
                           str(ins.get("expiry_choice", "current")), ["current", "next"])
        self._dropdown_row(frame, "Option Type", "option_type",
                           str(ins.get("option_type", "CE")), ["CE", "PE"])
        self._dropdown_row(frame, "Strike Mode", "strike_mode",
                           str(ins.get("strike_mode", "ATM")), ["ATM", "ITM", "OTM"])
        self._num_row(frame, "Strike Offset", "strike_offset", ins.get("strike_offset", 0))
        self._num_row(frame, "Lots", "lots", ins.get("lots", 1))

        # Order execution
        self._section_label(frame, "Order Execution")
        order = self.strategy_cfg.get("order_execution", {})
        self._dropdown_row(frame, "Order Type", "order_type",
                           str(order.get("order_type", "LIMIT")), ["LIMIT", "MARKET", "SL", "SL-M"])
        self._dropdown_row(frame, "Product", "product",
                           str(order.get("product", "D")), ["D", "I", "CO", "OCO"])
        self._num_row(frame, "Tick Size", "tick_size", order.get("tick_size", 0.05))

        # Exit conditions
        self._section_label(frame, "Exit Conditions")
        exits = self.strategy_cfg.get("exit_conditions", {})
        sl = exits.get("stoploss", {})
        self._switch_row(frame, "Enable Stop-Loss", "sl_enabled", bool(sl.get("enabled", True)))
        self._dropdown_row(frame, "SL Type", "sl_type", str(sl.get("type", "percent")),
                           ["percent", "points", "fixed_price"])
        self._num_row(frame, "SL Value", "sl_value", sl.get("value", 30.0))
        tgt = exits.get("target", {})
        self._switch_row(frame, "Enable Target", "tgt_enabled", bool(tgt.get("enabled", False)))
        self._num_row(frame, "Target Value (%/pts)", "tgt_value", tgt.get("value", 50.0))
        trail = exits.get("trailing_sl", {})
        self._switch_row(frame, "Enable Trailing SL", "trail_enabled", bool(trail.get("enabled", False)))
        self._num_row(frame, "Trail Activate %", "trail_activate", trail.get("activate_at_percent", 20.0))
        self._num_row(frame, "Trail By %", "trail_by", trail.get("trail_by_percent", 10.0))
        time_exit = exits.get("time_based_exit", {})
        self._switch_row(frame, "Enable Time Exit", "time_exit_enabled", bool(time_exit.get("enabled", False)))
        self._str_row(frame, "Exit At Time", "time_exit_at", time_exit.get("exit_at_time", "15:15:00"))

        # Order modify
        self._section_label(frame, "Order Modify")
        mod = self.strategy_cfg.get("order_modify", {})
        self._switch_row(frame, "Modify on Re-entry Signal", "modify_reentry",
                         bool(mod.get("modify_on_reentry_signal", True)))
        self._num_row(frame, "Modify Cooldown (s)", "modify_cooldown", mod.get("modify_cooldown_seconds", 10))
        self._switch_row(frame, "Only Improve Price", "only_improve", bool(mod.get("only_improve_price", True)))

        # Position management
        self._section_label(frame, "Position Management")
        pos = self.strategy_cfg.get("position_management", {})
        self._num_row(frame, "Re-entry Wait (s)", "reentry_wait", pos.get("reentry_wait_seconds_after_close", 30))
        self._switch_row(frame, "Manual Exit Detection", "manual_exit_enabled",
                         bool(pos.get("manual_exit_detection_enabled", True)))

        ctk.CTkButton(frame, text="Save Strategy Config", command=self._save_strategy,
                       fg_color="#2d6cdf", hover_color="#2258b8").pack(anchor="e", padx=8, pady=12)

    def _save_strategy(self) -> None:
        cfg = self.strategy_cfg

        # Entry conditions
        entry = cfg.setdefault("entry_conditions", {})
        entry["timeframe_minutes"] = self._int_val("timeframe_minutes", 3)
        entry.setdefault("rsi", {})
        entry["rsi"]["enabled"] = self._bool_val("rsi_enabled")
        entry["rsi"]["period"] = self._int_val("rsi_period", 14)
        entry["rsi"]["threshold"] = self._float_val("rsi_threshold", 60.0)
        entry["rsi"]["operator"] = ">"
        entry.setdefault("volume_vs_ema", {})
        entry["volume_vs_ema"]["enabled"] = self._bool_val("vol_enabled")
        entry["volume_vs_ema"]["ema_period"] = self._int_val("vol_ema_period", 20)
        entry.setdefault("macd", {})
        entry["macd"]["enabled"] = self._bool_val("macd_enabled")
        entry["macd"]["fast_period"] = self._int_val("macd_fast", 12)
        entry["macd"]["slow_period"] = self._int_val("macd_slow", 26)
        entry["macd"]["signal_period"] = self._int_val("macd_signal", 9)
        entry.setdefault("adx", {})
        entry["adx"]["enabled"] = self._bool_val("adx_enabled")
        entry["adx"]["period"] = self._int_val("adx_period", 14)
        entry["adx"]["min_threshold"] = self._float_val("adx_threshold", 20.0)

        # Instrument selection
        ins = cfg.setdefault("instrument_selection", {})
        ins["underlying"] = self._str_val("underlying")
        ins["expiry_choice"] = self._str_val("expiry_choice")
        ins["option_type"] = self._str_val("option_type")
        ins["strike_mode"] = self._str_val("strike_mode")
        ins["strike_offset"] = self._int_val("strike_offset", 0)
        ins["lots"] = max(1, self._int_val("lots", 1))
        ins["quantity_mode"] = "lots"

        # Order execution
        order = cfg.setdefault("order_execution", {})
        order["order_type"] = self._str_val("order_type")
        order["product"] = self._str_val("product")
        order["tick_size"] = self._float_val("tick_size", 0.05)

        # Exit conditions
        exits = cfg.setdefault("exit_conditions", {})
        exits.setdefault("stoploss", {})
        exits["stoploss"]["enabled"] = self._bool_val("sl_enabled")
        exits["stoploss"]["type"] = self._str_val("sl_type")
        exits["stoploss"]["value"] = self._float_val("sl_value", 30.0)
        exits.setdefault("target", {})
        exits["target"]["enabled"] = self._bool_val("tgt_enabled")
        exits["target"]["value"] = self._float_val("tgt_value", 50.0)
        exits.setdefault("trailing_sl", {})
        exits["trailing_sl"]["enabled"] = self._bool_val("trail_enabled")
        exits["trailing_sl"]["activate_at_percent"] = self._float_val("trail_activate", 20.0)
        exits["trailing_sl"]["trail_by_percent"] = self._float_val("trail_by", 10.0)
        exits.setdefault("time_based_exit", {})
        exits["time_based_exit"]["enabled"] = self._bool_val("time_exit_enabled")
        exits["time_based_exit"]["exit_at_time"] = self._str_val("time_exit_at")

        # Order modify
        mod = cfg.setdefault("order_modify", {})
        mod["modify_on_reentry_signal"] = self._bool_val("modify_reentry")
        mod["modify_cooldown_seconds"] = self._int_val("modify_cooldown", 10)
        mod["only_improve_price"] = self._bool_val("only_improve")

        # Position management
        pos = cfg.setdefault("position_management", {})
        pos["reentry_wait_seconds_after_close"] = self._int_val("reentry_wait", 30)
        pos["manual_exit_detection_enabled"] = self._bool_val("manual_exit_enabled")

        self._save(self.strategy_path, cfg)
        self._status.set("Strategy config saved")

    # --- System ---

    def _build_system_tab(self, parent) -> None:
        frame = ctk.CTkScrollableFrame(parent, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._section_label(frame, "Runtime")
        runtime = self.system_cfg.get("runtime", {})
        self._dropdown_row(frame, "Mode", "sys_mode", str(runtime.get("mode", "paper")), ["paper", "live"],
                           store=self._system_vars)
        self._num_row(frame, "Loop Interval (s)", "sys_loop_interval",
                      runtime.get("loop_interval_seconds", 5), store=self._system_vars)
        self._switch_row(frame, "Ignore Market Hours", "sys_ignore_market",
                         bool(runtime.get("ignore_market_hours", False)), store=self._system_vars)
        self._dropdown_row(frame, "Log Level", "sys_log_level",
                           str(runtime.get("log_level", "INFO")), ["DEBUG", "INFO", "WARNING", "ERROR"],
                           store=self._system_vars)

        self._section_label(frame, "Market Hours")
        market = self.system_cfg.get("market", {})
        self._str_row(frame, "Market Open", "sys_market_open", market.get("open", "09:15:00"),
                      store=self._system_vars)
        self._str_row(frame, "Market Close", "sys_market_close", market.get("close", "15:30:00"),
                      store=self._system_vars)

        self._section_label(frame, "Risk Guard")
        risk = self.system_cfg.get("risk", {})
        self._switch_row(frame, "Risk Enabled", "sys_risk_enabled",
                         bool(risk.get("enabled", False)), store=self._system_vars)
        self._num_row(frame, "Max Daily Loss", "sys_max_loss",
                      risk.get("max_daily_loss", 5000.0), store=self._system_vars)
        self._num_row(frame, "Max Trades/Session", "sys_max_trades",
                      risk.get("max_trades_per_session", 10), store=self._system_vars)

        self._section_label(frame, "Auth")
        auth = self.system_cfg.get("auth", {})
        self._switch_row(frame, "Headless Login", "sys_headless",
                         bool(auth.get("headless", True)), store=self._system_vars)
        self._str_row(frame, "Token Reset Time", "sys_token_reset",
                      auth.get("token_reset_time", "03:30"), store=self._system_vars)

        ctk.CTkButton(frame, text="Save System Config", command=self._save_system,
                       fg_color="#2d6cdf", hover_color="#2258b8").pack(anchor="e", padx=8, pady=12)

    def _save_system(self) -> None:
        cfg = self.system_cfg
        runtime = cfg.setdefault("runtime", {})
        mode = self._str_val("sys_mode", store=self._system_vars).lower()
        runtime["mode"] = "live" if mode == "live" else "paper"
        runtime["loop_interval_seconds"] = max(1, self._int_val("sys_loop_interval", 5, store=self._system_vars))
        runtime["ignore_market_hours"] = self._bool_val("sys_ignore_market", store=self._system_vars)
        runtime["log_level"] = self._str_val("sys_log_level", store=self._system_vars)

        market = cfg.setdefault("market", {})
        market["open"] = self._str_val("sys_market_open", store=self._system_vars)
        market["close"] = self._str_val("sys_market_close", store=self._system_vars)

        risk = cfg.setdefault("risk", {})
        risk["enabled"] = self._bool_val("sys_risk_enabled", store=self._system_vars)
        risk["max_daily_loss"] = self._float_val("sys_max_loss", 5000.0, store=self._system_vars)
        risk["max_trades_per_session"] = self._int_val("sys_max_trades", 10, store=self._system_vars)

        auth = cfg.setdefault("auth", {})
        auth["headless"] = self._bool_val("sys_headless", store=self._system_vars)
        auth["token_reset_time"] = self._str_val("sys_token_reset", store=self._system_vars)

        self._save(self.system_path, cfg)
        self._status.set("System config saved")

    # --- Widget helpers ---

    def _section_label(self, parent, text: str) -> None:
        ctk.CTkLabel(parent, text=text, font=("Segoe UI", 16, "bold"), text_color="#223b66").pack(
            anchor="w", padx=8, pady=(14, 6)
        )

    def _entry_row(self, parent, label: str, var: ctk.StringVar, secret: bool = False) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(row, text=label, width=200, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=var, width=320, show="*" if secret else "").pack(side="left", padx=8)

    def _num_row(self, parent, label: str, key: str, default, store: Dict = None) -> None:
        if store is None:
            store = self._strategy_vars
        var = ctk.StringVar(value=str(default))
        store[key] = var
        self._entry_row(parent, label, var)

    def _str_row(self, parent, label: str, key: str, default: str, store: Dict = None) -> None:
        if store is None:
            store = self._strategy_vars
        var = ctk.StringVar(value=default)
        store[key] = var
        self._entry_row(parent, label, var)

    def _switch_row(self, parent, label: str, key: str, default: bool, store: Dict = None) -> None:
        if store is None:
            store = self._strategy_vars
        var = ctk.BooleanVar(value=default)
        store[key] = var
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(row, text=label, width=200, anchor="w").pack(side="left")
        ctk.CTkSwitch(row, text="", variable=var).pack(side="left", padx=8)

    def _dropdown_row(self, parent, label: str, key: str, default: str, values: list,
                      store: Dict = None) -> None:
        if store is None:
            store = self._strategy_vars
        var = ctk.StringVar(value=default)
        store[key] = var
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(row, text=label, width=200, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, values=values, variable=var, width=200).pack(side="left", padx=8)

    # --- Value getters ---

    def _str_val(self, key: str, store: Dict = None) -> str:
        if store is None:
            store = self._strategy_vars
        var = store.get(key)
        return str(var.get()) if var else ""

    def _int_val(self, key: str, default: int = 0, store: Dict = None) -> int:
        try:
            return int(float(self._str_val(key, store)))
        except (ValueError, TypeError):
            return default

    def _float_val(self, key: str, default: float = 0.0, store: Dict = None) -> float:
        try:
            return float(self._str_val(key, store))
        except (ValueError, TypeError):
            return default

    def _bool_val(self, key: str, store: Dict = None) -> bool:
        if store is None:
            store = self._strategy_vars
        var = store.get(key)
        if isinstance(var, ctk.BooleanVar):
            return var.get()
        return False

    # --- IO ---

    @staticmethod
    def _load(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw = f.read().strip()
                return json.loads(raw) if raw else default
        except Exception:
            return default

    @staticmethod
    def _save(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
