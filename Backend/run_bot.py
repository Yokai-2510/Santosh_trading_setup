"""run_bot — headless entry point for Santosh trading bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main.engine import TradingEngine
from utils.config_loader import build_paths, load_all_configs
from utils.logger import setup_logger
from utils.state import StateStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Santosh trading bot")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--force-login", action="store_true", help="Force fresh Upstox login")
    args = parser.parse_args()

    project_root = CURRENT_DIR.parent
    paths = build_paths(project_root)
    config_bundle = load_all_configs(paths)

    level = config_bundle["system"].get("runtime", {}).get("log_level", "INFO")
    logger = setup_logger("santosh_bot", paths.logs_dir, level=level)
    state_store = StateStore()

    engine = TradingEngine(config_bundle=config_bundle, state_store=state_store, logger=logger)
    if not engine.initialize(force_login=args.force_login):
        return 1

    try:
        if args.once:
            engine.run_once()
        else:
            engine.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        engine.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
