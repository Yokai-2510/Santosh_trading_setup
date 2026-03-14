"""
position_card — active position or working order with inline modify controls.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from modules.state.runtime_state import PositionSnapshot, WorkingOrderSnapshot

_BG2 = "#252a3d"
_FG = "#c9d1e0"
_GREEN = "#22c55e"
_RED = "#ef4444"
_AMBER = "#f59e0b"
_MUTED = "#6b7280"
_INPUT_BG = "#1a1f32"
_INPUT_BORDER = "#3d4870"


class PositionCard(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_manual_exit: Optional[Callable] = None,
        on_cancel_order: Optional[Callable] = None,
        on_modify_price: Optional[Callable[..., None]] = None,
        on_set_sl: Optional[Callable[..., None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, corner_radius=10, fg_color=_BG2, **kwargs)
        self._on_manual_exit = on_manual_exit
        self._on_cancel_order = on_cancel_order
        self._on_modify_price = on_modify_price
        self._on_set_sl = on_set_sl

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", padx=14, pady=(12, 6))
        self._title = ctk.CTkLabel(title_row, text="Position", font=("Segoe UI", 15, "bold"), text_color="#e2e8f0")
        self._title.pack(side="left")
        self._badge = ctk.CTkLabel(title_row, text="", font=("Segoe UI", 11, "bold"), text_color=_MUTED)
        self._badge.pack(side="right")

        self._info = ctk.CTkLabel(self, text="No active position", font=("Segoe UI", 13),
                                   text_color=_MUTED, justify="left")
        self._info.pack(anchor="w", padx=14, pady=(0, 6))

        # Controls (packed dynamically)
        self._pos_controls = self._build_position_controls()
        self._ord_controls = self._build_order_controls()

        ctk.CTkFrame(self, fg_color="transparent", height=6).pack()

    def _build_position_controls(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text="Override SL %:", font=("Segoe UI", 12), text_color=_MUTED, width=110).pack(side="left")
        self._sl_var = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self._sl_var, width=72, fg_color=_INPUT_BG, text_color=_FG,
                      border_color=_INPUT_BORDER, height=28).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Apply SL", width=82, height=28, fg_color=_AMBER, hover_color="#d97706",
                       text_color="#111827", font=("Segoe UI", 12, "bold"),
                       command=self._apply_sl).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Exit Now", width=82, height=28, fg_color=_RED, hover_color="#b91c1c",
                       font=("Segoe UI", 12, "bold"), command=self._manual_exit).pack(side="left", padx=6)
        return frame

    def _build_order_controls(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text="New Price:", font=("Segoe UI", 12), text_color=_MUTED, width=80).pack(side="left")
        self._price_var = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self._price_var, width=72, fg_color=_INPUT_BG, text_color=_FG,
                      border_color=_INPUT_BORDER, height=28).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Modify", width=70, height=28, fg_color=_AMBER, hover_color="#d97706",
                       text_color="#111827", font=("Segoe UI", 12, "bold"),
                       command=self._modify_price).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Cancel Order", width=100, height=28, fg_color=_RED, hover_color="#b91c1c",
                       font=("Segoe UI", 12, "bold"), command=self._cancel_order).pack(side="left", padx=6)
        return frame

    def update_state(
        self,
        position: Optional[PositionSnapshot],
        working_order: Optional[WorkingOrderSnapshot],
    ) -> None:
        self._pos_controls.pack_forget()
        self._ord_controls.pack_forget()

        if position:
            pnl = position.unrealised_pnl
            sign = "+" if pnl >= 0 else ""
            self._info.configure(
                text=(f"{position.trading_symbol}\n"
                      f"Qty: {position.quantity}   Entry: {position.entry_price:.2f}   LTP: {position.current_ltp:.2f}\n"
                      f"P&L: {sign}{pnl:.2f}   Peak: {position.peak_ltp:.2f}"),
                text_color=_GREEN if pnl >= 0 else _RED,
            )
            self._title.configure(text="Active Position")
            self._badge.configure(text="ACTIVE", text_color=_GREEN)
            self._pos_controls.pack(fill="x", pady=(0, 4))

        elif working_order:
            self._info.configure(
                text=(f"{working_order.trading_symbol}\n"
                      f"Order: {working_order.order_id[:18]}   Price: {working_order.price:.2f}\n"
                      f"Qty: {working_order.quantity}   Status: {working_order.status}"),
                text_color=_AMBER,
            )
            self._title.configure(text="Working Order")
            self._badge.configure(text="PENDING", text_color=_AMBER)
            self._ord_controls.pack(fill="x", pady=(0, 4))

        else:
            self._info.configure(text="No active position", text_color=_MUTED)
            self._title.configure(text="Position")
            self._badge.configure(text="")

    def _manual_exit(self) -> None:
        if self._on_manual_exit:
            self._on_manual_exit()

    def _cancel_order(self) -> None:
        if self._on_cancel_order:
            self._on_cancel_order()

    def _modify_price(self) -> None:
        try:
            price = float(self._price_var.get())
            if self._on_modify_price:
                self._on_modify_price(price)
        except ValueError:
            pass

    def _apply_sl(self) -> None:
        try:
            sl = float(self._sl_var.get())
            if 0 < sl <= 100 and self._on_set_sl:
                self._on_set_sl(sl)
        except ValueError:
            pass
