"""
stat_card — small dark-themed metric tile.
"""

from __future__ import annotations

import customtkinter as ctk

_BG2 = "#252a3d"
_MUTED = "#6b7280"
_FG = "#e2e8f0"


class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label: str, **kwargs) -> None:
        super().__init__(parent, corner_radius=10, fg_color=_BG2, width=160, height=72, **kwargs)
        self.pack_propagate(False)
        ctk.CTkLabel(self, text=label, font=("Segoe UI", 11), text_color=_MUTED).pack(
            anchor="w", padx=12, pady=(10, 0)
        )
        self._value = ctk.CTkLabel(self, text="--", font=("Segoe UI", 20, "bold"), text_color=_FG)
        self._value.pack(anchor="w", padx=12, pady=(0, 10))

    def set_value(self, value: str, color: str = _FG) -> None:
        self._value.configure(text=value, text_color=color)
