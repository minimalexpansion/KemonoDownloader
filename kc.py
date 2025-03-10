import sys
import os
import requests
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QPushButton, QLineEdit, QProgressBar, QTextEdit, 
                             QLabel, QCheckBox, QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
                             QAbstractItemView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QColor, QPalette, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import qtawesome as qta
import json

# Headers for API requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://kemono.su/"
}
API_BASE = "https://kemono.su/api/v1"

class PreviewThread(QThread):
    preview_ready = pyqtSignal(str, QPixmap)
    video_ready = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        if self.url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            try:
                response = requests.get(self.url, headers=HEADERS)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                scaled_pixmap = pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_ready.emit(self.url, scaled_pixmap)
            except Exception as e:
                print(f"Preview error: {e}")
        elif self.url.lower().endswith('.mp4'):
            self.video_ready.emit(self.url)

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    overall_progress = pyqtSignal(int)
    log = pyqtSignal(str, str)
    finished = pyqtSignal()
    file_detected = pyqtSignal(str)

    def __init__(self, url, download_folder, file_types, selected_files):
        super().__init__()
        self.url = url
        self.download_folder = download_folder
        self.file_types = file_types
        self.selected_files = selected_files
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        self.log.emit(f"[INFO] DownloadThread started with URL: {self.url}", "INFO")
        parts = self.url.split('/')
        self.log.emit(f"[INFO] URL parts: {parts}", "INFO")
        if len(parts) < 7 or 'kemono.su' not in self.url:
            self.log.emit("[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[user_id]/post/[post_id]", "ERROR")
            self.finished.emit()
            return
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        self.log.emit(f"[INFO] Extracted: service={service}, creator_id={creator_id}, post_id={post_id}", "INFO")
        self.download_post(service, creator_id, post_id)

    def download_file(self, url, folder, file_index, total_files):
        self.log.emit(f"[INFO] Starting download of file: {url}", "INFO")
        if not self.is_running:
            self.log.emit(f"[WARNING] Download cancelled for {url}", "WARNING")
            return
        try:
            response = requests.get(url, headers=HEADERS, stream=True)
            response.raise_for_status()
            filename = url.split('f=')[-1] if 'f=' in url else url.split('/')[-1].split('?')[0]
            filename = os.path.join(folder, filename.replace('/', '_'))
            file_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.is_running:
                        self.log.emit(f"[WARNING] Download interrupted for {url}", "WARNING")
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if file_size > 0:
                            progress = int((downloaded_size / file_size) * 100)
                            self.progress.emit(progress)
            self.log.emit(f"[INFO] Successfully downloaded: {filename}", "INFO")
            self.overall_progress.emit(int((file_index + 1) / total_files * 100))
        except Exception as e:
            self.log.emit(f"[ERROR] Error downloading {url}: {e}", "ERROR")

    def download_post(self, service, creator_id, post_id):
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        self.log.emit(f"[INFO] Fetching post from API: {api_url}", "INFO")
        
        response = requests.get(api_url, headers=HEADERS)
        self.log.emit(f"[INFO] API response status code: {response.status_code}", "INFO")
        if response.status_code != 200:
            self.log.emit(f"[ERROR] Failed to fetch {api_url} - Status code: {response.status_code}", "ERROR")
            self.finished.emit()
            return
        
        post_data = response.json()
        self.log.emit(f"[INFO] Raw API response: {json.dumps(post_data, indent=2)}", "INFO")
        if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
            self.log.emit("[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2), "ERROR")
            self.finished.emit()
            return

        post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
        self.log.emit(f"[INFO] Processed post data: {json.dumps(post, indent=2)}", "INFO")

        post_folder = os.path.join(self.download_folder, f"{service}_post_{post_id}")
        os.makedirs(post_folder, exist_ok=True)
        self.log.emit(f"[INFO] Created directory: {post_folder}", "INFO")

        files_to_download = []
        allowed_extensions = self.file_types.get('extensions', [])

        if self.file_types.get('main') and 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1] or os.path.splitext(file_name)[1]
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if file_ext.lower() in allowed_extensions and file_url in self.selected_files:
                files_to_download.append(file_url)
                self.log.emit(f"[INFO] Detected main file: {file_url}", "INFO")

        if self.file_types.get('attachments') and 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1] or os.path.splitext(attachment_name)[1]
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if attachment_ext.lower() in allowed_extensions and attachment_url in self.selected_files:
                        files_to_download.append(attachment_url)
                        self.log.emit(f"[INFO] Detected attachment: {attachment_url}", "INFO")

        if self.file_types.get('content') and 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                if img_ext in allowed_extensions and img_url in self.selected_files:
                    files_to_download.append(img_url)
                    self.log.emit(f"[INFO] Detected content image: {img_url}", "INFO")

        total_files = len(files_to_download)
        self.log.emit(f"[INFO] Total files to download: {total_files}", "INFO")
        for file_url in files_to_download:
            self.file_detected.emit(file_url)

        for i, file_url in enumerate(files_to_download):
            if self.is_running:
                self.download_file(file_url, post_folder, i, total_files)

        self.finished.emit()

class KemonoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kemono Downloader")
        self.setGeometry(100, 100, 1200, 700)
        self.download_folder = "kemono_downloads"
        self.files_to_download = []
        self.file_url_map = {}  # Map file names to URLs for preview
        self.preview_cache = {}
        self.all_detected_files = []  # Store all detected files for filtering
        self.setup_ui()

    def setup_ui(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1A2A44"))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor("#2A3B5A"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#3A4B6A"))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor("#3A4B6A"))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        self.setPalette(palette)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        content_layout = QHBoxLayout()

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { background: #3A4B6A; color: white; padding: 8px; } "
                                "QTabBar::tab:selected { background: #4A5B7A; }")
        left_layout.addWidget(self.tabs)

        download_tab = QWidget()
        download_layout = QVBoxLayout(download_tab)
        
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter post URL (e.g., https://kemono.su/patreon/user/114138605/post/119966758)")
        self.url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        url_layout.addWidget(self.url_input)
        
        self.check_btn = QPushButton(qta.icon('fa5s.search'), "Check")
        self.check_btn.clicked.connect(self.check_post)
        self.check_btn.setStyleSheet("background: #4A5B7A; padding: 5px; border-radius: 5px;")
        url_layout.addWidget(self.check_btn)
        download_layout.addLayout(url_layout)

        options_group = QGroupBox("Download Options")
        options_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        options_layout = QVBoxLayout()
        
        categories_layout = QHBoxLayout()
        self.main_check = QCheckBox("Main File")
        self.main_check.setChecked(True)
        categories_layout.addWidget(self.main_check)
        self.attachments_check = QCheckBox("Attachments")
        self.attachments_check.setChecked(True)
        categories_layout.addWidget(self.attachments_check)
        self.content_check = QCheckBox("Content Images")
        self.content_check.setChecked(True)
        categories_layout.addWidget(self.content_check)
        categories_layout.addStretch()
        options_layout.addLayout(categories_layout)

        ext_group = QGroupBox("File Extensions")
        ext_group.setStyleSheet("QGroupBox { color: white; }")
        ext_layout = QGridLayout()
        ext_layout.setHorizontalSpacing(20)
        ext_layout.setVerticalSpacing(10)
        self.ext_checks = {
            '.jpg': QCheckBox("JPG"),
            '.jpeg': QCheckBox("JPEG"),
            '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"),
            '.mp4': QCheckBox("MP4"),
            '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"),
            '.7z': QCheckBox("7Z")
        }
        for i, (ext, check) in enumerate(self.ext_checks.items()):
            check.setChecked(True)
            ext_layout.addWidget(check, i // 3, i % 3)
        ext_group.setLayout(ext_layout)
        options_layout.addWidget(ext_group)
        options_group.setLayout(options_layout)
        download_layout.addWidget(options_group)

        progress_layout = QVBoxLayout()
        self.file_progress = QProgressBar()
        self.file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
                                         "QProgressBar::chunk { background: #4A5B7A; }")
        progress_layout.addWidget(QLabel("File Progress"))
        progress_layout.addWidget(self.file_progress)
        self.overall_progress = QProgressBar()
        self.overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
                                            "QProgressBar::chunk { background: #4A5B7A; }")
        progress_layout.addWidget(QLabel("Overall Progress"))
        progress_layout.addWidget(self.overall_progress)
        download_layout.addLayout(progress_layout)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        download_layout.addWidget(self.console)

        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton(qta.icon('fa5s.download'), "Download")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        btn_layout.addWidget(self.download_btn)
        self.cancel_btn = QPushButton(qta.icon('fa5s.times'), "Cancel")
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)
        download_layout.addLayout(btn_layout)

        self.tabs.addTab(download_tab, "Downloader")
        left_layout.addStretch()
        content_layout.addWidget(left_widget, stretch=2)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        files_group = QGroupBox("Detected Files")
        files_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        files_group_layout = QVBoxLayout()

        # Add search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search files...")
        self.search_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.search_input.textChanged.connect(self.filter_files)
        files_group_layout.addWidget(self.search_input)

        # Add "Check All" checkbox
        self.check_all = QCheckBox("Check All")
        self.check_all.setChecked(True)
        self.check_all.setStyleSheet("color: white;")
        self.check_all.stateChanged.connect(self.toggle_check_all)
        files_group_layout.addWidget(self.check_all)

        # Add filter checkboxes
        filter_group = QGroupBox("Filter by Type")
        filter_group.setStyleSheet("QGroupBox { color: white; }")
        filter_layout = QGridLayout()
        self.filter_checks = {
            '.jpg': QCheckBox("JPG"),
            '.jpeg': QCheckBox("JPEG"),
            '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"),
            '.mp4': QCheckBox("MP4"),
            '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"),
            '.7z': QCheckBox("7Z")
        }
        for i, (ext, check) in enumerate(self.filter_checks.items()):
            check.setChecked(True)
            check.stateChanged.connect(self.filter_files)
            filter_layout.addWidget(check, i // 3, i % 3)
        filter_group.setLayout(filter_layout)
        files_group_layout.addWidget(filter_group)

        self.file_list = QListWidget()
        self.file_list.setFixedSize(300, 300)
        self.file_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_list.itemClicked.connect(self.preview_file)
        self.file_list.itemChanged.connect(self.update_checked_files)
        files_group_layout.addWidget(self.file_list)

        self.file_count_label = QLabel("Files: 0")
        self.file_count_label.setStyleSheet("color: white;")
        files_group_layout.addWidget(self.file_count_label)
        files_group.setLayout(files_group_layout)
        right_layout.addWidget(files_group)

        preview_group = QGroupBox("Preview")
        preview_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(300, 300)
        self.preview_label.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.preview_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.preview_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.video_widget.setFixedSize(300, 300)
        self.video_widget.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.preview_player.setVideoOutput(self.video_widget)
        self.video_widget.hide()
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.video_widget)
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)
        right_layout.addStretch()
        
        content_layout.addWidget(right_widget, stretch=1)
        main_layout.addLayout(content_layout)

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

        self.download_btn.enterEvent = lambda e: self.animate_button(self.download_btn, True)
        self.download_btn.leaveEvent = lambda e: self.animate_button(self.download_btn, False)
        self.cancel_btn.enterEvent = lambda e: self.animate_button(self.cancel_btn, True)
        self.cancel_btn.leaveEvent = lambda e: self.animate_button(self.cancel_btn, False)

    def animate_button(self, button, enter):
        anim = QPropertyAnimation(button, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        rect = button.geometry()
        if enter:
            anim.setEndValue(rect.adjusted(-2, -2, 2, 2))
        else:
            anim.setEndValue(rect.adjusted(2, 2, -2, -2))
        anim.start()

    def toggle_check_all(self, state):
        """Toggle the checked state of all visible items in the file list and update the selection."""
        # Determine the new state (0 = Unchecked, 2 = Checked)
        is_checked = state == 2  # Qt.CheckState.Checked is 2
        
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        self.files_to_download = []  # Reset the list to rebuild it

        # Update the checked state of all visible items
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if not item.isHidden():  # Only affect visible items
                item.setCheckState(new_state)

        # Rebuild files_to_download based on the new state of visible items
        self.update_checked_files()

        # Ensure the Check All checkbox state matches the visible items
        all_visible_checked = all(self.file_list.item(i).checkState() == Qt.CheckState.Checked 
                                for i in range(self.file_list.count()) if not self.file_list.item(i).isHidden())
        self.check_all.blockSignals(True)
        self.check_all.setChecked(all_visible_checked)
        self.check_all.blockSignals(False)

    def update_checked_files(self):
        """Update the list of files to download based on checked items."""
        self.files_to_download = []
        seen_urls = set()  # To avoid duplicates
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if not item.isHidden() and item.checkState() == Qt.CheckState.Checked:
                file_name = item.text()
                if file_name in self.file_url_map:
                    file_url = self.file_url_map[file_name]
                    if file_url not in seen_urls:  # Avoid duplicates
                        self.files_to_download.append(file_url)
                        seen_urls.add(file_url)
        self.file_count_label.setText(f"Files: {len(self.files_to_download)}")

    def filter_files(self):
        """Filter the file list based on search text and filter checkboxes."""
        search_text = self.search_input.text().lower()
        active_filters = [ext for ext, check in self.filter_checks.items() if check.isChecked()]
        
        self.file_list.clear()
        for file_name, file_url in self.all_detected_files:
            file_ext = os.path.splitext(file_name)[1].lower()
            if (not search_text or search_text in file_name.lower()) and (not active_filters or file_ext in active_filters):
                item = QListWidgetItem(file_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                # Restore the checked state if the file was previously selected
                item.setCheckState(Qt.CheckState.Checked if file_url in self.files_to_download else Qt.CheckState.Unchecked)
                self.file_list.addItem(item)

        # Update Check All checkbox state based on visible items
        all_visible_checked = all(self.file_list.item(i).checkState() == Qt.CheckState.Checked 
                                for i in range(self.file_list.count()) if not self.file_list.item(i).isHidden())
        self.check_all.blockSignals(True)
        self.check_all.setChecked(all_visible_checked)
        self.check_all.blockSignals(False)
        self.update_checked_files()  # Ensure count is updated after filtering

    def check_post(self):
        self.append_log(f"[INFO] Checking post with URL: {self.url_input.text()}")
        url = self.url_input.text()
        if not url:
            self.append_log("[ERROR] No URL entered.")
            return
        self.status_label.setText("Checking...")
        parts = url.split('/')
        self.append_log(f"[INFO] URL parts: {parts}")
        if len(parts) < 7 or 'kemono.su' not in url:
            self.append_log("[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[user_id]/post/[post_id]")
            self.status_label.setText("Idle")
            return
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        self.append_log(f"[INFO] Extracted: service={service}, creator_id={creator_id}, post_id={post_id}")
        
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        self.append_log(f"[INFO] API request URL: {api_url}")
        response = requests.get(api_url, headers=HEADERS)
        self.append_log(f"[INFO] API response status code: {response.status_code}")
        if response.status_code != 200:
            self.append_log(f"[ERROR] Failed to fetch post - Status code: {response.status_code}")
            self.status_label.setText("Idle")
            return
        
        post_data = response.json()
        self.append_log(f"[INFO] Raw API response: {json.dumps(post_data, indent=2)}")
        if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
            self.append_log("[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2))
            self.status_label.setText("Idle")
            return

        post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
        self.append_log(f"[INFO] Processed post data: {json.dumps(post, indent=2)}")

        self.files_to_download = []
        self.file_url_map = {}
        self.all_detected_files = []
        allowed_extensions = [ext for ext, check in self.ext_checks.items() if check.isChecked()]
        self.append_log(f"[INFO] Allowed extensions: {allowed_extensions}")

        detected_files = []
        if self.main_check.isChecked() and 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1] or os.path.splitext(file_name)[1]
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if file_ext.lower() in allowed_extensions:
                detected_files.append((file_name, file_url))
                self.file_url_map[file_name] = file_url
                self.append_log(f"[INFO] Detected main file: {file_url}")

        if self.attachments_check.isChecked() and 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1] or os.path.splitext(attachment_name)[1]
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if attachment_ext.lower() in allowed_extensions:
                        detected_files.append((attachment_name, attachment_url))
                        self.file_url_map[attachment_name] = attachment_url
                        self.append_log(f"[INFO] Detected attachment: {attachment_url}")

        if self.content_check.isChecked() and 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            self.append_log(f"[INFO] Content HTML: {post['content']}")
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                self.append_log(f"[INFO] Found image tag with src: {img['src']}")
                img_ext = os.path.splitext(img_url)[1].lower()
                img_name = img_url.split('f=')[-1] if 'f=' in img_url else os.path.basename(img_url)
                if img_ext in allowed_extensions:
                    detected_files.append((img_name, img_url))
                    self.file_url_map[img_name] = img_url
                    self.append_log(f"[INFO] Detected content image: {img_url}")

        self.all_detected_files = list(dict.fromkeys(detected_files))  # Remove duplicates
        self.file_list.clear()
        for file_name, file_url in self.all_detected_files:
            item = QListWidgetItem(file_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.file_list.addItem(item)
        
        self.update_checked_files()
        self.filter_files()
        self.append_log(f"[INFO] Total files detected: {len(self.all_detected_files)}")
        self.status_label.setText("Idle")

    def start_download(self):
        self.append_log(f"[INFO] Starting download with URL: {self.url_input.text()}")
        url = self.url_input.text()
        if not url:
            self.append_log("[ERROR] No URL entered.")
            return
        if not self.files_to_download:
            self.append_log("[WARNING] No files selected to download. Please check the post and select files.")
            return
        
        file_types = {
            'main': self.main_check.isChecked(),
            'attachments': self.attachments_check.isChecked(),
            'content': self.content_check.isChecked(),
            'extensions': [ext for ext, check in self.ext_checks.items() if check.isChecked()]
        }
        self.append_log(f"[INFO] File types enabled: {file_types}")

        self.status_label.setText("Downloading...")
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.file_progress.setValue(0)
        self.overall_progress.setValue(0)

        self.thread = DownloadThread(url, self.download_folder, file_types, self.files_to_download)
        self.thread.progress.connect(self.update_file_progress)
        self.thread.overall_progress.connect(self.update_overall_progress)
        self.thread.log.connect(self.append_log)
        self.thread.finished.connect(self.download_finished)
        self.thread.file_detected.connect(self.add_detected_file)
        self.thread.start()

    def cancel_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.append_log("[WARNING] Download cancelled by user")
            self.download_finished()

    def update_file_progress(self, value):
        self.file_progress.setValue(value)

    def update_overall_progress(self, value):
        self.overall_progress.setValue(value)

    def download_finished(self):
        self.status_label.setText("Idle")
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.append_log("[INFO] Download process ended")

    def append_log(self, message, level="INFO"):
        color = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}.get(level, "white")
        self.console.append(f"<span style='color:{color}'>{message}</span>")

    def add_detected_file(self, file_url):
        item = QListWidgetItem(file_url)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        self.file_list.addItem(item)

    def preview_file(self, item):
        url = self.file_url_map.get(item.text())
        if url:
            self.append_log(f"[INFO] Previewing file: {url}")
            self.video_widget.hide()
            self.preview_label.show()
            self.preview_label.clear()
            
            self.preview_thread = PreviewThread(url)
            self.preview_thread.preview_ready.connect(self.display_image_preview)
            self.preview_thread.video_ready.connect(self.display_video_preview)
            self.preview_thread.start()

    def display_image_preview(self, url, pixmap):
        self.preview_label.setPixmap(pixmap)
        self.preview_cache[url] = pixmap
        self.video_widget.hide()
        self.append_log(f"[INFO] Displayed image preview for: {url}")

    def display_video_preview(self, url):
        self.preview_label.hide()
        self.video_widget.show()
        self.preview_player.setSource(url)
        self.preview_player.play()
        self.append_log(f"[INFO] Displayed video preview for: {url}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KemonoDownloader()
    window.show()
    sys.exit(app.exec())