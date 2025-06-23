"""Utilities for fetching pages, managing directories, and clearing the terminal.

It includes functions to handle common tasks such as sending HTTP requests,
parsing HTML, creating download directories, and clearing the terminal, making it
reusable across projects.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

from .config import DOWNLOAD_FOLDER, HANIME_NAME_PATTERN


def validate_url(url: str) -> None:
    """Validate the provided URL against a predefined pattern."""
    if not re.compile(HANIME_NAME_PATTERN, re.IGNORECASE).match(url):
        logging.warning("Invalid URL.")
        sys.exit(0)

    return url.split("/")[-1]


def sanitize_directory_name(directory_name: str) -> str:
    """Sanitize a given directory name by replacing invalid characters with underscores.

    Handles the invalid characters specific to Windows, macOS, and Linux.
    """
    invalid_chars_dict = {
        "nt": r'[\\/:*?"<>|]',  # Windows
        "posix": r"[/:]",       # macOS and Linux
    }
    invalid_chars = invalid_chars_dict.get(os.name)
    return re.sub(invalid_chars, "_", directory_name)


def create_download_directory(directory_name: str) -> str:
    """Create a directory for downloading the video, based on its name."""
    download_path = Path(DOWNLOAD_FOLDER) / sanitize_directory_name(directory_name)

    try:
        Path(download_path).mkdir(parents=True, exist_ok=True)

    except OSError as os_err:
        log_message = f"Error creating directory: {os_err}"
        logging.exception(log_message)
        sys.exit(1)

    return download_path


def clear_terminal() -> None:
    """Clear the terminal screen based on the operating system."""
    commands = {
        "nt": "cls",       # Windows
        "posix": "clear",  # macOS and Linux
    }

    command = commands.get(os.name)
    if command:
        os.system(command)  # noqa: S605
