#!/usr/bin/env python3
"""
Quick Telegram credential check.

Usage:
  # From env / .env already loaded:
  python3 scripts/test_telegram.py

  # Or pass explicitly (prefer env so secrets stay out of shell history):
  TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 scripts/test_telegram.py

Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"").strip()
        os.environ.setdefault(key, value)


def main() -> int:
    app_dir = Path(__file__).resolve().parent.parent
    load_dotenv(app_dir / ".env")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().strip("'\"")
    chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID", "").strip().strip("'\"")

    if not token or not chat_id_raw:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        print("Set them in .env or the environment, then re-run.")
        return 1

    chat_id: object = chat_id_raw
    if chat_id_raw.lstrip("-").isdigit():
        chat_id = int(chat_id_raw)

    # 1) Validate the bot token
    me_url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(me_url, timeout=15) as resp:
            me = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"getMe failed (HTTP {exc.code}): {body}")
        print("→ Bot token is likely wrong.")
        return 1
    except Exception as exc:
        print(f"getMe failed: {exc}")
        return 1

    if not me.get("ok"):
        print(f"getMe error: {me.get('description', me)}")
        print("→ Bot token is likely wrong.")
        return 1

    username = me["result"].get("username", "?")
    print(f"Bot token OK — @{username}")

    # 2) Try sending a test message
    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": "Xteink watcher Telegram test — credentials look good.",
    }).encode("utf-8")
    req = urllib.request.Request(
        send_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            sent = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("description", body)
        except Exception:
            detail = body
        print(f"sendMessage failed (HTTP {exc.code}): {detail}")
        print("→ Open a chat with your bot and tap Start, then re-check CHAT_ID.")
        return 1
    except Exception as exc:
        print(f"sendMessage failed: {exc}")
        return 1

    if not sent.get("ok"):
        print(f"sendMessage error: {sent.get('description', sent)}")
        return 1

    print(f"Message sent to chat_id={chat_id} — check Telegram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
