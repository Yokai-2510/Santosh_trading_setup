"""filter_instruments — standalone helper for building option universe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from data.instrument_filter import build_index_option_universe
from utils.config_loader import build_paths, load_all_configs
from utils.logger import setup_logger
from utils.login_manager import authenticate_upstox


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NIFTY/BANKNIFTY option universe")
    parser.add_argument("--expiry", choices=["current", "next"], required=True, help="Expiry choice")
    parser.add_argument("--force-login", action="store_true", help="Force fresh auth")
    args = parser.parse_args()

    project_root = CURRENT_DIR.parent
    paths = build_paths(project_root)
    cfg = load_all_configs(paths)
    logger = setup_logger("instrument_filter", paths.logs_dir, level="INFO")

    ok, headers, message = authenticate_upstox(
        credentials_cfg=cfg["credentials"],
        auth_cfg=cfg["system"].get("auth", {}),
        token_cache_path=paths.token_cache,
        force_login=args.force_login,
    )
    if not ok:
        logger.error(message)
        return 1

    logger.info(message)
    universe = build_index_option_universe(
        headers=headers,
        cache_dir=paths.cache_dir,
        expiry_choice=args.expiry,
        timeout_seconds=int(
            cfg["system"].get("broker", {}).get("api_timeouts", {}).get("master_contract_seconds", 60)
        ),
    )
    logger.info("Universe written with indices=%s", ",".join(sorted(universe.get("indices", {}).keys())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
