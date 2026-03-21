"""
credentials_view — Upstox API credentials editor.
"""

from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk

_BG = "#1e2130"
_BG2 = "#252a3d"
_FG = "#c9d1e0"
_MUTED = "#6b7280"
_INPUT_BG = "#1a1f32"
_INPUT_BORDER = "#3d4870"
_GREEN = "#22c55e"


class CredentialsView(ctk.CTkScrollableFrame):
    def __init__(self, parent, configs_dir: Path, **kwargs) -> None:
        super().__init__(parent, fg_color=_BG, scrollbar_button_color=_BG2,
                         scrollbar_button_hover_color="#3d4870", **kwargs)
        self._path = configs_dir / "credentials.json"
        self._cfg = _load(self._path, {"upstox": {}})
        self._vars: dict[str, ctk.StringVar] = {}
        self._status = ctk.StringVar(value="")

        _section(self, "Upstox Credentials")

        up = self._cfg.get("upstox", {})
        for key, label, secret in [
            ("api_key", "API Key", False),
            ("api_secret", "API Secret", True),
            ("redirect_uri", "Redirect URI", False),
            ("totp_key", "TOTP Key", True),
            ("mobile_no", "Mobile Number", False),
            ("pin", "PIN", True),
        ]:
            var = ctk.StringVar(value=str(up.get(key, "")))
            self._vars[key] = var
            _entry_row(self, label, var, secret=secret)

        ctk.CTkButton(self, text="Save Credentials", width=180, height=34, fg_color="#2563eb",
                       hover_color="#1d4ed8", font=("Segoe UI", 13, "bold"),
                       command=self._save).pack(anchor="e", padx=16, pady=16)

        ctk.CTkLabel(self, textvariable=self._status, font=("Segoe UI", 12),
                     text_color=_GREEN).pack(anchor="e", padx=16)

    def update_state(self, state) -> None:
        pass

    def _save(self) -> None:
        self._cfg.setdefault("upstox", {})
        for key, var in self._vars.items():
            self._cfg["upstox"][key] = var.get().strip()
        _save(self._path, self._cfg)
        self._status.set("Saved ✓")


# ── helpers ──────────────────────────────────────────────────────────────────

def _section(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, font=("Segoe UI", 16, "bold"),
                 text_color="#e2e8f0").pack(anchor="w", padx=16, pady=(18, 8))


def _entry_row(parent, label: str, var: ctk.StringVar, secret: bool = False) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=16, pady=4)
    ctk.CTkLabel(row, text=label, width=160, anchor="w", font=("Segoe UI", 13),
                 text_color=_FG).pack(side="left")
    ctk.CTkEntry(row, textvariable=var, width=340, fg_color=_INPUT_BG, text_color=_FG,
                  border_color=_INPUT_BORDER, height=32, show="*" if secret else "").pack(side="left", padx=8)


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8-sig") as f:
            raw = f.read().strip()
            return json.loads(raw) if raw else default
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
