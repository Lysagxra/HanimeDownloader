"""Module to download hanime episodes from a given hanime.tv URL.

It includes functions for validating URLs, retrieving video information,
displaying video details, handling video stream processing, and downloading
the video in encrypted segments. The module uses various libraries for HTTP
requests, cryptography, and terminal styling.

Usage:
    - Run the script with the URL of the hanime page as a command-line
      argument.
    - It will create a directory structure in the 'Downloads' folder based on
      the hanime name where each episode will be downloaded.
"""

from __future__ import annotations

import argparse
import logging
import sys
from argparse import Namespace

from helpers.downloader.episode_downloader import EpisodeDownloader
from helpers.general_utils import clear_terminal
from helpers.managers.live_manager import LiveManager
from helpers.managers.log_manager import LoggerTable
from helpers.managers.progress_manager import ProgressManager

# Suppress the httpx log messages
logging.getLogger("httpx").setLevel(logging.WARNING)


def initialize_managers(*, disable_ui: bool = False) -> LiveManager:
    """Initialize and return the managers for progress tracking and logging."""
    progress_manager = ProgressManager(task_name="Episode", item_description="File")
    logger_table = LoggerTable()
    return LiveManager(progress_manager, logger_table, disable_ui=disable_ui)


def parse_arguments() -> Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Acquire URL and other arguments.")
    parser.add_argument("url", type=str, help="The URL to process")
    parser.add_argument(
        "--disable-ui",
        action="store_true",
        help="Disable the user interface",
    )
    return parser.parse_args()


def validate_and_download(url: str, live_manager: LiveManager) -> None:
    """Validate the provided URL, and initiate the download process."""
    episode_downloader = EpisodeDownloader(url=url, live_manager=live_manager)
    episode_downloader.download()


def main() -> None:
    """Run the script."""
    clear_terminal()
    args = parse_arguments()
    live_manager = initialize_managers(disable_ui=args.disable_ui)

    try:
        with live_manager.live:
            validate_and_download(args.url, live_manager)
            live_manager.stop()

    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
