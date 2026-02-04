"""Render Engine - Generates wallpaper images with calendar overlay."""
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .calendar_engine import CalendarData
from .config import (
    WIDTH, HEIGHT,
    BACKGROUNDS_DIR, FONTS_DIR, OUTPUT_DIR,
    CALENDAR_TOP_MARGIN, MONTH_YEAR_HEIGHT, CALENDAR_GRID_HEIGHT,
    MONTH_FONT_SIZE, DAY_HEADER_FONT_SIZE, DATE_FONT_SIZE,
    TODAY_HIGHLIGHT_PADDING,
    TEXT_COLOR, TEXT_SHADOW_COLOR, TODAY_HIGHLIGHT_COLOR, TODAY_TEXT_COLOR,
    PAST_DAY_COLOR, FUTURE_DAY_COLOR, WEEKEND_TEXT_COLOR, WEEKEND_PAST_COLOR,
    HEADER_TEXT_COLOR
)


class RenderEngine:
    """Renders calendar data onto wallpaper backgrounds."""

    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts with sophisticated fallback chain - preferring light weights."""
        # Light/thin fonts for elegant appearance
        light_font_candidates = [
            # SF Pro - Light weight
            "/System/Library/Fonts/SFNSDisplayLight.ttf",
            # Avenir Next - Light/UltraLight
            "/System/Library/Fonts/Avenir Next.ttc",
            # Helvetica Neue Light
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/Helvetica Neue.ttc",
            # System fonts
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]

        # Check for custom fonts first
        custom_light = FONTS_DIR / "custom-light.otf"
        custom_regular = FONTS_DIR / "custom-regular.otf"
        if custom_light.exists():
            light_font_candidates.insert(0, str(custom_light))
        elif custom_regular.exists():
            light_font_candidates.insert(0, str(custom_regular))

        font_path = None
        for path in light_font_candidates:
            if Path(path).exists():
                font_path = path
                break

        if font_path:
            self.month_font = ImageFont.truetype(font_path, MONTH_FONT_SIZE)
            self.header_font = ImageFont.truetype(font_path, DAY_HEADER_FONT_SIZE)
            self.date_font = ImageFont.truetype(font_path, DATE_FONT_SIZE)
        else:
            self.month_font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()
            self.date_font = ImageFont.load_default()

    def _create_forest_gradient(self) -> Image.Image:
        """Create a sophisticated deep forest green gradient background."""
        img = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(img)

        # Deep forest palette - dark at bottom, slightly lighter at top
        # Creates depth and draws eye upward to calendar
        top_color = (18, 42, 32)      # Deep forest green
        mid_color = (12, 32, 24)      # Darker forest
        bottom_color = (8, 22, 16)    # Near black forest

        for y in range(self.height):
            ratio = y / self.height

            if ratio < 0.5:
                # Top half: top_color to mid_color
                t = ratio * 2
                r = int(top_color[0] + (mid_color[0] - top_color[0]) * t)
                g = int(top_color[1] + (mid_color[1] - top_color[1]) * t)
                b = int(top_color[2] + (mid_color[2] - top_color[2]) * t)
            else:
                # Bottom half: mid_color to bottom_color
                t = (ratio - 0.5) * 2
                r = int(mid_color[0] + (bottom_color[0] - mid_color[0]) * t)
                g = int(mid_color[1] + (bottom_color[1] - mid_color[1]) * t)
                b = int(mid_color[2] + (bottom_color[2] - mid_color[2]) * t)

            draw.line([(0, y), (self.width, y)], fill=(r, g, b))

        return img

    def _create_placeholder_background(self) -> Image.Image:
        """Create default gradient placeholder - now uses forest theme."""
        return self._create_forest_gradient()

    def _load_background(self, background_path: Optional[Path] = None) -> Image.Image:
        """Load background image or create placeholder."""
        if background_path and background_path.exists():
            img = Image.open(background_path)
            if img.size != (self.width, self.height):
                img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            return img.convert('RGB')

        default_bg = BACKGROUNDS_DIR / "default.png"
        if default_bg.exists():
            img = Image.open(default_bg)
            if img.size != (self.width, self.height):
                img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            return img.convert('RGB')

        return self._create_placeholder_background()

    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: Tuple[int, int, int] = TEXT_COLOR,
        shadow_offset: int = 2,
        shadow_alpha: int = 80
    ):
        """Draw text with subtle shadow for depth and readability."""
        x, y = position
        # Subtle shadow for depth
        shadow_color = (0, 0, 0)
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=fill)

    def _get_text_dimensions(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont
    ) -> Tuple[int, int, int, int]:
        """Get precise text dimensions including baseline offset."""
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        offset_x = bbox[0]
        offset_y = bbox[1]
        return width, height, offset_x, offset_y

    def _draw_rounded_rect(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Tuple[int, int, int, int],
        radius: int,
        fill: Tuple[int, int, int]
    ):
        """Draw a rounded rectangle (pill shape for highlight)."""
        x1, y1, x2, y2 = bounds

        # Draw rounded rectangle using pieslices and rectangles
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
        draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)

    def render(
        self,
        calendar_data: CalendarData,
        background_path: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> Image.Image:
        """
        Render calendar onto wallpaper with high-design aesthetic.

        Args:
            calendar_data: Calendar data from CalendarEngine
            background_path: Optional custom background image
            output_path: If provided, save the image to this path

        Returns:
            PIL Image object
        """
        img = self._load_background(background_path)
        draw = ImageDraw.Draw(img)

        # Layout calculations
        top_margin = int(self.height * CALENDAR_TOP_MARGIN)
        month_area_height = int(self.height * MONTH_YEAR_HEIGHT)
        grid_area_height = int(self.height * CALENDAR_GRID_HEIGHT)

        # --- Month and Year (ALL CAPS for month) ---
        month_year_text = f"{calendar_data.month_name.upper()} {calendar_data.year}"
        text_w, text_h, off_x, off_y = self._get_text_dimensions(draw, month_year_text, self.month_font)

        # Center precisely (accounting for font metrics)
        month_x = (self.width - text_w) // 2 - off_x
        month_y = top_margin + (month_area_height - text_h) // 2 - off_y

        self._draw_text_with_shadow(draw, (month_x, month_y), month_year_text, self.month_font)

        # --- Grid Layout ---
        grid_top = top_margin + month_area_height
        cell_width = self.width // 7
        num_rows = len(calendar_data.grid) + 1
        cell_height = grid_area_height // num_rows

        # --- Weekday Headers (same font size as dates) ---
        header_y_base = grid_top
        for col, header in enumerate(calendar_data.weekday_headers):
            # Use single letter for clean look (M T W T F S S)
            short_header = header[0]
            hw, hh, hox, hoy = self._get_text_dimensions(draw, short_header, self.date_font)

            hx = col * cell_width + (cell_width - hw) // 2 - hox
            hy = header_y_base + (cell_height - hh) // 2 - hoy

            # Weekend headers more subtle
            color = WEEKEND_PAST_COLOR if col >= 5 else HEADER_TEXT_COLOR
            self._draw_text_with_shadow(draw, (hx, hy), short_header, self.date_font, fill=color, shadow_offset=1)

        # --- Calendar Days ---
        dates_top = grid_top + cell_height

        # Find today's day number for past/future comparison
        today_day = None
        if calendar_data.today_position:
            today_row, today_col = calendar_data.today_position
            today_day = calendar_data.grid[today_row][today_col].day

        for row_idx, week in enumerate(calendar_data.grid):
            for col_idx, day in enumerate(week):
                if day.day == 0:
                    continue

                cell_x = col_idx * cell_width
                cell_y = dates_top + row_idx * cell_height
                cell_center_x = cell_x + cell_width // 2
                cell_center_y = cell_y + cell_height // 2

                day_text = str(day.day)
                dw, dh, dox, doy = self._get_text_dimensions(draw, day_text, self.date_font)

                # Determine if this day is in the past
                is_past = today_day is not None and day.day < today_day

                if day.is_today:
                    # Draw highlight - pill/rounded rectangle shape
                    padding = TODAY_HIGHLIGHT_PADDING
                    highlight_w = dw + padding * 2
                    highlight_h = dh + padding * 2
                    radius = min(highlight_w, highlight_h) // 2  # Circular ends

                    hl_x1 = cell_center_x - highlight_w // 2
                    hl_y1 = cell_center_y - highlight_h // 2
                    hl_x2 = cell_center_x + highlight_w // 2
                    hl_y2 = cell_center_y + highlight_h // 2

                    self._draw_rounded_rect(draw, (hl_x1, hl_y1, hl_x2, hl_y2), radius, TODAY_HIGHLIGHT_COLOR)

                    # Center text precisely within highlight
                    text_x = cell_center_x - dw // 2 - dox
                    text_y = cell_center_y - dh // 2 - doy
                    draw.text((text_x, text_y), day_text, font=self.date_font, fill=TODAY_TEXT_COLOR)
                else:
                    # Regular day - color based on past/future and weekend
                    text_x = cell_center_x - dw // 2 - dox
                    text_y = cell_center_y - dh // 2 - doy

                    is_weekend = col_idx >= 5
                    if is_past:
                        color = WEEKEND_PAST_COLOR if is_weekend else PAST_DAY_COLOR
                    else:
                        color = WEEKEND_TEXT_COLOR if is_weekend else FUTURE_DAY_COLOR

                    self._draw_text_with_shadow(draw, (text_x, text_y), day_text, self.date_font, fill=color)

        # Save output
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, 'PNG', optimize=True)

        return img

    def generate_background_variants(self, output_dir: Optional[Path] = None) -> list:
        """Generate a set of background variants for testing."""
        output_dir = output_dir or BACKGROUNDS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        variants = []

        # Forest green (default)
        forest = self._create_forest_gradient()
        forest_path = output_dir / "forest_green.png"
        forest.save(forest_path, 'PNG')
        variants.append(forest_path)

        # Deep ocean
        ocean = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(ocean)
        for y in range(self.height):
            ratio = y / self.height
            r = int(8 + 12 * (1 - ratio))
            g = int(24 + 18 * (1 - ratio))
            b = int(42 + 28 * (1 - ratio))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        ocean_path = output_dir / "deep_ocean.png"
        ocean.save(ocean_path, 'PNG')
        variants.append(ocean_path)

        # Midnight
        midnight = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(midnight)
        for y in range(self.height):
            ratio = y / self.height
            r = int(18 + 10 * (1 - ratio))
            g = int(18 + 10 * (1 - ratio))
            b = int(28 + 14 * (1 - ratio))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        midnight_path = output_dir / "midnight.png"
        midnight.save(midnight_path, 'PNG')
        variants.append(midnight_path)

        return variants


if __name__ == "__main__":
    from .calendar_engine import CalendarEngine

    cal_engine = CalendarEngine()
    cal_data = cal_engine.generate()

    render_engine = RenderEngine()
    output = OUTPUT_DIR / "test_wallpaper.png"
    img = render_engine.render(cal_data, output_path=output)
    print(f"Test wallpaper saved to: {output}")
