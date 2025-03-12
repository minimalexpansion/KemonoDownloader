import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
import qtawesome as qta
from post_downloader import PostDownloaderTab
from creator_downloader import CreatorDownloaderTab
from kd_settings import SettingsTab

class KemonoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kemono Downloader")
        self.setGeometry(100, 100, 1000, 700)
        
        # Initialize settings
        self.settings_tab = SettingsTab(self)
        self.base_folder = os.path.join(self.settings_tab.settings["base_directory"], self.settings_tab.settings["base_folder_name"])
        self.download_folder = os.path.join(self.base_folder, "Downloads")
        self.cache_folder = os.path.join(self.base_folder, "Cache")
        self.other_files_folder = os.path.join(self.base_folder, "Other Files")
        
        # Ensure all folders exist at startup
        self.ensure_folders_exist()
        
        self.setup_ui()

    def ensure_folders_exist(self):
        """Create all necessary folders if they don't exist."""
        os.makedirs(self.base_folder, exist_ok=True)
        os.makedirs(self.download_folder, exist_ok=True)
        os.makedirs(self.cache_folder, exist_ok=True)
        os.makedirs(self.other_files_folder, exist_ok=True)

    def setup_ui(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.settings_tab.settings["theme_color"]))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor("#2A3B5A"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#3A4B6A"))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor("#3A5B7A"))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        self.setPalette(palette)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { background: #3A4B6A; color: white; padding: 8px; } "
                                "QTabBar::tab:selected { background: #4A5B7A; } "
                                "QTabBar::tab:disabled { color: gray; }")
        main_layout.addWidget(self.tabs)

        self.post_tab = PostDownloaderTab(self)
        self.tabs.addTab(self.post_tab, qta.icon('fa5s.download'), "Post Downloader")

        self.creator_tab = CreatorDownloaderTab(self)
        self.tabs.addTab(self.creator_tab, qta.icon('fa5s.user-edit'), "Creator Downloader")

        self.tabs.addTab(self.settings_tab, qta.icon('fa5s.cog'), "Settings")

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: white;")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        dev_label = QLabel("Developed by VoxDroid | GitHub: @VoxDroid")
        dev_label.setStyleSheet("color: white;")
        footer_layout.addWidget(dev_label)
        main_layout.addWidget(footer)

    def animate_button(self, button, enter):
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        anim = QPropertyAnimation(button, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        rect = button.geometry()
        if enter:
            anim.setEndValue(rect.adjusted(-2, -2, 2, 2))
        else:
            anim.setEndValue(rect.adjusted(2, 2, -2, -2))
        anim.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KemonoDownloader()
    window.show()
    sys.exit(app.exec())