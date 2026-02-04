"""E-Ink Renderer - Black & white wallpapers for e-ink displays."""
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .calendar_engine import CalendarData
from .config import FONTS_DIR, OUTPUT_DIR

# E-ink display settings
EINK_WIDTH = 480
EINK_HEIGHT = 800

# Colors (pure B&W for e-ink)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
LIGHT_GRAY = (180, 180, 180)  # For past days
DARK_GRAY = (80, 80, 80)      # For subtle elements

# Typography - scaled for 480x800
MONTH_FONT_SIZE = 32
DATE_FONT_SIZE = 24
HEADER_FONT_SIZE = 24

# Layout
TOP_MARGIN = 0.08
MONTH_HEIGHT = 0.12
GRID_HEIGHT = 0.55


class EinkRenderer:
    """Renders calendar for e-ink displays in B&W."""

    def __init__(self):
        self.width = EINK_WIDTH
        self.height = EINK_HEIGHT
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts - using medium weight for better e-ink readability."""
        avenir_path = "/System/Library/Fonts/Avenir Next.ttc"

        if Path(avenir_path).exists():
            # Index 5 = Medium, good for e-ink contrast
            self.month_font = ImageFont.truetype(avenir_path, MONTH_FONT_SIZE, index=5)
            self.date_font = ImageFont.truetype(avenir_path, DATE_FONT_SIZE, index=7)  # Regular
            self.highlight_font = ImageFont.truetype(avenir_path, DATE_FONT_SIZE, index=2)  # Demi Bold
            return

        # Fallback
        fallbacks = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        for path in fallbacks:
            if Path(path).exists():
                self.month_font = ImageFont.truetype(path, MONTH_FONT_SIZE)
                self.date_font = ImageFont.truetype(path, DATE_FONT_SIZE)
                self.highlight_font = self.date_font
                return

        self.month_font = ImageFont.load_default()
        self.date_font = ImageFont.load_default()
        self.highlight_font = ImageFont.load_default()

    def _get_text_dimensions(self, draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int, int, int]:
        """Get text dimensions with offsets."""
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[0], bbox[1]

    def _get_spaced_text_width(self, draw: ImageDraw.ImageDraw, text: str, font, spacing: int) -> int:
        """Calculate width with letter spacing."""
        total = 0
        for i, char in enumerate(text):
            total += draw.textbbox((0, 0), char, font=font)[2]
            if i < len(text) - 1:
                total += spacing
        return total

    def _draw_spaced_text(self, draw: ImageDraw.ImageDraw, pos: Tuple[int, int], text: str, font, fill, spacing: int):
        """Draw text with letter spacing."""
        x, y = pos
        for char in text:
            draw.text((x, y), char, font=font, fill=fill)
            x += draw.textbbox((0, 0), char, font=font)[2] + spacing

    def render(
        self,
        calendar_data: CalendarData,
        output_path: Optional[Path] = None,
        invert: bool = False
    ) -> Image.Image:
        """
        Render B&W calendar for e-ink display.

        Args:
            calendar_data: Calendar data
            output_path: Save path (use .bmp extension)
            invert: If True, white background with black text

        Returns:
            PIL Image
        """
        # E-ink typically looks better with white bg, black text
        bg_color = WHITE if not invert else BLACK
        text_color = BLACK if not invert else WHITE
        past_color = LIGHT_GRAY if not invert else DARK_GRAY

        img = Image.new('RGB', (self.width, self.height), bg_color)
        draw = ImageDraw.Draw(img)

        # Layout
        top_margin = int(self.height * TOP_MARGIN)
        month_area = int(self.height * MONTH_HEIGHT)
        grid_area = int(self.height * GRID_HEIGHT)

        # --- Month/Year ---
        month_text = f"{calendar_data.month_name.upper()} {calendar_data.year}"
        letter_spacing = 4
        spaced_width = self._get_spaced_text_width(draw, month_text, self.month_font, letter_spacing)
        _, text_h, _, off_y = self._get_text_dimensions(draw, month_text, self.month_font)

        month_x = (self.width - spaced_width) // 2
        month_y = top_margin + (month_area - text_h) // 2 - off_y
        self._draw_spaced_text(draw, (month_x, month_y), month_text, self.month_font, text_color, letter_spacing)

        # --- Grid ---
        grid_top = top_margin + month_area
        cell_width = self.width // 7
        num_rows = len(calendar_data.grid) + 1
        cell_height = grid_area // num_rows

        # Find today's column for highlighting the weekday header
        today_col = None
        if calendar_data.today_position:
            _, today_col = calendar_data.today_position

        # Weekday headers - bold black for today's day of week
        for col, header in enumerate(calendar_data.weekday_headers):
            short = header[0]
            is_today_col = (col == today_col)

            # Use bold font and black for today's weekday
            font = self.highlight_font if is_today_col else self.date_font
            color = text_color if is_today_col else past_color

            hw, hh, hox, hoy = self._get_text_dimensions(draw, short, font)
            hx = col * cell_width + (cell_width - hw) // 2 - hox
            hy = grid_top + (cell_height - hh) // 2 - hoy
            draw.text((hx, hy), short, font=font, fill=color)

        # Days
        dates_top = grid_top + cell_height
        today_day = None
        if calendar_data.today_position:
            tr, tc = calendar_data.today_position
            today_day = calendar_data.grid[tr][tc].day

        for row_idx, week in enumerate(calendar_data.grid):
            for col_idx, day in enumerate(week):
                if day.day == 0:
                    continue

                cell_x = col_idx * cell_width
                cell_y = dates_top + row_idx * cell_height
                center_x = cell_x + cell_width // 2
                center_y = cell_y + cell_height // 2

                day_text = str(day.day)
                is_past = today_day and day.day < today_day

                if day.is_today:
                    # Inverted highlight for e-ink (black circle, white text)
                    dw, dh, dox, doy = self._get_text_dimensions(draw, day_text, self.highlight_font)
                    radius = max(dw, dh) // 2 + 8

                    draw.ellipse(
                        [center_x - radius, center_y - radius,
                         center_x + radius, center_y + radius],
                        fill=text_color
                    )

                    tx = center_x - dw // 2 - dox
                    ty = center_y - dh // 2 - doy
                    draw.text((tx, ty), day_text, font=self.highlight_font, fill=bg_color)
                else:
                    dw, dh, dox, doy = self._get_text_dimensions(draw, day_text, self.date_font)
                    tx = center_x - dw // 2 - dox
                    ty = center_y - dh // 2 - doy
                    color = past_color if is_past else text_color
                    draw.text((tx, ty), day_text, font=self.date_font, fill=color)

        # Save as BMP if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Save as 24-bit BMP (uncompressed)
            img.save(output_path, 'BMP')

        return img


def generate_eink(date_str: Optional[str] = None, output_dir: Optional[Path] = None) -> Path:
    """Generate e-ink wallpaper."""
    from .calendar_engine import CalendarEngine
    import pytz
    from datetime import datetime
    from .config import DEFAULT_TIMEZONE

    engine = CalendarEngine()

    if date_str:
        parts = [int(x) for x in date_str.split('-')]
        tz = pytz.timezone(DEFAULT_TIMEZONE)
        target = tz.localize(datetime(*parts))
        cal_data = engine.generate(target)
    else:
        cal_data = engine.generate()

    renderer = EinkRenderer()
    output_dir = output_dir or OUTPUT_DIR
    output_path = output_dir / f"eink_{cal_data.year}-{cal_data.month:02d}-{cal_data.grid[cal_data.today_position[0]][cal_data.today_position[1]].day:02d}.bmp"

    renderer.render(cal_data, output_path=output_path)
    return output_path


if __name__ == "__main__":
    path = generate_eink()
    print(f"E-ink wallpaper saved to: {path}")
