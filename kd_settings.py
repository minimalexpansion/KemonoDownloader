import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                             QGroupBox, QGridLayout, QLabel, QSlider, QSpinBox, 
                             QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal

class SettingsTab(QWidget):
    settings_applied = pyqtSignal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.qsettings = QSettings("VoxDroid", "KemonoDownloader")
        self.default_settings = {
            "base_folder_name": "Kemono Downloader",
            "base_directory": os.getcwd(),
            "simultaneous_downloads": 5,
        }
        self.settings = self.load_settings()
        self.temp_settings = self.settings.copy()
        self.setup_ui()

    def load_settings(self):
        settings_dict = {}
        settings_dict["base_folder_name"] = self.qsettings.value("base_folder_name", self.default_settings["base_folder_name"], type=str)
        settings_dict["base_directory"] = self.qsettings.value("base_directory", self.default_settings["base_directory"], type=str)
        settings_dict["simultaneous_downloads"] = self.qsettings.value("simultaneous_downloads", self.default_settings["simultaneous_downloads"], type=int)
        return settings_dict

    def save_settings(self):
        self.qsettings.setValue("base_folder_name", self.settings["base_folder_name"])
        self.qsettings.setValue("base_directory", self.settings["base_directory"])
        self.qsettings.setValue("simultaneous_downloads", self.settings["simultaneous_downloads"])
        self.qsettings.sync()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Folder Settings Group
        folder_group = QGroupBox("Folder Settings")
        folder_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        folder_layout = QGridLayout()
        folder_layout.addWidget(QLabel("Folder Name:"), 0, 0)
        self.folder_name_input = QLineEdit(self.temp_settings["base_folder_name"])
        self.folder_name_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.folder_name_input.textChanged.connect(lambda: self.update_temp_setting("base_folder_name", self.folder_name_input.text()))
        folder_layout.addWidget(self.folder_name_input, 0, 1)
        folder_layout.addWidget(QLabel("Save Directory:"), 1, 0)
        self.directory_input = QLineEdit(self.temp_settings["base_directory"])
        self.directory_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.directory_input.textChanged.connect(lambda: self.update_temp_setting("base_directory", self.directory_input.text()))
        folder_layout.addWidget(self.directory_input, 1, 1)
        self.browse_button = QPushButton("Browse")
        self.browse_button.setStyleSheet("background: #4A5B7A; padding: 5px; border-radius: 5px;")
        self.browse_button.clicked.connect(self.browse_directory)
        folder_layout.addWidget(self.browse_button, 1, 2)
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # Download Settings Group
        download_group = QGroupBox("Download Settings")
        download_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        download_layout = QGridLayout()
        download_layout.addWidget(QLabel("Simultaneous Downloads:"), 0, 0)
        self.download_slider = QSlider(Qt.Orientation.Horizontal)
        self.download_slider.setRange(1, 10)
        self.download_slider.setValue(self.temp_settings["simultaneous_downloads"])
        self.download_slider.setStyleSheet("QSlider::groove:horizontal { border: 1px solid #4A5B7A; height: 8px; background: #2A3B5A; margin: 2px 0; }"
                                           "QSlider::handle:horizontal { background: #4A5B7A; width: 18px; margin: -2px 0; border-radius: 9px; }")
        self.download_slider.valueChanged.connect(self.update_simultaneous_downloads)
        download_layout.addWidget(self.download_slider, 0, 1)
        self.download_spinbox = QSpinBox()
        self.download_spinbox.setRange(1, 10)
        self.download_spinbox.setValue(self.temp_settings["simultaneous_downloads"])
        self.download_spinbox.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.download_spinbox.valueChanged.connect(self.update_simultaneous_downloads)
        download_layout.addWidget(self.download_spinbox, 0, 2)
        download_group.setLayout(download_layout)
        layout.addWidget(download_group)

        # Apply Button
        apply_button = QPushButton("Apply Changes")
        apply_button.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        apply_button.clicked.connect(self.confirm_and_apply_settings)
        layout.addWidget(apply_button)
        layout.addStretch()

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", self.temp_settings["base_directory"])
        if directory:
            self.directory_input.setText(directory)
            self.update_temp_setting("base_directory", directory)

    def update_temp_setting(self, key, value):
        self.temp_settings[key] = value

    def update_simultaneous_downloads(self, value):
        self.temp_settings["simultaneous_downloads"] = value
        self.download_slider.blockSignals(True)
        self.download_spinbox.blockSignals(True)
        self.download_slider.setValue(value)
        self.download_spinbox.setValue(value)
        self.download_slider.blockSignals(False)
        self.download_spinbox.blockSignals(False)

    def confirm_and_apply_settings(self):
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Settings Change",
            "Are you sure you want to apply these settings?\n\n"
            f"Folder Name: {self.temp_settings['base_folder_name']}\n"
            f"Save Directory: {self.temp_settings['base_directory']}\n"
            f"Simultaneous Downloads: {self.temp_settings['simultaneous_downloads']}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return  # User canceled, do nothing

        # Validate settings before applying
        if not self.temp_settings["base_folder_name"].strip():
            QMessageBox.warning(self, "Invalid Input", "Folder name cannot be empty.")
            self.folder_name_input.setText(self.settings["base_folder_name"])
            self.temp_settings["base_folder_name"] = self.settings["base_folder_name"]
            return
        if not os.path.isdir(self.temp_settings["base_directory"]):
            QMessageBox.warning(self, "Invalid Input", "Selected directory does not exist.")
            self.directory_input.setText(self.settings["base_directory"])
            self.temp_settings["base_directory"] = self.settings["base_directory"]
            return

        # Apply settings
        self.settings = self.temp_settings.copy()
        self.save_settings()
        old_base_folder = self.parent.base_folder
        self.parent.base_folder = os.path.join(self.settings["base_directory"], self.settings["base_folder_name"])
        self.parent.download_folder = os.path.join(self.parent.base_folder, "Downloads")
        self.parent.cache_folder = os.path.join(self.parent.base_folder, "Cache")
        self.parent.other_files_folder = os.path.join(self.parent.base_folder, "Other Files")
        self.parent.ensure_folders_exist()

        if old_base_folder != self.parent.base_folder:
            self.parent.post_tab.cache_dir = self.parent.cache_folder
            self.parent.post_tab.other_files_dir = self.parent.other_files_folder
            self.parent.creator_tab.cache_dir = self.parent.cache_folder
            self.parent.creator_tab.other_files_dir = self.parent.other_files_folder

        self.settings_applied.emit()

        # Show success notification
        QMessageBox.information(
            self,
            "Settings Applied",
            "Settings have been successfully applied!\n\n"
            f"Folder Name: {self.settings['base_folder_name']}\n"
            f"Save Directory: {self.settings['base_directory']}\n"
            f"Simultaneous Downloads: {self.settings['simultaneous_downloads']}"
        )

    def get_simultaneous_downloads(self):
        return self.settings["simultaneous_downloads"]