"""Module that provides functionality to read URLs from a file, and download from them.

This module manages the entire download process by leveraging asynchronous
operations, allowing for efficient handling of multiple URLs.

Usage:
    To run the module, execute the script directly. It will process URLs
    listed in 'URLs.txt' and log the session activities in 'session_log.txt'.
"""

import argparse
import sys
from argparse import Namespace

from hanime_downloader import initialize_managers, validate_and_download
from helpers.config import FILE
from helpers.file_utils import read_file, write_file
from helpers.general_utils import clear_terminal


def parse_arguments() -> Namespace:
    """Parse only the --disable-ui and --resolution arguments."""
    parser = argparse.ArgumentParser(description="Acquire URL and other arguments.")
    parser.add_argument(
        "--disable-ui",
        action="store_true",
        help="Disable the user interface",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="720p",
        help="Set the resolution (e.g., '480p', '720p')",
    )
    return parser.parse_args()


def process_urls(urls: list[str], args: Namespace) -> None:
    """Validate and downloads items for a list of URLs."""
    live_manager = initialize_managers(disable_ui=args.disable_ui)

    try:
        with live_manager.live:
            for url in urls:
                validate_and_download(url, live_manager, args=args)
            live_manager.stop()

    except KeyboardInterrupt:
        sys.exit(1)


def main() -> None:
    """Run the script and process URLs."""
    # Clear the terminal
    clear_terminal()

    # Parse arguments to get disable_ui flag
    args = parse_arguments()

    # Read and process URLs
    urls = read_file(FILE)
    process_urls(urls, args)

    # Clear URLs file
    write_file(FILE)


if __name__ == "__main__":
    main()
