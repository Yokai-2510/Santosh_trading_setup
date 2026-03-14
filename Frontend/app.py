"""
app — dark-themed CTK window with sidebar navigation and 1s live refresh.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from views.credentials_view import CredentialsView
from views.dashboard_view import DashboardView
from views.logs_view import LogsView
from views.strategy_view import StrategyView
from views.system_view import SystemView
from views.trades_view import TradesView
from widgets.status_bar import StatusBar

FRONTEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FRONTEND_DIR.parent
SOURCE_DIR = PROJECT_ROOT / "Backend" / "source"

_REFRESH_MS = 1000
_SIDEBAR_W = 170

# Dark palette
_SIDEBAR_BG = "#13151f"
_CONTENT_BG = "#1e2130"
_HEADER_BG = "#13151f"
_FG = "#c9d1e0"
_MUTED = "#6b7280"
_ACTIVE_FG = "#2563eb"
_ACTIVE_HOVER = "#1d4ed8"
_NAV_FG = "transparent"
_NAV_HOVER = "#1e2642"
_NAV_TEXT = "#94a3b8"
_NAV_TEXT_ACTIVE = "#ffffff"

_NAV = ["Dashboard", "Credentials", "Strategy", "System", "Trades", "Logs"]

# Nav icons (unicode glyphs — no extra deps)
_ICONS = {
    "Dashboard":   "⌂",
    "Credentials": "🔑",
    "Strategy":    "📈",
    "System":      "⚙",
    "Trades":      "⚡",
    "Logs":        "📋",
}


class SantoshApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Santosh Trading Setup")
        self.geometry("1280x860")
        self.minsize(1020, 700)
        self.configure(fg_color=_HEADER_BG)

        self.bridge = BotBridge(PROJECT_ROOT)
        self._active = "Dashboard"

        self._build_layout()
        self._show_view("Dashboard")
        self.after(_REFRESH_MS, self._refresh_loop)

    def _build_layout(self) -> None:
        # ── Header ───────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=_HEADER_BG, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="Santosh Trading", font=("Segoe UI", 20, "bold"),
                     text_color="#e2e8f0").pack(side="left", padx=20)

        self._mode_badge = ctk.CTkLabel(
            hdr, text="PAPER", font=("Segoe UI", 11, "bold"), text_color="#ffffff",
            fg_color="#7c3aed", corner_radius=5, width=64, height=22,
        )
        self._mode_badge.pack(side="left", padx=6)

        self._auth_lbl = ctk.CTkLabel(hdr, text="Auth: --", font=("Segoe UI", 12), text_color=_MUTED)
        self._auth_lbl.pack(side="right", padx=20)

        ctk.CTkFrame(hdr, fg_color="#1e2642", width=1).pack(side="right", fill="y", pady=8)

        # ── Body ─────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # Sidebar
        sidebar = ctk.CTkFrame(body, width=_SIDEBAR_W, corner_radius=0, fg_color=_SIDEBAR_BG)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ctk.CTkFrame(sidebar, fg_color="#1e2642", height=1).pack(fill="x")

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for name in _NAV:
            icon = _ICONS.get(name, "")
            btn = ctk.CTkButton(
                sidebar,
                text=f"  {icon}  {name}",
                width=_SIDEBAR_W,
                height=38,
                font=("Segoe UI", 13),
                anchor="w",
                fg_color=_NAV_FG,
                text_color=_NAV_TEXT,
                hover_color=_NAV_HOVER,
                corner_radius=0,
                command=lambda n=name: self._show_view(n),
            )
            btn.pack(fill="x")
            self._nav_btns[name] = btn

        # Content
        self._content = ctk.CTkFrame(body, fg_color=_CONTENT_BG, corner_radius=0)
        self._content.pack(side="right", fill="both", expand=True)

        # Views — instantiated once, swapped in/out
        self._views: dict[str, ctk.CTkFrame] = {
            "Dashboard":   DashboardView(self._content, self.bridge),
            "Credentials": CredentialsView(self._content, SOURCE_DIR),
            "Strategy":    StrategyView(self._content, SOURCE_DIR),
            "System":      SystemView(self._content, SOURCE_DIR),
            "Trades":      TradesView(self._content, self.bridge),
            "Logs":        LogsView(self._content, self.bridge.get_log_path()),
        }

        # Status bar
        self._status_bar = StatusBar(self)
        self._status_bar.pack(side="bottom", fill="x")

    def _show_view(self, name: str) -> None:
        for view in self._views.values():
            view.pack_forget()
        self._views[name].pack(fill="both", expand=True)
        self._active = name

        for btn_name, btn in self._nav_btns.items():
            if btn_name == name:
                btn.configure(fg_color=_ACTIVE_FG, text_color=_NAV_TEXT_ACTIVE,
                               hover_color=_ACTIVE_HOVER)
            else:
                btn.configure(fg_color=_NAV_FG, text_color=_NAV_TEXT,
                               hover_color=_NAV_HOVER)

    def _refresh_loop(self) -> None:
        state = self.bridge.get_state()
        mode = self.bridge.get_runtime_mode()

        # Header badges
        self._mode_badge.configure(
            text=mode.upper(),
            fg_color="#ef4444" if mode == "live" else "#7c3aed",
        )
        self._auth_lbl.configure(
            text="Auth: OK" if state.auth_ok else "Auth: —",
            text_color="#22c55e" if state.auth_ok else _MUTED,
        )

        # Status bar
        self._status_bar.update_state(state, mode=mode)

        # Active view
        view = self._views.get(self._active)
        if view and hasattr(view, "update_state"):
            view.update_state(state)

        self.after(_REFRESH_MS, self._refresh_loop)
