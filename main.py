import sys
from PySide6.QtWidgets import QApplication
from app.dashboard import Dashboard

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PSN Live Code Detector")
    window = Dashboard()
    window.show()
    sys.exit(app.exec())
