"""Readwise integration - fetch quotes from your highlight library."""
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import urllib.request
import urllib.error
import json

# Load token from .env file
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

_load_env()

READWISE_TOKEN = os.environ.get("READWISE_TOKEN", "")
BASE_URL = "https://readwise.io/api/v2"


@dataclass
class Quote:
    """A highlight/quote from Readwise."""
    text: str
    author: str
    title: str
    is_favorite: bool = False
    note: str = ""


def _api_request(endpoint: str, params: dict = None) -> dict:
    """Make authenticated request to Readwise API."""
    if not READWISE_TOKEN:
        raise ValueError("READWISE_TOKEN not set in .env file")

    url = f"{BASE_URL}/{endpoint}/"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Token {READWISE_TOKEN}")

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        raise Exception(f"Readwise API error: {e.code} - {e.read().decode()}")


def get_highlights(page_size: int = 100, book_id: int = None) -> List[Quote]:
    """Fetch highlights from Readwise using export endpoint for full metadata."""
    # Use export endpoint to get book/author info with highlights
    data = _api_request("export", {})

    quotes = []
    for book in data.get("results", []):
        author = book.get("author", "Unknown")
        title = book.get("title", "")

        for h in book.get("highlights", []):
            text = h.get("text", "").strip()
            # Skip very short highlights
            if len(text) < 20:
                continue

            quotes.append(Quote(
                text=text,
                author=author if author else "Unknown",
                title=title,
                is_favorite=h.get("is_favorite", False),
                note=h.get("note", "")
            ))

            if len(quotes) >= page_size:
                break

        if len(quotes) >= page_size:
            break

    return quotes


def get_favorites(max_results: int = 100) -> List[Quote]:
    """Fetch only favorited highlights."""
    all_quotes = get_highlights(page_size=1000)
    favorites = [q for q in all_quotes if q.is_favorite]
    return favorites[:max_results]


def get_random_favorite() -> Optional[Quote]:
    """Get a random quote from favorites."""
    favorites = get_favorites()
    if not favorites:
        # Fall back to any highlight
        all_quotes = get_highlights(page_size=100)
        if all_quotes:
            return random.choice(all_quotes)
        return None
    return random.choice(favorites)


def get_daily_review_quotes() -> List[Quote]:
    """Get quotes from Readwise's daily review selection."""
    try:
        data = _api_request("review")
        quotes = []
        for h in data.get("highlights", []):
            quotes.append(Quote(
                text=h.get("text", ""),
                author=h.get("author", "Unknown"),
                title=h.get("title", ""),
                is_favorite=h.get("is_favorite", False),
                note=h.get("note", "")
            ))
        return quotes
    except Exception:
        return []


def get_quote_for_date(date_str: str) -> Quote:
    """
    Get a deterministic quote for a specific date.
    Uses the date as a seed to always return the same quote for the same date.
    """
    favorites = get_favorites()
    if not favorites:
        favorites = get_highlights(page_size=100)

    if not favorites:
        return Quote(
            text="No quotes available",
            author="",
            title=""
        )

    # Use date string as seed for deterministic selection
    seed = sum(ord(c) for c in date_str)
    index = seed % len(favorites)
    return favorites[index]


if __name__ == "__main__":
    # Test the integration
    print("Testing Readwise integration...\n")

    # Test getting favorites
    print("Fetching favorites...")
    favorites = get_favorites()
    print(f"Found {len(favorites)} favorites\n")

    if favorites:
        print("Sample favorite:")
        q = favorites[0]
        print(f'  "{q.text[:100]}..."')
        print(f"  — {q.author}, {q.title}\n")

    # Test random favorite
    print("Random favorite:")
    q = get_random_favorite()
    if q:
        print(f'  "{q.text[:100]}..."')
        print(f"  — {q.author}, {q.title}")
