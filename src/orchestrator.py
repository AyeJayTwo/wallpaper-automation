"""Orchestrator - Coordinates the wallpaper generation pipeline."""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .calendar_engine import CalendarEngine
from .render_engine import RenderEngine
from .validator import Validator, ValidationResult
from .config import OUTPUT_DIR, BACKGROUNDS_DIR, DEFAULT_TIMEZONE


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when the pipeline fails."""
    pass


class Orchestrator:
    """
    Coordinates the wallpaper generation pipeline.

    Pipeline: Calendar Engine → Render Engine → Validator → Delivery
    """

    def __init__(self, timezone: str = DEFAULT_TIMEZONE):
        self.calendar_engine = CalendarEngine(timezone)
        self.render_engine = RenderEngine()
        self.validator = Validator()
        self.timezone = timezone

    def _get_output_filename(self, date: datetime) -> str:
        """Generate deterministic filename for a date."""
        return f"wallpaper_{date.strftime('%Y-%m-%d')}.png"

    def _select_background(self, date: datetime) -> Optional[Path]:
        """
        Select background for the given date.

        Currently uses default background. Can be extended for:
        - Day-of-week backgrounds
        - Seasonal backgrounds
        - Random selection from pool
        """
        # Check for date-specific background
        date_bg = BACKGROUNDS_DIR / f"{date.strftime('%Y-%m-%d')}.png"
        if date_bg.exists():
            return date_bg

        # Check for day-of-week background
        weekday_bg = BACKGROUNDS_DIR / f"{date.strftime('%A').lower()}.png"
        if weekday_bg.exists():
            return weekday_bg

        # Check for month background
        month_bg = BACKGROUNDS_DIR / f"{date.strftime('%B').lower()}.png"
        if month_bg.exists():
            return month_bg

        # Default background
        default_bg = BACKGROUNDS_DIR / "default.png"
        if default_bg.exists():
            return default_bg

        # No background found - will use placeholder
        return None

    def run(
        self,
        target_date: Optional[datetime] = None,
        output_dir: Optional[Path] = None,
        background: Optional[Path] = None,
        fail_fast: bool = True
    ) -> Path:
        """
        Run the complete wallpaper generation pipeline.

        Args:
            target_date: Date to generate wallpaper for (default: today)
            output_dir: Directory to save output (default: OUTPUT_DIR)
            background: Custom background image path
            fail_fast: If True, raise on validation errors

        Returns:
            Path to generated wallpaper

        Raises:
            PipelineError: If pipeline fails and fail_fast is True
        """
        output_dir = output_dir or OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Get target date
        if target_date is None:
            target_date = self.calendar_engine.get_current_date()
        logger.info(f"Generating wallpaper for: {target_date.strftime('%Y-%m-%d')}")

        # Step 2: Generate calendar data
        logger.info("Running Calendar Engine...")
        calendar_data = self.calendar_engine.generate(target_date)
        logger.info(f"Calendar: {calendar_data.month_name} {calendar_data.year}")

        # Step 3: Select background
        if background is None:
            background = self._select_background(target_date)
        if background:
            logger.info(f"Using background: {background}")
        else:
            logger.info("Using placeholder background")

        # Step 4: Render wallpaper
        logger.info("Running Render Engine...")
        output_filename = self._get_output_filename(target_date)
        output_path = output_dir / output_filename
        self.render_engine.render(
            calendar_data,
            background_path=background,
            output_path=output_path
        )
        logger.info(f"Rendered to: {output_path}")

        # Step 5: Validate output
        logger.info("Running Validator...")
        validation_result = self.validator.validate_all(
            calendar_data,
            output_path,
            expected_date=target_date
        )

        if validation_result.warnings:
            for warning in validation_result.warnings:
                logger.warning(warning)

        if not validation_result.is_valid:
            for error in validation_result.errors:
                logger.error(error)
            if fail_fast:
                raise PipelineError(f"Validation failed: {validation_result.errors}")

        logger.info("Validation passed!")

        # Step 6: Create "latest" symlink for easy access
        latest_link = output_dir / "latest.png"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(output_path.name)
        logger.info(f"Updated latest symlink: {latest_link}")

        logger.info("Pipeline complete!")
        return output_path

    def run_for_date(
        self,
        year: int,
        month: int,
        day: int,
        **kwargs
    ) -> Path:
        """Run pipeline for a specific date."""
        import pytz
        tz = pytz.timezone(self.timezone)
        target_date = tz.localize(datetime(year, month, day))
        return self.run(target_date=target_date, **kwargs)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate calendar wallpaper for iPhone"
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Target date (YYYY-MM-DD format). Default: today'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory. Default: ./output'
    )
    parser.add_argument(
        '--background',
        type=str,
        help='Custom background image path'
    )
    parser.add_argument(
        '--timezone',
        type=str,
        default=DEFAULT_TIMEZONE,
        help=f'Timezone. Default: {DEFAULT_TIMEZONE}'
    )
    parser.add_argument(
        '--no-fail-fast',
        action='store_true',
        help='Continue on validation errors'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--eink',
        action='store_true',
        help='Generate B&W wallpaper for e-ink displays (480x800 BMP)'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle e-ink mode separately
    if args.eink:
        from .eink_renderer import generate_eink
        output_dir = Path(args.output_dir) if args.output_dir else None
        try:
            output_path = generate_eink(date_str=args.date, output_dir=output_dir)
            print(f"\nE-ink wallpaper saved to: {output_path}")
            sys.exit(0)
        except Exception as e:
            logger.exception(f"E-ink generation failed: {e}")
            sys.exit(1)

    orchestrator = Orchestrator(timezone=args.timezone)

    # Parse date if provided
    target_date = None
    if args.date:
        import pytz
        try:
            date_parts = [int(x) for x in args.date.split('-')]
            tz = pytz.timezone(args.timezone)
            target_date = tz.localize(datetime(*date_parts))
        except ValueError as e:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)

    # Parse output dir
    output_dir = Path(args.output_dir) if args.output_dir else None

    # Parse background
    background = Path(args.background) if args.background else None

    try:
        output_path = orchestrator.run(
            target_date=target_date,
            output_dir=output_dir,
            background=background,
            fail_fast=not args.no_fail_fast
        )
        print(f"\nWallpaper saved to: {output_path}")
        sys.exit(0)
    except PipelineError as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
