"""
logs_view — event log tail. Reads bot.log on file-size change only (no looped writes).
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from modules.state.runtime_state import RuntimeState

_BG = "#1e2130"
_BG2 = "#252a3d"
_MUTED = "#6b7280"
_MAX_LINES = 300


class LogsView(ctk.CTkFrame):
    def __init__(self, parent, log_path: Path, **kwargs) -> None:
        super().__init__(parent, fg_color=_BG, **kwargs)
        self.log_path = log_path
        self._last_size = -1
        self._all_lines: list[str] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(header, text="Logs", font=("Segoe UI", 18, "bold"),
                     text_color="#e2e8f0").pack(side="left")

        self._level_var = ctk.StringVar(value="ALL")
        ctk.CTkOptionMenu(header, values=["ALL", "INFO", "WARNING", "ERROR"],
                           variable=self._level_var, width=120,
                           fg_color="#1a1f32", button_color="#3d4870",
                           dropdown_fg_color="#1e2130", text_color=_MUTED,
                           command=self._apply_filter).pack(side="right", padx=(8, 0))
        ctk.CTkButton(header, text="Clear", width=70, height=28, fg_color="#374151",
                       hover_color="#4b5563", font=("Segoe UI", 12),
                       command=self._clear).pack(side="right")

        self._textbox = ctk.CTkTextbox(self, font=("Consolas", 12),
                                        fg_color="#0f1117", text_color="#94a3b8",
                                        state="disabled", wrap="none")
        self._textbox.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    def update_state(self, state: RuntimeState) -> None:
        self._poll_log()

    def _poll_log(self) -> None:
        if not self.log_path.exists():
            return
        try:
            size = self.log_path.stat().st_size
            if size == self._last_size:
                return
            self._last_size = size
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                self._all_lines = f.readlines()[-_MAX_LINES:]
            self._apply_filter()
        except Exception:
            pass

    def _apply_filter(self, _=None) -> None:
        level = self._level_var.get()
        filtered = (
            self._all_lines if level == "ALL"
            else [ln for ln in self._all_lines if f"| {level}" in ln]
        )
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.insert("end", "".join(filtered[-_MAX_LINES:]))
        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def _clear(self) -> None:
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
