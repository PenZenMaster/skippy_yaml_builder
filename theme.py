"""
Module/Script Name: theme.py
Path: E:\\projects\\skippy_yaml_builder\\theme.py

Description:
Centralized button color/style system -- one semantic style per action
category (success, export, import, danger, secondary) instead of
hand-rolled inline stylesheets per button. Adapted from the pattern in
the sibling cloud-stack-generator project's src/ui/themes/default_theme.py,
with one change: that project's tabs don't consistently use its own
ThemeManager (several hardcode near-duplicate inline styles instead) --
this module is meant to be the ONLY place a button style is defined, so
that inconsistency doesn't get repeated here.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-08-25

Last Modified Date:
2026-08-25

Comments:
- v1.00 Initial implementation.
"""


class ColorPalette:
    SUCCESS_GREEN = "#28a745"
    SUCCESS_GREEN_HOVER = "#218838"
    SUCCESS_GREEN_PRESSED = "#1e7e34"

    EXPORT_BLUE = "#3498db"
    EXPORT_BLUE_HOVER = "#2980b9"
    EXPORT_BLUE_PRESSED = "#216696"

    IMPORT_GREEN = "#27ae60"
    IMPORT_GREEN_HOVER = "#219a52"
    IMPORT_GREEN_PRESSED = "#1d8743"

    DANGER_RED = "#e74c3c"
    DANGER_RED_HOVER = "#c0392b"
    DANGER_RED_PRESSED = "#962d20"

    SECONDARY_GRAY = "#6c757d"
    SECONDARY_GRAY_HOVER = "#5a6268"
    SECONDARY_GRAY_PRESSED = "#495057"

    DISABLED_GRAY = "#95a5a6"
    WHITE = "#ffffff"


_BUTTON_TEMPLATE = """
    QPushButton {{
        background-color: {color};
        color: {text_color};
        font-family: Arial;
        font-size: 10pt;
        font-weight: bold;
        padding: 6px 14px;
        border: none;
        border-radius: 4px;
    }}
    QPushButton:hover {{
        background-color: {hover_color};
    }}
    QPushButton:pressed {{
        background-color: {pressed_color};
    }}
    QPushButton:disabled {{
        background-color: {disabled_color};
        color: {text_color};
    }}
"""


def _button_style(color: str, hover_color: str, pressed_color: str) -> str:
    return _BUTTON_TEMPLATE.format(
        color=color,
        hover_color=hover_color,
        pressed_color=pressed_color,
        text_color=ColorPalette.WHITE,
        disabled_color=ColorPalette.DISABLED_GRAY,
    )


class ButtonStyles:
    """One style per semantic action category -- see ThemeManager.BUTTON_STYLES
    for which skippy buttons use which."""

    SUCCESS = _button_style(
        ColorPalette.SUCCESS_GREEN, ColorPalette.SUCCESS_GREEN_HOVER, ColorPalette.SUCCESS_GREEN_PRESSED
    )
    EXPORT = _button_style(
        ColorPalette.EXPORT_BLUE, ColorPalette.EXPORT_BLUE_HOVER, ColorPalette.EXPORT_BLUE_PRESSED
    )
    IMPORT = _button_style(
        ColorPalette.IMPORT_GREEN, ColorPalette.IMPORT_GREEN_HOVER, ColorPalette.IMPORT_GREEN_PRESSED
    )
    DANGER = _button_style(
        ColorPalette.DANGER_RED, ColorPalette.DANGER_RED_HOVER, ColorPalette.DANGER_RED_PRESSED
    )
    SECONDARY = _button_style(
        ColorPalette.SECONDARY_GRAY, ColorPalette.SECONDARY_GRAY_HOVER, ColorPalette.SECONDARY_GRAY_PRESSED
    )


class ThemeManager:
    BUTTON_STYLES = {
        "success": ButtonStyles.SUCCESS,
        "export": ButtonStyles.EXPORT,
        "import": ButtonStyles.IMPORT,
        "danger": ButtonStyles.DANGER,
        "secondary": ButtonStyles.SECONDARY,
    }

    @staticmethod
    def apply_button_style(button, style_name: str) -> None:
        style_name = style_name.lower()
        if style_name not in ThemeManager.BUTTON_STYLES:
            raise ValueError(
                f"Unknown button style: {style_name}. "
                f"Available styles: {', '.join(ThemeManager.BUTTON_STYLES.keys())}"
            )
        button.setStyleSheet(ThemeManager.BUTTON_STYLES[style_name])
