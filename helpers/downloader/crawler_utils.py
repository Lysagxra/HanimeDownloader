"""Module for extracting media download links from video pages."""

from typing import Any

import httpx

from helpers.config import API_URL, RESOLUTION_MAP


def get_hanime_info(video_id: str) -> dict[str, Any]:
    """Retrieve video information from hanime.tv using the provided video ID."""
    return httpx.get(f"{API_URL}/video?id={video_id}").json()


def get_hanime_title(info: dict[str, Any]) -> str:
    """Extract the title of the hentai video from the provided information."""
    return info["hentai_franchise"]["title"]


def fetch_streams(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch the list of available video streams from the provided information."""
    return info["videos_manifest"]["servers"][0]["streams"]


def format_filename(
    streams: list[dict[str, Any]], video_id: str, resolution_choice: str,
) -> str:
    """Format the file name for the video based on the chosen stream resolution."""
    resolution_indx = RESOLUTION_MAP[resolution_choice]
    resolution = streams[resolution_indx]["height"]
    return f"{video_id}-{resolution}p.mp4"
