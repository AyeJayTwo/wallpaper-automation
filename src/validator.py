"""Validator - Ensures output correctness."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image

from .calendar_engine import CalendarData
from .config import WIDTH, HEIGHT


@dataclass
class ValidationResult:
    """Result of validation checks."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def __str__(self):
        status = "VALID" if self.is_valid else "INVALID"
        lines = [f"Validation: {status}"]
        if self.errors:
            lines.append("Errors:")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


class Validator:
    """Validates calendar data and rendered output."""

    def __init__(self):
        self.expected_width = WIDTH
        self.expected_height = HEIGHT

    def validate_calendar_data(
        self,
        calendar_data: CalendarData,
        expected_date: Optional[datetime] = None
    ) -> ValidationResult:
        """
        Validate calendar data for correctness.

        Args:
            calendar_data: Calendar data to validate
            expected_date: If provided, verify the date matches

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Check month name matches month number
        import calendar
        expected_month_name = calendar.month_name[calendar_data.month]
        if calendar_data.month_name != expected_month_name:
            errors.append(
                f"Month name mismatch: got '{calendar_data.month_name}', "
                f"expected '{expected_month_name}'"
            )

        # Check year is reasonable
        current_year = datetime.now().year
        if not (current_year - 1 <= calendar_data.year <= current_year + 1):
            warnings.append(f"Year {calendar_data.year} seems unusual")

        # Check grid structure
        if not calendar_data.grid:
            errors.append("Calendar grid is empty")
        else:
            # Should have 4-6 weeks
            if not (4 <= len(calendar_data.grid) <= 6):
                errors.append(f"Invalid grid rows: {len(calendar_data.grid)}")

            # Each week should have 7 days
            for i, week in enumerate(calendar_data.grid):
                if len(week) != 7:
                    errors.append(f"Week {i} has {len(week)} days, expected 7")

        # Check today's position exists and is valid
        if calendar_data.today_position is None:
            errors.append("Today's position not set")
        else:
            row, col = calendar_data.today_position
            if row < 0 or row >= len(calendar_data.grid):
                errors.append(f"Today's row {row} out of bounds")
            elif col < 0 or col >= 7:
                errors.append(f"Today's column {col} out of bounds")
            else:
                # Verify the day at today's position is marked as today
                day = calendar_data.grid[row][col]
                if not day.is_today:
                    errors.append("Day at today_position is not marked as is_today")
                if day.day == 0:
                    errors.append("Today's position points to empty cell")

        # Validate against expected date if provided
        if expected_date:
            if calendar_data.year != expected_date.year:
                errors.append(
                    f"Year mismatch: got {calendar_data.year}, "
                    f"expected {expected_date.year}"
                )
            if calendar_data.month != expected_date.month:
                errors.append(
                    f"Month mismatch: got {calendar_data.month}, "
                    f"expected {expected_date.month}"
                )
            if calendar_data.today_position:
                row, col = calendar_data.today_position
                today_day = calendar_data.grid[row][col].day
                if today_day != expected_date.day:
                    errors.append(
                        f"Day mismatch: got {today_day}, "
                        f"expected {expected_date.day}"
                    )

        # Check weekday headers
        if len(calendar_data.weekday_headers) != 7:
            errors.append(
                f"Invalid weekday headers count: {len(calendar_data.weekday_headers)}"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_image(self, image_path: Path) -> ValidationResult:
        """
        Validate rendered wallpaper image.

        Args:
            image_path: Path to the rendered image

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Check file exists
        if not image_path.exists():
            errors.append(f"Image file does not exist: {image_path}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check file size (should be reasonable, not empty or corrupted)
        file_size = image_path.stat().st_size
        if file_size < 1000:  # Less than 1KB is suspicious
            errors.append(f"Image file too small ({file_size} bytes), may be corrupted")
        elif file_size > 50_000_000:  # More than 50MB is suspicious
            warnings.append(f"Image file unusually large ({file_size / 1_000_000:.1f} MB)")

        try:
            img = Image.open(image_path)

            # Check dimensions
            width, height = img.size
            if width != self.expected_width:
                errors.append(
                    f"Width mismatch: got {width}, expected {self.expected_width}"
                )
            if height != self.expected_height:
                errors.append(
                    f"Height mismatch: got {height}, expected {self.expected_height}"
                )

            # Check format
            if img.format != 'PNG':
                warnings.append(f"Unexpected format: {img.format}, expected PNG")

            # Check mode (should be RGB or RGBA)
            if img.mode not in ('RGB', 'RGBA'):
                warnings.append(f"Unexpected mode: {img.mode}")

            # Verify image can be fully loaded (catches truncation)
            img.load()

        except Exception as e:
            errors.append(f"Failed to open/read image: {e}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_all(
        self,
        calendar_data: CalendarData,
        image_path: Path,
        expected_date: Optional[datetime] = None
    ) -> ValidationResult:
        """
        Run all validations.

        Returns combined ValidationResult.
        """
        all_errors = []
        all_warnings = []

        # Validate calendar data
        cal_result = self.validate_calendar_data(calendar_data, expected_date)
        all_errors.extend(cal_result.errors)
        all_warnings.extend(cal_result.warnings)

        # Validate image
        img_result = self.validate_image(image_path)
        all_errors.extend(img_result.errors)
        all_warnings.extend(img_result.warnings)

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings
        )


if __name__ == "__main__":
    from .calendar_engine import CalendarEngine

    # Test validation
    engine = CalendarEngine()
    data = engine.generate()

    validator = Validator()
    result = validator.validate_calendar_data(data)
    print(result)
