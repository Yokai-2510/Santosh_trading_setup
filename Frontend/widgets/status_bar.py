"""
status_bar — bottom bar: bot state, mode, market, last update.
"""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from utils.state import RuntimeState

_BAR_BG = "#13151f"
_MUTED = "#6b7280"
_GREEN = "#22c55e"
_RED = "#ef4444"
_AMBER = "#f59e0b"


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, corner_radius=0, fg_color=_BAR_BG, height=30, **kwargs)
        self.pack_propagate(False)

        self._bot_lbl = ctk.CTkLabel(self, text="Bot: Stopped", font=("Segoe UI", 11), text_color=_MUTED)
        self._bot_lbl.pack(side="left", padx=14)
        ctk.CTkLabel(self, text="|", font=("Segoe UI", 11), text_color="#2a2f45").pack(side="left")
        self._market_lbl = ctk.CTkLabel(self, text="Market: --", font=("Segoe UI", 11), text_color=_MUTED)
        self._market_lbl.pack(side="left", padx=14)
        ctk.CTkLabel(self, text="|", font=("Segoe UI", 11), text_color="#2a2f45").pack(side="left")
        self._pause_lbl = ctk.CTkLabel(self, text="", font=("Segoe UI", 11), text_color=_MUTED)
        self._pause_lbl.pack(side="left", padx=14)

        self._mode_lbl = ctk.CTkLabel(self, text="", font=("Segoe UI", 11, "bold"), text_color=_MUTED)
        self._mode_lbl.pack(side="right", padx=14)
        self._update_lbl = ctk.CTkLabel(self, text="", font=("Segoe UI", 11), text_color="#4b5563")
        self._update_lbl.pack(side="right", padx=8)

    def update_state(self, state: RuntimeState, mode: str = "paper") -> None:
        self._bot_lbl.configure(
            text="Bot: Running" if state.bot_running else "Bot: Stopped",
            text_color=_GREEN if state.bot_running else _RED,
        )
        self._market_lbl.configure(
            text="Market: Open" if state.market_active else "Market: Closed",
            text_color=_GREEN if state.market_active else _AMBER,
        )
        if state.bot_running:
            self._pause_lbl.configure(
                text="⏸ Paused" if state.trading_paused else "▶ Trading",
                text_color=_AMBER if state.trading_paused else _GREEN,
            )
        else:
            self._pause_lbl.configure(text="")

        self._mode_lbl.configure(
            text=f"MODE: {mode.upper()}",
            text_color=_RED if mode == "live" else "#7c3aed",
        )
        if state.last_cycle_epoch > 0:
            self._update_lbl.configure(
                text=f"cycle {datetime.fromtimestamp(state.last_cycle_epoch).strftime('%H:%M:%S')}"
            )
