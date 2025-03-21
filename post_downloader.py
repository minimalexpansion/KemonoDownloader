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
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36", "Referer": "https://kemono.su/"}
API_BASE = "https://kemono.su/api/v1"

# Define PreviewThread class
class PreviewThread(QThread):
    preview_ready = pyqtSignal(str, object)
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
                scaled_pixmap.save(cache_path)
                self.preview_ready.emit(self.url, scaled_pixmap)
            except requests.RequestException as e:
                self.error.emit(f"Failed to download image from {self.url}: {str(e)}")
            except Exception as e:
                self.error.emit(f"Unexpected error while processing image from {self.url}: {str(e)}")

# Define ImageModal class
class ImageModal(QDialog):
    def __init__(self, image_url, cache_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.setModal(True)
        self.resize(800, 800)
        self.image_url = image_url
        self.cache_dir = cache_dir
        self.init_ui()
        self.start_preview()

    def init_ui(self):
        layout = QVBoxLayout()
        self.image_label = QLabel("Loading Image...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; } QProgressBar::chunk { background: #4A5B7A; }")
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

    def start_preview(self):
        self.preview_thread = PreviewThread(self.image_url, self.cache_dir)
        self.preview_thread.preview_ready.connect(self.display_image)
        self.preview_thread.progress.connect(self.update_progress)
        self.preview_thread.error.connect(self.display_error)
        self.preview_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.image_label.setText(f"Loading Image... ({value}%)")

    def display_image(self, url, pixmap):
        self.image_label.setText("")
        self.progress_bar.hide()
        self.image_label.setPixmap(pixmap)

    def display_error(self, error_message):
        self.image_label.setText("Error loading image")
        self.progress_bar.hide()
        QMessageBox.critical(self, "Image Load Error", error_message)

    def resizeEvent(self, event):
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            pixmap = self.image_label.pixmap()
            scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

# Define PostDetectionThread class
class PostDetectionThread(QThread):
    finished = pyqtSignal(list)
    log = pyqtSignal(str, str)
    error = pyqtSignal(str)
    file_detected = pyqtSignal(list)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.is_running = True

    def stop(self):
        self.is_running = False
        self.log.emit("[INFO] PostDetectionThread cancellation initiated", "INFO")

    def run(self):
        self.log.emit(f"[INFO] Checking post with URL: {self.url}", "INFO")
        if not self.is_running:
            self.log.emit("[INFO] PostDetectionThread stopped before starting", "INFO")
            return

        parts = self.url.split('/')
        if len(parts) < 7 or 'kemono.su' not in self.url:
            self.error.emit("Invalid URL format. Expected: https://kemono.su/[service]/user/[user_id]/post/[post_id]")
            return
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"

        try:
            response = requests.get(api_url, headers=HEADERS, timeout=10)
            if not self.is_running:
                self.log.emit("[INFO] PostDetectionThread stopped during request", "INFO")
                return
            if response.status_code != 200:
                self.log.emit(f"[ERROR] Failed to fetch post - Status code: {response.status_code}", "ERROR")
                self.error.emit(f"Failed to fetch post - Status code: {response.status_code}")
                return

            post_data = response.json()
            if not post_data or (isinstance(post_data, list) and not post_data) or (isinstance(post_data, dict) and not post_data):
                self.log.emit("[ERROR] No valid post data returned! Response: " + json.dumps(post_data, indent=2), "ERROR")
                self.error.emit("No valid post data returned")
                return

            post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
            detected_files = [(post.get('title', f"File {post_id}"), post_id)]
            self.log.emit(f"[INFO] Post fetched for {self.url}: {post.get('title', f'File {post_id}')}", "INFO")
            
            files = self.detect_files(post)
            if self.is_running:
                self.file_detected.emit(files)
                self.finished.emit(detected_files)
            else:
                self.log.emit("[INFO] PostDetectionThread stopped before emitting results", "INFO")

        except requests.RequestException as e:
            self.log.emit(f"[ERROR] Failed to fetch post: {str(e)}", "ERROR")
            self.error.emit(f"Failed to fetch post: {str(e)}")
            return

    def detect_files(self, post):
        detected_files = []
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.zip', '.mp4', '.pdf', '.7z', 
                          '.mp3', '.wav', '.rar', '.mov', '.docx', '.psd']
        if 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1].lower() or os.path.splitext(file_name)[1].lower()
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if file_ext in allowed_extensions:
                detected_files.append((file_name, file_url))

        if 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1].lower() or os.path.splitext(attachment_name)[1].lower()
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if attachment_ext in allowed_extensions:
                        detected_files.append((attachment_name, attachment_url))

        if 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                img_name = os.path.basename(img_url)
                if img_ext in allowed_extensions:
                    detected_files.append((img_name, img_url))

        return list(dict.fromkeys(detected_files))

class FilePreparationThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list, dict)
    log = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, post_ids, all_files_map, post_ext_checks, file_url_map, max_concurrent=10):
        super().__init__()
        self.post_ids = post_ids
        self.all_files_map = all_files_map
        self.post_ext_checks = post_ext_checks
        self.file_url_map = file_url_map
        self.max_concurrent = max_concurrent
        self.is_running = True

    def stop(self):
        self.is_running = False
        self.log.emit("[INFO] FilePreparationThread cancellation initiated", "INFO")

    def detect_files(self, post, allowed_extensions):
        files_to_download = []
        self.log.emit(f"[DEBUG] Detecting files for post with allowed extensions: {allowed_extensions}", "INFO")
        
        if 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1].lower() or os.path.splitext(file_name)[1].lower()
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            self.log.emit(f"[DEBUG] Checking main file: {file_name} ({file_ext})", "INFO")
            if '.jpg' in allowed_extensions and file_ext in ['.jpg', '.jpeg']:
                self.log.emit(f"[DEBUG] Added main file: {file_name}", "INFO")
                files_to_download.append((file_name, file_url))
            elif file_ext in allowed_extensions:
                self.log.emit(f"[DEBUG] Added main file: {file_name}", "INFO")
                files_to_download.append((file_name, file_url))

        if 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1].lower() or os.path.splitext(attachment_name)[1].lower()
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    self.log.emit(f"[DEBUG] Checking attachment: {attachment_name} ({attachment_ext})", "INFO")
                    if '.jpg' in allowed_extensions and attachment_ext in ['.jpg', '.jpeg']:
                        self.log.emit(f"[DEBUG] Added attachment: {attachment_name}", "INFO")
                        files_to_download.append((attachment_name, attachment_url))
                    elif attachment_ext in allowed_extensions:
                        self.log.emit(f"[DEBUG] Added attachment: {attachment_name}", "INFO")
                        files_to_download.append((attachment_name, attachment_url))

        if 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                img_name = os.path.basename(img_url)
                self.log.emit(f"[DEBUG] Checking content image: {img_name} ({img_ext})", "INFO")
                if '.jpg' in allowed_extensions and img_ext in ['.jpg', '.jpeg']:
                    self.log.emit(f"[DEBUG] Added content image: {img_name}", "INFO")
                    files_to_download.append((img_name, img_url))
                elif img_ext in allowed_extensions:
                    self.log.emit(f"[DEBUG] Added content image: {img_name}", "INFO")
                    files_to_download.append((img_name, img_url))

        self.log.emit(f"[DEBUG] Total files detected: {len(files_to_download)}", "INFO")
        return list(dict.fromkeys(files_to_download))

    def fetch_and_detect_files(self, post_id, post_url):
        if not self.is_running:
            self.log.emit("[INFO] FilePreparationThread stopped during fetch", "INFO")
            return None

        parts = post_url.split('/')
        service, creator_id = parts[-5], parts[-3]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        try:
            response = requests.get(api_url, headers=HEADERS)
            if not self.is_running:
                self.log.emit("[INFO] FilePreparationThread stopped during request", "INFO")
                return None
            if response.status_code != 200:
                self.log.emit(f"[ERROR] Failed to fetch {api_url} - Status code: {response.status_code}", "ERROR")
                return None
            post_data = response.json()
            post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
            self.log.emit(f"[DEBUG] Post data for {post_id}: {json.dumps(post, indent=2)}", "INFO")
            allowed_extensions = [ext.lower() for ext, check in self.post_ext_checks.items() if check]
            detected_files = self.detect_files(post, allowed_extensions)
            files_to_download = [(file_name, file_url) for file_name, file_url in detected_files]
            return (post_id, files_to_download)
        except Exception as e:
            self.log.emit(f"[ERROR] Error fetching post {post_id}: {str(e)}", "ERROR")
            return None

    def run(self):
        files_to_download = []
        files_to_posts_map = {}
        allowed_extensions = [ext.lower() for ext, check in self.post_ext_checks.items() if check]
        self.log.emit(f"[DEBUG] Allowed extensions for download: {allowed_extensions}", "INFO")

        total_posts = len(self.post_ids)
        completed_posts = 0

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            future_to_post = {executor.submit(self.fetch_and_detect_files, post_id, post_url): post_id
                             for post_url, posts in self.all_files_map.items()
                             for _, post_id in posts
                             if post_id in self.post_ids}
            
            for future in as_completed(future_to_post):
                if not self.is_running:
                    self.log.emit("[INFO] FilePreparationThread stopped during execution", "INFO")
                    break
                result = future.result()
                if result:
                    post_id, detected_files = result
                    for file_name, file_url in detected_files:
                        self.log.emit(f"[DEBUG] Detected file: {file_name} from {file_url}", "INFO")
                        files_to_download.append(file_url)
                        files_to_posts_map[file_url] = post_id
                completed_posts += 1
                progress = min(int((completed_posts / total_posts) * 100), 100)
                self.progress.emit(progress)

        if self.is_running:
            files_to_download = list(dict.fromkeys(files_to_download))
            self.log.emit(f"[DEBUG] Total files to download: {len(files_to_download)}", "INFO")
            self.finished.emit(files_to_download, files_to_posts_map)
        else:
            self.log.emit("[INFO] FilePreparationThread stopped before emitting results", "INFO")

class DownloadThread(QThread):
    file_progress = pyqtSignal(int, int)
    file_completed = pyqtSignal(int, str)
    post_completed = pyqtSignal(str)
    log = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, url, download_folder, selected_files, files_to_posts_map, console, other_files_dir, post_id, max_concurrent=5):
        super().__init__()
        self.url = url
        self.download_folder = download_folder
        self.selected_files = selected_files
        self.files_to_posts_map = files_to_posts_map
        self.console = console
        self.is_running = True
        self.other_files_dir = other_files_dir
        self.hash_file_path = os.path.join(self.other_files_dir, "file_hashes.json")
        self.file_hashes = self.load_hashes()
        self.max_concurrent = max_concurrent
        self.post_id = post_id
        self.service = self.extract_service_from_url(url)
        self.post_files_map = self.build_post_files_map()
        self.completed_files = set()

    def extract_service_from_url(self, url):
        parts = url.split('/')
        if len(parts) >= 5 and 'kemono.su' in url:
            return parts[-5]
        return "unknown_service"

    def build_post_files_map(self):
        post_files_map = {self.post_id: []}
        for file_url in self.selected_files:
            post_id = self.files_to_posts_map.get(file_url)
            if post_id == self.post_id:
                post_files_map[post_id].append(file_url)
        return post_files_map

    def load_hashes(self):
        os.makedirs(self.other_files_dir, exist_ok=True)
        if os.path.exists(self.hash_file_path):
            try:
                with open(self.hash_file_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.log.emit(f"[ERROR] Failed to load file hashes: {str(e)}", "ERROR")
                return {}
        return {}

    def save_hashes(self):
        os.makedirs(self.other_files_dir, exist_ok=True)
        try:
            with open(self.hash_file_path, 'w') as f:
                json.dump(self.file_hashes, f, indent=4)
        except IOError as e:
            self.log.emit(f"[ERROR] Failed to save file hashes: {str(e)}", "ERROR")

    def stop(self):
        self.is_running = False
        self.log.emit("[INFO] DownloadThread cancellation initiated", "INFO")

    def download_file(self, file_url, folder, file_index, total_files):
        if not self.is_running or file_url not in self.selected_files:
            self.log.emit(f"[INFO] Skipping {file_url} due to cancellation", "INFO")
            return

        post_id = self.files_to_posts_map.get(file_url, self.post_id)
        service_folder = os.path.join(folder, self.service)
        post_folder = os.path.join(service_folder, f"post_{post_id}")
        os.makedirs(post_folder, exist_ok=True)

        filename = file_url.split('f=')[-1] if 'f=' in file_url else file_url.split('/')[-1].split('?')[0]
        full_path = os.path.join(post_folder, filename.replace('/', '_'))
        url_hash = hashlib.md5(file_url.encode()).hexdigest()

        file_hashes_keys = list(self.file_hashes.keys())
        for hash_key in file_hashes_keys:
            if hash_key == url_hash:
                existing_path = self.file_hashes[hash_key]["file_path"]
                if os.path.exists(existing_path):
                    file_hash = hashlib.md5(open(existing_path, 'rb').read()).hexdigest()
                    stored_hash = self.file_hashes[hash_key]["file_hash"]
                    if file_hash == stored_hash:
                        self.log.emit(f"[INFO] File {filename} already downloaded at {existing_path}, skipping.", "INFO")
                        self.file_progress.emit(file_index, 100)
                        self.file_completed.emit(file_index, file_url)
                        self.completed_files.add(file_url)
                        self.check_post_completion(file_url)
                        return

        self.log.emit(f"[INFO] Starting download of file {file_index + 1}/{total_files}: {file_url} to {post_folder}", "INFO")
        try:
            response = requests.get(file_url, headers=HEADERS, stream=True)
            response.raise_for_status()
            file_size = int(response.headers.get('content-length', 0)) or 1
            downloaded_size = 0
            
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.is_running:
                        self.log.emit(f"[WARNING] Download interrupted for {file_url}", "WARNING")
                        os.remove(full_path) if os.path.exists(full_path) else None
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = int((downloaded_size / file_size) * 100)
                        self.file_progress.emit(file_index, progress)
                        if progress == 100:
                            self.file_completed.emit(file_index, file_url)

            file_hash = hashlib.md5(open(full_path, 'rb').read()).hexdigest()
            self.file_hashes[url_hash] = {
                "file_path": full_path,
                "file_hash": file_hash,
                "url": file_url
            }
            self.save_hashes()
            self.log.emit(f"[INFO] Successfully downloaded: {full_path}", "INFO")
            self.completed_files.add(file_url)
            self.check_post_completion(file_url)
        except Exception as e:
            self.log.emit(f"[ERROR] Error downloading {file_url}: {e}", "ERROR")
            self.file_progress.emit(file_index, 0)

    def check_post_completion(self, file_url):
        post_id = self.files_to_posts_map.get(file_url)
        if post_id in self.post_files_map:
            post_files = self.post_files_map[post_id]
            if all(f in self.completed_files for f in post_files):
                self.post_completed.emit(post_id)
                self.log.emit(f"[INFO] All files for post {post_id} have been downloaded", "INFO")

    def run(self):
        self.log.emit(f"[INFO] DownloadThread started with URL: {self.url}", "INFO")
        service_folder = os.path.join(self.download_folder, self.service)
        os.makedirs(service_folder, exist_ok=True)
        self.log.emit(f"[INFO] Created directory: {service_folder}", "INFO")

        total_files = len(self.selected_files)
        self.log.emit(f"[INFO] Total selected files to download for this post: {total_files}", "INFO")

        if total_files > 0:
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                futures = {executor.submit(self.download_file, file_url, self.download_folder, i, total_files): i
                           for i, file_url in enumerate(self.selected_files)}
                for future in as_completed(futures):
                    if not self.is_running:
                        break
                    try:
                        future.result()
                    except Exception as e:
                        self.log.emit(f"[ERROR] Error in download: {e}", "ERROR")
        else:
            self.log.emit("[WARNING] No files selected for download for this post.", "WARNING")

        self.log.emit(f"[INFO] DownloadThread for post {self.post_id} finished", "INFO")
        self.finished.emit()

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
        self.cache_dir = self.parent.cache_folder
        self.other_files_dir = self.parent.other_files_folder
        self.current_file_index = -1
        self.checked_urls = {}
        self.active_threads = []
        self.current_post_url = None
        self.all_files_map = {}
        self.all_detected_posts = []
        self.post_url_map = {}
        self.total_files_to_download = 0
        self.completed_files = set()
        self.completed_posts = set()
        self.total_posts_to_download = 0
        self.detected_files_during_check_all = []
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.other_files_dir, exist_ok=True)
        self.setup_ui()
        self.parent.settings_tab.settings_applied.connect(self.refresh_ui)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        post_url_layout = QHBoxLayout()
        self.post_url_input = QLineEdit()
        self.post_url_input.setPlaceholderText("Enter post URL (e.g., https://kemono.su/patreon/user/12345678/post/123456789)")
        self.post_url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        post_url_layout.addWidget(self.post_url_input)
        self.post_add_to_queue_btn = QPushButton(qta.icon('fa5s.plus', color='white'), "Add to Queue")
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

        post_progress_layout = QVBoxLayout()
        self.post_file_progress_label = QLabel("File Progress 0%")
        post_progress_layout.addWidget(self.post_file_progress_label)
        self.post_file_progress = QProgressBar()
        self.post_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
        self.post_file_progress.setRange(0, 100)
        post_progress_layout.addWidget(self.post_file_progress)
        self.post_overall_progress_label = QLabel("Overall Progress (0/0 files, 0/0 posts)")
        post_progress_layout.addWidget(self.post_overall_progress_label)
        self.post_overall_progress = QProgressBar()
        self.post_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
        self.post_overall_progress.setRange(0, 100)
        post_progress_layout.addWidget(self.post_overall_progress)
        left_layout.addLayout(post_progress_layout)

        self.post_console = QTextEdit()
        self.post_console.setReadOnly(True)
        self.post_console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        left_layout.addWidget(self.post_console)

        post_btn_layout = QHBoxLayout()
        self.post_download_btn = QPushButton(qta.icon('fa5s.download', color='white'), "Download")
        self.post_download_btn.clicked.connect(self.start_post_download)
        self.post_download_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        post_btn_layout.addWidget(self.post_download_btn)
        self.post_cancel_btn = QPushButton(qta.icon('fa5s.times', color='white'), "Cancel")
        self.post_cancel_btn.clicked.connect(self.cancel_post_download)
        self.post_cancel_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        self.post_cancel_btn.setEnabled(False)
        post_btn_layout.addWidget(self.post_cancel_btn)
        left_layout.addLayout(post_btn_layout)

        left_layout.addStretch()
        layout.addWidget(left_widget, stretch=2)

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

        checkbox_layout = QHBoxLayout()
        self.post_check_all = QCheckBox("Check ALL")
        self.post_check_all.setChecked(True)
        self.post_check_all.setStyleSheet("color: white;")
        self.post_check_all.stateChanged.connect(self.toggle_check_all)
        checkbox_layout.addWidget(self.post_check_all)

        self.download_all_links = QCheckBox("Download All Links")
        self.download_all_links.setStyleSheet("color: white;")
        self.download_all_links.stateChanged.connect(self.toggle_download_all_links)
        checkbox_layout.addWidget(self.download_all_links)
        file_list_layout.addLayout(checkbox_layout)

        self.post_filter_group = QGroupBox("Filter by Type")
        self.post_filter_group.setStyleSheet("QGroupBox { color: white; }")
        filter_layout = QGridLayout()
        self.post_filter_checks = {
            '.jpg': QCheckBox("JPG"), '.jpeg': QCheckBox("JPEG"), '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"), '.mp4': QCheckBox("MP4"), '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"), '.7z': QCheckBox("7Z"),
            '.mp3': QCheckBox("MP3"), '.wav': QCheckBox("WAV"), '.rar': QCheckBox("RAR"),
            '.mov': QCheckBox("MOV"), '.docx': QCheckBox("DOCX"), '.psd': QCheckBox("PSD")
        }
        for i, (ext, check) in enumerate(self.post_filter_checks.items()):
            check.setChecked(True)
            check.stateChanged.connect(self.filter_items)
            filter_layout.addWidget(check, i // 4, i % 4)
        self.post_filter_group.setLayout(filter_layout)
        file_list_layout.addWidget(self.post_filter_group)
        self.post_file_list = QListWidget()
        self.post_file_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.post_file_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.post_file_list.itemClicked.connect(self.handle_item_click)
        self.post_file_list.currentItemChanged.connect(self.update_current_preview_url)
        file_list_layout.addWidget(self.post_file_list)
        bottom_layout = QHBoxLayout()
        self.post_file_count_label = QLabel("Files: 0")
        self.post_file_count_label.setStyleSheet("color: white;")
        bottom_layout.addWidget(self.post_file_count_label)
        self.post_view_button = QPushButton(qta.icon('fa5s.eye', color='white'), "")
        self.post_view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
        self.post_view_button.clicked.connect(self.view_current_item)
        self.post_view_button.setEnabled(False)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.post_view_button)
        file_list_layout.addLayout(bottom_layout)
        file_list_group.setLayout(file_list_layout)
        right_layout.addWidget(file_list_group)

        self.background_task_label = QLabel("Idle")
        self.background_task_label.setStyleSheet("color: white;")
        right_layout.addWidget(self.background_task_label)

        self.background_task_progress = QProgressBar()
        self.background_task_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        right_layout.addWidget(self.background_task_progress)

        right_layout.addStretch()
        layout.addWidget(right_widget, stretch=1)

        self.post_download_btn.enterEvent = lambda e: self.parent.animate_button(self.post_download_btn, True)
        self.post_download_btn.leaveEvent = lambda e: self.parent.animate_button(self.post_download_btn, False)
        self.post_cancel_btn.enterEvent = lambda e: self.parent.animate_button(self.post_cancel_btn, True)
        self.post_cancel_btn.leaveEvent = lambda e: self.parent.animate_button(self.post_cancel_btn, False)

    def update_progress_bar_style(self):
        separator_style = "QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }"
        self.post_file_progress.setStyleSheet(separator_style)
        self.post_overall_progress.setStyleSheet(separator_style)
        self.background_task_progress.setStyleSheet(separator_style)

    def refresh_ui(self):
        self.update_progress_bar_style()
        if not self.downloading:
            self.post_file_progress.setValue(0)
            self.post_file_progress_label.setText("File Progress 0%")
            self.post_overall_progress.setValue(0)
            self.post_overall_progress_label.setText("Overall Progress (0/0 files, 0/0 posts)")
            self.current_file_index = -1
            self.completed_posts.clear()
            self.completed_files.clear()
            self.total_files_to_download = 0
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")

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
            if self.download_all_links.isChecked():
                self.check_all_posts()
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
                        self.checked_urls = {}
                        self.all_files_map = {}
                        self.all_detected_posts = []
                        self.post_url_map = {}
                        self.current_post_url = None
                        self.previous_selected_widget = None
                        self.update_checked_files()
                        self.filter_items()
                    elif self.download_all_links.isChecked():
                        self.check_all_posts()
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
            view_button = QPushButton(qta.icon('fa5s.eye', color='white'), "")
            view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
            view_button.clicked.connect(self.create_view_handler(url, checked))
            layout.addWidget(view_button)
            label = QLabel(url)
            label.setStyleSheet("color: white;")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(label, stretch=1)
            remove_button = QPushButton(qta.icon('fa5s.times', color='white'), "")
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
        self.append_log_to_console(f"[INFO] Viewing post: {url}", "INFO")
        
        self.current_post_url = url
        self.checked_urls.clear()
        self.files_to_download = []
        
        self.post_file_list.clear()
        self.previous_selected_widget = None
        
        if url in self.all_files_map:
            self.all_detected_posts = [(title, post_id) for title, post_id in self.all_files_map.get(url, [])]
            self.post_url_map = {title: post_id for title, post_id in self.all_detected_posts}
            self.append_log_to_console(f"[DEBUG] Total detected posts: {len(self.all_detected_posts)}", "INFO")
            self.display_files_for_post(url)
            for i, (queue_url, _) in enumerate(self.post_queue):
                if queue_url == url:
                    self.post_queue[i] = (url, True)
                    self.update_post_queue_list()
                    break
            self.update_checked_files()
            self.filter_items()
            self.append_log_to_console(f"[DEBUG] Displayed files for post {url}", "INFO")
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")
        else:
            self.background_task_label.setText("Detecting post from link...")
            self.background_task_progress.setRange(0, 0)
            self.post_detection_thread = PostDetectionThread(url)
            self.post_detection_thread.finished.connect(self.on_post_detection_finished)
            self.post_detection_thread.log.connect(self.append_log_to_console)
            self.post_detection_thread.error.connect(self.on_post_detection_error)
            self.post_detection_thread.finished.connect(lambda posts: self.cleanup_thread(self.post_detection_thread, []))
            self.post_detection_thread.error.connect(lambda err: self.cleanup_thread(self.post_detection_thread, []))
            self.active_threads.append(self.post_detection_thread)
            self.post_detection_thread.start()

    def on_post_detection_finished(self, detected_posts):
        self.all_files_map[self.current_post_url] = detected_posts
        self.all_detected_posts = detected_posts
        self.post_url_map = {title: post_id for title, post_id in self.all_detected_posts}
        self.append_log_to_console(f"[DEBUG] Total detected posts: {len(self.all_detected_posts)}", "INFO")
        self.display_files_for_post(self.current_post_url)
        for i, (queue_url, _) in enumerate(self.post_queue):
            if queue_url == self.current_post_url:
                self.post_queue[i] = (self.current_post_url, True)
                self.update_post_queue_list()
                break
        self.update_checked_files()
        self.filter_items()
        self.append_log_to_console(f"[DEBUG] Displayed files for post {self.current_post_url}", "INFO")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def on_post_detection_error(self, error_message):
        self.append_log_to_console(f"[ERROR] {error_message}", "ERROR")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def display_files_for_post(self, url):
        parts = url.split('/')
        service, creator_id, post_id = parts[-5], parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        try:
            response = requests.get(api_url, headers=HEADERS)
            if response.status_code != 200:
                self.append_log_to_console(f"[ERROR] Failed to fetch {api_url} - Status code: {response.status_code}", "ERROR")
                return
            post_data = response.json()
            post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
            allowed_extensions = [ext.lower() for ext, check in self.post_filter_checks.items() if check.isChecked()]
            self.all_detected_files = self.detect_files(post, allowed_extensions)
            self.file_url_map = {file_name: file_url for file_name, file_url in self.all_detected_files}
            self.checked_urls.clear()
            for file_name, file_url in self.all_detected_files:
                self.checked_urls[file_url] = True
                self.add_list_item(file_name, file_url)
            self.update_checked_files()
        except Exception as e:
            self.append_log_to_console(f"[ERROR] Error fetching files for post {url}: {str(e)}", "ERROR")

    def detect_files(self, post, allowed_extensions):
        detected_files = []
        if 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = os.path.splitext(file_path)[1].lower() or os.path.splitext(file_name)[1].lower()
            file_url = urljoin("https://kemono.su", file_path)
            if 'f=' not in file_url and file_name:
                file_url += f"?f={file_name}"
            if '.jpg' in allowed_extensions and file_ext in ['.jpg', '.jpeg']:
                detected_files.append((file_name, file_url))
            elif file_ext in allowed_extensions:
                detected_files.append((file_name, file_url))

        if 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = os.path.splitext(attachment_path)[1].lower() or os.path.splitext(attachment_name)[1].lower()
                    attachment_url = urljoin("https://kemono.su", attachment_path)
                    if 'f=' not in attachment_url and attachment_name:
                        attachment_url += f"?f={attachment_name}"
                    if '.jpg' in allowed_extensions and attachment_ext in ['.jpg', '.jpeg']:
                        detected_files.append((attachment_name, attachment_url))
                    elif attachment_ext in allowed_extensions:
                        detected_files.append((attachment_name, attachment_url))

        if 'content' in post and post['content']:
            soup = BeautifulSoup(post['content'], 'html.parser')
            for img in soup.select('img[src]'):
                img_url = urljoin("https://kemono.su", img['src'])
                img_ext = os.path.splitext(img_url)[1].lower()
                img_name = os.path.basename(img_url)
                if '.jpg' in allowed_extensions and img_ext in ['.jpg', '.jpeg']:
                    detected_files.append((img_name, img_url))
                elif img_ext in allowed_extensions:
                    detected_files.append((img_name, img_url))

        return list(dict.fromkeys(detected_files))

    def check_all_posts(self):
        self.all_files_map.clear()
        self.checked_urls.clear()
        self.detected_files_during_check_all = []
        self.files_to_download = []
        self.file_url_map.clear()
        self.post_file_count_label.setText(f"Files: 0 (Detecting...)")
        self.append_log_to_console("[INFO] Starting detection of all posts in queue", "INFO")

        for url, _ in self.post_queue:
            if url not in self.all_files_map:
                self.background_task_label.setText("Detecting posts from link...")
                self.background_task_progress.setRange(0, 0)
                thread = PostDetectionThread(url)
                thread.finished.connect(lambda posts, u=url: self.on_check_all_posts_detected(u, posts))
                thread.file_detected.connect(self.on_files_detected_during_check_all)
                thread.log.connect(self.append_log_to_console)
                thread.error.connect(self.on_post_detection_error)
                thread.finished.connect(lambda posts: self.cleanup_thread(thread, []))
                thread.error.connect(lambda err: self.cleanup_thread(thread, []))
                self.active_threads.append(thread)
                thread.start()

    def on_files_detected_during_check_all(self, detected_files):
        for file_name, file_url in detected_files:
            self.detected_files_during_check_all.append(file_url)
            self.checked_urls[file_url] = True
            self.file_url_map[file_name] = file_url
        self.files_to_download = list(dict.fromkeys(self.detected_files_during_check_all))
        self.post_file_count_label.setText(f"Files: {len(self.files_to_download)} (Detecting...)")
        self.append_log_to_console(f"[DEBUG] Files detected so far: {len(self.files_to_download)}", "INFO")

    def on_check_all_posts_detected(self, url, posts):
        self.all_files_map[url] = posts
        total_posts = sum(len(posts) for posts in self.all_files_map.values())
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        if not any(thread.isRunning() for thread in self.active_threads if isinstance(thread, PostDetectionThread)):
            self.files_to_download = list(dict.fromkeys(self.detected_files_during_check_all))
            self.post_file_count_label.setText(f"Files: {len(self.files_to_download)}")
            self.append_log_to_console(f"[INFO] Finished checking all posts. Total posts: {total_posts}, Total files: {len(self.files_to_download)}", "INFO")
            self.detected_files_during_check_all = []
            self.update_checked_files()

    def on_post_detection_error(self, error_message):
        self.append_log_to_console(f"[ERROR] {error_message}", "ERROR")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def start_post_download(self):
        if not self.post_queue:
            self.append_log_to_console("[WARNING] No posts in queue to download.", "WARNING")
            return

        self.update_checked_files()
        checked_files = [file_url for file_url, is_checked in self.checked_urls.items() if is_checked]
        self.append_log_to_console(f"[DEBUG] Checked files for download: {checked_files}", "INFO")
        if not checked_files:
            self.append_log_to_console("[WARNING] No files selected for download.", "WARNING")
            return

        self.downloading = True
        self.parent.tabs.setTabEnabled(1, False)
        self.parent.status_label.setText("Preparing files...")
        self.post_download_btn.setEnabled(False)
        self.post_cancel_btn.setEnabled(True)
        self.post_overall_progress.setValue(0)
        self.completed_posts.clear()
        self.completed_files.clear()
        self.total_files_to_download = 0
        self.post_overall_progress_label.setText(f"Overall Progress (0/0 files, 0/0 posts)")
        self.current_file_index = -1
        self.post_file_progress.setValue(0)
        self.post_file_progress_label.setText("File Progress 0%")
        self.update_progress_bar_style()

        self.background_task_label.setText("Preparing files to download...")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)

        if self.download_all_links.isChecked():
            urls = [url for url, _ in self.post_queue]
            self.total_posts_to_download = len(urls)
            self.total_files_to_download = len(checked_files)
            self.post_overall_progress_label.setText(f"Overall Progress (0/{self.total_files_to_download} files, 0/{self.total_posts_to_download} posts)")
            self.append_log_to_console(f"[INFO] Preparing files for all posts in queue: {urls}", "INFO")
        else:
            if not self.current_post_url:
                self.append_log_to_console("[WARNING] No post currently viewed to download.", "WARNING")
                self.post_download_finished()
                return
            urls = [self.current_post_url]
            self.total_posts_to_download = 1
            self.total_files_to_download = len(checked_files)
            self.post_overall_progress_label.setText(f"Overall Progress (0/{self.total_files_to_download} files, 0/{self.total_posts_to_download} posts)")
            self.append_log_to_console(f"[INFO] Preparing files for currently viewed post: {self.current_post_url}", "INFO")

        self.prepare_files_for_download(urls)

    def prepare_files_for_download(self, urls):
        self.append_log_to_console(f"[DEBUG] Preparing files for URLs: {urls}", "INFO")
        if not urls:
            self.append_log_to_console("[INFO] No more URLs to process. Finishing download.", "INFO")
            self.post_download_finished()
            return

        if self.download_all_links.isChecked():
            post_ids = []
            for url in urls:
                post_ids.extend([post_id for _, post_id in self.all_files_map.get(url, [])])
        else:
            post_ids = [post_id for _, post_id in self.all_files_map.get(urls[0], [])]

        if not post_ids:
            self.append_log_to_console(f"[WARNING] No posts available for download in URLs: {urls}. Skipping to next.", "WARNING")
            self.process_next_post(urls[1:] if len(urls) > 1 else [])
            return

        self.file_preparation_thread = FilePreparationThread(
            post_ids,
            self.all_files_map,
            self.post_filter_checks,
            self.file_url_map,
            max_concurrent=5
        )
        self.file_preparation_thread.progress.connect(self.update_background_progress)
        self.file_preparation_thread.finished.connect(lambda files, files_map: self.on_file_preparation_finished(urls, files, files_map))
        self.file_preparation_thread.log.connect(self.append_log_to_console)
        self.file_preparation_thread.error.connect(self.on_file_preparation_error)
        self.file_preparation_thread.finished.connect(lambda files, files_map: self.cleanup_thread(self.file_preparation_thread, []))
        self.file_preparation_thread.error.connect(lambda err: self.cleanup_thread(self.file_preparation_thread, []))
        self.active_threads.append(self.file_preparation_thread)
        self.file_preparation_thread.start()

    def update_background_progress(self, value):
        self.background_task_progress.setValue(value)

    def on_file_preparation_finished(self, urls, files_to_download, files_to_posts_map):
        self.append_log_to_console(f"[DEBUG] Files prepared for URLs: {urls}, Total files: {len(files_to_download)}", "INFO")
        for file_url in files_to_download:
            if file_url not in self.checked_urls:
                self.checked_urls[file_url] = True
        self.append_log_to_console(f"[DEBUG] Updated checked_urls after preparation: {self.checked_urls}", "INFO")

        active_filters = [ext.lower() for ext, check in self.post_filter_checks.items() if check.isChecked()]
        checked_files = []
        for file_url in files_to_download:
            if not self.checked_urls.get(file_url, False):
                continue
            file_name = file_url.split('f=')[-1] if 'f=' in file_url else file_url.split('/')[-1]
            file_ext = os.path.splitext(file_name)[1].lower()
            if not active_filters or file_ext in active_filters or (file_ext == '.jpeg' and '.jpg' in active_filters):
                checked_files.append(file_url)

        self.append_log_to_console(f"[DEBUG] Checked files after filtering: {len(checked_files)}", "INFO")
        self.append_log_to_console(f"[DEBUG] Checked files list: {checked_files}", "INFO")

        if not checked_files:
            self.append_log_to_console(f"[WARNING] No files to download for URLs: {urls}. Proceeding to next post.", "WARNING")
            self.process_next_post(urls[1:] if len(urls) > 1 else [])
            return

        url = urls[0]
        remaining_urls = urls[1:] if len(urls) > 1 else []
        self.append_log_to_console(f"[INFO] Processing post: {url}, Remaining URLs: {remaining_urls}", "INFO")
        parts = url.split('/')
        post_id = parts[-1]

        max_concurrent = self.parent.settings_tab.get_simultaneous_downloads()
        self.thread = DownloadThread(url, self.parent.download_folder, checked_files, files_to_posts_map, 
                                    self.post_console, self.other_files_dir, post_id, max_concurrent)
        self.active_threads.append(self.thread)
        self.thread.file_progress.connect(self.update_file_progress)
        self.thread.file_completed.connect(self.update_file_completion)
        self.thread.post_completed.connect(self.update_post_completion)
        self.thread.log.connect(self.append_log_to_console)
        self.thread.finished.connect(lambda: self.cleanup_thread(self.thread, remaining_urls))
        self.thread.start()

    def on_file_preparation_error(self, error_message):
        self.append_log_to_console(f"[ERROR] {error_message}", "ERROR")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        self.post_download_finished()

    def process_next_post(self, remaining_urls):
        self.append_log_to_console(f"[INFO] Processing next post. Remaining URLs: {remaining_urls}", "INFO")
        if not remaining_urls:
            self.append_log_to_console("[INFO] No more posts to download. Finishing.", "INFO")
            self.post_download_finished()
            return
        self.prepare_files_for_download(remaining_urls)

    def cleanup_thread(self, thread, remaining_urls):
        self.append_log_to_console(f"[INFO] Cleaning up thread for post. Remaining URLs: {remaining_urls}", "INFO")
        if thread in self.active_threads:
            self.active_threads.remove(thread)
            self.append_log_to_console(f"[DEBUG] Removed thread from active_threads. Active threads remaining: {len(self.active_threads)}", "INFO")
        else:
            self.append_log_to_console(f"[WARNING] Thread not found in active_threads.", "WARNING")

        active_download_threads = [t for t in self.active_threads if isinstance(t, DownloadThread)]
        self.append_log_to_console(f"[DEBUG] Active DownloadThreads remaining: {len(active_download_threads)}", "INFO")

        if not active_download_threads:
            self.append_log_to_console(f"[INFO] No active DownloadThreads remaining. Proceeding to next post.", "INFO")
            self.process_next_post(remaining_urls)
        else:
            self.append_log_to_console(f"[DEBUG] Active DownloadThreads still running: {len(active_download_threads)}. Waiting before proceeding.", "INFO")

    def cancel_post_download(self):
        if self.active_threads:
            for thread in self.active_threads[:]:
                if isinstance(thread, (DownloadThread, PostDetectionThread, FilePreparationThread)):
                    thread.stop()
            self.append_log_to_console("[WARNING] Cancelling all downloads...", "WARNING")
            time.sleep(1)
            for thread in self.active_threads[:]:
                if thread.isRunning():
                    thread.terminate()
                    self.active_threads.remove(thread)
                    self.append_log_to_console(f"[INFO] Terminated thread: {thread.__class__.__name__}", "INFO")
            self.post_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #D4A017; }")
            self.post_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #D4A017; }")
            self.post_file_progress_label.setText("Downloads Terminated")
            self.post_overall_progress_label.setText("Downloads Terminated")
            self.active_threads.clear()
            self.downloading = False
            self.parent.tabs.setTabEnabled(1, True)
            self.parent.status_label.setText("Idle")
            self.post_download_btn.setEnabled(True)
            self.post_cancel_btn.setEnabled(False)
            self.total_files_to_download = 0
            self.completed_files.clear()
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")

    def update_file_progress(self, file_index, progress):
        if self.current_file_index == file_index or self.current_file_index == -1:
            self.current_file_index = file_index
            self.post_file_progress.setValue(progress)
            self.post_file_progress_label.setText(f"File Progress {progress}%")

    def update_file_completion(self, file_index, file_url):
        if file_url not in self.completed_files:
            self.completed_files.add(file_url)
            self.append_log_to_console(f"[DEBUG] File completed: {file_url}, Total completed: {len(self.completed_files)}/{self.total_files_to_download}", "INFO")
            self.update_overall_progress()
        if self.current_file_index == file_index:
            self.current_file_index = -1
            self.post_file_progress.setValue(0)
            self.post_file_progress_label.setText("File Progress 0%")

    def update_overall_progress(self):
        if self.total_files_to_download > 0:
            completed_count = len(self.completed_files)
            percentage = int((completed_count / self.total_files_to_download) * 100)
            self.post_overall_progress.setValue(percentage)
            self.append_log_to_console(
                f"[DEBUG] Overall progress updated: {completed_count}/{self.total_files_to_download} files, {percentage}%", "INFO"
            )
            self.post_overall_progress_label.setText(
                f"Overall Progress ({completed_count}/{self.total_files_to_download} files, {len(self.completed_posts)}/{self.total_posts_to_download} posts)"
            )
        else:
            self.post_overall_progress.setValue(0)
            self.post_overall_progress_label.setText(
                f"Overall Progress (0/0 files, {len(self.completed_posts)}/{self.total_posts_to_download} posts)"
            )

    def update_post_completion(self, post_id):
        self.completed_posts.add(post_id)
        self.append_log_to_console(f"[INFO] Post {post_id} fully downloaded.", "INFO")
        self.update_overall_progress()

    def post_download_finished(self):
        self.downloading = False
        self.parent.tabs.setTabEnabled(1, True)
        self.parent.status_label.setText("Idle")
        self.post_download_btn.setEnabled(True)
        self.post_cancel_btn.setEnabled(False)
        self.append_log_to_console("[INFO] Download process ended", "INFO")
        
        if self.total_files_to_download > 0 and len(self.completed_files) == self.total_files_to_download:
            self.post_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: green; }")
            self.post_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: green; }")
            self.post_overall_progress_label.setText("Downloads Complete")
        
        self.total_files_to_download = 0
        self.completed_files.clear()
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def toggle_check_all(self, state):
        is_checked = state == 2
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        
        if self.current_post_url and self.current_post_url in self.all_files_map:
            current_post_id = self.all_files_map[self.current_post_url][0][1]
            parts = self.current_post_url.split('/')
            service, creator_id = parts[-5], parts[-3]
            api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{current_post_id}"
            try:
                response = requests.get(api_url, headers=HEADERS)
                if response.status_code == 200:
                    post_data = response.json()
                    post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
                    allowed_extensions = [ext.lower() for ext, check in self.post_filter_checks.items() if check.isChecked()]
                    current_files = self.detect_files(post, allowed_extensions)
                    current_file_urls = [file_url for _, file_url in current_files]
                    
                    for file_url in self.checked_urls:
                        if file_url in current_file_urls:
                            self.checked_urls[file_url] = (new_state == Qt.CheckState.Checked)
            
            except Exception as e:
                self.append_log_to_console(f"[ERROR] Error fetching post data for Check ALL: {str(e)}", "ERROR")

        for i in range(self.post_file_list.count()):
            item = self.post_file_list.item(i)
            if not item.isHidden():
                widget = self.post_file_list.itemWidget(item)
                file_url = item.data(Qt.UserRole)
                if widget and file_url in current_file_urls:
                    widget.check_box.blockSignals(True)
                    widget.check_box.setCheckState(new_state)
                    widget.check_box.blockSignals(False)
        
        self.update_checked_files()
        self.append_log_to_console(f"[DEBUG] Check ALL state updated to {is_checked} for current post", "INFO")

    def toggle_download_all_links(self, state):
        is_checked = state == 2
        if is_checked:
            self.post_check_all.setEnabled(False)
            for i in range(self.post_file_list.count()):
                item = self.post_file_list.item(i)
                widget = self.post_file_list.itemWidget(item)
                if widget:
                    widget.check_box.setEnabled(False)
            self.check_all_posts()
        else:
            self.post_check_all.setEnabled(True)
            for i in range(self.post_file_list.count()):
                item = self.post_file_list.item(i)
                widget = self.post_file_list.itemWidget(item)
                if widget:
                    widget.check_box.setEnabled(True)
            self.update_checked_files()
            self.filter_items()
            self.append_log_to_console("[INFO] Download All Links disabled. Reverted to current post.", "INFO")

    def update_checked_files(self):
        self.files_to_download = [file_url for file_url, is_checked in self.checked_urls.items() if is_checked]
        self.post_file_count_label.setText(f"Files: {len(self.files_to_download)}")
        self.append_log_to_console(
            f"[DEBUG] Updated checked files count: {len(self.files_to_download)}, checked_urls: {len(self.checked_urls)}",
            "INFO"
        )

    def filter_items(self):
        search_text = self.post_search_input.text().lower()
        active_filters = [ext.lower() for ext, check in self.post_filter_checks.items() if check.isChecked()]
        
        current_states = {item.data(Qt.UserRole): self.checked_urls.get(item.data(Qt.UserRole), True)
                         for i in range(self.post_file_list.count())
                         for item in [self.post_file_list.item(i)] if not item.isHidden()}
        
        self.post_file_list.clear()
        self.previous_selected_widget = None
        for file_name, file_url in self.all_detected_files:
            file_ext = os.path.splitext(file_name)[1].lower()
            if (not search_text or search_text in file_name.lower()) and (not active_filters or file_ext in active_filters):
                self.add_list_item(file_name, file_url)

        for i in range(self.post_file_list.count()):
            item = self.post_file_list.item(i)
            if not item.isHidden():
                widget = self.post_file_list.itemWidget(item)
                file_url = item.data(Qt.UserRole)
                if widget and file_url in current_states:
                    widget.check_box.blockSignals(True)
                    widget.check_box.setChecked(current_states[file_url])
                    widget.check_box.blockSignals(False)
                    self.checked_urls[file_url] = current_states[file_url]
                if self.download_all_links.isChecked():
                    widget.check_box.setEnabled(False)

        self.update_check_all_state()

    def add_list_item(self, text, url):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, url)
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        check_box = QCheckBox()
        check_box.setStyleSheet("color: white;")
        initial_state = self.checked_urls.get(url, True)
        check_box.setChecked(initial_state)
        check_box.clicked.connect(lambda: self.toggle_checkbox_state(url))
        if self.download_all_links.isChecked():
            check_box.setEnabled(False)
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

    def toggle_checkbox_state(self, url):
        current_state = self.checked_urls.get(url, True)
        new_state = not current_state
        self.checked_urls[url] = new_state
        widget = self.get_widget_for_url(url)
        if widget:
            widget.check_box.blockSignals(True)
            widget.check_box.setChecked(new_state)
            widget.check_box.blockSignals(False)
        self.append_log_to_console(f"[DEBUG] Checkbox toggled for {url} to {new_state}, checked_urls count: {len(self.checked_urls)}", "INFO")
        self.update_checked_files()
        self.update_check_all_state()

    def get_widget_for_url(self, url):
        for i in range(self.post_file_list.count()):
            item = self.post_file_list.item(i)
            if item and item.data(Qt.UserRole) == url:
                return self.post_file_list.itemWidget(item)
        return None

    def update_check_all_state(self):
        all_visible_checked = all(
            self.post_file_list.itemWidget(self.post_file_list.item(i)).check_box.isChecked()
            for i in range(self.post_file_list.count()) if not self.post_file_list.item(i).isHidden()
        ) and self.post_file_list.count() > 0
        self.post_check_all.blockSignals(True)
        self.post_check_all.setChecked(all_visible_checked)
        self.post_check_all.blockSignals(False)
        self.append_log_to_console(f"[DEBUG] Check ALL state updated to {all_visible_checked}", "INFO")

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