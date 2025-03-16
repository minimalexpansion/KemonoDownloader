from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class HelpTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        # Main layout for the Help tab
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #2A3B5A;
                border-radius: 5px;
            }
            QScrollBar:vertical {
                border: none;
                background: #3A4B6A;
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #4A5B7A;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setSpacing(20)

        # Title
        title_label = QLabel("<h1>Kemono Downloader User Manual</h1>")
        title_label.setFont(QFont("Poppins", 20, QFont.Weight.Bold))
        title_label.setStyleSheet("color: white; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title_label)

        # Introduction
        intro_label = QLabel(
            "Welcome to the Kemono Downloader, a powerful tool designed to help you download content from Kemono.su, "
            "a platform that archives posts from various creator services such as Patreon, Fanbox, and more. This user manual provides "
            "detailed instructions on how to use the application, covering every feature and tab in depth. Whether you're downloading a single post "
            "or an entire creator's archive, this guide will walk you through each step, explain the interface, and offer troubleshooting tips to ensure a smooth experience.<br><br>"
            "<b>Key Features:</b><br>"
            "- Download individual posts or entire creator profiles from Kemono.su.<br>"
            "- Support for multiple file types including images (JPG, PNG, GIF), videos (MP4), archives (ZIP, 7Z), and PDFs.<br>"
            "- Concurrent downloads for faster performance, with customizable settings.<br>"
            "- Preview images before downloading to confirm content.<br>"
            "- Deduplication of files using URL hashes to avoid redundant downloads.<br>"
            "- Detailed logging for monitoring download progress and diagnosing issues.<br>"
            "- Customizable save directories, themes, and notification settings.<br><br>"
            "Follow the sections below to learn how to use each tab and feature of the Kemono Downloader."
        )
        intro_label.setFont(QFont("Poppins", 12))
        intro_label.setStyleSheet("color: #D0D0D0; padding: 5px;")
        intro_label.setWordWrap(True)
        intro_label.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(intro_label)

        # Section: Getting Started
        getting_started_title = QLabel("<h2>1. Getting Started</h2>")
        getting_started_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        getting_started_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(getting_started_title)

        getting_started_text = QLabel(
            "<b>1.1 Launching the Application</b><br>"
            "- When you first open the Kemono Downloader, you'll be greeted by an introductory screen featuring the application title 'Kemono.su Downloader'.<br>"
            "- Below the title, you'll see the developer's name ('Developed by VoxDroid') and a clickable link to the GitHub repository (github.com/VoxDroid) for updates and support.<br>"
            "- Click the 'Launch' button in the center of the screen to proceed to the main interface.<br><br>"
            "<b>1.2 Main Interface Overview</b><br>"
            "The main interface is divided into four tabs, each serving a specific purpose:<br>"
            "  - <b>Post Downloader</b>: Use this tab to download files from specific Kemono.su posts by entering their URLs. Ideal for downloading individual posts.<br>"
            "  - <b>Creator Downloader</b>: Use this tab to download content from an entire creator's profile, fetching all their posts and associated files.<br>"
            "  - <b>Settings</b>: Configure the application's behavior, such as save directories, simultaneous downloads, and UI preferences.<br>"
            "  - <b>Help</b>: You're here! This tab provides this comprehensive user manual to guide you through using the application.<br><br>"
            "<b>1.3 Interface Elements</b><br>"
            "- <b>Tabs</b>: Located at the top of the main interface, the tabs are styled with icons and labels. The active tab is highlighted with a darker background.<br>"
            "- <b>Status Bar</b>: At the bottom of the window, a status label (e.g., 'Idle') indicates the application's current state. It updates during operations like downloading.<br>"
            "- <b>Footer</b>: Also at the bottom, the footer displays the developer's name and GitHub link for quick access to the project page.<br><br>"
            "<b>1.4 Initial Setup</b><br>"
            "- Upon first launch, the application creates several directories in the default save location (configurable in the Settings tab):<br>"
            "  - <b>Downloads</b>: Where downloaded files are saved.<br>"
            "  - <b>Cache</b>: Stores temporary files for image previews.<br>"
            "  - <b>Other Files</b>: Contains metadata like file hashes for deduplication.<br>"
            "- Ensure you have an active internet connection, as the application needs to fetch data from Kemono.su."
        )
        getting_started_text.setFont(QFont("Poppins", 12))
        getting_started_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        getting_started_text.setWordWrap(True)
        getting_started_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(getting_started_text)

        # Section: Using the Post Downloader Tab
        post_downloader_title = QLabel("<h2>2. Using the Post Downloader Tab</h2>")
        post_downloader_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        post_downloader_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(post_downloader_title)

        post_downloader_text = QLabel(
            "The Post Downloader tab is designed for downloading content from specific Kemono.su posts. You can add multiple posts to a queue, view their contents, select files to download, and monitor the download progress. Below are the detailed steps to use this tab effectively:<br><br>"
            "<b>2.1 Adding a Post to the Queue</b><br>"
            "- <b>Step 1</b>: Navigate to the 'Post Downloader' tab by clicking its label at the top of the interface. The tab is marked with a download icon.<br>"
            "- <b>Step 2</b>: Locate the 'Enter post URL' field at the top left of the tab. This is a text input field with a placeholder text 'Enter post URL (e.g., https://kemono.su/patreon/user/123/post/456)'.<br>"
            "- <b>Step 3</b>: Enter the URL of a Kemono.su post. The URL must follow the format: https://kemono.su/[service]/user/[user_id]/post/[post_id]. For example: https://kemono.su/patreon/user/123456785/post/12345678.<br>"
            "- <b>Step 4</b>: Click the 'Add to Queue' button next to the input field. The button is styled with a plus icon and a blue background.<br>"
            "- <b>Step 5</b>: The post URL will appear in the 'Post Queue' list below the input field. Each entry in the list includes:<br>"
            "  - An eye icon to view the post's contents.<br>"
            "  - The post URL as a clickable label.<br>"
            "  - An 'X' button to remove the post from the queue.<br><br>"
            "<b>2.2 Viewing Post Contents</b><br>"
            "- <b>Step 1</b>: In the 'Post Queue' list, find the post you want to inspect.<br>"
            "- <b>Step 2</b>: Click the eye icon next to the post URL. This initiates a background task to fetch the post's data from Kemono.su.<br>"
            "- <b>Step 3</b>: The files associated with the post will be displayed in the 'Files to Download' list on the right side of the tab.<br>"
            "- <b>Step 4</b>: Use the 'Filter by Type' checkboxes (e.g., JPG, ZIP, MP4) to show only specific file types. For example, checking 'JPG' will display only image files with .jpg or .jpeg extensions.<br>"
            "- <b>Step 5</b>: Use the search bar above the 'Files to Download' list to filter files by name. For example, typing 'image' will show only files with 'image' in their names.<br>"
            "- <b>Note</b>: The 'Background Task Progress' bar at the bottom right will show a looping animation while the post data is being fetched. The label above it will read 'Fetching files from link...'.<br><br>"
            "<b>2.3 Selecting Files to Download</b><br>"
            "- <b>Step 1</b>: In the 'Files to Download' list, each file is listed with a checkbox next to its name. By default, all files are selected (checkboxes are checked).<br>"
            "- <b>Step 2</b>: Uncheck the boxes next to files you do not wish to download. For example, if you only want images, uncheck ZIP or MP4 files.<br>"
            "- <b>Step 3</b>: Use the 'Check ALL' checkbox above the list to quickly select or deselect all visible files. If filters are applied, this affects only the filtered files.<br>"
            "- <b>Step 4</b>: To download files from all posts in the queue at once, check the 'Download All Links' option. This disables individual file selection and prepares all files from all queued posts for download.<br>"
            "- <b>Note</b>: When 'Download All Links' is enabled, the checkboxes in the 'Files to Download' list are disabled, and the application will attempt to download all files from all posts in the queue.<br><br>"
            "<b>2.4 Starting the Download</b><br>"
            "- <b>Step 1</b>: Ensure you have selected the desired files or enabled 'Download All Links'.<br>"
            "- <b>Step 2</b>: Click the 'Download' button at the bottom left of the tab. The button is marked with a download icon and styled with a blue background.<br>"
            "- <b>Step 3</b>: The download process will begin, and the following elements will update:<br>"
            "  - <b>File Progress Bar</b>: Shows the progress of the current file being downloaded (0% to 100%). The label above it (e.g., 'File Progress 50%') updates accordingly.<br>"
            "  - <b>Overall Progress Bar</b>: Displays the total progress across all files and posts (e.g., 'Overall Progress (5/10 files, 2/3 posts)').<br>"
            "  - <b>Console</b>: Logs messages about the download process, such as 'Starting download of file 1/10: [URL]' or 'Successfully downloaded: [path]'. Logs are color-coded: green for info, yellow for warnings, red for errors.<br>"
            "- <b>Note</b>: During the download, the 'Download' button becomes disabled, and the 'Cancel' button is enabled.<br><br>"
            "<b>2.5 Managing Downloads</b><br>"
            "- <b>Canceling Downloads</b>: Click the 'Cancel' button (marked with an 'X' icon) to stop all active downloads. The progress bars will turn yellow, and the labels will update to 'Downloads Terminated'.<br>"
            "- <b>Removing Posts from Queue</b>: Click the 'X' button next to a post URL in the 'Post Queue' list to remove it. You'll be prompted to confirm the removal.<br>"
            "- <b>Previewing Images</b>: Select an image file (JPG, JPEG, PNG, or GIF) in the 'Files to Download' list, then click the eye icon button below the list to preview it. A modal window will open showing the image, with a progress bar while it loads.<br>"
            "- <b>Note</b>: If a post is removed during an active download, the download for that post's files will be canceled.<br><br>"
            "<b>2.6 Where Files Are Saved</b><br>"
            "- Files are saved in the directory specified in the Settings tab (default is your user directory under 'Kemono Downloader/Downloads').<br>"
            "- The folder structure is organized as follows:<br>"
            "  - <b>Service Folder</b>: Named after the service (e.g., 'patreon').<br>"
            "  - <b>Post Folder</b>: Named 'post_[post_id]' (e.g., 'post_12345678').<br>"
            "  - Example: If downloading from https://kemono.su/patreon/user/123456785/post/12345678, files will be saved in '[Save Directory]/patreon/post_12345678/'.<br>"
            "- Files are named based on their original URLs, with any special characters (e.g., '/') replaced with underscores to ensure compatibility with your filesystem.<br><br>"
            "<b>2.7 Additional Features</b><br>"
            "- <b>Concurrent Downloads</b>: The application supports downloading multiple files simultaneously, with the number of concurrent downloads set in the Settings tab (default is 10, adjustable between 1-10).<br>"
            "- <b>File Deduplication</b>: The application uses URL hashes to detect and skip previously downloaded files, preventing duplicates. Hash data is stored in the 'Other Files' directory as 'file_hashes.json'.<br>"
            "- <b>Image Caching</b>: When previewing images, they are cached in the 'Cache' directory to speed up future previews of the same image.<br>"
            "- <b>Logging</b>: The console provides detailed logs of all operations, including file detection, download progress, and errors. This is useful for debugging issues."
        )
        post_downloader_text.setFont(QFont("Poppins", 12))
        post_downloader_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        post_downloader_text.setWordWrap(True)
        post_downloader_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(post_downloader_text)

        # Section: Using the Creator Downloader Tab
        creator_downloader_title = QLabel("<h2>3. Using the Creator Downloader Tab</h2>")
        creator_downloader_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        creator_downloader_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(creator_downloader_title)

        creator_downloader_text = QLabel(
            "The Creator Downloader tab is designed for bulk downloading content from a creator's entire profile on Kemono.su. You can queue multiple creators, fetch their posts, select specific content to download, and monitor the progress. This tab is ideal for archiving a creator's work or downloading content from multiple creators at once. Below are the detailed steps to use this tab effectively:<br><br>"
            "<b>3.1 Adding a Creator to the Queue</b><br>"
            "- <b>Step 1</b>: Navigate to the 'Creator Downloader' tab by clicking its label at the top of the interface. The tab is marked with a user-edit icon.<br>"
            "- <b>Step 2</b>: Locate the 'Enter creator URL' field at the top left of the tab. This is a text input field with a placeholder text 'Enter creator URL (e.g., https://kemono.su/patreon/user/12345678)'.<br>"
            "- <b>Step 3</b>: Enter the URL of a creator's profile on Kemono.su. The URL must follow the format: https://kemono.su/[service]/user/[user_id]. For example: https://kemono.su/patreon/user/12345678.<br>"
            "- <b>Step 4</b>: Click the 'Add to Queue' button next to the input field. The button is styled with a plus icon and a blue background.<br>"
            "- <b>Step 5</b>: The creator URL will appear in the 'Creator Queue' list below the input field. Each entry in the list includes:<br>"
            "  - An eye icon to fetch and view the creator's posts.<br>"
            "  - The creator URL as a clickable label.<br>"
            "  - An 'X' button to remove the creator from the queue.<br>"
            "- <b>Note</b>: Duplicate URLs are automatically prevented. If you try to add a URL already in the queue, a warning message will appear in the console: '[WARNING] URL already in queue.'<br><br>"
            "<b>3.2 Viewing Creator Posts</b><br>"
            "- <b>Step 1</b>: In the 'Creator Queue' list, find the creator whose posts you want to view.<br>"
            "- <b>Step 2</b>: Click the eye icon next to the creator URL. This initiates a background task to fetch all posts associated with the creator from Kemono.su.<br>"
            "- <b>Step 3</b>: The posts will be displayed in the 'Posts to Download' list on the right side of the tab. Each post entry includes:<br>"
            "  - A checkbox to select the post for download.<br>"
            "  - The post title (or 'Post [post_id]' if no title is available).<br>"
            "  - A thumbnail URL (if available) stored as user data for previewing.<br>"
            "- <b>Step 4</b>: Use the search bar above the 'Posts to Download' list to filter posts by title. For example, typing 'artwork' will show only posts with 'artwork' in their titles.<br>"
            "- <b>Note</b>: The 'Background Task Progress' bar at the bottom right will show a looping animation while posts are being fetched, with the label 'Detecting posts from link...'. Once complete, the label changes to 'Idle'.<br><br>"
            "<b>3.3 Configuring Download Options</b><br>"
            "- <b>Step 1</b>: Under the 'Download Options' group box, configure which content types to include in the download:<br>"
            "  - <b>Main File</b>: Includes the primary file attached to each post (e.g., a featured image or video). Enabled by default.<br>"
            "  - <b>Attachments</b>: Includes additional files attached to the post (e.g., ZIP files, extra images). Enabled by default.<br>"
            "  - <b>Content Images</b>: Includes images embedded in the post's content (e.g., images in the post description). Enabled by default.<br>"
            "- <b>Step 2</b>: In the 'File Extensions' group box, select which file types to download:<br>"
            "  - Options include JPG/JPEG, PNG, ZIP, MP4, GIF, PDF, and 7Z.<br>"
            "  - All file types are enabled by default. Uncheck any file types you do not wish to download.<br>"
            "  - Example: If you only want images, uncheck ZIP, MP4, PDF, and 7Z, leaving JPG/JPEG, PNG, and GIF checked.<br>"
            "- <b>Note</b>: Changing these options will automatically update the list of files to download when you start the download process.<br><br>"
            "<b>3.4 Selecting Posts to Download</b><br>"
            "- <b>Step 1</b>: In the 'Posts to Download' list, check the boxes next to the posts you want to download. By default, no posts are selected.<br>"
            "- <b>Step 2</b>: Use the 'Check ALL' checkbox above the list to select or deselect all visible posts. If the search filter is applied, this affects only the filtered posts.<br>"
            "- <b>Step 3</b>: Alternatively, enable the 'Download All Links' option to download all files from all queued creators without manual selection:<br>"
            "  - When enabled, this option disables individual post checkboxes and fetches all posts from all creators in the queue.<br>"
            "  - The application will automatically select all posts for download, ignoring manual selections.<br>"
            "- <b>Note</b>: The 'Posts: [number]' label below the list updates to reflect the number of selected posts. When 'Download All Links' is enabled, this shows the total number of posts across all queued creators.<br><br>"
            "<b>3.5 Starting the Download</b><br>"
            "- <b>Step 1</b>: Ensure you have selected the desired posts or enabled 'Download All Links'.<br>"
            "- <b>Step 2</b>: Click the 'Download' button at the bottom left of the tab. The button is marked with a download icon and styled with a blue background.<br>"
            "- <b>Step 3</b>: The application will first prepare the files for download, showing 'Preparing files to download...' in the background task label and a progress bar.<br>"
            "- <b>Step 4</b>: Once preparation is complete, the download process begins, and the following elements update:<br>"
            "  - <b>File Progress Bar</b>: Shows the progress of the current file being downloaded (0% to 100%). The label above it (e.g., 'File Progress 50%') updates accordingly.<br>"
            "  - <b>Overall Progress Bar</b>: Displays the total progress across all files and posts (e.g., 'Overall Progress (5/10 files, 2/3 posts)').<br>"
            "  - <b>Console</b>: Logs messages such as 'Starting download of file 1/10: [URL]' or 'Successfully downloaded: [path]'. Logs are color-coded: green for info, yellow for warnings, red for errors.<br>"
            "- <b>Note</b>: During the download, the 'Download' button becomes disabled, the 'Cancel' button is enabled, and the 'Post Downloader' tab is temporarily disabled to prevent conflicts.<br><br>"
            "<b>3.6 Managing Downloads</b><br>"
            "- <b>Canceling Downloads</b>: Click the 'Cancel' button (marked with an 'X' icon) to stop all active downloads. The progress bars will turn yellow, and the labels will update to 'Downloads Terminated'. The 'Post Downloader' tab will be re-enabled.<br>"
            "- <b>Removing Creators from Queue</b>: Click the 'X' button next to a creator URL in the 'Creator Queue' list to remove it. You'll be prompted to confirm the removal. If removed during an active download, the download for that creator's posts will be canceled.<br>"
            "- <b>Previewing Images</b>: Select a post in the 'Posts to Download' list, then click the eye icon button below the list to preview its thumbnail (if available). Only JPG, JPEG, PNG, and GIF files are supported for preview. A modal window will open showing the image, with a progress bar while it loads.<br>"
            "- <b>Note</b>: If no posts are selected when you click 'Download', a warning will appear in the console: '[WARNING] No posts selected for download.'<br><br>"
            "<b>3.7 Where Files Are Saved</b><br>"
            "- Files are saved in the directory specified in the Settings tab (default is your user directory under 'Kemono Downloader/Downloads').<br>"
            "- The folder structure is organized as follows:<br>"
            "  - <b>Creator Folder</b>: Named after the creator's ID (e.g., '12345678').<br>"
            "  - <b>Post Folder</b>: Named 'post_[post_id]' within the creator folder (e.g., 'post_12345678').<br>"
            "  - Example: If downloading from creator https://kemono.su/patreon/user/12345678, files from post 12345678 will be saved in '[Save Directory]/12345678/post_12345678/'.<br>"
            "- Files are named based on their original URLs, with any special characters (e.g., '/') replaced with underscores to ensure compatibility with your filesystem.<br>"
            "- <b>File Deduplication</b>: The application uses URL hashes to detect and skip previously downloaded files, storing hash data in 'file_hashes.json' in the 'Other Files' directory.<br><br>"
            "<b>3.8 Additional Features</b><br>"
            "- <b>Concurrent Downloads</b>: The application supports downloading multiple files simultaneously, with the number of concurrent downloads set in the Settings tab (default is 10, adjustable between 1-10).<br>"
            "- <b>Image Caching</b>: Thumbnails and preview images are cached in the 'Cache' directory to speed up future previews of the same image.<br>"
            "- <b>Logging</b>: The console provides detailed logs of all operations, including post detection, file preparation, download progress, and errors. This is useful for debugging issues.<br>"
            "- <b>Batch Processing</b>: When 'Download All Links' is enabled, the application processes creators sequentially, preparing and downloading files for each creator one at a time to manage resources efficiently."
        )
        creator_downloader_text.setFont(QFont("Poppins", 12))
        creator_downloader_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        creator_downloader_text.setWordWrap(True)
        creator_downloader_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(creator_downloader_text)

        # Section: Using the Settings Tab
        settings_title = QLabel("<h2>4. Using the Settings Tab</h2>")
        settings_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        settings_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(settings_title)

        settings_text = QLabel(
            "The Settings tab allows you to customize the Kemono Downloader's behavior to suit your preferences. You can configure save directories, download settings, and UI options. Below are the detailed steps to use this tab:<br><br>"
            "<b>4.1 Accessing the Settings Tab</b><br>"
            "- Navigate to the 'Settings' tab by clicking its label at the top of the interface. The tab is marked with a cog icon.<br><br>"
            "<b>4.2 Folder Settings</b><br>"
            "- <b>Folder Name</b>: This field specifies the name of the base folder where all downloads and related files will be saved. The default is 'Kemono Downloader'.<br>"
            "  - Example: If set to 'My Downloads', the application will create directories like 'My Downloads/Downloads', 'My Downloads/Cache', etc.<br>"
            "  - <b>Note</b>: The folder name cannot be empty. If you try to save an empty name, a warning will appear, and the setting will revert to its previous value.<br>"
            "- <b>Save Directory</b>: This field specifies the root directory where the base folder will be created.<br>"
            "  - Default: Your user directory (e.g., 'C:/Users/YourName' on Windows).<br>"
            "  - Click the 'Browse' button next to the field to open a file dialog and select a new directory.<br>"
            "  - Example: If set to 'D:/Media' with a folder name 'Kemono Downloader', downloads will be saved in 'D:/Media/Kemono Downloader/Downloads'.<br>"
            "  - <b>Note</b>: The directory must be valid and writable. If invalid, a warning will appear, and the setting will revert.<br><br>"
            "<b>4.3 Download Settings</b><br>"
            "- <b>Simultaneous Downloads</b>: This setting controls how many files can be downloaded concurrently.<br>"
            "  - Range: 1 to 10.<br>"
            "  - Default: 10.<br>"
            "  - Use the slider or input field to adjust the value.<br>"
            "  - Example: Setting this to 5 means up to 5 files will be downloaded at the same time, which can reduce network strain on slower connections.<br>"
            "  - <b>Note</b>: Higher values may speed up downloads but can overload your network or the server, leading to timeouts or errors.<br><br>"
            "<b>4.4 UI Customization</b><br>"
            "- <b>Show Notifications</b>: Enable this checkbox to display pop-up notifications for certain events, such as settings updates or download completion.<br>"
            "  - Default: Enabled.<br>"
            "  - Example: When enabled, changing settings and clicking 'Apply Changes' will show a notification confirming the update.<br>"
            "- <b>Dark Theme (Default)</b>: Enable this checkbox to use the dark theme, which features a dark background with light text for better readability in low-light conditions.<br>"
            "  - Default: Enabled.<br>"
            "  - Uncheck to switch to a light theme, which uses a lighter background and darker text.<br>"
            "  - <b>Note</b>: Changing the theme requires clicking 'Apply Changes' to take effect.<br><br>"
            "<b>4.5 Applying Changes</b><br>"
            "- <b>Step 1</b>: Make the desired changes to the settings fields.<br>"
            "- <b>Step 2</b>: Click the 'Apply Changes' button at the bottom of the tab to save your settings.<br>"
            "- <b>Step 3</b>: If the settings are valid, they will be saved, and the application will update accordingly (e.g., new save directories will be created, theme will change).<br>"
            "- <b>Error Handling</b>: If any setting is invalid (e.g., empty folder name, invalid directory), a warning dialog will appear with details of the error, and the settings will revert to their previous values.<br>"
            "- <b>Note</b>: If 'Show Notifications' is enabled, a confirmation notification will appear after successfully applying changes.<br><br>"
            "<b>4.6 Additional Notes</b><br>"
            "- Settings are persistent across application restarts, stored in a configuration file.<br>"
            "- Changing the save directory or folder name will not move existing files; it only affects new downloads.<br>"
            "- The simultaneous downloads setting applies to both the Post Downloader and Creator Downloader tabs."
        )
        settings_text.setFont(QFont("Poppins", 12))
        settings_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        settings_text.setWordWrap(True)
        settings_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(settings_text)

        # Section: Using the Help Tab
        help_tab_title = QLabel("<h2>5. Using the Help Tab</h2>")
        help_tab_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        help_tab_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(help_tab_title)

        help_tab_text = QLabel(
            "The Help tab provides this comprehensive user manual to assist you in using the Kemono Downloader. Here's how to navigate and use this tab:<br><br>"
            "<b>5.1 Accessing the Help Tab</b><br>"
            "- Navigate to the 'Help' tab by clicking its label at the top of the interface. The tab is marked with a question-circle icon.<br><br>"
            "<b>5.2 Navigating the Manual</b><br>"
            "- The manual is presented in a scrollable area with clearly labeled sections.<br>"
            "- Use the scrollbar on the right to navigate through the content, or use your mouse wheel.<br>"
            "- Sections are organized as follows:<br>"
            "  - <b>Getting Started</b>: Initial setup and interface overview.<br>"
            "  - <b>Using the Post Downloader Tab</b>: Instructions for downloading individual posts.<br>"
            "  - <b>Using the Creator Downloader Tab</b>: Instructions for bulk downloading from creators.<br>"
            "  - <b>Using the Settings Tab</b>: Guide to configuring the application.<br>"
            "  - <b>Using the Help Tab</b>: This section, explaining how to use the manual.<br>"
            "  - <b>Troubleshooting</b>: Tips for resolving common issues.<br>"
            "  - <b>Contact and Support</b>: Information on getting help and reporting issues.<br><br>"
            "<b>5.3 Features of the Help Tab</b><br>"
            "- <b>Formatted Text</b>: The manual uses HTML formatting for readability, with headings, bold text, bullet points, and spacing to organize information.<br>"
            "- <b>Examples</b>: Each section includes practical examples (e.g., sample URLs, folder structures) to illustrate usage.<br>"
            "- <b>Comprehensive Coverage</b>: Every feature of the application is documented, including UI elements, error messages, and advanced functionality.<br>"
            "- <b>Scroll Area</b>: The content is contained within a scrollable area with a custom-styled scrollbar for a seamless reading experience.<br><br>"
            "<b>5.4 Additional Notes</b><br>"
            "- The Help tab is static and does not require an internet connection to view, as the manual is embedded within the application.<br>"
            "- If you need further assistance, refer to the 'Contact and Support' section for links to the GitHub repository and issue reporting."
        )
        help_tab_text.setFont(QFont("Poppins", 12))
        help_tab_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        help_tab_text.setWordWrap(True)
        help_tab_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(help_tab_text)

        # Section: Troubleshooting
        troubleshooting_title = QLabel("<h2>6. Troubleshooting</h2>")
        troubleshooting_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        troubleshooting_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(troubleshooting_title)

        troubleshooting_text = QLabel(
            "If you encounter issues while using the Kemono Downloader, this section provides detailed troubleshooting steps to help you resolve them. Below are common problems and their solutions, along with tips for diagnosing issues using the console logs:<br><br>"
            "<b>6.1 Common Issues and Solutions</b><br>"
            "- <b>Invalid URL Error</b>: This occurs when the URL format is incorrect.<br>"
            "  - <b>Post Downloader</b>: Ensure the URL follows the format https://kemono.su/[service]/user/[user_id]/post/[post_id]. Example: https://kemono.su/patreon/user/123456785/post/12345678.<br>"
            "  - <b>Creator Downloader</b>: Ensure the URL follows the format https://kemono.su/[service]/user/[user_id]. Example: https://kemono.su/patreon/user/12345678.<br>"
            "  - <b>Console Message</b>: Look for '[ERROR] Invalid URL format. Expected: [format]' in the console.<br>"
            "  - <b>Solution</b>: Double-check the URL and correct any typos. Ensure the URL points to a valid Kemono.su post or creator profile.<br>"
            "- <b>Download Fails</b>: Downloads may fail due to network issues or unavailable files.<br>"
            "  - <b>Console Message</b>: Look for '[ERROR] Error downloading [URL]: [error]' (e.g., 'connection timed out') or '[ERROR] Failed to fetch [URL] - Status code: [code]' (e.g., 404).<br>"
            "  - <b>Solution</b>: Check your internet connection. If the error is a 404, the file may no longer be available on Kemono.su. Try accessing the URL in a browser to confirm.<br>"
            "- <b>No Files Detected</b>: The 'Files to Download' or 'Posts to Download' list is empty after fetching.<br>"
            "  - <b>Console Message</b>: Look for '[WARNING] No files detected for selected posts. Skipping.' or '[DEBUG] Total files detected: 0'.<br>"
            "  - <b>Solution</b>: Ensure the file types you want to download are checked in the 'Filter by Type' (Post Downloader) or 'File Extensions' (Creator Downloader) sections. Verify that the post or creator has content available.<br>"
            "- <b>Slow Downloads</b>: Downloads are taking longer than expected.<br>"
            "  - <b>Console Message</b>: Look for repeated '[INFO] Starting download of file [index]/[total]: [URL]' messages with slow progress updates.<br>"
            "  - <b>Solution</b>: Reduce the number of simultaneous downloads in the Settings tab to lessen the load on your network. Check your internet speed and ensure no other applications are consuming bandwidth.<br>"
            "- <b>Application Crashes</b>: The application closes unexpectedly.<br>"
            "  - <b>Console Message</b>: If the application crashes, you may not see a message. Check the logs in the console before the crash for clues (e.g., '[ERROR] Unexpected error...').<br>"
            "  - <b>Solution</b>: Ensure you have the latest version of the downloader by checking the GitHub page (github.com/VoxDroid). Update your system and dependencies (e.g., PyQt6, requests). If the issue persists, report it on GitHub with the console logs.<br>"
            "- <b>Image Preview Fails</b>: Attempting to preview an image results in an error.<br>"
            "  - <b>Console Message</b>: Look for '[ERROR] Failed to download image from [URL]: [error]' or '[ERROR] Failed to load image from [URL]: Invalid or corrupted image data'.<br>"
            "  - <b>Solution</b>: Verify your internet connection. Ensure the file is a supported image type (JPG, JPEG, PNG, GIF). The image may no longer be available on Kemono.su or may be corrupted.<br><br>"
            "<b>6.2 Using the Console for Debugging</b><br>"
            "- The console in both the Post Downloader and Creator Downloader tabs logs all operations, making it a valuable tool for diagnosing issues.<br>"
            "- <b>Log Levels</b>:<br>"
            "  - <b>INFO (Green)</b>: Normal operations, such as starting a download or adding a URL to the queue.<br>"
            "  - <b>WARNING (Yellow)</b>: Non-critical issues, such as attempting to add a duplicate URL or canceling a download.<br>"
            "  - <b>ERROR (Red)</b>: Critical issues, such as failed downloads or invalid URLs.<br>"
            "- <b>DEBUG Logs</b>: These provide additional details for advanced users. They are prefixed with '[DEBUG]' and include information like the number of files detected or API responses.<br>"
            "- <b>Tips</b>: Scroll through the console to find the first error or warning message related to your issue. Copy the message and use it to search this troubleshooting section or report the issue on GitHub.<br><br>"
            "<b>6.3 Advanced Troubleshooting</b><br>"
            "- <b>Check File Hashes</b>: If files are not downloading due to deduplication, inspect the 'file_hashes.json' file in the 'Other Files' directory. Each entry maps a URL hash to a file path and its hash. Delete entries for files you want to redownload.<br>"
            "- <b>Clear Cache</b>: If image previews are failing, clear the 'Cache' directory to remove corrupted or outdated cache files.<br>"
            "- <b>Network Issues</b>: Use a tool like 'ping kemono.su' or 'tracert kemono.su' (on Windows) to check for network connectivity issues to the Kemono.su server.<br>"
            "- <b>Rate Limiting</b>: Kemono.su may impose rate limits on requests. If you see frequent '[ERROR] Failed to fetch [URL] - Status code: 429', reduce the number of simultaneous downloads and wait before retrying.<br>"
            "- <b>Dependencies</b>: Ensure all required Python libraries are installed and up to date (e.g., PyQt6, requests, beautifulsoup4, qtawesome). Use 'pip list' to check versions and 'pip install --upgrade [package]' to update.<br><br>"
            "<b>6.4 Known Limitations</b><br>"
            "- The application relies on Kemono.su's availability and API structure. If Kemono.su changes its API or goes offline, the downloader may fail.<br>"
            "- Large creator profiles with thousands of posts may take significant time to fetch and download. Consider downloading in smaller batches by selecting specific posts.<br>"
            "- The image preview feature only supports JPG, JPEG, PNG, and GIF files. Other file types (e.g., MP4, ZIP) cannot be previewed.<br>"
            "- The application does not support resumable downloads. If a download is interrupted, it will restart from the beginning."
        )
        troubleshooting_text.setFont(QFont("Poppins", 12))
        troubleshooting_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        troubleshooting_text.setWordWrap(True)
        troubleshooting_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(troubleshooting_text)

        # Section: Contact and Support
        support_title = QLabel("<h2>7. Contact and Support</h2>")
        support_title.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        support_title.setStyleSheet("color: white; padding: 10px 5px 5px 5px;")
        content_layout.addWidget(support_title)

        support_text = QLabel(
            "If you need further assistance with the Kemono Downloader, the following resources are available:<br><br>"
            "<b>7.1 GitHub Repository</b><br>"
            "- The Kemono Downloader is an open-source project hosted on GitHub.<br>"
            "- Visit the repository at: <a href='https://github.com/VoxDroid' style='color: #A0C0FF; text-decoration: none;'>github.com/VoxDroid</a>.<br>"
            "- The repository contains:<br>"
            "  - The latest version of the application.<br>"
            "  - Release notes with changelogs.<br>"
            "  - An issue tracker for reporting bugs and requesting features.<br>"
            "  - Documentation and contribution guidelines for developers.<br><br>"
            "<b>7.2 Reporting Issues</b><br>"
            "- If you encounter a bug or have a feature request, create an issue on GitHub:<br>"
            "  - Go to the 'Issues' tab in the repository.<br>"
            "  - Click 'New Issue' and choose the appropriate template (e.g., Bug Report, Feature Request).<br>"
            "  - Provide a detailed description, including:<br>"
            "    - Steps to reproduce the issue.<br>"
            "    - Relevant console logs (copy-paste from the application's console).<br>"
            "    - Your operating system and application version.<br>"
            "    - Any screenshots or screen recordings that illustrate the problem.<br>"
            "- <b>Note</b>: Be respectful and provide as much detail as possible to help the developer address your issue efficiently.<br><br>"
            "<b>7.3 Community Support</b><br>"
            "- Check the GitHub 'Discussions' tab for community-driven support. Other users may have encountered and resolved similar issues.<br>"
            "- Search existing issues to see if your problem has already been reported and resolved.<br><br>"
            "<b>7.4 Developer Contact</b><br>"
            "- The Kemono Downloader is developed by VoxDroid. For direct inquiries, check the GitHub repository for contact information (e.g., in the README or profile).<br>"
            "- Avoid contacting the developer for issues that can be resolved through the troubleshooting steps or GitHub issues.<br><br>"
            "<b>7.5 Contributing to the Project</b><br>"
            "- If you're a developer interested in contributing, fork the repository, make your changes, and submit a pull request.<br>"
            "- Review the contribution guidelines in the repository for coding standards and submission requirements."
        )
        support_text.setFont(QFont("Poppins", 12))
        support_text.setStyleSheet("color: #D0D0D0; padding: 5px;")
        support_text.setWordWrap(True)
        support_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        content_layout.addWidget(support_text)

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        self.setMinimumSize(300, 400)  

    def refresh_ui(self):
        pass