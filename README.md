# Calendar Wallpaper Generator

A deterministic wallpaper generator that creates daily calendar wallpapers for iPhone and e-ink devices. Each wallpaper displays the current month with today's date highlighted, plus an optional daily quote from your Readwise library.

## Features

- **iPhone Wallpapers** (1320×2868 PNG) — Optimized for iPhone 16 Pro
- **E-ink Wallpapers** (480×800 BMP) — Pure black & white for e-readers
- **Readwise Integration** — Display a daily quote from your highlights
- **Deterministic Output** — Same date always produces the same wallpaper
- **Timezone Aware** — Configurable timezone support
- **Automation Ready** — Predictable output paths with `latest` symlinks

## Screenshots

| iPhone | E-ink |
|--------|-------|
| Deep forest green gradient with amber highlight | Pure B&W with bold weekday indicator |

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/wallpaper-automation.git
cd wallpaper-automation

# Install dependencies
pip install -r requirements.txt
```

### Requirements

- Python 3.9+
- macOS (uses system fonts; Linux requires font installation)
- Pillow
- pytz

## Quick Start

```bash
# Generate today's iPhone wallpaper
python generate.py

# Generate today's e-ink wallpaper
python generate.py --eink

# Generate for a specific date
python generate.py --date 2024-12-25
python generate.py --eink --date 2024-12-25
```

## Output Structure

```
output/
├── iphone/
│   ├── latest.png              ← Always points to today's wallpaper
│   └── wallpaper_YYYY-MM-DD.png
└── eink/
    ├── latest.bmp              ← Always points to today's wallpaper
    └── eink_YYYY-MM-DD.bmp
```

For automation, always reference:
- `output/iphone/latest.png` for iPhone
- `output/eink/latest.bmp` for e-ink

## Configuration

Edit `src/config.py` to customize:

```python
# Display dimensions
WIDTH = 1320                    # iPhone 16 Pro width
HEIGHT = 2868                   # iPhone 16 Pro height

# Calendar
WEEK_START_MONDAY = True        # False for Sunday start

# Colors (iPhone)
TODAY_HIGHLIGHT_COLOR = (255, 171, 64)  # Amber gold
TEXT_COLOR = (250, 248, 245)            # Warm white

# Timezone
DEFAULT_TIMEZONE = "America/Los_Angeles"
```

## Readwise Integration

### Daily quotes (e-ink wallpaper)

Add daily quotes from your [Readwise](https://readwise.io) highlight library to e-ink wallpapers.

### Setup

1. Get your API token from [readwise.io/access_token](https://readwise.io/access_token)
2. Create a `.env` file in the project root:

```bash
READWISE_TOKEN=your_token_here
```

Quotes are deterministically selected — the same date will always show the same quote.

### Disable Quotes

```python
# In src/eink_renderer.py, generate_eink()
generate_eink(include_quote=False)
```

### Reader article sync (Xteink / Synology watcher)

When the Synology watcher detects your Xteink on the File Upload screen, it also
pulls new documents from [Readwise Reader](https://readwise.io/reader_api) and
uploads them as `.epub` files the device can open.

```bash
# Manual download only (no device upload)
python3 -m src.reader --max 10

# Optional .env knobs for the watcher
READER_SYNC=1
READER_LOCATIONS=new          # or: new,later
READER_MAX_ARTICLES=25
```

Articles are written to `output/reader/` and tracked in `state/reader_sync.json`
so each document is only downloaded once.

## CLI Reference

```
usage: generate.py [-h] [--date DATE] [--output-dir OUTPUT_DIR]
                   [--background BACKGROUND] [--timezone TIMEZONE]
                   [--no-fail-fast] [-v] [--eink]

Generate calendar wallpaper

options:
  --date DATE           Target date (YYYY-MM-DD). Default: today
  --output-dir DIR      Output directory
  --background PATH     Custom background image (iPhone only)
  --timezone TZ         Timezone. Default: America/Los_Angeles
  --eink                Generate e-ink version (480x800 BMP)
  -v, --verbose         Verbose output
```

## Automation

### Cron (Linux/macOS)

```bash
# Make script executable
chmod +x scripts/daily_generate.sh

# Edit crontab
crontab -e

# Add line (generates at 5:30 AM daily)
30 5 * * * /path/to/wallpaper-automation/scripts/daily_generate.sh
```

### iOS Shortcuts

See [docs/ios_shortcuts_setup.md](docs/ios_shortcuts_setup.md) for setting up automatic wallpaper updates on iPhone.

## Design

### iPhone

- **Font**: Avenir Next Ultra Light
- **Month**: ALL CAPS with letter spacing
- **Today**: Amber gold pill highlight with medium-weight text
- **Past days**: Light grey
- **Background**: Deep forest green gradient (customizable)

### E-ink

- **Pure B&W**: No greys (optimized for e-ink rendering)
- **Today indicator**: Bold weekday header + black circle
- **Quote**: Italic text with author attribution

## Project Structure

```
├── generate.py              # CLI entry point
├── src/
│   ├── calendar_engine.py   # Date/calendar logic
│   ├── render_engine.py     # iPhone wallpaper rendering
│   ├── eink_renderer.py     # E-ink rendering + quotes
│   ├── readwise.py          # Readwise highlights API (quotes)
│   ├── reader.py            # Readwise Reader API (article → EPUB)
│   ├── validator.py         # Output validation
│   ├── orchestrator.py      # Pipeline coordination
│   └── config.py            # Configuration
├── scripts/
│   ├── daily_generate.sh    # Cron automation
│   ├── deliver_to_shortcuts.py
│   └── watch_and_upload.py  # Synology: wallpaper + Reader sync
├── assets/
│   └── backgrounds/         # Background images
├── output/                  # Generated wallpapers + Reader EPUBs
│   ├── iphone/
│   ├── eink/
│   └── reader/
└── docs/                    # Setup guides
```

## Customization

### Custom Backgrounds

Place images in `assets/backgrounds/`:

```
assets/backgrounds/
├── default.png           # Used if no other match
├── monday.png            # Day-of-week backgrounds
├── january.png           # Month backgrounds
└── 2024-12-25.png        # Date-specific backgrounds
```

### Custom Fonts

Place `.otf` or `.ttf` files in `assets/fonts/`:

```
assets/fonts/
├── custom-light.otf      # Used for main text
└── custom-bold.otf       # Used for highlights
```

## API

### Python

```python
from src.calendar_engine import CalendarEngine
from src.render_engine import RenderEngine
from src.eink_renderer import EinkRenderer, generate_eink

# Generate calendar data
engine = CalendarEngine(timezone="America/New_York")
calendar_data = engine.generate()

# Render iPhone wallpaper
renderer = RenderEngine()
renderer.render(calendar_data, output_path=Path("my_wallpaper.png"))

# Generate e-ink with quote
generate_eink(date_str="2024-12-25", include_quote=True)
```

## Contributing

Contributions welcome! Please open an issue or submit a PR.

### Ideas for Future Development

- [ ] Multiple e-ink resolutions (600×800, 758×1024)
- [ ] Month transition (show prev/next month days)
- [ ] Holiday/event markers
- [ ] Theme system for easy color switching
- [ ] Docker container for cross-platform use
- [ ] Web endpoint for fetching wallpapers

## License

MIT License — see [LICENSE](LICENSE) for details.

---

Built with Pillow, pytz, and the Readwise API.
