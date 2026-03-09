"""
Simple CTK config editor for Santosh trading setup.
GUI is intentionally file-based and does not perform broker authentication.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

import customtkinter as ctk

FRONTEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FRONTEND_DIR.parent
SOURCE_DIR = PROJECT_ROOT / "Backend" / "source"
STRATEGY_PATH = SOURCE_DIR / "strategy_config.json"
SYSTEM_PATH = SOURCE_DIR / "system_config.json"
CREDENTIALS_PATH = SOURCE_DIR / "credentials.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            raw = file.read().strip()
            if not raw:
                return default
            return json.loads(raw)
    except Exception:
        return default


def _save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


class SantoshConfigApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("Santosh Trading Setup - Config Editor")
        self.geometry("1100x760")
        self.minsize(960, 680)

        self.system_cfg: Dict[str, Any] = _load_json(SYSTEM_PATH, {})
        self.strategy_cfg: Dict[str, Any] = _load_json(STRATEGY_PATH, {})
        self.credentials_cfg: Dict[str, Any] = _load_json(CREDENTIALS_PATH, {"upstox": {}})

        self._status_text = ctk.StringVar(value="Ready")
        self._build_ui()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="#f5f8ff")
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="Santosh Trading Setup",
            font=("Segoe UI", 24, "bold"),
            text_color="#1b3056",
        ).pack(anchor="w", padx=20, pady=(14, 0))
        ctk.CTkLabel(
            header,
            text="Standalone config editor",
            font=("Segoe UI", 13),
            text_color="#4c5b78",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        tabs = ctk.CTkTabview(self, fg_color="#eef3ff")
        tabs.pack(fill="both", expand=True, padx=16, pady=16)
        for name in ("Credentials", "Strategy", "System"):
            tabs.add(name)

        self._build_credentials_tab(tabs.tab("Credentials"))
        self._build_strategy_tab(tabs.tab("Strategy"))
        self._build_system_tab(tabs.tab("System"))

        footer = ctk.CTkFrame(self, corner_radius=0, fg_color="#f7f9ff")
        footer.pack(fill="x")
        ctk.CTkLabel(footer, textvariable=self._status_text, text_color="#1f4778").pack(
            anchor="w", padx=16, pady=8
        )

    def _build_credentials_tab(self, parent) -> None:
        self._cred_vars: Dict[str, ctk.StringVar] = {}
        frame = ctk.CTkScrollableFrame(parent, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(frame, text="Upstox Credentials", font=("Segoe UI", 18, "bold"), text_color="#223b66").pack(
            anchor="w", padx=8, pady=(8, 12)
        )

        up = self.credentials_cfg.get("upstox", {})
        fields = [
            ("api_key", "API Key"),
            ("api_secret", "API Secret"),
            ("redirect_uri", "Redirect URI"),
            ("totp_key", "TOTP Key"),
            ("mobile_no", "Mobile Number"),
            ("pin", "PIN"),
        ]
        for key, label in fields:
            var = ctk.StringVar(value=str(up.get(key, "")))
            self._cred_vars[key] = var
            self._entry_row(frame, label, var, secret=(key in {"api_secret", "totp_key", "pin"}))

        ctk.CTkButton(
            frame,
            text="Save Credentials",
            command=self._save_credentials,
            fg_color="#2d6cdf",
            hover_color="#2258b8",
        ).pack(anchor="e", padx=8, pady=14)

    def _build_strategy_tab(self, parent) -> None:
        self._strategy_vars: Dict[str, object] = {}
        frame = ctk.CTkScrollableFrame(parent, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(frame, text="Entry Conditions", font=("Segoe UI", 17, "bold"), text_color="#223b66").pack(
            anchor="w", padx=8, pady=(8, 10)
        )
        entry = self.strategy_cfg.get("entry_conditions", {})
        self._option_row(
            frame,
            "Timeframe (minutes)",
            "timeframe_minutes",
            ctk.StringVar(value=str(entry.get("timeframe_minutes", 3))),
            ["2", "3", "5"],
        )
        self._switch_row(frame, "Enable RSI", "rsi_enabled", bool(entry.get("rsi", {}).get("enabled", True)))
        self._entry_row(frame, "RSI Period", self._bind_strategy_var("rsi_period", entry.get("rsi", {}).get("period", 14)))
        self._entry_row(
            frame,
            "RSI Threshold",
            self._bind_strategy_var("rsi_threshold", entry.get("rsi", {}).get("threshold", 60.0)),
        )
        self._switch_row(
            frame,
            "Enable Volume > EMA",
            "volume_enabled",
            bool(entry.get("volume_vs_ema", {}).get("enabled", True)),
        )
        self._entry_row(
            frame,
            "Volume EMA Period",
            self._bind_strategy_var("volume_ema_period", entry.get("volume_vs_ema", {}).get("ema_period", 20)),
        )

        ctk.CTkLabel(frame, text="Additional Indicators", font=("Segoe UI", 17, "bold"), text_color="#223b66").pack(
            anchor="w", padx=8, pady=(16, 10)
        )
        macd = entry.get("macd_confirmation", {})
        self._switch_row(frame, "Enable MACD Confirmation", "macd_enabled", bool(macd.get("enabled", False)))
        self._entry_row(frame, "MACD Fast", self._bind_strategy_var("macd_fast", macd.get("fast_period", 12)))
        self._entry_row(frame, "MACD Slow", self._bind_strategy_var("macd_slow", macd.get("slow_period", 26)))
        self._entry_row(frame, "MACD Signal", self._bind_strategy_var("macd_signal", macd.get("signal_period", 9)))
        self._entry_row(
            frame,
            "MACD Min Histogram",
            self._bind_strategy_var("macd_hist", macd.get("min_histogram", 0.0)),
        )

        adx = entry.get("adx_strength", {})
        self._switch_row(frame, "Enable ADX Strength", "adx_enabled", bool(adx.get("enabled", False)))
        self._entry_row(frame, "ADX Period", self._bind_strategy_var("adx_period", adx.get("period", 14)))
        self._entry_row(frame, "ADX Threshold", self._bind_strategy_var("adx_threshold", adx.get("threshold", 20.0)))

        ctk.CTkLabel(frame, text="Instrument Selection", font=("Segoe UI", 17, "bold"), text_color="#223b66").pack(
            anchor="w", padx=8, pady=(16, 10)
        )
        ins = self.strategy_cfg.get("instrument_selection", {})
        self._option_row(
            frame,
            "Underlying",
            "underlying",
            ctk.StringVar(value=str(ins.get("underlying", "NIFTY"))),
            ["NIFTY", "BANKNIFTY"],
        )
        self._option_row(
            frame,
            "Expiry Choice",
            "expiry_choice",
            ctk.StringVar(value=str(ins.get("expiry_choice", "current"))),
            ["current", "next"],
        )
        self._option_row(
            frame,
            "Option Type",
            "option_type",
            ctk.StringVar(value=str(ins.get("option_type", "CE"))),
            ["CE", "PE"],
        )
        self._option_row(
            frame,
            "Strike Mode",
            "strike_mode",
            ctk.StringVar(value=str(ins.get("strike_mode", "ATM"))),
            ["ATM", "ITM", "OTM"],
        )
        self._entry_row(frame, "Strike Offset", self._bind_strategy_var("strike_offset", ins.get("strike_offset", 0)))

        ctk.CTkLabel(frame, text="Order Details", font=("Segoe UI", 17, "bold"), text_color="#223b66").pack(
            anchor="w", padx=8, pady=(16, 10)
        )
        order = self.strategy_cfg.get("order_details", {})
        self._option_row(
            frame,
            "Order Type",
            "order_type",
            ctk.StringVar(value=str(order.get("order_type", "LIMIT"))),
            ["LIMIT", "MARKET", "SL", "SL-M"],
        )
        self._entry_row(frame, "Lots", self._bind_strategy_var("lots", order.get("lots", 1)))
        self._switch_row(
            frame,
            "Modify on Re-entry Signal",
            "modify_on_reentry_signal",
            bool(order.get("modify_on_reentry_signal", True)),
        )
        self._entry_row(
            frame,
            "Modify Cooldown Seconds",
            self._bind_strategy_var("modify_cooldown_seconds", order.get("modify_cooldown_seconds", 10)),
        )
        self._switch_row(
            frame,
            "Only Improve Price",
            "only_improve_price",
            bool(order.get("only_improve_price", True)),
        )

        ctk.CTkButton(
            frame,
            text="Save Strategy Config",
            command=self._save_strategy,
            fg_color="#2d6cdf",
            hover_color="#2258b8",
        ).pack(anchor="e", padx=8, pady=14)

    def _build_system_tab(self, parent) -> None:
        self._system_vars: Dict[str, object] = {}
        frame = ctk.CTkFrame(parent, fg_color="#ffffff")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        runtime = self.system_cfg.get("runtime", {})
        ctk.CTkLabel(frame, text="Runtime", font=("Segoe UI", 17, "bold"), text_color="#223b66").pack(
            anchor="w", padx=14, pady=(14, 10)
        )
        self._system_option_row(
            frame,
            "Mode",
            "runtime_mode",
            ctk.StringVar(value=str(runtime.get("mode", "paper"))),
            ["paper", "live"],
        )
        self._system_entry_row(
            frame,
            "Loop Interval Seconds",
            self._bind_system_var("loop_interval", runtime.get("loop_interval_seconds", 5)),
        )
        self._system_switch_row(
            frame,
            "Ignore Market Hours",
            "ignore_market_hours",
            bool(runtime.get("ignore_market_hours", False)),
        )

        ctk.CTkButton(
            frame,
            text="Save System Config",
            command=self._save_system,
            fg_color="#2d6cdf",
            hover_color="#2258b8",
        ).pack(anchor="e", padx=14, pady=16)

    def _entry_row(self, parent, label: str, var: ctk.StringVar, secret: bool = False) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(row, text=label, width=210, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=var, width=380, show="*" if secret else "").pack(side="left", padx=10)

    def _option_row(self, parent, label: str, key: str, var: ctk.StringVar, values) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(row, text=label, width=210, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, values=values, variable=var, width=220).pack(side="left", padx=10)
        self._strategy_vars[key] = var

    def _switch_row(self, parent, label: str, key: str, value: bool) -> None:
        var = ctk.BooleanVar(value=value)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=5)
        ctk.CTkLabel(row, text=label, width=210, anchor="w").pack(side="left")
        ctk.CTkSwitch(row, text="", variable=var).pack(side="left", padx=10)
        self._strategy_vars[key] = var

    def _bind_strategy_var(self, key: str, value) -> ctk.StringVar:
        var = ctk.StringVar(value=str(value))
        self._strategy_vars[key] = var
        return var

    def _system_entry_row(self, parent, label: str, var: ctk.StringVar) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=5)
        ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=var, width=220).pack(side="left", padx=10)

    def _system_option_row(self, parent, label: str, key: str, var: ctk.StringVar, values) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=5)
        ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, values=values, variable=var, width=220).pack(side="left", padx=10)
        self._system_vars[key] = var

    def _system_switch_row(self, parent, label: str, key: str, value: bool) -> None:
        var = ctk.BooleanVar(value=value)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=5)
        ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left")
        ctk.CTkSwitch(row, text="", variable=var).pack(side="left", padx=10)
        self._system_vars[key] = var

    def _bind_system_var(self, key: str, value) -> ctk.StringVar:
        var = ctk.StringVar(value=str(value))
        self._system_vars[key] = var
        return var

    def _save_credentials(self) -> None:
        self.credentials_cfg.setdefault("upstox", {})
        for key, var in self._cred_vars.items():
            self.credentials_cfg["upstox"][key] = var.get().strip()
        _save_json(CREDENTIALS_PATH, self.credentials_cfg)
        self._status_text.set("Credentials saved")

    def _save_strategy(self) -> None:
        entry = self.strategy_cfg.setdefault("entry_conditions", {})
        entry.setdefault("rsi", {})
        entry.setdefault("volume_vs_ema", {})
        entry.setdefault("macd_confirmation", {})
        entry.setdefault("adx_strength", {})

        entry["timeframe_minutes"] = _safe_int(self._strategy_vars["timeframe_minutes"].get(), 3)
        if entry["timeframe_minutes"] not in (2, 3, 5):
            entry["timeframe_minutes"] = 3

        entry["rsi"]["enabled"] = bool(self._strategy_vars["rsi_enabled"].get())
        entry["rsi"]["period"] = _safe_int(self._strategy_vars["rsi_period"].get(), 14)
        entry["rsi"]["threshold"] = _safe_float(self._strategy_vars["rsi_threshold"].get(), 60.0)
        entry["rsi"]["operator"] = ">"

        entry["volume_vs_ema"]["enabled"] = bool(self._strategy_vars["volume_enabled"].get())
        entry["volume_vs_ema"]["ema_period"] = _safe_int(self._strategy_vars["volume_ema_period"].get(), 20)

        entry["macd_confirmation"]["enabled"] = bool(self._strategy_vars["macd_enabled"].get())
        entry["macd_confirmation"]["fast_period"] = _safe_int(self._strategy_vars["macd_fast"].get(), 12)
        entry["macd_confirmation"]["slow_period"] = _safe_int(self._strategy_vars["macd_slow"].get(), 26)
        entry["macd_confirmation"]["signal_period"] = _safe_int(self._strategy_vars["macd_signal"].get(), 9)
        entry["macd_confirmation"]["min_histogram"] = _safe_float(self._strategy_vars["macd_hist"].get(), 0.0)

        entry["adx_strength"]["enabled"] = bool(self._strategy_vars["adx_enabled"].get())
        entry["adx_strength"]["period"] = _safe_int(self._strategy_vars["adx_period"].get(), 14)
        entry["adx_strength"]["threshold"] = _safe_float(self._strategy_vars["adx_threshold"].get(), 20.0)

        ins = self.strategy_cfg.setdefault("instrument_selection", {})
        ins["underlying"] = self._strategy_vars["underlying"].get()
        ins["expiry_choice"] = self._strategy_vars["expiry_choice"].get()
        if ins["expiry_choice"] not in {"current", "next"}:
            ins["expiry_choice"] = "current"
        ins["option_type"] = self._strategy_vars["option_type"].get()
        ins["strike_mode"] = self._strategy_vars["strike_mode"].get()
        ins["strike_offset"] = _safe_int(self._strategy_vars["strike_offset"].get(), 0)

        order = self.strategy_cfg.setdefault("order_details", {})
        order["order_type"] = self._strategy_vars["order_type"].get()
        order["lots"] = max(1, _safe_int(self._strategy_vars["lots"].get(), 1))
        order["modify_on_reentry_signal"] = bool(self._strategy_vars["modify_on_reentry_signal"].get())
        order["modify_cooldown_seconds"] = max(1, _safe_int(self._strategy_vars["modify_cooldown_seconds"].get(), 10))
        order["only_improve_price"] = bool(self._strategy_vars["only_improve_price"].get())
        order["max_active_positions"] = 1

        _save_json(STRATEGY_PATH, self.strategy_cfg)
        self._status_text.set("Strategy config saved")

    def _save_system(self) -> None:
        runtime = self.system_cfg.setdefault("runtime", {})
        mode = str(self._system_vars["runtime_mode"].get()).lower()
        runtime["mode"] = "live" if mode == "live" else "paper"
        runtime["loop_interval_seconds"] = max(1, _safe_int(self._system_vars["loop_interval"].get(), 5))
        runtime["ignore_market_hours"] = bool(self._system_vars["ignore_market_hours"].get())

        _save_json(SYSTEM_PATH, self.system_cfg)
        self._status_text.set("System config saved")


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
