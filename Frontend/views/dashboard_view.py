"""
dashboard_view — live positions, signals, stats, and bot controls. Dark themed.
"""

from __future__ import annotations

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from theme import colors as C, fonts as F
from utils.state import RuntimeState
from widgets.position_card import PositionCard
from widgets.signal_panel import SignalPanel
from widgets.stat_card import StatCard

# Aliases for backward compat within this file
_BG = C.BG_SECONDARY
_BG2 = C.BG_CARD
_FG = C.TEXT_PRIMARY
_GREEN = C.GREEN
_RED = C.RED
_AMBER = C.AMBER
_MUTED = C.TEXT_MUTED
_CARD_BG = C.BG_CARD


def _btn(parent, text, fg, hover, cmd, **kw):
    return ctk.CTkButton(parent, text=text, fg_color=fg, hover_color=hover,
                          font=("Segoe UI", 13, "bold"), command=cmd, **kw)


class DashboardView(ctk.CTkScrollableFrame):
    def __init__(self, parent, bridge: BotBridge, **kwargs) -> None:
        super().__init__(parent, fg_color=_BG, scrollbar_button_color=_BG2,
                         scrollbar_button_hover_color="#3d4870", **kwargs)
        self.bridge = bridge

        # ── Bot Controls Card ─────────────────────────────────────
        ctrl_card = ctk.CTkFrame(self, fg_color=_CARD_BG, corner_radius=10)
        ctrl_card.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(ctrl_card, text="Controls", font=("Segoe UI", 13, "bold"),
                     text_color=_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))

        self._start_btn = _btn(btn_row, "▶  Start", "#16a34a", "#15803d",
                                self._start_bot, width=110, height=34)
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = _btn(btn_row, "■  Stop", _RED, "#b91c1c",
                               self._stop_bot, width=110, height=34)
        self._stop_btn.pack(side="left", padx=(0, 8))

        # Pause/Resume — permanent visual accent
        self._pause_btn = _btn(btn_row, "⏸  Pause", "#374151", "#4b5563",
                                self._toggle_pause, width=130, height=34)
        self._pause_btn.pack(side="left", padx=(0, 8))

        _btn(btn_row, "↻  Login", "#2563eb", "#1d4ed8",
              self._force_login, width=110, height=34).pack(side="left", padx=(0, 8))

        _btn(btn_row, "→  Run Once", "#7c3aed", "#6d28d9",
              self._run_once, width=120, height=34).pack(side="left")

        # ── Stats Row ─────────────────────────────────────────────
        stats_row = ctk.CTkFrame(self, fg_color="transparent")
        stats_row.pack(fill="x", padx=16, pady=(0, 8))

        self._pnl_card = StatCard(stats_row, "Session P&L")
        self._pnl_card.pack(side="left", padx=(0, 8))

        self._trades_card = StatCard(stats_row, "Trades")
        self._trades_card.pack(side="left", padx=(0, 8))

        self._cycles_card = StatCard(stats_row, "Cycles")
        self._cycles_card.pack(side="left", padx=(0, 8))

        self._auth_card = StatCard(stats_row, "Auth")
        self._auth_card.pack(side="left", padx=(0, 8))

        # ── Position Card ─────────────────────────────────────────
        self._position_card = PositionCard(
            self,
            on_manual_exit=self.bridge.manual_exit_position,
            on_cancel_order=self.bridge.cancel_working_order,
            on_modify_price=self.bridge.modify_working_order_price,
            on_set_sl=self.bridge.set_position_sl,
        )
        self._position_card.pack(fill="x", padx=16, pady=(0, 8))

        # ── Entry Signal Card ──────────────────────────────────────
        self._signal_panel = SignalPanel(self)
        self._signal_panel.pack(fill="x", padx=16, pady=(0, 8))

        # ── Error Banner ──────────────────────────────────────────
        self._error_lbl = ctk.CTkLabel(self, text="", font=("Segoe UI", 12),
                                        text_color=_RED, wraplength=700, justify="left")
        self._error_lbl.pack(anchor="w", padx=16, pady=(0, 8))

        self._paused = False

    def update_state(self, state: RuntimeState) -> None:
        running = state.bot_running
        paused = state.trading_paused

        self._start_btn.configure(state="disabled" if running else "normal")
        self._stop_btn.configure(state="normal" if running else "disabled")
        self._pause_btn.configure(state="normal" if running else "disabled")

        # Pause button — permanent accent when paused
        if paused:
            self._pause_btn.configure(text="▶  Resume", fg_color=_AMBER, hover_color="#d97706",
                                       text_color="#111827")
        else:
            self._pause_btn.configure(text="⏸  Pause", fg_color="#374151", hover_color="#4b5563",
                                       text_color=_FG)

        self._position_card.update_state(state.active_position, state.working_order)
        self._signal_panel.update_state(state.last_signal)

        pnl = state.session_realised_pnl
        self._pnl_card.set_value(f"{'+' if pnl >= 0 else ''}{pnl:.0f}",
                                  color=_GREEN if pnl >= 0 else _RED)
        self._trades_card.set_value(str(state.session_trade_count))
        self._cycles_card.set_value(str(state.cycle_count))
        self._auth_card.set_value("OK" if state.auth_ok else "No", color=_GREEN if state.auth_ok else _RED)

        self._error_lbl.configure(text=state.error_message or "")

    def _start_bot(self) -> None:
        self.bridge.start_bot()

    def _stop_bot(self) -> None:
        self.bridge.stop_bot()

    def _toggle_pause(self) -> None:
        state = self.bridge.get_state()
        if state.trading_paused:
            self.bridge.resume_trading()
        else:
            self.bridge.pause_trading()

    def _force_login(self) -> None:
        self.bridge.force_login()

    def _run_once(self) -> None:
        self.bridge.run_once()
