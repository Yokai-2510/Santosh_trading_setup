"""
trades_view — Open Positions tab + Closed Trades history tab.
"""

from __future__ import annotations

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from utils.state import RuntimeState

_BG = "#1e2130"
_BG2 = "#252a3d"
_FG = "#c9d1e0"
_GREEN = "#22c55e"
_RED = "#ef4444"
_AMBER = "#f59e0b"
_MUTED = "#6b7280"
_INPUT_BG = "#1a1f32"
_INPUT_BORDER = "#3d4870"


class TradesView(ctk.CTkFrame):
    def __init__(self, parent, bridge: BotBridge, **kwargs) -> None:
        super().__init__(parent, fg_color=_BG, **kwargs)
        self.bridge = bridge

        tabs = ctk.CTkTabview(self, fg_color=_BG2,
                               segmented_button_fg_color="#1a1f32",
                               segmented_button_selected_color="#2563eb",
                               segmented_button_selected_hover_color="#1d4ed8",
                               segmented_button_unselected_color="#1a1f32",
                               segmented_button_unselected_hover_color=_BG2,
                               text_color=_FG)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        tabs.add("Open Position")
        tabs.add("Closed Trades")

        self._build_open(tabs.tab("Open Position"))
        self._build_closed(tabs.tab("Closed Trades"))
        self._closed_count = 0

    # ── Open Position tab ─────────────────────────────────────────────────────

    def _build_open(self, parent) -> None:
        self._open_frame = ctk.CTkScrollableFrame(parent, fg_color=_BG, scrollbar_button_color=_BG2)
        self._open_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self._open_content = ctk.CTkFrame(self._open_frame, fg_color="transparent")
        self._open_content.pack(fill="both", expand=True)
        self._open_info = ctk.CTkLabel(
            self._open_content, text="No open position",
            font=("Segoe UI", 15), text_color=_MUTED,
        )
        self._open_info.pack(pady=40)
        self._open_controls = None

    def _render_open_position(self, pos, wo) -> None:
        for w in self._open_content.winfo_children():
            w.destroy()
        self._open_controls = None

        if pos:
            pnl = pos.unrealised_pnl
            sign = "+" if pnl >= 0 else ""
            card = ctk.CTkFrame(self._open_content, fg_color=_BG2, corner_radius=10)
            card.pack(fill="x", padx=16, pady=16)

            _kv(card, "Symbol", pos.trading_symbol)
            _kv(card, "Quantity", str(pos.quantity))
            _kv(card, "Entry Price", f"{pos.entry_price:.2f}")
            _kv(card, "LTP", f"{pos.current_ltp:.2f}")
            _kv(card, "Unrealised P&L", f"{sign}{pnl:.2f}",
                color=_GREEN if pnl >= 0 else _RED)
            _kv(card, "Peak LTP", f"{pos.peak_ltp:.2f}")

            ctk.CTkFrame(card, fg_color="#2a2f45", height=1).pack(fill="x", padx=14, pady=8)

            # Controls
            ctrl = ctk.CTkFrame(card, fg_color="transparent")
            ctrl.pack(fill="x", padx=14, pady=(0, 14))

            sl_row = ctk.CTkFrame(ctrl, fg_color="transparent")
            sl_row.pack(fill="x", pady=4)
            ctk.CTkLabel(sl_row, text="Override SL %:", font=("Segoe UI", 12), text_color=_MUTED, width=120).pack(side="left")
            self._open_sl_var = ctk.StringVar()
            ctk.CTkEntry(sl_row, textvariable=self._open_sl_var, width=80, fg_color=_INPUT_BG,
                          text_color=_FG, border_color=_INPUT_BORDER, height=28).pack(side="left", padx=6)
            ctk.CTkButton(sl_row, text="Apply SL", width=80, height=28, fg_color=_AMBER,
                           hover_color="#d97706", text_color="#111827",
                           font=("Segoe UI", 12, "bold"), command=self._apply_sl).pack(side="left", padx=4)
            ctk.CTkButton(sl_row, text="Exit Now", width=80, height=28, fg_color=_RED,
                           hover_color="#b91c1c", font=("Segoe UI", 12, "bold"),
                           command=self.bridge.manual_exit_position).pack(side="left", padx=8)

        elif wo:
            card = ctk.CTkFrame(self._open_content, fg_color=_BG2, corner_radius=10)
            card.pack(fill="x", padx=16, pady=16)

            _kv(card, "Symbol", wo.trading_symbol)
            _kv(card, "Order ID", wo.order_id[:20])
            _kv(card, "Price", f"{wo.price:.2f}")
            _kv(card, "Quantity", str(wo.quantity))
            _kv(card, "Status", wo.status, color=_AMBER)

            ctk.CTkFrame(card, fg_color="#2a2f45", height=1).pack(fill="x", padx=14, pady=8)

            ctrl = ctk.CTkFrame(card, fg_color="transparent")
            ctrl.pack(fill="x", padx=14, pady=(0, 14))

            price_row = ctk.CTkFrame(ctrl, fg_color="transparent")
            price_row.pack(fill="x", pady=4)
            ctk.CTkLabel(price_row, text="New Price:", font=("Segoe UI", 12), text_color=_MUTED, width=90).pack(side="left")
            self._open_price_var = ctk.StringVar()
            ctk.CTkEntry(price_row, textvariable=self._open_price_var, width=80, fg_color=_INPUT_BG,
                          text_color=_FG, border_color=_INPUT_BORDER, height=28).pack(side="left", padx=6)
            ctk.CTkButton(price_row, text="Modify", width=70, height=28, fg_color=_AMBER,
                           hover_color="#d97706", text_color="#111827",
                           font=("Segoe UI", 12, "bold"), command=self._modify_price).pack(side="left", padx=4)
            ctk.CTkButton(price_row, text="Cancel Order", width=100, height=28, fg_color=_RED,
                           hover_color="#b91c1c", font=("Segoe UI", 12, "bold"),
                           command=self.bridge.cancel_working_order).pack(side="left", padx=6)

        else:
            ctk.CTkLabel(self._open_content, text="No open position",
                         font=("Segoe UI", 15), text_color=_MUTED).pack(pady=40)

    def _apply_sl(self) -> None:
        try:
            sl = float(self._open_sl_var.get())
            if 0 < sl <= 100:
                self.bridge.set_position_sl(sl)
        except (ValueError, AttributeError):
            pass

    def _modify_price(self) -> None:
        try:
            price = float(self._open_price_var.get())
            self.bridge.modify_working_order_price(price)
        except (ValueError, AttributeError):
            pass

    # ── Closed Trades tab ─────────────────────────────────────────────────────

    def _build_closed(self, parent) -> None:
        # Header row
        hdr = ctk.CTkFrame(parent, fg_color="#1a1f32", corner_radius=0)
        hdr.pack(fill="x", padx=8, pady=(8, 2))
        for col, w in [("Time", 70), ("Symbol", 180), ("Qty", 55),
                        ("Entry", 80), ("Exit", 80), ("P&L", 90), ("Reason", 140)]:
            ctk.CTkLabel(hdr, text=col, width=w, font=("Segoe UI", 11, "bold"),
                         text_color=_MUTED, anchor="w").pack(side="left", padx=4, pady=4)

        self._closed_scroll = ctk.CTkScrollableFrame(parent, fg_color=_BG,
                                                      scrollbar_button_color=_BG2)
        self._closed_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def update_state(self, state: RuntimeState) -> None:
        self._render_open_position(state.active_position, state.working_order)
        self._refresh_closed(state)

    def _refresh_closed(self, state: RuntimeState) -> None:
        trades = state.trade_history
        if len(trades) == self._closed_count:
            return
        for w in self._closed_scroll.winfo_children():
            w.destroy()
        for trade in reversed(trades):
            row = ctk.CTkFrame(self._closed_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            pnl_color = _GREEN if trade.pnl >= 0 else _RED
            for val, w in [
                (trade.exit_time or trade.entry_time, 70),
                (trade.symbol, 180),
                (str(trade.quantity), 55),
                (f"{trade.entry_price:.2f}", 80),
                (f"{trade.exit_price:.2f}" if trade.exit_price else "--", 80),
                (f"{trade.pnl:+.2f}", 90),
                (trade.exit_reason, 140),
            ]:
                color = pnl_color if val == f"{trade.pnl:+.2f}" else _FG
                ctk.CTkLabel(row, text=val, width=w, font=("Segoe UI", 12),
                             text_color=color, anchor="w").pack(side="left", padx=4)
        self._closed_count = len(trades)


def _kv(parent, label: str, value: str, color: str = _FG) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=14, pady=2)
    ctk.CTkLabel(row, text=label + ":", width=130, anchor="w",
                 font=("Segoe UI", 12), text_color=_MUTED).pack(side="left")
    ctk.CTkLabel(row, text=value, font=("Segoe UI", 13, "bold"), text_color=color).pack(side="left")
