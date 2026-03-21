"""
connections_view — WebSocket, API, and broker connection status.
"""

from __future__ import annotations

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from theme import colors as C, fonts as F
from utils.state import RuntimeState


class ConnectionsView(ctk.CTkScrollableFrame):
    def __init__(self, parent, bridge: BotBridge, **kwargs) -> None:
        super().__init__(parent, fg_color=C.BG_SECONDARY,
                         scrollbar_button_color=C.BG_CARD,
                         scrollbar_button_hover_color=C.BORDER_INPUT, **kwargs)
        self.bridge = bridge

        ctk.CTkLabel(self, text="Connections", font=F.HEADING,
                     text_color=C.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(16, 12))

        # Broker API
        self._broker_card = _ConnCard(self, "Broker API (Upstox)")
        self._broker_card.pack(fill="x", padx=16, pady=(0, 8))

        # WebSocket
        self._ws_card = _ConnCard(self, "WebSocket Market Feed")
        self._ws_card.pack(fill="x", padx=16, pady=(0, 8))

        # Data Services
        self._data_card = _ConnCard(self, "Data Services")
        self._data_card.pack(fill="x", padx=16, pady=(0, 16))

    def update_state(self, state: RuntimeState) -> None:
        # Broker
        self._broker_card.set_status(
            connected=state.auth_ok,
            details=[
                ("Auth", "Connected" if state.auth_ok else "Disconnected"),
                ("Message", state.auth_message or "--"),
            ],
        )

        # WebSocket
        health = self.bridge.service_health()
        ws_alive = False
        if state.bot_running:
            ws_alive = True  # approximation — WS is started with engine
        self._ws_card.set_status(
            connected=ws_alive,
            details=[
                ("Feed", "Active" if ws_alive else "Inactive"),
                ("Bot", "Running" if state.bot_running else "Stopped"),
            ],
        )

        # Data
        self._data_card.set_status(
            connected=state.bot_running,
            details=[
                ("Candle Service", "Ready" if state.bot_running else "Idle"),
                ("Cycle Count", str(state.cycle_count)),
            ],
        )


class _ConnCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, **kw):
        super().__init__(parent, corner_radius=10, fg_color=C.BG_CARD, **kw)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(hdr, text=title, font=F.BODY_BOLD,
                     text_color=C.TEXT_PRIMARY).pack(side="left")
        self._dot = ctk.CTkLabel(hdr, text="\u25cf", font=F.BODY,
                                  text_color=C.TEXT_MUTED)
        self._dot.pack(side="right")

        self._details_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._details_frame.pack(fill="x", padx=14, pady=(0, 10))
        self._detail_labels: list = []

    def set_status(self, connected: bool, details: list) -> None:
        self._dot.configure(text_color=C.GREEN if connected else C.RED)

        if len(details) != len(self._detail_labels):
            for w in self._details_frame.winfo_children():
                w.destroy()
            self._detail_labels = []
            for label, value in details:
                row = ctk.CTkFrame(self._details_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                lbl = ctk.CTkLabel(row, text=label + ":", width=140, anchor="w",
                                   font=F.SMALL, text_color=C.TEXT_MUTED)
                lbl.pack(side="left")
                val = ctk.CTkLabel(row, text=value, font=F.SMALL,
                                   text_color=C.TEXT_SECONDARY)
                val.pack(side="left")
                self._detail_labels.append((lbl, val))
        else:
            for (lbl_w, val_w), (label, value) in zip(self._detail_labels, details):
                val_w.configure(text=value)
