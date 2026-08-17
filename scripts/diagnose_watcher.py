#!/usr/bin/env python3
"""
Diagnose why the Xteink watcher may not upload today's wallpaper.

Run on the NAS (project root), with the Xteink on the File Upload screen:

    python3 scripts/diagnose_watcher.py

Or inside the container:

    sudo docker compose exec xteink-watcher python -u scripts/diagnose_watcher.py
"""

from __future__ import annotations

import ipaddress
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

# Keep this list small and LAN-only; used only as extra probes in diagnostics.
KNOWN_IPS = ("192.168.1.69", "10.0.0.164", "10.1.16.252")


def _load_env_file() -> dict[str, str]:
    env_path = APP_DIR / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _ok(label: str, detail: str) -> None:
    print(f"[OK]   {label}: {detail}")


def _warn(label: str, detail: str) -> None:
    print(f"[WARN] {label}: {detail}")


def _fail(label: str, detail: str) -> None:
    print(f"[FAIL] {label}: {detail}")


def _info(label: str, detail: str) -> None:
    print(f"[INFO] {label}: {detail}")


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out.strip()
    except FileNotFoundError:
        return 127, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def main() -> int:
    sys.path.insert(0, str(APP_DIR / "scripts"))
    from watch_and_upload import probe_device  # type: ignore

    print("=== Xteink watcher diagnostics ===\n")
    env_file = _load_env_file()

    tz = os.environ.get("TZ", "(unset, using system local time)")
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    _info("now", f"{now.isoformat(timespec='seconds')}  TZ={tz}")
    _info("today (watcher date)", today)

    git_rc, git_out = _run(["git", "-C", str(APP_DIR), "rev-parse", "--abbrev-ref", "HEAD"])
    if git_rc == 0:
        _info("git branch", git_out)
    else:
        _warn("git branch", git_out or "could not read")

    device_ip = (os.environ.get("DEVICE_IP") or env_file.get("DEVICE_IP") or "10.0.0.164").strip()
    try:
        device_ip = str(ipaddress.IPv4Address(device_ip))
        _ok("DEVICE_IP", device_ip)
    except ValueError:
        _fail("DEVICE_IP", f"invalid IPv4: {device_ip!r}")
        return 2

    if device_ip == "10.0.0.164":
        _warn(
            "DEVICE_IP",
            "this is the compose default. Home device is often 192.168.1.69 "
            "(set DEVICE_IP in .env if the probe below fails).",
        )

    state_dir = APP_DIR / "state"
    lock = state_dir / f"uploaded_{today}"
    reader_lock = state_dir / f"reader_uploaded_{today}"
    if lock.exists():
        _warn(
            "wallpaper lockfile",
            f"{lock} exists — watcher will skip wallpaper until tomorrow.\n"
            f"         contents: {lock.read_text().strip()!r}\n"
            f"         delete it to force a re-upload today:  rm {lock}",
        )
    else:
        _ok("wallpaper lockfile", f"absent ({lock.name}) — wallpaper is eligible today")

    if reader_lock.exists():
        _info("reader lockfile", f"{reader_lock.name}: {reader_lock.read_text().strip()!r}")
    else:
        _info("reader lockfile", f"absent ({reader_lock.name})")

    bmp = APP_DIR / "output" / "eink" / f"eink_{today}.bmp"
    if bmp.exists():
        _ok("today's BMP", f"{bmp} ({bmp.stat().st_size} bytes)")
    else:
        _warn("today's BMP", f"not generated yet: {bmp}")

    token = os.environ.get("READWISE_TOKEN") or env_file.get("READWISE_TOKEN") or ""
    if token:
        _ok("READWISE_TOKEN", f"set ({len(token)} chars)")
    else:
        _warn("READWISE_TOKEN", "missing — quotes/Reader sync will fail; wallpaper may still generate")

    todo = os.environ.get("TODOIST_TOKEN") or os.environ.get("TODOIST_API_TOKEN")
    todo = todo or env_file.get("TODOIST_TOKEN") or env_file.get("TODOIST_API_TOKEN") or ""
    if todo:
        _ok("TODOIST_TOKEN", f"set ({len(todo)} chars)")
    else:
        _info("TODOIST_TOKEN", "unset — e-ink wallpaper generates without tasks")

    print("\n--- Docker ---")
    for cmd in (
        ["docker", "compose", "ps"],
        ["sudo", "docker", "compose", "ps"],
    ):
        rc, out = _run(cmd)
        if rc == 0 and out:
            _ok(" ".join(cmd), "\n" + out)
            break
        if "permission denied" in out.lower():
            _fail(" ".join(cmd), "permission denied — retry with: sudo docker compose ps")
            break
        if rc == 127:
            continue
        _warn(" ".join(cmd), out or f"exit {rc}")

    print("\n--- Device probes (put Xteink on File Upload screen first) ---")
    ips = [device_ip]
    for extra in KNOWN_IPS:
        if extra not in ips:
            ips.append(extra)

    seen = False
    for ip in ips:
        ok, detail = probe_device(ip, timeout=5)
        if ok:
            seen = True
            _ok(f"probe {ip}", detail)
        else:
            _fail(f"probe {ip}", detail)

    print("\n--- Likely cause ---")
    configured_ok, configured_detail = probe_device(device_ip, timeout=5)
    working = [ip for ip in ips if probe_device(ip, timeout=3)[0]]

    if lock.exists():
        print("Watcher thinks wallpaper was already uploaded today. Remove the lockfile and reconnect.")
    elif working and device_ip not in working:
        print(
            f"Device is reachable at {', '.join(working)} but watcher is polling "
            f"{device_ip}. Set DEVICE_IP={working[0]} in .env, then:\n"
            "  sudo docker compose up -d"
        )
    elif not seen:
        print(
            "No CrossPoint /api/status response. Typical reasons:\n"
            "  1. Device is on WiFi but NOT on the File Upload screen (web server is off).\n"
            "  2. DEVICE_IP is wrong for this network.\n"
            "  3. Watcher container is not running (docker permission denied / not rebuilt).\n"
            f"Last configured-IP error: {configured_detail}"
        )
    else:
        print(
            "Device is online at the configured IP. If wallpaper still did not change, "
            "check container logs for Generation failed / Upload failed, then sleep the device "
            "after a successful upload (sleep.bmp is the custom sleep screen)."
        )

    print("\nNext: sudo docker compose logs --tail=100 xteink-watcher")
    return 0 if configured_ok or seen else 1


if __name__ == "__main__":
    raise SystemExit(main())
