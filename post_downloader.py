import os
import hashlib
import requests
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                             QGroupBox, QGridLayout, QProgressBar, QTextEdit, QListWidget, 
                             QListWidgetItem, QAbstractItemView, QMessageBox, QCheckBox, 
                             QLabel, QDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
import qtawesome as qta

# Headers for API requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36", "Referer": "https://kemono.su/"}
API_BASE = "https://kemono.su/api/v1"

class PreviewThread(QThread):
    preview_ready = pyqtSignal(str, object)  # Using object to allow QPixmap
    progress = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, url, cache_dir):
        super().__init__()
        self.url = url
        self.cache_dir = cache_dir
        self.total_size = 0
        self.downloaded_size = 0
        os.makedirs(self.cache_dir, exist_ok=True)

    def run(self):
        if self.url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            # Check cache first
            cache_key = hashlib.md5(self.url.encode()).hexdigest() + os.path.splitext(self.url)[1]
            cache_path = os.path.join(self.cache_dir, cache_key)
            if os.path.exists(cache_path):
                pixmap = QPixmap()
                if pixmap.load(cache_path):
                    self.preview_ready.emit(self.url, pixmap)
                    return

            try:
                response = requests.get(self.url, headers=HEADERS, stream=True)
                response.raise_for_status()
                self.total_size = int(response.headers.get('content-length', 0)) or 1
                downloaded_data = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_data.extend(chunk)
                        self.downloaded_size += len(chunk)
                        progress = int((self.downloaded_size / self.total_size) * 100)
                        self.progress.emit(min(progress, 100))
                pixmap = QPixmap()
                if not pixmap.loadFromData(downloaded_data):
                    self.error.emit(f"Failed to load image from {self.url}: Invalid or corrupted image data")
                    return
                scaled_pixmap = pixmap.scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                scaled_pixmap.save(cache_path)  # Save to cache
                self.preview_ready.emit(self.url, scaled_pixmap)
            except requests.RequestException as e:
                self.error.emit(f"Failed to download image from {self.url}: {str(e)}")
            except Exception as e:
                self.error.emit(f"Unexpected error while processing image from {self.url}: {str(e)}")

class ImageModal(QDialog):
    def __init__(self, url, cache_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.setModal(True)
        self.resize(800, 800)
        self.layout = QVBoxLayout()
        self.label = QLabel("Loading Image...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } QProgressBar::chunk { background: #4A5B7A; }")
        self.layout.addWidget(self.progress_bar)
        self.setLayout(self.layout)
        
        self.preview_thread = PreviewThread(url, cache_dir)
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

    def __init__(self, url, download_folder, file_types, selected_files, console, cache_dir, other_files_dir):
        super().__init__()
        self.url = url
        self.download_folder = download_folder
        self.file_types = file_types
        self.selected_files = selected_files  # Only download these files
        self.console = console
        self.is_running = True
        self.cache_dir = cache_dir
        self.other_files_dir = other_files_dir
        self.hash_file_path = os.path.join(self.other_files_dir, "file_hashes.json")
        self.file_hashes = self.load_hashes()

    def load_hashes(self):
        """Load the hash data from the JSON file."""
        if os.path.exists(self.hash_file_path):
            try:
                with open(self.hash_file_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.log.emit(f"[ERROR] Failed to load file hashes: {str(e)}", "ERROR")
                return {}
        return {}

    def save_hashes(self):
        """Save the hash data to the JSON file."""
        try:
            with open(self.hash_file_path, 'w') as f:
                json.dump(self.file_hashes, f, indent=4)
        except IOError as e:
            self.log.emit(f"[ERROR] Failed to save file hashes: {str(e)}", "ERROR")

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
        if url not in self.selected_files:
            self.log.emit(f"[INFO] Skipping {url} as it is not selected.", "INFO")
            return

        # Check if file already exists in the hash database
        filename = url.split('f=')[-1] if 'f=' in url else url.split('/')[-1].split('?')[0]
        full_path = os.path.join(folder, filename.replace('/', '_'))
        url_hash = hashlib.md5(url.encode()).hexdigest()

        if url_hash in self.file_hashes:
            existing_path = self.file_hashes[url_hash]["file_path"]
            if os.path.exists(existing_path):
                file_hash = hashlib.md5(open(existing_path, 'rb').read()).hexdigest()
                stored_hash = self.file_hashes[url_hash]["file_hash"]
                if file_hash == stored_hash:
                    self.log.emit(f"[INFO] File {filename} already downloaded at {existing_path}, skipping.", "INFO")
                    return

        try:
            response = requests.get(url, headers=HEADERS, stream=True)
            response.raise_for_status()
            file_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(full_path, 'wb') as f:
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

            # Calculate file hash and store in JSON
            file_hash = hashlib.md5(open(full_path, 'rb').read()).hexdigest()
            self.file_hashes[url_hash] = {
                "file_path": full_path,
                "file_hash": file_hash,
                "url": url
            }
            self.save_hashes()

            self.log.emit(f"[INFO] Successfully downloaded: {full_path}", "INFO")
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
        total_files = len(self.selected_files)
        self.log.emit(f"[INFO] Total selected files to download: {total_files}", "INFO")
        for file_url in files_to_download:
            self.file_detected.emit(file_url)

        if total_files > 0:
            for i, file_url in enumerate(self.selected_files):
                if self.is_running:
                    self.download_file(file_url, post_folder, i, total_files)
        else:
            self.log.emit("[WARNING] No files selected for download.", "WARNING")

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

class PostDownloaderTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.files_to_download = []
        self.file_url_map = {}
        self.all_detected_files = []
        self.post_queue = []
        self.downloading = False
        self.current_preview_url = None
        self.previous_selected_widget = None
        self.cache_dir = self.parent.cache_folder  # Use the cache folder from main.py
        self.other_files_dir = self.parent.other_files_folder  # Use the other files folder from main.py
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.other_files_dir, exist_ok=True)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Left side: Options and Queue
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        post_url_layout = QHBoxLayout()
        self.post_url_input = QLineEdit()
        self.post_url_input.setPlaceholderText("Enter post URL (e.g., https://kemono.su/patreon/user/114138605/post/119966758)")
        self.post_url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        post_url_layout.addWidget(self.post_url_input)
        
        self.post_add_to_queue_btn = QPushButton(qta.icon('fa5s.plus'), "Add to Queue")
        self.post_add_to_queue_btn.clicked.connect(self.add_post_to_queue)
        self.post_add_to_queue_btn.setStyleSheet("background: #4A5B7A; padding: 5px; border-radius: 5px;")
        post_url_layout.addWidget(self.post_add_to_queue_btn)
        left_layout.addLayout(post_url_layout)

        post_queue_group = QGroupBox("Post Queue")
        post_queue_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        post_queue_layout = QVBoxLayout()
        self.post_queue_list = QListWidget()
        self.post_queue_list.setFixedHeight(100)
        self.post_queue_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        post_queue_layout.addWidget(self.post_queue_list)
        post_queue_group.setLayout(post_queue_layout)
        left_layout.addWidget(post_queue_group)

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
        left_layout.addWidget(post_options_group)

        post_progress_layout = QVBoxLayout()
        self.post_file_progress = QProgressBar()
        self.post_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } QProgressBar::chunk { background: #4A5B7A; }")
        post_progress_layout.addWidget(QLabel("File Progress"))
        post_progress_layout.addWidget(self.post_file_progress)
        self.post_overall_progress = QProgressBar()
        self.post_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } QProgressBar::chunk { background: #4A5B7A; }")
        post_progress_layout.addWidget(QLabel("Overall Progress"))
        post_progress_layout.addWidget(self.post_overall_progress)
        left_layout.addLayout(post_progress_layout)

        self.post_console = QTextEdit()
        self.post_console.setReadOnly(True)
        self.post_console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        left_layout.addWidget(self.post_console)

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
        left_layout.addLayout(post_btn_layout)

        left_layout.addStretch()
        layout.addWidget(left_widget, stretch=2)

        # Right side: File List Panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        file_list_group = QGroupBox("Files to Download")
        file_list_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        file_list_layout = QVBoxLayout()

        self.post_search_input = QLineEdit()
        self.post_search_input.setPlaceholderText("Search items...")
        self.post_search_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.post_search_input.textChanged.connect(self.filter_items)
        file_list_layout.addWidget(self.post_search_input)

        # Check ALL checkbox above the filter group
        self.post_check_all = QCheckBox("Check ALL")
        self.post_check_all.setChecked(True)
        self.post_check_all.setStyleSheet("color: white;")
        self.post_check_all.stateChanged.connect(self.toggle_check_all)
        file_list_layout.addWidget(self.post_check_all)

        # Filter by Type group
        self.post_filter_group = QGroupBox("Filter by Type")
        self.post_filter_group.setStyleSheet("QGroupBox { color: white; }")
        filter_layout = QGridLayout()
        self.post_filter_checks = {
            '.jpg': QCheckBox("JPG"),
            '.jpeg': QCheckBox("JPEG"),
            '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"),
            '.mp4': QCheckBox("MP4"),
            '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"),
            '.7z': QCheckBox("7Z")
        }
        for i, (ext, check) in enumerate(self.post_filter_checks.items()):
            check.setChecked(True)
            check.stateChanged.connect(self.filter_items)
            filter_layout.addWidget(check, i // 3, i % 3)
        self.post_filter_group.setLayout(filter_layout)
        file_list_layout.addWidget(self.post_filter_group)

        # File list
        self.post_file_list = QListWidget()
        self.post_file_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.post_file_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.post_file_list.itemClicked.connect(self.handle_item_click)
        self.post_file_list.itemChanged.connect(self.update_checked_files)
        self.post_file_list.currentItemChanged.connect(self.update_current_preview_url)
        file_list_layout.addWidget(self.post_file_list)

        # Bottom row: File count and view button
        bottom_layout = QHBoxLayout()
        self.post_file_count_label = QLabel("Files: 0")
        self.post_file_count_label.setStyleSheet("color: white;")
        bottom_layout.addWidget(self.post_file_count_label)

        self.post_view_button = QPushButton(qta.icon('fa5s.eye'), "")
        self.post_view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
        self.post_view_button.clicked.connect(self.view_current_item)
        self.post_view_button.setEnabled(False)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.post_view_button)

        file_list_layout.addLayout(bottom_layout)

        file_list_group.setLayout(file_list_layout)
        right_layout.addWidget(file_list_group)
        right_layout.addStretch()
        layout.addWidget(right_widget, stretch=1)

        # Button animations
        self.post_download_btn.enterEvent = lambda e: self.parent.animate_button(self.post_download_btn, True)
        self.post_download_btn.leaveEvent = lambda e: self.parent.animate_button(self.post_download_btn, False)
        self.post_cancel_btn.enterEvent = lambda e: self.parent.animate_button(self.post_cancel_btn, True)
        self.post_cancel_btn.leaveEvent = lambda e: self.parent.animate_button(self.post_cancel_btn, False)

    def add_post_to_queue(self):
        url = self.post_url_input.text().strip()
        if not url:
            self.append_log_to_console("[ERROR] No URL entered.", "ERROR")
            return
        if any(item[0] == url for item in self.post_queue):
            self.append_log_to_console("[WARNING] URL already in queue.", "WARNING")
            return
        if self.check_post_url_validity(url):
            self.post_queue.append((url, False))
            self.update_post_queue_list()
            self.post_url_input.clear()
            self.append_log_to_console(f"[INFO] Added post URL to queue: {url}", "INFO")
        else:
            self.append_log_to_console(f"[ERROR] Invalid post URL or failed to fetch: {url}", "ERROR")

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

    def create_view_handler(self, url, checked):
        def handler():
            if not checked:
                self.check_post_from_queue(url)
        return handler

    def create_remove_handler(self, url):
        def handler():
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
                    self.update_post_queue_list()
                    self.append_log_to_console(f"[INFO] Link ({url}) is removed from the queue.", "INFO")
                    if not any(c for _, c in self.post_queue):
                        self.post_file_list.clear()
                        self.all_detected_files = []
                        self.files_to_download = []
                        self.file_url_map = {}
                        self.previous_selected_widget = None
                else:
                    self.append_log_to_console(f"[WARNING] URL ({url}) not found in queue.", "WARNING")
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
            view_button.clicked.connect(self.create_view_handler(url, checked))
            layout.addWidget(view_button)

            label = QLabel(url)
            label.setStyleSheet("color: white;")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(label, stretch=1)

            remove_button = QPushButton(qta.icon('fa5s.times'), "")
            remove_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
            remove_button.clicked.connect(self.create_remove_handler(url))
            layout.addWidget(remove_button)

            widget.setLayout(layout)
            item.setSizeHint(widget.sizeHint())
            self.post_queue_list.addItem(item)
            self.post_queue_list.setItemWidget(item, widget)
            widget.view_button = view_button
            widget.label = label
            widget.remove_button = remove_button

    def check_post_from_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        self.append_log_to_console(f"[INFO] Checking post from queue: {url}", "INFO")
        self.post_file_list.clear()
        self.all_detected_files = []
        self.files_to_download = []
        self.file_url_map = {}
        self.previous_selected_widget = None
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
            self.append_log_to_console(f"[ERROR] Failed to check post: {url}", "ERROR")

    def check_post(self, url):
        self.append_log_to_console(f"[INFO] Checking post with URL: {url}", "INFO")
        parts = url.split('/')
        if len(parts) < 7 or 'kemono.su' not in url:
            self.append_log_to_console("[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[user_id]/post/[post_id]", "ERROR")
            return False
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        response = requests.get(api_url, headers=HEADERS)
        if response.status_code != 200:
            self.append_log_to_console(f"[ERROR] Failed to fetch post - Status code: {response.status_code}", "ERROR")
            return False
        
        post_data = response.json()
        if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
            self.append_log_to_console("[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2), "ERROR")
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

        self.all_detected_files = detected_files
        self.update_checked_files()  # Ensure files_to_download is updated here
        return True

    def start_post_download(self):
        selected_urls = [url for url, checked in self.post_queue if checked]
        if not selected_urls:
            self.append_log_to_console("[WARNING] No posts selected to download. Please check posts in the queue.", "WARNING")
            return

        self.downloading = True
        self.parent.tabs.setTabEnabled(1, False)
        self.parent.status_label.setText("Checking posts...")
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
            self.append_log_to_console(f"[DEBUG] Files to download for {url}: {self.files_to_download}", "INFO")
            if not self.files_to_download:
                self.append_log_to_console(f"[WARNING] No files selected for download from {url}. Skipping.", "WARNING")
                self.process_next_post(remaining_urls)
                return
            self.thread = DownloadThread(url, self.parent.download_folder, file_types, self.files_to_download, self.post_console, self.cache_dir, self.other_files_dir)
            self.thread.progress.connect(self.update_post_file_progress)
            self.thread.overall_progress.connect(self.update_post_overall_progress)
            self.thread.log.connect(self.append_log_to_console)
            self.thread.finished.connect(lambda: self.process_next_post(remaining_urls))
            self.thread.start()
        else:
            self.process_next_post(remaining_urls)

    def cancel_post_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.append_log_to_console("[WARNING] Download cancelled by user", "WARNING")
            self.post_download_finished()

    def update_post_file_progress(self, value):
        self.post_file_progress.setValue(value)

    def update_post_overall_progress(self, value):
        self.post_overall_progress.setValue(value)

    def post_download_finished(self):
        self.downloading = False
        self.parent.tabs.setTabEnabled(1, True)
        self.parent.status_label.setText("Idle")
        self.post_download_btn.setEnabled(True)
        self.post_cancel_btn.setEnabled(False)
        self.append_log_to_console("[INFO] Download process ended", "INFO")

    def toggle_check_all(self, state):
        is_checked = state == 2
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        self.files_to_download = []
        for i in range(self.post_file_list.count()):
            item = self.post_file_list.item(i)
            if not item.isHidden():
                widget = self.post_file_list.itemWidget(item)
                if widget:
                    widget.check_box.setCheckState(new_state)
        self.update_checked_files()
        all_visible_checked = all(self.post_file_list.itemWidget(self.post_file_list.item(i)).check_box.checkState() == Qt.CheckState.Checked 
                                for i in range(self.post_file_list.count()) if not self.post_file_list.item(i).isHidden())
        self.post_check_all.blockSignals(True)
        self.post_check_all.setChecked(all_visible_checked)
        self.post_check_all.blockSignals(False)

    def update_checked_files(self):
        self.files_to_download = []
        seen_urls = set()
        for i in range(self.post_file_list.count()):
            item_widget = self.post_file_list.itemWidget(self.post_file_list.item(i))
            if item_widget and not self.post_file_list.item(i).isHidden() and item_widget.check_box.checkState() == Qt.CheckState.Checked:
                file_name = item_widget.label.text()
                if file_name in self.file_url_map:
                    file_url = self.file_url_map[file_name]
                    if file_url not in seen_urls:
                        self.files_to_download.append(file_url)
                        seen_urls.add(file_url)
        self.post_file_count_label.setText(f"Files: {len(self.files_to_download)}")

    def filter_items(self):
        search_text = self.post_search_input.text().lower()
        active_filters = [ext for ext, check in self.post_filter_checks.items() if check.isChecked()]
        
        self.post_file_list.clear()
        self.previous_selected_widget = None
        for file_name, file_url in self.all_detected_files:
            file_ext = os.path.splitext(file_name)[1].lower()
            if (not search_text or search_text in file_name.lower()) and (not active_filters or file_ext in active_filters):
                self.add_list_item(file_name, file_url)

        all_visible_checked = all(self.post_file_list.itemWidget(self.post_file_list.item(i)).check_box.checkState() == Qt.CheckState.Checked 
                                for i in range(self.post_file_list.count()) if not self.post_file_list.item(i).isHidden())
        self.post_check_all.blockSignals(True)
        self.post_check_all.setChecked(all_visible_checked)
        self.post_check_all.blockSignals(False)
        self.update_checked_files()

    def add_list_item(self, text, url):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, url)
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
        self.post_file_list.addItem(item)
        self.post_file_list.setItemWidget(item, widget)
        widget.check_box = check_box
        widget.label = label
        widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")

    def update_current_preview_url(self, current, previous):
        if current:
            widget = self.post_file_list.itemWidget(current)
            if widget:
                self.current_preview_url = current.data(Qt.UserRole)
                self.post_view_button.setEnabled(True)
            else:
                self.current_preview_url = None
                self.post_view_button.setEnabled(False)
        else:
            self.current_preview_url = None
            self.post_view_button.setEnabled(False)

    def view_current_item(self):
        if self.current_preview_url:
            if self.current_preview_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                modal = ImageModal(self.current_preview_url, self.cache_dir, self)
                modal.exec()
            else:
                self.append_log_to_console(f"[WARNING] Viewing not supported for {self.current_preview_url}", "WARNING")

    def handle_item_click(self, item):
        if item:
            if self.previous_selected_widget:
                self.previous_selected_widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")
            widget = self.post_file_list.itemWidget(item)
            if widget:
                widget.setStyleSheet("background-color: #4A5B7A; border-radius: 5px;")
                self.previous_selected_widget = widget
                self.current_preview_url = item.data(Qt.UserRole)
                self.post_view_button.setEnabled(True)
            else:
                self.current_preview_url = None
                self.post_view_button.setEnabled(False)
        else:
            if self.previous_selected_widget:
                self.previous_selected_widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")
                self.previous_selected_widget = None
            self.current_preview_url = None
            self.post_view_button.setEnabled(False)

    def append_log_to_console(self, message, level="INFO"):
        color = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}.get(level, "white")
        self.post_console.append(f"<span style='color:{color}'>{message}</span>")

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