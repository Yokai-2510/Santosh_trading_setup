"""
system_view — runtime, market hours, risk, and auth settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import customtkinter as ctk

_BG = "#1e2130"
_BG2 = "#252a3d"
_FG = "#c9d1e0"
_MUTED = "#6b7280"
_INPUT_BG = "#1a1f32"
_INPUT_BORDER = "#3d4870"
_GREEN = "#22c55e"


class SystemView(ctk.CTkScrollableFrame):
    def __init__(self, parent, configs_dir: Path, **kwargs) -> None:
        super().__init__(parent, fg_color=_BG, scrollbar_button_color=_BG2,
                         scrollbar_button_hover_color="#3d4870", **kwargs)
        self._path = configs_dir / "system_config.json"
        self._cfg = _load(self._path, {})
        self._vars: Dict[str, Any] = {}
        self._status = ctk.StringVar(value="")

        # Runtime
        _section(self, "Runtime")
        runtime = self._cfg.get("runtime", {})
        _dropdown(self, "Mode", "mode", str(runtime.get("mode", "paper")), ["paper", "live"], self._vars)
        _num(self, "Loop Interval (s)", "loop_interval", runtime.get("loop_interval_seconds", 5), self._vars)
        _switch(self, "Ignore Market Hours", "ignore_market", bool(runtime.get("ignore_market_hours", False)), self._vars)
        _dropdown(self, "Log Level", "log_level", str(runtime.get("log_level", "INFO")),
                  ["DEBUG", "INFO", "WARNING", "ERROR"], self._vars)

        # Market Hours
        _section(self, "Market Hours")
        market = self._cfg.get("market", {})
        _text(self, "Market Open", "market_open", market.get("open", "09:15:00"), self._vars)
        _text(self, "Market Close", "market_close", market.get("close", "15:30:00"), self._vars)

        # Risk Guard
        _section(self, "Risk Guard")
        risk = self._cfg.get("risk", {})
        _switch(self, "Enable Risk Guard", "risk_enabled", bool(risk.get("enabled", False)), self._vars)
        _num(self, "Max Daily Loss (₹)", "max_loss", risk.get("max_daily_loss", 5000.0), self._vars)
        _num(self, "Max Trades / Session", "max_trades", risk.get("max_trades_per_session", 10), self._vars)

        # Auth
        _section(self, "Auth")
        auth = self._cfg.get("auth", {})
        _switch(self, "Headless Login", "headless", bool(auth.get("headless", True)), self._vars)
        _text(self, "Token Reset Time", "token_reset", auth.get("token_reset_time", "03:30"), self._vars)

        ctk.CTkButton(self, text="Save System Config", width=180, height=34, fg_color="#2563eb",
                       hover_color="#1d4ed8", font=("Segoe UI", 13, "bold"),
                       command=self._save).pack(anchor="e", padx=16, pady=16)
        ctk.CTkLabel(self, textvariable=self._status, font=("Segoe UI", 12), text_color=_GREEN).pack(
            anchor="e", padx=16)

    def update_state(self, state) -> None:
        pass

    def _save(self) -> None:
        v = self._vars
        mode = _sv(v, "mode").lower()
        self._cfg.setdefault("runtime", {})
        self._cfg["runtime"]["mode"] = "live" if mode == "live" else "paper"
        self._cfg["runtime"]["loop_interval_seconds"] = max(1, _iv(v, "loop_interval", 5))
        self._cfg["runtime"]["ignore_market_hours"] = _bv(v, "ignore_market")
        self._cfg["runtime"]["log_level"] = _sv(v, "log_level")
        self._cfg.setdefault("market", {})
        self._cfg["market"]["open"] = _sv(v, "market_open")
        self._cfg["market"]["close"] = _sv(v, "market_close")
        self._cfg.setdefault("risk", {})
        self._cfg["risk"]["enabled"] = _bv(v, "risk_enabled")
        self._cfg["risk"]["max_daily_loss"] = _fv(v, "max_loss", 5000.0)
        self._cfg["risk"]["max_trades_per_session"] = _iv(v, "max_trades", 10)
        self._cfg.setdefault("auth", {})
        self._cfg["auth"]["headless"] = _bv(v, "headless")
        self._cfg["auth"]["token_reset_time"] = _sv(v, "token_reset")
        _save(self._path, self._cfg)
        self._status.set("Saved ✓")


# ── widget helpers ────────────────────────────────────────────────────────────

def _section(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, font=("Segoe UI", 16, "bold"),
                 text_color="#e2e8f0").pack(anchor="w", padx=16, pady=(18, 8))


def _row(parent) -> ctk.CTkFrame:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=4)
    return row


def _text(parent, label, key, default, store) -> None:
    row = _row(parent)
    ctk.CTkLabel(row, text=label, width=200, anchor="w", font=("Segoe UI", 13), text_color=_FG).pack(side="left")
    var = ctk.StringVar(value=str(default))
    store[key] = var
    ctk.CTkEntry(row, textvariable=var, width=200, fg_color=_INPUT_BG, text_color=_FG,
                  border_color=_INPUT_BORDER, height=32).pack(side="left", padx=8)


def _num(parent, label, key, default, store) -> None:
    _text(parent, label, key, default, store)


def _switch(parent, label, key, default, store) -> None:
    row = _row(parent)
    ctk.CTkLabel(row, text=label, width=200, anchor="w", font=("Segoe UI", 13), text_color=_FG).pack(side="left")
    var = ctk.BooleanVar(value=default)
    store[key] = var
    ctk.CTkSwitch(row, text="", variable=var, progress_color="#2563eb").pack(side="left", padx=8)


def _dropdown(parent, label, key, default, values, store) -> None:
    row = _row(parent)
    ctk.CTkLabel(row, text=label, width=200, anchor="w", font=("Segoe UI", 13), text_color=_FG).pack(side="left")
    var = ctk.StringVar(value=default)
    store[key] = var
    ctk.CTkOptionMenu(row, values=values, variable=var, width=200,
                       fg_color=_INPUT_BG, button_color="#3d4870",
                       dropdown_fg_color="#1e2130", text_color=_FG).pack(side="left", padx=8)


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
