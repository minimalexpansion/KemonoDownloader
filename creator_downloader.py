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

# Headers for API requests
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36", "Referer": "https://kemono.su/"}
API_BASE = "https://kemono.su/api/v1"

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
        self.preview_thread.finished.connect(self.preview_thread.deleteLater)
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

class PostDetectionThread(QThread):
    finished = pyqtSignal(list)
    log = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        if not self.is_running:
            return
        self.log.emit(f"[INFO] Checking creator with URL: {self.url}", "INFO")
        parts = self.url.split('/')
        if len(parts) < 5 or 'kemono.su' not in self.url or parts[-2] != 'user':
            self.error.emit("Invalid URL format. Expected: https://kemono.su/[service]/user/[creator_id]")
            return
        service, creator_id = parts[-3], parts[-1]
        base_api_url = f"{API_BASE}/{service}/user/{creator_id}"

        all_posts = []
        offset = 0
        page_size = 50
        max_attempts = 200

        attempt = 1
        while attempt <= max_attempts and self.is_running:
            api_url = f"{base_api_url}?o={offset}"
            self.log.emit(f"[DEBUG] Fetching page {attempt} (offset {offset}) from {api_url}", "INFO")
            
            try:
                response = requests.get(api_url, headers=HEADERS, timeout=10)
                if response.status_code != 200:
                    self.log.emit(f"[ERROR] Failed to fetch creator posts at offset {offset} - Status code: {response.status_code}", "ERROR")
                    break
                
                posts_data = response.json()
                if not isinstance(posts_data, list):
                    self.log.emit("[ERROR] Invalid posts data returned! Response: " + json.dumps(posts_data, indent=2), "ERROR")
                    break

                self.log.emit(f"[DEBUG] Fetched {len(posts_data)} posts at offset {offset}", "INFO")

                if not posts_data:
                    self.log.emit(f"[INFO] No more posts to fetch at offset {offset}. Stopping pagination.", "INFO")
                    break

                all_posts.extend(posts_data)
                offset += page_size
                attempt += 1
                time.sleep(0.5)

            except requests.RequestException as e:
                self.log.emit(f"[ERROR] Failed to fetch posts at offset {offset}: {str(e)}", "ERROR")
                break

        if self.is_running:
            detected_posts = []
            for post in all_posts:
                post_id = post.get('id')
                title = post.get('title', f"Post {post_id}")
                thumbnail_url = None
                if 'file' in post and post['file'] and 'path' in post['file']:
                    if post['file']['path'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        thumbnail_url = urljoin("https://kemono.su", post['file']['path'])
                if not thumbnail_url and 'attachments' in post:
                    for attachment in post['attachments']:
                        if isinstance(attachment, dict) and 'path' in attachment and attachment['path'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                            thumbnail_url = urljoin("https://kemono.su", attachment['path'])
                            break
                if not thumbnail_url and 'file' in post and post['file'] and 'path' in post['file']:
                    thumbnail_url = urljoin("https://kemono.su", post['file']['path'])
                detected_posts.append((title, (post_id, thumbnail_url)))

            self.log.emit(f"[INFO] Total posts fetched for creator {self.url}: {len(detected_posts)}", "INFO")
            self.finished.emit(detected_posts)

class PostPopulationThread(QThread):
    finished = pyqtSignal(dict, list)
    log = pyqtSignal(str, str)

    def __init__(self, detected_posts):
        super().__init__()
        self.detected_posts = detected_posts
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        if not self.is_running:
            return
        post_url_map = {post_title: (post_id, thumbnail_url) for post_title, (post_id, thumbnail_url) in self.detected_posts}
        self.log.emit(f"[DEBUG] Prepared {len(self.detected_posts)} posts for population", "INFO")
        self.finished.emit(post_url_map, self.detected_posts)

class FilterThread(QThread):
    finished = pyqtSignal(list)
    log = pyqtSignal(str, str)

    def __init__(self, all_detected_posts, checked_urls, search_text):
        super().__init__()
        self.all_detected_posts = all_detected_posts
        self.checked_urls = checked_urls.copy()
        self.search_text = search_text.lower()
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        if not self.is_running:
            return
        filtered_items = []
        for post_title, (post_id, thumbnail_url) in self.all_detected_posts:
            if not self.search_text or self.search_text in post_title.lower():
                is_checked = self.checked_urls.get(post_id, False)
                filtered_items.append((post_title, post_id, thumbnail_url, is_checked))
                self.log.emit(f"[DEBUG] Filtered post: {post_title} (ID: {post_id})", "INFO")
        self.finished.emit(filtered_items)

class FilePreparationThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list, dict)
    log = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, post_ids, all_files_map, creator_ext_checks, creator_main_check, creator_attachments_check, creator_content_check, max_concurrent=20):
        super().__init__()
        self.post_ids = post_ids
        self.all_files_map = all_files_map
        self.creator_ext_checks = creator_ext_checks
        self.creator_main_check = creator_main_check
        self.creator_attachments_check = creator_attachments_check
        self.creator_content_check = creator_content_check
        self.max_concurrent = max_concurrent
        self.is_running = True

    def stop(self):
        self.is_running = False

    def detect_files(self, post, allowed_extensions):
        files_to_download = []
        self.log.emit(f"[DEBUG] Detecting files for post with allowed extensions: {allowed_extensions}", "INFO")
        
        def get_effective_extension(file_path, file_name):
            name_ext = os.path.splitext(file_name)[1].lower()
            path_ext = os.path.splitext(file_path)[1].lower()
            return name_ext if name_ext else path_ext

        # Main file detection
        if self.creator_main_check and 'file' in post and post['file'] and 'path' in post['file']:
            file_path = post['file']['path']
            file_name = post['file'].get('name', '')
            file_ext = get_effective_extension(file_path, file_name)
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

        # Attachments detection
        if self.creator_attachments_check and 'attachments' in post:
            for attachment in post['attachments']:
                if isinstance(attachment, dict) and 'path' in attachment:
                    attachment_path = attachment['path']
                    attachment_name = attachment.get('name', '')
                    attachment_ext = get_effective_extension(attachment_path, attachment_name)
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

        # Content images detection
        if self.creator_content_check and 'content' in post and post['content']:
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

    def fetch_and_detect_files(self, post_id, creator_url):
        parts = creator_url.split('/')
        service, creator_id = parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}/post/{post_id}"
        try:
            response = requests.get(api_url, headers=HEADERS)
            if response.status_code != 200:
                self.log.emit(f"[ERROR] Failed to fetch {api_url} - Status code: {response.status_code}", "ERROR")
                return None
            post_data = response.json()
            post = post_data if isinstance(post_data, dict) and 'post' not in post_data else post_data.get('post', {})
            self.log.emit(f"[DEBUG] Post data for {post_id}: {json.dumps(post, indent=2)}", "INFO")
            allowed_extensions = [ext.lower() for ext, checkbox in self.creator_ext_checks.items() if checkbox.isChecked()]
            detected_files = self.detect_files(post, allowed_extensions)
            files_to_download = [(file_name, file_url) for file_name, file_url in detected_files]
            return (post_id, files_to_download)
        except Exception as e:
            self.log.emit(f"[ERROR] Error fetching post {post_id}: {str(e)}", "ERROR")
            return None

    def run(self):
        if not self.is_running:
            return
        files_to_download = []
        files_to_posts_map = {}
        allowed_extensions = [ext.lower() for ext, checkbox in self.creator_ext_checks.items() if checkbox.isChecked()]
        self.log.emit(f"[DEBUG] Allowed extensions for download: {allowed_extensions}", "INFO")

        total_posts = len(self.post_ids)
        completed_posts = 0

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            future_to_post = {executor.submit(self.fetch_and_detect_files, post_id, creator_url): post_id
                             for creator_url, posts in self.all_files_map.items()
                             for _, (post_id, _) in posts
                             if post_id in self.post_ids}
            
            for future in as_completed(future_to_post):
                if not self.is_running:
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

class CreatorDownloadThread(QThread):
    file_progress = pyqtSignal(int, int) 
    file_completed = pyqtSignal(int, str)  
    post_completed = pyqtSignal(str)
    log = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, service, creator_id, download_folder, selected_posts, files_to_download, files_to_posts_map, console, other_files_dir, max_concurrent=10):
        super().__init__()
        self.service = service
        self.creator_id = creator_id
        self.download_folder = download_folder
        self.selected_posts = selected_posts
        self.files_to_download = files_to_download
        self.files_to_posts_map = files_to_posts_map
        self.console = console
        self.is_running = True
        self.other_files_dir = other_files_dir
        self.hash_file_path = os.path.join(self.other_files_dir, "file_hashes.json")
        self.file_hashes = self.load_hashes()
        self.max_concurrent = max_concurrent
        self.post_files_map = self.build_post_files_map()
        self.completed_files = set()

    def build_post_files_map(self):
        post_files_map = {post_id: [] for post_id in self.selected_posts}
        for file_url in self.files_to_download:
            post_id = self.files_to_posts_map.get(file_url)
            if post_id in post_files_map:
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

    def download_file(self, file_url, folder, file_index, total_files):
        if not self.is_running or file_url not in self.files_to_download:
            self.log.emit(f"[INFO] Skipping {file_url}", "INFO")
            return

        post_id = self.files_to_posts_map.get(file_url, self.creator_id)
        post_folder = os.path.join(folder, post_id)
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

    def run(self):
        if not self.is_running:
            return
        self.log.emit(f"[INFO] CreatorDownloadThread started for service: {self.service}, creator_id: {self.creator_id}", "INFO")
        total_posts = len(self.selected_posts)
        self.log.emit(f"[INFO] Total posts: {total_posts}", "INFO")

        creator_folder = os.path.join(self.download_folder, self.creator_id)
        os.makedirs(creator_folder, exist_ok=True)
        self.log.emit(f"[INFO] Created directory: {creator_folder}", "INFO")

        total_files = len(self.files_to_download)
        self.log.emit(f"[INFO] Total selected files to download: {total_files}", "INFO")

        if total_files > 0:
            for batch_start in range(0, total_files, self.max_concurrent):
                if not self.is_running:
                    break
                batch_files = self.files_to_download[batch_start:batch_start + self.max_concurrent]
                self.log.emit(f"[INFO] Starting batch of {len(batch_files)} files simultaneously", "INFO")
                
                with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                    futures = {executor.submit(self.download_file, file_url, creator_folder, i, total_files): i
                               for i, file_url in enumerate(batch_files, start=batch_start)}
                    
                    for future in as_completed(futures):
                        if not self.is_running:
                            break
                        try:
                            future.result()
                        except Exception as e:
                            self.log.emit(f"[ERROR] Error in download: {e}", "ERROR")
        else:
            self.log.emit("[WARNING] No files selected for download.", "WARNING")

        if self.is_running:
            self.finished.emit()

class ValidationThread(QThread):
    result = pyqtSignal(bool)
    log = pyqtSignal(str, str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        if not self.is_running:
            return
        parts = self.url.split('/')
        if len(parts) < 5 or 'kemono.su' not in self.url or parts[-2] != 'user':
            self.log.emit(f"[ERROR] Invalid URL format: {self.url}", "ERROR")
            self.result.emit(False)
            return
        service, creator_id = parts[-3], parts[-1]
        api_url = f"{API_BASE}/{service}/user/{creator_id}"
        try:
            response = requests.get(api_url, headers=HEADERS, timeout=5)
            valid = response.status_code == 200
            self.log.emit(f"[INFO] Validated URL {self.url}: {'Valid' if valid else 'Invalid'}", "INFO")
            self.result.emit(valid)
        except requests.RequestException as e:
            self.log.emit(f"[ERROR] Failed to validate {self.url}: {str(e)}", "ERROR")
            self.result.emit(False)

class CheckboxToggleThread(QThread):
    finished = pyqtSignal(dict, list)
    log = pyqtSignal(str, str)

    def __init__(self, all_detected_posts, checked_urls, check_all_state):
        super().__init__()
        self.all_detected_posts = all_detected_posts
        self.checked_urls = checked_urls.copy()
        self.check_all_state = check_all_state
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        if not self.is_running:
            return
        is_checked = self.check_all_state == 2
        new_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        for post_title, (post_id, _) in self.all_detected_posts:
            self.checked_urls[post_id] = (new_state == Qt.CheckState.Checked)
        posts_to_download = [post_id for post_id, checked in self.checked_urls.items() if checked]
        self.log.emit(f"[DEBUG] Checkbox toggle completed: Check ALL = {is_checked}, Updated posts: {len(posts_to_download)}", "INFO")
        self.finished.emit(self.checked_urls, posts_to_download)

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
        self.cache_dir = self.parent.cache_folder
        self.other_files_dir = self.parent.other_files_folder
        self.current_creator_url = None
        self.all_files_map = {}
        self.checked_urls = {}
        self.current_file_index = -1
        self.active_threads = []
        self.completed_posts = set()
        self.total_posts_to_download = 0
        self.total_files_to_download = 0
        self.completed_files = set()
        self.validation_thread = None
        self.post_detection_thread = None
        self.post_population_thread = None
        self.filter_thread = None
        self.file_preparation_thread = None
        self.checkbox_toggle_thread = None
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.other_files_dir, exist_ok=True)
        self.setup_ui()
        self.parent.settings_tab.settings_applied.connect(self.refresh_ui)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        creator_url_layout = QHBoxLayout()
        self.creator_url_input = QLineEdit()
        self.creator_url_input.setPlaceholderText("Enter creator URL (e.g., https://kemono.su/patreon/user/12345678)")
        self.creator_url_input.setStyleSheet("padding: 5px; border-radius: 5px;")
        creator_url_layout.addWidget(self.creator_url_input)
        
        self.creator_add_to_queue_btn = QPushButton(qta.icon('fa5s.plus', color='white'), "Add to Queue")
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
            '.jpg': QCheckBox("JPG/JPEG"),
            '.png': QCheckBox("PNG"),
            '.zip': QCheckBox("ZIP"),
            '.mp4': QCheckBox("MP4"),
            '.gif': QCheckBox("GIF"),
            '.pdf': QCheckBox("PDF"),
            '.7z': QCheckBox("7Z"),
            '.mp3': QCheckBox("MP3"),
            '.wav': QCheckBox("WAV"),
            '.rar': QCheckBox("RAR"),
            '.mov': QCheckBox("MOV"),
            '.docx': QCheckBox("DOCX"),
            '.psd': QCheckBox("PSD")
        }
        for i, (ext, check) in enumerate(self.creator_ext_checks.items()):
            check.setChecked(True)
            check.stateChanged.connect(self.filter_items)
            creator_ext_layout.addWidget(check, i // 5, i % 5)
        creator_ext_group.setLayout(creator_ext_layout)
        creator_options_layout.addWidget(creator_ext_group)
        creator_options_group.setLayout(creator_options_layout)
        left_layout.addWidget(creator_options_group)

        creator_progress_layout = QVBoxLayout()
        self.creator_file_progress_label = QLabel("File Progress 0%")
        creator_progress_layout.addWidget(self.creator_file_progress_label)
        self.creator_file_progress = QProgressBar()
        self.creator_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
        self.creator_file_progress.setRange(0, 100)
        creator_progress_layout.addWidget(self.creator_file_progress)
        self.creator_overall_progress_label = QLabel("Overall Progress (0/0 files, 0/0 posts)")
        creator_progress_layout.addWidget(self.creator_overall_progress_label)
        self.creator_overall_progress = QProgressBar()
        self.creator_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
        self.creator_overall_progress.setRange(0, 100)
        creator_progress_layout.addWidget(self.creator_overall_progress)
        left_layout.addLayout(creator_progress_layout)

        self.creator_console = QTextEdit()
        self.creator_console.setReadOnly(True)
        self.creator_console.setStyleSheet("background: #2A3B5A; border-radius: 5px; padding: 5px;")
        left_layout.addWidget(self.creator_console)

        creator_btn_layout = QHBoxLayout()
        self.creator_download_btn = QPushButton(qta.icon('fa5s.download', color='white'), "Download")
        self.creator_download_btn.clicked.connect(self.start_creator_download)
        self.creator_download_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        creator_btn_layout.addWidget(self.creator_download_btn)
        self.creator_cancel_btn = QPushButton(qta.icon('fa5s.times', color='white'), "Cancel")
        self.creator_cancel_btn.clicked.connect(self.cancel_creator_download)
        self.creator_cancel_btn.setStyleSheet("background: #4A5B7A; padding: 8px; border-radius: 5px;")
        self.creator_cancel_btn.setEnabled(False)
        creator_btn_layout.addWidget(self.creator_cancel_btn)
        left_layout.addLayout(creator_btn_layout)

        left_layout.addStretch()
        layout.addWidget(left_widget, stretch=2)

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

        checkbox_layout = QHBoxLayout()
        self.creator_check_all = QCheckBox("Check ALL")
        self.creator_check_all.setChecked(False)
        self.creator_check_all.setStyleSheet("color: white;")
        self.creator_check_all.stateChanged.connect(self.toggle_check_all)
        checkbox_layout.addWidget(self.creator_check_all)

        self.download_all_links = QCheckBox("Download All Links")
        self.download_all_links.setStyleSheet("color: white;")
        self.download_all_links.stateChanged.connect(self.toggle_download_all_links)
        checkbox_layout.addWidget(self.download_all_links)
        post_list_layout.addLayout(checkbox_layout)

        self.creator_post_list = QListWidget()
        self.creator_post_list.setStyleSheet("background: #2A3B5A; border-radius: 5px;")
        self.creator_post_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.creator_post_list.itemClicked.connect(self.handle_item_click)
        self.creator_post_list.currentItemChanged.connect(self.update_current_preview_url)
        post_list_layout.addWidget(self.creator_post_list)

        bottom_layout = QHBoxLayout()
        self.creator_post_count_label = QLabel("Posts: 0")
        self.creator_post_count_label.setStyleSheet("color: white;")
        bottom_layout.addWidget(self.creator_post_count_label)

        self.creator_view_button = QPushButton(qta.icon('fa5s.eye', color='white'), "")
        self.creator_view_button.setStyleSheet("background: #4A5B7A; padding: 2px; border-radius: 5px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;")
        self.creator_view_button.clicked.connect(self.view_current_item)
        self.creator_view_button.setEnabled(False)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.creator_view_button)

        post_list_layout.addLayout(bottom_layout)
        post_list_group.setLayout(post_list_layout)
        right_layout.addWidget(post_list_group)

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

        self.creator_download_btn.enterEvent = lambda e: self.parent.animate_button(self.creator_download_btn, True)
        self.creator_download_btn.leaveEvent = lambda e: self.parent.animate_button(self.creator_download_btn, False)
        self.creator_cancel_btn.enterEvent = lambda e: self.parent.animate_button(self.creator_cancel_btn, True)
        self.creator_cancel_btn.leaveEvent = lambda e: self.parent.animate_button(self.creator_cancel_btn, False)

    def update_progress_bar_style(self):
        separator_style = "QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }"
        self.creator_file_progress.setStyleSheet(separator_style)
        self.creator_overall_progress.setStyleSheet(separator_style)
        self.background_task_progress.setStyleSheet(separator_style)

    def refresh_ui(self):
        self.update_progress_bar_style()
        if not self.downloading:
            self.creator_file_progress.setValue(0)
            self.creator_file_progress_label.setText("File Progress 0%")
            self.creator_overall_progress.setValue(0)
            self.creator_overall_progress_label.setText("Overall Progress (0/0 files, 0/0 posts)")
            self.current_file_index = -1
            self.completed_posts.clear()
            self.completed_files.clear()
            self.total_files_to_download = 0
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")

    def add_creator_to_queue(self):
        url = self.creator_url_input.text().strip()
        if not url:
            self.append_log_to_console("[ERROR] No URL entered.", "ERROR")
            return
        if any(item[0] == url for item in self.creator_queue):
            self.append_log_to_console("[WARNING] URL already in queue.", "WARNING")
            return
        if hasattr(self, 'validation_thread') and self.validation_thread is not None and self.validation_thread.isRunning():
            self.append_log_to_console("[WARNING] Validation already in progress. Please wait.", "WARNING")
            return
        self.background_task_label.setText("Validating URL...")
        self.background_task_progress.setRange(0, 0)
        self.validation_thread = ValidationThread(url)
        self.validation_thread.result.connect(lambda valid: self.on_validation_finished(url, valid))
        self.validation_thread.log.connect(self.append_log_to_console)
        self.validation_thread.finished.connect(self.cleanup_validation_thread)
        self.active_threads.append(self.validation_thread)
        self.validation_thread.start()
    
    def cleanup_validation_thread(self):
        """Clean up the validation thread after it finishes."""
        if self.validation_thread in self.active_threads:
            self.active_threads.remove(self.validation_thread)
        self.validation_thread.deleteLater()
        self.validation_thread = None

    def on_validation_finished(self, url, valid):
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        if valid:
            self.creator_queue.append((url, False))
            self.update_creator_queue_list()
            self.creator_url_input.clear()
            self.append_log_to_console(f"[INFO] Added creator URL to queue: {url}", "INFO")
            if self.download_all_links.isChecked():
                self.check_all_creators()
        else:
            self.append_log_to_console(f"[ERROR] Invalid creator URL or failed to fetch: {url}", "ERROR")

    def create_view_handler(self, url, checked):
        def handler():
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
                        self.checked_urls = {}
                        self.all_files_map = {}
                        self.current_creator_url = None
                        self.previous_selected_widget = None
                        self.update_checked_posts()
                        self.filter_items()
                    elif self.download_all_links.isChecked():
                        self.check_all_creators()
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
            self.creator_queue_list.addItem(item)
            self.creator_queue_list.setItemWidget(item, widget)
            widget.view_button = view_button
            widget.label = label
            widget.remove_button = remove_button

    def check_creator_from_queue(self, url):
        if not isinstance(url, str):
            self.append_log_to_console(f"[ERROR] Invalid URL type: {type(url)}. Expected string.", "ERROR")
            return
        self.append_log_to_console(f"[INFO] Viewing creator: {url}", "INFO")
        
        self.current_creator_url = url
        self.checked_urls.clear()
        self.posts_to_download = []
        
        self.creator_post_list.clear()
        self.previous_selected_widget = None
        
        if url in self.all_files_map:
            self.all_detected_posts = self.all_files_map.get(url, [])
            self.post_url_map = {post_title: (post_id, thumbnail_url) for post_title, (post_id, thumbnail_url) in self.all_detected_posts}
            self.append_log_to_console(f"[DEBUG] Total detected posts: {len(self.all_detected_posts)}", "INFO")
            self.start_population_thread(self.all_detected_posts)
            for i, (queue_url, _) in enumerate(self.creator_queue):
                if queue_url == url:
                    self.creator_queue[i] = (url, True)
                    self.update_creator_queue_list()
                    break
        else:
            if self.post_detection_thread and self.post_detection_thread.isRunning():
                self.append_log_to_console("[WARNING] Post detection already in progress. Please wait.", "WARNING")
                return
            self.background_task_label.setText("Detecting posts from link...")
            self.background_task_progress.setRange(0, 0)
            self.post_detection_thread = PostDetectionThread(url)
            self.post_detection_thread.finished.connect(self.on_post_detection_finished)
            self.post_detection_thread.log.connect(self.append_log_to_console)
            self.post_detection_thread.error.connect(self.on_post_detection_error)
            self.post_detection_thread.finished.connect(self.post_detection_thread.deleteLater)
            self.active_threads.append(self.post_detection_thread)
            self.post_detection_thread.start()

    def on_post_detection_finished(self, detected_posts):
        self.all_files_map[self.current_creator_url] = detected_posts
        self.all_detected_posts = detected_posts
        self.start_population_thread(detected_posts)

    def start_population_thread(self, detected_posts):
        self.background_task_label.setText("Populating posts...")
        self.background_task_progress.setRange(0, 0)
        self.post_population_thread = PostPopulationThread(detected_posts)
        self.post_population_thread.finished.connect(self.on_post_population_finished)
        self.post_population_thread.log.connect(self.append_log_to_console)
        self.post_population_thread.finished.connect(self.post_population_thread.deleteLater)
        self.active_threads.append(self.post_population_thread)
        self.post_population_thread.start()

    def on_post_population_finished(self, post_url_map, all_detected_posts):
        self.post_url_map = post_url_map
        self.all_detected_posts = all_detected_posts
        for post_title, (post_id, thumbnail_url) in self.all_detected_posts:
            self.checked_urls[post_id] = False
        for i, (queue_url, _) in enumerate(self.creator_queue):
            if queue_url == self.current_creator_url:
                self.creator_queue[i] = (self.current_creator_url, True)
                self.update_creator_queue_list()
                break
        self.filter_items()
        self.append_log_to_console(f"[DEBUG] Populated {len(self.all_detected_posts)} posts for creator {self.current_creator_url}", "INFO")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def on_post_detection_error(self, error_message):
        self.append_log_to_console(f"[ERROR] {error_message}", "ERROR")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def check_all_creators(self):
        self.all_files_map.clear()
        self.checked_urls.clear()
        self.posts_to_download = []
        unique_post_ids = set()
        total_posts = 0
        for url, _ in self.creator_queue:
            if url not in self.all_files_map:
                thread = PostDetectionThread(url)
                thread.finished.connect(lambda posts, u=url: self.on_check_all_posts_detected(u, posts))
                thread.log.connect(self.append_log_to_console)
                thread.error.connect(self.on_post_detection_error)
                thread.finished.connect(thread.deleteLater)
                self.active_threads.append(thread)
                thread.start()
                self.background_task_label.setText("Detecting posts from link...")
                self.background_task_progress.setRange(0, 0)
            else:
                total_posts += len(self.all_files_map[url])
        self.creator_post_count_label.setText(f"Posts: {total_posts}")
        self.append_log_to_console(f"[INFO] Checked all creators. Total unique posts: {total_posts}", "INFO")

    def on_check_all_posts_detected(self, url, posts):
        self.all_files_map[url] = posts
        total_posts = sum(len(posts) for posts in self.all_files_map.values())
        self.creator_post_count_label.setText(f"Posts: {total_posts}")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        if not any(thread.isRunning() for thread in self.active_threads):
            self.append_log_to_console(f"[INFO] Finished checking all creators. Total posts: {total_posts}", "INFO")

    def start_creator_download(self):
        if not self.creator_queue:
            self.append_log_to_console("[WARNING] No creators in queue to download.", "WARNING")
            return

        if not self.posts_to_download:
            self.append_log_to_console("[WARNING] No posts selected for download.", "WARNING")
            return

        self.downloading = True
        self.parent.tabs.setTabEnabled(0, False)
        self.parent.status_label.setText("Preparing files...")
        self.creator_download_btn.setEnabled(False)
        self.creator_cancel_btn.setEnabled(True)
        self.creator_overall_progress.setValue(0)
        self.total_posts_to_download = len(self.posts_to_download)
        self.completed_posts.clear()
        self.completed_files.clear()
        self.total_files_to_download = 0
        self.creator_overall_progress_label.setText(f"Overall Progress (0/0 files, 0/{self.total_posts_to_download} posts)")
        self.current_file_index = -1
        self.creator_file_progress.setValue(0)
        self.creator_file_progress_label.setText("File Progress 0%")
        self.update_progress_bar_style()

        self.background_task_label.setText("Preparing files to download...")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)

        if self.download_all_links.isChecked():
            urls = [url for url, _ in self.creator_queue]
            self.append_log_to_console(f"[INFO] Preparing files for all creators in queue", "INFO")
        else:
            if not self.current_creator_url:
                self.append_log_to_console("[WARNING] No creator currently viewed to download.", "WARNING")
                self.creator_download_finished()
                return
            urls = [self.current_creator_url]
            self.append_log_to_console(f"[INFO] Preparing files for currently viewed creator: {self.current_creator_url}", "INFO")

        self.prepare_files_for_download(urls)

    def prepare_files_for_download(self, urls):
        if hasattr(self, 'file_preparation_thread') and self.file_preparation_thread is not None and self.file_preparation_thread.isRunning():
            self.append_log_to_console("[WARNING] File preparation already in progress. Please wait.", "WARNING")
            return

        if self.download_all_links.isChecked():
            post_ids = []
            for url in urls:
                post_ids.extend([post_id for _, (post_id, _) in self.all_files_map.get(url, [])])
        else:
            if not self.current_creator_url:
                self.append_log_to_console("[WARNING] No creator currently viewed to download.", "WARNING")
                self.creator_download_finished()
                return
            current_creator_posts = {post_id for _, (post_id, _) in self.all_files_map.get(self.current_creator_url, [])}
            post_ids = [post_id for post_id in self.posts_to_download if post_id in current_creator_posts]

        if not post_ids:
            self.append_log_to_console(f"[WARNING] No posts available for download. Skipping.", "WARNING")
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")
            self.creator_download_finished()
            return

        self.file_preparation_thread = FilePreparationThread(
            post_ids,
            self.all_files_map,
            self.creator_ext_checks,
            self.creator_main_check.isChecked(),
            self.creator_attachments_check.isChecked(),
            self.creator_content_check.isChecked(),
            max_concurrent=5
        )
        self.file_preparation_thread.progress.connect(self.update_background_progress)
        self.file_preparation_thread.finished.connect(lambda files, files_map: self.on_file_preparation_finished(urls, files, files_map))
        self.file_preparation_thread.log.connect(self.append_log_to_console)
        self.file_preparation_thread.error.connect(self.on_file_preparation_error)
        self.file_preparation_thread.finished.connect(self.cleanup_file_preparation_thread)
        self.active_threads.append(self.file_preparation_thread)
        self.file_preparation_thread.start()

    def cleanup_file_preparation_thread(self):
        """Clean up the file preparation thread after it finishes."""
        if self.file_preparation_thread in self.active_threads:
            self.active_threads.remove(self.file_preparation_thread)
        self.file_preparation_thread.deleteLater()
        self.file_preparation_thread = None

    def update_background_progress(self, value):
        self.background_task_progress.setValue(value)

    def on_file_preparation_finished(self, urls, files_to_download, files_to_posts_map):
        self.total_files_to_download = len(files_to_download)
        self.append_log_to_console(f"[DEBUG] Prepared {self.total_files_to_download} files for download", "INFO")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

        if not files_to_download:
            self.append_log_to_console(f"[WARNING] No files detected for selected posts. Skipping.", "WARNING")
            self.process_next_creator(urls[1:] if len(urls) > 1 else [])
            return

        url = urls[0]
        remaining_urls = urls[1:]
        parts = url.split('/')
        service, creator_id = parts[-3], parts[-1]

        self.creator_overall_progress_label.setText(
            f"Overall Progress (0/{self.total_files_to_download} files, 0/{self.total_posts_to_download} posts)"
        )
        max_concurrent = self.parent.settings_tab.get_simultaneous_downloads()
        thread = CreatorDownloadThread(service, creator_id, self.parent.download_folder, 
                                      self.posts_to_download, files_to_download, files_to_posts_map, 
                                      self.creator_console, self.other_files_dir, max_concurrent)
        thread.file_progress.connect(self.update_creator_file_progress)
        thread.file_completed.connect(self.update_file_completion)
        thread.post_completed.connect(self.update_post_completion)
        thread.log.connect(self.append_log_to_console)
        thread.finished.connect(lambda: self.cleanup_thread(thread, remaining_urls))
        thread.finished.connect(thread.deleteLater)
        self.active_threads.append(thread)
        thread.start()

    def on_file_preparation_error(self, error_message):
        self.append_log_to_console(f"[ERROR] {error_message}", "ERROR")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        self.creator_download_finished()

    def process_next_creator(self, remaining_urls):
        """Process the next creator or finish if no more remain."""
        if not remaining_urls:
            self.creator_download_finished()
            return
        url = remaining_urls[0]
        new_remaining_urls = remaining_urls[1:]
        self.append_log_to_console(f"[INFO] Moving to next creator: {url}", "INFO")
        self.completed_files.clear()
        self.completed_posts.clear()  
        self.prepare_files_for_download([url] + new_remaining_urls)

    def cleanup_thread(self, thread, remaining_urls):
        """Clean up a download thread and proceed to the next creator or finish."""
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        if self.total_files_to_download > 0 and len(self.completed_files) >= self.total_files_to_download:
            self.append_log_to_console(f"[DEBUG] All files downloaded for current creator. Proceeding.", "INFO")
            self.process_next_creator(remaining_urls)
        elif not self.active_threads and not remaining_urls:
            self.append_log_to_console(f"[DEBUG] No more active threads or creators. Finishing.", "INFO")
            self.creator_download_finished()
        else:
            self.append_log_to_console(f"[DEBUG] Waiting for remaining files: {len(self.completed_files)}/{self.total_files_to_download}", "INFO")

    def cancel_creator_download(self):
        if self.active_threads:
            for thread in self.active_threads[:]:
                if hasattr(thread, 'stop'):
                    thread.stop()
            self.append_log_to_console("[WARNING] All downloads cancelled by user", "WARNING")
            self.creator_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #D4A017; }")
            self.creator_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #D4A017; }")
            self.creator_file_progress_label.setText("Downloads Terminated")
            self.creator_overall_progress_label.setText("Downloads Terminated")
            self.active_threads.clear()
            self.downloading = False
            self.parent.tabs.setTabEnabled(0, True)
            self.parent.status_label.setText("Idle")
            self.creator_download_btn.setEnabled(True)
            self.creator_cancel_btn.setEnabled(False)
            self.total_files_to_download = 0
            self.completed_files.clear()
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")
            self.file_preparation_thread = None

    def update_creator_file_progress(self, file_index, progress):
        if self.current_file_index == file_index or self.current_file_index == -1:
            self.current_file_index = file_index
            self.creator_file_progress.setValue(progress)
            self.creator_file_progress_label.setText(f"File Progress {progress}%")

    def update_file_completion(self, file_index, file_url):
        """Update file completion status and check overall progress."""
        if file_url not in self.completed_files:
            self.completed_files.add(file_url)
            self.append_log_to_console(f"[DEBUG] File completed: {file_url}, Total completed: {len(self.completed_files)}/{self.total_files_to_download}", "INFO")
            self.update_overall_progress()
        if self.current_file_index == file_index:
            self.current_file_index = -1
            self.creator_file_progress.setValue(0)
            self.creator_file_progress_label.setText("File Progress 0%")

    def update_overall_progress(self):
        """Update the overall progress bar and label."""
        if self.total_files_to_download > 0:
            completed_count = len(self.completed_files)
            percentage = int((completed_count / self.total_files_to_download) * 100)
            self.creator_overall_progress.setValue(percentage)
            self.append_log_to_console(
                f"[DEBUG] Overall progress updated: {completed_count}/{self.total_files_to_download} files, {percentage}%", "INFO"
            )
            self.creator_overall_progress_label.setText(
                f"Overall Progress ({completed_count}/{self.total_files_to_download} files, {len(self.completed_posts)}/{self.total_posts_to_download} posts)"
            )
        else:
            self.creator_overall_progress.setValue(0)
            self.creator_overall_progress_label.setText(
                f"Overall Progress (0/0 files, {len(self.completed_posts)}/{self.total_posts_to_download} posts)"
            )

    def update_post_completion(self, post_id):
        """Update post completion status and check overall progress."""
        self.completed_posts.add(post_id)
        self.append_log_to_console(f"[INFO] Post {post_id} fully downloaded.", "INFO")
        self.update_overall_progress()
        if len(self.completed_posts) == self.total_posts_to_download and self.total_files_to_download == len(self.completed_files):
            self.append_log_to_console(f"[DEBUG] All posts and files completed for current creator.", "INFO")

    def creator_download_finished(self):
        """Reset UI state after download completes or is cancelled."""
        self.downloading = False
        self.parent.tabs.setTabEnabled(0, True)
        self.parent.status_label.setText("Idle")
        self.creator_download_btn.setEnabled(True)
        self.creator_cancel_btn.setEnabled(False)
        self.append_log_to_console("[INFO] Download process completed", "INFO")
        
        if self.total_files_to_download > 0 and len(self.completed_files) == self.total_files_to_download:
            self.creator_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: green; }")
            self.creator_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: green; }")
            self.creator_overall_progress_label.setText("Downloads Complete")
        else:
            self.creator_file_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
            self.creator_overall_progress.setStyleSheet("QProgressBar { border: 1px solid #4A5B7A; border-radius: 5px; background: #2A3B5A; } QProgressBar::chunk { background: #4A5B7A; }")
            self.creator_overall_progress_label.setText(f"Overall Progress ({len(self.completed_files)}/{self.total_files_to_download} files, {len(self.completed_posts)}/{self.total_posts_to_download} posts)")
        
        self.total_files_to_download = 0
        self.completed_files.clear()
        self.completed_posts.clear()
        self.current_file_index = -1
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        self.file_preparation_thread = None

    def toggle_check_all(self, state):
        if self.checkbox_toggle_thread and self.checkbox_toggle_thread.isRunning():
            self.append_log_to_console("[WARNING] Checkbox toggle already in progress. Please wait.", "WARNING")
            return
        self.background_task_label.setText("Updating checkboxes...")
        self.background_task_progress.setRange(0, 0)
        self.checkbox_toggle_thread = CheckboxToggleThread(self.all_detected_posts, self.checked_urls, state)
        self.checkbox_toggle_thread.finished.connect(self.on_toggle_check_all_finished)
        self.checkbox_toggle_thread.log.connect(self.append_log_to_console)
        self.checkbox_toggle_thread.finished.connect(self.checkbox_toggle_thread.deleteLater)
        self.active_threads.append(self.checkbox_toggle_thread)
        self.checkbox_toggle_thread.start()

    def on_toggle_check_all_finished(self, checked_urls, posts_to_download):
        self.checked_urls = checked_urls
        self.posts_to_download = posts_to_download
        self.filter_items()
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        self.append_log_to_console(f"[DEBUG] Check ALL toggle finished, checked posts: {len(self.posts_to_download)}", "INFO")

    def toggle_download_all_links(self, state):
        self.background_task_label.setText("Updating download mode...")
        self.background_task_progress.setRange(0, 0)
        is_checked = state == 2
        if is_checked:
            self.creator_check_all.setEnabled(False)
            for i in range(self.creator_post_list.count()):
                item = self.creator_post_list.item(i)
                widget = self.creator_post_list.itemWidget(item)
                if widget:
                    widget.check_box.setEnabled(False)
            self.check_all_creators()
            for creator_url, posts in self.all_files_map.items():
                for _, (post_id, _) in posts:
                    self.checked_urls[post_id] = True
            self.update_checked_posts()
        else:
            self.creator_check_all.setEnabled(True)
            for i in range(self.creator_post_list.count()):
                item = self.creator_post_list.item(i)
                widget = self.creator_post_list.itemWidget(item)
                if widget:
                    widget.check_box.setEnabled(True)
            self.update_checked_posts()
            self.filter_items()
            self.append_log_to_console("[INFO] Download All Links disabled. Reverted to current creator.", "INFO")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def update_checked_posts(self):
        if self.download_all_links.isChecked():
            self.posts_to_download = []
            seen_ids = set()
            for creator_url, posts in self.all_files_map.items():
                for _, (post_id, _) in posts:
                    if post_id not in seen_ids and self.checked_urls.get(post_id, False):
                        self.posts_to_download.append(post_id)
                        seen_ids.add(post_id)
            self.creator_post_count_label.setText(f"Posts: {len(self.posts_to_download)}")
        else:
            self.posts_to_download = []
            seen_ids = set()
            current_creator_posts = {post_id for _, (post_id, _) in self.all_detected_posts}
            for post_id, is_checked in self.checked_urls.items():
                if is_checked and post_id in current_creator_posts and post_id not in seen_ids:
                    self.posts_to_download.append(post_id)
                    seen_ids.add(post_id)
            self.creator_post_count_label.setText(f"Posts: {len(self.posts_to_download)}")
        self.append_log_to_console(
            f"[DEBUG] Updated checked posts count: {len(self.posts_to_download)}, checked_urls: {len(self.checked_urls)}, all_detected: {len(self.all_detected_posts)}, selected IDs: {[pid for pid in self.posts_to_download]}",
            "INFO"
        )

    def filter_items(self):
        if hasattr(self, 'filter_thread') and self.filter_thread is not None and self.filter_thread.isRunning():
            self.append_log_to_console("[WARNING] Filtering already in progress. Please wait.", "WARNING")
            return
        self.background_task_label.setText("Filtering posts...")
        self.background_task_progress.setRange(0, 0)
        self.filter_thread = FilterThread(self.all_detected_posts, self.checked_urls, self.creator_search_input.text())
        self.filter_thread.finished.connect(self.on_filter_finished)
        self.filter_thread.log.connect(self.append_log_to_console)
        self.filter_thread.finished.connect(self.cleanup_filter_thread)
        self.active_threads.append(self.filter_thread)
        self.filter_thread.start()

    def on_filter_finished(self, filtered_items):
        self.creator_post_list.clear()
        self.previous_selected_widget = None

        for post_title, post_id, thumbnail_url, is_checked in filtered_items:
            self.add_list_item(post_title, thumbnail_url, is_checked)

        self.update_check_all_state()
        self.update_checked_posts()
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")
        self.append_log_to_console(f"[DEBUG] Filtering completed, displayed {self.creator_post_list.count()} posts", "INFO")

    def cleanup_filter_thread(self):
        """Clean up the filter thread after it finishes."""
        if self.filter_thread in self.active_threads:
            self.active_threads.remove(self.filter_thread)
        self.filter_thread.deleteLater()
        self.filter_thread = None
                
    def add_list_item(self, text, url, is_checked):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, url)
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        check_box = QCheckBox()
        check_box.setStyleSheet("color: white;")
        check_box.setChecked(is_checked)
        check_box.clicked.connect(lambda: self.toggle_checkbox_state(text))
        if self.download_all_links.isChecked():
            check_box.setEnabled(False)
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

    def toggle_checkbox_state(self, post_title):
        self.background_task_label.setText("Toggling checkbox...")
        self.background_task_progress.setRange(0, 0)
        post_id, _ = self.post_url_map.get(post_title, (None, None))
        if not post_id:
            self.background_task_progress.setRange(0, 100)
            self.background_task_progress.setValue(0)
            self.background_task_label.setText("Idle")
            return
        current_state = self.checked_urls.get(post_id, False)
        new_state = not current_state
        self.checked_urls[post_id] = new_state
        widget = self.get_widget_for_post_title(post_title)
        if widget:
            widget.check_box.blockSignals(True)
            widget.check_box.setChecked(new_state)
            widget.check_box.blockSignals(False)
        self.update_checked_posts()
        self.update_check_all_state()
        self.append_log_to_console(f"[DEBUG] Checkbox toggled for post {post_id} to {new_state}", "INFO")
        self.background_task_progress.setRange(0, 100)
        self.background_task_progress.setValue(0)
        self.background_task_label.setText("Idle")

    def get_widget_for_post_title(self, post_title):
        for i in range(self.creator_post_list.count()):
            item = self.creator_post_list.item(i)
            widget = self.creator_post_list.itemWidget(item)
            if widget and widget.label.text() == post_title:
                return widget
        return None

    def update_check_all_state(self):
        all_visible_checked = all(
            self.creator_post_list.itemWidget(self.creator_post_list.item(i)).check_box.isChecked()
            for i in range(self.creator_post_list.count()) if not self.creator_post_list.item(i).isHidden()
        ) and self.creator_post_list.count() > 0
        self.creator_check_all.blockSignals(True)
        self.creator_check_all.setChecked(all_visible_checked)
        self.creator_check_all.blockSignals(False)
        self.append_log_to_console(f"[DEBUG] Check ALL state updated to {all_visible_checked}", "INFO")

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