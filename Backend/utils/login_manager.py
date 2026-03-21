"""login_manager — auth orchestrator (cache-first flow)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from brokers.upstox.auth import (
    exchange_code_for_token,
    fetch_auth_code,
    is_token_valid,
    load_token_cache,
    save_token_cache,
)


def authenticate_upstox(
    credentials_cfg: Dict[str, Any],
    auth_cfg: Dict[str, Any],
    token_cache_path: Path,
    force_login: bool = False,
) -> Tuple[bool, Dict[str, str], str]:
    """
    Authenticate using cache-first flow.

    Returns:
        (success, headers, message)
    """
    upstox_creds = credentials_cfg.get("upstox", {})
    required_keys = ["api_key", "api_secret", "redirect_uri", "totp_key", "mobile_no", "pin"]
    missing = [key for key in required_keys if not str(upstox_creds.get(key, "")).strip()]
    if missing:
        return False, {}, f"Missing credential fields: {', '.join(missing)}"

    expiry_buffer = int(auth_cfg.get("token_expiry_buffer_min", 5))
    if not force_login and token_cache_path.exists():
        cache = load_token_cache(token_cache_path)
        if cache and is_token_valid(cache, expiry_buffer):
            token = cache["access_token"]
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            return True, headers, "Authenticated with cached token"

    try:
        auth_code = fetch_auth_code(upstox_creds, auth_cfg)
        token = exchange_code_for_token(upstox_creds, auth_code)
        save_token_cache(
            cache_path=token_cache_path,
            access_token=token,
            reset_time=auth_cfg.get("token_reset_time", "03:30"),
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        return True, headers, "Fresh authentication successful"
    except Exception as exc:
        return False, {}, f"Authentication failed: {exc}"
