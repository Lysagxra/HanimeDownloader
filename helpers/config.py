"""Configuration module for managing constants and settings used across the project.

These configurations aim to improve modularity and readability by consolidating settings
into a single location.
"""

# ============================
# API / Video Endpoints
# ============================
API_URL = "https://hanime.tv/api/v8"           # The API endpoint for Hanime video data.
VIDEO_URL = "https://hanime.tv/videos/hentai"  # The base URL for Hanime video pages.

# ============================
# Paths and Files
# ============================
DOWNLOAD_FOLDER = "Downloads"  # The folder where downloaded files will be stored.
URLS_FILE = "URLs.txt"         # The file containing the list of URLs to process.

# ============================
# Regex Patterns
# ============================
HANIME_NAME_PATTERN = r"https://hanime\.tv/videos/hentai/([A-Za-z0-9]+(-[A-Za-z0-9]+)+)"

# ============================
# Download Settings
# ============================
MAX_WORKERS = 8  # The maximum number of threads for concurrent downloads.

# Resolution map for selecting video quality
RESOLUTION_MAP = {
    "1080p": 0,
    "720p": 1,
    "480p": 2,
    "360p": 3,
}
