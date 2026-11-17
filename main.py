"""
JARVIS AI Desktop Assistant
Main entry point - initializes and launches the application.
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Initialize configuration and logging first
from config import setup_logging, ASSISTANT_NAME
logger = setup_logging()
logger.info(f"Starting {ASSISTANT_NAME} AI Desktop Assistant...")

from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QRadialGradient

def create_splash_pixmap() -> QPixmap:
    """Create a stylish splash screen."""
    pixmap = QPixmap(600, 400)
    pixmap.fill(QColor("#0a0e1a"))
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw gradient circle (the orb)
    gradient = QRadialGradient(300, 200, 100)
    gradient.setColorAt(0, QColor("#00bcd4"))
    gradient.setColorAt(0.5, QColor("#1565c0"))
    gradient.setColorAt(1, QColor("#0a0e1a"))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(200, 100, 200, 200)
    
    # Draw title
    font = QFont("Segoe UI", 32, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#00bcd4"))
    painter.drawText(0, 320, 600, 40, Qt.AlignmentFlag.AlignCenter, "JARVIS")
    
    # Draw subtitle
    font2 = QFont("Segoe UI", 11)
    painter.setFont(font2)
    painter.setPen(QColor("#64748b"))
    painter.drawText(0, 355, 600, 30, Qt.AlignmentFlag.AlignCenter, "AI Desktop Assistant")
    
    painter.end()
    return pixmap


def check_dependencies() -> list[str]:
    """Check that critical dependencies are available."""
    missing = []
    
    try:
        import PySide6
    except ImportError:
        missing.append("PySide6 (UI framework) - run: python -m pip install PySide6")
    
    try:
        import ollama
    except ImportError:
        missing.append("ollama (AI engine) - run: python -m pip install ollama")
    
    try:
        import sqlalchemy
    except ImportError:
        missing.append("SQLAlchemy (database) - run: python -m pip install SQLAlchemy")
    
    try:
        import psutil
    except ImportError:
        missing.append("psutil (system monitor) - run: python -m pip install psutil")
    
    return missing


def main():
    """Main application entry point."""
    # Check critical dependencies
    missing = check_dependencies()
    if missing:
        print("JARVIS: Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nPlease install missing dependencies and restart.")
        sys.exit(1)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName(ASSISTANT_NAME)
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("JARVIS")
    
    # Set application-wide dark palette
    app.setStyle("Fusion")
    
    # Show splash screen
    splash_pix = create_splash_pixmap()
    splash = QSplashScreen(splash_pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()
    
    splash.showMessage(
        "Initializing JARVIS...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        QColor("#00bcd4")
    )
    app.processEvents()
    
    try:
        # Initialize database
        splash.showMessage("Loading database...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("#00bcd4"))
        app.processEvents()
        from memory.database import init_database
        init_database()
        
        # Initialize main window
        splash.showMessage("Building interface...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, QColor("#00bcd4"))
        app.processEvents()
        from ui.main_window import MainWindow
        window = MainWindow()
        
        # Close splash and show main window
        splash.finish(window)
        window.show()
        
        logger.info("JARVIS started successfully")
        sys.exit(app.exec())
        
    except Exception as e:
        splash.close()
        logger.exception(f"Fatal error during startup: {e}")
        
        # Show error dialog
        error_app = QApplication.instance()
        msg = QMessageBox()
        msg.setWindowTitle("JARVIS - Startup Error")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(f"JARVIS failed to start:\n\n{e}")
        msg.setDetailedText(
            "Check the logs directory for details.\n"
            "Common causes:\n"
            "- Missing dependencies (run install_dependencies.bat)\n"
            "- Corrupt database (delete data/jarvis.db)\n"
            "- Port conflict on 11434 (Ollama)"
        )
        msg.exec()
        sys.exit(1)


if __name__ == "__main__":
    main()
