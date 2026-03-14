"""
orders_view — session trade history table.
"""

from __future__ import annotations

import customtkinter as ctk

from modules.state.runtime_state import RuntimeState


class OrdersView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, fg_color="transparent", **kwargs)

        ctk.CTkLabel(self, text="Trade History", font=("Segoe UI", 18, "bold"), text_color="#1b3056").pack(
            anchor="w", padx=16, pady=(12, 8)
        )

        # Header
        header = ctk.CTkFrame(self, fg_color="#e2e8f0", corner_radius=0)
        header.pack(fill="x", padx=16)
        cols = ["Time", "Symbol", "Qty", "Entry", "Exit", "P&L", "Reason"]
        widths = [70, 180, 60, 80, 80, 90, 140]
        for col, w in zip(cols, widths):
            ctk.CTkLabel(header, text=col, width=w, font=("Segoe UI", 12, "bold"),
                         text_color="#334155", anchor="w").pack(side="left", padx=4, pady=4)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="#ffffff")
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._row_count = 0

    def update_state(self, state: RuntimeState) -> None:
        trades = state.trade_history
        if len(trades) == self._row_count:
            return

        # Clear and rebuild
        for widget in self._scroll.winfo_children():
            widget.destroy()

        for trade in reversed(trades):
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            pnl_color = "#16a34a" if trade.pnl >= 0 else "#dc2626"
            values = [
                trade.exit_time or trade.entry_time,
                trade.symbol,
                str(trade.quantity),
                f"{trade.entry_price:.2f}",
                f"{trade.exit_price:.2f}" if trade.exit_price else "--",
                f"{trade.pnl:+.2f}",
                trade.exit_reason,
            ]
            widths = [70, 180, 60, 80, 80, 90, 140]
            for val, w in zip(values, widths):
                color = pnl_color if val == values[5] else "#334155"
                ctk.CTkLabel(row, text=val, width=w, font=("Segoe UI", 12),
                             text_color=color, anchor="w").pack(side="left", padx=4)

        self._row_count = len(trades)
