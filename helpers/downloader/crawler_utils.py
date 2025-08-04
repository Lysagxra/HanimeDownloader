"""Module for extracting media download links from video pages."""

import logging
import re
import sys
from typing import Any

import httpx

from helpers.config import API_URL, HANIME_NAME_PATTERN, RESOLUTION_MAP, VIDEO_URL


def get_episode_id(url: str) -> None:
    """Validate the provided URL against a predefined pattern."""
    if not re.compile(HANIME_NAME_PATTERN, re.IGNORECASE).match(url):
        logging.warning("Invalid URL.")
        sys.exit(0)

    return url.rstrip("/").split("/")[-1]


def get_hanime_info(video_id: str) -> dict[str, Any]:
    """Retrieve video information from hanime.tv using the provided video ID."""
    return httpx.get(f"{API_URL}/video?id={video_id}").json()


def get_all_episodes_ids(info: dict[str, Any]) -> list[str]:
    """Extract the episode IDs (slugs) for a hanime series."""
    episode_infos = info["hentai_franchise_hentai_videos"]
    return [episode_info["slug"] for episode_info in episode_infos]


def generate_all_episode_urls(episode_ids: str) -> str:
    """Generate a list of URLs for the given episode IDs."""
    return [f"{VIDEO_URL}/{episode_id}" for episode_id in episode_ids]


def get_hanime_title(info: dict[str, Any]) -> str:
    """Extract the title of the hanime video from the provided information."""
    return info["hentai_franchise"]["title"]


def fetch_streams(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch the list of available video streams from the provided information."""
    return info["videos_manifest"]["servers"][0]["streams"]


def select_and_validate_stream(
    resolution_choice: str,
    streams: list[dict[str, Any]],
) -> dict[str, Any]:
    """Select and validate the video stream based on the user's resolution choice.

    Attempts to select the stream at the index corresponding to the given resolution.
    If it's invalid, not guest-accessible, or doesn't match the intended height,
    falls back to the first guest-accessible stream with matching height.
    If none is found, falls back to any guest-accessible stream.
    """
    # If the provided resolution is not available, fall back to first index (0)
    resolution_indx = RESOLUTION_MAP.get(resolution_choice, 0)

    # Extract numeric resolution (e.g., 480 from "480p")
    target_height = resolution_choice.lower().replace("p", "")

    def is_valid_stream(stream: dict[str, Any]) -> bool:
        return stream.get("is_guest_allowed", False)

    def match_target_height(stream: dict[str, Any]) -> bool:
        return stream.get("height") == target_height

    # Try the selected index first
    if 0 <= resolution_indx < len(streams):
        stream = streams[resolution_indx]
        if is_valid_stream(stream) and match_target_height(stream):
            return stream

    # Fallback: guest-accessible with matching height
    for stream in streams:
        if is_valid_stream(stream) and match_target_height(stream):
            return stream

    # Fallback: any guest-accessible stream
    for stream in streams:
        if is_valid_stream(stream):
            return stream

    message = "No guest-accessible stream available."
    raise ValueError(message)


def format_filename(
    streams: list[dict[str, Any]],
    video_id: str,
    resolution_choice: str,
) -> str:
    """Format the file name for the video based on the chosen stream resolution."""
    stream = select_and_validate_stream(resolution_choice, streams)
    resolution = stream["height"]
    return f"{video_id}-{resolution}p.mp4"
