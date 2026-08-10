"""Todoist integration - fetch Today's tasks for e-ink wallpapers."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List


def _load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env()

TODOIST_TOKEN = os.environ.get("TODOIST_TOKEN") or os.environ.get("TODOIST_API_TOKEN", "")
BASE_URL = "https://api.todoist.com/rest/v2"


@dataclass
class TodoItem:
    """A single Todoist task."""
    content: str
    priority: int = 1  # 1=normal … 4=urgent (Todoist API)
    is_completed: bool = False


def _api_request(endpoint: str, params: dict | None = None) -> list | dict:
    """Make an authenticated request to the Todoist REST API."""
    if not TODOIST_TOKEN:
        raise ValueError("TODOIST_TOKEN (or TODOIST_API_TOKEN) not set in .env file")

    url = f"{BASE_URL}/{endpoint}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TODOIST_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise Exception(f"Todoist API error: {e.code} - {body}") from e


def get_today_tasks(max_items: int = 12) -> List[TodoItem]:
    """
    Fetch incomplete tasks due today (Todoist filter: today).

    Results are sorted by priority (urgent first), then by API order.
    """
    tasks = _api_request("tasks", {"filter": "today"})
    if not isinstance(tasks, list):
        return []

    items: List[TodoItem] = []
    for t in tasks:
        content = (t.get("content") or "").strip()
        if not content:
            continue
        # Strip markdown link syntax common in Todoist: [label](url) → label
        if content.startswith("[") and "](" in content:
            end = content.find("](")
            if end > 1:
                content = content[1:end]
        items.append(
            TodoItem(
                content=content,
                priority=int(t.get("priority") or 1),
                is_completed=bool(t.get("is_completed")),
            )
        )

    # Todoist priority: 4 = urgent, 1 = normal — sort descending
    items.sort(key=lambda x: (-x.priority, x.content.lower()))
    return items[:max_items]


if __name__ == "__main__":
    print("Fetching today's Todoist tasks...")
    for i, task in enumerate(get_today_tasks(), 1):
        print(f"  {i}. [P{task.priority}] {task.content}")
