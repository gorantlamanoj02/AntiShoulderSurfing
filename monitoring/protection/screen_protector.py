
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class PrivacyOverlay(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Workstation Privacy Protection")

        # Borderless window that requests to remain on top
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setStyleSheet("""
            QWidget {
                background-color: #080b12;
                color: white;
            }

            QLabel#heading {
                color: #ff5252;
                font-size: 30px;
                font-weight: bold;
            }

            QLabel#description {
                color: #d1d5db;
                font-size: 18px;
            }

            QPushButton {
                background-color: #273449;
                color: white;
                padding: 14px 25px;
                border-radius: 8px;
                font-size: 16px;
            }

            QPushButton:hover {
                background-color: #384b66;
            }
        """)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(25)

        heading = QLabel("PRIVACY PROTECTION ACTIVATED")
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "Potential unauthorized viewer detected.\n"
            "Workstation contents have been masked."
        )
        description.setObjectName("description")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # For testing only: a manual recovery control
        dismiss_button = QPushButton(
            "Dismiss Demo Overlay"
        )
        dismiss_button.setFixedWidth(260)
        dismiss_button.clicked.connect(self.hide)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(
            dismiss_button,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.setLayout(layout)

    def activate(self):
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event):
        # Emergency exit for development/testing
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class ProtectionDemo(QWidget):
    def __init__(self):
        super().__init__()

        self.overlay = PrivacyOverlay()

        self.setWindowTitle(
            "Anti-Shoulder-Surfing - Protection Test"
        )

        self.resize(460, 260)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        title = QLabel("Workstation Protection Controller")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 19px; font-weight: bold;"
        )

        description = QLabel(
            "Simulate an intrusion to test screen masking."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        activate_button = QPushButton(
            "Simulate Unauthorized Viewer"
        )
        activate_button.clicked.connect(
            self.overlay.activate
        )

        quit_button = QPushButton("Quit Demo")
        quit_button.clicked.connect(
            QApplication.instance().quit
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(activate_button)
        layout.addWidget(quit_button)

        self.setLayout(layout)


def main():
    app = QApplication(sys.argv)

    controller = ProtectionDemo()
    controller.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
