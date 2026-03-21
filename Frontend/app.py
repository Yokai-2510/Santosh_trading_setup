"""
app — dark-themed CTK window with expanded sidebar navigation,
password gate, and 1s live refresh.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from bridge.bot_bridge import BotBridge
from theme import colors as C, fonts as F
from utils.password_manager import PasswordManager

from views.credentials_view import CredentialsView
from views.dashboard_view import DashboardView
from views.logs_view import LogsView
from views.strategy_view import StrategyView
from views.system_view import SystemView
from views.trades_view import TradesView
from views.analytics_view import AnalyticsView
from views.status_view import StatusView
from views.backtest_view import BacktestView
from views.connections_view import ConnectionsView
from widgets.status_bar import StatusBar

FRONTEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FRONTEND_DIR.parent

_REFRESH_MS = 1000
_SIDEBAR_W = 180

# Sidebar navigation sections
_NAV_SECTIONS = {
    "MAIN": [
        ("Dashboard",   "\u2302"),
        ("Trades",      "\u26a1"),
        ("Analytics",   "\U0001F4CA"),
        ("Logs",        "\U0001F4CB"),
    ],
    "CONFIG": [
        ("Strategy",    "\U0001F4C8"),
        ("System",      "\u2699"),
        ("Credentials", "\U0001F511"),
        ("Connections", "\U0001F517"),
    ],
    "TOOLS": [
        ("Status",      "\U0001F4E1"),
        ("Backtesting", "\U0001F501"),
    ],
}


class SantoshApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Santosh Trading Setup")
        self.geometry("1360x900")
        self.minsize(1060, 740)
        self.configure(fg_color=C.BG_PRIMARY)

        self._pw_mgr = PasswordManager(PROJECT_ROOT / "Backend" / "data_store")
        self.bridge = BotBridge(PROJECT_ROOT)
        self._active = "Dashboard"
        self._authenticated = False

        if self._pw_mgr.is_set:
            self._show_password_gate()
        else:
            self._authenticated = True
            self._build_main_ui()

    # ── Password Gate ─────────────────────────────────────────────────────

    def _show_password_gate(self) -> None:
        self._gate = ctk.CTkFrame(self, fg_color=C.BG_SECONDARY)
        self._gate.pack(fill="both", expand=True)

        box = ctk.CTkFrame(self._gate, fg_color=C.BG_CARD, corner_radius=16,
                           width=400, height=300)
        box.place(relx=0.5, rely=0.45, anchor="center")
        box.pack_propagate(False)

        ctk.CTkLabel(box, text="Santosh Trading", font=F.TITLE,
                     text_color=C.TEXT_PRIMARY).pack(pady=(40, 6))
        ctk.CTkLabel(box, text="Enter password to continue", font=F.SMALL,
                     text_color=C.TEXT_MUTED).pack(pady=(0, 20))

        self._pw_var = ctk.StringVar()
        pw_entry = ctk.CTkEntry(box, textvariable=self._pw_var, show="*",
                                width=260, height=38, fg_color=C.BG_INPUT,
                                text_color=C.TEXT_SECONDARY,
                                border_color=C.BORDER_INPUT,
                                placeholder_text="Password")
        pw_entry.pack(pady=(0, 12))
        pw_entry.bind("<Return>", lambda _: self._try_login())

        self._pw_err = ctk.CTkLabel(box, text="", font=F.SMALL, text_color=C.RED)
        self._pw_err.pack()

        ctk.CTkButton(box, text="Unlock", width=260, height=38,
                       fg_color=C.ACCENT_BLUE, hover_color=C.ACCENT_BLUE_HOVER,
                       font=F.BODY_BOLD, command=self._try_login).pack(pady=(6, 20))

        pw_entry.focus_set()

    def _try_login(self) -> None:
        if self._pw_mgr.verify(self._pw_var.get()):
            self._authenticated = True
            self._gate.destroy()
            self._build_main_ui()
        else:
            self._pw_err.configure(text="Incorrect password")

    # ── Main UI ───────────────────────────────────────────────────────────

    def _build_main_ui(self) -> None:
        # Header
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=C.BG_PRIMARY, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="Santosh Trading", font=F.TITLE,
                     text_color=C.TEXT_PRIMARY).pack(side="left", padx=20)

        self._mode_badge = ctk.CTkLabel(
            hdr, text="PAPER", font=F.TINY_BOLD, text_color="#ffffff",
            fg_color=C.ACCENT_PURPLE, corner_radius=5, width=64, height=22,
        )
        self._mode_badge.pack(side="left", padx=6)

        self._auth_lbl = ctk.CTkLabel(hdr, text="Auth: --", font=F.SMALL,
                                       text_color=C.TEXT_MUTED)
        self._auth_lbl.pack(side="right", padx=20)

        ctk.CTkFrame(hdr, fg_color=C.BG_HOVER, width=1).pack(side="right", fill="y", pady=8)

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # Sidebar
        sidebar = ctk.CTkFrame(body, width=_SIDEBAR_W, corner_radius=0, fg_color=C.BG_PRIMARY)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ctk.CTkFrame(sidebar, fg_color=C.BG_HOVER, height=1).pack(fill="x")

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for section, items in _NAV_SECTIONS.items():
            # Section label
            ctk.CTkLabel(sidebar, text=section, font=F.TINY_BOLD,
                         text_color=C.TEXT_DIMMED).pack(anchor="w", padx=16, pady=(12, 4))
            for name, icon in items:
                btn = ctk.CTkButton(
                    sidebar,
                    text=f"  {icon}  {name}",
                    width=_SIDEBAR_W,
                    height=36,
                    font=F.BODY,
                    anchor="w",
                    fg_color=C.NAV_FG,
                    text_color=C.NAV_TEXT,
                    hover_color=C.NAV_HOVER,
                    corner_radius=0,
                    command=lambda n=name: self._show_view(n),
                )
                btn.pack(fill="x")
                self._nav_btns[name] = btn

        # Password management at bottom of sidebar
        pw_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        pw_frame.pack(side="bottom", fill="x", padx=8, pady=8)
        self._pw_toggle = ctk.CTkButton(
            pw_frame,
            text="Set Password" if not self._pw_mgr.is_set else "Change Password",
            width=_SIDEBAR_W - 16, height=28,
            font=F.TINY, fg_color="#374151", hover_color="#4b5563",
            text_color=C.TEXT_MUTED, corner_radius=4,
            command=self._password_dialog,
        )
        self._pw_toggle.pack()

        # Content
        self._content = ctk.CTkFrame(body, fg_color=C.BG_SECONDARY, corner_radius=0)
        self._content.pack(side="right", fill="both", expand=True)

        configs_dir = self.bridge.get_configs_dir()
        self._views: dict[str, ctk.CTkFrame] = {
            "Dashboard":   DashboardView(self._content, self.bridge),
            "Credentials": CredentialsView(self._content, configs_dir),
            "Strategy":    StrategyView(self._content, configs_dir),
            "System":      SystemView(self._content, configs_dir),
            "Trades":      TradesView(self._content, self.bridge),
            "Logs":        LogsView(self._content, self.bridge.get_log_path()),
            "Analytics":   AnalyticsView(self._content, self.bridge),
            "Status":      StatusView(self._content, self.bridge),
            "Backtesting": BacktestView(self._content, self.bridge),
            "Connections": ConnectionsView(self._content, self.bridge),
        }

        # Status bar
        self._status_bar = StatusBar(self)
        self._status_bar.pack(side="bottom", fill="x")

        self._show_view("Dashboard")
        self.after(_REFRESH_MS, self._refresh_loop)

    def _show_view(self, name: str) -> None:
        for view in self._views.values():
            view.pack_forget()
        if name in self._views:
            self._views[name].pack(fill="both", expand=True)
        self._active = name

        for btn_name, btn in self._nav_btns.items():
            if btn_name == name:
                btn.configure(fg_color=C.ACCENT_BLUE, text_color=C.NAV_TEXT_ACTIVE,
                               hover_color=C.ACCENT_BLUE_HOVER)
            else:
                btn.configure(fg_color=C.NAV_FG, text_color=C.NAV_TEXT,
                               hover_color=C.NAV_HOVER)

    def _refresh_loop(self) -> None:
        if not self._authenticated:
            self.after(_REFRESH_MS, self._refresh_loop)
            return

        state = self.bridge.get_state()
        mode = self.bridge.get_runtime_mode()

        # Header badges
        self._mode_badge.configure(
            text=mode.upper(),
            fg_color=C.RED if mode == "live" else C.ACCENT_PURPLE,
        )
        self._auth_lbl.configure(
            text="Auth: OK" if state.auth_ok else "Auth: --",
            text_color=C.GREEN if state.auth_ok else C.TEXT_MUTED,
        )

        # Status bar
        self._status_bar.update_state(state, mode=mode)

        # Active view
        view = self._views.get(self._active)
        if view and hasattr(view, "update_state"):
            view.update_state(state)

        self.after(_REFRESH_MS, self._refresh_loop)

    def _password_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Set Password")
        dialog.geometry("380x220")
        dialog.configure(fg_color=C.BG_CARD)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Set Application Password", font=F.SUBHEADING,
                     text_color=C.TEXT_PRIMARY).pack(pady=(20, 12))

        pw_var = ctk.StringVar()
        pw_entry = ctk.CTkEntry(dialog, textvariable=pw_var, show="*", width=280, height=36,
                                fg_color=C.BG_INPUT, text_color=C.TEXT_SECONDARY,
                                border_color=C.BORDER_INPUT, placeholder_text="New password")
        pw_entry.pack(pady=(0, 8))

        status = ctk.CTkLabel(dialog, text="", font=F.SMALL, text_color=C.GREEN)
        status.pack()

        def _save():
            pw = pw_var.get().strip()
            if pw:
                self._pw_mgr.set_password(pw)
                self._pw_toggle.configure(text="Change Password")
                status.configure(text="Password set!")
                dialog.after(800, dialog.destroy)
            else:
                self._pw_mgr.clear()
                self._pw_toggle.configure(text="Set Password")
                status.configure(text="Password cleared")
                dialog.after(800, dialog.destroy)

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=8)
        ctk.CTkButton(btn_row, text="Save", width=120, height=34,
                       fg_color=C.ACCENT_BLUE, hover_color=C.ACCENT_BLUE_HOVER,
                       font=F.BODY_BOLD, command=_save).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Remove Password", width=140, height=34,
                       fg_color="#374151", hover_color="#4b5563",
                       font=F.BODY, command=lambda: (self._pw_mgr.clear(),
                       self._pw_toggle.configure(text="Set Password"),
                       dialog.destroy())).pack(side="left", padx=4)
