"""Configuration module for managing constants and settings used across the project.

These configurations aim to improve modularity and readability by consolidating settings
into a single location.
"""

from argparse import ArgumentParser, Namespace

# ============================
# Paths and Files
# ============================
DOWNLOAD_FOLDER = "Downloads"  # The folder where downloaded files will be stored.
URLS_FILE = "URLs.txt"         # The file containing the list of URLs to process.

# ============================
# API / Video Endpoints
# ============================
API_URL = "https://hanime.tv/api/v8"           # The API endpoint for Hanime video data.
VIDEO_URL = "https://hanime.tv/videos/hentai"  # The base URL for Hanime video pages.

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

# ============================
# Argument Parsing
# ============================
def add_common_arguments(parser: ArgumentParser) -> None:
    """Add arguments shared across parsers."""
    parser.add_argument(
        "--custom-path",
        type=str,
        default=None,
        help="The directory where the downloaded content will be saved.",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="720p",
        help="Set the resolution (e.g., '480p', '720p')",
    )
    parser.add_argument(
        "--all-episodes",
        action="store_true",
        help="Download all hanime episodes",
    )
    parser.add_argument(
        "--disable-ui",
        action="store_true",
        help="Disable the user interface.",
    )


def setup_parser(*, include_url: bool = False) -> ArgumentParser:
    """Set up parser with optional argument groups."""
    parser = ArgumentParser(description="Command-line arguments.")

    if include_url:
        parser.add_argument("url", type=str, help="The URL to process")

    add_common_arguments(parser)
    return parser


def parse_arguments(*, common_only: bool = False) -> Namespace:
    """Full argument parser (including URL, filters, and common)."""
    parser = setup_parser() if common_only else setup_parser(include_url=True)
    return parser.parse_args()
