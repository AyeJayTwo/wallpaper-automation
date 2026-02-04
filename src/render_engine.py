"""Render Engine - Generates wallpaper images with calendar overlay."""
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .calendar_engine import CalendarData
from .config import (
    WIDTH, HEIGHT,
    BACKGROUNDS_DIR, FONTS_DIR, OUTPUT_DIR,
    CALENDAR_TOP_MARGIN, MONTH_YEAR_HEIGHT, CALENDAR_GRID_HEIGHT,
    MONTH_FONT_SIZE, DAY_HEADER_FONT_SIZE, DATE_FONT_SIZE,
    TODAY_HIGHLIGHT_PADDING,
    TEXT_COLOR, TEXT_SHADOW_COLOR, TODAY_HIGHLIGHT_COLOR, TODAY_TEXT_COLOR
)


class RenderEngine:
    """Renders calendar data onto wallpaper backgrounds."""

    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts, falling back to system fonts if custom not available."""
        # Try to use SF Pro or fall back to system default
        try:
            # Check for custom fonts first
            custom_font = FONTS_DIR / "SF-Pro-Display-Bold.otf"
            if custom_font.exists():
                self.month_font = ImageFont.truetype(str(custom_font), MONTH_FONT_SIZE)
                self.header_font = ImageFont.truetype(str(custom_font), DAY_HEADER_FONT_SIZE)
                self.date_font = ImageFont.truetype(str(custom_font), DATE_FONT_SIZE)
                return
        except Exception:
            pass

        # Try system fonts (macOS)
        system_fonts = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]

        font_path = None
        for path in system_fonts:
            if Path(path).exists():
                font_path = path
                break

        if font_path:
            self.month_font = ImageFont.truetype(font_path, MONTH_FONT_SIZE)
            self.header_font = ImageFont.truetype(font_path, DAY_HEADER_FONT_SIZE)
            self.date_font = ImageFont.truetype(font_path, DATE_FONT_SIZE)
        else:
            # Ultimate fallback to default
            self.month_font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()
            self.date_font = ImageFont.load_default()

    def _create_placeholder_background(self) -> Image.Image:
        """Create a gradient placeholder background."""
        img = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(img)

        # Dark gradient from deep blue to black
        for y in range(self.height):
            ratio = y / self.height
            r = int(20 * (1 - ratio))
            g = int(30 * (1 - ratio) + 10)
            b = int(60 * (1 - ratio) + 20)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))

        return img

    def _load_background(self, background_path: Optional[Path] = None) -> Image.Image:
        """Load background image or create placeholder."""
        if background_path and background_path.exists():
            img = Image.open(background_path)
            # Resize to fit if needed
            if img.size != (self.width, self.height):
                img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            return img.convert('RGB')

        # Check for default background
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
        shadow_offset: int = 3
    ):
        """Draw text with a subtle shadow for readability."""
        x, y = position
        # Draw shadow
        shadow_color = TEXT_SHADOW_COLOR[:3]  # RGB only
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
        # Draw main text
        draw.text((x, y), text, font=font, fill=fill)

    def _get_text_bbox(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
        """Get width and height of text."""
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def render(
        self,
        calendar_data: CalendarData,
        background_path: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> Image.Image:
        """
        Render calendar onto wallpaper.

        Args:
            calendar_data: Calendar data from CalendarEngine
            background_path: Optional custom background image
            output_path: If provided, save the image to this path

        Returns:
            PIL Image object
        """
        # Load or create background
        img = self._load_background(background_path)
        draw = ImageDraw.Draw(img)

        # Calculate layout positions
        top_margin = int(self.height * CALENDAR_TOP_MARGIN)
        month_area_height = int(self.height * MONTH_YEAR_HEIGHT)
        grid_area_height = int(self.height * CALENDAR_GRID_HEIGHT)

        # Draw month and year (centered)
        month_year_text = f"{calendar_data.month_name} {calendar_data.year}"
        text_width, text_height = self._get_text_bbox(draw, month_year_text, self.month_font)
        month_x = (self.width - text_width) // 2
        month_y = top_margin + (month_area_height - text_height) // 3
        self._draw_text_with_shadow(draw, (month_x, month_y), month_year_text, self.month_font)

        # Calculate grid dimensions
        grid_top = top_margin + month_area_height
        cell_width = self.width // 7
        num_rows = len(calendar_data.grid) + 1  # +1 for header row
        cell_height = grid_area_height // num_rows

        # Draw weekday headers
        header_y = grid_top
        for col, header in enumerate(calendar_data.weekday_headers):
            text_w, text_h = self._get_text_bbox(draw, header, self.header_font)
            x = col * cell_width + (cell_width - text_w) // 2
            y = header_y + (cell_height - text_h) // 2
            # Weekend headers slightly dimmed
            color = (200, 200, 200) if col >= 5 else TEXT_COLOR
            self._draw_text_with_shadow(draw, (x, y), header, self.header_font, fill=color, shadow_offset=2)

        # Draw calendar grid
        dates_top = grid_top + cell_height
        for row_idx, week in enumerate(calendar_data.grid):
            for col_idx, day in enumerate(week):
                if day.day == 0:
                    continue

                cell_x = col_idx * cell_width
                cell_y = dates_top + row_idx * cell_height

                day_text = str(day.day)
                text_w, text_h = self._get_text_bbox(draw, day_text, self.date_font)

                # Center text in cell
                text_x = cell_x + (cell_width - text_w) // 2
                text_y = cell_y + (cell_height - text_h) // 2

                if day.is_today:
                    # Draw highlight circle
                    circle_radius = max(text_w, text_h) // 2 + TODAY_HIGHLIGHT_PADDING
                    circle_center_x = cell_x + cell_width // 2
                    circle_center_y = cell_y + cell_height // 2

                    # Draw filled circle
                    draw.ellipse(
                        [
                            circle_center_x - circle_radius,
                            circle_center_y - circle_radius,
                            circle_center_x + circle_radius,
                            circle_center_y + circle_radius
                        ],
                        fill=TODAY_HIGHLIGHT_COLOR
                    )

                    # Draw date in contrasting color (no shadow needed)
                    draw.text((text_x, text_y), day_text, font=self.date_font, fill=TODAY_TEXT_COLOR)
                else:
                    # Weekend dates slightly dimmed
                    color = (180, 180, 180) if col_idx >= 5 else TEXT_COLOR
                    self._draw_text_with_shadow(draw, (text_x, text_y), day_text, self.date_font, fill=color)

        # Save if output path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, 'PNG', optimize=True)

        return img


if __name__ == "__main__":
    from .calendar_engine import CalendarEngine

    # Test render
    cal_engine = CalendarEngine()
    cal_data = cal_engine.generate()

    render_engine = RenderEngine()
    output = OUTPUT_DIR / "test_wallpaper.png"
    img = render_engine.render(cal_data, output_path=output)
    print(f"Test wallpaper saved to: {output}")
