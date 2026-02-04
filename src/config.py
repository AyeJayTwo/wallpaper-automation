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
CALENDAR_TOP_MARGIN = 0.10  # Generous top margin for visual breathing room
MONTH_YEAR_HEIGHT = 0.14    # Month/year - elegant, not overpowering
CALENDAR_GRID_HEIGHT = 0.48  # Grid takes generous space for legibility
# Total calendar area: ~72% of screen (top 2/3 with better proportions)

# Typography - refined sizing for visual hierarchy
MONTH_FONT_SIZE = 96        # Elegant, not shouting
DAY_HEADER_FONT_SIZE = 36   # Subtle weekday labels
DATE_FONT_SIZE = 64         # Comfortable reading size
TODAY_HIGHLIGHT_PADDING = 28  # Generous padding for highlight

# Color palette - sophisticated, high contrast
# Primary text: warm white (not pure white - easier on eyes)
TEXT_COLOR = (250, 248, 245)
# Subtle shadow for depth
TEXT_SHADOW_COLOR = (0, 0, 0, 100)
# Today highlight: warm amber/coral - creates striking contrast with forest green
TODAY_HIGHLIGHT_COLOR = (255, 171, 64)  # Amber gold
TODAY_TEXT_COLOR = (28, 28, 30)  # Near-black for contrast
# Weekend text: slightly muted
WEEKEND_TEXT_COLOR = (180, 178, 175)
# Weekday headers: subtle, understated
HEADER_TEXT_COLOR = (200, 198, 195)

# Timezone
DEFAULT_TIMEZONE = "America/Los_Angeles"
