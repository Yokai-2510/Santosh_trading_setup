"""
signal_panel — real-time indicator status table (current value vs threshold).
"""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from modules.state.runtime_state import SignalSnapshot

_BG2 = "#252a3d"
_FG = "#c9d1e0"
_GREEN = "#22c55e"
_RED = "#ef4444"
_MUTED = "#6b7280"
_HDR_BG = "#1a1f32"

_LABELS = {
    "rsi": "RSI",
    "volume_vs_ema": "Volume vs EMA",
    "adx": "ADX",
}


class SignalPanel(ctk.CTkFrame):
    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, corner_radius=10, fg_color=_BG2, **kwargs)

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(title_row, text="Entry Signal", font=("Segoe UI", 15, "bold"),
                     text_color="#e2e8f0").pack(side="left")
        self._overall = ctk.CTkLabel(title_row, text="", font=("Segoe UI", 12, "bold"), text_color=_MUTED)
        self._overall.pack(side="right")

        hdr = ctk.CTkFrame(self, fg_color=_HDR_BG, corner_radius=0)
        hdr.pack(fill="x", padx=14, pady=(0, 2))
        for txt, w, anchor in [("Indicator", 150, "w"), ("Value", 90, "e"),
                                ("Threshold", 110, "e"), ("", 28, "center")]:
            ctk.CTkLabel(hdr, text=txt, width=w, font=("Segoe UI", 11),
                         anchor=anchor, text_color=_MUTED).pack(side="left", padx=4, pady=3)

        self._rows: dict[str, dict] = {}
        self._rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rows_frame.pack(fill="x", padx=14, pady=(0, 12))

    def update_state(self, signal: Optional[SignalSnapshot]) -> None:
        if not signal or not signal.checks:
            self._overall.configure(text="No data", text_color=_MUTED)
            return

        self._overall.configure(
            text="ENTRY" if signal.ok else "NO ENTRY",
            text_color=_GREEN if signal.ok else _RED,
        )

        for key, passed in signal.checks.items():
            display_val = _fmt_value(key, signal.values.get(key), signal.values)
            threshold = signal.thresholds.get(key, "")
            if key not in self._rows:
                self._rows[key] = self._make_row(key)
            row = self._rows[key]
            row["val_lbl"].configure(text=display_val)
            row["thr_lbl"].configure(text=threshold)
            row["dot_lbl"].configure(text="●", text_color=_GREEN if passed else _RED)

    def _make_row(self, key: str) -> dict:
        frame = ctk.CTkFrame(self._rows_frame, fg_color="transparent")
        frame.pack(fill="x", pady=1)
        label = _LABELS.get(key, key.replace("_", " ").title())
        ctk.CTkLabel(frame, text=label, width=150, anchor="w",
                     font=("Segoe UI", 13), text_color=_FG).pack(side="left", padx=4)
        val_lbl = ctk.CTkLabel(frame, text="--", width=90, anchor="e",
                               font=("Consolas", 13), text_color="#94a3b8")
        val_lbl.pack(side="left", padx=4)
        thr_lbl = ctk.CTkLabel(frame, text="--", width=110, anchor="e",
                               font=("Segoe UI", 12), text_color=_MUTED)
        thr_lbl.pack(side="left", padx=4)
        dot_lbl = ctk.CTkLabel(frame, text="●", width=28, anchor="center",
                               font=("Segoe UI", 14), text_color=_MUTED)
        dot_lbl.pack(side="left", padx=4)
        return {"val_lbl": val_lbl, "thr_lbl": thr_lbl, "dot_lbl": dot_lbl}


def _fmt_value(key: str, value, all_values: dict) -> str:
    if key == "volume_vs_ema":
        vol = all_values.get("volume", 0)
        ema = all_values.get("volume_ema", 0)
        if ema and ema > 0:
            return f"{vol / ema:.2f}x"
        return "--"
    if value is None:
        return "--"
    return f"{value:.2f}" if isinstance(value, float) else str(value)
