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
from urllib.parse import urljoin

import httpx
import m3u8
from Crypto.Util.Padding import pad, unpad
from Cryptodome.Cipher import AES

from src.config import MAX_DELAY, MAX_RETRIES, MAX_WORKERS, VIDEO_URL
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

    def _fetch_playlist(self, stream_url: str) -> tuple[m3u8.M3U8, bytes]:
        """Fetch the stream playlist and its decryption key."""
        response = httpx.get(stream_url)
        response.raise_for_status()

        m3u8_playlist = m3u8.loads(response.text)
        if not m3u8_playlist.keys or m3u8_playlist.keys[0] is None:
            self.live_manager("No decryption key", "Missing decryption key in playlist")
            sys.exit(1)

        key_uri = m3u8_playlist.keys[0].uri
        key_data = httpx.get(key_uri).content
        return m3u8_playlist, key_data

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
            stream_url = selected_stream.get("src") or selected_stream["url"]
            if not stream_url.startswith(("http://", "https://")):
                stream_url = urljoin(VIDEO_URL, stream_url)

            response = httpx.get(stream_url)
            response.raise_for_status()

        except (KeyError, ValueError) as err:
            log_and_exit(type(err).__name__, str(err))

        except httpx.RequestError as req_err:
            log_and_exit("Request error", req_err)

        m3u8_playlist, key_data = self._fetch_playlist(stream_url)
        segment_uris = m3u8_playlist.segments.uri
        media_sequence = m3u8_playlist.media_sequence  # pylint: disable=no-member

        final_path = Path(self._download_path) / filename
        self._download_and_decrypt_segments(
            final_path, segment_uris, key_data, media_sequence,
        )

    def _download_segment(
        self,
        segment_uri: str,
        segment_index: int,
        decrypt_fn: callable,
    ) -> bytes | None:
        """Download and decrypt a single segment with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                response = httpx.get(segment_uri)
                response.raise_for_status()

            except (httpx.HTTPStatusError, httpx.RequestError):
                if attempt < MAX_RETRIES - 1:
                    backoff_delay = 2 ** (attempt + 1) + random.uniform(1, 3)  # noqa: S311
                    delay = min(backoff_delay, MAX_DELAY)
                    time.sleep(delay)
                    self.live_manager.update_log(
                        "Request error",
                        f"Retrying to download segment {segment_uri}... "
                        f"({attempt + 1}/{MAX_RETRIES})",
                    )
                    continue

            else:
                return decrypt_fn(response.content, segment_index)

        self.live_manager.update_log(
            "Failed segment download",
            f"Failed to download {segment_uri}",
        )
        return None

    def _download_and_decrypt_segments(
        self,
        final_path: str,
        segment_uris: list[str],
        key_data: bytes,
        media_sequence: int,
    ) -> None:
        """Download and decrypt video segments concurrently and write them in order."""
        num_segments = len(segment_uris)
        task = self.live_manager.add_task()
        results: list[bytes | None] = [None] * num_segments

        def _decrypt_with_iv(data: bytes, segment_index: int) -> bytes:
            iv = (media_sequence + segment_index).to_bytes(16, "big")
            decryptor = AES.new(key_data, AES.MODE_CBC, iv=iv)

            if len(data) % decryptor.block_size != 0:
                padded_data = pad(data, decryptor.block_size)
                decrypted_data = decryptor.decrypt(padded_data)

                try:
                    return unpad(decrypted_data, decryptor.block_size)

                except ValueError:
                    return decrypted_data

            return decryptor.decrypt(data)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._download_segment, uri, segment_id, _decrypt_with_iv,
                ): segment_id
                for segment_id, uri in enumerate(segment_uris)
            }

            for current_segment, future in enumerate(as_completed(futures)):
                segment_id = futures[future]
                results[segment_id] = future.result()
                completed = ((current_segment + 1) / num_segments) * 100
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
