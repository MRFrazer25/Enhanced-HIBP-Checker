"""
Defines the dark mode stylesheet for the PyQt6 application.

This module contains `DARK_MODE_STYLESHEET`, which includes CSS-like rules to
style various Qt widgets for a consistent dark theme, and `STATUS_COLORS` for
status messages.
"""

STATUS_COLORS = {
    "info": "#aaaaaa",
    "success": "#4caf50",
    "warning": "#ffb74d",
    "error": "#ef5350",
}

DARK_MODE_STYLESHEET = """
QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
    border: none;
    font-size: 10pt;
}

QTabWidget::pane {
    border-top: 1px solid #444444;
}

QTabBar::tab {
    background-color: #3c3c3c;
    color: #ffffff;
    padding: 8px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border: 1px solid #2b2b2b;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #2b2b2b;
    border: 1px solid #444444;
    border-bottom: 1px solid #2b2b2b; /* Match pane background */
}

QTabBar::tab:!selected {
    margin-top: 2px; /* make non-selected tabs look smaller */
}

QLineEdit {
    background-color: #3c3c3c;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 5px;
}

QLineEdit:focus {
    border: 1px solid #0078d7; /* Accent color on focus */
}

QComboBox {
    background-color: #3c3c3c; /* Match QLineEdit */
    color: #ffffff; /* Match QLineEdit */
    border: 1px solid #555555; /* Match QLineEdit */
    border-radius: 3px; /* Match QLineEdit */
    padding: 5px; /* Match QLineEdit */
    min-width: 6em; /* Ensure some minimum width */
}

/* Style for the dropdown list itself */
QComboBox QAbstractItemView {
    background-color: #3c3c3c;
    color: #ffffff;
    border: 1px solid #555555;
    selection-background-color: #0078d7; /* Accent color for selection */
}

/* Style for the dropdown arrow */
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-top-right-radius: 3px; 
    border-bottom-right-radius: 3px;
}

QPushButton {
    background-color: #0078d7; /* Primary button color */
    color: #ffffff;
    border: 1px solid #0078d7;
    border-radius: 3px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #005a9e;
    border: 1px solid #005a9e;
}

QPushButton:pressed {
    background-color: #00396e;
    border: 1px solid #00396e;
}

QPushButton:disabled {
    background-color: #3c3c3c;
    border: 1px solid #444444;
    color: #888888;
}

QPushButton#secondary {
    background-color: #3c3c3c;
    border: 1px solid #555555;
}

QPushButton#secondary:hover {
    background-color: #4a4a4a;
}

QPushButton#secondary:pressed {
    background-color: #555555;
}

QLineEdit:disabled {
    color: #888888;
}

QCheckBox {
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #888888;
    border-radius: 3px;
    background-color: #3c3c3c;
}

QCheckBox::indicator:hover {
    border: 1px solid #0078d7;
}

QCheckBox::indicator:checked {
    background-color: #0078d7;
    border: 1px solid #0078d7;
}

QGroupBox {
    border: 1px solid #444444;
    border-radius: 4px;
    margin-top: 14px;
    padding: 10px 8px 6px 8px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QGroupBox QLabel, QGroupBox QPushButton, QGroupBox QLineEdit, QGroupBox QComboBox, QGroupBox QCheckBox {
    font-weight: normal;
}

QTextEdit {
    background-color: #333333;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 5px;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}

QLabel {
    color: #cccccc;
    padding-top: 5px;
    padding-bottom: 2px;
}

/* Customize scrollbars for dark mode */
QScrollBar:vertical {
    border: 1px solid #444444;
    background: #3c3c3c;
    width: 12px;
    margin: 15px 0 15px 0;
    border-radius: 0px;
}

QScrollBar::handle:vertical {
    background-color: #5a5a5a;
    min-height: 30px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background-color: #6a6a6a;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    border: 1px solid #444444;
    background: #3c3c3c;
    height: 12px;
    margin: 0px 15px 0 15px;
    border-radius: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #5a5a5a;
    min-width: 30px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #6a6a6a;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}

QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
    background: none;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

""" 