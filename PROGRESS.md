# Wallpaper Automation - Project Progress

## Summary

A deterministic calendar wallpaper generator that creates daily wallpapers for iPhone and e-ink devices. The system generates wallpapers with the current month's calendar, highlighting today's date, with past days dimmed.

**Repository**: https://github.com/AyeJayTwo/wallpaper-automation

---

## Completed Features

### Core Pipeline
- [x] **Calendar Engine** - Generates month grid with timezone awareness, Monday-start weeks
- [x] **Render Engine** - Creates iPhone 16 Pro wallpapers (1320x2868 PNG)
- [x] **Validator** - Ensures date correctness, dimensions, and file integrity
- [x] **Orchestrator** - Coordinates pipeline with CLI interface

### Visual Design (iPhone)
- [x] Deep forest green gradient background
- [x] Avenir Next Ultra Light typography
- [x] ALL CAPS month with 12px letter spacing
- [x] Amber gold highlight for today (Medium weight for visibility)
- [x] Past days rendered in light grey
- [x] Weekend days subtly dimmed
- [x] 3 background variants: forest green, deep ocean, midnight

### E-Ink Support
- [x] 480x800 resolution, 24-bit uncompressed BMP
- [x] Black & white optimized for e-ink contrast
- [x] Today's weekday header in bold black for quick scanning
- [x] Black circle highlight with inverted text
- [x] `--eink` CLI flag

### Automation
- [x] CLI with `--date`, `--eink`, `--output-dir` options
- [x] Cron scheduling script (`scripts/daily_generate.sh`)
- [x] iOS Shortcuts integration (`scripts/deliver_to_shortcuts.py`)
- [x] Documentation for cron and Shortcuts setup

---

## Outstanding Tasks

### Not Yet Implemented
- [ ] Actual cron job installation (script exists, not activated)
- [ ] iOS Shortcut creation (documentation exists, needs manual setup on device)
- [ ] iCloud delivery testing (script exists, needs iCloud path verification)

### Known Limitations
- Font loading relies on macOS system fonts (Avenir Next) - won't work on Linux without font installation
- E-ink renderer doesn't support custom backgrounds (intentional for B&W)
- No automated testing suite yet

---

## Technical Notes

### File Structure
```
├── generate.py              # Main entry point
├── src/
│   ├── calendar_engine.py   # Date/calendar logic
│   ├── render_engine.py     # iPhone wallpaper rendering
│   ├── eink_renderer.py     # E-ink display rendering
│   ├── validator.py         # Output validation
│   ├── orchestrator.py      # Pipeline coordination + CLI
│   └── config.py            # All configuration constants
├── scripts/
│   ├── daily_generate.sh    # Cron automation script
│   └── deliver_to_shortcuts.py  # iCloud delivery
├── assets/
│   └── backgrounds/         # Generated gradient backgrounds
├── output/                  # Generated wallpapers
└── docs/                    # Setup guides
```

### Key Design Decisions
1. **Deterministic output** - Same date always produces identical wallpaper
2. **Separation of concerns** - Calendar logic, rendering, and validation are independent
3. **Fail-fast validation** - Pipeline stops on errors by default
4. **Font weight strategy** - Ultra Light for elegance, Medium for emphasis (highlight)

### Font Indices (Avenir Next.ttc)
- Index 10: Ultra Light (main text)
- Index 7: Regular
- Index 5: Medium (highlighted date)
- Index 2: Demi Bold (e-ink highlight)

---

## Suggestions for Future Improvements

### High Impact
1. **Month transition handling** - Generate wallpapers that show previous/next month days in the grid (currently shows empty cells)
2. **Widget-aware layout** - Option to position calendar to avoid iOS clock/widgets
3. **Batch generation script** - Generate a month's worth of wallpapers in advance

### E-Ink Enhancements
4. **Multiple e-ink resolutions** - Support common sizes (600x800, 758x1024, etc.)
5. **Dithering options** - For e-ink displays that support grayscale
6. **Landscape mode** - Rotated layout for horizontal displays

### Automation
7. **Systemd/launchd service** - More robust than cron for always-on generation
8. **Push notification on failure** - Alert when generation fails
9. **Web endpoint** - Simple Flask/FastAPI server to fetch today's wallpaper

### Visual
10. **Theme system** - Easy switching between color palettes
11. **Custom highlight shapes** - Rounded rect, underline, outline options
12. **Holiday/event markers** - Subtle dots for calendar events
13. **Seasonal backgrounds** - Auto-switch backgrounds by month/season

### Code Quality
14. **Unit tests** - Test calendar logic, date edge cases
15. **CI/CD pipeline** - Auto-generate and validate on push
16. **Docker container** - Portable execution without font dependencies
17. **Config file support** - YAML/JSON config instead of Python constants

---

## Usage Quick Reference

```bash
# iPhone wallpaper (today)
python generate.py

# iPhone wallpaper (specific date)
python generate.py --date 2026-02-14

# E-ink wallpaper
python generate.py --eink

# E-ink with date range (bash)
for d in 01 02 03; do python generate.py --eink --date "2026-02-$d"; done

# See all options
python generate.py --help
```

---

*Last updated: 2026-02-03*
