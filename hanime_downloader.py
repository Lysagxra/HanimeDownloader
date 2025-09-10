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

import logging
import sys
from argparse import ArgumentParser, Namespace

from helpers.downloader.crawler_utils import (
    generate_all_episode_urls,
    get_all_episodes_ids,
    get_episode_id,
    get_hanime_info,
)
from helpers.downloader.episode_downloader import EpisodeDownloader
from helpers.general_utils import clear_terminal
from helpers.managers.live_manager import LiveManager
from helpers.managers.log_manager import LoggerTable
from helpers.managers.progress_manager import ProgressManager

# Suppress the httpx log messages
logging.getLogger("httpx").setLevel(logging.WARNING)


def handle_download_process(
    url: str,
    live_manager: LiveManager,
    args: Namespace,
) -> None:
    """Handle the download process for one or multiple episodes based on user arguments.

    If the `--all-episodes` flag is set in `args`, retrieves all related episode URLs
    from the given `url`, then downloads each episode sequentially using
    `validate_and_download`.
    """
    if args.all_episodes:
        episode_id = get_episode_id(url)
        hanime_info = get_hanime_info(episode_id)
        episode_ids = get_all_episodes_ids(hanime_info)
        episode_urls = generate_all_episode_urls(episode_ids)

        for episode_url in episode_urls:
            validate_and_download(episode_url, live_manager, args)

    else:
        validate_and_download(url, live_manager, args)


def validate_and_download(url: str, live_manager: LiveManager, args: Namespace) -> None:
    """Validate the provided URL, and initiate the download process."""
    episode_downloader = EpisodeDownloader(
        url=url,
        live_manager=live_manager,
        args=args,
    )
    episode_downloader.download()


def initialize_managers(*, disable_ui: bool = False) -> LiveManager:
    """Initialize and return the managers for progress tracking and logging."""
    progress_manager = ProgressManager(task_name="Episode", item_description="File")
    logger_table = LoggerTable()
    return LiveManager(progress_manager, logger_table, disable_ui=disable_ui)


def add_disable_ui_argument(parser: ArgumentParser) -> None:
    """Add the --disable-ui argument to any parser."""
    parser.add_argument(
        "--disable-ui",
        action="store_true",
        help="Disable the user interface",
    )


def add_resolution_argument(parser: ArgumentParser) -> None:
    """Add the --resolution argument to any parser."""
    parser.add_argument(
        "--resolution",
        type=str,
        default="720p",
        help="Set the resolution (e.g., '480p', '720p')",
    )

def parse_arguments() -> Namespace:
    """Parse command-line arguments."""
    parser = ArgumentParser(description="Acquire URL and other arguments.")
    parser.add_argument("url", type=str, help="The URL to process")
    parser.add_argument(
        "--all-episodes",
        action="store_true",
        help="Download all hanime episodes",
    )
    add_disable_ui_argument(parser)
    add_resolution_argument(parser)
    return parser.parse_args()


def main() -> None:
    """Run the script."""
    clear_terminal()
    args = parse_arguments()
    live_manager = initialize_managers(disable_ui=args.disable_ui)

    try:
        with live_manager.live:
            handle_download_process(args.url, live_manager, args)
            live_manager.stop()

    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
