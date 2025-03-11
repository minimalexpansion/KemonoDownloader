import sys
import os
import requests
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QPushButton, QLineEdit, QProgressBar, QTextEdit, 
                             QLabel, QCheckBox, QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
                             QAbstractItemView, QDialog, QVBoxLayout as QVBoxLayoutDialog, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize, QTimer
from PyQt6.QtGui import QColor, QPalette, QPixmap, QBrush
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
    progress = pyqtSignal(int)
    error = pyqtSignal(str)  # Signal for reporting errors

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.total_size = 0
        self.downloaded_size = 0

    def run(self):
        if self.url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            try:
                # Download the entire image first
                response = requests.get(self.url, headers=HEADERS, stream=True)
                response.raise_for_status()

                self.total_size = int(response.headers.get('content-length', 0)) or 1  # Avoid division by zero
                downloaded_data = bytearray()

                # Collect all chunks before attempting to load
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_data.extend(chunk)
                        self.downloaded_size += len(chunk)
                        progress = int((self.downloaded_size / self.total_size) * 100)
                        self.progress.emit(min(progress, 100))  # Cap at 100%

                # Now load the complete data into QPixmap
                pixmap = QPixmap()
                if not pixmap.loadFromData(downloaded_data):
                    self.error.emit(f"Failed to load image from {self.url}: Invalid or corrupted image data")
                    return

                # Scale the pixmap for display
                scaled_pixmap = pixmap.scaled(
                    800, 800,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_ready.emit(self.url, scaled_pixmap)

            except requests.RequestException as e:
                self.error.emit(f"Failed to download image from {self.url}: {str(e)}")
            except Exception as e:
                self.error.emit(f"Unexpected error while processing image from {self.url}: {str(e)}")

class ImageModal(QDialog):
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.setModal(True)
        self.resize(800, 800)
        self.layout = QVBoxLayoutDialog()
        self.label = QLabel("Loading Image...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
            "QProgressBar::chunk { background: #4A5B7A; }"
        )
        self.layout.addWidget(self.progress_bar)
        self.setLayout(self.layout)
        
        self.preview_thread = PreviewThread(url)
        self.preview_thread.preview_ready.connect(self.display_image)
        self.preview_thread.progress.connect(self.update_progress)
        self.preview_thread.error.connect(self.display_error)
        self.preview_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.label.setText(f"Loading Image... ({value}%)")

    def display_image(self, url, pixmap):
        self.label.setText("")
        self.progress_bar.hide()
        self.label.setPixmap(pixmap)

    def display_error(self, error_message):
        self.label.setText("Error loading image")
        self.progress_bar.hide()
        QMessageBox.critical(self, "Image Load Error", error_message)

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    overall_progress = pyqtSignal(int)
    log = pyqtSignal(str, str)
    finished = pyqtSignal()
    file_detected = pyqtSignal(str)

    def __init__(self, url, download_folder, file_types, selected_files, console):
        super().__init__()
        self.url = url
        self.download_folder = download_folder
        self.file_types = file_types
        self.selected_files = selected_files
        self.console = console
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        self.log.emit(f"[INFO] DownloadThread started with URL: {self.url}", "INFO")
        parts = self.url.split('/')
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
        if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
            self.log.emit("[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2), "ERROR")
            self.finished.emit()
            return

        post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
        self.log.emit(f"[INFO] Processed post data: {json.dumps(post, indent=2)}", "INFO")

        post_folder = os.path.join(self.download_folder, f"post_{post_id}")
        os.makedirs(post_folder, exist_ok=True)
        self.log.emit(f"[INFO] Created directory: {post_folder}", "INFO")

        files_to_download = self.detect_files(post, self.file_types)
        total_files = len(files_to_download)
        self.log.emit(f"[INFO] Total files to download: {total_files}", "INFO")
        for file_url in files_to_download:
            self.file_detected.emit(file_url)

        for i, file_url in enumerate(files_to_download):
            if self.is_running:
                self.download_file(file_url, post_folder, i, total_files)

        self.finished.emit()

    def detect_files(self, post, file_types):
        files_to_download = []
        allowed_extensions = file_types.get('extensions', [])

        if file_types.get('main') and 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1] or os.path.splitext(file_name)[1]
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if file_ext.lower() in allowed_extensions:
                files_to_download.append(file_url)

        if file_types.get('attachments') and 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1] or os.path.splitext(attachment_name)[1]
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if attachment_ext.lower() in allowed_extensions:
                        files_to_download.append(attachment_url)

        if file_types.get('content') and 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                if img_ext in allowed_extensions:
                    files_to_download.append(img_url)

        files_to_download = list(dict.fromkeys(files_to_download))
        return files_to_download

class CreatorDownloadThread(QThread):
    progress = pyqtSignal(int)
    overall_progress = pyqtSignal(int)
    log = pyqtSignal(str, str)
    finished = pyqtSignal()
    post_detected = pyqtSignal(str, str)

    def __init__(self, service, creator_id, download_folder, file_types, selected_posts, console):
        super().__init__()
        self.service = service
        self.creator_id = creator_id
        self.download_folder = download_folder
        self.file_types = file_types
        self.selected_posts = selected_posts
        self.console = console
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        self.log.emit(f"[INFO] CreatorDownloadThread started for service: {self.service}, creator_id: {self.creator_id}", "INFO")
        self.log.emit(f"[INFO] Selected posts: {self.selected_posts}", "INFO")
        
        total_posts = len(self.selected_posts)
        self.log.emit(f"[INFO] Total posts to process: {total_posts}", "INFO")
        
        total_files = 0
        files_per_post = {}
        for post_id in self.selected_posts:
            api_url = f"{API_BASE}/{self.service}/user/{self.creator_id}/post/{post_id}"
            response = requests.get(api_url, headers=HEADERS)
            if response.status_code != 200:
                self.log.emit(f"[ERROR] Failed to fetch {api_url} - Status code: {response.status_code}", "ERROR")
                continue
            post_data = response.json()
            post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
            files = self.detect_files(post, self.file_types)
            files_per_post[post_id] = files
            total_files += len(files)
        self.log.emit(f"[INFO] Total files across all posts: {total_files}", "INFO")

        files_processed = 0
        for post_index, post_id in enumerate(self.selected_posts):
            if not self.is_running:
                self.log.emit(f"[WARNING] Download cancelled for creator {self.creator_id}", "WARNING")
                break
            self.log.emit(f"[INFO] Processing post {post_id} ({post_index + 1}/{total_posts})", "INFO")
            api_url = f"{API_BASE}/{self.service}/user/{self.creator_id}/post/{post_id}"
            self.log.emit(f"[INFO] Fetching post from API: {api_url}", "INFO")
            
            response = requests.get(api_url, headers=HEADERS)
            self.log.emit(f"[INFO] API response status code: {response.status_code}", "INFO")
            if response.status_code != 200:
                self.log.emit(f"[ERROR] Failed to fetch {api_url} - Status code: {response.status_code}", "ERROR")
                continue
            
            post_data = response.json()
            if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
                self.log.emit("[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2), "ERROR")
                continue

            post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
            self.log.emit(f"[INFO] Processed post data: {json.dumps(post, indent=2)}", "INFO")

            creator_folder = os.path.join(self.download_folder, self.creator_id)
            os.makedirs(creator_folder, exist_ok=True)
            self.log.emit(f"[INFO] Created creator directory: {creator_folder}", "INFO")
            post_folder = os.path.join(creator_folder, f"post_{post_id}")
            os.makedirs(post_folder, exist_ok=True)
            self.log.emit(f"[INFO] Created post directory: {post_folder}", "INFO")

            files_to_download = files_per_post.get(post_id, [])
            total_files_in_post = len(files_to_download)
            self.log.emit(f"[INFO] Total files to download for post {post_id}: {total_files_in_post}", "INFO")

            for file_index, file_url in enumerate(files_to_download):
                if not self.is_running:
                    self.log.emit(f"[WARNING] Download cancelled for post {post_id}", "WARNING")
                    break
                self.log.emit(f"[INFO] Downloading file {file_index + 1}/{total_files_in_post} for post {post_id}: {file_url}", "INFO")
                try:
                    response = requests.get(file_url, headers=HEADERS, stream=True)
                    response.raise_for_status()
                    filename = file_url.split('f=')[-1] if 'f=' in file_url else file_url.split('/')[-1].split('?')[0]
                    filename = os.path.join(post_folder, filename.replace('/', '_'))
                    file_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if not self.is_running:
                                self.log.emit(f"[WARNING] Download interrupted for {file_url}", "WARNING")
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                if file_size > 0:
                                    progress = int((downloaded_size / file_size) * 100)
                                    self.progress.emit(progress)
                    self.log.emit(f"[INFO] Successfully downloaded: {filename}", "INFO")
                    files_processed += 1
                    if total_files > 0:
                        self.overall_progress.emit(int((files_processed / total_files) * 100))
                except Exception as e:
                    self.log.emit(f"[ERROR] Error downloading {file_url}: {e}", "ERROR")

        self.finished.emit()

    def detect_files(self, post, file_types):
        files_to_download = []
        allowed_extensions = file_types.get('extensions', [])

        if file_types.get('main') and 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1] or os.path.splitext(file_name)[1]
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if file_ext.lower() in allowed_extensions:
                files_to_download.append(file_url)

        if file_types.get('attachments') and 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1] or os.path.splitext(attachment_name)[1]
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if attachment_ext.lower() in allowed_extensions:
                        files_to_download.append(attachment_url)

        if file_types.get('content') and 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                if img_ext in allowed_extensions:
                    files_to_download.append(img_url)

        files_to_download = list(dict.fromkeys(files_to_download))
        return files_to_download

class KemonoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kemono Downloader")
        self.setGeometry(100, 100, 1000, 700)
        self.download_folder = "kemono_downloads"
        self.files_to_download = []
        self.file_url_map = {}  # Map file names to URLs for Post Downloader
        self.preview_cache = {}
        self.all_detected_files = []  # For Post Downloader
        self.posts_to_download = []  # For Creator Downloader
        self.post_url_map = {}  # Map post titles to (post_id, thumbnail_url) for Creator Downloader
        self.all_detected_posts = []  # For Creator Downloader
        self.post_queue = []  # Queue for Post Downloader URLs
        self.creator_queue = []  # Queue for Creator Downloader URLs
        self.downloading = False  # Flag to track if a download is in progress
        self.current_preview_url = None  # Track the current preview URL
        self.previous_selected_widget = None  # Track the previously selected item's widget
        self.setup_ui()

    def setup_ui(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1A2A44"))
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

        content_layout = QHBoxLayout()

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { background: #3A4B6A; color: white; padding: 8px; } "
                                "QTabBar::tab:selected { background: #4A5B7A; } "
                                "QTabBar::tab:disabled { color: gray; }")
        left_layout.addWidget(self.tabs)

        # Post Downloader Tab
        post_download_tab = QWidget()
        post_download_layout = QVBoxLayout(post_download_tab)
        
        post_url_layout = QHBoxLayout()
        self.post_url_input = QLineEdit()
        self.post_url_input.setPlaceholderText("Enter post URL (e.g., https://kemono.su/patreon/user/123456789/post/123456789)")
        self.post_url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        post_url_layout.addWidget(self.post_url_input)
        
        self.post_add_to_queue_btn = QPushButton(qta.icon('fa5s.plus'), "Add to Queue")
        self.post_add_to_queue_btn.clicked.connect(self.add_post_to_queue)
        self.post_add_to_queue_btn.setStyleSheet("background: #4A5B7A; padding: 5px; border-radius: 5px;")
        post_url_layout.addWidget(self.post_add_to_queue_btn)
        post_download_layout.addLayout(post_url_layout)

        post_queue_group = QGroupBox("Post Queue")
        post_queue_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        post_queue_layout = QVBoxLayout()
        self.post_queue_list = QListWidget()
        self.post_queue_list.setFixedHeight(100)
        self.post_queue_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        post_queue_layout.addWidget(self.post_queue_list)
        post_queue_group.setLayout(post_queue_layout)
        post_download_layout.addWidget(post_queue_group)

        post_options_group = QGroupBox("Download Options")
        post_options_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        post_options_layout = QVBoxLayout()
        
        post_categories_layout = QHBoxLayout()
        self.post_main_check = QCheckBox("Main File")
        self.post_main_check.setChecked(True)
        post_categories_layout.addWidget(self.post_main_check)
        self.post_attachments_check = QCheckBox("Attachments")
        self.post_attachments_check.setChecked(True)
        post_categories_layout.addWidget(self.post_attachments_check)
        self.post_content_check = QCheckBox("Content Images")
        self.post_content_check.setChecked(True)
        post_categories_layout.addWidget(self.post_content_check)
        post_categories_layout.addStretch()
        post_options_layout.addLayout(post_categories_layout)

        post_ext_group = QGroupBox("File Extensions")
        post_ext_group.setStyleSheet("QGroupBox { color: white; }")
        post_ext_layout = QGridLayout()
        post_ext_layout.setHorizontalSpacing(20)
        post_ext_layout.setVerticalSpacing(10)
        self.post_ext_checks = {
            '.jpg': QCheckBox("JPG"),
            '.jpeg': QCheckBox("JPEG"),
            '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"),
            '.mp4': QCheckBox("MP4"),
            '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"),
            '.7z': QCheckBox("7Z")
        }
        for i, (ext, check) in enumerate(self.post_ext_checks.items()):
            check.setChecked(True)
            post_ext_layout.addWidget(check, i // 3, i % 3)
        post_ext_group.setLayout(post_ext_layout)
        post_options_layout.addWidget(post_ext_group)
        post_options_group.setLayout(post_options_layout)
        post_download_layout.addWidget(post_options_group)

        post_progress_layout = QVBoxLayout()
        self.post_file_progress = QProgressBar()
        self.post_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
                                              "QProgressBar::chunk { background: #4A5B7A; }")
        post_progress_layout.addWidget(QLabel("File Progress"))
        post_progress_layout.addWidget(self.post_file_progress)
        self.post_overall_progress = QProgressBar()
        self.post_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
                                                 "QProgressBar::chunk { background: #4A5B7A; }")
        post_progress_layout.addWidget(QLabel("Overall Progress"))
        post_progress_layout.addWidget(self.post_overall_progress)
        post_download_layout.addLayout(post_progress_layout)

        self.post_console = QTextEdit()
        self.post_console.setReadOnly(True)
        self.post_console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        post_download_layout.addWidget(self.post_console)

        post_btn_layout = QHBoxLayout()
        self.post_download_btn = QPushButton(qta.icon('fa5s.download'), "Download")
        self.post_download_btn.clicked.connect(self.start_post_download)
        self.post_download_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        post_btn_layout.addWidget(self.post_download_btn)
        self.post_cancel_btn = QPushButton(qta.icon('fa5s.times'), "Cancel")
        self.post_cancel_btn.clicked.connect(self.cancel_post_download)
        self.post_cancel_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        self.post_cancel_btn.setEnabled(False)
        post_btn_layout.addWidget(self.post_cancel_btn)
        post_download_layout.addLayout(post_btn_layout)

        self.tabs.addTab(post_download_tab, "Post Downloader")

        # Creator Downloader Tab
        creator_download_tab = QWidget()
        creator_download_layout = QVBoxLayout(creator_download_tab)
        
        creator_url_layout = QHBoxLayout()
        self.creator_url_input = QLineEdit()
        self.creator_url_input.setPlaceholderText("Enter creator URL (e.g., https://kemono.su/patreon/user/12345678911)")
        self.creator_url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        creator_url_layout.addWidget(self.creator_url_input)
        
        self.creator_add_to_queue_btn = QPushButton(qta.icon('fa5s.plus'), "Add to Queue")
        self.creator_add_to_queue_btn.clicked.connect(self.add_creator_to_queue)
        self.creator_add_to_queue_btn.setStyleSheet("background: #4A5B7A; padding: 5px; border-radius: 5px;")
        creator_url_layout.addWidget(self.creator_add_to_queue_btn)
        creator_download_layout.addLayout(creator_url_layout)

        creator_queue_group = QGroupBox("Creator Queue")
        creator_queue_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        creator_queue_layout = QVBoxLayout()
        self.creator_queue_list = QListWidget()
        self.creator_queue_list.setFixedHeight(100)
        self.creator_queue_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        creator_queue_layout.addWidget(self.creator_queue_list)
        creator_queue_group.setLayout(creator_queue_layout)
        creator_download_layout.addWidget(creator_queue_group)

        creator_options_group = QGroupBox("Download Options")
        creator_options_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        creator_options_layout = QVBoxLayout()
        
        creator_categories_layout = QHBoxLayout()
        self.creator_main_check = QCheckBox("Main File")
        self.creator_main_check.setChecked(True)
        creator_categories_layout.addWidget(self.creator_main_check)
        self.creator_attachments_check = QCheckBox("Attachments")
        self.creator_attachments_check.setChecked(True)
        creator_categories_layout.addWidget(self.creator_attachments_check)
        self.creator_content_check = QCheckBox("Content Images")
        self.creator_content_check.setChecked(True)
        creator_categories_layout.addWidget(self.creator_content_check)
        creator_categories_layout.addStretch()
        creator_options_layout.addLayout(creator_categories_layout)

        creator_ext_group = QGroupBox("File Extensions")
        creator_ext_group.setStyleSheet("QGroupBox { color: white; }")
        creator_ext_layout = QGridLayout()
        creator_ext_layout.setHorizontalSpacing(20)
        creator_ext_layout.setVerticalSpacing(10)
        self.creator_ext_checks = {
            '.jpg': QCheckBox("JPG"),
            '.jpeg': QCheckBox("JPEG"),
            '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"),
            '.mp4': QCheckBox("MP4"),
            '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"),
            '.7z': QCheckBox("7Z")
        }
        for i, (ext, check) in enumerate(self.creator_ext_checks.items()):
            check.setChecked(True)
            creator_ext_layout.addWidget(check, i // 3, i % 3)
        creator_ext_group.setLayout(creator_ext_layout)
        creator_options_layout.addWidget(creator_ext_group)
        creator_options_group.setLayout(creator_options_layout)
        creator_download_layout.addWidget(creator_options_group)

        creator_progress_layout = QVBoxLayout()
        self.creator_file_progress = QProgressBar()
        self.creator_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
                                                 "QProgressBar::chunk { background: #4A5B7A; }")
        creator_progress_layout.addWidget(QLabel("File Progress"))
        creator_progress_layout.addWidget(self.creator_file_progress)
        self.creator_overall_progress = QProgressBar()
        self.creator_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } "
                                                    "QProgressBar::chunk { background: #4A5B7A; }")
        creator_progress_layout.addWidget(QLabel("Overall Progress"))
        creator_progress_layout.addWidget(self.creator_overall_progress)
        creator_download_layout.addLayout(creator_progress_layout)

        self.creator_console = QTextEdit()
        self.creator_console.setReadOnly(True)
        self.creator_console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        creator_download_layout.addWidget(self.creator_console)

        creator_btn_layout = QHBoxLayout()
        self.creator_download_btn = QPushButton(qta.icon('fa5s.download'), "Download")
        self.creator_download_btn.clicked.connect(self.start_creator_download)
        self.creator_download_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        creator_btn_layout.addWidget(self.creator_download_btn)
        self.creator_cancel_btn = QPushButton(qta.icon('fa5s.times'), "Cancel")
        self.creator_cancel_btn.clicked.connect(self.cancel_creator_download)
        self.creator_cancel_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        self.creator_cancel_btn.setEnabled(False)
        creator_btn_layout.addWidget(self.creator_cancel_btn)
        creator_download_layout.addLayout(creator_btn_layout)

        self.tabs.addTab(creator_download_tab, "Creator Downloader")

        left_layout.addStretch()
        content_layout.addWidget(left_widget, stretch=2)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        files_group = QGroupBox("Detected Items")
        files_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        files_group_layout = QVBoxLayout()

        files_header_layout = QHBoxLayout()
        files_header_layout.addWidget(QLabel("Items List"))
        files_header_layout.addStretch()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search items...")
        self.search_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.search_input.textChanged.connect(self.filter_items)
        files_group_layout.addWidget(self.search_input)

        self.check_all = QCheckBox("Check All")
        self.check_all.setChecked(True)
        self.check_all.setStyleSheet("color: white;")
        self.check_all.stateChanged.connect(self.toggle_check_all)
        files_group_layout.addWidget(self.check_all)

        self.filter_group = QGroupBox("Filter by Type")
        self.filter_group.setStyleSheet("QGroupBox { color: white; }")
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
            check.stateChanged.connect(self.filter_items)
            filter_layout.addWidget(check, i // 3, i % 3)
        self.filter_group.setLayout(filter_layout)
        files_group_layout.addWidget(self.filter_group)

        self.file_list = QListWidget()
        self.file_list.setFixedSize(300, 300)
        self.file_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)  # Disable default selection
        self.file_list.itemClicked.connect(self.handle_item_click)
        self.file_list.itemChanged.connect(self.update_checked_items)
        self.file_list.currentItemChanged.connect(self.update_current_preview_url)
        files_group_layout.addWidget(self.file_list)

        count_layout = QHBoxLayout()
        self.file_count_label = QLabel("Files: 0")
        self.file_count_label.setStyleSheet("color: white;")
        count_layout.addWidget(self.file_count_label)
        self.view_button = QPushButton(qta.icon('fa5s.eye'), "")
        self.view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
        self.view_button.clicked.connect(self.view_current_item)
        self.view_button.setEnabled(False)
        count_layout.addWidget(self.view_button)
        files_group_layout.addLayout(count_layout)

        files_group.setLayout(files_group_layout)
        right_layout.addWidget(files_group)

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

        self.post_download_btn.enterEvent = lambda e: self.animate_button(self.post_download_btn, True)
        self.post_download_btn.leaveEvent = lambda e: self.animate_button(self.post_download_btn, False)
        self.post_cancel_btn.enterEvent = lambda e: self.animate_button(self.post_cancel_btn, True)
        self.post_cancel_btn.leaveEvent = lambda e: self.animate_button(self.post_cancel_btn, False)
        self.creator_download_btn.enterEvent = lambda e: self.animate_button(self.creator_download_btn, True)
        self.creator_download_btn.leaveEvent = lambda e: self.animate_button(self.creator_download_btn, False)
        self.creator_cancel_btn.enterEvent = lambda e: self.animate_button(self.creator_cancel_btn, True)
        self.creator_cancel_btn.leaveEvent = lambda e: self.animate_button(self.creator_cancel_btn, False)

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        if index == 0:  # Post Downloader
            self.filter_group.show()
            self.file_count_label.setText(f"Files: {len(self.files_to_download)}")
        else:  # Creator Downloader
            self.filter_group.hide()
            self.file_count_label.setText(f"Posts: {len(self.posts_to_download)}")
        self.filter_items()

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

    def add_post_to_queue(self):
        url = self.post_url_input.text().strip()
        if not url:
            self.append_log_to_console(self.post_console, "[ERROR] No URL entered.", "ERROR")
            return
        if any(item[0] == url for item in self.post_queue):
            self.append_log_to_console(self.post_console, "[WARNING] URL already in queue.", "WARNING")
            return
        if self.check_post_url_validity(url):
            self.post_queue.append((url, False))  # False indicates not checked yet
            self.update_post_queue_list()
            self.post_url_input.clear()
            self.append_log_to_console(self.post_console, f"[INFO] Added post URL to queue: {url}", "INFO")
        else:
            self.append_log_to_console(self.post_console, f"[ERROR] Invalid post URL or failed to fetch: {url}", "ERROR")

    def add_creator_to_queue(self):
        url = self.creator_url_input.text().strip()
        if not url:
            self.append_log_to_console(self.creator_console, "[ERROR] No URL entered.", "ERROR")
            return
        if any(item[0] == url for item in self.creator_queue):
            self.append_log_to_console(self.creator_console, "[WARNING] URL already in queue.", "WARNING")
            return
        if self.check_creator_url_validity(url):
            self.creator_queue.append((url, False))  # False indicates not checked yet
            self.update_creator_queue_list()
            self.creator_url_input.clear()
            self.append_log_to_console(self.creator_console, f"[INFO] Added creator URL to queue: {url}", "INFO")
        else:
            self.append_log_to_console(self.creator_console, f"[ERROR] Invalid creator URL or failed to fetch: {url}", "ERROR")

    def check_post_url_validity(self, url):
        parts = url.split('/')
        if len(parts) < 7 or 'kemono.su' not in url:
            return False
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        try:
            response = requests.get(api_url, headers=HEADERS, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def check_creator_url_validity(self, url):
        parts = url.split('/')
        if len(parts) < 5 or 'kemono.su' not in url or parts[-2] != 'user':
            return False
        service, creator_id = parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}"
        try:
            response = requests.get(api_url, headers=HEADERS, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def create_view_handler(self, url, checked, queue_type):
        """Factory function to create a handler for viewing a URL from the queue."""
        def handler():
            if not checked:
                if queue_type == "post":
                    self.check_post_from_queue(url)
                else:
                    self.check_creator_from_queue(url)
        return handler

    def create_remove_handler(self, url, queue_type):
        """Factory function to create a handler for removing a URL from the queue."""
        def handler():
            if queue_type == "post":
                self.remove_from_post_queue(url)
            else:
                self.remove_from_creator_queue(url)
        return handler

    def update_post_queue_list(self):
        self.post_queue_list.clear()
        for url, checked in self.post_queue:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            view_button = QPushButton(qta.icon('fa5s.eye'), "")
            view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
            view_button.clicked.connect(self.create_view_handler(url, checked, "post"))
            layout.addWidget(view_button)

            label = QLabel(url)
            label.setStyleSheet("color: white;")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(label, stretch=1)

            remove_button = QPushButton(qta.icon('fa5s.times'), "")
            remove_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
            remove_button.clicked.connect(self.create_remove_handler(url, "post"))
            layout.addWidget(remove_button)

            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            self.post_queue_list.addItem(item)
            self.post_queue_list.setItemWidget(item, widget)
            widget.view_button = view_button
            widget.label = label
            widget.remove_button = remove_button

    def update_creator_queue_list(self):
        self.creator_queue_list.clear()
        for url, checked in self.creator_queue:
            item = QListWidgetItem()
            widget = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            view_button = QPushButton(qta.icon('fa5s.eye'), "")
            view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
            view_button.clicked.connect(self.create_view_handler(url, checked, "creator"))
            layout.addWidget(view_button)

            label = QLabel(url)
            label.setStyleSheet("color: white;")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(label, stretch=1)

            remove_button = QPushButton(qta.icon('fa5s.times'), "")
            remove_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
            remove_button.clicked.connect(self.create_remove_handler(url, "creator"))
            layout.addWidget(remove_button)

            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            self.creator_queue_list.addItem(item)
            self.creator_queue_list.setItemWidget(item, widget)
            widget.view_button = view_button
            widget.label = label
            widget.remove_button = remove_button

    def check_post_from_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(self.post_console, f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        self.append_log_to_console(self.post_console, f"[INFO] Checking post from queue: {url}", "INFO")
        self.file_list.clear()
        self.all_detected_files = []
        self.files_to_download = []
        self.file_url_map = {}
        self.previous_selected_widget = None  # Reset previous selection
        if self.check_post(url):
            for i, (queue_url, _) in enumerate(self.post_queue):
                if queue_url == url:
                    self.post_queue[i] = (url, True)
                    self.update_post_queue_list()
                    for file_name, file_url in self.all_detected_files:
                        self.add_list_item(file_name, file_url)
                    self.update_checked_files()
                    self.filter_items()
                    break
        else:
            self.append_log_to_console(self.post_console, f"[ERROR] Failed to check post: {url}", "ERROR")

    def check_creator_from_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(self.creator_console, f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        self.append_log_to_console(self.creator_console, f"[INFO] Checking creator from queue: {url}", "INFO")
        self.file_list.clear()
        self.all_detected_posts = []
        self.posts_to_download = []
        self.post_url_map = {}
        self.previous_selected_widget = None  # Reset previous selection
        if self.check_creator(url):
            for i, (queue_url, _) in enumerate(self.creator_queue):
                if queue_url == url:
                    self.creator_queue[i] = (url, True)
                    self.update_creator_queue_list()
                    for post_title, (post_id, thumbnail_url) in self.all_detected_posts:
                        self.add_list_item(post_title, thumbnail_url)
                    self.update_checked_posts()
                    self.filter_items()
                    break
        else:
            self.append_log_to_console(self.creator_console, f"[ERROR] Failed to check creator: {url}", "ERROR")

    def remove_from_post_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(self.post_console, f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        reply = QMessageBox.question(self, "Confirm Removal", f"Are you sure you want to remove {url} from the queue?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            found = False
            for i, (queue_url, _) in enumerate(self.post_queue):
                if queue_url == url:
                    del self.post_queue[i]
                    found = True
                    break
            if found:
                self.update_post_queue_list()  # Rebuild the list
                self.append_log_to_console(self.post_console, f"[INFO] Link ({url}) is removed from the queue.", "INFO")
                if not any(c for _, c in self.post_queue):
                    self.file_list.clear()
                    self.all_detected_files = []
                    self.files_to_download = []
                    self.file_url_map = {}
                    self.previous_selected_widget = None  # Reset previous selection
            else:
                self.append_log_to_console(self.post_console, f"[WARNING] URL ({url}) not found in queue.", "WARNING")

    def remove_from_creator_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(self.creator_console, f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        reply = QMessageBox.question(self, "Confirm Removal", f"Are you sure you want to remove {url} from the queue?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            found = False
            for i, (queue_url, _) in enumerate(self.creator_queue):
                if queue_url == url:
                    del self.creator_queue[i]
                    found = True
                    break
            if found:
                self.update_creator_queue_list()  # Rebuild the list
                self.append_log_to_console(self.creator_console, f"[INFO] Link ({url}) is removed from the queue.", "INFO")
                if not any(c for _, c in self.creator_queue):
                    self.file_list.clear()
                    self.all_detected_posts = []
                    self.posts_to_download = []
                    self.post_url_map = {}
                    self.previous_selected_widget = None  # Reset previous selection
            else:
                self.append_log_to_console(self.creator_console, f"[WARNING] URL ({url}) not found in queue.", "WARNING")

    def toggle_check_all(self, state):
        is_checked = state == 2
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        
        if self.tabs.currentWidget() == self.tabs.widget(0):
            self.files_to_download = []
        else:
            self.posts_to_download = []

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if not item.isHidden():
                widget = self.file_list.itemWidget(item)
                if widget:
                    widget.check_box.setCheckState(new_state)

        if self.tabs.currentWidget() == self.tabs.widget(0):
            self.update_checked_files()
        else:
            self.update_checked_posts()

        all_visible_checked = all(self.file_list.itemWidget(self.file_list.item(i)).check_box.checkState() == Qt.CheckState.Checked 
                                for i in range(self.file_list.count()) if not self.file_list.item(i).isHidden())
        self.check_all.blockSignals(True)
        self.check_all.setChecked(all_visible_checked)
        self.check_all.blockSignals(False)

    def update_checked_files(self):
        self.files_to_download = []
        seen_urls = set()
        for i in range(self.file_list.count()):
            item_widget = self.file_list.itemWidget(self.file_list.item(i))
            if item_widget and not self.file_list.item(i).isHidden() and item_widget.check_box.checkState() == Qt.CheckState.Checked:
                file_name = item_widget.label.text()
                if file_name in self.file_url_map:
                    file_url = self.file_url_map[file_name]
                    if file_url not in seen_urls:
                        self.files_to_download.append(file_url)
                        seen_urls.add(file_url)
        self.file_count_label.setText(f"Files: {len(self.files_to_download)}")

    def update_checked_posts(self):
        self.posts_to_download = []
        seen_ids = set()
        for i in range(self.file_list.count()):
            item_widget = self.file_list.itemWidget(self.file_list.item(i))
            if item_widget and not self.file_list.item(i).isHidden() and item_widget.check_box.checkState() == Qt.CheckState.Checked:
                post_title = item_widget.label.text()
                if post_title in self.post_url_map:
                    post_id, _ = self.post_url_map[post_title]
                    if post_id not in seen_ids:
                        self.posts_to_download.append(post_id)
                        seen_ids.add(post_id)
        self.file_count_label.setText(f"Posts: {len(self.posts_to_download)}")

    def update_checked_items(self):
        if self.tabs.currentWidget() == self.tabs.widget(0):
            self.update_checked_files()
        else:
            self.update_checked_posts()

    def filter_items(self):
        search_text = self.search_input.text().lower()
        active_filters = [ext for ext, check in self.filter_checks.items() if check.isChecked()]
        
        self.file_list.clear()
        self.previous_selected_widget = None  # Reset previous selection when filtering
        if self.tabs.currentWidget() == self.tabs.widget(0):
            for file_name, file_url in self.all_detected_files:
                file_ext = os.path.splitext(file_name)[1].lower()
                if (not search_text or search_text in file_name.lower()) and (not active_filters or file_ext in active_filters):
                    self.add_list_item(file_name, file_url)
        else:
            for post_title, (post_id, thumbnail_url) in self.all_detected_posts:
                if not search_text or search_text in post_title.lower():
                    self.add_list_item(post_title, thumbnail_url)

        all_visible_checked = all(self.file_list.itemWidget(self.file_list.item(i)).check_box.checkState() == Qt.CheckState.Checked 
                                for i in range(self.file_list.count()) if not self.file_list.item(i).isHidden())
        self.check_all.blockSignals(True)
        self.check_all.setChecked(all_visible_checked)
        self.check_all.blockSignals(False)
        self.update_checked_items()

    def add_list_item(self, text, url):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, url)  # Store URL in item data
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        check_box = QCheckBox()
        check_box.setStyleSheet("color: white;")
        check_box.setChecked(True)
        layout.addWidget(check_box)

        label = QLabel(text)
        label.setStyleSheet("color: white;")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, stretch=1)

        widget.setLayout(layout)
        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)
        widget.check_box = check_box
        widget.label = label
        # Set default background color for the custom widget
        widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")

    def update_current_preview_url(self, current, previous):
        if current:
            widget = self.file_list.itemWidget(current)
            if widget:
                self.current_preview_url = current.data(Qt.UserRole)
                self.view_button.setEnabled(True)
            else:
                self.current_preview_url = None
                self.view_button.setEnabled(False)
        else:
            self.current_preview_url = None
            self.view_button.setEnabled(False)

    def view_current_item(self):
        if self.current_preview_url:
            if self.current_preview_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                modal = ImageModal(self.current_preview_url, self)
                modal.exec()
            else:
                self.append_log_to_console(self.post_console if self.tabs.currentWidget() == self.tabs.widget(0) else self.creator_console,
                                           f"[WARNING] Viewing not supported for {self.current_preview_url}", "WARNING")

    def check_post(self, url):
        self.append_log_to_console(self.post_console, f"[INFO] Checking post with URL: {url}", "INFO")
        parts = url.split('/')
        if len(parts) < 7 or 'kemono.su' not in url:
            self.append_log_to_console(self.post_console, "[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[user_id]/post/[post_id]", "ERROR")
            return False
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        response = requests.get(api_url, headers=HEADERS)
        if response.status_code != 200:
            self.append_log_to_console(self.post_console, f"[ERROR] Failed to fetch post - Status code: {response.status_code}", "ERROR")
            return False
        
        post_data = response.json()
        if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
            self.append_log_to_console(self.post_console, "[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2), "ERROR")
            return False

        post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})

        self.files_to_download = []
        self.file_url_map = {}
        file_types = {
            'main': self.post_main_check.isChecked(),
            'attachments': self.post_attachments_check.isChecked(),
            'content': self.post_content_check.isChecked(),
            'extensions': [ext for ext, check in self.post_ext_checks.items() if check.isChecked()]
        }
        detected_files = []
        files_to_download = self.detect_files(post, file_types)
        for file_url in files_to_download:
            file_name = file_url.split('f=')[-1] if 'f=' in file_url else os.path.basename(file_url)
            detected_files.append((file_name, file_url))
            self.file_url_map[file_name] = file_url

        self.all_detected_files = detected_files  # Update to only this post's files
        return True

    def check_creator(self, url):
        self.append_log_to_console(self.creator_console, f"[INFO] Checking creator with URL: {url}", "INFO")
        parts = url.split('/')
        if len(parts) < 5 or 'kemono.su' not in url or parts[-2] != 'user':
            self.append_log_to_console(self.creator_console, "[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[creator_id]", "ERROR")
            return False
        service, creator_id = parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}"
        response = requests.get(api_url, headers=HEADERS)
        if response.status_code != 200:
            self.append_log_to_console(self.creator_console, f"[ERROR] Failed to fetch creator posts - Status code: {response.status_code}", "ERROR")
            return False
        
        posts_data = response.json()
        if not posts_data or not isinstance(posts_data, list):
            self.append_log_to_console(self.creator_console, "[ERROR] No valid posts data returned! Response: " + json.dumps(posts_data, indent=2), "ERROR")
            return False

        self.posts_to_download = []
        self.post_url_map = {}
        allowed_extensions = [ext for ext, check in self.creator_ext_checks.items() if check.isChecked()]

        detected_posts = []
        for post in posts_data:
            post_id = post.get('id')
            title = post.get('title', f"Post {post_id}")
            thumbnail_url = None
            if self.creator_main_check.isChecked() and 'file' in post and post['file'] and 'path' in post['file']:
                if post['file']['path'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    thumbnail_url = urljoin("https://kemono.su", post['file']['path'])
            if not thumbnail_url and self.creator_attachments_check.isChecked() and 'attachments' in post:
                for attachment in post['attachments']:
                    if isinstance(attachment, dict) and 'path' in attachment and attachment['path'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        thumbnail_url = urljoin("https://kemono.su", attachment['path'])
                        break
            if thumbnail_url and any(thumbnail_url.lower().endswith(ext) for ext in allowed_extensions):
                detected_posts.append((title, (post_id, thumbnail_url)))
                self.post_url_map[title] = (post_id, thumbnail_url)

        self.all_detected_posts = detected_posts  # Update to only this creator's posts
        return True

    def start_post_download(self):
        selected_urls = [url for url, checked in self.post_queue if checked]
        if not selected_urls:
            self.append_log_to_console(self.post_console, "[WARNING] No posts selected to download. Please check posts in the queue.", "WARNING")
            return

        self.downloading = True
        self.tabs.setTabEnabled(1, False)
        self.status_label.setText("Checking posts...")
        self.post_download_btn.setEnabled(False)
        self.post_cancel_btn.setEnabled(True)
        self.post_file_progress.setValue(0)
        self.post_overall_progress.setValue(0)
        self.all_detected_files = []

        self.process_next_post(selected_urls)

    def process_next_post(self, urls):
        if not urls:
            self.post_download_finished()
            return

        url = urls[0]
        remaining_urls = urls[1:]

        if self.check_post(url):
            file_types = {
                'main': self.post_main_check.isChecked(),
                'attachments': self.post_attachments_check.isChecked(),
                'content': self.post_content_check.isChecked(),
                'extensions': [ext for ext, check in self.post_ext_checks.items() if check.isChecked()]
            }
            self.thread = DownloadThread(url, self.download_folder, file_types, self.files_to_download, self.post_console)
            self.thread.progress.connect(self.update_post_file_progress)
            self.thread.overall_progress.connect(self.update_post_overall_progress)
            self.thread.log.connect(lambda msg, lvl: self.append_log_to_console(self.post_console, msg, lvl))
            self.thread.finished.connect(lambda: self.process_next_post(remaining_urls))
            self.thread.start()
        else:
            self.process_next_post(remaining_urls)

    def start_creator_download(self):
        selected_urls = [url for url, checked in self.creator_queue if checked]
        if not selected_urls:
            self.append_log_to_console(self.creator_console, "[WARNING] No creators selected to download. Please check creators in the queue.", "WARNING")
            return

        self.downloading = True
        self.tabs.setTabEnabled(0, False)
        self.status_label.setText("Checking creators...")
        self.creator_download_btn.setEnabled(False)
        self.creator_cancel_btn.setEnabled(True)
        self.creator_file_progress.setValue(0)
        self.creator_overall_progress.setValue(0)
        self.all_detected_posts = []

        self.process_next_creator(selected_urls)

    def process_next_creator(self, urls):
        if not urls:
            self.creator_download_finished()
            return

        url = urls[0]
        remaining_urls = urls[1:]

        if self.check_creator(url):
            parts = url.split('/')
            if len(parts) < 5 or 'kemono.su' not in url or parts[-2] != 'user':
                self.append_log_to_console(self.creator_console, "[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[creator_id]", "ERROR")
                self.process_next_creator(remaining_urls)
                return
            service, creator_id = parts[-3], parts[-1]

            file_types = {
                'main': self.creator_main_check.isChecked(),
                'attachments': self.creator_attachments_check.isChecked(),
                'content': self.creator_content_check.isChecked(),
                'extensions': [ext for ext, check in self.creator_ext_checks.items() if check.isChecked()]
            }
            self.thread = CreatorDownloadThread(service, creator_id, self.download_folder, file_types, self.posts_to_download, self.creator_console)
            self.thread.progress.connect(self.update_creator_file_progress)
            self.thread.overall_progress.connect(self.update_creator_overall_progress)
            self.thread.log.connect(lambda msg, lvl: self.append_log_to_console(self.creator_console, msg, lvl))
            self.thread.finished.connect(lambda: self.process_next_creator(remaining_urls))
            self.thread.start()
        else:
            self.process_next_creator(remaining_urls)

    def cancel_post_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.append_log_to_console(self.post_console, "[WARNING] Download cancelled by user", "WARNING")
            self.post_download_finished()

    def cancel_creator_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.append_log_to_console(self.creator_console, "[WARNING] Download cancelled by user", "WARNING")
            self.creator_download_finished()

    def update_post_file_progress(self, value):
        self.post_file_progress.setValue(value)

    def update_post_overall_progress(self, value):
        self.post_overall_progress.setValue(value)

    def update_creator_file_progress(self, value):
        self.creator_file_progress.setValue(value)

    def update_creator_overall_progress(self, value):
        self.creator_overall_progress.setValue(value)

    def post_download_finished(self):
        self.downloading = False
        self.tabs.setTabEnabled(1, True)
        self.status_label.setText("Idle")
        self.post_download_btn.setEnabled(True)
        self.post_cancel_btn.setEnabled(False)
        self.append_log_to_console(self.post_console, "[INFO] Download process ended", "INFO")

    def creator_download_finished(self):
        self.downloading = False
        self.tabs.setTabEnabled(0, True)
        self.status_label.setText("Idle")
        self.creator_download_btn.setEnabled(True)
        self.creator_cancel_btn.setEnabled(False)
        self.append_log_to_console(self.creator_console, "[INFO] Download process ended", "INFO")

    def append_log_to_console(self, console, message, level="INFO"):
        color = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}.get(level, "white")
        console.append(f"<span style='color:{color}'>{message}</span>")

    def detect_files(self, post, file_types):
        files_to_download = []
        allowed_extensions = file_types.get('extensions', [])

        if file_types.get('main') and 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1] or os.path.splitext(file_name)[1]
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if file_ext.lower() in allowed_extensions:
                files_to_download.append(file_url)

        if file_types.get('attachments') and 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1] or os.path.splitext(attachment_name)[1]
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if attachment_ext.lower() in allowed_extensions:
                        files_to_download.append(attachment_url)

        if file_types.get('content') and 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                if img_ext in allowed_extensions:
                    files_to_download.append(img_url)

        files_to_download = list(dict.fromkeys(files_to_download))
        return files_to_download

    def handle_item_click(self, item):
        """Handle item click to change the background color of the custom widget."""
        if item:
            # Reset the background of the previously selected item (if any)
            if self.previous_selected_widget:
                self.previous_selected_widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")

            # Change the clicked item's background color
            widget = self.file_list.itemWidget(item)
            if widget:
                widget.setStyleSheet("background-color: #4A5B7A; border-radius: 5px;")
                self.previous_selected_widget = widget  # Update the previous selection

                # Update preview URL and view button
                self.current_preview_url = item.data(Qt.UserRole)
                self.view_button.setEnabled(True)
            else:
                self.current_preview_url = None
                self.view_button.setEnabled(False)
        else:
            # If no item is clicked (e.g., deselected), reset the previous selection
            if self.previous_selected_widget:
                self.previous_selected_widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")
                self.previous_selected_widget = None
            self.current_preview_url = None
            self.view_button.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KemonoDownloader()
    window.show()
    sys.exit(app.exec())