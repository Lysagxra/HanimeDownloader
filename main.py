"""Module that provides functionality to read URLs from a file, and download from them.

This module manages the entire download process by leveraging asynchronous operations,
allowing for efficient handling of multiple URLs.

Usage:
    To run the module, execute the script directly. It will process URLs
    listed in 'URLs.txt' and log the session activities in 'session.log'.
"""

import sys
from argparse import Namespace

from hanime_downloader import validate_and_download
from src.config import URLS_FILE, parse_arguments
from src.file_utils import read_file, write_file
from src.general_utils import clear_terminal
from src.managers.live_manager import initialize_managers


def process_urls(urls: list[str], args: Namespace) -> None:
    """Validate and downloads items for a list of URLs."""
    live_manager = initialize_managers(disable_ui=args.disable_ui)

    with live_manager.live:
        for url in urls:
            validate_and_download(url, live_manager, args=args)

        live_manager.stop()


def main() -> None:
    """Run the script."""
    # Clear terminal and parse arguments
    clear_terminal()
    args = parse_arguments(common_only=True)

    # Read and process URLs, ignoring empty lines
    urls = [url.strip() for url in read_file(URLS_FILE) if url.strip()]
    process_urls(urls, args)

    # Clear URLs file
    write_file(URLS_FILE)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        sys.exit(1)
