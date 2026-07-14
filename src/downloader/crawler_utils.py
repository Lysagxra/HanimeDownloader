"""Module for extracting media download links from video pages."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from typing import Any

import httpx

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from src.config import (
    AES_HEADER,
    AES_KEY,
    AUTH_API_URL,
    DENO_PREAMBLE,
    HANIME_NAME_PATTERN,
    RESOLUTION_MAP,
    VIDEO_URL,
)


def _b64url_encode(data: bytes) -> str:
    from base64 import urlsafe_b64encode
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str | bytes) -> bytes:
    from base64 import urlsafe_b64decode
    if isinstance(data, str):
        data = data.encode("ascii", errors="ignore")
    return urlsafe_b64decode(data.ljust((len(data) // 4 + 1) * 4, b"="))


def encrypt_token(payload: dict[str, Any]) -> str:
    """Encrypt a payload dict using AES-256-GCM (mirrors hanime.tv handshake)."""
    plaintext = json.dumps(payload, separators=(",", ":")).encode()
    iv = get_random_bytes(12)
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=iv)
    cipher.update(AES_HEADER)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)

    result = {
        "v": 1,
        "alg": "AES-256-GCM",
        "iv": _b64url_encode(iv),
        "tag": _b64url_encode(tag),
        "data": _b64url_encode(ciphertext),
    }
    return _b64url_encode(json.dumps(result, separators=(",", ":")).encode())


def decrypt_token(token: str) -> dict[str, Any]:
    """Decrypt an AES-256-GCM-encrypted handshake token."""
    decoded = json.loads(_b64url_decode(token))
    iv = _b64url_decode(decoded["iv"])
    tag = _b64url_decode(decoded["tag"])
    data = _b64url_decode(decoded["data"])
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=iv)
    cipher.update(AES_HEADER)
    plaintext = cipher.decrypt_and_verify(data, tag)
    return json.loads(plaintext.decode())


def get_episode_id(url: str) -> str | None:
    """Validate the provided URL against a predefined pattern."""
    if not re.compile(HANIME_NAME_PATTERN, re.IGNORECASE).match(url):
        logging.warning("Invalid URL.")
        sys.exit(0)

    return url.rstrip("/").split("/")[-1]


def _find_vendor_js_url(page_html: str) -> str:
    """Extract the vendor JS URL (containing embedded WASM) from the page HTML."""
    match = re.search(
        r'<script[^>]*src="(https://hanime-cdn\.com/js/vendor\.[^"]+)"',
        page_html,
    )
    if not match:
        msg = "Could not find vendor JS URL on page"
        raise ValueError(msg)
    return match.group(1)


def _generate_credentials(vendor_js: str) -> tuple[str, int]:
    """Run vendor JS (with embedded WASM) in Deno to extract ssignature and stime."""
    script = DENO_PREAMBLE + vendor_js
    try:
        result = subprocess.run(
            ["deno", "run", "-"],
            input=script,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        msg = (
            "Deno is required but not found. "
            "Install it from https://deno.land"
        )
        raise RuntimeError(msg) from None
    except subprocess.TimeoutExpired:
        msg = "Deno WASM auth script timed out"
        raise RuntimeError(msg) from None

    if result.returncode != 0:
        msg = f"Deno WASM auth failed: {result.stderr.strip()}"
        raise RuntimeError(msg)

    lines = result.stdout.strip().split("\n", 1)
    creds: dict[str, str] = {}
    for line in lines:
        if " " in line:
            key, val = line.split(" ", 1)
            creds[key] = val

    ssignature = creds.get("ssignature", "")
    stime_str = creds.get("stime", "0")
    return ssignature, int(stime_str)


def get_hanime_info(video_id: str) -> dict[str, Any]:
    """Retrieve video stream information via the new handshake API."""
    # Fetch the video page to get vendor JS URL and page content
    page_url = f"{VIDEO_URL}/{video_id}"
    page_resp = httpx.get(
        page_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    page_resp.raise_for_status()
    page_html = page_resp.text

    # Extract video title from page
    title_match = re.search(r"<h1[^>]+?>([^<]+)", page_html)
    hanime_title = title_match.group(1).strip() if title_match else video_id

    # Download the vendor JS containing embedded WASM
    vendor_js_url = _find_vendor_js_url(page_html)
    vendor_resp = httpx.get(
        vendor_js_url,
        headers={
            "Referer": "https://hanime.tv/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    vendor_resp.raise_for_status()
    vendor_js = vendor_resp.text

    # Generate handshake credentials via Deno + WASM
    ssignature, stime = _generate_credentials(vendor_js)

    # Build and encrypt handshake payload
    payload = encrypt_token({
        "timestamp_unix": int(time.time()),
        "directive": "htv_player_handshake",
        "slug": video_id,
    })

    # Perform handshake
    handshake_resp = httpx.post(
        f"{AUTH_API_URL}/api/v11/handshake",
        json={"token": payload},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://hanime.tv",
            "Referer": "https://hanime.tv/",
            "X-Csrf-Token": "null",
            "X-Signature": ssignature,
            "X-Time": str(stime),
            "X-Signature-Version": "web2",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    handshake_resp.raise_for_status()

    # Decrypt the x-token header to get stream sources
    x_token = handshake_resp.headers.get("X-Token")
    if not x_token:
        msg = "Handshake response missing X-Token header"
        raise ValueError(msg)

    manifest = decrypt_token(x_token)

    return {
        "title": hanime_title,
        "slug": video_id,
        "sources": manifest.get("sources", []),
    }


def get_all_episodes_ids(info: dict[str, Any]) -> list[str]:
    """Extract the episode IDs (slugs) for a hanime series.

    NOTE: The new hanime.tv API no longer returns franchise episode data
    in the handshake response. This function returns an empty list as
    a placeholder.
    """
    logging.warning(
        "All-episodes mode is not supported with the current hanime.tv API. "
        "Only the current episode will be downloaded."
    )
    return [info.get("slug", "")] if info.get("slug") else []


def generate_all_episode_urls(episode_ids: str) -> str:
    """Generate a list of URLs for the given episode IDs."""
    return [f"{VIDEO_URL}/{episode_id}" for episode_id in episode_ids]


def get_hanime_title(info: dict[str, Any]) -> str:
    """Extract the title of the hanime video from the provided information."""
    return info["title"]


def fetch_streams(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch the list of available video streams from the provided information."""
    return info["sources"]


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
    resolution_indx = RESOLUTION_MAP.get(resolution_choice, 0)

    target_height = resolution_choice.lower().replace("p", "")

    def is_valid_stream(stream: dict[str, Any]) -> bool:
        return stream.get("kind") in ("normal", None)

    def match_target_height(stream: dict[str, Any]) -> bool:
        label = stream.get("label", "")
        return target_height in label

    if 0 <= resolution_indx < len(streams):
        stream = streams[resolution_indx]
        if is_valid_stream(stream) and match_target_height(stream):
            return stream

    for stream in streams:
        if is_valid_stream(stream) and match_target_height(stream):
            return stream

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
    resolution = stream.get("label", resolution_choice).lower()
    return f"{video_id}-{resolution}.mp4"
