import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect, 
    QTabWidget
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPalette, QFont, QCursor, QIcon
import qtawesome as qta
from post_downloader import PostDownloaderTab
from creator_downloader import CreatorDownloaderTab
from kd_settings import SettingsTab
from kd_help import HelpTab


class IntroScreen(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()
        self.start_fade_in()

    def setup_ui(self):
        self.setStyleSheet("background-color: #1A2A44; border: none;")
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # Title
        self.title = QLabel("Kemono.su Downloader")
        self.title.setFont(QFont("Poppins", 42, QFont.Weight.Bold))
        self.title.setStyleSheet("""
            color: #FFFFFF;
            background: rgba(255, 255, 255, 0.1);
            padding: 20px 40px;
            border-radius: 12px;
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        self.title.setGraphicsEffect(shadow)
        main_layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Info Container
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(10)
        info_widget.setStyleSheet("""
            background: rgba(255, 255, 255, 0.08);
            padding: 15px 25px;
            border-radius: 10px;
        """)
        info_shadow = QGraphicsDropShadowEffect()
        info_shadow.setBlurRadius(15)
        info_shadow.setColor(QColor(0, 0, 0, 80))
        info_widget.setGraphicsEffect(info_shadow)

        self.dev_label = QLabel("Developed by VoxDroid")
        self.dev_label.setFont(QFont("Poppins", 16))
        self.dev_label.setStyleSheet("color: #FFFFFF;")
        self.dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.dev_label)

        self.github_label = QLabel(
            '<a href="https://github.com/VoxDroid" style="color: #A0C0FF; text-decoration: none;">github.com/VoxDroid</a>'
        )
        self.github_label.setFont(QFont("Poppins", 14))
        self.github_label.setOpenExternalLinks(True)
        self.github_label.setStyleSheet("QLabel { background: transparent; } QLabel:hover { color: #C0E0FF; }")
        self.github_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.github_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.github_label)

        main_layout.addWidget(info_widget)
        main_layout.addSpacing(40)

        # Launch Button
        self.launch_button = QPushButton("Launch Application")
        self.launch_button.setFont(QFont("Poppins", 16, QFont.Weight.Medium))
        self.launch_button.setFixedSize(220, 60)
        self.launch_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4A6B9A, stop:1 #3A5B7A);
                color: #FFFFFF;
                border-radius: 18px;
                border: 2px solid #5A7BA9;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5A7BA9, stop:1 #4A6B9A);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3A5B7A, stop:1 #2A4B6A);
            }
        """)
        button_shadow = QGraphicsDropShadowEffect()
        button_shadow.setBlurRadius(20)
        button_shadow.setColor(QColor(0, 0, 0, 100))
        button_shadow.setOffset(0, 5)
        self.launch_button.setGraphicsEffect(button_shadow)
        self.launch_button.clicked.connect(self.parent.transition_to_main)
        main_layout.addWidget(self.launch_button, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addStretch()

    def start_fade_in(self):
        self.setWindowOpacity(0)
        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(1000)
        fade_in.setStartValue(0)
        fade_in.setEndValue(1)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_in.start()

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.dirname(__file__), relative_path)

class KemonoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kemono Downloader")
        self.setGeometry(100, 100, 1000, 700)

        # Initialize settings and folder structure
        self.settings_tab = SettingsTab(self)
        self.base_folder = os.path.join(
            self.settings_tab.settings["base_directory"], 
            self.settings_tab.settings["base_folder_name"]
        )
        self.download_folder = os.path.join(self.base_folder, "Downloads")
        self.cache_folder = os.path.join(self.base_folder, "Cache")
        self.other_files_folder = os.path.join(self.base_folder, "Other Files")
        self.ensure_folders_exist()

        self.setWindowIcon(QIcon(resource_path("KemonoDownloader.ico")))

        # Set up UI
        self.intro_screen = IntroScreen(self)
        self.main_widget = None
        self.setCentralWidget(self.intro_screen)
        self.apply_palette()

    def apply_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1A2A44"))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor("#2A3B5A"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#3A4B6A"))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor("#3A5B7A"))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        self.setPalette(palette)

    def ensure_folders_exist(self):
        for folder in [self.base_folder, self.download_folder, self.cache_folder, self.other_files_folder]:
            os.makedirs(folder, exist_ok=True)

    def setup_main_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        main_widget.setStyleSheet("background: #1A2A44;")

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #1A2A44;
            }
            QTabBar::tab {
                background: #3A4B6A;
                color: white;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-width: 100px;
            }
            QTabBar::tab:selected {
                background: #4A5B7A;
                color: white;
            }
            QTabBar::tab:!selected {
                margin-top: 2px;
            }
            QTabBar::tab:disabled {
                color: gray;
            }
            * {
                color: white;
            }
        """)
        main_layout.addWidget(self.tabs)

        # Add Tabs
        self.post_tab = PostDownloaderTab(self)
        self.tabs.addTab(self.post_tab, qta.icon('fa5s.download', color='white'), "Post Downloader")

        self.creator_tab = CreatorDownloaderTab(self)
        self.tabs.addTab(self.creator_tab, qta.icon('fa5s.user-edit', color='white'), "Creator Downloader")

        self.tabs.addTab(self.settings_tab, qta.icon('fa5s.cog', color='white'), "Settings")

        self.help_tab = HelpTab(self)
        self.tabs.addTab(self.help_tab, qta.icon('fa5s.question-circle', color='white'), "Help")

        # Footer
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: white; font-size: 12px;")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        dev_label = QLabel("Developed by VoxDroid | GitHub: @VoxDroid")
        dev_label.setStyleSheet("color: white; font-size: 12px;")
        footer_layout.addWidget(dev_label)
        main_layout.addWidget(footer)

        return main_widget

    def transition_to_main(self):
        self.main_widget = self.setup_main_ui()
        self.main_widget.setParent(self)
        self.main_widget.move(0, 0)
        self.main_widget.resize(self.size())
        self.main_widget.setWindowOpacity(0)

        self.intro_fade = QPropertyAnimation(self.intro_screen, b"windowOpacity")
        self.intro_fade.setDuration(800)
        self.intro_fade.setStartValue(1)
        self.intro_fade.setEndValue(0)
        self.intro_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.main_fade = QPropertyAnimation(self.main_widget, b"windowOpacity")
        self.main_fade.setDuration(800)
        self.main_fade.setStartValue(0)
        self.main_fade.setEndValue(1)
        self.main_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.intro_fade.finished.connect(lambda: self.setCentralWidget(self.main_widget))
        self.intro_fade.start()
        self.main_fade.start()

    def animate_button(self, button, enter):
        anim = QPropertyAnimation(button, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        rect = button.geometry()
        if enter:
            anim.setEndValue(rect.adjusted(-3, -3, 3, 3))
        else:
            anim.setEndValue(rect.adjusted(3, 3, -3, -3))
        anim.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = KemonoDownloader()
    window.show()
    sys.exit(app.exec())