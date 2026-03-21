"""
status_view — system health, service status, and connection info.
"""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from theme import colors as C, fonts as F
from utils.state import RuntimeState


class StatusView(ctk.CTkScrollableFrame):
    def __init__(self, parent, bridge: BotBridge, **kwargs) -> None:
        super().__init__(parent, fg_color=C.BG_SECONDARY,
                         scrollbar_button_color=C.BG_CARD,
                         scrollbar_button_hover_color=C.BORDER_INPUT, **kwargs)
        self.bridge = bridge

        ctk.CTkLabel(self, text="System Status", font=F.HEADING,
                     text_color=C.TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(16, 12))

        # Bot status card
        self._bot_card = _StatusCard(self, "Bot Engine")
        self._bot_card.pack(fill="x", padx=16, pady=(0, 8))

        # Auth card
        self._auth_card = _StatusCard(self, "Authentication")
        self._auth_card.pack(fill="x", padx=16, pady=(0, 8))

        # Market card
        self._market_card = _StatusCard(self, "Market")
        self._market_card.pack(fill="x", padx=16, pady=(0, 8))

        # Services card
        self._services_card = _StatusCard(self, "Background Services")
        self._services_card.pack(fill="x", padx=16, pady=(0, 8))

        # Runtime info
        self._runtime_card = _StatusCard(self, "Runtime")
        self._runtime_card.pack(fill="x", padx=16, pady=(0, 16))

    def update_state(self, state: RuntimeState) -> None:
        # Bot
        bot_items = [
            ("Status", "Running" if state.bot_running else "Stopped",
             C.GREEN if state.bot_running else C.RED),
            ("Trading", "Paused" if state.trading_paused else "Active",
             C.AMBER if state.trading_paused else C.GREEN),
            ("Cycles", str(state.cycle_count), C.TEXT_SECONDARY),
        ]
        if state.last_cycle_epoch > 0:
            bot_items.append(("Last Cycle",
                             datetime.fromtimestamp(state.last_cycle_epoch).strftime("%H:%M:%S"),
                             C.TEXT_SECONDARY))
        if state.error_message:
            bot_items.append(("Error", state.error_message[:80], C.RED))
        self._bot_card.set_items(bot_items)

        # Auth
        self._auth_card.set_items([
            ("Status", "Authenticated" if state.auth_ok else "Not authenticated",
             C.GREEN if state.auth_ok else C.RED),
            ("Message", state.auth_message or "--", C.TEXT_SECONDARY),
        ])

        # Market
        self._market_card.set_items([
            ("Status", "Open" if state.market_active else "Closed",
             C.GREEN if state.market_active else C.AMBER),
        ])

        # Services
        health = self.bridge.service_health()
        if health:
            svc_items = []
            for name, info in health.items():
                alive = info.get("alive", False)
                svc_items.append((
                    name,
                    f"Running ({info.get('run_count', 0)} ticks)" if alive else "Stopped",
                    C.GREEN if alive else C.TEXT_MUTED,
                ))
                if info.get("last_error"):
                    svc_items.append(("  Error", info["last_error"][:60], C.RED))
            self._services_card.set_items(svc_items)
        else:
            self._services_card.set_items([
                ("Status", "No services registered", C.TEXT_MUTED),
            ])

        # Runtime
        mode = self.bridge.get_runtime_mode()
        pos_status = "IDLE"
        if state.active_position:
            pos_status = state.active_position.status
        elif state.working_order:
            pos_status = "PENDING_ENTRY"
        self._runtime_card.set_items([
            ("Mode", mode.upper(), C.RED if mode == "live" else C.ACCENT_PURPLE),
            ("Position", pos_status, C.TEXT_SECONDARY),
            ("Session P&L", f"{state.session_realised_pnl:+.2f}",
             C.GREEN if state.session_realised_pnl >= 0 else C.RED),
            ("Session Trades", str(state.session_trade_count), C.TEXT_SECONDARY),
        ])


class _StatusCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, **kw):
        super().__init__(parent, corner_radius=10, fg_color=C.BG_CARD, **kw)
        ctk.CTkLabel(self, text=title, font=F.BODY_BOLD,
                     text_color=C.TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 6))
        self._items_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._items_frame.pack(fill="x", padx=14, pady=(0, 10))
        self._rows: list = []

    def set_items(self, items: list) -> None:
        # Rebuild if row count changed
        if len(items) != len(self._rows):
            for w in self._items_frame.winfo_children():
                w.destroy()
            self._rows = []
            for label, value, color in items:
                row = ctk.CTkFrame(self._items_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                lbl = ctk.CTkLabel(row, text=label + ":", width=160, anchor="w",
                                   font=F.SMALL, text_color=C.TEXT_MUTED)
                lbl.pack(side="left")
                val = ctk.CTkLabel(row, text=value, font=F.BODY_BOLD, text_color=color)
                val.pack(side="left")
                self._rows.append((lbl, val))
        else:
            for (lbl_w, val_w), (label, value, color) in zip(self._rows, items):
                lbl_w.configure(text=label + ":")
                val_w.configure(text=value, text_color=color)
