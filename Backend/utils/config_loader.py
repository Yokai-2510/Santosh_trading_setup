"""config_loader — load and validate Santosh bot config files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class ConfigPaths:
    root: Path
    configs_dir: Path
    system: Path
    strategy: Path
    credentials: Path
    cache_dir: Path
    logs_dir: Path
    token_cache: Path
    universe_cache: Path


def build_paths(project_root: Path) -> ConfigPaths:
    configs_dir = project_root / "Backend" / "configs"
    system = configs_dir / "system_config.json"
    strategy = configs_dir / "strategy_config.json"
    credentials = configs_dir / "credentials.json"

    system_cfg = safe_json_load(system, {})
    data_paths = system_cfg.get("data", {}).get("paths", {})

    cache_dir = project_root / data_paths.get("cache", "Backend/data_store/cache")
    logs_dir = project_root / data_paths.get("logs", "Backend/data_store/logs")
    token_cache = cache_dir / "access_token.json"
    universe_cache = cache_dir / "index_option_universe.json"

    return ConfigPaths(
        root=project_root,
        configs_dir=configs_dir,
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


def validate_strategy_config(cfg: Dict[str, Any]) -> None:
    # Entry conditions
    entry = cfg.setdefault("entry_conditions", {})
    timeframe = int(entry.get("timeframe_minutes", 3))
    if timeframe not in (1, 2, 3, 5):
        entry["timeframe_minutes"] = 3
    entry.setdefault("rsi", {})
    entry.setdefault("volume_vs_ema", {})
    entry.setdefault("macd", {})
    entry.setdefault("adx", {})

    # Instrument selection
    ins = cfg.setdefault("instrument_selection", {})
    if str(ins.get("underlying", "NIFTY")).upper() not in {"NIFTY", "BANKNIFTY"}:
        ins["underlying"] = "NIFTY"
    else:
        ins["underlying"] = str(ins.get("underlying", "NIFTY")).upper()
    expiry = str(ins.get("expiry_choice", "current")).lower()
    ins["expiry_choice"] = expiry if expiry in {"current", "next"} else "current"
    strike_mode = str(ins.get("strike_mode", "ATM")).upper()
    ins["strike_mode"] = strike_mode if strike_mode in {"ATM", "ITM", "OTM"} else "ATM"
    option_type = str(ins.get("option_type", "CE")).upper()
    ins["option_type"] = option_type if option_type in {"CE", "PE"} else "CE"

    # Order execution
    cfg.setdefault("order_execution", {})

    # Exit conditions
    exits = cfg.setdefault("exit_conditions", {})
    exits.setdefault("stoploss", {"enabled": True, "type": "percent", "value": 30.0, "order_type": "SL-M"})
    exits.setdefault("target", {"enabled": False})
    exits.setdefault("trailing_sl", {"enabled": False})
    exits.setdefault("time_based_exit", {"enabled": False})

    # Order modify
    cfg.setdefault("order_modify", {})

    # Position management
    cfg.setdefault("position_management", {})


def validate_system_config(cfg: Dict[str, Any]) -> None:
    runtime = cfg.setdefault("runtime", {})
    mode = str(runtime.get("mode", "paper")).lower()
    runtime["mode"] = "live" if mode == "live" else "paper"
    runtime.setdefault("loop_interval_seconds", 5)
    runtime.setdefault("log_level", "INFO")

    cfg.setdefault("auth", {})
    cfg["auth"].setdefault("token_reset_time", "03:30")
    cfg["auth"].setdefault("token_expiry_buffer_min", 5)

    cfg.setdefault("market", {})
    cfg["market"].setdefault("open", "09:15:00")
    cfg["market"].setdefault("close", "15:30:00")

    cfg.setdefault("risk", {"enabled": False})

    cfg.setdefault("broker", {})
    cfg["broker"].setdefault("api_timeouts", {})
