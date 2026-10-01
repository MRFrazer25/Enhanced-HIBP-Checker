import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    """
    Initializes and runs the PyQt6 application.
    Sets up the main window and starts the application event loop.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Enhanced HIBP Checker")
    app.setStyle("Fusion")  # Consistent look across platforms that works well with the dark stylesheet
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
