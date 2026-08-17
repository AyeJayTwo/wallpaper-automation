"""E-Ink Renderer - Black & white wallpapers for e-ink displays.

Layout (480x800):
  1. Month header
  2. Calendar grid (cell height expands to fill available space)
  3. TODAY section banner + Todoist tasks (2-column, checkboxes)
  4. QUOTE section banner + Readwise quote
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .calendar_engine import CalendarData
from .config import OUTPUT_EINK_DIR

# E-ink display settings
EINK_WIDTH = 480
EINK_HEIGHT = 800

# Colors (pure B&W for e-ink - no greys)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Typography - scaled for 480x800
MONTH_FONT_SIZE = 32
DATE_FONT_SIZE = 30
HEADER_FONT_SIZE = 24
QUOTE_FONT_SIZE = 18
QUOTE_AUTHOR_SIZE = 16
TODO_HEADER_SIZE = 20

# Layout
TOP_MARGIN = 0.03
BOTTOM_MARGIN = 0.03
SECTION_GAP = 12
MARGIN_X = 24
MIN_CELL_HEIGHT = 36
MAX_CELL_HEIGHT = 52
CHECKBOX_SIZE = 14
CHECKBOX_GAP = 8
TODO_COL_GAP = 16
TODO_LINE_MIN = 1.35
TODO_LINE_MAX = 2.0
QUOTE_LINE_HEIGHT = 1.4
SECTION_BANNER_H = 30
SECTION_BANNER_GAP = 8
MAX_TODO_ITEMS = 12


class EinkRenderer:
    """Renders calendar + todos + quote for e-ink displays in B&W."""

    def __init__(self):
        self.width = EINK_WIDTH
        self.height = EINK_HEIGHT
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts - Avenir on macOS, DejaVu/Noto/Liberation on Linux/Docker."""
        avenir_path = "/System/Library/Fonts/Avenir Next.ttc"

        if Path(avenir_path).exists():
            # Index 5 = Medium, good for e-ink contrast
            self.month_font = ImageFont.truetype(avenir_path, MONTH_FONT_SIZE, index=5)
            self.date_font = ImageFont.truetype(avenir_path, DATE_FONT_SIZE, index=7)
            self.highlight_font = ImageFont.truetype(avenir_path, DATE_FONT_SIZE, index=2)
            self.quote_font = ImageFont.truetype(avenir_path, QUOTE_FONT_SIZE, index=4)
            self.quote_author_font = ImageFont.truetype(avenir_path, QUOTE_AUTHOR_SIZE, index=7)
            self.todo_header_font = ImageFont.truetype(avenir_path, TODO_HEADER_SIZE, index=2)
            self.todo_font = ImageFont.truetype(avenir_path, QUOTE_FONT_SIZE, index=7)
            return

        fallbacks = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in fallbacks:
            if Path(path).exists():
                self.month_font = ImageFont.truetype(path, MONTH_FONT_SIZE)
                self.date_font = ImageFont.truetype(path, DATE_FONT_SIZE)
                self.highlight_font = self.date_font
                self.quote_font = ImageFont.truetype(path, QUOTE_FONT_SIZE)
                self.quote_author_font = ImageFont.truetype(path, QUOTE_AUTHOR_SIZE)
                self.todo_header_font = ImageFont.truetype(path, TODO_HEADER_SIZE)
                self.todo_font = ImageFont.truetype(path, QUOTE_FONT_SIZE)
                return

        self.month_font = ImageFont.load_default()
        self.date_font = ImageFont.load_default()
        self.highlight_font = ImageFont.load_default()
        self.quote_font = ImageFont.load_default()
        self.quote_author_font = ImageFont.load_default()
        self.todo_header_font = ImageFont.load_default()
        self.todo_font = ImageFont.load_default()

    def _get_text_dimensions(
        self, draw: ImageDraw.ImageDraw, text: str, font
    ) -> Tuple[int, int, int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[0], bbox[1]

    def _get_spaced_text_width(
        self, draw: ImageDraw.ImageDraw, text: str, font, spacing: int
    ) -> int:
        total = 0
        for i, char in enumerate(text):
            total += draw.textbbox((0, 0), char, font=font)[2]
            if i < len(text) - 1:
                total += spacing
        return total

    def _draw_spaced_text(
        self, draw: ImageDraw.ImageDraw, pos: Tuple[int, int], text: str, font, fill, spacing: int
    ):
        x, y = pos
        for char in text:
            draw.text((x, y), char, font=font, fill=fill)
            x += draw.textbbox((0, 0), char, font=font)[2] + spacing

    def _wrap_text(self, text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        words = text.replace("\n", " ").split()
        lines: list[str] = []
        current_line: list[str] = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def _truncate_text(
        self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int
    ) -> str:
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text
        trimmed = text
        while trimmed and draw.textbbox((0, 0), f"{trimmed}...", font=font)[2] > max_width:
            trimmed = trimmed[:-1]
        return f"{trimmed}..." if trimmed else "..."

    def _draw_section_banner(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        label: str,
        bg_color,
        ink,
    ) -> int:
        """Draw a full-width inverted section banner. Returns y below the banner."""
        draw.rectangle([0, y, self.width, y + SECTION_BANNER_H], fill=ink)
        _, th, _, toy = self._get_text_dimensions(draw, label, self.todo_header_font)
        text_y = y + (SECTION_BANNER_H - th) // 2 - toy
        draw.text((MARGIN_X, text_y), label, font=self.todo_header_font, fill=bg_color)
        return y + SECTION_BANNER_H + SECTION_BANNER_GAP

    def _draw_task_row(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        task: str,
        col_width: int,
        text_color,
        line_h: int,
    ) -> None:
        """Draw one checkbox + truncated task label in a column."""
        box_y = y + (line_h - CHECKBOX_SIZE) // 2
        draw.rectangle(
            [x, box_y, x + CHECKBOX_SIZE, box_y + CHECKBOX_SIZE],
            outline=text_color,
            width=2,
        )
        text_x = x + CHECKBOX_SIZE + CHECKBOX_GAP
        max_text_width = col_width - CHECKBOX_SIZE - CHECKBOX_GAP
        line = self._truncate_text(draw, task, self.todo_font, max_text_width)
        _, th, _, toy = self._get_text_dimensions(draw, line, self.todo_font)
        text_y = y + (line_h - th) // 2 - toy
        draw.text((text_x, text_y), line, font=self.todo_font, fill=text_color)

    def _estimate_quote_height(
        self,
        draw: ImageDraw.ImageDraw,
        quote_text: Optional[str],
        quote_author: Optional[str],
    ) -> int:
        if not quote_text:
            return 0
        max_quote_width = self.width - (MARGIN_X * 2)
        clean = quote_text.replace("*", "").replace("_", "").strip()
        lines = self._wrap_text(f'"{clean}"', self.quote_font, max_quote_width, draw)
        lines = lines[:6]
        line_h = int(QUOTE_FONT_SIZE * QUOTE_LINE_HEIGHT)
        h = SECTION_BANNER_H + SECTION_BANNER_GAP + len(lines) * line_h
        if quote_author and quote_author != "Unknown":
            h += int(QUOTE_AUTHOR_SIZE * QUOTE_LINE_HEIGHT) + 4
        return h

    def render(
        self,
        calendar_data: CalendarData,
        output_path: Optional[Path] = None,
        invert: bool = False,
        quote_text: Optional[str] = None,
        quote_author: Optional[str] = None,
        todos: Optional[List[str]] = None,
    ) -> Image.Image:
        """
        Render B&W calendar + today tasks + quote for e-ink.

        Args:
            calendar_data: Calendar data
            output_path: Save path (.bmp)
            invert: If True, black background / white ink
            quote_text: Optional Readwise quote
            quote_author: Optional author attribution
            todos: Optional list of today task strings
        """
        bg_color = WHITE if not invert else BLACK
        text_color = BLACK if not invert else WHITE

        img = Image.new("RGB", (self.width, self.height), bg_color)
        draw = ImageDraw.Draw(img)

        todos = (todos or [])[:MAX_TODO_ITEMS]
        top_margin = int(self.height * TOP_MARGIN)
        bottom_margin = int(self.height * BOTTOM_MARGIN)

        # --- Measure sections to size the calendar ---
        letter_spacing = 4
        month_text = f"{calendar_data.month_name.upper()} {calendar_data.year}"
        _, month_h, _, _ = self._get_text_dimensions(draw, month_text, self.month_font)
        month_block = month_h + 16

        quote_block = self._estimate_quote_height(draw, quote_text, quote_author)
        if quote_text:
            quote_block += SECTION_GAP

        # Todo block: banner + rows (2 columns)
        todo_block = 0
        todo_line_h = int(QUOTE_FONT_SIZE * TODO_LINE_MIN)
        if todos:
            n_rows = (len(todos) + 1) // 2
            todo_block = (
                SECTION_BANNER_H
                + SECTION_BANNER_GAP
                + n_rows * todo_line_h
                + SECTION_GAP
            )

        # Calendar gets remaining vertical space
        num_rows = len(calendar_data.grid) + 1  # +1 weekday header row
        available = (
            self.height
            - top_margin
            - bottom_margin
            - month_block
            - todo_block
            - quote_block
        )
        cell_height = max(MIN_CELL_HEIGHT, min(MAX_CELL_HEIGHT, available // num_rows))
        # If still short, compress todo line height toward TODO_LINE_MIN floor
        used = month_block + num_rows * cell_height + todo_block + quote_block
        slack = self.height - top_margin - bottom_margin - used
        if slack < 0 and todos:
            # shrink todo lines slightly
            n_rows = (len(todos) + 1) // 2
            shrink = min(-slack, n_rows * (todo_line_h - int(QUOTE_FONT_SIZE * 1.1)))
            if n_rows > 0:
                todo_line_h = max(int(QUOTE_FONT_SIZE * 1.1), todo_line_h - shrink // n_rows)

        # --- Month / Year ---
        current_y = top_margin
        spaced_width = self._get_spaced_text_width(
            draw, month_text, self.month_font, letter_spacing
        )
        _, text_h, _, off_y = self._get_text_dimensions(draw, month_text, self.month_font)
        month_x = (self.width - spaced_width) // 2
        month_y = current_y + (month_block - text_h) // 2 - off_y
        self._draw_spaced_text(
            draw, (month_x, month_y), month_text, self.month_font, text_color, letter_spacing
        )
        current_y += month_block

        # --- Calendar grid ---
        grid_top = current_y
        cell_width = self.width // 7

        today_col = None
        if calendar_data.today_position:
            _, today_col = calendar_data.today_position

        for col, header in enumerate(calendar_data.weekday_headers):
            short = header[0]
            font = self.highlight_font if col == today_col else self.date_font
            hw, hh, hox, hoy = self._get_text_dimensions(draw, short, font)
            hx = col * cell_width + (cell_width - hw) // 2 - hox
            hy = grid_top + (cell_height - hh) // 2 - hoy
            draw.text((hx, hy), short, font=font, fill=text_color)

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
                    dw, dh, dox, doy = self._get_text_dimensions(
                        draw, day_text, self.highlight_font
                    )
                    radius = max(dw, dh) // 2 + 8
                    draw.ellipse(
                        [
                            center_x - radius,
                            center_y - radius,
                            center_x + radius,
                            center_y + radius,
                        ],
                        fill=text_color,
                    )
                    tx = center_x - dw // 2 - dox
                    ty = center_y - dh // 2 - doy
                    draw.text((tx, ty), day_text, font=self.highlight_font, fill=bg_color)
                else:
                    dw, dh, dox, doy = self._get_text_dimensions(
                        draw, day_text, self.date_font
                    )
                    tx = center_x - dw // 2 - dox
                    ty = center_y - dh // 2 - doy
                    draw.text((tx, ty), day_text, font=self.date_font, fill=text_color)

        current_y = dates_top + len(calendar_data.grid) * cell_height + SECTION_GAP

        # --- TODAY tasks ---
        if todos:
            current_y = self._draw_section_banner(
                draw, current_y, "TODAY", bg_color, text_color
            )
            col_width = (self.width - 2 * MARGIN_X - TODO_COL_GAP) // 2
            for i, task in enumerate(todos):
                col = i % 2
                row = i // 2
                x = MARGIN_X + col * (col_width + TODO_COL_GAP)
                y = current_y + row * todo_line_h
                self._draw_task_row(
                    draw, x, y, task, col_width, text_color, todo_line_h
                )
            n_rows = (len(todos) + 1) // 2
            current_y += n_rows * todo_line_h + SECTION_GAP

        # --- Quote ---
        if quote_text:
            current_y = self._draw_section_banner(
                draw, current_y, "QUOTE", bg_color, text_color
            )
            max_quote_width = self.width - (MARGIN_X * 2)
            clean_quote = quote_text.replace("*", "").replace("_", "").strip()
            quote_lines = self._wrap_text(
                f'"{clean_quote}"', self.quote_font, max_quote_width, draw
            )
            if len(quote_lines) > 6:
                quote_lines = quote_lines[:6]
                quote_lines[-1] = quote_lines[-1].rstrip(".\"") + '..."'

            line_height = int(QUOTE_FONT_SIZE * QUOTE_LINE_HEIGHT)
            for line in quote_lines:
                draw.text((MARGIN_X, current_y), line, font=self.quote_font, fill=text_color)
                current_y += line_height

            if quote_author and quote_author != "Unknown":
                current_y += 4
                author_text = f"— {quote_author}"
                draw.text(
                    (MARGIN_X, current_y),
                    author_text,
                    font=self.quote_author_font,
                    fill=text_color,
                )

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "BMP")

        return img


def generate_eink(
    date_str: Optional[str] = None,
    output_dir: Optional[Path] = None,
    include_quote: bool = True,
    include_todos: bool = True,
) -> Path:
    """Generate e-ink wallpaper with calendar, Todoist Today tasks, and Readwise quote."""
    from datetime import datetime

    import pytz

    from .calendar_engine import CalendarEngine
    from .config import DEFAULT_TIMEZONE

    engine = CalendarEngine()

    if date_str:
        parts = [int(x) for x in date_str.split("-")]
        tz = pytz.timezone(DEFAULT_TIMEZONE)
        target = tz.localize(datetime(*parts))
        cal_data = engine.generate(target)
    else:
        cal_data = engine.generate()

    today_day = cal_data.grid[cal_data.today_position[0]][cal_data.today_position[1]].day
    date_key = f"{cal_data.year}-{cal_data.month:02d}-{today_day:02d}"

    quote_text = None
    quote_author = None
    if include_quote:
        try:
            from .readwise import get_quote_for_date

            quote = get_quote_for_date(date_key)
            quote_text = quote.text
            quote_author = quote.author
        except Exception as e:
            print(f"Could not fetch quote: {e}")

    todos: List[str] = []
    if include_todos:
        try:
            from .todoist import get_today_tasks

            todos = [t.content for t in get_today_tasks(MAX_TODO_ITEMS)]
            print(f"Loaded {len(todos)} Todoist task(s) for today")
        except Exception as e:
            print(f"Could not fetch Todoist tasks: {e}")

    renderer = EinkRenderer()
    output_dir = output_dir or OUTPUT_EINK_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    output_filename = f"eink_{date_key}.bmp"
    output_path = output_dir / output_filename

    renderer.render(
        cal_data,
        output_path=output_path,
        quote_text=quote_text,
        quote_author=quote_author,
        todos=todos,
    )

    latest_link = output_dir / "latest.bmp"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(output_filename)

    return output_path


if __name__ == "__main__":
    path = generate_eink()
    print(f"E-ink wallpaper saved to: {path}")
