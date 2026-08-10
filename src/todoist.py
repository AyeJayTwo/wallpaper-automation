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
# REST v2 was deprecated; current API lives under /api/v1/
BASE_URL = "https://api.todoist.com/api/v1"


@dataclass
class TodoItem:
    """A single Todoist task."""
    content: str
    priority: int = 1  # 1=normal … 4=urgent (Todoist API)
    is_completed: bool = False


def _api_request(endpoint: str, params: dict | None = None) -> dict | list:
    """Make an authenticated request to the Todoist API v1."""
    if not TODOIST_TOKEN:
        raise ValueError("TODOIST_TOKEN (or TODOIST_API_TOKEN) not set in .env file")

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
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


def _current_user_id() -> str | None:
    """Return the authenticated Todoist user id, or None on failure."""
    try:
        data = _api_request("user")
        if isinstance(data, dict) and data.get("id") is not None:
            return str(data["id"])
    except Exception:
        pass
    return None


def _is_mine_or_unassigned(task: dict, my_uid: str | None) -> bool:
    """
    Keep tasks assigned to me or with no assignee.
    Drop tasks assigned to someone else (e.g. a shared-project partner).
    """
    responsible = task.get("responsible_uid")
    if responsible is None or responsible == "" or responsible == 0:
        return True
    if my_uid is not None and str(responsible) == my_uid:
        return True
    return False


def get_today_tasks(max_items: int = 12) -> List[TodoItem]:
    """
    Fetch tasks for the daily agenda: due today or overdue, assigned to me
    or unassigned (excludes tasks assigned to others in shared projects).

    Uses GET /api/v1/tasks/filter (paginated).
    Results are sorted by priority (urgent first), then by content.
    """
    items: List[TodoItem] = []
    cursor = None
    # today|overdue for the agenda; !assigned to: others drops partner tasks.
    query = "(today | overdue) & (!assigned to: others)"
    my_uid = _current_user_id()

    while len(items) < max_items:
        params: dict = {"query": query, "limit": min(50, max_items * 2)}
        if cursor:
            params["cursor"] = cursor

        data = _api_request("tasks/filter", params)

        # v1 filter endpoint returns {results: [...], next_cursor: ...}
        if isinstance(data, dict):
            tasks = data.get("results") or data.get("tasks") or []
            cursor = data.get("next_cursor")
        elif isinstance(data, list):
            tasks = data
            cursor = None
        else:
            break

        for t in tasks:
            if not _is_mine_or_unassigned(t, my_uid):
                continue
            content = (t.get("content") or "").strip()
            if not content:
                continue
            # Strip markdown link syntax: [label](url) → label
            if content.startswith("[") and "](" in content:
                end = content.find("](")
                if end > 1:
                    content = content[1:end]
            items.append(
                TodoItem(
                    content=content,
                    priority=int(t.get("priority") or 1),
                    is_completed=bool(t.get("checked") or t.get("is_completed")),
                )
            )
            if len(items) >= max_items:
                break

        if not cursor:
            break

    items.sort(key=lambda x: (-x.priority, x.content.lower()))
    return items[:max_items]


if __name__ == "__main__":
    print("Fetching today's Todoist tasks...")
    for i, task in enumerate(get_today_tasks(), 1):
        print(f"  {i}. [P{task.priority}] {task.content}")
