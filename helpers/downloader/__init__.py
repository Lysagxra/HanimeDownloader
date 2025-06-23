"""Utility modules and functions to support the main application.

These utilities include functions for downloading, file management, URL handling,
progress tracking, and more.

Modules:
    - crawler_utils: Module with utility functions for crawling and handling URLs.
    - episode_downloader: Manages the downloading of individual episodes.

This package is designed to be reusable and modular, allowing its components
to be easily imported and used across different parts of the application.
"""

# managers/__init__.py

__all__ = [
    "crawler_utils",
    "episode_downloader",
]
