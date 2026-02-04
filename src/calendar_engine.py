"""Calendar Engine - Generates calendar data for a given date."""
import calendar
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pytz

from .config import DEFAULT_TIMEZONE, WEEK_START_MONDAY


@dataclass
class CalendarDay:
    """Represents a single day in the calendar grid."""
    day: int  # 0 means empty cell
    is_today: bool = False
    row: int = 0
    col: int = 0


@dataclass
class CalendarData:
    """Complete calendar data for rendering."""
    year: int
    month: int
    month_name: str
    weekday_headers: List[str]
    grid: List[List[CalendarDay]]
    today_position: Optional[tuple]  # (row, col) of today


class CalendarEngine:
    """Generates deterministic calendar data for any given date."""

    def __init__(self, timezone: str = DEFAULT_TIMEZONE):
        self.timezone = pytz.timezone(timezone)
        # Set week start (0=Monday, 6=Sunday)
        self.week_start = 0 if WEEK_START_MONDAY else 6

    def get_current_date(self) -> datetime:
        """Get current date in configured timezone."""
        return datetime.now(self.timezone)

    def generate(self, target_date: Optional[datetime] = None) -> CalendarData:
        """
        Generate calendar data for a specific date.

        Args:
            target_date: Date to generate calendar for. Uses current date if None.

        Returns:
            CalendarData with complete month grid and today's position.
        """
        if target_date is None:
            target_date = self.get_current_date()

        year = target_date.year
        month = target_date.month
        today = target_date.day

        # Configure calendar for Monday start
        cal = calendar.Calendar(firstweekday=self.week_start)

        # Get month matrix (includes days from prev/next months as 0)
        month_days = cal.monthdayscalendar(year, month)

        # Build weekday headers
        if WEEK_START_MONDAY:
            weekday_headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        else:
            weekday_headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

        # Build grid with CalendarDay objects
        grid = []
        today_position = None

        for row_idx, week in enumerate(month_days):
            row = []
            for col_idx, day in enumerate(week):
                is_today = (day == today and day != 0)
                calendar_day = CalendarDay(
                    day=day,
                    is_today=is_today,
                    row=row_idx,
                    col=col_idx
                )
                row.append(calendar_day)

                if is_today:
                    today_position = (row_idx, col_idx)

            grid.append(row)

        # Get month name
        month_name = calendar.month_name[month]

        return CalendarData(
            year=year,
            month=month,
            month_name=month_name,
            weekday_headers=weekday_headers,
            grid=grid,
            today_position=today_position
        )

    def generate_for_date(self, year: int, month: int, day: int) -> CalendarData:
        """Generate calendar data for a specific date (for testing/determinism)."""
        target_date = self.timezone.localize(datetime(year, month, day))
        return self.generate(target_date)


if __name__ == "__main__":
    # Quick test
    engine = CalendarEngine()
    data = engine.generate()

    print(f"{data.month_name} {data.year}")
    print(" ".join(f"{h:>3}" for h in data.weekday_headers))

    for week in data.grid:
        row_str = ""
        for day in week:
            if day.day == 0:
                row_str += "    "
            elif day.is_today:
                row_str += f"[{day.day:2}]"
            else:
                row_str += f" {day.day:2} "
        print(row_str)

    print(f"\nToday's position: {data.today_position}")
