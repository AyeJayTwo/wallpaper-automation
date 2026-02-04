"""E-Ink Renderer - Black & white wallpapers for e-ink displays."""
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .calendar_engine import CalendarData
from .config import FONTS_DIR, OUTPUT_EINK_DIR

# E-ink display settings
EINK_WIDTH = 480
EINK_HEIGHT = 800

# Colors (pure B&W for e-ink - no greys, they don't render well)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Typography - scaled for 480x800
MONTH_FONT_SIZE = 32
DATE_FONT_SIZE = 24
HEADER_FONT_SIZE = 24
QUOTE_FONT_SIZE = 16
QUOTE_AUTHOR_SIZE = 14

# Layout
TOP_MARGIN = 0.06
MONTH_HEIGHT = 0.10
GRID_HEIGHT = 0.45
QUOTE_MARGIN = 0.03  # Space between grid and quote


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
            # Quote fonts - italic for quote, regular for author
            self.quote_font = ImageFont.truetype(avenir_path, QUOTE_FONT_SIZE, index=4)  # Italic
            self.quote_author_font = ImageFont.truetype(avenir_path, QUOTE_AUTHOR_SIZE, index=7)  # Regular
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
                self.quote_font = ImageFont.truetype(path, QUOTE_FONT_SIZE)
                self.quote_author_font = ImageFont.truetype(path, QUOTE_AUTHOR_SIZE)
                return

        self.month_font = ImageFont.load_default()
        self.date_font = ImageFont.load_default()
        self.highlight_font = ImageFont.load_default()
        self.quote_font = ImageFont.load_default()
        self.quote_author_font = ImageFont.load_default()

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

    def _wrap_text(self, text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        """Wrap text to fit within max_width."""
        words = text.replace('\n', ' ').split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def render(
        self,
        calendar_data: CalendarData,
        output_path: Optional[Path] = None,
        invert: bool = False,
        quote_text: Optional[str] = None,
        quote_author: Optional[str] = None
    ) -> Image.Image:
        """
        Render B&W calendar for e-ink display.

        Args:
            calendar_data: Calendar data
            output_path: Save path (use .bmp extension)
            invert: If True, white background with black text
            quote_text: Optional quote to display below calendar
            quote_author: Optional author attribution

        Returns:
            PIL Image
        """
        # E-ink: pure black and white only - no greys
        bg_color = WHITE if not invert else BLACK
        text_color = BLACK if not invert else WHITE

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

        # Weekday headers - all black, BOLD for today's day
        for col, header in enumerate(calendar_data.weekday_headers):
            short = header[0]
            is_today_col = (col == today_col)

            # Bold for today's weekday, regular for others - all black
            font = self.highlight_font if is_today_col else self.date_font

            hw, hh, hox, hoy = self._get_text_dimensions(draw, short, font)
            hx = col * cell_width + (cell_width - hw) // 2 - hox
            hy = grid_top + (cell_height - hh) // 2 - hoy
            draw.text((hx, hy), short, font=font, fill=text_color)

        # Days - all same color (black), only today has circle highlight
        dates_top = grid_top + cell_height

        for row_idx, week in enumerate(calendar_data.grid):
            for col_idx, day in enumerate(week):
                if day.day == 0:
                    continue

                cell_x = col_idx * cell_width
                cell_y = dates_top + row_idx * cell_height
                center_x = cell_x + cell_width // 2
                center_y = cell_y + cell_height // 2

                day_text = str(day.day)

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
                    # All other days: same black color
                    dw, dh, dox, doy = self._get_text_dimensions(draw, day_text, self.date_font)
                    tx = center_x - dw // 2 - dox
                    ty = center_y - dh // 2 - doy
                    draw.text((tx, ty), day_text, font=self.date_font, fill=text_color)

        # --- Quote Section ---
        if quote_text:
            quote_top = grid_top + grid_area + int(self.height * QUOTE_MARGIN)
            quote_margin_x = 24
            max_quote_width = self.width - (quote_margin_x * 2)

            # Clean up quote text (remove markdown formatting)
            clean_quote = quote_text.replace('*', '').replace('_', '').strip()

            # Wrap quote text
            quote_lines = self._wrap_text(f'"{clean_quote}"', self.quote_font, max_quote_width, draw)

            # Limit to reasonable number of lines
            max_lines = 6
            if len(quote_lines) > max_lines:
                quote_lines = quote_lines[:max_lines]
                quote_lines[-1] = quote_lines[-1].rstrip() + '..."'

            # Draw quote lines
            line_height = int(QUOTE_FONT_SIZE * 1.4)
            current_y = quote_top

            for line in quote_lines:
                draw.text((quote_margin_x, current_y), line, font=self.quote_font, fill=text_color)
                current_y += line_height

            # Draw author attribution
            if quote_author and quote_author != "Unknown":
                author_text = f"— {quote_author}"
                current_y += 4  # Small gap
                draw.text((quote_margin_x, current_y), author_text, font=self.quote_author_font, fill=text_color)

        # Save as BMP if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Save as 24-bit BMP (uncompressed)
            img.save(output_path, 'BMP')

        return img


def generate_eink(date_str: Optional[str] = None, output_dir: Optional[Path] = None, include_quote: bool = True) -> Path:
    """Generate e-ink wallpaper with optional Readwise quote."""
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

    # Fetch quote from Readwise
    quote_text = None
    quote_author = None

    if include_quote:
        try:
            from .readwise import get_quote_for_date
            today_day = cal_data.grid[cal_data.today_position[0]][cal_data.today_position[1]].day
            date_key = f"{cal_data.year}-{cal_data.month:02d}-{today_day:02d}"
            quote = get_quote_for_date(date_key)
            quote_text = quote.text
            quote_author = quote.author
        except Exception as e:
            print(f"Could not fetch quote: {e}")

    renderer = EinkRenderer()
    output_dir = output_dir or OUTPUT_EINK_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    today_day = cal_data.grid[cal_data.today_position[0]][cal_data.today_position[1]].day
    output_filename = f"eink_{cal_data.year}-{cal_data.month:02d}-{today_day:02d}.bmp"
    output_path = output_dir / output_filename

    renderer.render(cal_data, output_path=output_path, quote_text=quote_text, quote_author=quote_author)

    # Create latest.bmp symlink
    latest_link = output_dir / "latest.bmp"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_filename)

    return output_path


if __name__ == "__main__":
    path = generate_eink()
    print(f"E-ink wallpaper saved to: {path}")
