"""Configuration for the wallpaper pipeline."""
from pathlib import Path

# Output dimensions (iPhone 16 Pro)
WIDTH = 1320
HEIGHT = 2868

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
FONTS_DIR = ASSETS_DIR / "fonts"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Calendar settings
WEEK_START_MONDAY = True  # ISO standard

# Layout settings (as fractions of screen height)
CALENDAR_TOP_MARGIN = 0.08  # Start below notch area
MONTH_YEAR_HEIGHT = 0.17    # Month/year takes top portion
CALENDAR_GRID_HEIGHT = 0.42  # Grid takes remaining space
# Total calendar area: ~67% of screen (top 2/3)

# Typography
MONTH_FONT_SIZE = 120
DAY_HEADER_FONT_SIZE = 48
DATE_FONT_SIZE = 72
TODAY_HIGHLIGHT_PADDING = 20

# Colors (clean/readable style)
TEXT_COLOR = (255, 255, 255)  # White
TEXT_SHADOW_COLOR = (0, 0, 0, 128)  # Semi-transparent black
TODAY_HIGHLIGHT_COLOR = (255, 255, 255)  # White circle
TODAY_TEXT_COLOR = (0, 0, 0)  # Black text on white

# Timezone
DEFAULT_TIMEZONE = "America/Los_Angeles"
