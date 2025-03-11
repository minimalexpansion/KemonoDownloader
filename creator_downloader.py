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

# Reuse the PreviewThread and ImageModal with caching support
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

class CreatorDownloadThread(QThread):
    progress = pyqtSignal(int)
    overall_progress = pyqtSignal(int)
    log = pyqtSignal(str, str)
    finished = pyqtSignal()
    post_detected = pyqtSignal(str, str)

    def __init__(self, service, creator_id, download_folder, file_types, selected_posts, console, other_files_dir):
        super().__init__()
        self.service = service
        self.creator_id = creator_id
        self.download_folder = download_folder
        self.file_types = file_types
        self.selected_posts = selected_posts
        self.console = console
        self.is_running = True
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
                
                # Check if file already exists in the hash database
                filename = file_url.split('f=')[-1] if 'f=' in file_url else file_url.split('/')[-1].split('?')[0]
                full_path = os.path.join(post_folder, filename.replace('/', '_'))
                url_hash = hashlib.md5(file_url.encode()).hexdigest()

                if url_hash in self.file_hashes:
                    existing_path = self.file_hashes[url_hash]["file_path"]
                    if os.path.exists(existing_path):
                        file_hash = hashlib.md5(open(existing_path, 'rb').read()).hexdigest()
                        stored_hash = self.file_hashes[url_hash]["file_hash"]
                        if file_hash == stored_hash:
                            self.log.emit(f"[INFO] File {filename} already downloaded at {existing_path}, skipping.", "INFO")
                            files_processed += 1
                            if total_files > 0:
                                self.overall_progress.emit(int((files_processed / total_files) * 100))
                            continue

                try:
                    response = requests.get(file_url, headers=HEADERS, stream=True)
                    response.raise_for_status()
                    file_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(full_path, 'wb') as f:
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

                    # Calculate file hash and store in JSON
                    file_hash = hashlib.md5(open(full_path, 'rb').read()).hexdigest()
                    self.file_hashes[url_hash] = {
                        "file_path": full_path,
                        "file_hash": file_hash,
                        "url": file_url
                    }
                    self.save_hashes()

                    self.log.emit(f"[INFO] Successfully downloaded: {full_path}", "INFO")
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

class CreatorDownloaderTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.posts_to_download = []
        self.post_url_map = {}
        self.all_detected_posts = []
        self.creator_queue = []
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

        creator_url_layout = QHBoxLayout()
        self.creator_url_input = QLineEdit()
        self.creator_url_input.setPlaceholderText("Enter creator URL (e.g., https://kemono.su/patreon/user/11413860)")
        self.creator_url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        creator_url_layout.addWidget(self.creator_url_input)
        
        self.creator_add_to_queue_btn = QPushButton(qta.icon('fa5s.plus'), "Add to Queue")
        self.creator_add_to_queue_btn.clicked.connect(self.add_creator_to_queue)
        self.creator_add_to_queue_btn.setStyleSheet("background: #4A5B7A; padding: 5px; border-radius: 5px;")
        creator_url_layout.addWidget(self.creator_add_to_queue_btn)
        left_layout.addLayout(creator_url_layout)

        creator_queue_group = QGroupBox("Creator Queue")
        creator_queue_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        creator_queue_layout = QVBoxLayout()
        self.creator_queue_list = QListWidget()
        self.creator_queue_list.setFixedHeight(100)
        self.creator_queue_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        creator_queue_layout.addWidget(self.creator_queue_list)
        creator_queue_group.setLayout(creator_queue_layout)
        left_layout.addWidget(creator_queue_group)

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
        left_layout.addWidget(creator_options_group)

        creator_progress_layout = QVBoxLayout()
        self.creator_file_progress = QProgressBar()
        self.creator_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } QProgressBar::chunk { background: #4A5B7A; }")
        creator_progress_layout.addWidget(QLabel("File Progress"))
        creator_progress_layout.addWidget(self.creator_file_progress)
        self.creator_overall_progress = QProgressBar()
        self.creator_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } QProgressBar::chunk { background: #4A5B7A; }")
        creator_progress_layout.addWidget(QLabel("Overall Progress"))
        creator_progress_layout.addWidget(self.creator_overall_progress)
        left_layout.addLayout(creator_progress_layout)

        self.creator_console = QTextEdit()
        self.creator_console.setReadOnly(True)
        self.creator_console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        left_layout.addWidget(self.creator_console)

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
        left_layout.addLayout(creator_btn_layout)

        left_layout.addStretch()
        layout.addWidget(left_widget, stretch=2)

        # Right side: Post List Panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        post_list_group = QGroupBox("Posts to Download")
        post_list_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; padding: 10px; }")
        post_list_layout = QVBoxLayout()

        self.creator_search_input = QLineEdit()
        self.creator_search_input.setPlaceholderText("Search posts...")
        self.creator_search_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        self.creator_search_input.textChanged.connect(self.filter_items)
        post_list_layout.addWidget(self.creator_search_input)

        # Check ALL checkbox
        self.creator_check_all = QCheckBox("Check ALL")
        self.creator_check_all.setChecked(True)
        self.creator_check_all.setStyleSheet("color: white;")
        self.creator_check_all.stateChanged.connect(self.toggle_check_all)
        post_list_layout.addWidget(self.creator_check_all)

        # Post list
        self.creator_post_list = QListWidget()
        self.creator_post_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.creator_post_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.creator_post_list.itemClicked.connect(self.handle_item_click)
        self.creator_post_list.itemChanged.connect(self.update_checked_posts)
        self.creator_post_list.currentItemChanged.connect(self.update_current_preview_url)
        post_list_layout.addWidget(self.creator_post_list)

        # Bottom row: Post count and view button
        bottom_layout = QHBoxLayout()
        self.creator_post_count_label = QLabel("Posts: 0")
        self.creator_post_count_label.setStyleSheet("color: white;")
        bottom_layout.addWidget(self.creator_post_count_label)

        self.creator_view_button = QPushButton(qta.icon('fa5s.eye'), "")
        self.creator_view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
        self.creator_view_button.clicked.connect(self.view_current_item)
        self.creator_view_button.setEnabled(False)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.creator_view_button)

        post_list_layout.addLayout(bottom_layout)

        post_list_group.setLayout(post_list_layout)
        right_layout.addWidget(post_list_group)
        right_layout.addStretch()
        layout.addWidget(right_widget, stretch=1)

        # Button animations
        self.creator_download_btn.enterEvent = lambda e: self.parent.animate_button(self.creator_download_btn, True)
        self.creator_download_btn.leaveEvent = lambda e: self.parent.animate_button(self.creator_download_btn, False)
        self.creator_cancel_btn.enterEvent = lambda e: self.parent.animate_button(self.creator_cancel_btn, True)
        self.creator_cancel_btn.leaveEvent = lambda e: self.parent.animate_button(self.creator_cancel_btn, False)

    def add_creator_to_queue(self):
        url = self.creator_url_input.text().strip()
        if not url:
            self.append_log_to_console("[ERROR] No URL entered.", "ERROR")
            return
        if any(item[0] == url for item in self.creator_queue):
            self.append_log_to_console("[WARNING] URL already in queue.", "WARNING")
            return
        if self.check_creator_url_validity(url):
            self.creator_queue.append((url, False))
            self.update_creator_queue_list()
            self.creator_url_input.clear()
            self.append_log_to_console(f"[INFO] Added creator URL to queue: {url}", "INFO")
        else:
            self.append_log_to_console(f"[ERROR] Invalid creator URL or failed to fetch: {url}", "ERROR")

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

    def create_view_handler(self, url, checked):
        def handler():
            if not checked:
                self.check_creator_from_queue(url)
        return handler

    def create_remove_handler(self, url):
        def handler():
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
                    self.update_creator_queue_list()
                    self.append_log_to_console(f"[INFO] Link ({url}) is removed from the queue.", "INFO")
                    if not any(c for _, c in self.creator_queue):
                        self.creator_post_list.clear()
                        self.all_detected_posts = []
                        self.posts_to_download = []
                        self.post_url_map = {}
                        self.previous_selected_widget = None
                else:
                    self.append_log_to_console(f"[WARNING] URL ({url}) not found in queue.", "WARNING")
        return handler

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
            self.creator_queue_list.addItem(item)
            self.creator_queue_list.setItemWidget(item, widget)
            widget.view_button = view_button
            widget.label = label
            widget.remove_button = remove_button

    def check_creator_from_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        self.append_log_to_console(f"[INFO] Checking creator from queue: {url}", "INFO")
        self.creator_post_list.clear()
        self.all_detected_posts = []
        self.posts_to_download = []
        self.post_url_map = {}
        self.previous_selected_widget = None
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
            self.append_log_to_console(f"[ERROR] Failed to check creator: {url}", "ERROR")

    def check_creator(self, url):
        self.append_log_to_console(f"[INFO] Checking creator with URL: {url}", "INFO")
        parts = url.split('/')
        if len(parts) < 5 or 'kemono.su' not in url or parts[-2] != 'user':
            self.append_log_to_console("[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[creator_id]", "ERROR")
            return False
        service, creator_id = parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}"
        response = requests.get(api_url, headers=HEADERS)
        if response.status_code != 200:
            self.append_log_to_console(f"[ERROR] Failed to fetch creator posts - Status code: {response.status_code}", "ERROR")
            return False
        
        posts_data = response.json()
        if not posts_data or not isinstance(posts_data, list):
            self.append_log_to_console("[ERROR] No valid posts data returned! Response: " + json.dumps(posts_data, indent=2), "ERROR")
            return False

        self.posts_to_download = []
        self.post_url_map = {}

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
            if thumbnail_url:
                detected_posts.append((title, (post_id, thumbnail_url)))
                self.post_url_map[title] = (post_id, thumbnail_url)

        self.all_detected_posts = detected_posts
        self.update_checked_posts()  # Ensure posts_to_download is updated here
        return True

    def start_creator_download(self):
        selected_urls = [url for url, checked in self.creator_queue if checked]
        if not selected_urls:
            self.append_log_to_console("[WARNING] No creators selected to download. Please check creators in the queue.", "WARNING")
            return

        self.downloading = True
        self.parent.tabs.setTabEnabled(0, False)
        self.parent.status_label.setText("Checking creators...")
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
                self.append_log_to_console("[ERROR] Invalid URL format. Expected: https://kemono.su/[service]/user/[creator_id]", "ERROR")
                self.process_next_creator(remaining_urls)
                return
            service, creator_id = parts[-3], parts[-1]

            file_types = {
                'main': self.creator_main_check.isChecked(),
                'attachments': self.creator_attachments_check.isChecked(),
                'content': self.creator_content_check.isChecked(),
                'extensions': [ext for ext, check in self.creator_ext_checks.items() if check.isChecked()]
            }
            self.append_log_to_console(f"[DEBUG] Posts to download for {url}: {self.posts_to_download}", "INFO")
            if not self.posts_to_download:
                self.append_log_to_console(f"[WARNING] No posts selected for download from {url}. Skipping.", "WARNING")
                self.process_next_creator(remaining_urls)
                return
            self.thread = CreatorDownloadThread(service, creator_id, self.parent.download_folder, file_types, self.posts_to_download, self.creator_console, self.other_files_dir)
            self.thread.progress.connect(self.update_creator_file_progress)
            self.thread.overall_progress.connect(self.update_creator_overall_progress)
            self.thread.log.connect(self.append_log_to_console)
            self.thread.finished.connect(lambda: self.process_next_creator(remaining_urls))
            self.thread.start()
        else:
            self.process_next_creator(remaining_urls)

    def cancel_creator_download(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.append_log_to_console("[WARNING] Download cancelled by user", "WARNING")
            self.creator_download_finished()

    def update_creator_file_progress(self, value):
        self.creator_file_progress.setValue(value)

    def update_creator_overall_progress(self, value):
        self.creator_overall_progress.setValue(value)

    def creator_download_finished(self):
        self.downloading = False
        self.parent.tabs.setTabEnabled(0, True)
        self.parent.status_label.setText("Idle")
        self.creator_download_btn.setEnabled(True)
        self.creator_cancel_btn.setEnabled(False)
        self.append_log_to_console("[INFO] Download process ended", "INFO")

    def toggle_check_all(self, state):
        is_checked = state == 2
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        self.posts_to_download = []
        for i in range(self.creator_post_list.count()):
            item = self.creator_post_list.item(i)
            if not item.isHidden():
                widget = self.creator_post_list.itemWidget(item)
                if widget:
                    widget.check_box.setCheckState(new_state)
        self.update_checked_posts()
        all_visible_checked = all(self.creator_post_list.itemWidget(self.creator_post_list.item(i)).check_box.checkState() == Qt.CheckState.Checked 
                                for i in range(self.creator_post_list.count()) if not self.creator_post_list.item(i).isHidden())
        self.creator_check_all.blockSignals(True)
        self.creator_check_all.setChecked(all_visible_checked)
        self.creator_check_all.blockSignals(False)

    def update_checked_posts(self):
        self.posts_to_download = []
        seen_ids = set()
        for i in range(self.creator_post_list.count()):
            item_widget = self.creator_post_list.itemWidget(self.creator_post_list.item(i))
            if item_widget and not self.creator_post_list.item(i).isHidden() and item_widget.check_box.checkState() == Qt.CheckState.Checked:
                post_title = item_widget.label.text()
                if post_title in self.post_url_map:
                    post_id, _ = self.post_url_map[post_title]
                    if post_id not in seen_ids:
                        self.posts_to_download.append(post_id)
                        seen_ids.add(post_id)
        self.creator_post_count_label.setText(f"Posts: {len(self.posts_to_download)}")

    def filter_items(self):
        search_text = self.creator_search_input.text().lower()
        
        self.creator_post_list.clear()
        self.previous_selected_widget = None
        for post_title, (post_id, thumbnail_url) in self.all_detected_posts:
            if not search_text or search_text in post_title.lower():
                self.add_list_item(post_title, thumbnail_url)

        all_visible_checked = all(self.creator_post_list.itemWidget(self.creator_post_list.item(i)).check_box.checkState() == Qt.CheckState.Checked 
                                for i in range(self.creator_post_list.count()) if not self.creator_post_list.item(i).isHidden())
        self.creator_check_all.blockSignals(True)
        self.creator_check_all.setChecked(all_visible_checked)
        self.creator_check_all.blockSignals(False)
        self.update_checked_posts()

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
        self.creator_post_list.addItem(item)
        self.creator_post_list.setItemWidget(item, widget)
        widget.check_box = check_box
        widget.label = label
        widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")

    def update_current_preview_url(self, current, previous):
        if current:
            widget = self.creator_post_list.itemWidget(current)
            if widget:
                self.current_preview_url = current.data(Qt.UserRole)
                self.creator_view_button.setEnabled(True)
            else:
                self.current_preview_url = None
                self.creator_view_button.setEnabled(False)
        else:
            self.current_preview_url = None
            self.creator_view_button.setEnabled(False)

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
            widget = self.creator_post_list.itemWidget(item)
            if widget:
                widget.setStyleSheet("background-color: #4A5B7A; border-radius: 5px;")
                self.previous_selected_widget = widget
                self.current_preview_url = item.data(Qt.UserRole)
                self.creator_view_button.setEnabled(True)
            else:
                self.current_preview_url = None
                self.creator_view_button.setEnabled(False)
        else:
            if self.previous_selected_widget:
                self.previous_selected_widget.setStyleSheet("background-color: #2A3B5A; border-radius: 5px;")
                self.previous_selected_widget = None
            self.current_preview_url = None
            self.creator_view_button.setEnabled(False)

    def append_log_to_console(self, message, level="INFO"):
        color = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}.get(level, "white")
        self.creator_console.append(f"<span style='color:{color}'>{message}</span>")