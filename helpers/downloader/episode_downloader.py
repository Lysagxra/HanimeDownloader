"""Module that provides tools to manage the downloading of episodes from hanime.tv.

It supports retry mechanisms, progress tracking, and error handling for a robust
download experience.
"""

from __future__ import annotations

import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import m3u8
from Cryptodome.Cipher import AES

from helpers.config import MAX_WORKERS, RESOLUTION_CHOICE
from helpers.general_utils import create_download_directory, validate_url

from .crawler_utils import (
    fetch_streams,
    format_filename,
    get_hanime_info,
    get_hanime_title,
)

if TYPE_CHECKING:
    from Cryptodome.Cipher._mode_cbc import CbcMode

    from helpers.managers.live_manager import LiveManager


class EpisodeDownloader:
    """Class to handle downloading and decrypting an episode from hanime.tv."""

    def __init__(
        self,
        url: str,
        live_manager: LiveManager,
        max_workers: int = MAX_WORKERS,
    ) -> None:
        """Initialize the EpisodeDownloader instance."""
        self.episode_id = validate_url(url)
        self.live_manager = live_manager
        self.max_workers = max_workers

        # Extract the hanime info and video segments
        episode_info = get_hanime_info(self.episode_id)
        self.streams = fetch_streams(episode_info)

        # Create the download directory
        self.hanime_title = get_hanime_title(episode_info)
        self.download_path = create_download_directory(self.hanime_title)

    def download_segment(
        self,
        segment_uri: str,
        decryptor: CbcMode,
        retries: int = 5,
    ) -> bytes | None:
        """Download and decrypt a single segment with retry logic."""
        for attempt in range(retries):
            try:
                response = httpx.get(segment_uri)
                response.raise_for_status()
                return decryptor.decrypt(response.content)

            except (httpx.HTTPStatusError, httpx.RequestError):
                if attempt < retries - 1:
                    delay = 3 ** (attempt + 1) + random.uniform(1, 3)  # noqa: S311
                    time.sleep(delay)
                    self.live_manager.update_log(
                        "Request error",
                        f"Retrying to download {self.episode_id}... "
                        f"({attempt + 1}/{retries})",
                    )
                    continue

        self.live_manager.update_log(
            "Failed segment download",
            f"Failed to download {segment_uri}",
        )
        return None

    def download_and_decrypt_segments(
        self,
        final_path: str,
        segment_uris: list[str],
        decryptor: CbcMode,
    ) -> None:
        """Download and decrypt video segments concurrently and write them in order."""
        total_segments = len(segment_uris)
        task = self.live_manager.add_task()
        results: list[bytes | None] = [None] * total_segments

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.download_segment, uri, decryptor): segment_id
                for segment_id, uri in enumerate(segment_uris)
            }

            for current_segment, future in enumerate(as_completed(futures)):
                segment_id = futures[future]
                results[segment_id] = future.result()
                completed = ((current_segment + 1) / total_segments) * 100
                self.live_manager.update_task(task, completed=completed)

        # Write all segments in order
        with Path(final_path).open("ab") as video:
            for segment_id, segment_data in enumerate(results):
                if segment_data is None:
                    self.live_manager.update_log(
                        "Missing video segment",
                        f"Segment {segment_id} is missing, skipping.",
                    )
                    continue

                video.write(segment_data)

    def download(self) -> None:
        """Process the video stream and downloads the video."""

        def log_and_exit(event: str, message: str) -> None:
            self.live_manager.update_log(event, message)
            sys.exit(1)

        filename = format_filename(self.streams, self.episode_id)
        self.live_manager.add_overall_task(filename, num_tasks=1)

        try:
            stream_url = self.streams[RESOLUTION_CHOICE]["url"]
            m3u8_playlist = m3u8.loads(httpx.get(stream_url).text)
            segment_uris = m3u8_playlist.segments.uri
            final_path = Path(self.download_path) / filename

        except KeyError as key_err:
            log_and_exit("Key error", key_err)

        except httpx.RequestError as req_err:
            log_and_exit("Request error", req_err)

        except ValueError as val_err:
            log_and_exit("Value error", val_err)

        if not m3u8_playlist.keys or m3u8_playlist.keys[0] is None:
            log_and_exit("No decryption key", "Missing decryption key in playlist")

        key_uri = m3u8_playlist.keys[0].uri
        key_data = httpx.get(key_uri).content
        decryptor = AES.new(key_data, AES.MODE_CBC)
        self.download_and_decrypt_segments(final_path, segment_uris, decryptor)
