"""Configuration module for managing constants and settings used across the project.

These configurations aim to improve modularity and readability by consolidating settings
into a single location.
"""

FILE = "URLs.txt"
DOWNLOAD_FOLDER = "Downloads"
MAX_WORKERS = 8

API_URL = "https://hanime.tv/api/v8"
VIDEO_URL = "https://hanime.tv/videos/hentai"
HANIME_NAME_PATTERN = r"https://hanime\.tv/videos/hentai/([A-Za-z0-9]+(-[A-Za-z0-9]+)+)"

RESOLUTION_MAP = {
    "1080p": 0,
    "720p": 1,
    "480p": 2,
    "360p": 3,
}
