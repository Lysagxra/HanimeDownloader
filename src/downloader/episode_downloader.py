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
from typing import TYPE_CHECKING, Any

import httpx
import m3u8
from Crypto.Util.Padding import pad, unpad
from Cryptodome.Cipher import AES

from src.config import MAX_WORKERS
from src.file_utils import create_download_directory

from .crawler_utils import (
    fetch_streams,
    format_filename,
    get_episode_id,
    get_hanime_info,
    get_hanime_title,
    select_and_validate_stream,
)

if TYPE_CHECKING:
    from argparse import Namespace

    from Cryptodome.Cipher._mode_cbc import CbcMode

    from src.managers.live_manager import LiveManager


class EpisodeDownloader:
    """Class to handle downloading and decrypting an episode from hanime.tv."""

    def __init__(
        self,
        url: str,
        live_manager: LiveManager,
        args: Namespace,
        max_workers: int = MAX_WORKERS,
    ) -> None:
        """Initialize the EpisodeDownloader instance."""
        self.episode_id = get_episode_id(url)
        self.live_manager = live_manager
        self.args = args
        self.max_workers = max_workers

        # Lazy-loaded later
        self._episode_info: dict[str, Any] | None = None
        self._streams: dict[str, Any] | None = None
        self._download_path: Path | None = None

    def init_download(self) -> None:
        """Initialize episode metadata, stream data, and download directory.

        This method retrieves detailed episode information and available stream data
        based on the episode ID. It also creates and stores the appropriate download
        directory using the episode's title.
        """
        self._episode_info = get_hanime_info(self.episode_id)
        self._streams = fetch_streams(self._episode_info)
        hanime_title = get_hanime_title(self._episode_info)
        self._download_path = create_download_directory(
            hanime_title, custom_path=self.args.custom_path,
        )

    def download(self) -> None:
        """Process the video stream and downloads the video."""

        def log_and_exit(event: str, message: str) -> None:
            self.live_manager.update_log(event, message)
            sys.exit(1)

        # Initialize the download process
        self.init_download()

        # Format the episode filename
        filename = format_filename(self._streams, self.episode_id, self.args.resolution)
        self.live_manager.add_overall_task(filename, num_tasks=1)

        try:
            selected_stream = select_and_validate_stream(
                self.args.resolution,
                self._streams,
            )
            stream_url = selected_stream["url"]

            response = httpx.get(stream_url)
            response.raise_for_status()

            m3u8_playlist = m3u8.loads(response.text)
            segment_uris = m3u8_playlist.segments.uri

        except (KeyError, ValueError) as err:
            log_and_exit(type(err).__name__, str(err))

        except httpx.RequestError as req_err:
            log_and_exit("Request error", req_err)

        if not m3u8_playlist.keys or m3u8_playlist.keys[0] is None:
            log_and_exit("No decryption key", "Missing decryption key in playlist")

        key_uri = m3u8_playlist.keys[0].uri
        key_data = httpx.get(key_uri).content
        decryptor = AES.new(key_data, AES.MODE_CBC)

        final_path = Path(self._download_path) / filename
        self._download_and_decrypt_segments(final_path, segment_uris, decryptor)

    # Private methods
    def _decrypt_with_padding(
        self, data: bytes, decryptor: CbcMode, segment_uri: str,
    ) -> bytes:
        """Decrypt the given data with padding handling."""
        padded_data = pad(data, decryptor.block_size)
        decrypted_data = decryptor.decrypt(padded_data)

        try:
            return unpad(decrypted_data, decryptor.block_size)

        except ValueError:
            self.live_manager.update_log(
                "Decryption error",
                f"Padding error for segment {segment_uri}. "
                "Proceeding with partial data.",
            )
            return decrypted_data

    def _download_segment(
        self,
        segment_uri: str,
        decryptor: CbcMode,
        retries: int = 10,
        max_delay: int = 30,
    ) -> bytes | None:
        """Download and decrypt a single segment with retry logic."""
        for attempt in range(retries):
            try:
                response = httpx.get(segment_uri)
                response.raise_for_status()

            except (httpx.HTTPStatusError, httpx.RequestError):
                if attempt < retries - 1:
                    backoff_delay = 2 ** (attempt + 1) + random.uniform(1, 3)  # noqa: S311
                    delay = min(backoff_delay, max_delay)
                    time.sleep(delay)
                    self.live_manager.update_log(
                        "Request error",
                        f"Retrying to download segment {segment_uri}... "
                        f"({attempt + 1}/{retries})",
                    )
                    continue

            else:
                data = response.content

                # If the data length is not a multiple of the block size, apply
                # padding before decryption
                if len(data) % decryptor.block_size != 0:
                    return self._decrypt_with_padding(data, decryptor, segment_uri)

                return decryptor.decrypt(data)

        self.live_manager.update_log(
            "Failed segment download",
            f"Failed to download {segment_uri}",
        )
        return None

    def _download_and_decrypt_segments(
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
                executor.submit(self._download_segment, uri, decryptor): segment_id
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
