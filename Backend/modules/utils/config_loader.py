"""
config_loader — load and validate Santosh bot config files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ConfigPaths:
    root: Path
    source_dir: Path
    system: Path
    strategy: Path
    credentials: Path
    cache_dir: Path
    logs_dir: Path
    token_cache: Path
    universe_cache: Path


def build_paths(project_root: Path) -> ConfigPaths:
    source_dir = project_root / "Backend" / "source"
    system = source_dir / "system_config.json"
    strategy = source_dir / "strategy_config.json"
    credentials = source_dir / "credentials.json"

    system_cfg = safe_json_load(system, {})
    data_paths = system_cfg.get("data", {}).get("paths", {})

    cache_dir = project_root / data_paths.get("cache", "Backend/data/cache")
    logs_dir = project_root / data_paths.get("logs", "Backend/data/logs")
    token_cache = cache_dir / "access_token.json"
    universe_cache = cache_dir / "index_option_universe.json"

    return ConfigPaths(
        root=project_root,
        source_dir=source_dir,
        system=system,
        strategy=strategy,
        credentials=credentials,
        cache_dir=cache_dir,
        logs_dir=logs_dir,
        token_cache=token_cache,
        universe_cache=universe_cache,
    )


def safe_json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8-sig") as file:
            raw = file.read().strip()
            if not raw:
                return default
            return json.loads(raw)
    except Exception:
        return default


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def load_all_configs(paths: ConfigPaths) -> Dict[str, Any]:
    system = safe_json_load(paths.system, {})
    strategy = safe_json_load(paths.strategy, {})
    credentials = safe_json_load(paths.credentials, {})

    validate_strategy_config(strategy)
    validate_system_config(system)
    return {
        "system": system,
        "strategy": strategy,
        "credentials": credentials,
        "paths": paths,
    }


def validate_strategy_config(strategy_cfg: Dict[str, Any]) -> None:
    entry = strategy_cfg.setdefault("entry_conditions", {})
    timeframe = int(entry.get("timeframe_minutes", 3))
    if timeframe not in (2, 3, 5):
        entry["timeframe_minutes"] = 3

    instrument = strategy_cfg.setdefault("instrument_selection", {})
    underlying = str(instrument.get("underlying", "NIFTY")).upper()
    if underlying not in {"NIFTY", "BANKNIFTY"}:
        instrument["underlying"] = "NIFTY"

    expiry_choice = str(instrument.get("expiry_choice", "current")).lower()
    if expiry_choice not in {"current", "next"}:
        instrument["expiry_choice"] = "current"
    else:
        instrument["expiry_choice"] = expiry_choice

    strike_mode = str(instrument.get("strike_mode", "ATM")).upper()
    if strike_mode not in {"ATM", "ITM", "OTM"}:
        instrument["strike_mode"] = "ATM"

    option_type = str(instrument.get("option_type", "CE")).upper()
    if option_type not in {"CE", "PE"}:
        instrument["option_type"] = "CE"

    order = strategy_cfg.setdefault("order_details", {})
    order["max_active_positions"] = 1


def validate_system_config(system_cfg: Dict[str, Any]) -> None:
    runtime = system_cfg.setdefault("runtime", {})
    mode = str(runtime.get("mode", "paper")).lower()
    runtime["mode"] = "live" if mode == "live" else "paper"

    runtime.setdefault("loop_interval_seconds", 5)
    runtime.setdefault("logs_level", "INFO")

    auth_cfg = system_cfg.setdefault("auth", {})
    auth_cfg.setdefault("token_reset_time", "03:30")
    auth_cfg.setdefault("token_expiry_buffer_min", 5)
