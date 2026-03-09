"""
brokers.upstox.auth — pure Upstox OAuth helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, quote, urlparse

import pyotp
import requests
from playwright.sync_api import sync_playwright

_LOGIN_URL = "https://api.upstox.com/v2/login/authorization/dialog"
_TOKEN_URL = "https://api-v2.upstox.com/login/authorization/token"


def load_token_cache(cache_path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(cache_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def is_token_valid(cache: Dict[str, Any], expiry_buffer_min: int = 0) -> bool:
    if not cache or "access_token" not in cache:
        return False
    until = cache.get("valid_until_ist")
    if not until:
        return False
    try:
        expiry = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    return datetime.now() + timedelta(minutes=expiry_buffer_min) < expiry


def save_token_cache(cache_path: Path, access_token: str, reset_time: str = "03:30") -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    valid_until = _compute_valid_until_ist(reset_time)
    payload = {
        "access_token": access_token,
        "created_at_ist": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "valid_until_ist": valid_until.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(cache_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def fetch_auth_code(creds: Dict[str, Any], auth_cfg: Dict[str, Any]) -> str:
    api_key = creds["api_key"]
    redirect_uri = creds["redirect_uri"]
    login_url = auth_cfg.get("login_url", _LOGIN_URL)
    headless = bool(auth_cfg.get("headless", True))
    playwright_args = auth_cfg.get("playwright_args", [])

    auth_url = (
        f"{login_url}?response_type=code"
        f"&client_id={api_key}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
    )

    auth_code: Optional[str] = None

    def on_request(request) -> None:
        nonlocal auth_code
        if auth_code is not None:
            return
        if redirect_uri in request.url and "code=" in request.url:
            parsed = parse_qs(urlparse(request.url).query)
            auth_code = parsed.get("code", [None])[0]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=playwright_args)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.on("request", on_request)

        page.goto(auth_url, wait_until="networkidle", timeout=60000)
        page.locator("#mobileNum").fill(creds["mobile_no"])
        page.get_by_role("button", name="Get OTP").click()
        page.wait_for_selector("#otpNum", timeout=30000)

        otp = pyotp.TOTP(creds["totp_key"]).now()
        page.locator("#otpNum").fill(otp)
        page.get_by_role("button", name="Continue").click()

        page.wait_for_selector("input[type='password']", timeout=30000)
        page.get_by_label("Enter 6-digit PIN").fill(creds["pin"])
        page.get_by_role("button", name="Continue").click()
        page.wait_for_timeout(5000)

        if auth_code is None and redirect_uri in page.url and "code=" in page.url:
            parsed = parse_qs(urlparse(page.url).query)
            auth_code = parsed.get("code", [None])[0]

        context.close()
        browser.close()

    if not auth_code:
        raise RuntimeError("Failed to capture Upstox authorization code")
    return auth_code


def exchange_code_for_token(creds: Dict[str, Any], auth_code: str, token_url: str = _TOKEN_URL) -> str:
    headers = {
        "accept": "application/json",
        "Api-Version": "2.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "code": auth_code,
        "client_id": creds["api_key"],
        "client_secret": creds["api_secret"],
        "redirect_uri": creds["redirect_uri"],
        "grant_type": "authorization_code",
    }
    response = requests.post(token_url, headers=headers, data=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token") or data.get("data", {}).get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in token exchange response: {data}")
    return token


def _compute_valid_until_ist(reset_time_str: str) -> datetime:
    hh, mm = reset_time_str.split(":")
    reset_t = dt_time(hour=int(hh), minute=int(mm), second=0)
    now = datetime.now()
    today_reset = datetime.combine(now.date(), reset_t)
    if now < today_reset:
        return today_reset
    return today_reset + timedelta(days=1)
